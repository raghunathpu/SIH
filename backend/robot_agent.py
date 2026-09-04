"""
FleetMind — Autonomous Robot Agent

This is the core of the distributed intelligence.  Each RobotAgent
instance owns its state, runs its own decision cycle, and communicates
with peers ONLY through the MessageBus.

No agent ever reads another agent's internal fields directly.
All peer knowledge comes from received messages.

Decision cycle (per tick):
  1. receive messages → update peer knowledge
  2. send heartbeat (periodic)
  3. check peer liveness
  4. drain battery
  5. if no task → bid for one
  6. if has task → execute task state machine
  7. broadcast own state
"""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional, Set

from models import (
    BATTERY_CRITICAL,
    BATTERY_DRAIN_IDLE,
    BATTERY_DRAIN_MOVE,
    CONFLICT_LOOKAHEAD,
    DEADLOCK_WAIT_THRESHOLD,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    MAX_WAIT_BEFORE_REROUTE,
    PICK_DROP_TICKS,
    PREDICTION_HORIZON_TICKS,
    TICKS_PER_MOVE,
    Message,
    MessageType,
    PeerKnowledge,
    Position,
    RobotStatus,
    SimulationEvent,
    Task,
    TaskStatus,
    CellType,
)
from astar import astar, find_alternative_path
from temporal_planner import astar_3d, SpaceTimeGrid
from conflict_resolver import (
    LocalConflict,
    compare_priority,
    detect_conflicts,
    should_reroute_vs_wait,
)
from deadlock_detector import DeadlockDetector
from task_manager import estimate_task_cost
from collision_predictor import CollisionPredictor, CollisionPrediction, CollisionRisk


from network_interface import NetworkInterface

