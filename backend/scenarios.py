"""
FleetMind — Scenario Definitions

10 named scenarios with deterministic robot starts, task lists,
obstacle placements, and configuration.  Each scenario is a
plain dataclass — no code, just data.

Scenarios are loaded by name.  No source-code edits needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models import Position, Task, TaskStatus


@dataclass
class ScenarioConfig:
    """Complete configuration for one simulation scenario."""
    scenario_id: str
    name: str
    description: str
    seed: int = 42

    # Robot start positions  {robot_id: (x, y)}
    robots: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    # Tasks
    tasks: List[Dict] = field(default_factory=list)

    # Dynamic obstacles injected at specific ticks  {tick: [(x,y), ...]}
    timed_obstacles: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)

    # Blocked aisles injected at specific ticks  {tick: {aisle_id: [(x,y), ...]}}
    timed_aisle_blocks: Dict[int, Dict[str, List[Tuple[int, int]]]] = field(default_factory=dict)

    # Robot failures at specific ticks  {tick: [robot_id, ...]}
    timed_failures: Dict[int, List[str]] = field(default_factory=dict)

    # Robot recoveries at specific ticks
    timed_recoveries: Dict[int, List[str]] = field(default_factory=dict)

    # Use baseline (stop-and-wait) mode?
    baseline_mode: bool = False

    # Max ticks before auto-stop (0 = unlimited)
    max_ticks: int = 600


def make_tasks(raw: List[Dict], creation_time: int = 0) -> List[Task]:
    """Convert raw task dicts from scenario config to Task objects."""
    tasks = []
    for i, d in enumerate(raw):
        tasks.append(Task(
            task_id=d.get("task_id", f"TASK-{i+1:03d}"),
            pickup=Position(*d["pickup"]),
            dropoff=Position(*d["dropoff"]),
            priority=d.get("priority", 1),
            deadline=d.get("deadline"),
            creation_time=creation_time,
        ))
    return tasks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SCENARIO CATALOGUE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIOS: Dict[str, ScenarioConfig] = {}


def _register(cfg: ScenarioConfig):
    SCENARIOS[cfg.scenario_id] = cfg


# ──────────────────────────────────────────────────────────
#  01 — OPEN WAREHOUSE / NORMAL TRAFFIC
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="01_OPEN_WAREHOUSE",
    name="Open Warehouse",
    description="3 AMRs, moderate tasks, no forced conflicts. Tests basic operation.",
    seed=42,
    robots={
        "AMR-01": (29, 0),
        "AMR-02": (28, 0),
        "AMR-03": (27, 0),
    },
    tasks=[
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (2, 1), "priority": 1},
        {"task_id": "TASK-002", "pickup": (3, 18), "dropoff": (3, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (4, 18), "dropoff": (4, 1), "priority": 1},
        {"task_id": "TASK-004", "pickup": (15, 18), "dropoff": (15, 1), "priority": 2},
        {"task_id": "TASK-005", "pickup": (16, 18), "dropoff": (16, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  02 — CROSS TRAFFIC (OVERLAPPING PATHS)
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="02_CROSS_TRAFFIC",
    name="Cross Traffic",
    description="Robots must cross paths at intersections. Tests conflict detection and negotiation.",
    seed=42,
    robots={
        "AMR-01": (0, 5),
        "AMR-02": (10, 0),
        "AMR-03": (0, 11),
    },
    tasks=[
        # AMR-01: left→right across row 5
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (26, 1), "priority": 2},
        # AMR-02: top→bottom through column 10
        {"task_id": "TASK-002", "pickup": (15, 18), "dropoff": (3, 1), "priority": 1},
        # AMR-03: left→right across row 11
        {"task_id": "TASK-003", "pickup": (4, 18), "dropoff": (16, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  03 — NARROW INTERSECTION / CHOKE POINT
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="03_CHOKE_POINT",
    name="Choke Point",
    description="All robots must pass through the same narrow vertical aisle. Tests queuing and priority.",
    seed=42,
    robots={
        "AMR-01": (4, 2),
        "AMR-02": (4, 14),
        "AMR-03": (7, 2),
    },
    tasks=[
        # AMR-01 needs to go down through narrow aisle at col 4
        {"task_id": "TASK-001", "pickup": (4, 18), "dropoff": (2, 1), "priority": 2},
        # AMR-02 needs to go up through same narrow aisle at col 4
        {"task_id": "TASK-002", "pickup": (3, 18), "dropoff": (4, 1), "priority": 1},
        # AMR-03 uses adjacent narrow aisle at col 7
        {"task_id": "TASK-003", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  04 — HEAD-ON NARROW AISLE
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="04_HEAD_ON_AISLE",
    name="Head-On Aisle",
    description="Two robots face each other in a 1-cell-wide corridor. One must yield.",
    seed=42,
    robots={
        "AMR-01": (4, 5),
        "AMR-02": (4, 11),
        "AMR-03": (29, 0),
    },
    tasks=[
        # AMR-01 goes down through narrow aisle at col 4 (rows 6-10)
        {"task_id": "TASK-001", "pickup": (4, 18), "dropoff": (4, 1), "priority": 1},
        # AMR-02 goes up through same aisle
        {"task_id": "TASK-002", "pickup": (3, 18), "dropoff": (3, 1), "priority": 1},
        # AMR-03 operates independently
        {"task_id": "TASK-003", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  05 — THREE-WAY INTERSECTION CONFLICT
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="05_THREE_WAY_CONFLICT",
    name="Three-Way Conflict",
    description="3 robots converge on the same intersection simultaneously.",
    seed=42,
    robots={
        "AMR-01": (8, 5),
        "AMR-02": (12, 5),
        "AMR-03": (10, 2),
    },
    tasks=[
        # All three need to pass through intersection around (10, 5)
        {"task_id": "TASK-001", "pickup": (15, 18), "dropoff": (2, 1), "priority": 1},
        {"task_id": "TASK-002", "pickup": (2, 18), "dropoff": (16, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (4, 18), "dropoff": (15, 1), "priority": 2},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  06 — DEADLOCK / CYCLIC WAITING
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="06_DEADLOCK_RECOVERY",
    name="Deadlock Recovery",
    description="Three robots form a circular wait dependency. Tests cycle detection and recovery.",
    seed=42,
    robots={
        "AMR-01": (4, 5),
        "AMR-02": (7, 5),
        "AMR-03": (4, 11),
    },
    tasks=[
        # AMR-01 needs to go where AMR-02 is heading
        {"task_id": "TASK-001", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
        # AMR-02 needs to go where AMR-03 is heading
        {"task_id": "TASK-002", "pickup": (4, 18), "dropoff": (2, 1), "priority": 1},
        # AMR-03 needs to go where AMR-01 is heading
        {"task_id": "TASK-003", "pickup": (3, 18), "dropoff": (15, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  07 — DYNAMIC AISLE BLOCKAGE
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="07_AISLE_BLOCKAGE",
    name="Aisle Blockage",
    description="An aisle is blocked mid-task. Affected robots must detect, reroute, and continue.",
    seed=42,
    robots={
        "AMR-01": (4, 0),
        "AMR-02": (15, 0),
        "AMR-03": (29, 0),
    },
    tasks=[
        {"task_id": "TASK-001", "pickup": (4, 18), "dropoff": (4, 1), "priority": 2},
        {"task_id": "TASK-002", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (2, 18), "dropoff": (15, 1), "priority": 1},
    ],
    # Block narrow aisle at col 4 after 60 ticks
    timed_obstacles={
        60: [(4, 7), (4, 8), (4, 9)],
    },
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  08 — TASK REASSIGNMENT (ROBOT FAILURE)
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="08_TASK_REASSIGNMENT",
    name="Task Reassignment",
    description="A robot fails mid-task. Its task is reassigned to another available robot.",
    seed=42,
    robots={
        "AMR-01": (0, 0),
        "AMR-02": (15, 0),
        "AMR-03": (29, 0),
    },
    tasks=[
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (2, 1), "priority": 2},
        {"task_id": "TASK-002", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (3, 18), "dropoff": (15, 1), "priority": 1},
        {"task_id": "TASK-004", "pickup": (4, 18), "dropoff": (3, 1), "priority": 1},
    ],
    # AMR-02 fails at tick 80
    timed_failures={80: ["AMR-02"]},
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  09 — HIGH TRAFFIC FLEET
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="09_HIGH_TRAFFIC",
    name="High Traffic",
    description="5 robots, many tasks, heavy congestion. Stress test.",
    seed=42,
    robots={
        "AMR-01": (29, 0),
        "AMR-02": (28, 0),
        "AMR-03": (27, 0),
        "AMR-04": (26, 0),
        "AMR-05": (25, 0),
    },
    tasks=[
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (2, 1), "priority": 2},
        {"task_id": "TASK-002", "pickup": (3, 18), "dropoff": (3, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (4, 18), "dropoff": (4, 1), "priority": 1},
        {"task_id": "TASK-004", "pickup": (15, 18), "dropoff": (15, 1), "priority": 3},
        {"task_id": "TASK-005", "pickup": (16, 18), "dropoff": (16, 1), "priority": 1},
        {"task_id": "TASK-006", "pickup": (2, 18), "dropoff": (16, 1), "priority": 2},
        {"task_id": "TASK-007", "pickup": (15, 18), "dropoff": (2, 1), "priority": 1},
        {"task_id": "TASK-008", "pickup": (3, 18), "dropoff": (15, 1), "priority": 1},
    ],
    max_ticks=0,
))

# ──────────────────────────────────────────────────────────
#  10 — BENCHMARK (OVERLAPPING PATHS)
# ──────────────────────────────────────────────────────────
_register(ScenarioConfig(
    scenario_id="10_BENCHMARK",
    name="Benchmark",
    description=(
        "Benchmark scenario with overlapping paths designed to show "
        "the advantage of distributed coordination vs stop-and-wait. "
        "3 robots with crossing routes through common intersections."
    ),
    seed=42,
    robots={
        "AMR-01": (0, 2),
        "AMR-02": (10, 0),
        "AMR-03": (22, 2),
    },
    tasks=[
        # AMR-01: left side pickup → right side dropoff (crosses middle)
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (26, 1), "priority": 2},
        # AMR-02: middle pickup → left dropoff (crosses AMR-01's path)
        {"task_id": "TASK-002", "pickup": (15, 18), "dropoff": (3, 1), "priority": 1},
        # AMR-03: right pickup → middle dropoff (crosses both paths)
        {"task_id": "TASK-003", "pickup": (16, 18), "dropoff": (15, 1), "priority": 1},
        # Second round of tasks to measure steady-state
        {"task_id": "TASK-004", "pickup": (3, 18), "dropoff": (16, 1), "priority": 2},
        {"task_id": "TASK-005", "pickup": (4, 18), "dropoff": (2, 1), "priority": 1},
        {"task_id": "TASK-006", "pickup": (15, 18), "dropoff": (4, 1), "priority": 1},
    ],
    max_ticks=0,
))


# ── DEMO MODE SCENARIO ──────────────────────────────────
_register(ScenarioConfig(
    scenario_id="DEMO_MODE",
    name="Demo Mode",
    description=(
        "Deterministic 3-5 minute demo showcasing: normal operation, "
        "conflict negotiation, aisle blockage, rerouting, robot failure, "
        "task reassignment, deadlock, recovery, and benchmark."
    ),
    seed=42,
    robots={
        "AMR-01": (29, 0),
        "AMR-02": (28, 0),
        "AMR-03": (27, 0),
    },
    tasks=[
        # Phase 1: Normal operations
        {"task_id": "TASK-001", "pickup": (2, 18), "dropoff": (2, 1), "priority": 2},
        {"task_id": "TASK-002", "pickup": (15, 18), "dropoff": (16, 1), "priority": 1},
        {"task_id": "TASK-003", "pickup": (4, 18), "dropoff": (15, 1), "priority": 1},
        # Phase 2: Crossing paths
        {"task_id": "TASK-004", "pickup": (3, 18), "dropoff": (26, 1), "priority": 2},
        {"task_id": "TASK-005", "pickup": (16, 18), "dropoff": (3, 1), "priority": 1},
        {"task_id": "TASK-006", "pickup": (2, 18), "dropoff": (4, 1), "priority": 1},
    ],
    timed_obstacles={
        # Phase 3: Aisle blockage at tick 120
        120: [(4, 7), (4, 8), (4, 9)],
    },
    timed_failures={
        # Phase 4: Robot failure at tick 200
        200: ["AMR-02"],
    },
    timed_recoveries={
        # Phase 5: Recovery at tick 280
        280: ["AMR-02"],
    },
    max_ticks=0,
))


def get_scenario(scenario_id: str) -> Optional[ScenarioConfig]:
    return SCENARIOS.get(scenario_id)


def list_scenarios() -> List[Dict[str, str]]:
    return [
        {
            "id": s.scenario_id,
            "name": s.name,
            "description": s.description,
            "robots": len(s.robots),
            "tasks": len(s.tasks),
        }
        for s in SCENARIOS.values()
    ]
