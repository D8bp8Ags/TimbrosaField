"""Perch backend for AI analysis.

LICENCE NOTICE
--------------
This module wraps the perch-hoplite library and the Perch bird-vocalization
classifier (version 2) developed by Google Research.

  perch-hoplite — Apache License 2.0
  Perch v2 model weights — Apache License 2.0

Commercial use is permitted under the Apache 2.0 licence.

Reference: https://github.com/google-research/perch
Model:     https://www.kaggle.com/models/google/bird-vocalization-classifier

Process isolation note
----------------------
TensorFlow and PyTorch (MPS) cannot share the same process on Apple Silicon.
Perch inference therefore runs in a dedicated subprocess spawned with
``multiprocessing.get_context("spawn")`` so TF never touches torch's Metal
context.  See: https://github.com/tensorflow/tensorflow/issues/13615
"""

import logging
import multiprocessing as mp
import os
import queue as queue_mod
import time
from math import gcd

from my_app.ai.model_manager import PERCH_MODEL, ensure_model_installed
from .base import AiBackend
from my_app.species_names import get_dutch_name

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.10
_TOP_K = 5


# ---------------------------------------------------------------------------
# Subprocess worker — must be a module-level function so it is picklable.
# Runs in a fresh Python process with no torch present.
# ---------------------------------------------------------------------------

def _perch_worker(model_path: str, wav_path: str, min_score: float, top_k: int,
                  overlap_ratio: float,
                  result_queue: mp.Queue) -> None:
    """Executed inside a spawned subprocess; TF is safe to import here."""
    try:
        import csv  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415
        from ml_collections import config_dict  # noqa: PLC0415
        from perch_hoplite.zoo.taxonomy_model_tf import TaxonomyModelTF  # noqa: PLC0415
        from scipy.signal import resample_poly  # noqa: PLC0415

        config = config_dict.ConfigDict()
        config.model_path = model_path
        config.tfhub_version = None
        config.window_size_s = 5.0
        config.hop_size_s = 5.0
        config.sample_rate = 32000
        model = TaxonomyModelTF.from_config(config)
        sample_rate: int = model.sample_rate
        window_samples = int(model.window_size_s * sample_rate)
        step_samples = max(1, int(window_samples * max(0.1, 1.0 - overlap_ratio)))

        # Load labels from model assets
        labels: list[str] = []
        for filename in ("labels.csv", "label.csv"):
            label_csv = os.path.join(model.model_path, "assets", filename)
            if not os.path.exists(label_csv):
                continue
            try:
                with open(label_csv) as fh:
                    reader = csv.DictReader(fh)
                    col = next(iter(reader.fieldnames or []), None)
                    if col:
                        labels = [row[col] for row in reader]
                        break
            except Exception:
                pass

        audio, source_sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if source_sr != sample_rate:
            divisor = gcd(int(source_sr), int(sample_rate))
            audio = resample_poly(
                audio,
                int(sample_rate) // divisor,
                int(source_sr) // divisor,
            ).astype(np.float32)
        total_samples = len(audio)
        results: list[dict] = []
        debug_windows: list[dict] = []

        for start in range(0, total_samples, step_samples):
            chunk = audio[start: start + window_samples].astype(np.float32)
            padded = len(chunk) < window_samples
            if padded:
                chunk = np.pad(chunk, (0, window_samples - len(chunk)))

            start_s = start / sample_rate
            end_s = min((start + window_samples) / sample_rate,
                        total_samples / sample_rate)

            batch = _frame_perch_audio(
                chunk[np.newaxis, :],
                sample_rate,
                float(model.window_size_s),
                float(model.hop_size_s),
            )
            batch = _normalize_perch_audio(batch, 0.25)
            rebatched = batch.reshape([-1, batch.shape[-1]])
            outputs = model.model.signatures["serving_default"](inputs=rebatched)
            logits = np.array(outputs["label"]).reshape(-1)
            shifted = logits - logits.max()
            exp = np.exp(shifted)
            probs = exp / exp.sum()
            top_predictions = []

            for rank, idx in enumerate(np.argsort(probs)[::-1][:top_k], start=1):
                score = float(probs[idx])
                label = labels[idx] if idx < len(labels) else str(idx)
                top_predictions.append({
                    "index": int(idx),
                    "rank": rank,
                    "label": label,
                    "score": score,
                })
                if score < min_score:
                    continue
                detail_parts = [f"Top {rank}/{top_k} window prediction"]
                if padded:
                    detail_parts.append("chunk padded")
                results.append({
                    "label": label,
                    "scientific_name": label,
                    "english_name": "",
                    "dutch_name": get_dutch_name(label),
                    "score": score,
                    "start_time": start_s,
                    "end_time": end_s,
                    "detail": "; ".join(detail_parts),
                    "tag": label,
                    "tag_key": label,
                })

            debug_windows.append({
                "start_time": start_s,
                "end_time": end_s,
                "padded": padded,
                "top_predictions": top_predictions,
            })
        result_queue.put({
            "detections": results,
            "raw_output": {
                "model_name": "perch_v2",
                "sample_rate": sample_rate,
                "window_size_s": float(model.window_size_s),
                "step_size_s": step_samples / sample_rate,
                "overlap_ratio": overlap_ratio,
                "label_count": len(labels),
                "windows": debug_windows,
            },
        })

    except Exception as exc:
        result_queue.put(exc)


