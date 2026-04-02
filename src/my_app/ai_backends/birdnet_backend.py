"""Official BirdNET backend for AI analysis.

LICENCE NOTICE
--------------
This module targets the official ``birdnet`` Python package published by the
BirdNET team / Cornell Lab of Ornithology ecosystem.

Reference: https://birdnet.cornell.edu/
Docs:      https://birdnet-team.github.io/birdnet/
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_mod
import time
from datetime import date as dt_date

from .base import AiBackend
from species_names import get_dutch_name

_MODEL_VERSION = "2.4"


def _rows_from_predictions(predictions) -> list[dict]:
    """Convert various dataframe-like outputs to ``list[dict]``."""
    if predictions is None:
        return []

    if hasattr(predictions, "to_structured_array"):
        structured = predictions.to_structured_array()
        if getattr(structured, "dtype", None) is not None and structured.dtype.names:
            return [
                {name: row[name] for name in structured.dtype.names}
                for row in structured
            ]

    if hasattr(predictions, "to_dataframe"):
        frame = predictions.to_dataframe()
        if hasattr(frame, "to_dict"):
            return frame.to_dict(orient="records")

    if isinstance(predictions, list):
        return [row for row in predictions if isinstance(row, dict)]

    if hasattr(predictions, "to_dicts"):
        return list(predictions.to_dicts())

    if hasattr(predictions, "iter_rows"):
        try:
            return list(predictions.iter_rows(named=True))
        except TypeError:
            pass

    if hasattr(predictions, "iterrows"):
        return [dict(row) for _, row in predictions.iterrows()]

    if hasattr(predictions, "to_dict"):
        try:
            records = predictions.to_dict(orient="records")
            if isinstance(records, list):
                return records
        except TypeError:
            pass

        as_dict = predictions.to_dict()
        if isinstance(as_dict, dict):
            keys = list(as_dict.keys())
            if keys and all(isinstance(as_dict[k], dict) for k in keys):
                row_ids = sorted({
                    row_id for value in as_dict.values()
                    for row_id in value.keys()
                })
                return [
                    {
                        key: as_dict[key].get(row_id)
                        for key in keys
                    }
                    for row_id in row_ids
                ]

    raise RuntimeError("BirdNET returned an unsupported predictions object")


def _to_seconds(value) -> float:
    """Convert BirdNET time values to seconds."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if ":" not in text:
        try:
            return float(text)
        except ValueError:
            return 0.0

    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
    except ValueError:
        return 0.0
    return 0.0


def _get_week(metadata: dict) -> int | None:
    """Extract ISO-like BirdNET week number from WAV metadata."""
    bext = metadata.get("bext") or {}
    date_str = (
        bext.get("Origination Date")
        or bext.get("OriginationDate")
        or ""
    )
    if not date_str or len(date_str) < 10:
        return None
    try:
        recorded = dt_date.fromisoformat(date_str[:10])
    except ValueError:
        return None
    return min(max(round(recorded.timetuple().tm_yday / 7.25), 1), 48)


def _birdnet_detail(metadata: dict, species_filter: list[str] | None) -> str:
    """Return contextual detail text for BirdNET detections."""
    gps = metadata.get("gps") or {}
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    week = _get_week(metadata)

    if species_filter:
        return f"Geo filter applied ({len(species_filter)} species)"
    if lat is not None and lon is not None and week is not None:
        return "Geo filter unavailable"
    return ""


def _split_species(row: dict) -> tuple[str, str]:
    """Return ``(scientific_name, common_name)`` from a BirdNET row."""
    scientific = str(row.get("scientific_name") or "").strip()
    common = str(row.get("common_name") or "").strip()

    if scientific or common:
        return scientific, common

    label = (
        row.get("species_name")
        or row.get("label")
        or row.get("species")
        or ""
    )
    text = str(label).strip()
    if not text:
        return "", ""

    if "_" in text:
        scientific, common = text.split("_", 1)
        return scientific.strip(), common.strip()
    return "", text


