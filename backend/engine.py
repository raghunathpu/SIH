"""
FleetMind — Simulation Engine

Orchestrates the tick loop, applies physics, detects collisions,
manages timed events (obstacles, failures), and collects metrics.

IMPORTANT: The engine is **infrastructure**.  It does NOT make
robot intelligence decisions.  Each robot's tick() method handles
all local planning, conflict resolution, and negotiation.

The engine only:
  • advances the clock
  • calls each robot's tick()
  • checks for physical collisions (safety net)
  • applies timed scenario events
  • aggregates metrics
  • serialises state for the frontend
"""

from __future__ import annotations

import asyncio
import random
from typing import Callable, Dict, List, Optional, Set

from models import (
    ROBOT_COLORS,
    TICKS_PER_MOVE,
    ConflictInfo,
    Position,
    RobotStatus,
    SimulationEvent,
    SimulationMetrics,
    Task,
    TaskStatus,
)
from warehouse import Warehouse
from message_bus import SimulatedNetwork
from robot_agent import RobotAgent
from task_manager import TaskPool, TaskBroker
from scenarios import ScenarioConfig, make_tasks
from temporal_planner import SpaceTimeGrid


class SimulationEngine:
    """
    Discrete-time simulation of a multi-AMR warehouse fleet.

    Usage::

        engine = SimulationEngine()
        engine.load_scenario(scenario_config)
        while engine.running:
            engine.step()
            state = engine.get_state()
    """

    def __init__(self):
        self.warehouse: Warehouse = Warehouse()
        self.message_bus: SimulatedNetwork = SimulatedNetwork()
        self.task_pool: TaskPool = TaskPool()

        self.robots: Dict[str, RobotAgent] = {}
        self.tick: int = 0
        self.running: bool = False
        self.speed: float = 1.0

        self.metrics: SimulationMetrics = SimulationMetrics()
        self.events: List[SimulationEvent] = []
        self.conflicts: List[ConflictInfo] = []

        self._scenario: Optional[ScenarioConfig] = None
        self._conflict_counter: int = 0

        # Baseline mode flag
        self.baseline_mode: bool = False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  SCENARIO LOADING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def load_scenario(self, cfg: ScenarioConfig, baseline: bool = False):
        """
        Initialise the simulation from a scenario configuration.
        """
        self._scenario = cfg
        self.baseline_mode = baseline or cfg.baseline_mode
        self.tick = 0
        self.running = False
        self.events.clear()
        self.conflicts.clear()
        self.metrics.reset()
        self._conflict_counter = 0

        # Set random seed
        random.seed(cfg.seed)

        # Reset warehouse
        self.warehouse = Warehouse()
        self.warehouse.clear_obstacles()

        # Reset message bus
        self.message_bus.clear_all()

        # Reset task pool
        self.task_pool.clear()

        # Create tasks
        tasks = make_tasks(cfg.tasks)
        for task in tasks:
            self.task_pool.add_task(task)
        self.metrics.tasks_total = len(tasks)

        # Create robots
        self.robots.clear()
        for i, (robot_id, pos_tuple) in enumerate(cfg.robots.items()):
            pos = Position(*pos_tuple)
            color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
            agent = RobotAgent(
                robot_id=robot_id,
                start_position=pos,
                color=color,
                warehouse=self.warehouse,
                message_bus=self.message_bus,
                task_pool=self.task_pool,
            )
            agent.baseline_mode = self.baseline_mode
            self.robots[robot_id] = agent

        self._log_event("SYSTEM", None,
            f"Loaded scenario: {cfg.name} ({'BASELINE' if self.baseline_mode else 'DISTRIBUTED'})")

    def reset(self):
        """Reset to the loaded scenario's initial state."""
        if self._scenario:
            self.load_scenario(self._scenario, self.baseline_mode)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TICK
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def step(self) -> bool:
        """
        Advance simulation by one tick.
        Returns False if the simulation should stop.
        """
        # ── network step ─────────────────────────────────
        self.message_bus.step(self.tick, self.robots)

        # ── task broker ──────────────────────────────────
        # (Task allocation is now decentralized)

        # ── failover detection ───────────────────────────
        for robot in self.robots.values():
            if robot.status == RobotStatus.UNAVAILABLE:
                # Unassign task if it held one so it can be re-offered
                reassigned = self.task_pool.unassign_robot_tasks(robot.robot_id)
                if reassigned:
                    self._log_event("SYSTEM", None, f"Recovered tasks {reassigned} from failed {robot.robot_id}")

        # ── timed events ─────────────────────────────────
        self._apply_timed_events()

        # ── robot decision cycles (ASYNCHRONOUS) ─────────
        # Build currently occupied cells mapping
        occupied_cells = {r.position: r.robot_id for r in self.robots.values() if r.status != RobotStatus.UNAVAILABLE}

        # Run all robot ticks concurrently!
        await asyncio.gather(*(
            robot.tick_async(self.tick, occupied_cells=occupied_cells)
            for robot in self.robots.values()
        ))

        # Collect robot events (they are pushed to lists synchronously inside async methods, which is safe in python asyncio)
        for robot in self.robots.values():
            if robot.status != RobotStatus.UNAVAILABLE:
                for ev in robot.events:
                    self.events.append(ev)
                    if ev.event_type == "NEGOTIATION":
                        self.metrics.conflicts_resolved += 1
                    elif ev.event_type == "REROUTE":
                        self.metrics.reroutes += 1
                    elif ev.event_type == "DEADLOCK":
                        self.metrics.deadlocks_detected += 1
                    elif ev.event_type == "TASK" and "reassign" in ev.description.lower():
                        self.metrics.task_reassignments += 1

        # ── collision detection ──────────────────────────
        self._check_collisions()

        # ── conflict zone detection ──────────────────────
        self._detect_conflict_zones()

        # ── task completion check ────────────────────────
        self._update_task_metrics()

        # ── communication metrics ────────────────────────
        self.metrics.communication_events = self.message_bus.total_sent

        # ── waiting time metrics ─────────────────────────
        self._update_waiting_metrics()

        # ── distance metrics ─────────────────────────────
        self.metrics.total_distance = sum(
            r.distance_travelled for r in self.robots.values()
        )

        # ── advance tick ─────────────────────────────────
        self.tick += 1

        # ── check stop conditions ────────────────────────
        if self._scenario and self._scenario.max_ticks > 0:
            if self.tick >= self._scenario.max_ticks:
                self.running = False
                self._log_event("SYSTEM", None, "Max ticks reached")
                return False

        # All tasks completed?
        all_done = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)
            for t in self.task_pool.get_all_tasks()
        ) if self.task_pool.get_all_tasks() else False

        if all_done:
            self.running = False
            self._log_event("SYSTEM", None, "All tasks completed")
            return False

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TIMED EVENTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _apply_timed_events(self):
        if not self._scenario:
            return

        # Dynamic obstacles
        obs = self._scenario.timed_obstacles.get(self.tick, [])
        for pos_tuple in obs:
            pos = Position(*pos_tuple)
            self.warehouse.add_obstacle(pos)
            self._log_event("OBSTACLE", None, f"Dynamic obstacle at {pos_tuple}")
            # Alert all robots
            self.message_bus.send(
                __import__("models").Message(
                    type=__import__("models").MessageType.OBSTACLE_ALERT,
                    sender_id="SYSTEM",
                    timestamp=self.tick,
                    data={"cells": [pos_tuple]},
                )
            )

        # Aisle blocks
        blocks = self._scenario.timed_aisle_blocks.get(self.tick, {})
        for aisle_id, cells in blocks.items():
            cell_positions = [Position(*c) for c in cells]
            self.warehouse.block_aisle(aisle_id, cell_positions)
            self._log_event("OBSTACLE", None, f"Aisle {aisle_id} blocked")

        # Robot failures
        failures = self._scenario.timed_failures.get(self.tick, [])
        for robot_id in failures:
            if robot_id in self.robots:
                self.robots[robot_id].make_unavailable(self.tick)
                self.metrics.unavailable_robots += 1
                self._log_event("SYSTEM", robot_id, f"{robot_id} became unavailable")

        # Robot recoveries
        recoveries = self._scenario.timed_recoveries.get(self.tick, [])
        for robot_id in recoveries:
            if robot_id in self.robots:
                self.robots[robot_id].make_available(self.tick)
                self._log_event("SYSTEM", robot_id, f"{robot_id} recovered")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  COLLISION DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _check_collisions(self):
        """
        Safety-net collision detection.
        This checks the ACTUAL positions after all robots have moved.
        Conflicts should be resolved before this point — any collision
        here indicates a coordination failure.
        """
        active = [r for r in self.robots.values()
                  if r.status != RobotStatus.UNAVAILABLE]

        # Same-cell collisions
        occupied: Dict[Position, str] = {}
        for r in active:
            if r.position in occupied:
                other_id = occupied[r.position]
                self.metrics.collisions += 1
                self._log_event("COLLISION", r.robot_id,
                    f"COLLISION: {r.robot_id} and {other_id} at {r.position.to_tuple()}")
            else:
                occupied[r.position] = r.robot_id

        # Swap collisions (head-on pass-through)
        for i, r1 in enumerate(active):
            for r2 in active[i+1:]:
                if (r1.position == r2.prev_position and
                    r2.position == r1.prev_position and
                    r1.position != r2.position):
                    self.metrics.collisions += 1
                    self._log_event("COLLISION", r1.robot_id,
                        f"SWAP COLLISION: {r1.robot_id} ↔ {r2.robot_id}")

        # Near-collision tracking (adjacent cells)
        for i, r1 in enumerate(active):
            for r2 in active[i+1:]:
                dist = r1.position.euclidean_distance(r2.position)
                if dist < self.metrics.min_separation:
                    self.metrics.min_separation = dist
                if r1.position != r2.position and dist <= 1.5:
                    self.metrics.near_collisions += 1

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  CONFLICT ZONE DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _detect_conflict_zones(self):
        """Track active conflict zones for visualisation."""
        active = [r for r in self.robots.values()
                  if r.status in (RobotStatus.WAITING, RobotStatus.NEGOTIATING,
                                  RobotStatus.APPROACHING_CONFLICT)]
        for r in active:
            if r.waiting_for and r.waiting_for in self.robots:
                self.metrics.num_conflicts += 1

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TASK & WAITING METRICS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _update_task_metrics(self):
        completed = self.task_pool.get_completed_tasks()
        self.metrics.tasks_completed = len(completed)

        if completed:
            times = [
                (t.completion_time - t.creation_time)
                for t in completed
                if t.completion_time is not None
            ]
            if times:
                self.metrics.total_task_completion_time = sum(times)
                self.metrics.average_task_completion_time = sum(times) / len(times)
                self.metrics.throughput = (
                    len(completed) / max(1, self.tick) * 100
                )

    def _update_waiting_metrics(self):
        total_wt = sum(r.total_waiting_time for r in self.robots.values())
        self.metrics.total_waiting_time = total_wt
        active_count = sum(
            1 for r in self.robots.values()
            if r.status != RobotStatus.UNAVAILABLE
        )
        if active_count > 0:
            self.metrics.average_waiting_time = total_wt / active_count

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  EXTERNAL ACTIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def inject_obstacle(self, x: int, y: int):
        pos = Position(x, y)
        if self.warehouse.add_obstacle(pos):
            self._log_event("OBSTACLE", None, f"Obstacle injected at ({x}, {y})")
            # Alert robots
            from models import Message, MessageType
            self.message_bus.send(Message(
                type=MessageType.OBSTACLE_ALERT,
                sender_id="SYSTEM",
                timestamp=self.tick,
                data={"cells": [(x, y)]},
            ))

    def remove_obstacle(self, x: int, y: int):
        pos = Position(x, y)
        self.warehouse.remove_obstacle(pos)
        self._log_event("OBSTACLE", None, f"Obstacle removed at ({x}, {y})")

    def fail_robot(self, robot_id: str):
        if robot_id in self.robots:
            self.robots[robot_id].make_unavailable(self.tick)
            self.metrics.unavailable_robots += 1
            self._log_event("SYSTEM", robot_id, f"{robot_id} failed")

    def recover_robot(self, robot_id: str):
        if robot_id in self.robots:
            self.robots[robot_id].make_available(self.tick)
            self._log_event("SYSTEM", robot_id, f"{robot_id} recovered")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  LOGGING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _log_event(self, event_type: str, robot_id: Optional[str], description: str):
        self.events.append(SimulationEvent(
            tick=self.tick,
            event_type=event_type,
            robot_id=robot_id,
            description=description,
        ))
        # Cap event log
        if len(self.events) > 1000:
            self.events = self.events[-500:]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  STATE SERIALISATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_state(self, include_warehouse: bool = True) -> dict:
        """Full simulation state for the frontend."""
        state = {
            "tick": self.tick,
            "running": self.running,
            "speed": self.speed,
            "baseline_mode": self.baseline_mode,
            "scenario": self._scenario.scenario_id if self._scenario else None,
            "scenario_name": self._scenario.name if self._scenario else None,
            "robots": {rid: r.to_dict() for rid, r in self.robots.items()},
            "tasks": [t.to_dict() for t in self.task_pool.get_all_tasks()],
            "metrics": self.metrics.to_dict(),
            "events": [e.to_dict() for e in self.events[-100:]],
            "comm_graph": self.message_bus.get_comm_graph(
                recent_ticks=15, current_tick=self.tick
            ),
            "comm_summary": self.message_bus.get_comm_summary(),
        }
        if include_warehouse:
            state["warehouse"] = self.warehouse.to_dict()
        return state
