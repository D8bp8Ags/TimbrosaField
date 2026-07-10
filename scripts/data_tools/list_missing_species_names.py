#!/usr/bin/env python3
"""Report scientific names seen in AI sidecars that lack a Dutch mapping.

Requirements:
    - src/ on the Python path, the same way python -m my_app.main needs it
      (e.g. PYTHONPATH=src, or an editable/normal install of the project).

Start command (from the repository root):
    PYTHONPATH=src python -m scripts.data_tools.list_missing_species_names [paths...]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from my_app.species_names import SPECIES_TO_DUTCH


def iter_sidecars(paths: list[Path]) -> list[Path]:
    sidecars: list[Path] = []
    for path in paths:
        if path.is_file() and path.name.endswith("_ai.json"):
            sidecars.append(path)
            continue
        if path.is_dir():
            sidecars.extend(sorted(path.rglob("*_ai.json")))
    return sidecars


def collect_missing(paths: list[Path]) -> tuple[Counter, dict[str, set[str]]]:
    counts: Counter = Counter()
    backends: dict[str, set[str]] = defaultdict(set)

    for sidecar in iter_sidecars(paths):
        try:
            data = json.loads(sidecar.read_text())
        except Exception:
            continue

        for layer in data.get("layers", []):
            backend_name = layer.get("name", "Unknown")
            for det in layer.get("detections", []):
                scientific_name = (det.get("scientific_name") or "").strip()
                if not scientific_name:
                    continue
                if scientific_name in SPECIES_TO_DUTCH:
                    continue
                counts[scientific_name] += 1
                backends[scientific_name].add(str(backend_name))

    return counts, backends


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List scientific names from AI sidecars that have no Dutch mapping."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan recursively for *_ai.json sidecars.",
    )
    args = parser.parse_args()

    counts, backends = collect_missing([Path(p).expanduser() for p in args.paths])
    if not counts:
        print("No missing species-name mappings found.")
        return 0

    print("Missing species-name mappings:\n")
    for scientific_name in sorted(counts):
        used_by = ", ".join(sorted(backends[scientific_name]))
        print(f"{scientific_name}\tcount={counts[scientific_name]}\tbackends={used_by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
