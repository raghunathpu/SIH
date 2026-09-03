"""
FleetMind — Distributed Deadlock Detection & Recovery

Each robot tracks its own wait-for dependency and broadcasts it.
Using received WAIT_FOR messages from peers, each robot builds
a local view of the wait-for graph and checks for cycles.

When a cycle is found, the robot with the **lowest priority** in
the cycle initiates recovery by yielding / rerouting.

Deadlock detection criteria:
  1. Cyclic wait-for dependency (A→B→C→A).
  2. Prolonged waiting beyond DEADLOCK_WAIT_THRESHOLD without progress.
  3. Repeated negotiation failures.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from models import Position, DEADLOCK_WAIT_THRESHOLD


def detect_cycle(
    wait_for_graph: Dict[str, Optional[str]],
) -> Optional[List[str]]:
    """
    Detect a cycle in the wait-for graph.

    Parameters
    ----------
    wait_for_graph : dict[str, str | None]
        Mapping from robot_id → the robot_id it is waiting for,
        or None if not waiting.

    Returns
    -------
    list[str] | None
        The robot IDs forming the cycle, or None.
    """
    visited: Set[str] = set()

    for start in wait_for_graph:
        if start in visited:
            continue

        path: List[str] = []
        path_set: Set[str] = set()
        current: Optional[str] = start

        while current is not None and current not in visited:
            if current in path_set:
                # Found a cycle — extract it
                cycle_start = path.index(current)
                return path[cycle_start:]

            path.append(current)
            path_set.add(current)
            current = wait_for_graph.get(current)

        visited.update(path_set)

    return None


def detect_prolonged_wait(
    robot_id: str,
    waiting_time: int,
    threshold: int = DEADLOCK_WAIT_THRESHOLD,
) -> bool:
    """True when a robot has been waiting longer than the threshold."""
    return waiting_time >= threshold


def select_yielding_robot(
    cycle: List[str],
    priorities: Dict[str, int],
) -> str:
    """
    From a deadlock cycle, pick the robot that should yield.

    Policy: the robot with the **lowest task priority** in the cycle
    yields.  Ties broken by highest robot_id (so "AMR-03" yields
    before "AMR-01").
    """
    return min(
        cycle,
        key=lambda rid: (priorities.get(rid, 0), -ord(rid[-1]) if rid else 0),
    )


class DeadlockDetector:
    """
    Maintains the local wait-for graph and provides cycle queries.

    Each robot owns one instance and feeds it data from
    WAIT_FOR messages received from peers.
    """

    def __init__(self):
        # robot_id → robot_id it waits for (or None)
        self.wait_for: Dict[str, Optional[str]] = {}

    def update(self, robot_id: str, waits_for: Optional[str]):
        """Update a single entry (from a received WAIT_FOR message)."""
        self.wait_for[robot_id] = waits_for

    def remove(self, robot_id: str):
        self.wait_for.pop(robot_id, None)

    def check_cycle(self) -> Optional[List[str]]:
        return detect_cycle(self.wait_for)

    def is_in_cycle(self, robot_id: str) -> bool:
        """Check if *robot_id* is part of a deadlock cycle."""
        cycle = self.check_cycle()
        if cycle is None:
            return False
        return robot_id in cycle

    def clear(self):
        self.wait_for.clear()
