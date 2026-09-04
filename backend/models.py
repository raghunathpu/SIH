"""
FleetMind — Core Data Models

All shared data structures for the distributed AMR fleet coordination system.
Every robot agent, the simulation engine, and the dashboard use these models
as the common language.  No module should invent ad-hoc dictionaries when
a model exists here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENUMERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CellType(Enum):
    """Warehouse grid cell types."""
    OPEN = "OPEN"
    RACK = "RACK"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    CHARGING = "CHARGING"
    STAGING = "STAGING"
    OBSTACLE = "OBSTACLE"


class RobotStatus(Enum):
    """Operational state of an AMR."""
    IDLE = "IDLE"
    MOVING = "MOVING"
    APPROACHING_CONFLICT = "APPROACHING_CONFLICT"
    NEGOTIATING = "NEGOTIATING"
    WAITING = "WAITING"
    REROUTING = "REROUTING"
    PICKING = "PICKING"
    DROPPING = "DROPPING"
    CHARGING = "CHARGING"
    BLOCKED = "BLOCKED"
    RECOVERY = "RECOVERY"
    UNAVAILABLE = "UNAVAILABLE"


class TaskStatus(Enum):
    """Lifecycle status of a warehouse task."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    PICKING = "PICKING"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class MessageType(Enum):
    """Types of peer-to-peer messages between robots."""
    STATE_UPDATE = "STATE_UPDATE"
    INTENT_BROADCAST = "INTENT_BROADCAST"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    RESERVATION_REQUEST = "RESERVATION_REQUEST"
    RESERVATION_GRANTED = "RESERVATION_GRANTED"
    RESERVATION_DENIED = "RESERVATION_DENIED"
    PRIORITY_CLAIM = "PRIORITY_CLAIM"
    PRIORITY_RESPONSE = "PRIORITY_RESPONSE"
    YIELD_NOTIFICATION = "YIELD_NOTIFICATION"
    OBSTACLE_ALERT = "OBSTACLE_ALERT"
    TASK_OFFER = "TASK_OFFER"
    TASK_BID = "TASK_BID"
    TASK_AWARD = "TASK_AWARD"
    TASK_REASSIGN = "TASK_REASSIGN"
    HEARTBEAT = "HEARTBEAT"
    DEADLOCK_DETECTED = "DEADLOCK_DETECTED"
    REROUTE_NOTIFICATION = "REROUTE_NOTIFICATION"
    WAIT_FOR = "WAIT_FOR"
    PATH_INTENT = "PATH_INTENT"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POSITION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class Position:
    """
    Immutable grid coordinate.  x = column, y = row.
    Origin (0, 0) is top-left.  x grows rightward, y grows downward.
    """
    x: int
    y: int

    # -- spatial helpers ---------------------------------------------------

    def manhattan_distance(self, other: Position) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def euclidean_distance(self, other: Position) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def neighbors_4(self) -> List[Position]:
        """4-connected grid neighbors (right, left, down, up)."""
        return [
            Position(self.x + 1, self.y),
            Position(self.x - 1, self.y),
            Position(self.x, self.y + 1),
            Position(self.x, self.y - 1),
        ]

    def direction_to(self, other: Position) -> float:
        """Heading in degrees from *self* to *other*.  0 = right, 90 = down."""
        dx = other.x - self.x
        dy = other.y - self.y
        if dx == 0 and dy == 0:
            return 0.0
        return math.degrees(math.atan2(dy, dx))

    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MESSAGES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Message:
    """
    Structured peer-to-peer message.

    * target_id = None  →  broadcast to every other robot
    * target_id = "AMR-02"  →  unicast to AMR-02
    """
    type: MessageType
    sender_id: str
    timestamp: int          # simulation tick when the message was created
    data: Dict[str, Any] = field(default_factory=dict)
    target_id: Optional[str] = None
    sequence: int = 0

    def validate(self) -> bool:
        """Basic structural validation.  Returns False for malformed messages."""
        if not self.sender_id:
            return False
        if self.timestamp < 0:
            return False
        if not isinstance(self.data, dict):
            return False
        return True

    def is_stale(self, current_tick: int, max_age: int = 60) -> bool:
        """True when the message is older than *max_age* ticks."""
        return (current_tick - self.timestamp) > max_age

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "target_id": self.target_id,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RESERVATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Reservation:
    """
    Temporal cell reservation: a robot claims occupancy of *cell*
    from tick *t_start* (inclusive) to *t_end* (exclusive).
    """
    cell: Position
    robot_id: str
    t_start: int
    t_end: int

    def overlaps(self, other: Reservation) -> bool:
        if self.cell != other.cell:
            return False
        return self.t_start < other.t_end and other.t_start < self.t_end

    def contains_time(self, t: int) -> bool:
        return self.t_start <= t < self.t_end

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell": self.cell.to_tuple(),
            "robot_id": self.robot_id,
            "t_start": self.t_start,
            "t_end": self.t_end,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TASKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Task:
    """A warehouse pick-and-place task."""
    task_id: str
    pickup: Position
    dropoff: Position
    priority: int = 1           # higher = more urgent
    deadline: Optional[int] = None
    assigned_robot: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    creation_time: int = 0
    start_time: Optional[int] = None
    completion_time: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "pickup": self.pickup.to_tuple(),
            "dropoff": self.dropoff.to_tuple(),
            "priority": self.priority,
            "deadline": self.deadline,
            "assigned_robot": self.assigned_robot,
            "status": self.status.value,
            "creation_time": self.creation_time,
            "start_time": self.start_time,
            "completion_time": self.completion_time,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFLICT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ConflictInfo:
    """Description of a detected spatial/temporal conflict."""
    conflict_id: str
    robot_ids: List[str]
    cell: Position
    tick: int
    conflict_type: str          # INTERSECTION / HEAD_ON / CHOKE_POINT / SIMULTANEOUS
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "robot_ids": self.robot_ids,
            "cell": self.cell.to_tuple(),
            "tick": self.tick,
            "conflict_type": self.conflict_type,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIMULATION EVENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SimulationEvent:
    """A single logged event from the simulation."""
    tick: int
    event_type: str             # CONFLICT / NEGOTIATION / REROUTE / TASK / OBSTACLE / SYSTEM / DEADLOCK / COLLISION
    robot_id: Optional[str]
    description: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "event_type": self.event_type,
            "robot_id": self.robot_id,
            "description": self.description,
            "data": self.data,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PEER KNOWLEDGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class PeerKnowledge:
    """
    What one robot knows about a peer, built exclusively from
    received P2P messages — never from direct state access.
    """
    robot_id: str
    position: Optional[Position] = None
    velocity: float = 0.0
    heading: float = 0.0
    status: RobotStatus = RobotStatus.IDLE
    intent: str = ""
    planned_path: List[Position] = field(default_factory=list)
    current_task: Optional[str] = None
    priority: int = 0
    last_update_tick: int = 0
    waiting_for: Optional[str] = None
    destination: Optional[Position] = None
    battery: float = 100.0

    def is_stale(self, current_tick: int, max_age: int = 30) -> bool:
        return (current_tick - self.last_update_tick) > max_age


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIMULATION METRICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SimulationMetrics:
    """Aggregate metrics collected during a simulation run."""
    total_task_completion_time: int = 0
    average_task_completion_time: float = 0.0
    throughput: float = 0.0
    total_waiting_time: int = 0
    average_waiting_time: float = 0.0
    num_conflicts: int = 0
    conflicts_resolved: int = 0
    collisions: int = 0
    deadlocks_detected: int = 0
    deadlock_recoveries: int = 0
    reroutes: int = 0
    total_distance: float = 0.0
    task_reassignments: int = 0
    unavailable_robots: int = 0
    communication_events: int = 0
    reservation_conflicts: int = 0
    tasks_completed: int = 0
    tasks_total: int = 0
    near_collisions: int = 0
    min_separation: float = float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_task_completion_time": self.total_task_completion_time,
            "average_task_completion_time": round(self.average_task_completion_time, 1),
            "throughput": round(self.throughput, 2),
            "total_waiting_time": self.total_waiting_time,
            "average_waiting_time": round(self.average_waiting_time, 1),
            "num_conflicts": self.num_conflicts,
            "conflicts_resolved": self.conflicts_resolved,
            "collisions": self.collisions,
            "deadlocks_detected": self.deadlocks_detected,
            "deadlock_recoveries": self.deadlock_recoveries,
            "reroutes": self.reroutes,
            "total_distance": round(self.total_distance, 1),
            "task_reassignments": self.task_reassignments,
            "unavailable_robots": self.unavailable_robots,
            "communication_events": self.communication_events,
            "reservation_conflicts": self.reservation_conflicts,
            "tasks_completed": self.tasks_completed,
            "tasks_total": self.tasks_total,
            "near_collisions": self.near_collisions,
            "min_separation": (
                round(self.min_separation, 2)
                if self.min_separation != float("inf")
                else None
            ),
        }

    def reset(self):
        """Zero out all counters for a fresh run."""
        self.total_task_completion_time = 0
        self.average_task_completion_time = 0.0
        self.throughput = 0.0
        self.total_waiting_time = 0
        self.average_waiting_time = 0.0
        self.num_conflicts = 0
        self.conflicts_resolved = 0
        self.collisions = 0
        self.deadlocks_detected = 0
        self.deadlock_recoveries = 0
        self.reroutes = 0
        self.total_distance = 0.0
        self.task_reassignments = 0
        self.unavailable_robots = 0
        self.communication_events = 0
        self.reservation_conflicts = 0
        self.tasks_completed = 0
        self.tasks_total = 0
        self.near_collisions = 0
        self.min_separation = float("inf")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TICKS_PER_MOVE = 4          # ticks to traverse one grid cell
