"""FastAPI server exposing transport-fed Leaf state."""

from __future__ import annotations

import logging
from threading import Thread
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig, load_config
from .state import StateStore
from .transports import OBD2Transport, PlaybackTransport, SyntheticTransport, Transport
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

        @self.app.get("/dtcs")
        def get_dtcs() -> Dict[str, Any]:
            read_dtcs = getattr(self.transport, "read_dtcs", None)
            if callable(read_dtcs):
                try:
                    results = read_dtcs()
                    # results is Dict[str, List[str]] - ECU name -> list of DTCs
                    return {"ecus": results}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e)) from e
            raise HTTPException(status_code=501, detail="DTC reading not supported")

        @self.app.post("/command/clear_dtcs")
        def clear_dtcs() -> Dict[str, Any]:
            clear_fn = getattr(self.transport, "clear_dtcs", None)
            if callable(clear_fn):
                try:
                    results = clear_fn()
                    # Check if all succeeded
                    all_ok = all(results.values()) if results else False
                    return {"status": "ok" if all_ok else "partial", "results": results}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e)) from e
            raise HTTPException(status_code=501, detail="DTC clearing not supported")

    def _create_transport(self) -> Transport:
        transport_type = self.config.transport.type
        transport_logger = None

        # Setup logger if enabled
        if self.config.logging.enabled:
            identifier = f"{transport_type}_transport"
            if transport_type == "obd2":
                conn_type = getattr(self.config.transport, "connection_type", "ble")
                if conn_type == "ble":
                    identifier = f"obd2_ble_{getattr(self.config.transport, 'ble_address', 'unknown')}"
                else:
                    identifier = f"obd2_serial_{getattr(self.config.transport, 'serial_port', 'unknown')}"
            transport_logger = get_transport_logger(identifier, self.config.logging)

        # Create transport based on type
        if transport_type == "synthetic":
            return SyntheticTransport(
                update_interval_sec=self.config.transport.update_interval_sec,
                cell_count=self.config.vehicle.cell_count,
            )

        elif transport_type == "obd2":
            # Unified OBD2 transport with pluggable connections
            connection_type = getattr(self.config.transport, "connection_type", "ble")

            return OBD2Transport(
                connection_type=connection_type,
                # BLE settings
                ble_address=getattr(self.config.transport, "ble_address", None),
                ble_service_uuid=getattr(self.config.transport, "ble_service_uuid",
                                         "0000ffe0-0000-1000-8000-00805f9b34fb"),
                ble_write_char_uuid=getattr(self.config.transport, "ble_write_char_uuid",
                                           "0000ffe1-0000-1000-8000-00805f9b34fb"),
                ble_notify_char_uuid=getattr(self.config.transport, "ble_notify_char_uuid",
                                            "0000ffe1-0000-1000-8000-00805f9b34fb"),
                # Serial settings
                serial_port=getattr(self.config.transport, "serial_port", None),
                serial_baudrate=getattr(self.config.transport, "serial_baudrate", 115200),
                # Common settings
                timeout_sec=self.config.transport.timeout_sec,
                update_interval_sec=self.config.transport.update_interval_sec,
                pid_path=self.config.transport.pid_path,
                reconnect_delay_sec=self.config.transport.reconnect_delay_sec,
                enable_flow_control=getattr(self.config.transport, "enable_flow_control", False),
                # Recording
                record_enabled=getattr(self.config.transport, "record_enabled", False),
                record_path=getattr(self.config.transport, "record_path", None),
                # Logging
                connection_logger=transport_logger,
            )

        elif transport_type == "playback":
            return PlaybackTransport(
                file_path=self.config.transport.playback_file,
                format=getattr(self.config.transport, "playback_format", "auto"),
                loop_playback=getattr(self.config.transport, "loop_playback", True),
                playback_speed=getattr(self.config.transport, "playback_speed", 1.0),
                update_interval_sec=self.config.transport.update_interval_sec,
            )

        else:
            raise NotImplementedError(f"Transport '{transport_type}' is not implemented")

    def start_background_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        for update in self.transport.loop():
            if isinstance(update, dict):
                self.state_store.update(**update)


def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="OpenLeaf State Server")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    config = load_config(args.config)
    server = LeafStateServer(config)
    server.start_background_loop()
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
