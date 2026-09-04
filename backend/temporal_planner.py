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
        self.reservations: Dict[Tuple[int, Position], Set[str]] = {}
        # Track the last reserved tick for each cell to prevent robots from
        # planning over a cell that another robot will rest on indefinitely.
        self.terminal_reservations: Dict[Position, Set[Tuple[int, str]]] = {}

    def reserve(self, robot_id: str, tick: int, position: Position):
        key = (tick, position)
        if key not in self.reservations:
            self.reservations[key] = set()
        self.reservations[key].add(robot_id)

    def reserve_path(self, robot_id: str, start_tick: int, path: List[Position]):
        """Reserves a sequence of positions starting from start_tick."""
        from models import TICKS_PER_MOVE
        
        if not path:
            return
            
        current_tick = start_tick
        current_pos = path[0]
        self.reserve(robot_id, current_tick, current_pos)
        
        for next_pos in path[1:]:
            if next_pos == current_pos:
                # Wait action takes 1 tick
                current_tick += 1
                self.reserve(robot_id, current_tick, current_pos)
            else:
                # Move action takes TICKS_PER_MOVE ticks
                for _ in range(TICKS_PER_MOVE):
                    current_tick += 1
                    self.reserve(robot_id, current_tick, next_pos)
                current_pos = next_pos
        
        # The robot will rest at the end of the path indefinitely (or until next plan)
        if path[-1] not in self.terminal_reservations:
            self.terminal_reservations[path[-1]] = set()
        self.terminal_reservations[path[-1]].add((current_tick, robot_id))

    def clear_robot_reservations(self, robot_id: str):
        """Remove all reservations for a specific robot."""
        # Clear specific tick reservations
        empty_keys = []
        for k, res_set in self.reservations.items():
            if robot_id in res_set:
                res_set.remove(robot_id)
                if not res_set:
                    empty_keys.append(k)
        for k in empty_keys:
            del self.reservations[k]
            
        # Clear terminal reservations
        empty_term_keys = []
        for pos, term_set in self.terminal_reservations.items():
            items_to_remove = [item for item in term_set if item[1] == robot_id]
            for item in items_to_remove:
                term_set.remove(item)
            if not term_set:
                empty_term_keys.append(pos)
        for k in empty_term_keys:
            del self.terminal_reservations[k]

    def is_reserved(self, tick: int, position: Position, exclude_robot: Optional[str] = None) -> bool:
        """Check if a cell is reserved at a specific tick."""
        # 1. Check exact tick reservation
        key = (tick, position)
        if key in self.reservations:
            for res_id in self.reservations[key]:
                if res_id != exclude_robot:
                    return True
        
        # 2. Check if a robot has stopped here indefinitely in the past
        if position in self.terminal_reservations:
            for term_tick, term_id in self.terminal_reservations[position]:
                if tick >= term_tick and term_id != exclude_robot:
                    return True
                
        return False

    def is_swap_conflict(self, tick: int, current_pos: Position, next_pos: Position, exclude_robot: Optional[str] = None) -> bool:
        """
        Check if moving current_pos -> next_pos at tick -> tick+1
        would cause a swap (vertex collision) with another robot moving next_pos -> current_pos.
        """
        if (tick, next_pos) in self.reservations and (tick + 1, current_pos) in self.reservations:
            r1_set = self.reservations[(tick, next_pos)]
            r2_set = self.reservations[(tick + 1, current_pos)]
            # If any robot (other than exclude_robot) is in both sets, it's a swap conflict
            for r_id in r1_set.intersection(r2_set):
                if r_id != exclude_robot:
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

    from models import TICKS_PER_MOVE

    _blocked = is_blocked or (lambda _: False)

    open_heap: list = []
    counter = 0

    # Heap stores: (f_score, counter, tick, current_pos)
    # NOTE: cost/heuristic are expressed in *ticks*, not action-count, so
    # that A* actually minimizes real elapsed time (which is what the
    # benchmark measures) rather than treating a 1-tick wait and a
    # TICKS_PER_MOVE-tick move as equally "expensive". Scaling the
    # heuristic by TICKS_PER_MOVE keeps it admissible/consistent under
    # this cost model.
    h0 = start.manhattan_distance(goal) * TICKS_PER_MOVE
    heapq.heappush(open_heap, (h0, counter, start_tick, start))
    counter += 1

    # came_from maps (tick, pos) -> (prev_tick, prev_pos)
    came_from: dict[Tuple[int, Position], Tuple[int, Position]] = {}
    
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
                curr_state = came_from[curr_state]
            path.append(start)
            path.reverse()
            return path

        if (current_tick, current_pos) in closed:
            continue
        closed.add((current_tick, current_pos))

        # 1. Wait action (stay in place)
        possible_moves = [current_pos] + get_neighbors(current_pos)

        for neighbor in possible_moves:
            collision = False
            
            if neighbor == current_pos:
                next_tick = current_tick + 1
                if grid.is_reserved(next_tick, neighbor, exclude_robot=robot_id):
                    collision = True
            else:
                next_tick = current_tick + TICKS_PER_MOVE
                # Check static obstacles
                if _blocked(neighbor) and neighbor != current_pos:
                    continue
                    
                # Check Space-Time Grid for vertex collision during the entire move
                for t in range(current_tick + 1, next_tick + 1):
                    if grid.is_reserved(t, neighbor, exclude_robot=robot_id):
                        collision = True
                        break
                        
                # Check Space-Time Grid for edge (swap) collision
                if not collision:
                    if grid.is_swap_conflict(current_tick, current_pos, neighbor, exclude_robot=robot_id):
                        collision = True

            if collision:
                continue

            tentative_g = g_score[(current_tick, current_pos)] + (next_tick - current_tick)
            if tentative_g < g_score.get((next_tick, neighbor), float("inf")):
                came_from[(next_tick, neighbor)] = (current_tick, current_pos)
                g_score[(next_tick, neighbor)] = tentative_g
                f = tentative_g + neighbor.manhattan_distance(goal) * TICKS_PER_MOVE
                heapq.heappush(open_heap, (f, counter, next_tick, neighbor))
                counter += 1

    return None