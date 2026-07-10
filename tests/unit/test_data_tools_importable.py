"""Confirms the species-name data tools are importable via their new module
path (scripts/data_tools/) with no manual sys.path manipulation.
"""

from __future__ import annotations

import importlib


def test_list_missing_species_names_importable():
    module = importlib.import_module(
        "scripts.data_tools.list_missing_species_names"
    )
    assert hasattr(module, "main")
    assert hasattr(module, "SPECIES_TO_DUTCH")


def test_validate_species_names_against_nsr_importable():
    module = importlib.import_module(
        "scripts.data_tools.validate_species_names_against_nsr"
    )
    assert hasattr(module, "main")
    assert hasattr(module, "SPECIES_TO_DUTCH")
