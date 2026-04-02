"""Base interface for AI analysis backends.

Copyright (c) TimbrosaField — all rights reserved.

Every backend must subclass :class:`AiBackend` and implement :meth:`analyze`.
The rest of the application (dialog, waveform overlay) only depends on this
interface, not on any specific model or library.
"""

from abc import ABC, abstractmethod


class AiBackend(ABC):
    """Contract that every AI analysis backend must fulfil.

    Attributes:
        name: Human-readable source name shown in the UI (e.g. ``"BirdNET"``).
        color: RGBA tuple used for the waveform overlay region brush.
        text_color: Hex colour string used for text labels on the waveform.
    """

    name: str
    color: tuple[int, int, int, int]
    text_color: str
    options: dict = {}

    @abstractmethod
    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        """Run analysis on a WAV file and return detections.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Dict as returned by ``wav_analyze()``.

        Returns:
            List of detection dicts.  Each dict contains at minimum:

            - ``label`` (str): primary human-readable label.
            - ``score`` (float 0–1): confidence.
            - ``start_time`` (float): detection start in seconds.
            - ``end_time`` (float): detection end in seconds.

            Backends may add optional keys recognised by the dialog:

            - ``detail`` (str): optional backend/context note shown in the
              Detections table (e.g. ``"Geo filter applied"``).
            - ``tag`` (str): preferred tag value written to ICMT; falls back
              to ``label`` when absent.
            - ``tag_key`` (str): deduplication key for the Tags tab; falls
              back to ``label`` when absent.

        Note:
            This method runs on a background ``QThread``; never touch Qt
            widgets here.
        """

    @property
    def device_label(self) -> str:
        """Human-readable compute device used by this backend (e.g. ``"CPU"``).

        Override in subclasses that support GPU acceleration.
        """
        return "CPU"

    @property
    def debug_output(self):
        """Optional JSON-serialisable backend payload for inspection/debugging."""
        return None
