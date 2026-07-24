"""AI detection overlay management for the waveform plots.

Owns the overlay plot items (regions + text labels) and their per-layer
visibility state, plus the toggle checkboxes shown above the waveform.
PyQt5 and pyqtgraph are used here for plot items and widgets. No audio
computation, model inference, or sidecar file I/O happens in this module —
callers (WavViewer) are responsible for loading detection data and pass it
in as plain layer dicts.
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout

from my_app.ai.settings import graph_label_for_detection, load_ai_settings

# Top-3 labels per unique start_time — sorted by score, min 0.10
_GRAPH_MIN = 0.10
_GRAPH_TOP = 3


class AiOverlayController:
    """Manages AI detection overlay plot items and layer visibility toggles.

    Args:
        plots: PlotWidget instances to draw region overlays on (typically
            the mono, top, and bottom waveform plots).
        label_plot: PlotWidget to draw text labels on (typically the main
            waveform plot).
        toggle_layout: QHBoxLayout to populate with per-layer visibility
            checkboxes.
    """

    def __init__(self, plots: list, label_plot, toggle_layout: QHBoxLayout):
        self._plots = plots
        self._label_plot = label_plot
        self._toggle_layout = toggle_layout
        self.overlay_items: list = []
        self.layer_visible: dict[str, bool] = {}

    def clear(self) -> None:
        """Remove all AI detection overlay items from all plots."""
        for plot, item, _source in self.overlay_items:
            try:
                plot.removeItem(item)
            except Exception:
                pass
        self.overlay_items.clear()

    def load_layers(self, layers: list[dict]) -> None:
        """Draw AI detection layers on the waveform.

        Each layer dict must contain ``name``, ``color`` (RGBA list),
        ``text_color`` (hex string) and ``detections`` (list of dicts with
        ``label``, ``score``, ``start_time``, ``end_time``).

        For layers with many overlapping windows (e.g. sliding-window
        models), only the highest-scoring detection per unique start time
        is shown.

        Args:
            layers: List of layer dicts as produced by AiAnalysisWorker.
        """
        self.clear()
        self._rebuild_toggles(layers)

        graph_mode = load_ai_settings().get("graph_label_mode", "scientific")

        for layer in layers:
            name = layer["name"]
            color = layer.get("color", [80, 80, 200, 35])
            brush = pg.mkBrush(*color)
            text_color = layer.get("text_color", "#aaaaff")

            by_window: dict[float, list] = {}
            for det in layer["detections"]:
                if not det.get("enabled", True):
                    continue
                if det["score"] < _GRAPH_MIN:
                    continue
                s = det["start_time"]
                by_window.setdefault(s, []).append(det)

            for start_s, dets in sorted(by_window.items()):
                top = sorted(dets, key=lambda d: -d["score"])[:_GRAPH_TOP]
                end_s = top[0]["end_time"]
                labels = [
                    (graph_label_for_detection(d, graph_mode), d["score"])
                    for d in top
                ]
                self._add_region(start_s, end_s, labels, name, brush, text_color)

    def _rebuild_toggles(self, layers: list[dict]) -> None:
        """Recreate the per-layer toggle checkboxes in the header row.

        Args:
            layers: List of layer dicts.
        """
        # Remove existing checkboxes
        while self._toggle_layout.count():
            item = self._toggle_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for layer in layers:
            name = layer["name"]
            color = layer.get("text_color", "#aaaaaa")
            cb = QCheckBox(name)
            cb.setObjectName("ai_layer_toggle")
            cb.setChecked(self.layer_visible.get(name, True))
            cb.setStyleSheet(f"color: {color};")
            cb.toggled.connect(lambda on, n=name: self.toggle_layer(n, on))
            self._toggle_layout.addWidget(cb)

    def _add_region(
        self,
        start_s: float,
        end_s: float,
        labels: list[tuple[str, float]],
        layer_name: str,
        brush,
        text_color: str,
    ) -> None:
        """Add a semi-transparent region and stacked text labels for one window.

        Args:
            start_s: Detection start in seconds.
            end_s: Detection end in seconds.
            labels: List of (label, score) tuples sorted by descending score.
            layer_name: Source layer name used for toggle lookup.
            brush: PyQtGraph brush for the region fill.
            text_color: Hex colour string for the text label.
        """
        visible = self.layer_visible.get(layer_name, True)

        for plot in self._plots:
            region = pg.LinearRegionItem(
                values=(start_s, end_s),
                movable=False,
                brush=brush,
            )
            region.setZValue(-10)
            region.setVisible(visible)
            plot.addItem(region)
            self.overlay_items.append((plot, region, layer_name))

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)

        for i, (label, score) in enumerate(labels):
            y = 0.95 - i * 0.15
            text = pg.TextItem(
                text=f"{label} {score:.2f}",
                color=text_color,
                anchor=(0, 1),
            )
            text.setFont(font)
            text.setPos(start_s, y)
            text.setZValue(5)
            text.setVisible(visible)
            self._label_plot.addItem(text)
            self.overlay_items.append((self._label_plot, text, layer_name))

    def toggle_layer(self, layer_name: str, visible: bool) -> None:
        """Show or hide all overlay items for a given layer.

        Args:
            layer_name: Name of the layer to toggle.
            visible: True to show, False to hide.
        """
        self.layer_visible[layer_name] = visible
        for _plot, item, name in self.overlay_items:
            if name == layer_name:
                item.setVisible(visible)
