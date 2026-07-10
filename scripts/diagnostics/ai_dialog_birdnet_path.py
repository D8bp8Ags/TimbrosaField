#!/usr/bin/env python3
"""Manual diagnostic: reproduce the app's BirdNET analysis path with minimal UI setup.

Purpose:
    Exercises the real ``AiAnalysisDialog`` BirdNET-only analysis flow against
    a given WAV file, printing step-by-step progress. Useful for reproducing
    BirdNET-specific analysis issues without running the full application.

Requirements:
    - A working PyQt5 installation.
    - The BirdNET model already installed locally (this script does not
      download models).
    - A real WAV file to analyze.
    - src/ on the Python path, the same way python -m my_app.main needs it
      (e.g. PYTHONPATH=src, or an editable/normal install of the project).

Start command (from the repository root):
    PYTHONPATH=src python3 -m scripts.diagnostics.ai_dialog_birdnet_path /path/to/file.wav

Not collected by pytest: this is a manual, interactive/CLI diagnostic tool,
not an automated regression test.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test the AI dialog BirdNET path inside a minimal Qt app."
    )
    parser.add_argument("wav", help="Path to WAV file")
    args = parser.parse_args()

    wav_path = str(Path(args.wav).expanduser().resolve())

    print("[STEP] import Qt + app modules", flush=True)
    from PyQt5.QtWidgets import QApplication  # noqa: PLC0415
    from my_app.wav.analyzer import wav_analyze  # noqa: PLC0415
    from my_app.ai.ui.analysis_dialog import AiAnalysisDialog  # noqa: PLC0415
    print("[OK] import Qt + app modules", flush=True)

    print("[STEP] create QApplication", flush=True)
    app = QApplication.instance() or QApplication([])
    print(f"[OK] create QApplication: {type(app).__name__}", flush=True)

    print("[STEP] analyze wav metadata", flush=True)
    metadata = wav_analyze(wav_path)
    print(f"[OK] analyze wav metadata: keys={sorted(metadata.keys())}", flush=True)

    print("[STEP] create AiAnalysisDialog", flush=True)
    dialog = AiAnalysisDialog(wav_path, metadata, parent=None)
    print("[OK] create AiAnalysisDialog", flush=True)

    print("[STEP] force BirdNET-only selection", flush=True)
    for checkbox, backend_name in dialog._backend_checkboxes:
        checkbox.setChecked(backend_name == "BirdNET")
    print("[OK] force BirdNET-only selection", flush=True)

    print("[STEP] start analysis", flush=True)
    dialog.start_analysis()
    print("[OK] start analysis", flush=True)

    worker = dialog._worker
    if worker is None:
        print("[INFO] no worker created; cache may have been used", flush=True)
        return 0

    print("[STEP] wait for worker", flush=True)
    worker.wait()
    print("[DONE] worker finished", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