class RobotAgent:
    """
    Autonomous robot agent with local decision-making.

    Every tick the simulation engine calls ``tick(current_tick)``.
    The agent processes messages, updates its knowledge, plans,
    detects conflicts, negotiates, and moves — all locally.
    """

    def __init__(
        self,
        robot_id: str,
        start_position: Position,
        color: str,
        warehouse,              # Warehouse instance (read-only grid/graph)
        message_bus: NetworkInterface, # Network abstraction
        task_pool,              # TaskPool instance (shared board)
        space_time_grid: SpaceTimeGrid = None,  # Shared grid (engine-owned)
    ):
        self.robot_id = robot_id
        self.color = color
        self.warehouse = warehouse
        self.message_bus = message_bus
        self.task_pool = task_pool
        # Use shared grid if provided; fall back to private one only in unit tests
        self.space_time_grid = space_time_grid if space_time_grid is not None else SpaceTimeGrid()

        # ── position & movement ──────────────────────────
        self.position: Position = start_position
        self.prev_position: Position = start_position
        self.render_x: float = float(start_position.x)
        self.render_y: float = float(start_position.y)
        self.velocity: float = 0.0
        self.heading: float = 0.0

        # ── movement state ───────────────────────────────
        self.moving: bool = False
        self.move_progress: int = 0
        self.target_cell: Optional[Position] = None

        # ── robot status ─────────────────────────────────
        self.status: RobotStatus = RobotStatus.IDLE
        self.battery: float = 100.0
        self.distance_travelled: float = 0.0

        # ── task ─────────────────────────────────────────
        self.current_task: Optional[Task] = None
        self.destination: Optional[Position] = None
        self.has_item: bool = False
        self.action_timer: int = 0        # countdown for pick/drop
        self.task_phase: str = "NONE"     # NONE / TO_PICKUP / PICKING / TO_DROPOFF / DROPPING
        
        # ── decentralized bidding ────────────────────────
        # task_id -> {robot_id -> bid_cost}
        self.active_auctions: Dict[str, Dict[str, float]] = {}
        # task_id -> tick_started
        self.auction_start_ticks: Dict[str, int] = {}

        # ── path ─────────────────────────────────────────
        self.planned_path: List[Position] = []

        # ── peer knowledge (from messages only) ──────────
        self.peer_knowledge: Dict[str, PeerKnowledge] = {}
        self.deadlock_detector = DeadlockDetector()

        # ── conflict / waiting ───────────────────────────
        self.waiting_for: Optional[str] = None
        self.waiting_time: int = 0
        self.total_waiting_time: int = 0
        # Ticks spent BLOCKED (no path found at all) — tracked separately
        # from waiting_time (occupied-cell / MAPF wait) so a robot that
        # can't even compute a route also gets an escape hatch instead of
        # sitting there forever holding a stale reservation.
        self.blocked_time: int = 0
        self.decision_reason: str = ""
        self.intent: str = ""
        self.priority: int = 0

        # ── communication ────────────────────────────────
        self.last_heartbeat: int = 0

        # ── mode ─────────────────────────────────────────
        self.baseline_mode: bool = False   # True = stop-and-wait

        # ── predictive collision detection ───────────────────
        self.collision_predictor = CollisionPredictor(robot_id)
        # Predictions from the last tick that were non-SAFE (for to_dict / logging)
        self.active_collision_predictions: List[CollisionPrediction] = []

        # ── hardware telemetry (simulated) ───────────────
        self.hardware = {
            "cpu": 5.0,     # %
            "ram": 128.0,   # MB
            "latency": 5.0, # ms
            "thermal": 40.0 # C
        }

        # ── event output ─────────────────────────────────────
        self.events: List[SimulationEvent] = []

        # ── communication counters ────────────────────────
        self.messages_sent: int = 0
        self.messages_received: int = 0

        # ── initial setup ────────────────────────────────────
        self.message_bus.register(self.robot_id)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  MAIN TICK
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def tick_async(
        self,
        current_tick: int,
        occupied_cells: Optional[Dict[Position, str]] = None,
    ):
        """
        Execute one local decision cycle (asynchronous).

        Parameters
        ----------
        current_tick : int
            Current simulation tick.
        occupied_cells : dict | None
            Sensor-equivalent: maps Position → robot_id for all
            active robots (simulates lidar/camera sensing).
        """
        self.events.clear()
        self._occupied_cells = occupied_cells or {}

        if self.status == RobotStatus.UNAVAILABLE:
            return

        # 1 ── process inbox ──────────────────────────────
        self._process_messages(current_tick)

        # 1b ── predictive collision detection ────────────
        # Runs immediately after messages are processed so peer_knowledge
        # is as fresh as possible before any movement decisions.
        self._run_collision_prediction(current_tick)

        # 2 ── heartbeat ──────────────────────────────────
        if current_tick - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            self._send_heartbeat(current_tick)

        # 3 ── peer liveness ──────────────────────────────
        self._check_peer_liveness(current_tick)

        # 4 ── battery & hardware ─────────────────────────
        self._drain_battery()
        import random
        # Simulate hardware metrics
        self.hardware["cpu"] = max(2.0, min(100.0, self.hardware["cpu"] * 0.8 + random.uniform(0, 15) + (50 if not self.planned_path and self.destination else 0)))
        self.hardware["ram"] = 128.0 + (len(self.planned_path) * 0.1) + random.uniform(-2, 2)
        self.hardware["latency"] = max(1.0, random.uniform(2.0, 10.0))
        target_thermal = 40.0 + (30.0 if self.moving else 0.0) + (self.hardware["cpu"] * 0.2)
        self.hardware["thermal"] += (target_thermal - self.hardware["thermal"]) * 0.05

        # 5 ── if in movement transit, keep moving ────────
        if self.moving:
            self._continue_movement(current_tick)
            return

        # 6 ── pick / drop action timer ───────────────────
        if self.status in (RobotStatus.PICKING, RobotStatus.DROPPING):
            self._continue_action(current_tick)
            return

        # 7 ── task acquisition & bidding ─────────────────
        self._resolve_auctions(current_tick)
        
        if self.current_task is None:
            self._try_acquire_task(current_tick)
            
            if self.current_task is None:
                cell_type = self.warehouse.get_cell_type(self.position)
                if cell_type != CellType.STAGING:
                    self.task_phase = "RETURNING_TO_STAGING"
                    if not self.destination or self.warehouse.get_cell_type(self.destination) != CellType.STAGING:
                        target = self._find_available_staging_area()
                        if target:
                            self.destination = target
                            self.planned_path.clear()
                            self.status = RobotStatus.MOVING
                            self._plan_and_move(current_tick)
                        else:
                            self.status = RobotStatus.IDLE
                            self.velocity = 0.0
                    else:
                        # We already have a STAGING destination. Check if a peer has parked on it.
                        parked = any(p for p in self.peer_knowledge.values() if p.position == self.destination and p.status == RobotStatus.IDLE)
                        if parked:
                            target = self._find_available_staging_area()
                            if target:
                                self.destination = target
                                self.planned_path.clear()
                                self.status = RobotStatus.MOVING
                                self._plan_and_move(current_tick)
                            else:
                                self.destination = None
                                self.status = RobotStatus.IDLE
                                self.velocity = 0.0
                        else:
                            # Path to our existing destination if we aren't moving
                            if self.position != self.destination:
                                self.status = RobotStatus.MOVING
                                self._plan_and_move(current_tick)
                else:
                    self.status = RobotStatus.IDLE
                    self.velocity = 0.0
                    self.destination = None
                    self.planned_path.clear()
            
            self._broadcast_state(current_tick)
            return

        # 8 ── task execution state machine ───────────────
        self._execute_task(current_tick)

        # 9 ── broadcast state ────────────────────────────
        self._broadcast_state(current_tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  MESSAGE PROCESSING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _process_messages(self, tick: int):
        messages = self.message_bus.receive(self.robot_id)
        self.messages_received += len(messages)
        for msg in messages:
            if not msg.validate():
                continue
            if msg.is_stale(tick):
                continue
            self._handle_message(msg, tick)

    def _handle_message(self, msg: Message, tick: int):
        t = msg.type

        if t == MessageType.STATE_UPDATE:
            self._on_state_update(msg, tick)
        elif t == MessageType.INTENT_BROADCAST:
            self._on_intent(msg, tick)
        elif t == MessageType.HEARTBEAT:
            self._on_heartbeat(msg, tick)
        elif t == MessageType.YIELD_NOTIFICATION:
            self._on_yield(msg, tick)
        elif t == MessageType.OBSTACLE_ALERT:
            self._on_obstacle_alert(msg, tick)
        elif t == MessageType.TASK_OFFER:
            self._on_task_offer(msg, tick)
        elif t == MessageType.TASK_BID:
            self._on_task_bid(msg, tick)
        elif t == MessageType.TASK_AWARD:
            self._on_task_award(msg, tick)
        elif t == MessageType.PRIORITY_CLAIM:
            self._on_priority_claim(msg, tick)
        elif t == MessageType.DEADLOCK_DETECTED:
            self._on_deadlock_notification(msg, tick)
        elif t == MessageType.WAIT_FOR:
            self._on_wait_for(msg, tick)
        elif t == MessageType.PATH_INTENT:
            self._on_path_intent(msg, tick)

    def _on_task_bid(self, msg: Message, tick: int):
        task_id = msg.data.get("task_id")
        cost = msg.data.get("cost")
        if not task_id or cost is None: return
        
        # If we aren't tracking this auction, initialize it (we might have missed the OFFER)
        if task_id not in self.active_auctions:
            self.active_auctions[task_id] = {}
            self.auction_start_ticks[task_id] = tick
            
        self.active_auctions[task_id][msg.sender_id] = cost

    def _on_path_intent(self, msg: Message, tick: int):
        path_tuples = msg.data.get("path", [])
        if not path_tuples:
            return
            
        path = [Position(x, y) for x, y in path_tuples]
        
        # Clear old intent from this robot
        self.space_time_grid.clear_robot_reservations(msg.sender_id)
        
        # Reserve new intent starting from the timestamp the message was sent
        self.space_time_grid.reserve_path(msg.sender_id, msg.timestamp, path)

    def _on_state_update(self, msg: Message, tick: int):
        d = msg.data
        sid = msg.sender_id
        
        pos_data = d.get("position")
        pos = Position(*pos_data) if pos_data else None

        path_data = d.get("planned_path", [])
        path = [Position(*p) for p in path_data]

        dest_data = d.get("destination")
        dest = Position(*dest_data) if dest_data else None

        if sid not in self.peer_knowledge:
            self.peer_knowledge[sid] = PeerKnowledge(robot_id=sid, last_update_tick=tick)
            
        pk = self.peer_knowledge[sid]
        
        if pos is not None: pk.position = pos
        if "velocity" in d: pk.velocity = d["velocity"]
        if "heading" in d: pk.heading = d["heading"]
        if "status" in d: pk.status = RobotStatus(d["status"])
        if "intent" in d: pk.intent = d["intent"]
        if "planned_path" in d: pk.planned_path = path
        if "current_task" in d: pk.current_task = d["current_task"]
        if "priority" in d: pk.priority = d["priority"]
        if "waiting_for" in d: pk.waiting_for = d["waiting_for"]
        if "destination" in d: pk.destination = dest
        if "battery" in d: pk.battery = d["battery"]
        pk.last_update_tick = tick

        # Update deadlock detector
        if "waiting_for" in d:
            self.deadlock_detector.update(sid, d.get("waiting_for"))
        else:
            # For full state update, if waiting_for is not there or is None, it means None
            self.deadlock_detector.update(sid, None)

    def _on_intent(self, msg: Message, tick: int):
        sid = msg.sender_id
        d = msg.data
        if sid not in self.peer_knowledge:
            self.peer_knowledge[sid] = PeerKnowledge(robot_id=sid, last_update_tick=tick)
            
        pk = self.peer_knowledge[sid]
        if "intent" in d: pk.intent = d["intent"]
        if "planned_path" in d:
            pk.planned_path = [Position(*p) for p in d["planned_path"]]
        if "destination" in d:
            dest_data = d.get("destination")
            pk.destination = Position(*dest_data) if dest_data else None
        pk.last_update_tick = tick

    def _on_heartbeat(self, msg: Message, tick: int):
        sid = msg.sender_id
        if sid in self.peer_knowledge:
            self.peer_knowledge[sid].last_update_tick = tick
        else:
            self.peer_knowledge[sid] = PeerKnowledge(
                robot_id=sid, last_update_tick=tick
            )

    def _on_yield(self, msg: Message, tick: int):
        # A peer is yielding to us — we can proceed
        sid = msg.sender_id
        if self.waiting_for == sid:
            self.waiting_for = None
            self.waiting_time = 0
            self._log_event(tick, "NEGOTIATION", f"Received yield from {sid}")

    def _on_obstacle_alert(self, msg: Message, tick: int):
        # Invalidate path if it passes through the obstacle
        obs_data = msg.data.get("cells", [])
        obstacle_cells = {Position(*c) for c in obs_data}
        if any(p in obstacle_cells for p in self.planned_path):
            self.planned_path.clear()
            self._log_event(tick, "OBSTACLE", f"Path invalidated by obstacle alert from {msg.sender_id}")

    def _on_task_offer(self, msg: Message, tick: int):
        if self.current_task is not None or self.battery < BATTERY_CRITICAL or self.status == RobotStatus.UNAVAILABLE:
            return
        
        task_id = msg.data.get("task_id")
        pickup_data = msg.data.get("pickup")
        priority = msg.data.get("priority", 1)
        if not task_id or not pickup_data: return

        pickup_pos = Position(pickup_data["x"], pickup_data["y"])
        
        # Simple cost: distance to pickup
        dist = self.position.manhattan_distance(pickup_pos)
        cost = dist - (20.0 * priority)
        if self.battery < 20.0: cost += 100.0

        # Start tracking the auction locally
        if task_id not in self.active_auctions:
            self.active_auctions[task_id] = {}
            self.auction_start_ticks[task_id] = tick
        
        self.active_auctions[task_id][self.robot_id] = cost

        # Broadcast bid to peers
        bid = Message(
            sender_id=self.robot_id,
            target_id=None,  # Broadcast
            type=MessageType.TASK_BID,
            timestamp=tick,
            data={"task_id": task_id, "cost": cost}
        )
        self.message_bus.send(bid)

    def _on_task_award(self, msg: Message, tick: int):
        task_id = msg.data.get("task_id")
        winner_id = msg.data.get("winner_id")
        if not task_id or not winner_id:
            return
            
        # Clean up local auction tracking
        self.active_auctions.pop(task_id, None)
        self.auction_start_ticks.pop(task_id, None)
        
        # If we thought we were bidding on this, but someone else won, log it.
        # (Though we shouldn't have won if our _resolve_auctions math is deterministic, 
        # but network latency could cause split brain, which is fine, the pool enforces safety).
        if winner_id != self.robot_id and self.current_task and self.current_task.task_id == task_id:
            self.current_task = None
            self.task_phase = "NONE"
            self._log_event(tick, "TASK", f"Lost task {task_id} to {winner_id} due to network split-brain")

    def _on_priority_claim(self, msg: Message, tick: int):
        # Peer claims priority — check if we should yield
        pass  # Handled in conflict detection

    def _on_deadlock_notification(self, msg: Message, tick: int):
        # Check if we are the one that should yield
        yield_robot = msg.data.get("yield_robot")
        if yield_robot == self.robot_id:
            self._initiate_reroute(tick, "Deadlock recovery — selected to yield")

    def _on_wait_for(self, msg: Message, tick: int):
        self.deadlock_detector.update(
            msg.sender_id, msg.data.get("waiting_for")
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  HEARTBEAT & LIVENESS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _send_heartbeat(self, tick: int):
        self.last_heartbeat = tick
        self.message_bus.send(Message(
            type=MessageType.HEARTBEAT,
            sender_id=self.robot_id,
            timestamp=tick,
            data={"battery": self.battery, "status": self.status.value},
        ))

    def _check_peer_liveness(self, tick: int):
        for pid, pk in list(self.peer_knowledge.items()):
            if pk.is_stale(tick, HEARTBEAT_TIMEOUT):
                pk.status = RobotStatus.UNAVAILABLE
                # If we were waiting for this peer, stop waiting
                if self.waiting_for == pid:
                    self.waiting_for = None
                    self.waiting_time = 0

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  BATTERY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _drain_battery(self):
        if self.moving:
            self.battery = max(0.0, self.battery - BATTERY_DRAIN_MOVE)
        else:
            self.battery = max(0.0, self.battery - BATTERY_DRAIN_IDLE)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  PREDICTIVE COLLISION DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _run_collision_prediction(self, tick: int):
        """
        Run the local predictive collision detector against all peers
        within DETECTION_RADIUS.

        Only uses self.render_x / render_y / planned_path / velocity and
        self.peer_knowledge — no global state is accessed.

        Side-effects:
        * self.active_collision_predictions updated.
        * WARNING / CRITICAL events appended to self.events (existing system).
        """
        if self.status == RobotStatus.UNAVAILABLE:
            self.active_collision_predictions = []
            return

        predictions = self.collision_predictor.predict(
            my_render_x    = self.render_x,
            my_render_y    = self.render_y,
            my_path        = self.planned_path,
            my_velocity    = self.velocity,
            peer_knowledge = self.peer_knowledge,
            current_tick   = tick,
        )

        self.active_collision_predictions = predictions

        # Log structured events for WARNING and CRITICAL predictions
        for pred in predictions:
            if pred.risk_level in (CollisionRisk.WARNING, CollisionRisk.CRITICAL):
                ttc_str = (
                    f"{pred.time_to_collision:.2f}s"
                    if pred.time_to_collision is not None
                    else "<1 tick"
                )
                pos_str = (
                    str(pred.conflict_position.to_tuple())
                    if pred.conflict_position else "unknown"
                )
                self._log_event(
                    tick,
                    "COLLISION_PREDICTION",
                    f"{self.robot_id} detected predicted collision with "
                    f"{pred.other_robot_id} | "
                    f"TTC: {ttc_str} | "
                    f"Min-sep: {pred.minimum_predicted_distance:.2f} cells | "
                    f"Conflict pos: {pos_str} | "
                    f"Risk: {pred.risk_level.value} | "
                    f"Confidence: {pred.confidence:.2f}",
                )

                # Active avoidance: yield if lower priority (and not currently mid-move)
                #
                # FIX #3: in distributed mode, astar_3d + SpaceTimeGrid already
                # guarantee collision-free paths against any peer whose
                # PATH_INTENT reservations we know about. Previously this block
                # fired an independent reroute on *every* WARNING/CRITICAL tick
                # regardless of that — two robots could each clear + replan
                # their space-time reservations every tick in response to each
                # other's predictions, fighting the MAPF planner and producing
                # exactly the thrash/livelock seen in the benchmark (huge
                # waiting time, tiny reroute count relative to conflict count).
                # We now only let this system override the planner when the
                # planner genuinely doesn't know about the peer yet (stale or
                # dropped PATH_INTENT) — otherwise we trust the existing
                # reservation-based path and treat this as an early-warning
                # signal, not an action trigger. In baseline mode there is no
                # space-time planner, so the original per-tick logic still
                # applies.
                if not self.moving:
                    peer_id = pred.other_robot_id
                    peer = self.peer_knowledge.get(peer_id)
                    if peer:
                        # Active avoidance happens below regardless of baseline_mode since
                        # decentralized planning relies on this prediction step to catch
                        # overlaps resulting from simultaneous pathing.

                        my_prio = self.priority
                        peer_prio = peer.priority

                        should_yield = False
                        if my_prio < peer_prio:
                            should_yield = True
                        elif my_prio == peer_prio and self.robot_id > peer_id:
                            should_yield = True

                        # If we have higher priority, but the other robot is trapped/stopped, we MUST yield!
                        if not should_yield:
                            if peer.status in (RobotStatus.BLOCKED, RobotStatus.WAITING, RobotStatus.UNAVAILABLE):
                                should_yield = True

                        if should_yield:
                            conflict_cell = pred.conflict_position or peer.position or self.position
                            conflict = LocalConflict(
                                other_robot_id=peer_id,
                                cell=conflict_cell,
                                conflict_type=f"PREDICTED_{pred.risk_level.value}",
                                my_distance=max(1, self.position.manhattan_distance(conflict_cell)),
                                peer_distance=(
                                    peer.position.manhattan_distance(conflict_cell)
                                    if peer.position else 1
                                ),
                                peer_priority=peer_prio,
                            )
                            # Route through the same negotiation path used
                            # elsewhere (FIX #1) instead of calling
                            # _initiate_reroute directly, so priority
                            # comparison, waiting_for/deadlock bookkeeping,
                            # and physical-occupancy checks are consistent
                            # no matter which code path detected the conflict.
                            self._handle_conflicts([conflict], tick, self._occupied_cells)
                            break  # Only initiate one reroute per tick

    def _space_time_grid_has_peer_reservations(
        self,
        peer_id: str,
        current_tick: int,
        horizon_ticks: int = PREDICTION_HORIZON_TICKS,
    ) -> bool:
        """
        True when the shared SpaceTimeGrid has a reservation from *peer_id*
        that is actually relevant *now* — i.e. inside
        [current_tick, current_tick + horizon_ticks], or a terminal
        (indefinite) reservation that has already taken effect by then.

        This used to match ANY reservation the peer had EVER made, anywhere
        in the grid — including stale entries from ticks long past. That
        gave false confidence ("the planner knows about this peer") even
        when the peer's relevant near-term intent had never arrived (e.g.
        a dropped/late PATH_INTENT), which is exactly the situation this
        check exists to catch. Scoping it to the live planning horizon
        makes the trust decision accurate.
        """
        cutoff = current_tick + horizon_ticks
        for (t, _pos), res_set in self.space_time_grid.reservations.items():
            if current_tick <= t <= cutoff and peer_id in res_set:
                return True
        for _pos, term_set in self.space_time_grid.terminal_reservations.items():
            for term_tick, term_id in term_set:
                if term_id == peer_id and term_tick <= cutoff:
                    return True
        return False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TASK ACQUISITION & BIDDING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _resolve_auctions(self, tick: int):
        AUCTION_DURATION = 15
        
        for task_id, start_tick in list(self.auction_start_ticks.items()):
            if tick - start_tick >= AUCTION_DURATION:
                # Auction closed. Determine the winner locally.
                bids = dict(self.active_auctions.get(task_id, {}))

                # BUGFIX: this method runs every tick regardless of whether
                # we already have a current_task. A robot can place a bid
                # while idle, then pick up other work before that auction's
                # AUCTION_DURATION window closes. If it was still the low
                # bidder, the code below used to blindly overwrite
                # self.current_task with the newly-won task — silently
                # orphaning whatever it was already doing (that task stays
                # ASSIGNED/PICKING/DELIVERING in the pool forever, since
                # reassignment only happens on robot failure, and nothing
                # else was going to revisit it). Drop our own bid before
                # picking a winner so we can never award a task to
                # ourselves while we're busy with something else; if we
                # were the only bidder the task simply stays PENDING and
                # gets re-gossiped the next time any robot goes idle.
                if self.current_task is not None:
                    bids.pop(self.robot_id, None)

                # Winner is the one with the lowest cost. Tie-break by robot_id string sorting.
                if bids:
                    winner_id = min(bids.keys(), key=lambda rid: (bids[rid], rid))
                    
                    if winner_id == self.robot_id:
                        # I won the auction!
                        task = self.task_pool.get_task(task_id)
                        if task and task.status == TaskStatus.PENDING:
                            # Update the global pool to prevent others from starting new auctions
                            self.task_pool.assign_task(task_id, self.robot_id, tick)
                            
                            self.current_task = task
                            self.task_phase = "TO_PICKUP"
                            self.destination = task.pickup
                            self.priority = task.priority
                            self.planned_path.clear()
                            
                            self._log_event(tick, "TASK", f"Won auction for {task_id} with bid {bids[self.robot_id]:.1f}")
                            
                            # Broadcast award so peers can delete their auctions
                            self._broadcast_task_award(task_id, tick)
                
                # Cleanup local tracking
                self.active_auctions.pop(task_id, None)
                self.auction_start_ticks.pop(task_id, None)

    def _broadcast_task_award(self, task_id: str, tick: int):
        self.message_bus.send(Message(
            type=MessageType.TASK_AWARD,
            sender_id=self.robot_id,
            target_id=None, # Broadcast to everyone
            timestamp=tick,
            data={"task_id": task_id, "winner_id": self.robot_id}
        ))

    def _find_available_staging_area(self) -> Optional[Position]:
        """Find the nearest available staging cell that is not occupied or targeted by a peer."""
        if not self.warehouse.staging_areas:
            return None
            
        claimed = set()
        for pid, state in self.peer_knowledge.items():
            if state.position:
                claimed.add(state.position)
            # Only consider a peer's destination if they are actively moving there or waiting
            if state.destination and state.status in (RobotStatus.MOVING, RobotStatus.WAITING, RobotStatus.REROUTING):
                claimed.add(state.destination)
                
        available = [p for p in self.warehouse.staging_areas if p not in claimed]
        if not available:
            # If all claimed, fallback to any staging area that isn't physically parked in
            parked = {state.position for state in self.peer_knowledge.values() if state.status == RobotStatus.IDLE and state.position}
            available = [p for p in self.warehouse.staging_areas if p not in parked]
            if not available:
                return None
            
        available.sort(key=lambda p: self.position.manhattan_distance(p))
        return available[0]

    def _try_acquire_task(self, tick: int):
        """Task Gossip: Idle robots check the 'environment' for tasks."""
        if self.battery < BATTERY_CRITICAL or self.status == RobotStatus.UNAVAILABLE:
            return
            
        # Find a PENDING task that isn't currently being auctioned
        for task_id, task in self.task_pool.tasks.items():
            if task.status == TaskStatus.PENDING and task_id not in self.active_auctions:
                # Discovered a task! Broadcast it.
                self._broadcast_task_offer(task_id, task, tick)
                # Note: We don't bid immediately, we wait for our own broadcast to hit _on_task_offer
                break

    def _broadcast_task_offer(self, task_id: str, task: Task, tick: int):
        msg = Message(
            type=MessageType.TASK_OFFER,
            sender_id=self.robot_id,
            timestamp=tick,
            data={
                "task_id": task_id,
                "pickup": {"x": task.pickup.x, "y": task.pickup.y},
                "dropoff": {"x": task.dropoff.x, "y": task.dropoff.y},
                "priority": task.priority,
            }
        )
        self.message_bus.send(msg)
        self._log_event(tick, "TASK", f"Discovered and gossiped task {task_id}")
        
        # Manually process our own offer since message_bus broadcast excludes sender
        self._on_task_offer(msg, tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  TASK EXECUTION STATE MACHINE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _execute_task(self, tick: int):
        if self.task_phase == "TO_PICKUP":
            self.destination = self.current_task.pickup
            if self.position == self.destination:
                # Arrived at pickup
                self.task_phase = "PICKING"
                self.status = RobotStatus.PICKING
                self.action_timer = PICK_DROP_TICKS
                self.task_pool.start_picking(self.current_task.task_id)
                self.velocity = 0.0
                self._log_event(tick, "TASK", f"Picking up {self.current_task.task_id}")
            else:
                self._plan_and_move(tick)

        elif self.task_phase == "TO_DROPOFF":
            self.destination = self.current_task.dropoff
            if self.position == self.destination:
                # Arrived at dropoff
                self.task_phase = "DROPPING"
                self.status = RobotStatus.DROPPING
                self.action_timer = PICK_DROP_TICKS
                self.velocity = 0.0
                self._log_event(tick, "TASK", f"Dropping off {self.current_task.task_id}")
            else:
                self._plan_and_move(tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ACTION TIMER (PICK / DROP)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _continue_action(self, tick: int):
        self.action_timer -= 1
        if self.action_timer <= 0:
            if self.status == RobotStatus.PICKING:
                self.has_item = True
                self.task_phase = "TO_DROPOFF"
                self.destination = self.current_task.dropoff
                self.task_pool.start_delivering(self.current_task.task_id)
                self.status = RobotStatus.IDLE
                self.planned_path.clear()
                self._log_event(tick, "TASK", f"Picked up {self.current_task.task_id}, heading to dropoff")
            elif self.status == RobotStatus.DROPPING:
                self.has_item = False
                self.task_pool.complete_task(self.current_task.task_id, tick)
                self._log_event(tick, "TASK", f"Completed {self.current_task.task_id}")
                self.current_task = None
                self.task_phase = "NONE"
                self.destination = None
                self.status = RobotStatus.IDLE
                self.priority = 0
                self.planned_path.clear()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  PLAN & MOVE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _plan_and_move(self, tick: int):
        # Plan a path if we don't have one (or it's been invalidated)
        if not self.planned_path:
            self._plan_path(tick)

        if not self.planned_path:
            self.status = RobotStatus.BLOCKED
            self.decision_reason = f"No path to {self.destination}"
            self.velocity = 0.0
            self.blocked_time += 1
            # Every DEADLOCK_WAIT_THRESHOLD ticks of being fully blocked
            # (astar_3d found no route at all, e.g. boxed in by other
            # stuck robots' reservations), explicitly drop our own
            # reservations and log it so this is visible instead of the
            # robot silently retrying forever with no diagnostic trail.
            if self.blocked_time % DEADLOCK_WAIT_THRESHOLD == 0:
                self._log_event(
                    tick, "DEADLOCK",
                    f"{self.robot_id} blocked with no viable path for "
                    f"{self.blocked_time} ticks — releasing reservations and retrying",
                )
                if not self.baseline_mode:
                    self.space_time_grid.clear_robot_reservations(self.robot_id)
            return

        self.blocked_time = 0
        # Next cell to move to
        next_cell = self.planned_path[0]

        if self.baseline_mode:
            # Baseline: Stop-and-wait if occupied.
            # FIX #1: route through the (previously dead) conflict_resolver
            # negotiation path instead of hand-rolling WAITING state here.
            # This restores waiting_for tracking, total_waiting_time
            # bookkeeping, and — critically — periodic deadlock checks.
            occupant = self._occupied_cells.get(next_cell)
            if occupant and occupant != self.robot_id:
                peer = self.peer_knowledge.get(occupant)
                conflict = LocalConflict(
                    other_robot_id=occupant,
                    cell=next_cell,
                    conflict_type="INTERSECTION",
                    my_distance=1,
                    peer_distance=0,
                    peer_priority=peer.priority if peer else 0,
                )
                self._handle_conflicts([conflict], tick, self._occupied_cells)
            else:
                self.waiting_time = 0
                self.waiting_for = None
                self._start_move(next_cell, tick)
        else:
            # Distributed MAPF mode: Space-Time A* guarantees no robot-robot collisions.
            # We just need to check for unexpected dynamic obstacles.
            if next_cell in self.warehouse.dynamic_obstacles:
                self.planned_path.clear()
                self._log_event(tick, "OBSTACLE", "Dynamic obstacle detected, replanning.")
                self.status = RobotStatus.BLOCKED
                self.velocity = 0.0
                return

            # Since Space-Time A* might return current position as the next step (i.e. 'wait' action)
            if next_cell == self.position:
                self.status = RobotStatus.WAITING
                self.waiting_time += 1
                self.total_waiting_time += 1
                self.velocity = 0.0
                self.decision_reason = "MAPF dictated wait"
                self.planned_path.pop(0)  # consume the wait action
                # FIX #2: previously this counter was tracked but never
                # acted on in distributed mode, so a robot could sit in a
                # "MAPF dictated wait" indefinitely if its reservation set
                # became stale. Force a hard replan once it's been stuck
                # too long instead of trusting the old reservations.
                if self.waiting_time >= DEADLOCK_WAIT_THRESHOLD:
                    self._log_event(
                        tick, "DEADLOCK",
                        f"{self.robot_id} stuck on MAPF wait for {self.waiting_time} ticks — forcing replan",
                    )
                    self.planned_path.clear()
                    self.space_time_grid.clear_robot_reservations(self.robot_id)
                    self.waiting_time = 0
                return

            self.waiting_time = 0
            self._start_move(next_cell, tick)

    def _plan_path(self, tick: int):
        """Compute a path from current position to destination."""
        if self.destination is None:
            return

        if self.baseline_mode:
            path = astar(
                self.position,
                self.destination,
                self.warehouse.get_walkable_neighbors,
            )
            if path and len(path) > 1:
                self.planned_path = path[1:]  # exclude current position
                self.intent = f"PATH_TO_{self.destination.to_tuple()}"
                self._broadcast_intent(tick)
            else:
                self.planned_path = []
        else:
            # Distributed MAPF
            self.space_time_grid.clear_robot_reservations(self.robot_id)
            path = astar_3d(
                start=self.position,
                goal=self.destination,
                start_tick=tick,
                get_neighbors=self.warehouse.get_walkable_neighbors,
                grid=self.space_time_grid,
                robot_id=self.robot_id,
            )
            if path and len(path) > 1:
                self.planned_path = path[1:]
                # the path from astar_3d includes current_pos at tick
                self.space_time_grid.reserve_path(self.robot_id, tick, path)
                self.intent = f"PATH_TO_{self.destination.to_tuple()}"
                self._broadcast_intent(tick)
                self._broadcast_path_intent(tick)
            else:
                self.planned_path = []

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  CONFLICT HANDLING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _handle_conflicts(self, conflicts: List[LocalConflict], tick: int, occupied_cells: Dict[Position, str]):
        # Take the most immediate conflict
        conflict = min(conflicts, key=lambda c: c.my_distance)
        other_id = conflict.other_robot_id

        if self.baseline_mode:
            # ── STOP-AND-WAIT baseline ───────────────────
            self.status = RobotStatus.WAITING
            self.waiting_for = other_id
            self.waiting_time += 1
            self.total_waiting_time += 1
            self.velocity = 0.0
            self.decision_reason = f"[BASELINE] Waiting: {conflict.cell.to_tuple()} occupied by {other_id}"

            # Broadcast wait-for
            self._broadcast_wait_for(other_id, tick)

            # Check for prolonged waiting
            if self.waiting_time >= DEADLOCK_WAIT_THRESHOLD:
                self._check_deadlock(tick)
            return

        # ── DISTRIBUTED conflict resolution ──────────────
        peer_wt = 0
        peer_batt = 100.0
        if other_id in self.peer_knowledge:
            pk = self.peer_knowledge[other_id]
            peer_wt = 0  # we don't know their exact waiting time locally
            peer_batt = pk.battery

        priority_cmp = compare_priority(
            self.priority,
            conflict.my_distance,
            self.waiting_time,
            self.robot_id,
            self.battery,
            conflict.peer_priority,
            conflict.peer_distance,
            peer_wt,
            other_id,
            peer_batt,
        )

        if priority_cmp > 0:
            # I have higher priority → proceed
            next_cell = self.planned_path[0] if self.planned_path else None
            
            # PHYSICAL OCCUPANCY CHECK: Even if we have priority, we cannot step into an occupied cell
            occupant = occupied_cells.get(next_cell) if next_cell else None
            if occupant and occupant != self.robot_id:
                self.status = RobotStatus.WAITING
                self.waiting_for = occupant  # wait for them to move
                self.waiting_time += 1
                self.total_waiting_time += 1
                self.velocity = 0.0
                self.decision_reason = f"Priority win but {next_cell.to_tuple()} physically occupied by {occupant}"
                self._broadcast_wait_for(occupant, tick)
                
                # CRITICAL: Clear our path so we stop pretending we are moving forward in the Space-Time Grid.
                # This ensures we drop our future reservations and place a solid terminal reservation
                # on our current cell on the next tick, forcing the trapped robot to detour around us!
                self.planned_path.clear()
            else:
                self.status = RobotStatus.MOVING
                self.decision_reason = f"Priority over {other_id} at {conflict.cell.to_tuple()}"
                self._log_event(tick, "NEGOTIATION",
                    f"Priority win over {other_id} at {conflict.cell.to_tuple()}")
                self.waiting_for = None
                self.waiting_time = 0

                if next_cell:
                    self._start_move(next_cell, tick)

            # Send priority claim to force the other robot to yield
            self.message_bus.send(Message(
                type=MessageType.PRIORITY_CLAIM,
                sender_id=self.robot_id,
                timestamp=tick,
                data={
                    "cell": conflict.cell.to_tuple(),
                    "priority": self.priority,
                },
            ))

        else:
            # I should yield
            self.status = RobotStatus.WAITING
            self.waiting_for = other_id
            self.waiting_time += 1
            self.total_waiting_time += 1
            self.velocity = 0.0

            self._broadcast_wait_for(other_id, tick)

            # Instantly attempt to reroute! If it fails to find an alternate path, it will fall back to WAITING.
            self._initiate_reroute(tick, f"Yielding to {other_id} at {conflict.cell.to_tuple()}")

            # FIX #2: distributed mode previously never checked for deadlock
            # cycles at all. If repeated reroute attempts keep failing,
            # waiting_time now keeps accumulating (see FIX #2 in
            # _initiate_reroute) so this can actually fire.
            if self.waiting_time >= DEADLOCK_WAIT_THRESHOLD:
                self._check_deadlock(tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  REROUTING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _initiate_reroute(self, tick: int, reason: str, extra_avoid: Optional[Set[Position]] = None):
        if self.destination is None:
            return

        self.status = RobotStatus.REROUTING

        # Cells to avoid: conflict zone + peer positions
        avoid: Set[Position] = set()
        if extra_avoid:
            avoid.update(extra_avoid)
            
        if self.waiting_for and self.waiting_for in self.peer_knowledge:
            pk = self.peer_knowledge[self.waiting_for]
            if self.baseline_mode and pk.position:
                avoid.add(pk.position)
                for p in pk.planned_path:
                    avoid.add(p)

        if self.baseline_mode:
            alt_path = find_alternative_path(
                self.position,
                self.destination,
                self.warehouse.get_walkable_neighbors,
                avoid,
            )
        else:
            self.space_time_grid.clear_robot_reservations(self.robot_id)
            alt_path = astar_3d(
                start=self.position,
                goal=self.destination,
                start_tick=tick,
                get_neighbors=self.warehouse.get_walkable_neighbors,
                grid=self.space_time_grid,
                robot_id=self.robot_id,
                is_blocked=lambda p: p in avoid
            )

        if alt_path and len(alt_path) > 1:
            self.planned_path = alt_path[1:]
            
            if not self.baseline_mode:
                # reservations were cleared above before astar_3d
                self.space_time_grid.reserve_path(self.robot_id, tick, [self.position] + self.planned_path)
                self._broadcast_intent(tick)
                self._broadcast_path_intent(tick)
                
            # Send yield notification to whoever we were waiting for
            if self.waiting_for:
                self.message_bus.send(Message(
                    type=MessageType.YIELD_NOTIFICATION,
                    sender_id=self.robot_id,
                    timestamp=tick,
                    target_id=self.waiting_for,
                    data={"reason": "rerouted"},
                ))
            
            self.waiting_for = None
            self.waiting_time = 0
            self.decision_reason = f"Rerouted: {reason}"
            self._log_event(tick, "REROUTE", f"Rerouted: {reason}")
            
            self.status = RobotStatus.IDLE  # ready to move on next tick
            self._broadcast_state(tick)
        else:
            # No alternative found this attempt.
            # FIX #2: this used to reset waiting_time to 0 "to prevent
            # deadlock spam", which had the side effect of making
            # DEADLOCK_WAIT_THRESHOLD unreachable for any robot stuck in a
            # repeated yield→reroute-fails→yield loop — the single biggest
            # contributor to the distributed-mode livelock. We now leave
            # waiting_time (and waiting_for) intact so the deadlock cycle
            # detector can eventually take over and force a real resolution
            # instead of retrying forever with no escalation.
            self.status = RobotStatus.BLOCKED
            self.decision_reason = f"No alternative route: {reason}"
            self._log_event(tick, "REROUTE", f"No alt route available: {reason}")
            self.planned_path.clear()  # CRITICAL: clear so it replans next tick with space-time A*
            
            if not self.baseline_mode:
                # Since we cleared reservations to search, but failed to find a path,
                # we are stuck here! We MUST reserve our current position indefinitely.
                self.space_time_grid.reserve_path(self.robot_id, tick, [self.position])
                self._broadcast_path_intent(tick)


    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  DEADLOCK
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _check_deadlock(self, tick: int):
        # Update own entry
        self.deadlock_detector.update(self.robot_id, self.waiting_for)

        cycle = self.deadlock_detector.check_cycle()
        if cycle and self.robot_id in cycle:
            self._log_event(tick, "DEADLOCK", f"Deadlock cycle detected: {cycle}")

            # Determine who yields: lowest priority in cycle
            priorities = {}
            for rid in cycle:
                if rid == self.robot_id:
                    priorities[rid] = self.priority
                elif rid in self.peer_knowledge:
                    priorities[rid] = self.peer_knowledge[rid].priority
                else:
                    priorities[rid] = 0

            from deadlock_detector import select_yielding_robot
            yielder = select_yielding_robot(cycle, priorities)

            # Broadcast deadlock detection
            self.message_bus.send(Message(
                type=MessageType.DEADLOCK_DETECTED,
                sender_id=self.robot_id,
                timestamp=tick,
                data={
                    "cycle": cycle,
                    "yield_robot": yielder,
                },
            ))

            if yielder == self.robot_id:
                self._initiate_reroute(tick, "Deadlock recovery — I yield")
                self.status = RobotStatus.RECOVERY

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  MOVEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _start_move(self, target: Position, tick: int):
        """Begin moving to an adjacent cell."""
        # ── Physical safety check ────────────────────────────────────────
        # Even if our Space-Time planner granted us this slot, a same-tick
        # race can leave another robot at target.  Bail out rather than overlap.
        occupant = self._occupied_cells.get(target)
        if occupant and occupant != self.robot_id:
            self.status = RobotStatus.WAITING
            self.waiting_for = occupant
            self.waiting_time += 1
            self.total_waiting_time += 1
            self.velocity = 0.0
            self.decision_reason = f"Target {target.to_tuple()} blocked by {occupant} (safety check)"
            # Invalidate the cached path so we replan next tick
            self.planned_path.clear()

            # This is the only place distributed-mode robots wait once the
            # predictive-avoidance override is disabled (see
            # _run_collision_prediction), so it must feed the wait-for graph
            # and deadlock check itself — otherwise a genuine A<->B<->A cycle
            # forming here would never be detected or broken.
            self._broadcast_wait_for(occupant, tick)
            if self.waiting_time >= DEADLOCK_WAIT_THRESHOLD:
                self._check_deadlock(tick)
            return
        # ─────────────────────────────────────────────────────────────────

        self.prev_position = self.position
        self.target_cell = target
        self.heading = self.position.direction_to(target)
        self.position = target         # claim cell immediately
        self.moving = True
        self.move_progress = 0
        self.velocity = 1.0
        self.status = RobotStatus.MOVING
        self.distance_travelled += 1.0
        self.decision_reason = f"Moving to {target.to_tuple()}"

        # Remove the cell from planned path
        if self.planned_path and self.planned_path[0] == target:
            self.planned_path.pop(0)
            
        # Broadcast state so peers know we are moving and no longer waiting
        self._broadcast_state(tick)

    def _continue_movement(self, tick: int):
        """Advance in-transit movement by one tick."""
        self.move_progress += 1

        # Interpolate render position
        if self.target_cell and self.prev_position:
            progress = self.move_progress / TICKS_PER_MOVE
            self.render_x = self.prev_position.x + progress * (self.target_cell.x - self.prev_position.x)
            self.render_y = self.prev_position.y + progress * (self.target_cell.y - self.prev_position.y)

        if self.move_progress >= TICKS_PER_MOVE:
            # Movement complete
            self.moving = False
            self.move_progress = 0
            self.render_x = float(self.position.x)
            self.render_y = float(self.position.y)
            self.target_cell = None
            self.velocity = 0.0

            # Broadcast updated state
            self._broadcast_state(tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  BROADCASTING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _broadcast_state(self, tick: int):
        self.messages_sent += 1
        self.message_bus.send(Message(
            type=MessageType.STATE_UPDATE,
            sender_id=self.robot_id,
            timestamp=tick,
            data={
                "position": self.position.to_tuple(),
                "velocity": self.velocity,
                "heading": self.heading,
                "status": self.status.value,
                "intent": self.intent,
                "planned_path": [p.to_tuple() for p in self.planned_path[:5]],
                "current_task": self.current_task.task_id if self.current_task else None,
                "priority": self.priority,
                "waiting_for": self.waiting_for,
                "destination": self.destination.to_tuple() if self.destination else None,
                "battery": self.battery,
            },
        ))

    def _broadcast_intent(self, tick: int):
        self.messages_sent += 1
        self.message_bus.send(Message(
            type=MessageType.INTENT_BROADCAST,
            sender_id=self.robot_id,
            timestamp=tick,
            data={
                "position": self.position.to_tuple(),
                "planned_path": [p.to_tuple() for p in self.planned_path[:8]],
                "destination": self.destination.to_tuple() if self.destination else None,
                "priority": self.priority,
                "intent": self.intent,
                "status": self.status.value,
            },
        ))

    def _broadcast_path_intent(self, tick: int):
        """Broadcast the full planned path so peers can update their local Space-Time Grids."""
        self.messages_sent += 1
        
        full_path = [self.position] + self.planned_path if self.planned_path else [self.position]
        
        self.message_bus.send(Message(
            type=MessageType.PATH_INTENT,
            sender_id=self.robot_id,
            timestamp=tick,
            data={
                "path": [p.to_tuple() for p in full_path],
            },
        ))

    def _broadcast_wait_for(self, other_id: str, tick: int):
        self.message_bus.send(Message(
            type=MessageType.WAIT_FOR,
            sender_id=self.robot_id,
            timestamp=tick,
            data={"waiting_for": other_id},
        ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  FAILURE / RECOVERY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def make_unavailable(self, tick: int):
        """Simulate robot failure."""
        self.status = RobotStatus.UNAVAILABLE
        self.velocity = 0.0
        self.moving = False
        self.planned_path.clear()

        # Unassign tasks
        if self.current_task:
            self.task_pool.fail_task(self.current_task.task_id)
            self._log_event(tick, "SYSTEM", f"Robot unavailable — {self.current_task.task_id} unassigned")
            self.current_task = None
            self.task_phase = "NONE"

        self.waiting_for = None
        self.destination = None

    def make_available(self, tick: int):
        """Recover from failure."""
        self.status = RobotStatus.IDLE
        self.battery = max(50.0, self.battery)
        self._log_event(tick, "SYSTEM", f"Robot recovered")
        self._send_heartbeat(tick)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  LOGGING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _log_event(self, tick: int, event_type: str, description: str):
        self.events.append(SimulationEvent(
            tick=tick,
            event_type=event_type,
            robot_id=self.robot_id,
            description=description,
        ))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  SERIALISATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def to_dict(self) -> dict:
        # Summarise worst active prediction for frontend telemetry
        worst_risk = "SAFE"
        worst_peer = None
        worst_ttc = None
        if self.active_collision_predictions:
            # Sort by risk severity (CRITICAL first)
            _order = {CollisionRisk.CRITICAL: 0, CollisionRisk.WARNING: 1,
                      CollisionRisk.LOW_RISK: 2, CollisionRisk.SAFE: 3}
            worst = min(self.active_collision_predictions,
                        key=lambda p: _order[p.risk_level])
            worst_risk = worst.risk_level.value
            worst_peer = worst.other_robot_id
            worst_ttc  = round(worst.time_to_collision, 2) if worst.time_to_collision else None

        return {
            "robot_id": self.robot_id,
            "position": self.position.to_tuple(),
            "prev_position": self.prev_position.to_tuple(),
            "render_x": round(self.render_x, 2),
            "render_y": round(self.render_y, 2),
            "velocity": self.velocity,
            "heading": round(self.heading, 1),
            "battery": round(self.battery, 1),
            "current_task": self.current_task.task_id if self.current_task else None,
            "task_phase": self.task_phase,
            "destination": self.destination.to_tuple() if self.destination else None,
            "planned_path": [p.to_tuple() for p in self.planned_path],
            "status": self.status.value,
            "priority": self.priority,
            "intent": self.intent,
            "waiting_for": self.waiting_for,
            "waiting_time": self.waiting_time,
            "total_waiting_time": self.total_waiting_time,
            "distance_travelled": round(self.distance_travelled, 1),
            "color": self.color,
            "decision_reason": self.decision_reason,
            "moving": self.moving,
            "move_progress": self.move_progress,
            "has_item": self.has_item,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "hardware": {
                "cpu": round(self.hardware["cpu"], 1),
                "ram": round(self.hardware["ram"], 1),
                "latency": round(self.hardware["latency"], 1),
                "thermal": round(self.hardware["thermal"], 1),
            },
            # ── Collision prediction telemetry ──────────────────
            "collision_risk": worst_risk,
            "collision_peer": worst_peer,
            "collision_ttc": worst_ttc,
        }

    def reset(self, position: Position):
        """Full reset to initial state."""
        self.position = position
        self.prev_position = position
        self.render_x = float(position.x)
        self.render_y = float(position.y)
        self.velocity = 0.0
        self.heading = 0.0
        self.moving = False
        self.move_progress = 0
        self.target_cell = None
        self.status = RobotStatus.IDLE
        self.battery = 100.0
        self.distance_travelled = 0.0
        self.current_task = None
        self.destination = None
        self.has_item = False
        self.action_timer = 0
        self.task_phase = "NONE"
        self.planned_path.clear()
        self.peer_knowledge.clear()
        self.deadlock_detector.clear()
        self.waiting_for = None
        self.waiting_time = 0
        self.total_waiting_time = 0
        self.blocked_time = 0
        self.decision_reason = ""
        self.intent = ""
        self.priority = 0
        self.last_heartbeat = 0
        self.events.clear()
        self.active_collision_predictions.clear()