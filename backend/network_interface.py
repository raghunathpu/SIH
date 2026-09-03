"""
FleetMind — Network Interface Abstraction

This module defines the abstract base class for robot-to-robot
and robot-to-system communication. This abstraction is required
so that RobotAgent can run on a physical ROS 2 DDS network
without changing its core coordination logic.
"""

from abc import ABC, abstractmethod
from typing import List
from models import Message


class NetworkInterface(ABC):
    """
    Abstract communication layer.
    Can be backed by SimulatedNetwork (MessageBus) or ROS2Network (DDS).
    """

    @abstractmethod
    def register(self, robot_id: str):
        """Register a robot ID on the network to receive messages."""
        pass

    @abstractmethod
    def send(self, message: Message):
        """Broadcast or unicast a message to the network."""
        pass

    @abstractmethod
    def receive(self, robot_id: str) -> List[Message]:
        """Fetch all pending messages for the given robot ID."""
        pass

    @abstractmethod
    def clear_all(self):
        """Clear all messages (mostly for simulation reset)."""
        pass
