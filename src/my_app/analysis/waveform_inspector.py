"""Pure local-peak, frequency, and channel-context analysis for waveform hover.

Qt-free: no PyQt5 or pyqtgraph imports. Operates purely on numpy arrays and
plain Python values. Presentation (label text placement, colors, cursors)
stays in WavViewer.
"""

from __future__ import annotations

import numpy as np


def analyze_local_peak(
    sample_idx: int,
    current_amplitude: float,
    cached_mean_signal: np.ndarray | None,
    sample_rate: int | None,
) -> str:
    """Analyze if current position is near a local peak.

    Args:
        sample_idx: Current sample index.
        current_amplitude: Current amplitude value.
        cached_mean_signal: Mono-mixed signal array, or None if unavailable.
        sample_rate: Audio sample rate in Hz, or None if unavailable.

    Returns:
        String with peak information, or empty string if not near a peak
        or if required data is unavailable.
    """
    if cached_mean_signal is None or sample_rate is None:
        return ""

    try:
        # Check 10ms window around current position
        window_size = int(sample_rate * 0.01)
        start_idx = max(0, sample_idx - window_size)
        end_idx = min(len(cached_mean_signal), sample_idx + window_size)

        if len(cached_mean_signal) <= end_idx:
            return ""

        window_data = cached_mean_signal[start_idx:end_idx]

        if len(window_data) == 0:
            return ""

        # Find local maximum in window
        local_max = np.max(np.abs(window_data))

        # Check if current position is near the peak (within 90%)
        if current_amplitude >= local_max * 0.9:
            peak_db = 20 * np.log10(local_max) if local_max > 1e-12 else -120
            return f"Local Peak: {peak_db:.1f} dB"

        return ""

    except (
        AttributeError,
        IndexError,
        KeyError,
        ValueError,
        TypeError,
        RuntimeError,
    ):
        return ""


def get_channel_context_info(
    label_attr: str, sample_idx: int, current_data: np.ndarray | None
) -> str:
    """Get channel-specific context information.

    Args:
        label_attr: Label attribute name to determine which plot/channel
            the hover position belongs to ('mouse_label_main',
            'mouse_label_top', or 'mouse_label_bottom').
        sample_idx: Current sample index.
        current_data: Stereo sample array (n_samples, 2), or None if no
            audio is loaded.

    Returns:
        Channel context string, or empty string if data is unavailable.
    """
    if current_data is None or sample_idx >= len(current_data):
        return ""

    text = ""
    try:
        if label_attr == "mouse_label_main":
            # Mono/Main plot - show L/R comparison
            left_val = current_data[sample_idx, 0]
            right_val = current_data[sample_idx, 1]

            # Stereo width analysis
            width = abs(left_val - right_val)
            if width > 0.1:
                text = f"L:{left_val:+.3f} R:{right_val:+.3f} Wide: {width:.3f}"
            elif width < 0.01:
                text = f"L:{left_val:+.3f} R:{right_val:+.3f} Centered"
            else:
                text = f"L:{left_val:+.3f} R:{right_val:+.3f}"

        elif label_attr == "mouse_label_top":
            # Left channel - show correlation with right
            right_val = current_data[sample_idx, 1]
            text = f"Left Ch (R:{right_val:+.3f})"

        elif label_attr == "mouse_label_bottom":
            # Right channel - show correlation with left
            left_val = current_data[sample_idx, 0]
            text = f"Right Ch (L:{left_val:+.3f})"

    except (
        AttributeError,
        IndexError,
        KeyError,
        ValueError,
        TypeError,
        RuntimeError,
    ):
        text = ""

    return text


def get_frequency_info_at_position(
    sample_idx: int,
    cached_mean_signal: np.ndarray | None,
    sample_rate: int | None,
) -> str:
    """Get frequency analysis at current position (CPU intensive - optional).

    Args:
        sample_idx: Current sample index.
        cached_mean_signal: Mono-mixed signal array, or None if unavailable.
        sample_rate: Audio sample rate in Hz, or None if unavailable.

    Returns:
        Frequency information string, or empty string if data is
        unavailable or the window is too short.
    """
    if cached_mean_signal is None or sample_rate is None:
        return ""

    try:
        # Small FFT window for responsiveness
        window_size = 1024
        start_idx = max(0, sample_idx - window_size // 2)
        end_idx = min(len(cached_mean_signal), start_idx + window_size)

        window_data = cached_mean_signal[start_idx:end_idx]

        if len(window_data) < 256:
            return ""

        # Apply window function and FFT
        windowed = window_data * np.hanning(len(window_data))
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)

        # Find dominant frequency
        freqs = np.fft.rfftfreq(len(windowed), 1 / sample_rate)
        dominant_idx = np.argmax(magnitude[1:]) + 1  # Skip DC
        dominant_freq = freqs[dominant_idx]

        if dominant_freq > 20:  # Above human hearing threshold
            return f"~{dominant_freq:.0f}Hz"

        return ""

    except (
        AttributeError,
        IndexError,
        KeyError,
        ValueError,
        TypeError,
        RuntimeError,
    ):
        return ""
