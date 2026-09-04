"""
FleetMind — Peer-to-Peer Message Bus

In-process message transport that simulates a local-network broadcast channel.
Each robot registers with the bus and receives messages in its own inbox.

In production, this maps to UDP multicast or MQTT on the warehouse LAN.
The interface is identical: send(message) / receive(robot_id) → [Message].
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from models import Message
from network_interface import NetworkInterface


class SimulatedNetwork(NetworkInterface):
    """
    Simulation-local message transport.

    • ``register(robot_id)`` — create an inbox for a robot.
    • ``send(message)``     — deliver to target or broadcast.
    • ``receive(robot_id)`` — drain the robot's inbox.

    Messages sent during tick *t* are available to be received
    immediately (simulating low-latency local networking).
    """

    def __init__(self):
        self._inboxes: Dict[str, List[Message]] = {}
        self._total_sent: int = 0
        self._log: List[Message] = []
        self._log_limit: int = 500  # rolling window
        # Communication graph: (sender, receiver) -> {msg_type: count}
        self._comm_graph: Dict[tuple, Dict[str, int]] = {}
        self._recent_edges: List[Dict] = []  # for frontend animation
        self._recent_edge_limit: int = 200
        
        # Simulated Network Physics
        self._inflight: List[tuple[int, str, Message]] = [] # (delivery_tick, target_id, message)
        self.base_latency_ticks = 1
        self.packet_drop_prob = 0.05
        self.max_range = 15.0 # Max cells for communication

        # Wi-Fi Dead Zones — rectangular regions where comms are blocked
        self.dead_zones: List[Tuple[int, int, int, int]] = []  # (x1, y1, x2, y2)

        # Reference to robots dict — set each tick by engine.step()
        self._robots_ref: dict = {}

    # ── registration ─────────────────────────────────────

    def register(self, robot_id: str):
        if robot_id not in self._inboxes:
            self._inboxes[robot_id] = []

    def unregister(self, robot_id: str):
        self._inboxes.pop(robot_id, None)

    # ── dead zone helpers ─────────────────────────────────

    def is_in_dead_zone(self, position) -> bool:
        """Check if a Position falls inside any dead zone rectangle."""
        px, py = position.x, position.y
        for x1, y1, x2, y2 in self.dead_zones:
            if min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
                return True
        return False

    def add_dead_zone(self, x1: int, y1: int, x2: int, y2: int):
        """Register a rectangular Wi-Fi dead zone."""
        zone = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if zone not in self.dead_zones:
            self.dead_zones.append(zone)

    def remove_dead_zone(self, x1: int, y1: int, x2: int, y2: int):
        """Remove a rectangular Wi-Fi dead zone."""
        zone = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if zone in self.dead_zones:
            self.dead_zones.remove(zone)

    def clear_dead_zones(self):
        self.dead_zones.clear()

    # ── send / receive ───────────────────────────────────

    def send(self, message: Message, robots_dict: dict = None):
        """
        Queue *message* for delivery. Simulates network unreliability.
        Blocks transmission if the sender is inside a Wi-Fi dead zone.
        """
        if not message.validate():
            return

        # Dead zone check — sender cannot transmit
        rdict = robots_dict or self._robots_ref
        if rdict and message.sender_id in rdict:
            sender_pos = rdict[message.sender_id].position
            if self.is_in_dead_zone(sender_pos):
                return  # silently drop — robot has no Wi-Fi

        import random
        # Simulate global packet drop (e.g. interference)
        if random.random() < self.packet_drop_prob:
            return

        self._total_sent += 1
        self._log.append(message)
        if len(self._log) > self._log_limit:
            self._log = self._log[-self._log_limit:]

        # Randomize latency slightly
        latency = self.base_latency_ticks + random.randint(0, 1)
        delivery_tick = message.timestamp + latency

        if message.target_id:
            # unicast
            if message.target_id in self._inboxes:
                self._inflight.append((delivery_tick, message.target_id, message))
            self._track_edge(message.sender_id, message.target_id, message.type.value, message.timestamp)
        else:
            # broadcast
            for rid in self._inboxes.keys():
                if rid != message.sender_id:
                    self._inflight.append((delivery_tick, rid, message))
                    self._track_edge(message.sender_id, rid, message.type.value, message.timestamp)

    def step(self, current_tick: int, robots_dict: dict = None):
        """
        Process the inflight queue and deliver messages whose time has come.
        Applies distance-based range limits and dead zone blocking.
        """
        # Store robots reference so send() can use it for dead zone checks
        if robots_dict:
            self._robots_ref = robots_dict

        pending = []
        for delivery_tick, target_id, msg in self._inflight:
            if current_tick >= delivery_tick:
                # Range check if positions are known
                drop = False
                if robots_dict and msg.sender_id in robots_dict and target_id in robots_dict:
                    sender_pos = robots_dict[msg.sender_id].position
                    target_pos = robots_dict[target_id].position
                    dist = sender_pos.manhattan_distance(target_pos)
                    if dist > self.max_range:
                        drop = True

                # Dead zone check — receiver cannot receive
                if not drop and robots_dict and target_id in robots_dict:
                    target_pos = robots_dict[target_id].position
                    if self.is_in_dead_zone(target_pos):
                        drop = True

                if not drop and target_id in self._inboxes:
                    self._inboxes[target_id].append(msg)
            else:
                pending.append((delivery_tick, target_id, msg))
        self._inflight = pending

    def receive(self, robot_id: str) -> List[Message]:
        """Drain and return all pending messages for *robot_id*."""
        inbox = self._inboxes.get(robot_id)
        if inbox is None:
            return []
        msgs = list(inbox)
        inbox.clear()
        return msgs

    # ── introspection ────────────────────────────────────

    @property
    def total_sent(self) -> int:
        return self._total_sent

    def get_recent_log(self, n: int = 50) -> List[Dict]:
        """Return the last *n* messages as dicts (for the event feed)."""
        return [m.to_dict() for m in self._log[-n:]]

    def _track_edge(self, sender: str, receiver: str, msg_type: str, tick: int):
        """Track a directed communication edge for the network topology view."""
        key = (sender, receiver)
        if key not in self._comm_graph:
            self._comm_graph[key] = {}
        self._comm_graph[key][msg_type] = self._comm_graph[key].get(msg_type, 0) + 1

        # Store recent edge for animation (with tick for TTL)
        self._recent_edges.append({
            "from": sender,
            "to": receiver,
            "type": msg_type,
            "tick": tick,
        })
        if len(self._recent_edges) > self._recent_edge_limit:
            self._recent_edges = self._recent_edges[-self._recent_edge_limit:]

    def get_comm_graph(self, recent_ticks: int = 30, current_tick: int = 0) -> List[Dict]:
        """
        Return recent communication edges for the network topology view.
        Each edge: {from, to, type, count, tick}
        """
        cutoff = current_tick - recent_ticks
        edges = [e for e in self._recent_edges if e["tick"] >= cutoff]
        return edges

    def get_comm_summary(self) -> Dict:
        """Return total message counts between robot pairs."""
        result = []
        for (sender, receiver), types in self._comm_graph.items():
            result.append({
                "from": sender,
                "to": receiver,
                "total": sum(types.values()),
                "by_type": dict(types),
            })
        return result

    def clear(self):
        """Reset bus state — called on simulation reset."""
        for inbox in self._inboxes.values():
            inbox.clear()
        self._log.clear()
        self._inflight.clear()
        self._total_sent = 0
        self._comm_graph.clear()
        self._recent_edges.clear()
        self.dead_zones.clear()

    def clear_all(self):
        """Full reset including registrations."""
        self._inboxes.clear()
        self._log.clear()
        self._inflight.clear()
        self._total_sent = 0
        self._comm_graph.clear()
        self._recent_edges.clear()
        self.dead_zones.clear()
