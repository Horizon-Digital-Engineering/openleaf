"""Async HTTP client for interacting with the OpenLeaf backend."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

import httpx

StateCallback = Callable[[Dict[str, Any]], Awaitable[None] | None]


class ApiClient:
    """Simple async client for polling the OpenLeaf API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_state(self) -> Dict[str, Any]:
        response = await self._client.get("/state")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        raise ValueError("State response must be a JSON object")

    async def clear_dtcs(self) -> bool:
        response = await self._client.post("/command/clear_dtcs")
        response.raise_for_status()
        return response.json().get("status") == "ok"

    async def polling_loop(
        self, callback: StateCallback, interval: float = 0.5
    ) -> None:
        """Repeatedly fetch state and invoke callback."""

        try:
            while True:
                try:
                    state = await self.get_state()
                    if callback:
                        result = callback(state)
                        if asyncio.iscoroutine(result):
                            await result
                except httpx.HTTPError:
                    # Swallow errors for now; UI can show stale data
                    pass
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            # Clean cancellation - this is expected on shutdown
            pass
