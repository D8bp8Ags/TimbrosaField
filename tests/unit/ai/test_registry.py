"""Unit tests for ai/registry.py (Fase 6: single AI backend registry).

Confirms the registry is the single source of truth for backend
registration, capabilities, and model-id requirements — no real model
downloads or inference are performed.
"""

from __future__ import annotations

import pytest

from my_app.ai import registry as reg


def test_registry_contains_ast_birdnet_and_perch():
    ids = {r.backend_id for r in reg.all_backends()}
    assert ids == {"ast", "birdnet", "perch"}


@pytest.mark.parametrize("backend_id", ["ast", "birdnet", "perch"])
def test_each_entry_has_valid_factory_reference_and_models(backend_id):
    registration = reg.get_by_id(backend_id)
    assert registration is not None
    assert registration.module_name.startswith("my_app.ai.backends.")
    assert registration.class_name
    assert len(registration.model_ids) >= 1
    assert registration.display_name
    assert registration.dependency_modules


def test_birdnet_has_geo_capability():
    registration = reg.get_by_id("birdnet")
    assert registration.capabilities.supports_geo_filter is True


@pytest.mark.parametrize("backend_id", ["ast", "perch"])
def test_non_birdnet_backends_do_not_have_geo_capability(backend_id):
    registration = reg.get_by_id(backend_id)
    assert registration.capabilities.supports_geo_filter is False


def test_get_by_display_name_matches_get_by_id():
    assert reg.get_by_display_name("BirdNET") is reg.get_by_id("birdnet")
    assert reg.get_by_display_name("AST") is reg.get_by_id("ast")
    assert reg.get_by_display_name("Perch") is reg.get_by_id("perch")


def test_get_by_id_unknown_returns_none():
    assert reg.get_by_id("nonexistent") is None


def test_get_by_display_name_unknown_returns_none():
    assert reg.get_by_display_name("Nonexistent") is None


# ---------------------------------------------------------------------------
# load_backends: backend factory produces the right type
# ---------------------------------------------------------------------------


def test_load_backends_creates_correct_backend_types():
    from my_app.ai.backends.base import AiBackend

    backends = reg.load_backends()
    # At least the backends whose dependencies happen to be installed in
    # this environment will load; all loaded instances must satisfy the
    # AiBackend contract and have a name matching a registry entry.
    for backend in backends:
        assert isinstance(backend, AiBackend)
        assert reg.get_by_display_name(backend.name) is not None


def test_load_backends_filters_by_selected_names():
    all_loaded = reg.load_backends()
    if not all_loaded:
        pytest.skip("no AI backend dependencies installed in this environment")
    only_first = reg.load_backends({all_loaded[0].name})
    assert all(b.name == all_loaded[0].name for b in only_first)


def test_load_backends_skips_unavailable_backend_without_raising(monkeypatch):
    def _raise_import_error(self):
        raise ImportError("simulated missing dependency")

    monkeypatch.setattr(reg.BackendRegistration, "create_backend", _raise_import_error)

    backends = reg.load_backends()

    assert backends == []


def test_missing_python_dependencies_are_reported_per_selected_backend(monkeypatch):
    def _fake_find_spec(module_name):
        if module_name in {"torch", "birdnet"}:
            return None
        return object()

    monkeypatch.setattr(reg.importlib.util, "find_spec", _fake_find_spec)

    missing = reg.missing_python_dependencies_for_backends({"AST", "BirdNET"})

    assert missing == {
        "BirdNET": ("birdnet",),
        "AST": ("torch",),
    }


def test_load_backends_skips_backend_when_dependency_probe_fails(monkeypatch):
    monkeypatch.setattr(reg.importlib.util, "find_spec", lambda _name: None)

    backends = reg.load_backends({"AST"})

    assert backends == []


# ---------------------------------------------------------------------------
# required_model_ids_for_backends: capability-driven geo-filter gating
# ---------------------------------------------------------------------------


def test_required_model_ids_birdnet_includes_geo_by_default():
    assert reg.required_model_ids_for_backends({"BirdNET"}) == [
        "birdnet_acoustic",
        "birdnet_geo",
    ]


def test_required_model_ids_birdnet_excludes_geo_when_disabled():
    result = reg.required_model_ids_for_backends(
        {"BirdNET"}, {"birdnet": {"use_geo_filter": False}}
    )
    assert result == ["birdnet_acoustic"]


def test_required_model_ids_ast_has_no_geo_model():
    assert reg.required_model_ids_for_backends({"AST"}) == ["ast_audioset"]


def test_required_model_ids_perch_has_no_geo_model():
    assert reg.required_model_ids_for_backends({"Perch"}) == ["perch_v2_cpu"]


def test_required_model_ids_combines_multiple_backends():
    result = reg.required_model_ids_for_backends({"BirdNET", "AST", "Perch"})
    assert result == ["birdnet_acoustic", "birdnet_geo", "ast_audioset", "perch_v2_cpu"]


def test_required_model_ids_empty_selection_returns_empty():
    assert reg.required_model_ids_for_backends(set()) == []
