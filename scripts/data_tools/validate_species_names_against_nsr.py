#!/usr/bin/env python3
"""Compare local species-name mapping against a Dutch Species Register export.

Expected input: a CSV/TSV export containing at least scientific and Dutch name
columns from Nederlands Soortenregister.

Requirements:
    - src/ on the Python path, the same way python -m my_app.main needs it
      (e.g. PYTHONPATH=src, or an editable/normal install of the project).

Start command (from the repository root):
    PYTHONPATH=src python -m scripts.data_tools.validate_species_names_against_nsr <reference_file>
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import zipfile

from my_app.species_names import SPECIES_TO_DUTCH


SCI_KEYS = {
    "wetenschappelijke naam",
    "scientific name",
    "scientificname",
}

DUTCH_KEYS = {
    "nederlandse voorkeursnaam",
    "nederlandse naam",
    "dutch name",
    "vernacularname",
}


def normalise_key(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


def detect_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def load_reference_from_text(text: str) -> dict[str, str]:
    dialect = detect_dialect(text[:4000])
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise RuntimeError("Reference file has no header row.")

    key_map = {normalise_key(name): name for name in reader.fieldnames}
    sci_col = next((key_map[k] for k in SCI_KEYS if k in key_map), None)
    dutch_col = next((key_map[k] for k in DUTCH_KEYS if k in key_map), None)
    if not sci_col or not dutch_col:
        raise RuntimeError(
            "Could not find scientific/Dutch name columns in reference export."
        )

    reference: dict[str, str] = {}
    for row in reader:
        scientific_name = (row.get(sci_col) or "").strip()
        dutch_name = (row.get(dutch_col) or "").strip()
        if scientific_name and dutch_name:
            reference[scientific_name] = dutch_name
    return reference


def load_reference(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".zip":
        return load_reference_from_nsr_dwca(path)

    text = path.read_text(encoding="utf-8-sig")
    return load_reference_from_text(text)


def load_reference_from_nsr_dwca(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as zf:
        with zf.open("Taxa.txt") as f:
            taxa_reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8-sig", newline=""),
                delimiter=",",
            )
            accepted_taxa: dict[str, str] = {}
            for row in taxa_reader:
                taxon_id = (row.get("taxonID") or "").strip()
                scientific_name = (row.get("scientificName") or "").strip()
                taxonomic_status = (row.get("taxonomicStatus") or "").strip().lower()
                if not taxon_id or not scientific_name or taxonomic_status != "accepted name":
                    continue
                accepted_taxa[taxon_id] = scientific_name.split(" (", 1)[0].strip()

        with zf.open("Vernacular_Names.txt") as f:
            names_reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8-sig", newline=""),
                delimiter=",",
            )
            reference: dict[str, str] = {}
            for row in names_reader:
                if (row.get("language") or "").strip().lower() != "dutch":
                    continue
                if (row.get("isPreferredName") or "").strip().lower() != "true":
                    continue
                taxon_id = (row.get("taxonID") or "").strip()
                scientific_name = accepted_taxa.get(taxon_id)
                dutch_name = (row.get("vernacularName") or "").strip()
                if scientific_name and dutch_name:
                    reference[scientific_name] = dutch_name
    return reference


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate local species_names.py against a Dutch Species Register export."
    )
    parser.add_argument("reference_file", help="CSV/TSV export from Nederlands Soortenregister")
    args = parser.parse_args()

    reference = load_reference(Path(args.reference_file).expanduser())

    mismatches = []
    missing_in_reference = []
    for scientific_name, local_dutch in sorted(SPECIES_TO_DUTCH.items()):
        ref_dutch = reference.get(scientific_name)
        if not ref_dutch:
            missing_in_reference.append(scientific_name)
            continue
        if ref_dutch != local_dutch:
            mismatches.append((scientific_name, local_dutch, ref_dutch))

    if not mismatches and not missing_in_reference:
        print("No differences found.")
        return 0

    if mismatches:
        print("Mismatched Dutch names:\n")
        for scientific_name, local_dutch, ref_dutch in mismatches:
            print(f"{scientific_name}\n  local: {local_dutch}\n  nsr:   {ref_dutch}\n")

    if missing_in_reference:
        print("Not found in reference export:\n")
        for scientific_name in missing_in_reference:
            print(scientific_name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
