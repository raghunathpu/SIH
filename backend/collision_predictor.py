"""
FleetMind — Predictive Collision Detection

Each RobotAgent owns one CollisionPredictor instance.
The predictor uses the robot's own state and its locally-maintained
peer_knowledge (built exclusively from received MessageBus messages)
to project future trajectories and compute:

    * Minimum predicted separation   (cells)
    * Time To Collision              (seconds of simulated time)
    * Risk level                     (SAFE / LOW_RISK / WARNING / CRITICAL)
    * Conflict position              (grid cell where closest approach occurs)
    * Confidence                     (0.0 – 1.0, degrades with stale peer data)

This module only answers "Is there a predicted conflict, how severe, when,
and where?"  It does NOT decide how to react.  Resolution (wait/yield/reroute)
is handled by the existing conflict_resolver and deadlock_detector modules.

Design principles
-----------------
* No global state — all input is passed explicitly.
* Nearby-only evaluation — robots outside DETECTION_RADIUS are skipped cheaply
  before any trajectory math is done.
* Path-aware trajectories — uses the planned A* path, not straight-line
  extrapolation, so predicted motion follows the actual route.
* Relative-motion TTC — separation is evaluated at each future tick;
  two diverging robots will correctly show TTC = None.
* All thresholds live in models.py; nothing is hard-coded here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from models import (
    DETECTION_RADIUS,
    PREDICTION_HORIZON_TICKS,
    ROBOT_RADIUS,
    SAFETY_MARGIN,
    TICKS_PER_MOVE,
    TICKS_PER_SECOND,
    PeerKnowledge,
    Position,
    RobotStatus,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS (derived — do not change here, change in models.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Two robots are in an unsafe spatial relationship when their centres are
# closer than this distance (in grid-cell units).
_UNSAFE_DISTANCE: float = ROBOT_RADIUS * 2 + SAFETY_MARGIN   # ≈ 1.1 cells

# Risk thresholds expressed as fractions of the prediction horizon (in ticks).
_CRITICAL_TTC_TICKS: float = PREDICTION_HORIZON_TICKS * 0.30   # ≤ 30 % of horizon
_WARNING_TTC_TICKS:  float = PREDICTION_HORIZON_TICKS * 0.60   # ≤ 60 % of horizon


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENUMERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CollisionRisk(Enum):
    """
    Severity of a predicted collision.

    SAFE      — no predicted encounter within the horizon.
    LOW_RISK  — trajectories approach but minimum separation stays above
                the unsafe threshold.
    WARNING   — TTC is within 30–60 % of the prediction horizon.
    CRITICAL  — TTC is within 30 % of the horizon, OR current separation
                is already below the unsafe distance.
    """
    SAFE     = "SAFE"
    LOW_RISK = "LOW_RISK"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DATA STRUCTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class CollisionPrediction:
    """
    The result of one robot-pair prediction pass.

    Fields
    ------
    robot_id              : the robot that ran the prediction
    other_robot_id        : the peer being evaluated
    risk_level            : CollisionRisk enum value
    time_to_collision     : seconds until unsafe separation (None = no collision
                            predicted within the horizon)
    minimum_predicted_distance : smallest separation found across the horizon (cells)
    conflict_position     : grid cell (as Position) where closest approach occurs
    confidence            : 0.0–1.0; degrades when peer data is stale or path is short
    timestamp_tick        : simulation tick when the prediction was made
    """
    robot_id: str
    other_robot_id: str
    risk_level: CollisionRisk
    time_to_collision: Optional[float]              # seconds, None if SAFE/LOW_RISK
    minimum_predicted_distance: float               # cells
    conflict_position: Optional[Position]           # cell of closest approach
    confidence: float                               # 0.0 – 1.0
    timestamp_tick: int

    def to_dict(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "other_robot_id": self.other_robot_id,
            "risk_level": self.risk_level.value,
            "time_to_collision": round(self.time_to_collision, 3) if self.time_to_collision is not None else None,
            "minimum_predicted_distance": round(self.minimum_predicted_distance, 3),
            "conflict_position": self.conflict_position.to_tuple() if self.conflict_position else None,
            "confidence": round(self.confidence, 2),
            "timestamp_tick": self.timestamp_tick,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRAJECTORY PREDICTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━



def _build_trajectory(
    start_x: float,
    start_y: float,
    planned_path: List[Position],
    horizon_ticks: int,
) -> List[Tuple[float, float]]:
    """
    Correct, step-origin-aware trajectory builder.
    Returns a list of (x, y) of length horizon_ticks + 1 (tick 0 … horizon).
    """
    trajectory: List[Tuple[float, float]] = []
    path = list(planned_path)

    # Current interpolation segment
    origin_x, origin_y = start_x, start_y      # where this step started
    target_x, target_y = start_x, start_y      # where this step is heading
    ticks_in_step = 0                           # ticks elapsed within current step
    step_active = False

    if path:
        target_x, target_y = float(path[0].x), float(path[0].y)
        step_active = True

    for tick in range(horizon_ticks + 1):
        if step_active:
            frac = ticks_in_step / TICKS_PER_MOVE
            px = origin_x + frac * (target_x - origin_x)
            py = origin_y + frac * (target_y - origin_y)
            trajectory.append((px, py))

            ticks_in_step += 1
            if ticks_in_step >= TICKS_PER_MOVE:
                # Step complete — advance to next waypoint
                origin_x, origin_y = target_x, target_y
                path.pop(0) if path else None
                ticks_in_step = 0
                if path:
                    target_x, target_y = float(path[0].x), float(path[0].y)
                else:
                    step_active = False
        else:
            # Stationary
            trajectory.append((origin_x, origin_y))

    return trajectory


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RISK CLASSIFICATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def classify_risk(
    ttc_ticks: Optional[int],
    min_separation: float,
) -> CollisionRisk:
    """
    Map (time_to_collision, minimum_separation) → CollisionRisk.

    Parameters
    ----------
    ttc_ticks : int | None
        Tick offset within the prediction horizon when separation first drops
        below _UNSAFE_DISTANCE.  None means no unsafe separation predicted.
    min_separation : float
        Smallest separation observed across the entire horizon.
    """
    if min_separation < _UNSAFE_DISTANCE:
        # A genuinely unsafe separation is predicted somewhere within the
        # horizon — this is at minimum a WARNING no matter how far out the
        # TTC is; TTC only decides whether it escalates to CRITICAL.
        # (Previously, an unsafe encounter with ttc_ticks beyond
        # _WARNING_TTC_TICKS but still inside the horizon fell all the way
        # through to LOW_RISK, silently suppressing real predicted
        # collisions such as head-on or crossing-path cases whose closest
        # approach happened to land in the last third of the horizon.)
        if ttc_ticks is None or ttc_ticks <= _CRITICAL_TTC_TICKS:
            return CollisionRisk.CRITICAL
        return CollisionRisk.WARNING

    # Separation never goes below unsafe threshold
    if min_separation < _UNSAFE_DISTANCE * 1.5:
        # Close approach but not unsafe
        return CollisionRisk.LOW_RISK

    return CollisionRisk.SAFE


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN PREDICTOR CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CollisionPredictor:
    """
    Per-robot predictive collision detector.

    Each RobotAgent owns exactly one instance.  The predictor uses only data
    that the robot already knows locally (its own state + peer_knowledge built
    from received messages).

    Usage::

        # In RobotAgent.__init__:
        self.collision_predictor = CollisionPredictor(robot_id)

        # In RobotAgent.tick_async (after message processing):
        predictions = self.collision_predictor.predict(
            my_render_x    = self.render_x,
            my_render_y    = self.render_y,
            my_path        = self.planned_path,
            my_velocity    = self.velocity,
            peer_knowledge = self.peer_knowledge,
            current_tick   = current_tick,
        )
    """

    def __init__(self, robot_id: str):
        self.robot_id = robot_id

    # ── public API ────────────────────────────────────────────────────────

    def predict(
        self,
        my_render_x: float,
        my_render_y: float,
        my_path: List[Position],
        my_velocity: float,
        peer_knowledge: Dict[str, "PeerKnowledge"],
        current_tick: int,
        horizon_ticks: int = PREDICTION_HORIZON_TICKS,
        detection_radius: float = DETECTION_RADIUS,
    ) -> List[CollisionPrediction]:
        """
        Predict collisions against all nearby peers.

        Only peers within *detection_radius* (euclidean distance in cells)
        are evaluated.  This keeps the inner loop O(nearby) rather than
        O(fleet size).

        Returns
        -------
        list[CollisionPrediction]
            One entry per peer that produced a non-SAFE result.
            An empty list means no predicted conflicts.
        """
        predictions: List[CollisionPrediction] = []

        if my_velocity == 0.0 and not my_path:
            # Stationary with no path — quick exit, cannot be in a closing
            # trajectory with anyone (though they could be closing on us;
            # that will be caught when the peer runs its own prediction).
            return predictions

        # Build own trajectory once (reused for every peer comparison)
        my_traj = _build_trajectory(my_render_x, my_render_y, my_path, horizon_ticks)

        for peer_id, peer in peer_knowledge.items():
            if peer_id == self.robot_id:
                continue
            if peer.status in (RobotStatus.UNAVAILABLE, RobotStatus.CHARGING):
                continue
            if peer.position is None:
                continue

            # ── Cheap proximity filter ────────────────────────────────────
            dx = float(peer.position.x) - my_render_x
            dy = float(peer.position.y) - my_render_y
            if math.hypot(dx, dy) > detection_radius:
                continue

            prediction = self._predict_pair(
                my_traj=my_traj,
                my_render_x=my_render_x,
                my_render_y=my_render_y,
                peer=peer,
                peer_id=peer_id,
                current_tick=current_tick,
                horizon_ticks=horizon_ticks,
            )

            if prediction.risk_level != CollisionRisk.SAFE:
                predictions.append(prediction)

        return predictions

    # ── internals ─────────────────────────────────────────────────────────

    def _predict_pair(
        self,
        my_traj: List[Tuple[float, float]],
        my_render_x: float,
        my_render_y: float,
        peer: "PeerKnowledge",
        peer_id: str,
        current_tick: int,
        horizon_ticks: int,
    ) -> CollisionPrediction:
        """Run full trajectory comparison for a single (self, peer) pair."""

        # Peer start position — use render position if available (more accurate
        # mid-transit), fall back to grid position.
        peer_x = float(peer.position.x)
        peer_y = float(peer.position.y)

        # Build peer trajectory
        peer_traj = _build_trajectory(
            peer_x,
            peer_y,
            peer.planned_path,
            horizon_ticks,
        )

        # ── Sweep across the horizon ──────────────────────────────────────
        min_sep = float("inf")
        ttc_ticks: Optional[int] = None
        conflict_pos: Optional[Tuple[float, float]] = None

        for t, ((mx, my), (px, py)) in enumerate(zip(my_traj, peer_traj)):
            sep = math.hypot(mx - px, my - py)
            if sep < min_sep:
                min_sep = sep

            if ttc_ticks is None and sep < _UNSAFE_DISTANCE:
                ttc_ticks = t
                conflict_pos = (mx, my)

        # ── Convert conflict position to nearest grid cell ────────────────
        conflict_position: Optional[Position] = None
        if conflict_pos is not None:
            conflict_position = Position(
                round(conflict_pos[0]),
                round(conflict_pos[1]),
            )

        # ── TTC in seconds ────────────────────────────────────────────────
        ttc_seconds: Optional[float] = None
        if ttc_ticks is not None:
            ttc_seconds = ttc_ticks / TICKS_PER_SECOND

        # ── Confidence ────────────────────────────────────────────────────
        # Degrades with stale peer data and short peer paths.
        staleness = min(1.0, (current_tick - peer.last_update_tick) / 20.0)
        path_coverage = min(1.0, len(peer.planned_path) / max(1, horizon_ticks / TICKS_PER_MOVE))
        confidence = max(0.0, (1.0 - staleness * 0.7) * (0.4 + 0.6 * path_coverage))

        # ── Risk classification ────────────────────────────────────────────
        risk = classify_risk(ttc_ticks, min_sep)

        return CollisionPrediction(
            robot_id=self.robot_id,
            other_robot_id=peer_id,
            risk_level=risk,
            time_to_collision=ttc_seconds,
            minimum_predicted_distance=min_sep,
            conflict_position=conflict_position,
            confidence=confidence,
            timestamp_tick=current_tick,
        )