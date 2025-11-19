"""Simple metric display widget."""

from __future__ import annotations

from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout


class Metric(BoxLayout):
    label = StringProperty("")
    value = StringProperty("--")
    unit = StringProperty("")

    def __init__(self, **kwargs):  # type: ignore[override]
        super().__init__(orientation="vertical", **kwargs)
