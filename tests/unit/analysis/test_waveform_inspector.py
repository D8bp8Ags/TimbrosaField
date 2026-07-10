"""Regression tests for the Fase 3 extraction of analysis.waveform_inspector.

Confirms the extracted pure functions produce exactly the same result
strings as the original WavViewer methods did.
"""

from __future__ import annotations

import numpy as np

from my_app.analysis import waveform_inspector as wi


# ---------------------------------------------------------------------------
# analyze_local_peak
# ---------------------------------------------------------------------------


def test_analyze_local_peak_reports_peak_near_local_max():
    signal = np.array([0.1] * 50 + [0.9] * 5 + [0.1] * 50)
    result = wi.analyze_local_peak(52, 0.9, signal, sample_rate=1000)
    assert result.startswith("Local Peak:")
    assert "dB" in result


def test_analyze_local_peak_returns_empty_when_not_near_peak():
    signal = np.array([0.1] * 50 + [0.9] * 5 + [0.1] * 50)
    result = wi.analyze_local_peak(52, 0.2, signal, sample_rate=1000)
    assert result == ""


def test_analyze_local_peak_returns_empty_without_signal():
    assert wi.analyze_local_peak(10, 0.5, None, sample_rate=1000) == ""


def test_analyze_local_peak_returns_empty_without_sample_rate():
    signal = np.array([0.1, 0.2, 0.3])
    assert wi.analyze_local_peak(1, 0.2, signal, sample_rate=None) == ""


def test_analyze_local_peak_short_signal_returns_empty():
    signal = np.array([0.1, 0.2])
    assert wi.analyze_local_peak(0, 0.2, signal, sample_rate=1000) == ""


# ---------------------------------------------------------------------------
# get_channel_context_info
# ---------------------------------------------------------------------------


def test_get_channel_context_info_main_wide_stereo():
    data = np.array([[0.5, -0.5]])
    result = wi.get_channel_context_info("mouse_label_main", 0, data)
    assert "Wide:" in result
    assert "L:+0.500" in result
    assert "R:-0.500" in result


def test_get_channel_context_info_main_centered():
    data = np.array([[0.5, 0.505]])
    result = wi.get_channel_context_info("mouse_label_main", 0, data)
    assert "Centered" in result


def test_get_channel_context_info_top_shows_left_channel():
    data = np.array([[0.3, 0.7]])
    result = wi.get_channel_context_info("mouse_label_top", 0, data)
    assert result == "Left Ch (R:+0.700)"


def test_get_channel_context_info_bottom_shows_right_channel():
    data = np.array([[0.3, 0.7]])
    result = wi.get_channel_context_info("mouse_label_bottom", 0, data)
    assert result == "Right Ch (L:+0.300)"


def test_get_channel_context_info_returns_empty_without_data():
    assert wi.get_channel_context_info("mouse_label_main", 0, None) == ""


def test_get_channel_context_info_returns_empty_when_index_out_of_range():
    data = np.array([[0.1, 0.2]])
    assert wi.get_channel_context_info("mouse_label_main", 5, data) == ""


def test_get_channel_context_info_unknown_label_returns_empty():
    data = np.array([[0.1, 0.2]])
    assert wi.get_channel_context_info("unknown_label", 0, data) == ""


# ---------------------------------------------------------------------------
# get_frequency_info_at_position
# ---------------------------------------------------------------------------


def test_get_frequency_info_at_position_detects_dominant_frequency():
    sample_rate = 8000
    t = np.arange(2048) / sample_rate
    signal = np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
    result = wi.get_frequency_info_at_position(1024, signal, sample_rate)
    assert result.startswith("~")
    assert result.endswith("Hz")
    # Dominant frequency should be close to 440 Hz.
    freq_value = float(result.strip("~Hz"))
    assert abs(freq_value - 440) < 50


def test_get_frequency_info_at_position_returns_empty_without_signal():
    assert wi.get_frequency_info_at_position(10, None, sample_rate=8000) == ""


def test_get_frequency_info_at_position_returns_empty_without_sample_rate():
    signal = np.zeros(2048)
    assert wi.get_frequency_info_at_position(10, signal, sample_rate=None) == ""


def test_get_frequency_info_at_position_short_window_returns_empty():
    signal = np.zeros(100)
    assert wi.get_frequency_info_at_position(10, signal, sample_rate=8000) == ""
