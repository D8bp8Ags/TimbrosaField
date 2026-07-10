"""Targeted tests for the read/write split between model discovery and
model installation.

Covers: get_models_install_root() never returns a legacy/cache location,
get_models_search_roots()/find_existing_model_path() find models across all
backward-compatible locations, re-installing a model that already exists in
a legacy root writes to the new install root instead of back into the
legacy root, removing a model only deletes the concrete found path, and
TIMBROSA_MODELS_ROOT remains both read and write priority 1.
"""

from __future__ import annotations

import pytest

import my_app.ai.model_manager as manager


@pytest.fixture
def clean_models_root_env(monkeypatch):
    monkeypatch.delenv("TIMBROSA_MODELS_ROOT", raising=False)


@pytest.fixture
def model_roots(tmp_path, monkeypatch, clean_models_root_env):
    """Isolate install root / old cache root / legacy root to tmp_path, with
    a single fake model definition so relative_dir is predictable."""
    default_root = tmp_path / "documents" / "models"
    old_cache_root = tmp_path / "old_cache" / "models"
    legacy_root = tmp_path / "legacy" / "models"

    monkeypatch.setattr("my_app.app_config.get_models_dir", lambda: default_root)
    monkeypatch.setattr("my_app.app_config.get_cache_dir", lambda: old_cache_root.parent)
    monkeypatch.setattr(manager, "_legacy_models_root", lambda: legacy_root)

    return {"default": default_root, "old_cache": old_cache_root, "legacy": legacy_root}


# ---------------------------------------------------------------------------
# get_models_install_root(): write-only root, never legacy/cache
# ---------------------------------------------------------------------------


def test_install_root_env_override_highest_priority(monkeypatch, tmp_path):
    override = tmp_path / "override_root"
    monkeypatch.setenv("TIMBROSA_MODELS_ROOT", str(override))
    assert manager.get_models_install_root() == override.resolve()


def test_install_root_defaults_to_documents_even_when_legacy_has_data(
    monkeypatch, tmp_path, model_roots
):
    """The install root must never be the legacy root or old cache root,
    even if those are populated — this is the exact bug being fixed."""
    (model_roots["legacy"] / "birdnet").mkdir(parents=True)
    (model_roots["legacy"] / "birdnet" / "model-fp32.tflite").write_bytes(b"fake")
    (model_roots["old_cache"]).mkdir(parents=True)
    (model_roots["old_cache"] / "marker").write_text("x", encoding="utf-8")

    assert manager.get_models_install_root() == model_roots["default"]


# ---------------------------------------------------------------------------
# get_models_search_roots() / find_existing_model_path(): read-only search
# ---------------------------------------------------------------------------


def test_search_roots_env_override_is_sole_root(monkeypatch, tmp_path):
    override = tmp_path / "override_root"
    monkeypatch.setenv("TIMBROSA_MODELS_ROOT", str(override))
    assert manager.get_models_search_roots() == (override.resolve(),)


def test_search_roots_priority_order(model_roots):
    roots = manager.get_models_search_roots()
    assert roots == (
        model_roots["default"],
        model_roots["old_cache"],
        model_roots["legacy"],
    )


def _patch_single_model_definition(monkeypatch, model_id="fake_model", relative_dir="fake/fake_model"):
    definition = manager.ModelDefinition(
        model_id=model_id,
        display_name="Fake Model",
        backend="Fake",
        version="1",
        relative_dir=relative_dir,
        source="test",
        license="test",
        required_files=("model.bin",),
    )
    monkeypatch.setitem(manager._MODEL_BY_ID, model_id, definition)
    return definition


def test_find_existing_model_path_returns_none_when_absent(monkeypatch, model_roots):
    definition = _patch_single_model_definition(monkeypatch)
    assert manager.find_existing_model_path(definition.model_id) is None


