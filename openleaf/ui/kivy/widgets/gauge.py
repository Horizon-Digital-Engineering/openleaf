"""Circular gauge widget for SOC/SOH displays."""

from __future__ import annotations

from kivy.graphics import Color, Line
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout


class Gauge(FloatLayout):
    """Simple circular gauge showing a percentage value."""

    value = NumericProperty(0.0)
    label = StringProperty("")
    color_rgba = ListProperty([0.2, 0.8, 0.5, 1.0])

    def __init__(self, **kwargs):  # type: ignore[override]
        super().__init__(**kwargs)
        with self.canvas:
            self._background_color = Color(0.2, 0.2, 0.2, 1)
            self._background = Line(circle=(0, 0, 0))
            self._fore_color = Color(0.2, 0.8, 0.5, 1)
            self._foreground = Line(circle=(0, 0, 0), cap='round')
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            value=self._update_canvas,
            color_rgba=self._update_canvas,
        )

    def _update_canvas(self, *_: object) -> None:
        self._fore_color.rgba = self.color_rgba
        radius = min(self.width, self.height) / 2 - 10
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        self._background.circle = (center_x, center_y, radius)
        self._background.width = 6
        self._foreground.width = 14
        angle_end = 360 * max(0.0, min(100.0, self.value)) / 100
        self._foreground.circle = (center_x, center_y, radius, -90, -90 + angle_end)
