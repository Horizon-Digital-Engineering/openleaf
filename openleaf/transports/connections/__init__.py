"""Connection implementations for OBD2 adapters."""

from .base import OBDConnection
from .ble import BLEConnection
from .serial import SerialConnection

__all__ = ["OBDConnection", "BLEConnection", "SerialConnection"]