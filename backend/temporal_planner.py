"""
FleetMind — 3D Space-Time Pathfinding (MAPF)

This module implements A* in space and time (x, y, t).
Robots reserve cells at specific ticks in a global SpaceTimeGrid,
allowing them to cooperatively avoid each other without deadlocks.
"""

from __future__ import annotations
import heapq
from typing import Callable, List, Optional, Set, Dict, Tuple
from models import Position

class SpaceTimeGrid:
    """
    Decentralized ledger of future cell reservations.
    Keys are (tick, Position), values are robot_id.
    """
    def __init__(self):
        self.reservations: Dict[Tuple[int, Position], str] = {}
        # Track the last reserved tick for each cell to prevent robots from
        # planning over a cell that another robot will rest on indefinitely.
        self.terminal_reservations: Dict[Position, Tuple[int, str]] = {}

    def reserve(self, robot_id: str, tick: int, position: Position):
        self.reservations[(tick, position)] = robot_id

    def reserve_path(self, robot_id: str, start_tick: int, path: List[Position]):
        """Reserves a sequence of positions starting from start_tick."""
        for i, pos in enumerate(path):
            t = start_tick + i
            self.reserve(robot_id, t, pos)
        
        # The robot will rest at the end of the path indefinitely (or until next plan)
        if path:
            self.terminal_reservations[path[-1]] = (start_tick + len(path) - 1, robot_id)

    def clear_robot_reservations(self, robot_id: str):
        """Remove all reservations for a specific robot."""
        # Clear specific tick reservations
        keys_to_delete = [k for k, v in self.reservations.items() if v == robot_id]
        for k in keys_to_delete:
            del self.reservations[k]
            
        # Clear terminal reservations
        term_keys = [k for k, v in self.terminal_reservations.items() if v[1] == robot_id]
        for k in term_keys:
            del self.terminal_reservations[k]

    def is_reserved(self, tick: int, position: Position, exclude_robot: Optional[str] = None) -> bool:
        """Check if a cell is reserved at a specific tick."""
        # 1. Check exact tick reservation
        if (tick, position) in self.reservations:
            res_id = self.reservations[(tick, position)]
            if res_id != exclude_robot:
                return True
        
        # 2. Check if a robot has stopped here indefinitely in the past
        if position in self.terminal_reservations:
            term_tick, term_id = self.terminal_reservations[position]
            if tick >= term_tick and term_id != exclude_robot:
                # Unless this cell is explicitly reserved by someone else at exactly this tick?
                # Actually if a robot rests here, no one else can pass.
                return True
                
        return False

    def is_swap_conflict(self, tick: int, current_pos: Position, next_pos: Position, exclude_robot: Optional[str] = None) -> bool:
        """
        Check if moving current_pos -> next_pos at tick -> tick+1
        would cause a swap (vertex collision) with another robot moving next_pos -> current_pos.
        """
        if (tick, next_pos) in self.reservations and (tick + 1, current_pos) in self.reservations:
            r1 = self.reservations[(tick, next_pos)]
            r2 = self.reservations[(tick + 1, current_pos)]
            if r1 == r2 and r1 != exclude_robot:
                return True
        return False


def astar_3d(
    start: Position,
    goal: Position,
    start_tick: int,
    get_neighbors: Callable[[Position], List[Position]],
    grid: SpaceTimeGrid,
    robot_id: str,
    is_blocked: Optional[Callable[[Position], bool]] = None,
    max_iterations: int = 5000,
) -> Optional[List[Position]]:
    """
    3D Space-Time A*.
    Returns a list of positions (path) where index i corresponds to start_tick + i.
    """
    if start == goal:
        return [start]

    _blocked = is_blocked or (lambda _: False)

    open_heap: list = []
    counter = 0
    
    # Heap stores: (f_score, counter, tick, current_pos)
    h0 = start.manhattan_distance(goal)
    heapq.heappush(open_heap, (h0, counter, start_tick, start))
    counter += 1

    # came_from maps (tick, pos) -> (tick-1, prev_pos)
    came_from: dict[Tuple[int, Position], Position] = {}
    
    # g_score maps (tick, pos) -> cost
    g_score: dict[Tuple[int, Position], int] = {(start_tick, start): 0}
    closed: set[Tuple[int, Position]] = set()

    iterations = 0
    while open_heap and iterations < max_iterations:
        iterations += 1
        _f, _cnt, current_tick, current_pos = heapq.heappop(open_heap)

        if current_pos == goal:
            # We must also ensure we can rest at the goal indefinitely without collision
            # But for simplicity, we assume reaching the goal is enough for the path.
            path = []
            curr_state = (current_tick, current_pos)
            while curr_state in came_from:
                path.append(curr_state[1])
                prev_pos = came_from[curr_state]
                curr_state = (curr_state[0] - 1, prev_pos)
            path.append(start)
            path.reverse()
            return path

        if (current_tick, current_pos) in closed:
            continue
        closed.add((current_tick, current_pos))

        next_tick = current_tick + 1
        
        # 1. Wait action (stay in place)
        possible_moves = [current_pos] + get_neighbors(current_pos)

        for neighbor in possible_moves:
            if (next_tick, neighbor) in closed:
                continue
            
            # Check static obstacles
            if _blocked(neighbor) and neighbor != current_pos:
                continue

            # Check Space-Time Grid for vertex collision
            if grid.is_reserved(next_tick, neighbor, exclude_robot=robot_id):
                continue

            # Check Space-Time Grid for edge (swap) collision
            if neighbor != current_pos:
                if grid.is_swap_conflict(current_tick, current_pos, neighbor, exclude_robot=robot_id):
                    continue

            tentative_g = g_score[(current_tick, current_pos)] + 1
            if tentative_g < g_score.get((next_tick, neighbor), float("inf")):
                came_from[(next_tick, neighbor)] = current_pos
                g_score[(next_tick, neighbor)] = tentative_g
                f = tentative_g + neighbor.manhattan_distance(goal)
                heapq.heappush(open_heap, (f, counter, next_tick, neighbor))
                counter += 1

    return None
