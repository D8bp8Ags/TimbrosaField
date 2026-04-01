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

from .base import AiBackend

_MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.448"
_CHUNK_SECONDS = 10
_STEP_SECONDS = 5
_TOP_N = 5
_MIN_SCORE = 0.05


class AstBackend(AiBackend):
    """Wraps the Audio Spectrogram Transformer for soundscape classification.

    Runs a sliding window (10 s chunks, 50 % overlap) over the full WAV.
    Uses Apple MPS (GPU) when available, falls back to CPU.
    """

    name = "AST"
    color = (80, 140, 220, 35)
    text_color = "#6aa0e0"

    def __init__(self) -> None:
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

        extractor = AutoFeatureExtractor.from_pretrained(_MODEL_ID)
        model = ASTForAudioClassification.from_pretrained(_MODEL_ID)
        model.eval()

        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self._device_label = "MPS (GPU)" if device.type == "mps" else "CPU"
        model = model.to(device)

        audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        target_sr = extractor.sampling_rate
        if sr != target_sr:
            import librosa  # noqa: PLC0415
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        chunk_samples = sr * _CHUNK_SECONDS
        step_samples = sr * _STEP_SECONDS
        results = []

        for start in range(0, len(audio), step_samples):
            chunk = audio[start: start + chunk_samples]
            if len(chunk) < sr * 2:
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

            for idx in scores.argsort()[::-1][:_TOP_N]:
                score = float(scores[idx])
                if score < _MIN_SCORE:
                    break
                results.append({
                    "label": model.config.id2label[idx],
                    "score": score,
                    "start_time": start_s,
                    "end_time": end_s,
                })

        return sorted(results, key=lambda x: x["start_time"])
