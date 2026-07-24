"""Confirms UI modules resolve resource files via app_config, not ad-hoc paths.

Regression guard for the Fase-7 bug where dialog_manager.py/components.py
derived background.png's path from their own __file__ location, which broke
once those modules moved deeper into ui/ and ui/dialogs/ while the image
stayed at the old src/my_app/ root.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "my_app"


def _source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _uses_get_resource_path(source: str) -> bool:
    tree = ast.parse(source)
    return any(
        isinstance(node, ast.Attribute) and node.attr == "get_resource_path"
        for node in ast.walk(tree)
    )


def test_dialog_manager_uses_central_resource_helper():
    source = _source("src/my_app/ui/dialogs/dialog_manager.py")
    assert _uses_get_resource_path(source)
    assert "dirname(os.path.abspath(__file__))" not in source


def test_components_uses_central_resource_helper():
    source = _source("src/my_app/ui/components.py")
    assert _uses_get_resource_path(source)
    assert "dirname(os.path.abspath(__file__))" not in source


def test_refactor_stays_on_pyqt5():
    """The Field Lab Dark branch must not mix in a Qt binding migration."""
    forbidden_imports = ("PyQt6", "PySide6")
    offenders = []

    for path in SOURCE_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            if forbidden in source:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {forbidden}")

    assert offenders == []
