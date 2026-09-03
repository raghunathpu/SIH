"""
FleetMind — A* Pathfinding

Standard A* on the warehouse grid graph.
Supports dynamic obstacle avoidance and forbidden-cell sets.
"""

from __future__ import annotations

import heapq
from typing import Callable, List, Optional, Set

from models import Position


def astar(
    start: Position,
    goal: Position,
    get_neighbors: Callable[[Position], List[Position]],
    is_blocked: Optional[Callable[[Position], bool]] = None,
    forbidden: Optional[Set[Position]] = None,
    max_iterations: int = 5000,
) -> Optional[List[Position]]:
    """
    Compute a shortest path from *start* to *goal*.

    Parameters
    ----------
    start, goal : Position
        Source and destination cells.
    get_neighbors : callable
        Returns the list of walkable neighbours for a cell.
        Typically ``warehouse.get_walkable_neighbors``.
    is_blocked : callable | None
        Extra predicate — if it returns True for a cell the cell
        is treated as impassable.  Used for avoiding known
        robot positions.
    forbidden : set[Position] | None
        Explicit set of cells to avoid (e.g. cells reserved by
        another robot).
    max_iterations : int
        Safety cap to avoid runaway searches on very large grids.

    Returns
    -------
    list[Position] | None
        The path including both *start* and *goal*, or None when
        no path exists.
    """
    if start == goal:
        return [start]

    forbidden = forbidden or set()
    _blocked = is_blocked or (lambda _: False)

    open_heap: list = []
    # Tie-break on insertion order to keep the heap deterministic.
    counter = 0
    h0 = start.manhattan_distance(goal)
    heapq.heappush(open_heap, (h0, counter, start))
    counter += 1

    came_from: dict[Position, Position] = {}
    g_score: dict[Position, int] = {start: 0}
    closed: set[Position] = set()

    iterations = 0
    while open_heap and iterations < max_iterations:
        iterations += 1
        _f, _cnt, current = heapq.heappop(open_heap)

        if current == goal:
            return _reconstruct(came_from, current)

        if current in closed:
            continue
        closed.add(current)

        for neighbor in get_neighbors(current):
            if neighbor in closed:
                continue
            if neighbor in forbidden:
                continue
            if _blocked(neighbor) and neighbor != goal:
                continue

            tentative_g = g_score[current] + 1
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + neighbor.manhattan_distance(goal)
                heapq.heappush(open_heap, (f, counter, neighbor))
                counter += 1

    return None  # no path


def astar_avoid_robots(
    start: Position,
    goal: Position,
    get_neighbors: Callable[[Position], List[Position]],
    robot_positions: Set[Position],
    max_iterations: int = 5000,
) -> Optional[List[Position]]:
    """
    A* that treats *robot_positions* as temporary obstacles
    (except the goal itself, in case a robot is sitting on it).
    """
    blocked = robot_positions - {goal, start}
    return astar(
        start, goal, get_neighbors,
        is_blocked=lambda p: p in blocked,
        max_iterations=max_iterations,
    )


def find_alternative_path(
    start: Position,
    goal: Position,
    get_neighbors: Callable[[Position], List[Position]],
    avoid_cells: Set[Position],
    max_iterations: int = 5000,
) -> Optional[List[Position]]:
    """
    Find a path that avoids a specific set of cells.
    Used for rerouting around blocked aisles or conflict zones.
    """
    return astar(
        start, goal, get_neighbors,
        forbidden=avoid_cells,
        max_iterations=max_iterations,
    )


# ── internal ─────────────────────────────────────────────

def _reconstruct(came_from: dict, current: Position) -> List[Position]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
