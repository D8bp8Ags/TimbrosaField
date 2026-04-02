#!/usr/bin/env python3
"""Minimal runtime test for the official BirdNET Python package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Test BirdNET import/load/predict runtime.")
    parser.add_argument("--wav", help="Optional WAV file to run a real prediction on.")
    parser.add_argument(
        "--geo",
        action="store_true",
        help="Also load the geo model and run a minimal geo prediction.",
    )
    args = parser.parse_args()

    print("[STEP] import birdnet", flush=True)
    import birdnet  # noqa: PLC0415
    print("[OK] import birdnet", flush=True)

    print("[STEP] load acoustic model", flush=True)
    acoustic = birdnet.load("acoustic", "2.4", "tf")
    print(f"[OK] load acoustic model: {type(acoustic).__name__}", flush=True)

    if args.geo:
        print("[STEP] load geo model", flush=True)
        geo = birdnet.load("geo", "2.4", "tf")
        print(f"[OK] load geo model: {type(geo).__name__}", flush=True)

        print("[STEP] geo predict", flush=True)
        geo_result = geo.predict(52.0, 5.0, week=20)
        print(f"[OK] geo predict: {type(geo_result).__name__}", flush=True)

    if args.wav:
        wav_path = Path(args.wav).expanduser().resolve()
        print(f"[STEP] acoustic predict on {wav_path}", flush=True)
        result = acoustic.predict(str(wav_path))
        print(f"[OK] acoustic predict: {type(result).__name__}", flush=True)

        if hasattr(result, "to_structured_array"):
            rows = result.to_structured_array()
            print(f"[INFO] rows={len(rows)}", flush=True)
        elif hasattr(result, "to_dataframe"):
            frame = result.to_dataframe()
            print(f"[INFO] rows={len(frame)}", flush=True)
        else:
            print("[INFO] result has no recognised row export helper", flush=True)

    print("[DONE] BirdNET runtime test completed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
