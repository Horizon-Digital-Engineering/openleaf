"""FastAPI server exposing transport-fed Leaf state."""

from __future__ import annotations

import logging
from threading import Thread
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig
from .state import StateStore
from .transports.base import Transport
from .transports.ble import BleOBDTransport
from .transports.obd import OBDTransport
from .transports.synthetic import SyntheticTransport
from .logging.setup import get_transport_logger


class LeafStateServer:
    """HTTP API server exposing real-time Leaf state."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_store = StateStore()
        self.transport: Transport = self._create_transport()
        self._thread: Optional[Thread] = None
        self.app = FastAPI(title="OpenLeaf State Server")
        self._configure_cors()
        self._setup_routes()

    def _configure_cors(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        @self.app.get("/health")
        def health() -> Dict[str, Any]:
            return {"status": "ok", "transport": self.config.transport.type}

        @self.app.get("/state")
        def get_state() -> Dict[str, Any]:
            state = self.state_store.snapshot()
            debug_log = getattr(self.transport, "debug_log", None)
            if callable(debug_log):
                try:
                    state["_debug_log"] = debug_log()
                except Exception:
                    state["_debug_log"] = []
            return state

        @self.app.get("/debug/transport_log")
        def transport_log() -> Dict[str, Any]:
            debug_log = getattr(self.transport, "debug_log", None)
            if callable(debug_log):
                try:
                    return {"log": debug_log()}
                except Exception:
                    return {"log": []}
            return {"log": []}

        @self.app.post("/command/clear_dtcs")
        def clear_dtcs() -> Dict[str, Any]:
            try:
                self.transport.send_command("CLEAR_DTC")
            except NotImplementedError as exc:  # pragma: no cover - transports may override later
                raise HTTPException(status_code=501, detail=str(exc)) from exc
            return {"status": "ok"}

    def _create_transport(self) -> Transport:
        transport_type = self.config.transport.type
        transport_logger = None
        if self.config.logging.enabled:
            identifier = "transport"
            if transport_type == "obd":
                identifier = f"obd_{self.config.transport.serial_port}"
            elif transport_type == "ble":
                identifier = f"ble_{self.config.transport.ble_address or self.config.transport.serial_port}"
            transport_logger = get_transport_logger(identifier, self.config.logging)

        if transport_type == "synthetic":
            return SyntheticTransport(
                update_interval_sec=self.config.transport.update_interval_sec,
                cell_count=self.config.vehicle.cell_count,
            )
        if transport_type == "obd":
            return OBDTransport(
                port=self.config.transport.serial_port,
                baudrate=self.config.transport.baudrate,
                timeout_sec=self.config.transport.timeout_sec,
                update_interval_sec=self.config.transport.update_interval_sec,
                pid_path=self.config.transport.pid_path,
                reconnect_delay_sec=self.config.transport.reconnect_delay_sec,
                enable_flow_control=self.config.transport.enable_flow_control,
                connection_logger=transport_logger,
            )
        if transport_type == "ble":
            return BleOBDTransport(
                address=self.config.transport.ble_address or self.config.transport.serial_port,
                service_uuid=self.config.transport.ble_service_uuid,
                write_char_uuid=self.config.transport.ble_write_char_uuid,
                notify_char_uuid=self.config.transport.ble_notify_char_uuid,
                timeout_sec=self.config.transport.timeout_sec,
                update_interval_sec=self.config.transport.update_interval_sec,
                pid_path=self.config.transport.pid_path,
                reconnect_delay_sec=self.config.transport.reconnect_delay_sec,
                enable_flow_control=self.config.transport.enable_flow_control,
                connection_logger=transport_logger,
            )
        raise NotImplementedError(f"Transport '{transport_type}' is not implemented yet")

    def start_background_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        for update in self.transport.loop():
            if isinstance(update, dict):
                self.state_store.update(**update)