def _frame_perch_audio(
    audio_batch,
    sample_rate: int,
    window_size_s: float,
    hop_size_s: float,
):
    """Frame audio like Perch's helper without importing librosa."""
    import numpy as np  # noqa: PLC0415

    frame_length = int(window_size_s * sample_rate)
    hop_length = int(hop_size_s * sample_rate)
    if audio_batch.shape[-1] < frame_length:
        total_pad = frame_length - audio_batch.shape[-1]
        left = total_pad // 2
        right = total_pad - left
        audio_batch = np.pad(audio_batch, [(0, 0), (left, right)])
    frames = []
    for audio in audio_batch:
        starts = range(0, max(1, audio.shape[-1] - frame_length + 1), hop_length)
        frames.append(np.stack([audio[start: start + frame_length] for start in starts]))
    return np.stack(frames)


def _normalize_perch_audio(framed_audio, target_peak: float):
    """Normalize framed audio like Perch's helper."""
    import numpy as np  # noqa: PLC0415

    framed_audio = framed_audio.copy()
    framed_audio -= np.mean(framed_audio, axis=-1, keepdims=True)
    peak_norm = np.max(np.abs(framed_audio), axis=-1, keepdims=True)
    framed_audio = np.divide(framed_audio, peak_norm, where=(peak_norm > 0.0))
    return framed_audio * target_peak


# ---------------------------------------------------------------------------
# Backend class
# ---------------------------------------------------------------------------

class PerchBackend(AiBackend):
    """Wraps perch-hoplite (Perch v2) to detect bird species in a WAV file.

    Inference runs in a separate spawned subprocess to avoid Metal GPU
    context conflicts with PyTorch/MPS on Apple Silicon.
    """

    name = "Perch"
    color = (220, 120, 50, 40)
    text_color = "#dc7832"

    def __init__(self) -> None:
        self.options = {}
        self._debug_output = None

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:  # noqa: ARG002
        """Run Perch inference in an isolated subprocess.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Unused; present for interface compatibility.

        Returns:
            List of detection dicts (label, score, start_time, end_time).
        """
        ctx = mp.get_context("spawn")
        result_queue: mp.Queue = ctx.Queue()
        model_path = str(ensure_model_installed(PERCH_MODEL.model_id))
        min_score = float(self.options.get("min_score", _MIN_SCORE))
        top_k = int(self.options.get("top_k", _TOP_K))
        overlap_ratio = float(self.options.get("overlap_ratio", 0.5))
        process = ctx.Process(
            target=_perch_worker,
            args=(model_path, wav_path, min_score, top_k, overlap_ratio, result_queue),
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
                            f"Perch subprocess exited before returning results "
                            f"(exit code {process.exitcode})"
                        )
                    if time.monotonic() >= deadline:
                        process.terminate()
                        raise RuntimeError("Perch subprocess timed out")
        finally:
            process.join(timeout=30)

        if isinstance(result, Exception):
            raise result
        self._debug_output = result.get("raw_output")
        return result.get("detections", [])

    @property
    def debug_output(self):
        """JSON-safe copy of the raw Perch prediction payload."""
        return self._debug_output
