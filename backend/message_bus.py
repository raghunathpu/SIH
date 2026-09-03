"""
FleetMind — Peer-to-Peer Message Bus

In-process message transport that simulates a local-network broadcast channel.
Each robot registers with the bus and receives messages in its own inbox.

In production, this maps to UDP multicast or MQTT on the warehouse LAN.
The interface is identical: send(message) / receive(robot_id) → [Message].
"""

from __future__ import annotations

from typing import Dict, List

from models import Message


class MessageBus:
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

    # ── registration ─────────────────────────────────────

    def register(self, robot_id: str):
        if robot_id not in self._inboxes:
            self._inboxes[robot_id] = []

    def unregister(self, robot_id: str):
        self._inboxes.pop(robot_id, None)

    # ── send / receive ───────────────────────────────────

    def send(self, message: Message):
        """
        Deliver *message*.

        • ``target_id is None`` → broadcast to all registered robots
          except the sender.
        • ``target_id = "AMR-02"`` → unicast to AMR-02 only.

        Invalid messages (failing ``validate()``) are silently dropped.
        """
        if not message.validate():
            return

        self._total_sent += 1
        self._log.append(message)
        if len(self._log) > self._log_limit:
            self._log = self._log[-self._log_limit:]

        if message.target_id:
            # unicast
            inbox = self._inboxes.get(message.target_id)
            if inbox is not None:
                inbox.append(message)
        else:
            # broadcast
            for rid, inbox in self._inboxes.items():
                if rid != message.sender_id:
                    inbox.append(message)

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

    def clear(self):
        """Reset bus state — called on simulation reset."""
        for inbox in self._inboxes.values():
            inbox.clear()
        self._log.clear()
        self._total_sent = 0

    def clear_all(self):
        """Full reset including registrations."""
        self._inboxes.clear()
        self._log.clear()
        self._total_sent = 0
