"""AST (Audio Spectrogram Transformer) backend for AI analysis.

LICENCE NOTICE
--------------
This module uses the ``MIT/ast-finetuned-audioset-10-10-0.448`` model via
the HuggingFace Transformers library.

  transformers library — Apache Licence 2.0
  MIT/ast-finetuned-audioset model — Apache Licence 2.0

Both licences permit commercial use with attribution.

Reference: https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.448
Original paper: https://arxiv.org/abs/2104.01778
"""

import json
import logging
import os
import urllib.request
from pathlib import Path

from .base import AiBackend

logger = logging.getLogger(__name__)

_MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.448"
_ONTOLOGY_URL = (
    "https://raw.githubusercontent.com/audioset/ontology/master/ontology.json"
)
_ONTOLOGY_CACHE = Path.home() / ".cache" / "audioset_ontology.json"

# Module-level cache so ontology is only parsed once per process
_ontology_has_children: set[str] | None = None
_ontology_has_parent: set[str] | None = None


def _load_ontology() -> tuple[set[str], set[str]]:
    """Load AudioSet ontology and return (has_children, has_parent) sets.

    Downloads once to ``~/.cache/audioset_ontology.json``.  Returns empty
    sets if the download fails.
    """
    global _ontology_has_children, _ontology_has_parent
    if _ontology_has_children is not None:
        return _ontology_has_children, _ontology_has_parent

    try:
        if not _ONTOLOGY_CACHE.exists():
            data = urllib.request.urlopen(_ONTOLOGY_URL, timeout=10).read()
            _ONTOLOGY_CACHE.write_bytes(data)
        entries = json.loads(_ONTOLOGY_CACHE.read_text())
    except Exception as exc:
        logger.warning("Could not load AudioSet ontology: %s", exc)
        _ontology_has_children = set()
        _ontology_has_parent = set()
        return _ontology_has_children, _ontology_has_parent

    id_to_name = {e["id"]: e["name"] for e in entries}
    has_children: set[str] = set()
    has_parent: set[str] = set()

    for entry in entries:
        parent_name = entry["name"]
        for child_id in entry.get("child_ids", []):
            child_name = id_to_name.get(child_id)
            if child_name:
                has_children.add(parent_name)
                has_parent.add(child_name)

    _ontology_has_children = has_children
    _ontology_has_parent = has_parent
    return has_children, has_parent


def _label_level(name: str, has_children: set[str], has_parent: set[str]) -> str:
    """Return ``"root"``, ``"mid"``, or ``"leaf"`` for an AudioSet label."""
    if name not in has_parent:
        return "root"
    if name in has_children:
        return "mid"
    return "leaf"
_CHUNK_SECONDS = 10
_STEP_SECONDS = 5
_TOP_N = 5
_MIN_SCORE = 0.05

# AST uses the PyTorch implementation from transformers. If TensorFlow is
# installed in the same environment, transformers may still probe/import TF
# modules during startup, which is a bad fit on macOS when torch is also used.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")


class AstBackend(AiBackend):
    """Wraps the Audio Spectrogram Transformer for soundscape classification.

    Runs a sliding window (10 s chunks, 50 % overlap) over the full WAV.
    Uses Apple MPS (GPU) when available, falls back to CPU.
    """

    name = "AST"
    color = (80, 140, 220, 35)
    text_color = "#6aa0e0"

    def __init__(self) -> None:
        self.options = {}
        try:
            import torch  # noqa: PLC0415
            self._device_label = "MPS (GPU)" if torch.backends.mps.is_available() else "CPU"
        except ImportError:
            self._device_label = "CPU"

    @property
    def device_label(self) -> str:
        return self._device_label

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        """Run AST with a sliding window over the full WAV file.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Unused; present for interface compatibility.

        Returns:
            List of detection dicts (label, score, start_time, end_time)
            sorted by start_time.
        """
        import numpy as np  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415
        import torch  # noqa: PLC0415
        from transformers import ASTForAudioClassification, AutoFeatureExtractor  # noqa: PLC0415

        def _load(cls, **kwargs):
            try:
                return cls.from_pretrained(_MODEL_ID, local_files_only=True, **kwargs)
            except Exception:
                return cls.from_pretrained(_MODEL_ID, **kwargs)

        extractor = _load(AutoFeatureExtractor)
        model = _load(ASTForAudioClassification)
        model.eval()

        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        model = model.to(device)
        step_seconds = max(1, int(self.options.get("step_seconds", _STEP_SECONDS)))
        top_n = max(1, int(self.options.get("top_n", _TOP_N)))
        min_score = float(self.options.get("min_score", _MIN_SCORE))

        audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        target_sr = extractor.sampling_rate
        if sr != target_sr:
            import librosa  # noqa: PLC0415
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        chunk_samples = sr * _CHUNK_SECONDS
        step_samples = sr * step_seconds
        has_children, has_parent = _load_ontology()
        results = []

        for start in range(0, len(audio), step_samples):
            chunk = audio[start: start + chunk_samples]
            if len(chunk) == 0:
                break
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

            inputs = extractor(chunk, sampling_rate=sr, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = model(**inputs).logits[0]

            scores = torch.sigmoid(logits).cpu().numpy()
            start_s = start / sr
            end_s = min((start + chunk_samples) / sr, len(audio) / sr)

            for idx in scores.argsort()[::-1][:top_n]:
                score = float(scores[idx])
                if score < min_score:
                    break
                label = model.config.id2label[idx]
                results.append({
                    "label": label,
                    "score": score,
                    "start_time": start_s,
                    "end_time": end_s,
                    "level": _label_level(label, has_children, has_parent),
                })

        return sorted(results, key=lambda x: x["start_time"])