class BirdnetBackend(AiBackend):
    """Wrap the official BirdNET Python package for species detection."""

    name = "BirdNET"
    color = (50, 200, 80, 45)
    text_color = "#40d060"

    def __init__(self) -> None:
        self.options = {}
        self._debug_output = None

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        """Run BirdNET in an isolated subprocess.

        The official ``birdnet`` package loads TensorFlow. On this macOS setup
        that cannot safely coexist with AST/PyTorch in the GUI process, so
        BirdNET runs in a spawned child process just like Perch.
        """
        ctx = mp.get_context("spawn")
        result_queue: mp.Queue = ctx.Queue()
        process = ctx.Process(
            target=_birdnet_worker,
            args=(wav_path, metadata, dict(self.options), result_queue),
        )
        process.start()
        try:
            deadline = time.monotonic() + 600
            while True:
                try:
                    result = result_queue.get(timeout=1)
                    break
                except queue_mod.Empty:
                    if not process.is_alive():
                        raise RuntimeError(
                            "BirdNET subprocess exited before returning "
                            f"results (exit code {process.exitcode})"
                        )
                    if time.monotonic() >= deadline:
                        process.terminate()
                        raise RuntimeError("BirdNET subprocess timed out")
        finally:
            process.join(timeout=30)

        if isinstance(result, Exception):
            raise result
        self._debug_output = result.get("raw_output")
        return result.get("detections", [])

    @property
    def debug_output(self):
        """JSON-safe copy of the raw BirdNET prediction payload."""
        return self._debug_output


def _birdnet_worker(
    wav_path: str,
    metadata: dict,
    options: dict,
    result_queue: mp.Queue,
) -> None:
    """Run official BirdNET inference inside a fresh subprocess."""
    try:
        import birdnet  # noqa: PLC0415

        model = birdnet.load("acoustic", _MODEL_VERSION, "tf")
        top_k = int(options.get("top_k", 5))
        min_confidence = float(options.get("min_confidence", 0.10))
        overlap_duration_s = float(options.get("overlap_duration_s", 0.0))
        sigmoid_sensitivity = float(options.get("sigmoid_sensitivity", 1.0))
        bandpass_fmin = int(options.get("bandpass_fmin", 0))
        bandpass_fmax = int(options.get("bandpass_fmax", 15000))
        use_geo_filter = bool(options.get("use_geo_filter", True))
        fallback_note = ""

        gps = metadata.get("gps") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        week = _get_week(metadata)
        species_filter = None
        if use_geo_filter and lat is not None and lon is not None and week is not None:
            try:
                geo_model = birdnet.load("geo", _MODEL_VERSION, "tf")
                geo_predictions = geo_model.predict(float(lat), float(lon), week=week)
                species = []
                for row in _rows_from_predictions(geo_predictions):
                    scientific, common = _split_species(row)
                    if scientific and common:
                        species.append(f"{scientific}_{common}")
                    elif common:
                        species.append(common)
                species_filter = species or None
            except Exception:
                species_filter = None

        try:
            kwargs = {
                "top_k": top_k,
                "overlap_duration_s": overlap_duration_s,
                "bandpass_fmin": bandpass_fmin,
                "bandpass_fmax": bandpass_fmax,
                "sigmoid_sensitivity": sigmoid_sensitivity,
                "default_confidence_threshold": min_confidence,
            }
            if species_filter:
                kwargs["custom_species_list"] = species_filter
            predictions = model.predict(wav_path, **kwargs)
        except TypeError:
            fallback_note = (
                "Limited API fallback used; some BirdNET options were not applied"
            )
            predictions = model.predict(wav_path)

        raw_rows = _rows_from_predictions(predictions)
        detail_text = _birdnet_detail(metadata, species_filter)
        if fallback_note:
            detail_text = f"{detail_text}; {fallback_note}" if detail_text else fallback_note
        detections = []
        for row in raw_rows:
            scientific, common = _split_species(row)
            dutch = get_dutch_name(scientific)
            label = scientific or common or str(row.get("label") or "Unknown")
            score = row.get("confidence")
            if score is None:
                score = row.get("score", 0.0)

            start = row.get("start_time", row.get("start"))
            end = row.get("end_time", row.get("end"))

            detections.append({
                "label": label,
                "scientific_name": scientific,
                "english_name": common,
                "dutch_name": dutch,
                "score": float(score),
                "start_time": _to_seconds(start),
                "end_time": _to_seconds(end),
                "detail": detail_text,
                "tag": scientific or label,
                "tag_key": scientific or label,
            })

        result_queue.put({
            "detections": detections,
            "raw_output": {
                "model_version": _MODEL_VERSION,
                "options": options,
                "species_filter": species_filter,
                "fallback_note": fallback_note,
                "prediction_rows": raw_rows,
            },
        })
    except Exception as exc:
        result_queue.put(exc)