PICK_DROP_TICKS = 6         # ticks to perform a pick or drop action
HEARTBEAT_INTERVAL = 10     # ticks between heartbeat broadcasts
HEARTBEAT_TIMEOUT = 40      # ticks before a peer is considered lost
CONFLICT_LOOKAHEAD = 3      # cells ahead to scan for conflicts
BATTERY_DRAIN_MOVE = 0.03   # % per move
BATTERY_DRAIN_IDLE = 0.005  # % per idle tick
BATTERY_CRITICAL = 15.0     # % threshold for charging
MAX_WAIT_BEFORE_REROUTE = 20  # ticks waiting before attempting reroute
DEADLOCK_WAIT_THRESHOLD = 40  # ticks before considering deadlock

# ── Predictive Collision Detection ───────────────────────────────────────────
# One cell-move takes TICKS_PER_MOVE ticks; we treat that as 1 second of
# simulated time so that TTC figures are human-readable.
TICKS_PER_SECOND: int = 4           # simulation ticks that equal one second
ROBOT_RADIUS: float = 0.3           # robot body radius in grid-cell units
SAFETY_MARGIN: float = 0.5          # extra clearance on top of combined radii
# UNSAFE_DISTANCE = ROBOT_RADIUS * 2 + SAFETY_MARGIN  ≈ 1.1 cells
# Horizon over which trajectories are projected for collision prediction.
PREDICTION_HORIZON_TICKS: int = 20  # ticks (~5 s at default speed)
# Only evaluate peers within this euclidean distance (cells).
# Keeps the inner loop O(nearby), not O(all robots).
DETECTION_RADIUS: float = 12.0      # cells

ROBOT_COLORS = [
    "#00B8D4",  # cyan
    "#FF6D00",  # orange
    "#AA00FF",  # violet
    "#64DD17",  # lime
    "#FF1744",  # rose
    "#00C853",  # green
    "#FFD600",  # gold
    "#2979FF",  # blue
    "#F50057",  # pink
    "#00BFA5",  # teal
]
