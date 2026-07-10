"""Unit tests for Fase 6: installer dispatch mapping in ai_model_manager.py.

Confirms install_model() selects the correct installer via the dispatch
mapping (not a central if/elif) and reports a controlled error for an
unknown model, without downloading anything real.
"""

from __future__ import annotations

from unittest import mock

import my_app.ai.model_manager as amm


def test_installer_dispatch_covers_all_known_backends():
    assert set(amm._INSTALLER_DISPATCH) == {"AST", "Perch", "BirdNET"}


def test_install_model_dispatches_to_ast_installer():
    mock_ast = mock.Mock(return_value="ast-path")
    with mock.patch.dict(amm._INSTALLER_DISPATCH, {"AST": mock_ast}):
        result = amm.install_model(amm.AST_MODEL.model_id)
    mock_ast.assert_called_once()
    assert result == "ast-path"


def test_install_model_dispatches_to_perch_installer():
    mock_perch = mock.Mock(return_value="perch-path")
    with mock.patch.dict(amm._INSTALLER_DISPATCH, {"Perch": mock_perch}):
        result = amm.install_model(amm.PERCH_MODEL.model_id)
    mock_perch.assert_called_once()
    assert result == "perch-path"


def test_install_model_dispatches_to_birdnet_installer_for_both_variants():
    mock_birdnet = mock.Mock(return_value="birdnet-path")
    with mock.patch.dict(amm._INSTALLER_DISPATCH, {"BirdNET": mock_birdnet}):
        amm.install_model(amm.BIRDNET_ACOUSTIC_MODEL.model_id)
        amm.install_model(amm.BIRDNET_GEO_MODEL.model_id)
    assert mock_birdnet.call_count == 2


def test_install_model_unknown_model_raises_typed_error():
    definition = amm.ModelDefinition(
        model_id="no_installer_model",
        display_name="No Installer",
        backend="SomeUnregisteredBackend",
        version="1",
        relative_dir="x/y",
        source="test",
        license="test",
        required_files=("f.bin",),
    )
    original = dict(amm._MODEL_BY_ID)
    amm._MODEL_BY_ID[definition.model_id] = definition
    try:
        try:
            amm.install_model(definition.model_id)
            raise AssertionError("expected ModelInstallError")
        except amm.ModelInstallError as exc:
            assert exc.model_id == definition.model_id
    finally:
        amm._MODEL_BY_ID.clear()
        amm._MODEL_BY_ID.update(original)