def test_find_existing_model_path_finds_legacy_model(monkeypatch, model_roots):
    definition = _patch_single_model_definition(monkeypatch)
    legacy_model_dir = model_roots["legacy"] / definition.relative_dir
    legacy_model_dir.mkdir(parents=True)

    assert manager.find_existing_model_path(definition.model_id) == legacy_model_dir


def test_find_existing_model_path_prefers_install_root_over_legacy(monkeypatch, model_roots):
    definition = _patch_single_model_definition(monkeypatch)
    (model_roots["legacy"] / definition.relative_dir).mkdir(parents=True)
    install_model_dir = model_roots["default"] / definition.relative_dir
    install_model_dir.mkdir(parents=True)

    assert manager.find_existing_model_path(definition.model_id) == install_model_dir


# ---------------------------------------------------------------------------
# Scenario from the bug report: model A in legacy, model B missing.
# Installing B must go to Documents, not legacy — and removing + reinstalling
# A must also land it in Documents.
# ---------------------------------------------------------------------------


def test_model_b_missing_installs_to_documents_not_legacy(monkeypatch, model_roots):
    """Model A exists in legacy (so get_models_root() used to resolve to the
    legacy root); Model B does not exist anywhere. A fresh install target
    for B must be under Documents, unaffected by A's location."""
    model_a = _patch_single_model_definition(monkeypatch, "model_a", "fake/model_a")
    model_b = _patch_single_model_definition(monkeypatch, "model_b", "fake/model_b")
    (model_roots["legacy"] / model_a.relative_dir).mkdir(parents=True)

    assert manager.find_existing_model_path(model_b.model_id) is None
    assert manager.get_install_target_dir(model_b.model_id) == (
        model_roots["default"] / model_b.relative_dir
    )


def test_remove_then_reinstall_lands_in_documents(monkeypatch, model_roots):
    definition = _patch_single_model_definition(monkeypatch, "model_a", "fake/model_a")
    legacy_model_dir = model_roots["legacy"] / definition.relative_dir
    legacy_model_dir.mkdir(parents=True)
    (legacy_model_dir / "model.bin").write_bytes(b"fake")

    # Found in legacy before removal.
    assert manager.find_existing_model_path(definition.model_id) == legacy_model_dir

    manager.remove_model(definition.model_id)

    assert not legacy_model_dir.exists()
    assert manager.find_existing_model_path(definition.model_id) is None
    # A fresh install after removal targets Documents, not legacy.
    assert manager.get_install_target_dir(definition.model_id) == (
        model_roots["default"] / definition.relative_dir
    )


def test_remove_model_deletes_only_the_found_path_not_other_models(monkeypatch, model_roots):
    """remove_model() must delete only the concrete model directory, never
    sibling models or the whole legacy root."""
    model_a = _patch_single_model_definition(monkeypatch, "model_a", "fake/model_a")
    model_b = _patch_single_model_definition(monkeypatch, "model_b", "fake/model_b")
    legacy_a = model_roots["legacy"] / model_a.relative_dir
    legacy_b = model_roots["legacy"] / model_b.relative_dir
    legacy_a.mkdir(parents=True)
    legacy_b.mkdir(parents=True)

    manager.remove_model(model_a.model_id)

    assert not legacy_a.exists()
    assert legacy_b.exists()
    assert model_roots["legacy"].exists()


def test_existing_legacy_models_remain_readable(monkeypatch, model_roots):
    """A model only ever present in the legacy root stays discoverable
    without being copied or migrated anywhere."""
    definition = _patch_single_model_definition(monkeypatch)
    legacy_model_dir = model_roots["legacy"] / definition.relative_dir
    legacy_model_dir.mkdir(parents=True)
    (legacy_model_dir / "model.bin").write_bytes(b"fake")

    found = manager.find_existing_model_path(definition.model_id)
    assert found == legacy_model_dir
    assert (found / "model.bin").exists()
    # No copy created anywhere else.
    assert not model_roots["default"].exists()
    assert not model_roots["old_cache"].exists()
