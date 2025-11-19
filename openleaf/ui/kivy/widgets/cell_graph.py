"""Simple per-cell bar graph widget."""

from __future__ import annotations

from typing import List

from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.widget import Widget


class CellGraph(Widget):
    """Displays a bar for each cell voltage value."""

    values = ListProperty([])

    def __init__(self, **kwargs):  # type: ignore[override]
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, values=self._redraw)

    def _redraw(self, *_: object) -> None:
        self.canvas.clear()
        with self.canvas:
            Color(0.08, 0.08, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.2, 0.2, 0.25, 1)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)

            if not self.values:
                return

            padding = dp(12)
            usable_width = max(self.width - 2 * padding, 1)
            usable_height = max(self.height - 2 * padding, 1)
            bar_width = max(usable_width / len(self.values), 2)

            min_v = min(self.values)
            max_v = max(self.values)
            span = max(max_v - min_v, 0.005)

            for index, value in enumerate(self.values):
                norm = (value - min_v) / span
                bar_height = usable_height * norm
                x = self.x + padding + index * bar_width
                y = self.y + padding
                Color(0.2 + 0.6 * norm, 0.8 - 0.4 * norm, 0.3, 1)
                Rectangle(pos=(x, y), size=(bar_width * 0.8, bar_height))

            Color(0.4, 0.4, 0.5, 0.5)
            Line(points=[self.x + padding, self.y + padding, self.x + padding + usable_width, self.y + padding], width=1)
