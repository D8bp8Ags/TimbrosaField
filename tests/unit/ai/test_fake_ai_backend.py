"""Unit tests for tests.fakes.fake_ai_backend.FakeAiBackend.

Confirms the fake fulfils the real AiBackend contract and that its
configurable detections/error-injection behave as documented, so it is
safe to use in future registry/dialog tests without touching production
backend code.
"""

from __future__ import annotations

import pytest

from my_app.ai.backends.base import AiBackend
from tests.fakes.fake_ai_backend import FakeAiBackend


def test_fake_backend_satisfies_aibackend_contract():
    backend = FakeAiBackend()
    assert isinstance(backend, AiBackend)
    assert backend.name and backend.color and backend.text_color
    assert backend.device_label == "CPU"
    assert backend.debug_output is None


def test_fake_backend_returns_configured_detections():
    detections = [{"label": "Owl", "score": 0.9, "start_time": 0.0, "end_time": 1.0}]
    backend = FakeAiBackend(detections=detections)
    result = backend.analyze("/tmp/fake.wav", {})
    assert result == detections
    assert backend.calls == [("/tmp/fake.wav", {})]


def test_fake_backend_detections_callable_receives_call_args():
    def _make_detections(wav_path, metadata):
        return [{"label": wav_path, "score": metadata.get("score", 0.0)}]

    backend = FakeAiBackend(detections=_make_detections)
    result = backend.analyze("/tmp/other.wav", {"score": 0.5})
    assert result == [{"label": "/tmp/other.wav", "score": 0.5}]


def test_fake_backend_raises_configured_error():
    backend = FakeAiBackend(error=RuntimeError("simulated failure"))
    with pytest.raises(RuntimeError, match="simulated failure"):
        backend.analyze("/tmp/fake.wav", {})


def test_fake_backend_defaults_to_empty_detections():
    backend = FakeAiBackend()
    assert backend.analyze("/tmp/fake.wav", {}) == []


def test_fake_backend_custom_metadata_and_capabilities():
    backend = FakeAiBackend(
        name="FakeBird",
        color=(1, 2, 3, 4),
        text_color="#010203",
        device_label="GPU",
        debug_output={"raw": True},
    )
    assert backend.name == "FakeBird"
    assert backend.color == (1, 2, 3, 4)
    assert backend.text_color == "#010203"
    assert backend.device_label == "GPU"
    assert backend.debug_output == {"raw": True}
