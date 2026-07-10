"""Targeted tests for Fase 8 model-root fallback/migration behavior.

Covers: TIMBROSA_MODELS_ROOT still has highest priority, new empty cache
dir falls back to a populated legacy src/my_app/models dir, and an empty
new cache dir with no legacy data is used (no download, no copy).
"""

from __future__ import annotations

import pytest

import my_app.ai.model_manager as manager


@pytest.fixture
def clean_models_root_env(monkeypatch):
    monkeypatch.delenv("TIMBROSA_MODELS_ROOT", raising=False)


def test_env_override_still_highest_priority(monkeypatch, tmp_path):
    override = tmp_path / "override_root"
    monkeypatch.setenv("TIMBROSA_MODELS_ROOT", str(override))
    assert manager.get_models_root() == override.resolve()


def test_falls_back_to_legacy_root_when_new_cache_empty(
    monkeypatch, tmp_path, clean_models_root_env
):
    new_cache_root = tmp_path / "new_cache" / "models"
    legacy_root = tmp_path / "legacy" / "models"
    (legacy_root / "birdnet").mkdir(parents=True)
    (legacy_root / "birdnet" / "model-fp32.tflite").write_bytes(b"fake")

    monkeypatch.setattr(
        "my_app.app_config.get_cache_dir", lambda: new_cache_root.parent
    )
    monkeypatch.setattr(manager, "_legacy_models_root", lambda: legacy_root)

    assert manager.get_models_root() == legacy_root
    # Legacy data must not be copied or deleted by merely resolving the root.
    assert (legacy_root / "birdnet" / "model-fp32.tflite").exists()
    assert not new_cache_root.exists()


def test_uses_new_cache_root_when_populated(monkeypatch, tmp_path, clean_models_root_env):
    new_cache_root = tmp_path / "new_cache" / "models"
    new_cache_root.mkdir(parents=True)
    (new_cache_root / "marker").write_text("x", encoding="utf-8")
    legacy_root = tmp_path / "legacy" / "models"
    (legacy_root / "birdnet").mkdir(parents=True)

    monkeypatch.setattr(
        "my_app.app_config.get_cache_dir", lambda: new_cache_root.parent
    )
    monkeypatch.setattr(manager, "_legacy_models_root", lambda: legacy_root)

    assert manager.get_models_root() == new_cache_root


def test_no_data_anywhere_returns_new_empty_cache_root(
    monkeypatch, tmp_path, clean_models_root_env
):
    new_cache_root = tmp_path / "new_cache" / "models"
    legacy_root = tmp_path / "legacy" / "models"  # does not exist

    monkeypatch.setattr(
        "my_app.app_config.get_cache_dir", lambda: new_cache_root.parent
    )
    monkeypatch.setattr(manager, "_legacy_models_root", lambda: legacy_root)

    result = manager.get_models_root()
    assert result == new_cache_root
    # No download, no directory creation just from resolving the root.
    assert not result.exists()
