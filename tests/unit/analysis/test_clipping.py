"""Regression tests for the Fase 3 extraction of analysis.clipping from WavViewer.

Confirms the extracted pure functions produce exactly the same regions and
summary structure as the original WavViewer methods did.
"""

from __future__ import annotations

import numpy as np

from my_app.analysis import clipping


def test_find_raw_clipping_regions_single_region():
    clipped = np.array([False, False, True, True, True, False, False])
    regions = clipping.find_raw_clipping_regions(clipped)
    assert regions == [(2, 5)]


def test_find_raw_clipping_regions_multi_channel_combines_any():
    clipped = np.array(
        [[False, False], [True, False], [False, True], [False, False]]
    )
    regions = clipping.find_raw_clipping_regions(clipped)
    assert regions == [(1, 3)]


def test_find_raw_clipping_regions_edge_start_and_end():
    clipped = np.array([True, True, False, False, True])
    regions = clipping.find_raw_clipping_regions(clipped)
    assert regions == [(0, 2), (4, 5)]


def test_find_raw_clipping_regions_no_clipping_returns_empty():
    clipped = np.array([False, False, False])
    assert clipping.find_raw_clipping_regions(clipped) == []


def test_merge_nearby_clipping_regions_bridges_small_gap():
    # sample_rate=1000 -> 5ms tolerance = 5 samples
    regions = [(0, 10), (12, 20)]
    merged = clipping.merge_nearby_clipping_regions(
        regions, sample_rate=1000, gap_tolerance_ms=5.0, min_duration_ms=0.0
    )
    assert merged == [(0, 20)]


def test_merge_nearby_clipping_regions_keeps_far_apart_regions_separate():
    regions = [(0, 10), (100, 110)]
    merged = clipping.merge_nearby_clipping_regions(
        regions, sample_rate=1000, gap_tolerance_ms=5.0, min_duration_ms=0.0
    )
    assert merged == [(0, 10), (100, 110)]


def test_merge_nearby_clipping_regions_filters_short_regions():
    # 1 sample at 1000Hz = 1ms, below the 5ms min_duration threshold
    regions = [(0, 1)]
    merged = clipping.merge_nearby_clipping_regions(
        regions, sample_rate=1000, gap_tolerance_ms=5.0, min_duration_ms=5.0
    )
    assert merged == []


def test_merge_nearby_clipping_regions_empty_input_returns_empty():
    assert clipping.merge_nearby_clipping_regions([], sample_rate=44100) == []


def test_get_clipping_summary_matches_expected_structure():
    sample_rate = 1000
    left = np.array([0.5, 0.99, 1.0, 0.5, 0.5])
    right = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    mono = (left + right) / 2

    summary = clipping.get_clipping_summary(
        left_channel=left,
        right_channel=right,
        mono_mix=mono,
        sample_rate=sample_rate,
        is_float_format=True,
    )

    assert summary["threshold_used"] == 0.99
    assert summary["format_type"] == "float"
    assert summary["left_channel"]["regions_count"] == 1
    assert summary["right_channel"]["regions_count"] == 0
    assert summary["left_channel"]["samples_clipped"] == 2


def test_get_clipping_summary_integer_format_uses_lower_threshold():
    sample_rate = 1000
    left = np.array([0.96, 0.96, 0.5])
    right = np.array([0.1, 0.1, 0.1])
    mono = (left + right) / 2

    summary = clipping.get_clipping_summary(
        left_channel=left,
        right_channel=right,
        mono_mix=mono,
        sample_rate=sample_rate,
        is_float_format=False,
    )

    assert summary["threshold_used"] == 0.95
    assert summary["left_channel"]["regions_count"] == 1
