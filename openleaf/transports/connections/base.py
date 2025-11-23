"""Base class for OBD2 adapter connections."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class OBDConnection(ABC):
    """Abstract base class for OBD2 adapter connections.

    This handles the physical/wireless connection to the ELM327 adapter.
    The actual OBD2/ELM327 protocol handling is done by ELM327Protocol.
    """

    @abstractmethod
    def connect_sync(self) -> None:
        """Establish connection to the adapter."""
        pass

    @abstractmethod
    def disconnect_sync(self) -> None:
        """Close connection to the adapter."""
        pass

    @abstractmethod
    def send_sync(self, command: str) -> None:
        """Send a command to the adapter.

        Args:
            command: ELM327 AT command or OBD2 PID to send
        """
        pass

    @abstractmethod
    def receive_sync(self, timeout: Optional[float] = None) -> str:
        """Receive data from the adapter.

        Args:
            timeout: Maximum time to wait for data (seconds)

        Returns:
            Response string from adapter (lines separated by \n)
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        pass

    def send_and_receive_sync(self, command: str, timeout: Optional[float] = None) -> str:
        """Send command and wait for response.

        Args:
            command: Command to send
            timeout: Maximum time to wait for response

        Returns:
            Response from adapter
        """
        self.send_sync(command)
        return self.receive_sync(timeout)