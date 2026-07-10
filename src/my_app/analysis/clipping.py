"""Pure clipping-region detection and summary calculations for WAV audio.

Qt-free: no PyQt5 or pyqtgraph imports. Operates purely on numpy arrays and
plain Python values, so it can be tested and reused without a GUI.
"""

from __future__ import annotations

import numpy as np


def find_raw_clipping_regions(clipped_samples: np.ndarray) -> list[tuple[int, int]]:
    """Find all raw clipping regions without merging.

    Args:
        clipped_samples: Boolean array of clipped samples.

    Returns:
        List of (start_sample, end_sample) tuples for raw clipping regions.
    """
    regions = []

    if len(clipped_samples.shape) > 1:
        # If multi-channel, combine all channels
        clipped_any_channel = np.any(clipped_samples, axis=1)
    else:
        # Single channel
        clipped_any_channel = clipped_samples

    # Find where clipping starts and stops
    clip_changes = np.diff(clipped_any_channel.astype(int))

    clip_starts = np.where(clip_changes == 1)[0] + 1
    clip_ends = np.where(clip_changes == -1)[0] + 1

    # Handle edge cases
    if clipped_any_channel[0]:
        clip_starts = np.concatenate([[0], clip_starts])
    if clipped_any_channel[-1]:
        clip_ends = np.concatenate([clip_ends, [len(clipped_any_channel)]])

    # Pair starts and ends
    for start, end in zip(clip_starts, clip_ends, strict=False):
        if end > start:  # Valid region
            regions.append((start, end))

    return regions


def merge_nearby_clipping_regions(
    regions: list[tuple[int, int]],
    sample_rate: int,
    gap_tolerance_ms: float = 5.0,
    min_duration_ms: float = 1.0,
) -> list[tuple[int, int]]:
    """Merge clipping regions that are close together.

    Args:
        regions: List of (start_sample, end_sample) tuples.
        sample_rate: Audio sample rate in Hz, used to convert the
            millisecond tolerances to sample counts.
        gap_tolerance_ms: Maximum gap in milliseconds to bridge.
        min_duration_ms: Minimum duration in milliseconds to keep a region.

    Returns:
        List of merged clipping regions.
    """
    if not regions:
        return []

    # Convert tolerances to samples
    gap_tolerance_samples = int(gap_tolerance_ms * sample_rate / 1000.0)
    min_duration_samples = int(min_duration_ms * sample_rate / 1000.0)

    # Sort regions by start time
    regions = sorted(regions, key=lambda x: x[0])

    # Merge nearby regions
    merged = [regions[0]]

    for start, end in regions[1:]:
        last_start, last_end = merged[-1]

        # If gap between regions is small enough, merge them
        gap_size = start - last_end
        if gap_size <= gap_tolerance_samples:
            # Extend the previous region to include this one
            merged[-1] = (last_start, end)
        else:
            # Keep as separate region
            merged.append((start, end))

    # Filter out regions that are too short (likely noise)
    filtered_regions = []
    for start, end in merged:
        duration_samples = end - start
        if duration_samples >= min_duration_samples:
            filtered_regions.append((start, end))

    return filtered_regions


def calculate_region_stats(
    regions: list[tuple[int, int]], clipped_array: np.ndarray, sample_rate: int
) -> dict:
    """Calculate clipping statistics for a set of regions.

    Args:
        regions: List of (start_sample, end_sample) tuples (typically merged).
        clipped_array: Boolean array of clipped samples for this channel.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Dictionary with samples_clipped, regions_count, total_duration_ms,
        and per-region detail (start_time/end_time/duration_ms in seconds
        and milliseconds respectively).
    """
    total_duration_ms = sum(
        (end - start) / sample_rate * 1000 for start, end in regions
    )
    return {
        "samples_clipped": int(np.sum(clipped_array)),
        "regions_count": len(regions),
        "total_duration_ms": round(total_duration_ms, 1),
        "regions_detail": [
            {
                "start_time": start / sample_rate,
                "end_time": end / sample_rate,
                "duration_ms": (end - start) / sample_rate * 1000,
            }
            for start, end in regions
        ],
    }


def get_clipping_summary(
    left_channel: np.ndarray,
    right_channel: np.ndarray,
    mono_mix: np.ndarray,
    sample_rate: int,
    is_float_format: bool = True,
) -> dict:
    """Get a summary of clipping detection results for all channels.

    Args:
        left_channel: Left channel sample array.
        right_channel: Right channel sample array.
        mono_mix: Mono-mixed sample array.
        sample_rate: Audio sample rate in Hz.
        is_float_format: Whether the source audio is float-formatted (uses
            a 0.99 clip threshold) or integer-formatted (uses 0.95).

    Returns:
        Dictionary with clipping statistics per channel using merged
        regions, matching the exact structure previously returned by
        WavViewer.get_clipping_summary().
    """
    clip_threshold = 0.99 if is_float_format else 0.95

    left_clipped = np.abs(left_channel) >= clip_threshold
    right_clipped = np.abs(right_channel) >= clip_threshold
    mono_clipped = np.abs(mono_mix) >= clip_threshold

    left_regions = merge_nearby_clipping_regions(
        find_raw_clipping_regions(left_clipped), sample_rate, gap_tolerance_ms=5.0
    )
    right_regions = merge_nearby_clipping_regions(
        find_raw_clipping_regions(right_clipped), sample_rate, gap_tolerance_ms=5.0
    )
    mono_regions = merge_nearby_clipping_regions(
        find_raw_clipping_regions(mono_clipped), sample_rate, gap_tolerance_ms=5.0
    )

    return {
        "left_channel": calculate_region_stats(left_regions, left_clipped, sample_rate),
        "right_channel": calculate_region_stats(right_regions, right_clipped, sample_rate),
        "mono_mix": calculate_region_stats(mono_regions, mono_clipped, sample_rate),
        "threshold_used": clip_threshold,
        "format_type": "float" if is_float_format else "integer",
        "gap_tolerance_ms": 5.0,
        "min_duration_ms": 1.0,
    }
