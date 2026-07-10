"""Typed contracts shared by the AI registry, backends, and UI.

Re-exports the existing AiBackend interface (unchanged, still defined in
ai_backends.base) and adds a TypedDict describing the detection dict shape
backends already return. Detection remains a plain dict at runtime — this
is a documented, checkable shape, not a new runtime type — so the existing
sidecar JSON format and UI dict-based consumption are unaffected.
"""

from __future__ import annotations

from typing import TypedDict

from ai_backends.base import AiBackend

__all__ = ["AiBackend", "Detection"]


class Detection(TypedDict, total=False):
    """Shape of a single detection dict returned by AiBackend.analyze().

    Required at the contract boundary: label, score, start_time, end_time.
    All other keys are optional and used by specific backends/UI features.
    """

    label: str
    score: float
    start_time: float
    end_time: float
    detail: str
    tag: str
    tag_key: str
    scientific_name: str
    english_name: str
    dutch_name: str
