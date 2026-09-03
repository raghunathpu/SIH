"""
FleetMind — Task Allocation & Reassignment

Distributed task allocation:
  1. Unassigned tasks are offered to all robots (TASK_OFFER broadcast).
  2. Each robot evaluates the task and sends a TASK_BID with its cost estimate.
  3. The task manager awards the task to the best bidder (TASK_AWARD).
  4. On robot failure, affected tasks are reassigned via the same bidding process.

Cost estimation considers:
  • Estimated travel distance (Manhattan) to pickup + pickup-to-dropoff
  • Battery level
  • Current workload (has existing task?)
  • Task priority / urgency

This module provides the *evaluation* logic.  The actual message exchange
happens in robot_agent.py.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models import (
    Position,
    RobotStatus,
    Task,
    TaskStatus,
    Message,
    MessageType,
)


def estimate_task_cost(
    robot_position: Position,
    robot_battery: float,
    robot_has_task: bool,
    task: Task,
) -> float:
    """
    Estimate cost for a robot to execute a task.
    Lower cost = better candidate.

    Components:
      distance_cost   = manhattan(robot → pickup) + manhattan(pickup → dropoff)
      battery_penalty  = 100 if battery < 20 else 0
      workload_penalty = 50 if robot already has a task
      urgency_bonus    = -20 * task.priority  (higher priority → lower cost)
    """
    dist_to_pickup = robot_position.manhattan_distance(task.pickup)
    pickup_to_dropoff = task.pickup.manhattan_distance(task.dropoff)
    distance_cost = float(dist_to_pickup + pickup_to_dropoff)

    battery_penalty = 100.0 if robot_battery < 20.0 else 0.0
    workload_penalty = 50.0 if robot_has_task else 0.0
    urgency_bonus = -20.0 * task.priority

    return distance_cost + battery_penalty + workload_penalty + urgency_bonus


def select_best_candidate(
    bids: Dict[str, float],
) -> Optional[str]:
    """
    From a dict of robot_id → cost, return the best (lowest cost).
    Returns None if *bids* is empty.
    """
    if not bids:
        return None
    return min(bids, key=bids.get)  # type: ignore[arg-type]


class TaskPool:
    """
    Central task pool.  This is infrastructure (like a shared task board),
    not a decision-maker.  Robots read from the board via messages and
    bid for tasks.

    The pool does NOT decide which robot gets which task — that is
    decided by the bidding protocol in robot_agent.py.
    """

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._next_id: int = 1

    def add_task(self, task: Task) -> str:
        """Add a task to the pool. Returns the task_id."""
        if not task.task_id:
            task.task_id = f"TASK-{self._next_id:03d}"
            self._next_id += 1
        self.tasks[task.task_id] = task
        return task.task_id

    def get_pending_tasks(self) -> List[Task]:
        """Return tasks that need assignment."""
        return [t for t in self.tasks.values()
                if t.status == TaskStatus.PENDING]

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def assign_task(self, task_id: str, robot_id: str, tick: int):
        """Mark a task as assigned to a robot."""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.ASSIGNED
            task.assigned_robot = robot_id
            task.start_time = tick

    def start_picking(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.PICKING

    def start_delivering(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.DELIVERING

    def complete_task(self, task_id: str, tick: int):
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completion_time = tick

    def fail_task(self, task_id: str):
        """Mark a task as failed (robot became unavailable)."""
        task = self.tasks.get(task_id)
        if task and task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            task.status = TaskStatus.PENDING
            task.assigned_robot = None
            task.start_time = None

    def unassign_robot_tasks(self, robot_id: str) -> List[str]:
        """
        Unassign all tasks from a robot (on failure).
        Returns list of task_ids that need reassignment.
        """
        affected: List[str] = []
        for task in self.tasks.values():
            if task.assigned_robot == robot_id and task.status not in (
                TaskStatus.COMPLETED, TaskStatus.CANCELLED
            ):
                task.status = TaskStatus.PENDING
                task.assigned_robot = None
                task.start_time = None
                affected.append(task.task_id)
        return affected

    def get_completed_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values()
                if t.status == TaskStatus.COMPLETED]

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def clear(self):
        self.tasks.clear()
        self._next_id = 1

    def get_stats(self) -> Dict[str, int]:
        """Summary counts by status."""
        stats: Dict[str, int] = {}
        for task in self.tasks.values():
            key = task.status.value
            stats[key] = stats.get(key, 0) + 1
        return stats


class TaskBroker:
    """
    Contract Net Protocol Auctioneer.
    Manages broadcasting TASK_OFFER, collecting TASK_BID, and issuing TASK_AWARD.
    """
    def __init__(self, task_pool: TaskPool, message_bus):
        self.task_pool = task_pool
        self.message_bus = message_bus
        self.message_bus.register("SYSTEM")
        self.auctions: Dict[str, Dict[str, float]] = {}  # task_id -> {robot_id -> bid_cost}
        self.auction_start_ticks: Dict[str, int] = {}    # task_id -> tick
        self.auction_duration = 5  # wait 5 ticks for bids

    def tick(self, current_tick: int):
        # 1. Start auctions for pending tasks
        pending = self.task_pool.get_pending_tasks()
        for task in pending:
            # If not already auctioning or awarded
            if task.task_id not in self.auctions and task.task_id not in self.auction_start_ticks:
                self.auctions[task.task_id] = {}
                self.auction_start_ticks[task.task_id] = current_tick
                
                # Broadcast TASK_OFFER
                msg = Message(
                    sender_id="SYSTEM",
                    type=MessageType.TASK_OFFER,
                    payload={"task_id": task.task_id, "priority": task.priority, "pickup": {"x": task.pickup.x, "y": task.pickup.y}}
                )
                self.message_bus.send(msg)

        # 2. Process incoming bids
        inbox = self.message_bus.receive("SYSTEM")
        for msg in inbox:
            if msg.type == MessageType.TASK_BID:
                task_id = msg.payload.get("task_id")
                cost = msg.payload.get("cost")
                if task_id in self.auctions:
                    self.auctions[task_id][msg.sender_id] = cost

        # 3. Close auctions
        for task_id, start_tick in list(self.auction_start_ticks.items()):
            if current_tick - start_tick >= self.auction_duration:
                bids = self.auctions.get(task_id, {})
                if bids:
                    best_robot = min(bids, key=bids.get)
                    self.task_pool.assign_task(task_id, best_robot, current_tick)
                    # Broadcast TASK_AWARD
                    award_msg = Message(
                        sender_id="SYSTEM",
                        target_id=best_robot,
                        type=MessageType.TASK_AWARD,
                        payload={"task_id": task_id}
                    )
                    self.message_bus.send(award_msg)
                
                # Cleanup
                if task_id in self.auctions:
                    del self.auctions[task_id]
                del self.auction_start_ticks[task_id]
