"""Fake AiBackend implementation for registry/dialog tests.

Fulfils the same contract as real backends (my_app.ai.backends.base.AiBackend)
without any model, subprocess, or heavy import — safe to instantiate and call
analyze() directly in unit tests. Detections and errors are fully
configurable per instance.
"""

from __future__ import annotations

from my_app.ai.backends.base import AiBackend


class FakeAiBackend(AiBackend):
    """Configurable in-memory stand-in for a real AI backend.

    Args:
        name: Display name shown in the UI (matches AiBackend.name).
        color: Waveform overlay region brush RGBA tuple.
        text_color: Hex colour string for waveform text labels.
        detections: Detection dicts returned by analyze(). Defaults to an
            empty list. A callable is invoked with (wav_path, metadata) so
            tests can vary output per call.
        error: Exception instance to raise from analyze() instead of
            returning detections, e.g. to test error handling paths.
        device_label: Value returned by the device_label property.
        debug_output: Value returned by the debug_output property.
    """

    def __init__(
        self,
        name: str = "Fake",
        color: tuple[int, int, int, int] = (128, 128, 128, 45),
        text_color: str = "#808080",
        detections: list[dict] | None = None,
        error: Exception | None = None,
        device_label: str = "CPU",
        debug_output=None,
    ) -> None:
        self.name = name
        self.color = color
        self.text_color = text_color
        self.options: dict = {}
        self._detections = detections if detections is not None else []
        self._error = error
        self._device_label = device_label
        self._debug_output = debug_output
        self.calls: list[tuple[str, dict]] = []

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        self.calls.append((wav_path, metadata))
        if self._error is not None:
            raise self._error
        if callable(self._detections):
            return self._detections(wav_path, metadata)
        return list(self._detections)

    @property
    def device_label(self) -> str:
        return self._device_label

    @property
    def debug_output(self):
        return self._debug_output
