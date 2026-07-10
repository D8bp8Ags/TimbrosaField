#!/usr/bin/env python3
"""Manual diagnostic: run the real modal AI dialog flow with BirdNET-only selection.

Purpose:
    Opens the actual modal ``AiAnalysisDialog`` (as shown to users) with only
    the BirdNET backend selected, auto-closing after a timeout. Useful for
    visually/manually verifying the modal dialog flow end-to-end.

Requirements:
    - A working PyQt5 installation with a display (or QT_QPA_PLATFORM=offscreen).
    - The BirdNET model already installed locally (this script does not
      download models).
    - A real WAV file to analyze.

Start command:
    python3 scripts/diagnostics/ai_dialog_modal_birdnet.py /path/to/file.wav

Not collected by pytest: this is a manual, interactive/CLI diagnostic tool,
not an automated regression test.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src" / "my_app"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test the modal AI dialog flow with BirdNET only."
    )
    parser.add_argument("wav", help="Path to WAV file")
    args = parser.parse_args()

    wav_path = str(Path(args.wav).expanduser().resolve())

    print("[STEP] import Qt + app modules", flush=True)
    from PyQt5.QtCore import QTimer  # noqa: PLC0415
    from PyQt5.QtWidgets import QApplication  # noqa: PLC0415
    from wav_analyzer import wav_analyze  # noqa: PLC0415
    from ai_analyzer import AiAnalysisDialog  # noqa: PLC0415
    print("[OK] import Qt + app modules", flush=True)

    print("[STEP] create QApplication", flush=True)
    app = QApplication.instance() or QApplication([])
    print(f"[OK] create QApplication: {type(app).__name__}", flush=True)

    print("[STEP] analyze wav metadata", flush=True)
    metadata = wav_analyze(wav_path)
    print("[OK] analyze wav metadata", flush=True)

    print("[STEP] create dialog", flush=True)
    dialog = AiAnalysisDialog(wav_path, metadata, parent=None)
    print("[OK] create dialog", flush=True)

    print("[STEP] force BirdNET-only selection", flush=True)
    for checkbox, backend_name in dialog._backend_checkboxes:
        checkbox.setChecked(backend_name == "BirdNET")
    print("[OK] force BirdNET-only selection", flush=True)

    print("[STEP] prepare analysis", flush=True)
    dialog.prepare_analysis()
    print("[OK] prepare analysis", flush=True)

    print("[STEP] schedule start + auto-close", flush=True)
    QTimer.singleShot(0, dialog.start_analysis)
    QTimer.singleShot(15000, dialog.accept)
    print("[OK] schedule start + auto-close", flush=True)

    print("[STEP] exec dialog", flush=True)
    dialog.exec_()
    print("[DONE] dialog closed cleanly", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
