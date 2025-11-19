"""FastAPI server exposing transport-fed Leaf state."""

from __future__ import annotations

from threading import Thread
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig
from .state import StateStore
from .transports.base import Transport
from .transports.synthetic import SyntheticTransport


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
            return self.state_store.snapshot()

        @self.app.post("/command/clear_dtcs")
        def clear_dtcs() -> Dict[str, Any]:
            try:
                self.transport.send_command("CLEAR_DTC")
            except NotImplementedError as exc:  # pragma: no cover - transports may override later
                raise HTTPException(status_code=501, detail=str(exc)) from exc
            return {"status": "ok"}

    def _create_transport(self) -> Transport:
        transport_type = self.config.transport.type
        if transport_type == "synthetic":
            return SyntheticTransport(
                update_interval_sec=self.config.transport.update_interval_sec,
                cell_count=self.config.vehicle.cell_count,
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
