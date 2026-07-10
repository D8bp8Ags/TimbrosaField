"""Regression tests for the Fase 4 extraction of AiOverlayController from WavViewer.

Confirms overlay item creation, removal, and layer visibility toggling
behave the same as the original WavViewer methods did.
"""

from __future__ import annotations

import pyqtgraph as pg
import pytest
from PyQt5.QtWidgets import QHBoxLayout, QWidget

from my_app.ui.waveform.ai_overlay import AiOverlayController


@pytest.fixture
def controller(qapp):
    plot = pg.PlotWidget()
    top = pg.PlotWidget()
    bottom = pg.PlotWidget()
    host = QWidget()
    layout = QHBoxLayout(host)
    ctrl = AiOverlayController(plots=[plot, top, bottom], label_plot=plot, toggle_layout=layout)
    # Keep strong references alive for the test's duration; PyQt5 deletes
    # the underlying C++ widgets once their Python wrappers are collected.
    ctrl._test_host = host
    ctrl._test_plots = (plot, top, bottom)
    return ctrl


def _layer(name="BirdNET", detections=None):
    return {
        "name": name,
        "color": [80, 80, 200, 35],
        "text_color": "#aaaaff",
        "detections": detections
        if detections is not None
        else [{"label": "Merel", "score": 0.9, "start_time": 1.0, "end_time": 2.0}],
    }


def test_load_layers_adds_overlay_items(controller):
    controller.load_layers([_layer()])
    assert len(controller.overlay_items) > 0
    # One region per plot (3) + one text label for the single detection window
    assert len(controller.overlay_items) == 4


def test_load_layers_creates_toggle_checkbox(controller):
    controller.load_layers([_layer(name="AST")])
    assert controller._toggle_layout.count() == 1


def test_clear_removes_all_overlay_items(controller):
    controller.load_layers([_layer()])
    assert len(controller.overlay_items) > 0

    controller.clear()

    assert controller.overlay_items == []


def test_load_layers_clears_previous_overlay(controller):
    controller.load_layers([_layer(name="A")])
    controller.load_layers([_layer(name="B")])
    # No leftover items from layer "A" should remain.
    assert all(name == "B" for _plot, _item, name in controller.overlay_items)


def test_toggle_layer_hides_and_shows_items(controller):
    controller.load_layers([_layer(name="BirdNET")])
    region = controller.overlay_items[0][1]
    assert region.isVisible() is True

    controller.toggle_layer("BirdNET", False)
    assert region.isVisible() is False

    controller.toggle_layer("BirdNET", True)
    assert region.isVisible() is True


def test_toggle_layer_only_affects_matching_layer(controller):
    controller.load_layers([_layer(name="A"), _layer(name="B")])

    controller.toggle_layer("A", False)

    for _plot, item, name in controller.overlay_items:
        expected_visible = name != "A"
        assert item.isVisible() is expected_visible


def test_load_layers_respects_existing_visibility_state(controller):
    controller.load_layers([_layer(name="BirdNET")])
    controller.toggle_layer("BirdNET", False)

    # Reloading the same layer name should keep it hidden (matches original
    # _ai_layer_visible persistence behavior).
    controller.load_layers([_layer(name="BirdNET")])

    for _plot, item, _name in controller.overlay_items:
        assert item.isVisible() is False
