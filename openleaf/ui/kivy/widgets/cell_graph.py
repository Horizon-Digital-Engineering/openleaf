"""Simple per-cell bar graph widget with axis labels."""

from __future__ import annotations

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.widget import Widget


class CellGraph(Widget):
    """Displays a bar for each cell voltage value with Y-axis legend and X-axis cell numbers."""

    values = ListProperty([])

    def __init__(self, **kwargs):  # type: ignore[override]
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, values=self._redraw)

    def _make_label(self, text: str, font_size: int = 11) -> CoreLabel:
        """Create a texture label for drawing on canvas."""
        label = CoreLabel(text=text, font_size=dp(font_size))
        label.refresh()
        return label

    def _redraw(self, *_: object) -> None:
        self.canvas.clear()
        with self.canvas:
            # Background
            Color(0.08, 0.08, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.2, 0.2, 0.25, 1)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)

            if not self.values:
                return

            # Layout margins for labels
            left_margin = dp(45)   # Space for Y-axis labels
            bottom_margin = dp(24) # Space for X-axis labels
            top_padding = dp(12)
            right_padding = dp(12)

            graph_x = self.x + left_margin
            graph_y = self.y + bottom_margin
            graph_width = max(self.width - left_margin - right_padding, 1)
            graph_height = max(self.height - bottom_margin - top_padding, 1)

            bar_width = max(graph_width / len(self.values), 2)

            min_v = min(self.values)
            max_v = max(self.values)
            span = max(max_v - min_v, 0.005)

            # Add 10% padding below min so lowest cells are still visible
            padding_v = span * 0.15
            display_min = min_v - padding_v
            display_span = (max_v - display_min)

            # Draw bars
            min_bar_height = dp(6)  # Minimum bar height so lowest cell is visible
            for index, value in enumerate(self.values):
                norm = (value - display_min) / display_span
                bar_height = max(graph_height * norm, min_bar_height)
                x = graph_x + index * bar_width
                y = graph_y
                # Color based on position relative to actual min/max
                color_norm = (value - min_v) / span if span > 0 else 0.5
                Color(0.2 + 0.6 * color_norm, 0.8 - 0.4 * color_norm, 0.3, 1)
                Rectangle(pos=(x, y), size=(bar_width * 0.8, bar_height))

            # Baseline
            Color(0.4, 0.4, 0.5, 0.5)
            Line(points=[graph_x, graph_y, graph_x + graph_width, graph_y], width=1)

            # Y-axis labels (voltage scale on left) - use display range
            Color(0.7, 0.7, 0.7, 1)
            for i in range(5):  # 5 tick marks
                frac = i / 4.0
                voltage = display_min + display_span * frac
                label_y = graph_y + graph_height * frac

                # Tick line
                Color(0.3, 0.3, 0.35, 1)
                Line(points=[graph_x - dp(4), label_y, graph_x, label_y], width=1)

                # Voltage label
                Color(0.7, 0.7, 0.7, 1)
                lbl = self._make_label(f"{voltage:.3f}V")
                tex = lbl.texture
                Rectangle(
                    texture=tex,
                    pos=(self.x + dp(4), label_y - tex.height / 2),
                    size=tex.size
                )

            # X-axis labels (cell numbers every 12 cells for 96 cells)
            num_cells = len(self.values)
            if num_cells >= 48:
                step = 12
            elif num_cells >= 24:
                step = 6
            else:
                step = 1
            Color(0.7, 0.7, 0.7, 1)
            for cell_num in range(1, num_cells + 1, step):
                index = cell_num - 1
                x = graph_x + index * bar_width + bar_width * 0.4

                # Cell number label
                lbl = self._make_label(str(cell_num))
                tex = lbl.texture
                Rectangle(
                    texture=tex,
                    pos=(x - tex.width / 2, self.y + dp(4)),
                    size=tex.size
                )
