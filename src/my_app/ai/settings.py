"""Persistent AI UI/runtime settings shared by analyzer and waveform overlay."""

from __future__ import annotations

from copy import deepcopy

from PyQt5.QtCore import QSettings

DEFAULT_AI_SETTINGS: dict = {
    "graph_label_mode": "scientific",
    "birdnet": {
        "top_k": 5,
        "min_confidence": 0.10,
        "overlap_duration_s": 0.0,
        "sigmoid_sensitivity": 1.0,
        "bandpass_fmin": 0,
        "bandpass_fmax": 15000,
        "use_geo_filter": True,
    },
    "ast": {
        "top_n": 5,
        "min_score": 0.05,
        "step_seconds": 5,
    },
    "perch": {
        "top_k": 5,
        "min_score": 0.10,
        "overlap_ratio": 0.5,
    },
}


def _merge_defaults(data: dict | None) -> dict:
    merged = deepcopy(DEFAULT_AI_SETTINGS)
    if not isinstance(data, dict):
        return merged

    for key, value in data.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def load_ai_settings() -> dict:
    """Load persisted AI settings from QSettings."""
    settings = QSettings()
    stored = settings.value("ai/settings", None, type=dict)
    return _merge_defaults(stored)


def save_ai_settings(data: dict) -> None:
    """Persist AI settings to QSettings."""
    settings = QSettings()
    settings.setValue("ai/settings", _merge_defaults(data))


def graph_label_for_detection(detection: dict, mode: str) -> str:
    """Choose the preferred overlay label for a detection."""
    scientific = (detection.get("scientific_name") or "").strip()
    english = (detection.get("english_name") or "").strip()
    dutch = (detection.get("dutch_name") or "").strip()
    fallback = (detection.get("label") or "").strip()

    if mode == "dutch":
        return dutch or scientific or english or fallback
    if mode == "english":
        return english or scientific or dutch or fallback
    return scientific or english or dutch or fallback
