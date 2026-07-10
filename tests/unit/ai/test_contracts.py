"""Unit test for Fase 6/7: typed Detection contract in ai/contracts.py.

Detection is a TypedDict, so it imposes no runtime type — this test only
confirms the contract's declared fields match what backends actually
produce (see ai/backends/*.py), and that AiBackend is importable via the
contracts module and matches the canonical ai.backends.base definition.
"""

from __future__ import annotations

from my_app.ai.contracts import AiBackend, Detection


def test_detection_declares_fields_used_by_existing_backends():
    fields = set(Detection.__annotations__)
    required_by_all_backends = {"label", "score", "start_time", "end_time"}
    optional_used_by_some_backends = {
        "detail",
        "tag",
        "tag_key",
        "scientific_name",
        "english_name",
        "dutch_name",
    }
    assert required_by_all_backends <= fields
    assert optional_used_by_some_backends <= fields


def test_detection_is_structurally_compatible_with_plain_dict():
    detection: Detection = {
        "label": "Merel",
        "score": 0.87,
        "start_time": 1.0,
        "end_time": 2.5,
    }
    assert isinstance(detection, dict)
    assert detection["label"] == "Merel"


def test_aibackend_still_importable_via_contracts_module():
    from my_app.ai.backends.base import AiBackend as OriginalAiBackend

    assert AiBackend is OriginalAiBackend
