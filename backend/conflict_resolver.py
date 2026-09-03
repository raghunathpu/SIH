"""
FleetMind — Local Conflict Detection & Resolution

Runs **inside each RobotAgent** — not centrally.
Each robot uses its own peer_knowledge (built from received messages)
to detect and resolve conflicts.

Priority policy (deterministic, documented):
  1. Higher task priority wins.
  2. If equal: robot closer to the conflict cell wins (less disruption).
  3. If equal: robot that has been waiting longer wins.
  4. If equal: lower robot_id wins (deterministic tiebreak).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models import (
    ConflictInfo,
    PeerKnowledge,
    Position,
    RobotStatus,
)


@dataclass
class LocalConflict:
    """A conflict detected locally by one robot."""
    other_robot_id: str
    cell: Position
    conflict_type: str   # INTERSECTION / HEAD_ON / CHOKE / SIMULTANEOUS
    my_distance: int     # cells until I reach the conflict cell
    peer_distance: int   # estimated cells until peer reaches it
    peer_priority: int


def detect_conflicts(
    my_id: str,
    my_position: Position,
    my_path: List[Position],
    my_task_priority: int,
    peer_knowledge: Dict[str, PeerKnowledge],
    lookahead: int = 3,
) -> List[LocalConflict]:
    """
    Scan upcoming cells on *my_path* for potential conflicts
    with known peers.

    Only considers non-stale, active peers.
    """
    conflicts: List[LocalConflict] = []
    if not my_path:
        return conflicts

    # Cells we will visit in the next *lookahead* steps
    upcoming = my_path[:lookahead]

    for step_idx, cell in enumerate(upcoming):
        for peer_id, peer in peer_knowledge.items():
            if peer_id == my_id:
                continue
            if peer.status in (RobotStatus.UNAVAILABLE, RobotStatus.CHARGING):
                continue
            if peer.position is None:
                continue

            ctype = _classify_conflict(
                cell, step_idx, my_position, my_path,
                peer,
            )
            if ctype is not None:
                peer_dist = (
                    peer.position.manhattan_distance(cell) if peer.position else 99
                )
                conflicts.append(LocalConflict(
                    other_robot_id=peer_id,
                    cell=cell,
                    conflict_type=ctype,
                    my_distance=step_idx + 1,
                    peer_distance=peer_dist,
                    peer_priority=peer.priority,
                ))

    return conflicts


def _classify_conflict(
    cell: Position,
    step_idx: int,
    my_pos: Position,
    my_path: List[Position],
    peer: PeerKnowledge,
) -> Optional[str]:
    """Return conflict type string or None if no conflict."""
    if peer.position is None:
        return None

    # Peer currently occupying the cell
    if peer.position == cell:
        return "INTERSECTION"

    # Peer planning to be at the cell soon
    for i, pcell in enumerate(peer.planned_path[:4]):
        if pcell == cell:
            # Timing proximity — both arriving around the same time
            if abs(step_idx - i) <= 1:
                return "SIMULTANEOUS"
            return "INTERSECTION"

    # Head-on: peer is 1 cell away from our next cell and heading toward us
    if peer.position.manhattan_distance(cell) <= 1:
        # Check if peer is heading toward us
        if peer.planned_path:
            if len(peer.planned_path) > 0 and peer.planned_path[0] == cell:
                return "HEAD_ON"
        # Check if we are heading toward peer
        if my_pos.manhattan_distance(peer.position) <= 2:
            if cell == peer.position:
                return "HEAD_ON"

    return None


def compare_priority(
    my_task_priority: int,
    my_distance: int,
    my_waiting_time: int,
    my_id: str,
    peer_task_priority: int,
    peer_distance: int,
    peer_waiting_time: int,
    peer_id: str,
) -> int:
    """
    Compare two robots' priority.

    Returns
    -------
    +1  if *my* priority is higher (I should proceed)
    -1  if *peer* priority is higher (I should yield)
     0  if exactly equal (should not happen with id tiebreak)
    """
    # 1. Task priority (higher wins)
    if my_task_priority != peer_task_priority:
        return 1 if my_task_priority > peer_task_priority else -1

    # 2. Distance to conflict cell (closer wins — already committed)
    if my_distance != peer_distance:
        return 1 if my_distance < peer_distance else -1

    # 3. Waiting time (more waiting = higher priority, fairness)
    if my_waiting_time != peer_waiting_time:
        return 1 if my_waiting_time > peer_waiting_time else -1

    # 4. Robot ID tiebreak (lower ID wins — deterministic)
    if my_id != peer_id:
        return 1 if my_id < peer_id else -1

    return 0


def should_reroute_vs_wait(
    waiting_time: int,
    max_wait: int,
    alternative_path_exists: bool,
) -> bool:
    """
    Decide whether to reroute instead of continuing to wait.
    Rerouting is preferred when:
      - We have waited a long time, AND
      - An alternative path exists.
    """
    if waiting_time >= max_wait and alternative_path_exists:
        return True
    return False
