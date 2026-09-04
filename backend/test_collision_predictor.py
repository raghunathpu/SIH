"""
FleetMind — Predictive Collision Detector: Deterministic Unit Tests

These tests exercise collision_predictor.py directly.
No engine, no message bus, no async required.

Run with:
    cd /home/yasaswi/SIH
    python3 -m pytest backend/test_collision_predictor.py -v

Or run directly:
    cd /home/yasaswi/SIH/backend
    python3 test_collision_predictor.py
"""

from __future__ import annotations

import math
import sys
import os

# Allow running from the backend directory or the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from models import Position, PeerKnowledge, RobotStatus, TICKS_PER_MOVE
from collision_predictor import (
    CollisionPredictor,
    CollisionPrediction,
    CollisionRisk,
    _build_trajectory,
    _UNSAFE_DISTANCE,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_peer(
    robot_id: str,
    position: Position,
    planned_path: list,
    status: RobotStatus = RobotStatus.MOVING,
    last_update_tick: int = 0,
) -> PeerKnowledge:
    """Build a PeerKnowledge with only the fields the predictor uses."""
    pk = PeerKnowledge(robot_id=robot_id, last_update_tick=last_update_tick)
    pk.position = position
    pk.planned_path = planned_path
    pk.status = status
    return pk


def _run(
    my_pos: Position,
    my_path: list,
    peer_id: str,
    peer_pos: Position,
    peer_path: list,
    current_tick: int = 0,
    horizon: int = 20,
) -> "CollisionPrediction | None":
    """
    Convenience wrapper: run prediction for one robot-pair.
    Returns the CollisionPrediction (or None if peer is filtered out).
    """
    predictor = CollisionPredictor("R1")
    peer = _make_peer(peer_id, peer_pos, peer_path)
    predictions = predictor.predict(
        my_render_x=float(my_pos.x),
        my_render_y=float(my_pos.y),
        my_path=my_path,
        my_velocity=1.0,
        peer_knowledge={peer_id: peer},
        current_tick=current_tick,
        horizon_ticks=horizon,
        detection_radius=50.0,   # large radius so no peer is filtered in tests
    )
    return predictions[0] if predictions else None


def _predicted_collision(result) -> bool:
    """True when a non-SAFE, non-None prediction was returned."""
    if result is None:
        return False
    return result.risk_level in (CollisionRisk.WARNING, CollisionRisk.CRITICAL)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRAJECTORY BUILDER SANITY CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_trajectory_builder_empty_path():
    """A robot with no path should stay at start for the whole horizon."""
    traj = _build_trajectory(3.0, 5.0, [], horizon_ticks=8)
    assert len(traj) == 9, f"Expected 9 points, got {len(traj)}"
    for x, y in traj:
        assert (x, y) == (3.0, 5.0), f"Expected stationary at (3,5), got ({x},{y})"
    print("PASS  trajectory_builder_empty_path")


def test_trajectory_builder_one_step():
    """A robot moving one cell to the right should interpolate smoothly."""
    path = [Position(1, 0)]
    traj = _build_trajectory(0.0, 0.0, path, horizon_ticks=TICKS_PER_MOVE)
    # At tick 0: (0,0). At tick TICKS_PER_MOVE: (1,0).
    assert traj[0] == (0.0, 0.0), f"Start wrong: {traj[0]}"
    # The robot should have arrived at (1, 0) by the end of the step
    final_x, final_y = traj[TICKS_PER_MOVE]
    assert abs(final_x - 1.0) < 1e-9 and abs(final_y - 0.0) < 1e-9, \
        f"End wrong: {traj[TICKS_PER_MOVE]}"
    print("PASS  trajectory_builder_one_step")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 1 — Head-on collision (R1 → ← R2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_head_on():
    """
    R1 at (0, 5) moving right → along y=5
    R2 at (8, 5) moving left  ← along y=5
    They will meet around (4, 5).
    Expected: predicted collision = TRUE, risk >= WARNING.
    """
    r1_path = [Position(x, 5) for x in range(1, 12)]
    r2_path = [Position(x, 5) for x in range(7, -1, -1)]

    result = _run(
        my_pos=Position(0, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(8, 5), peer_path=r2_path,
    )
    assert result is not None, "Expected a CollisionPrediction, got None"
    assert _predicted_collision(result), (
        f"Expected WARNING or CRITICAL, got {result.risk_level.value} | "
        f"min_sep={result.minimum_predicted_distance:.3f} | ttc={result.time_to_collision}"
    )
    print(f"PASS  head_on | risk={result.risk_level.value} | "
          f"TTC={result.time_to_collision}s | "
          f"min_sep={result.minimum_predicted_distance:.3f}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 2 — Moving away (R1 → R2 →, R2 already ahead)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_moving_away():
    """
    R1 at (0,5) moving right.
    R2 at (4,5) moving right at the same speed.
    Separation stays constant — no collision.
    Expected: SAFE (no WARNING or CRITICAL).
    """
    r1_path = [Position(x, 5) for x in range(1, 20)]
    r2_path = [Position(x, 5) for x in range(5, 20)]

    result = _run(
        my_pos=Position(0, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(4, 5), peer_path=r2_path,
    )
    is_collision = _predicted_collision(result)
    assert not is_collision, (
        f"Expected SAFE but got {result.risk_level.value if result else None}"
    )
    print(f"PASS  moving_away | risk={result.risk_level.value if result else 'SAFE (None)'}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 3 — Parallel robots with sufficient separation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_parallel_safe():
    """
    R1 at (0,5) moving right along y=5.
    R2 at (0,8) moving right along y=8.
    Lateral separation = 3 cells, well above UNSAFE_DISTANCE ≈ 1.1 cells.
    Expected: no collision (SAFE).
    """
    r1_path = [Position(x, 5) for x in range(1, 20)]
    r2_path = [Position(x, 8) for x in range(1, 20)]

    result = _run(
        my_pos=Position(0, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(0, 8), peer_path=r2_path,
    )
    is_collision = _predicted_collision(result)
    assert not is_collision, (
        f"Expected SAFE for parallel robots with 3-cell gap, "
        f"got {result.risk_level.value if result else None} "
        f"min_sep={result.minimum_predicted_distance if result else 'N/A'}"
    )
    print(f"PASS  parallel_safe | risk={result.risk_level.value if result else 'SAFE (None)'}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 4 — Crossing paths
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_crossing_paths():
    """
    R1 at (0,5) moving right → will pass through (5,5).
    R2 at (5,0) moving down ↓ will pass through (5,5).
    Expected: predicted collision = TRUE.
    """
    r1_path = [Position(x, 5) for x in range(1, 12)]
    r2_path = [Position(5, y) for y in range(1, 12)]

    result = _run(
        my_pos=Position(0, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(5, 0), peer_path=r2_path,
        horizon=40,   # wider horizon to catch timing
    )
    assert result is not None, "Expected a CollisionPrediction, got None"
    assert _predicted_collision(result), (
        f"Expected collision on crossing paths, got {result.risk_level.value} | "
        f"min_sep={result.minimum_predicted_distance:.3f}"
    )
    print(f"PASS  crossing_paths | risk={result.risk_level.value} | "
          f"TTC={result.time_to_collision}s | "
          f"conflict_pos={result.conflict_position}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 5 — Same path, very different ETA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_same_path_different_eta():
    """
    R1 at (0,5) moving right with path to (5,5).  ETA at (5,5) ≈ 20 ticks.
    R2 at (20,5) also moving right (same direction), well ahead.
    R2 will reach (5,5) only after leaving (5,5) already — or is far ahead.
    They are moving the same direction, R2 is far ahead → no catch-up possible.
    Expected: SAFE (R1 cannot catch R2 within the horizon).
    """
    # R2 starts at (20,5) moving further right — R1 at (0,5) moves right.
    # R1 can never catch R2 within a short horizon.
    r1_path = [Position(x, 5) for x in range(1, 12)]
    r2_path = [Position(x, 5) for x in range(21, 35)]

    result = _run(
        my_pos=Position(0, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(20, 5), peer_path=r2_path,
        horizon=20,
    )
    is_collision = _predicted_collision(result)
    min_sep_str = f"{result.minimum_predicted_distance:.3f}" if result else 'N/A'
    assert not is_collision, (
        f"Expected SAFE (different ETA), got {result.risk_level.value if result else None} | "
        f"min_sep={min_sep_str}"
    )
    print(f"PASS  same_path_different_eta | risk={result.risk_level.value if result else 'SAFE (None)'}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 6 — Same path, similar ETA (one right behind the other)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_same_path_similar_eta():
    """
    R1 at (3,5) moving right.
    R2 at (4,5) moving right (1 cell ahead on the same path).
    R1's next position (4,5) is where R2 currently is.
    Expected: predicted collision = TRUE (tailgating).
    """
    r1_path = [Position(x, 5) for x in range(4, 15)]
    r2_path = [Position(x, 5) for x in range(5, 15)]

    result = _run(
        my_pos=Position(3, 5), my_path=r1_path,
        peer_id="R2", peer_pos=Position(4, 5), peer_path=r2_path,
        horizon=20,
    )
    # R2 is only 1 cell ahead — R1 will reach (4,5) while R2 is at (4,5) or (5,5),
    # creating a close approach well within _UNSAFE_DISTANCE.
    assert result is not None, "Expected a CollisionPrediction, got None"
    assert result.risk_level != CollisionRisk.SAFE, (
        f"Expected non-SAFE for tailgating robots, got {result.risk_level.value} | "
        f"min_sep={result.minimum_predicted_distance:.3f}"
    )
    print(f"PASS  same_path_similar_eta | risk={result.risk_level.value} | "
          f"min_sep={result.minimum_predicted_distance:.3f} | TTC={result.time_to_collision}s")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 7 — Peer is UNAVAILABLE (should be skipped)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_unavailable_peer_skipped():
    """
    An UNAVAILABLE peer should always be skipped, even if on a collision path.
    """
    r1_path = [Position(x, 5) for x in range(1, 12)]
    r2_path = [Position(x, 5) for x in range(7, -1, -1)]

    predictor = CollisionPredictor("R1")
    peer = _make_peer("R2", Position(8, 5), r2_path, status=RobotStatus.UNAVAILABLE)
    predictions = predictor.predict(
        my_render_x=0.0,
        my_render_y=5.0,
        my_path=r1_path,
        my_velocity=1.0,
        peer_knowledge={"R2": peer},
        current_tick=0,
        horizon_ticks=20,
        detection_radius=50.0,
    )
    assert len(predictions) == 0, (
        f"Expected 0 predictions for UNAVAILABLE peer, got {len(predictions)}"
    )
    print("PASS  unavailable_peer_skipped")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 8 — Peer outside detection radius (should be skipped)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_peer_outside_detection_radius():
    """
    A peer far away (beyond detection_radius) should never be evaluated.
    """
    r1_path = [Position(x, 5) for x in range(1, 12)]
    r2_path = [Position(x, 5) for x in range(7, -1, -1)]

    predictor = CollisionPredictor("R1")
    peer = _make_peer("R2", Position(100, 5), r2_path)
    predictions = predictor.predict(
        my_render_x=0.0,
        my_render_y=5.0,
        my_path=r1_path,
        my_velocity=1.0,
        peer_knowledge={"R2": peer},
        current_tick=0,
        horizon_ticks=20,
        detection_radius=10.0,   # R2 is 100 cells away
    )
    assert len(predictions) == 0, (
        f"Expected 0 predictions for out-of-range peer, got {len(predictions)}"
    )
    print("PASS  peer_outside_detection_radius")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALL_TESTS = [
    test_trajectory_builder_empty_path,
    test_trajectory_builder_one_step,
    test_head_on,
    test_moving_away,
    test_parallel_safe,
    test_crossing_paths,
    test_same_path_different_eta,
    test_same_path_similar_eta,
    test_unavailable_peer_skipped,
    test_peer_outside_detection_radius,
]


def run_all():
    passed, failed = 0, 0
    print("\n" + "=" * 60)
    print("FleetMind — Collision Predictor Unit Tests")
    print("=" * 60)
    for fn in ALL_TESTS:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(ALL_TESTS)} tests")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)


# ── pytest compatibility ─────────────────────────────────────────────────────
# pytest will discover any function starting with "test_".
# The module-level names already satisfy this convention.
