"""
FleetMind — Warehouse Grid & Pathfinding Graph

30 × 20 cell warehouse with racks, aisles, narrow corridors,
intersections, pickup/dropoff zones, charging stations, and staging areas.

The grid is the single source of truth for spatial structure.
A graph (adjacency list) is derived from the grid for pathfinding.
Dynamic obstacles can be injected/removed at runtime.

Key layout features
───────────────────
• Horizontal main aisles at rows 0, 2, 5, 11, 14, 17, 19
• Narrow vertical corridors (1-cell wide) between rack pairs
  at columns 4, 7, 15, 18, 26 — these span rows 6-10 with no
  horizontal cross-aisle, creating natural choke points.
• Wide vertical corridors at columns 0-1, 10-12, 21-23, 29
• Pickup zones and charging stations at row 18
• Dropoff zones at row 1
• Staging / holding areas at row 18
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from models import CellType, Position


# ─── Character → CellType mapping ────────────────────────

_CHAR_MAP = {
    ".": CellType.OPEN,
    "#": CellType.RACK,
    "D": CellType.DROPOFF,
    "P": CellType.PICKUP,
    "C": CellType.CHARGING,
    "S": CellType.STAGING,
}

_WALKABLE = frozenset({
    CellType.OPEN,
    CellType.PICKUP,
    CellType.DROPOFF,
    CellType.CHARGING,
    CellType.STAGING,
})


def _pad(row: str, width: int = 30) -> str:
    """Ensure *row* is exactly *width* characters, padding with '.'."""
    return (row + "." * width)[:width]


# ─── Default layout ──────────────────────────────────────
#  30 columns × 20 rows

_DEFAULT_LAYOUT: List[str] = [
    _pad("." * 30),                                         #  0  top aisle
    _pad("..DDD..........DDD.........."),                    #  1  dropoff
    _pad("." * 30),                                         #  2  main aisle
    _pad("..##.##.##...##.##.##...##.##"),                   #  3  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   #  4  rack row
    _pad("." * 30),                                         #  5  cross aisle
    _pad("..##.##.##...##.##.##...##.##"),                   #  6  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   #  7  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   #  8  narrow zone
    _pad("..##.##.##...##.##.##...##.##"),                   #  9  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   # 10  rack row
    _pad("." * 30),                                         # 11  cross aisle
    _pad("..##.##.##...##.##.##...##.##"),                   # 12  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   # 13  rack row
    _pad("." * 30),                                         # 14  cross aisle
    _pad("..##.##.##...##.##.##...##.##"),                   # 15  rack row
    _pad("..##.##.##...##.##.##...##.##"),                   # 16  rack row
    _pad("." * 30),                                         # 17  main aisle
    _pad("..PPP..C.......PPP..C...SS.."),                    # 18  pickup/charging/staging
    _pad("." * 30),                                         # 19  bottom aisle
]


class Warehouse:
    """
    Grid-based warehouse with derived pathfinding graph.

    Parameters
    ----------
    layout : list[str] | None
        Optional custom layout.  Each string is one row of characters.
        Characters: . # D P C S  (see _CHAR_MAP).
    """

    def __init__(self, layout: Optional[List[str]] = None):
        raw = layout or _DEFAULT_LAYOUT
        self.layout: List[str] = [_pad(r, len(raw[0])) for r in raw]
        self.height: int = len(self.layout)
        self.width: int = len(self.layout[0])

        # Core data structures
        self.grid: Dict[Position, CellType] = {}
        self.graph: Dict[Position, List[Position]] = {}

        # Named locations
        self.pickups: List[Position] = []
        self.dropoffs: List[Position] = []
        self.charging_stations: List[Position] = []
        self.staging_areas: List[Position] = []
        self.intersections: List[Position] = []

        # Dynamic obstacles
        self.dynamic_obstacles: Set[Position] = set()
        self.blocked_aisles: Dict[str, List[Position]] = {}

        self._build()

    # ── construction ─────────────────────────────────────

    def _build(self):
        self._parse_grid()
        self._build_graph()
        self._find_locations()
        self._find_intersections()

    def _parse_grid(self):
        for y, row in enumerate(self.layout):
            for x, ch in enumerate(row):
                self.grid[Position(x, y)] = _CHAR_MAP.get(ch, CellType.OPEN)

    def _build_graph(self):
        """Build adjacency list from walkable cells."""
        self.graph.clear()
        for pos, ctype in self.grid.items():
            if ctype not in _WALKABLE:
                continue
            nbrs: List[Position] = []
            for n in pos.neighbors_4():
                if n in self.grid and self.grid[n] in _WALKABLE:
                    nbrs.append(n)
            self.graph[pos] = nbrs

    def _find_locations(self):
        self.pickups = sorted(
            (p for p, t in self.grid.items() if t == CellType.PICKUP),
            key=lambda p: (p.y, p.x),
        )
        self.dropoffs = sorted(
            (p for p, t in self.grid.items() if t == CellType.DROPOFF),
            key=lambda p: (p.y, p.x),
        )
        self.charging_stations = sorted(
            (p for p, t in self.grid.items() if t == CellType.CHARGING),
            key=lambda p: (p.y, p.x),
        )
        self.staging_areas = sorted(
            (p for p, t in self.grid.items() if t == CellType.STAGING),
            key=lambda p: (p.y, p.x),
        )

    def _find_intersections(self):
        """Cells with ≥ 3 walkable neighbours are junctions."""
        self.intersections = sorted(
            (pos for pos, nbrs in self.graph.items() if len(nbrs) >= 3),
            key=lambda p: (p.y, p.x),
        )

    # ── queries ──────────────────────────────────────────

    def is_walkable(self, pos: Position) -> bool:
        """True when *pos* is in-bounds, walkable, and not dynamically blocked."""
        if pos not in self.grid:
            return False
        if pos in self.dynamic_obstacles:
            return False
        return self.grid[pos] in _WALKABLE

    def get_walkable_neighbors(self, pos: Position) -> List[Position]:
        """Walkable neighbours of *pos*, respecting dynamic obstacles."""
        if pos not in self.graph:
            return []
        return [n for n in self.graph[pos] if n not in self.dynamic_obstacles]

    def get_cell_type(self, pos: Position) -> Optional[CellType]:
        return self.grid.get(pos)

    def is_narrow_aisle(self, pos: Position) -> bool:
        """True when *pos* has exactly 2 walkable neighbours (corridor)."""
        nbrs = self.graph.get(pos, [])
        return len(nbrs) == 2

    def get_all_walkable(self) -> List[Position]:
        """Return every walkable cell (for random placement, etc.)."""
        return list(self.graph.keys())

    # ── dynamic obstacles ────────────────────────────────

    def add_obstacle(self, pos: Position) -> bool:
        if pos in self.grid and self.grid[pos] in _WALKABLE:
            self.dynamic_obstacles.add(pos)
            return True
        return False

    def remove_obstacle(self, pos: Position):
        self.dynamic_obstacles.discard(pos)

    def block_aisle(self, aisle_id: str, cells: List[Position]):
        """Block a named aisle segment by injecting obstacles."""
        self.blocked_aisles[aisle_id] = list(cells)
        for c in cells:
            self.add_obstacle(c)

    def unblock_aisle(self, aisle_id: str):
        if aisle_id in self.blocked_aisles:
            for c in self.blocked_aisles[aisle_id]:
                self.remove_obstacle(c)
            del self.blocked_aisles[aisle_id]

    def clear_obstacles(self):
        self.dynamic_obstacles.clear()
        self.blocked_aisles.clear()

    # ── predefined aisle segments ────────────────────────

    def get_narrow_vertical_aisles(self) -> Dict[str, List[Position]]:
        """
        Named narrow vertical corridors between rack rows 6-10
        at columns 4, 7, 15, 18, 26.
        """
        segments: Dict[str, List[Position]] = {}
        narrow_cols = [4, 7, 15, 18, 26]
        for idx, col in enumerate(narrow_cols):
            key = f"NV{idx + 1}"
            cells = [Position(col, y) for y in range(6, 11)
                     if self.is_walkable(Position(col, y))]
            if cells:
                segments[key] = cells
        return segments

    def get_blockable_aisles(self) -> Dict[str, List[Position]]:
        """
        Return a catalogue of aisle segments that can be
        blocked for scenario testing.
        """
        aisles = self.get_narrow_vertical_aisles()
        # Also add horizontal aisle segments
        for row in [5, 11, 14]:
            key = f"H{row}"
            cells = [Position(x, row) for x in range(2, 28)
                     if self.is_walkable(Position(x, row))]
            if cells:
                aisles[key] = cells
        return aisles

    # ── serialisation ────────────────────────────────────

    def get_named_locations(self) -> Dict[str, List[Tuple[int, int]]]:
        return {
            "pickups": [p.to_tuple() for p in self.pickups],
            "dropoffs": [p.to_tuple() for p in self.dropoffs],
            "charging_stations": [c.to_tuple() for c in self.charging_stations],
            "staging_areas": [s.to_tuple() for s in self.staging_areas],
            "intersections": [i.to_tuple() for i in self.intersections],
        }

    def to_dict(self) -> Dict:
        """Full warehouse state for the frontend."""
        grid_data: List[List[str]] = []
        for y in range(self.height):
            row: List[str] = []
            for x in range(self.width):
                pos = Position(x, y)
                if pos in self.dynamic_obstacles:
                    row.append(CellType.OBSTACLE.value)
                else:
                    row.append(self.grid[pos].value)
            grid_data.append(row)

        return {
            "width": self.width,
            "height": self.height,
            "grid": grid_data,
            "locations": self.get_named_locations(),
            "blocked_aisles": list(self.blocked_aisles.keys()),
            "dynamic_obstacles": [p.to_tuple() for p in self.dynamic_obstacles],
        }
