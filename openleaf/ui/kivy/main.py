"""Kivy touchscreen UI for OpenLeaf telemetry."""

from __future__ import annotations

import asyncio
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.uix.button import Button

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from openleaf.ui.kivy.services.api import ApiClient

KV_FILE = Path(__file__).with_name("ui.kv")


class Dashboard(BoxLayout):
    """Root widget defined in ui.kv."""


class RootLayout(BoxLayout):
    """Top-level container holding navigation and screens."""


class OpenLeafApp(App):
    """Touchscreen UI that polls the OpenLeaf backend."""

    def __init__(self, **kwargs):  # type: ignore[override]
        super().__init__(**kwargs)
        self.api_client = ApiClient()
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._polling_future: asyncio.Future[Any] | None = None
        self._screen_order = ["dashboard", "cells", "dtcs", "debug"]
        self._last_dtcs: list[str] = []
        self._last_debug_log: Optional[list[Dict[str, Any]]] = None

    def build(self) -> BoxLayout:
        Builder.load_file(str(KV_FILE))
        root = RootLayout()
        if not self._loop_thread.is_alive():
            self._loop_thread.start()
        self._polling_future = asyncio.run_coroutine_threadsafe(
            self.api_client.polling_loop(self._handle_state_update, interval=0.5),
            self._loop,
        )
        return root

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _handle_state_update(self, state: Dict[str, Any]) -> None:
        Clock.schedule_once(lambda _: self._apply_state(state))

    def _apply_state(self, state: Dict[str, Any]) -> None:
        if not self.root:
            return
        screen_manager = self.root.ids.screen_manager
        dashboard_screen = screen_manager.get_screen("dashboard")
        dashboard_widget = dashboard_screen.children[0]
        dash_ids = dashboard_widget.ids
        # SOC: prefer soc_precise > soc_display > soc_true
        soc = state.get("soc_precise") or state.get("soc_display") or state.get("soc_true", 0.0)
        dash_ids.soc_gauge.value = soc

        # SOH: prefer soh > soh_alt (both from broadcast)
        soh = state.get("soh") or state.get("soh_alt", 0.0)
        dash_ids.soh_gauge.value = soh

        dash_ids.voltage.value = f"{state.get('pack_voltage', 0.0):.1f}"
        dash_ids.temp.value = f"{state.get('pack_temp_c', 0.0):.1f}"
        dash_ids.delta.value = f"{state.get('cell_delta_mv', 0.0):.1f}"

        # Update additional fields if widgets exist
        if hasattr(dash_ids, 'gids'):
            dash_ids.gids.value = f"{state.get('gids', 0):.0f}"
        if hasattr(dash_ids, 'hx'):
            dash_ids.hx.value = f"{state.get('battery_hx', 0.0):.1f}"
        if hasattr(dash_ids, 'range_val'):
            dash_ids.range_val.value = f"{state.get('range_km', 0.0):.1f}"

        cell_values = state.get("cell_voltages") or []
        cells_screen = screen_manager.get_screen("cells")
        cells_view = cells_screen.children[0]
        cells_ids = cells_view.ids
        cells_ids.cell_graph.values = cell_values
        if cell_values:
            cells_ids.cells_max.value = f"{max(cell_values):.3f}"
            cells_ids.cells_min.value = f"{min(cell_values):.3f}"
            delta_mv = (max(cell_values) - min(cell_values)) * 1000
            cells_ids.cells_delta.value = f"{delta_mv:.1f}"
        else:
            cells_ids.cells_max.value = "--"
            cells_ids.cells_min.value = "--"
            cells_ids.cells_delta.value = "--"

        dtcs = state.get("dtcs") or []
        self._update_dtc_view(screen_manager, dtcs)
        debug_log = state.get("_debug_log") or []
        self._update_debug_view(screen_manager, debug_log)

    def _update_dtc_view(self, screen_manager, ecu_results: dict[str, list[str]]) -> None:
        if ecu_results == self._last_dtcs:
            return
        self._last_dtcs = dict(ecu_results)
        dtc_screen = screen_manager.get_screen("dtcs")
        dtc_view = dtc_screen.children[0]
        dtc_ids = dtc_view.ids
        dtc_container = dtc_ids.dtc_container
        dtc_container.clear_widgets()

        # Always show results - even if all OK
        dtc_ids.dtc_empty.opacity = 0

        for ecu_name, codes in ecu_results.items():
            if not codes:
                # No DTCs - show OK
                label = Button(
                    text=f"{ecu_name}: OK",
                    size_hint_y=None,
                    height=dp(50),
                    font_size="22sp",
                    background_normal="",
                    background_color=(0.15, 0.35, 0.20, 1),  # Green-ish
                    disabled=True,
                )
                dtc_container.add_widget(label)
            elif codes == ["ERROR"]:
                # ECU didn't respond
                label = Button(
                    text=f"{ecu_name}: No Response",
                    size_hint_y=None,
                    height=dp(50),
                    font_size="22sp",
                    background_normal="",
                    background_color=(0.35, 0.25, 0.15, 1),  # Orange-ish
                    disabled=True,
                )
                dtc_container.add_widget(label)
            else:
                # Has DTCs - show each one
                for code in codes:
                    full_code = f"{ecu_name}:{code}"
                    button = Button(
                        text=full_code,
                        size_hint_y=None,
                        height=dp(60),
                        font_size="26sp",
                        background_normal="",
                        background_color=(0.45, 0.18, 0.18, 1),  # Red-ish
                    )
                    button.bind(on_release=lambda _, c=full_code: self.show_dtc_detail(c))
                    dtc_container.add_widget(button)

    def on_stop(self) -> None:
        if self._polling_future:
            self._polling_future.cancel()
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=1)
        asyncio.run(self.api_client.close())

    def show_toast(self, message: str) -> None:
        def _animate(_: float) -> None:
            if not self.root:
                return
            dashboard_widget = self.root.ids.screen_manager.get_screen("dashboard").children[0]
            toast = dashboard_widget.ids.toast
            toast.text = message
            toast.opacity = 1

            def fade_out(_: float) -> None:
                Animation(opacity=0, duration=2).start(toast)

            Clock.schedule_once(fade_out, 1)

        Clock.schedule_once(_animate, 0)

    def on_clear_dtcs(self) -> None:
        async def _clear() -> None:
            success = await self.api_client.clear_dtcs()
            self.show_toast("DTCs cleared" if success else "Failed to clear DTCs")

        asyncio.run_coroutine_threadsafe(_clear(), self._loop)

    def pull_dtcs(self) -> None:
        self.show_toast("Scanning ECUs...")

        async def _read() -> None:
            try:
                ecu_results = await self.api_client.read_dtcs()
                # Count total DTCs (excluding OK and ERROR)
                total_dtcs = sum(
                    len(codes) for codes in ecu_results.values()
                    if codes and codes != ["ERROR"]
                )
                if total_dtcs > 0:
                    self.show_toast(f"Found {total_dtcs} DTC(s)")
                else:
                    self.show_toast(f"Scanned {len(ecu_results)} ECUs - All OK")
                # Update the DTC view
                if self.root:
                    screen_manager = self.root.ids.screen_manager
                    self._update_dtc_view(screen_manager, ecu_results)
            except Exception as e:
                self.show_toast(f"Error: {e}")

        asyncio.run_coroutine_threadsafe(_read(), self._loop)

    def show_dtc_detail(self, code: str) -> None:
        self.show_toast(f"{code}: detail lookup TBD")

    def switch_screen(self, name: str) -> None:
        if not self.root:
            return
        manager = self.root.ids.screen_manager
        if name in self._screen_order:
            manager.current = name

    def _shift_screen(self, delta: int) -> None:
        if not self.root:
            return
        manager = self.root.ids.screen_manager
        current = manager.current or self._screen_order[0]
        try:
            idx = self._screen_order.index(current)
        except ValueError:
            idx = 0
        manager.current = self._screen_order[(idx + delta) % len(self._screen_order)]

    def next_screen(self) -> None:
        self._shift_screen(1)

    def prev_screen(self) -> None:
        self._shift_screen(-1)

    def on_stop(self) -> None:
        """Clean shutdown of async tasks."""
        # Cancel the polling task
        if self._polling_future:
            self._polling_future.cancel()

        # Close the API client
        asyncio.run_coroutine_threadsafe(
            self.api_client.close(),
            self._loop
        ).result(timeout=2.0)

        # Stop the event loop
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _update_debug_view(self, screen_manager, log: list) -> None:
        if self._last_debug_log is not None and log == self._last_debug_log:
            return
        self._last_debug_log = list(log)
        try:
            debug_screen = screen_manager.get_screen("debug")
        except Exception:
            return
        debug_view = debug_screen.children[0]
        debug_ids = debug_view.ids
        container = debug_ids.debug_container
        container.clear_widgets()
        debug_ids.debug_empty.opacity = 1 if not log else 0
        if not log:
            return
        for entry in reversed(log):
            # Handle both string entries and dict entries
            if isinstance(entry, str):
                line = entry
            else:
                ts = entry.get("ts", 0.0)
                direction = str(entry.get("direction", "")).upper()
                data = entry.get("data", "")
                ts_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                line = f"[{ts_str}] {direction}: {data}"
            button = Button(
                text=line,
                size_hint_y=None,
                height=dp(44),
                font_size="18sp",
                background_normal="",
                background_color=(0.12, 0.16, 0.2, 1),
                halign="left",
                valign="middle",
                text_size=(self.root.width - dp(60) if self.root else 0, dp(44)),
            )
            container.add_widget(button)


def main() -> None:
    OpenLeafApp().run()


if __name__ == "__main__":
    main()
