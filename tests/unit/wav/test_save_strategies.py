"""Unit tests for wav_save_strategies.py.

These strategies are Qt-free, so no QApplication is required. Tests use
tmp_path and monkeypatch concrete filesystem/injection calls only — no
dialogs, no real user files.

The save-manager's QDialog/QMessageBox UI layer (wav_save_manager.py) is not
covered here; that Qt-coupling is a known, separate concern tracked for
Fase 5 of the refactor plan, not addressed by this test task.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

import wav_save_strategies as wss
from tests.fixtures.wav import builder as wavbuild


@pytest.fixture
def source_wav(write_wav):
    """A minimal valid source WAV file path."""
    return write_wav(wavbuild.make_minimal_wav())


# ---------------------------------------------------------------------------
# save_as_edit_copy
# ---------------------------------------------------------------------------


def test_save_as_edit_copy_success(source_wav):
    result = wss.WavSaveStrategies.save_as_edit_copy(source_wav, {"INAM": "X"})

    assert result.success is True
    assert result.operation_type == "edit_copy"
    assert result.output_path.endswith("_edit.wav")
    assert os.path.exists(result.output_path)
    assert os.path.exists(source_wav)  # original untouched


def test_save_as_edit_copy_increments_on_existing_file(source_wav, tmp_path):
    base = os.path.splitext(source_wav)[0]
    existing_edit = base + "_edit.wav"
    with open(existing_edit, "wb") as f:
        f.write(b"already here")

    result = wss.WavSaveStrategies.save_as_edit_copy(source_wav, {"INAM": "X"})

    assert result.success is True
    assert result.output_path != existing_edit
    assert result.output_path.endswith("_edit_1.wav")


def test_save_as_edit_copy_validation_error_missing_source(tmp_path):
    missing = str(tmp_path / "does_not_exist.wav")

    result = wss.WavSaveStrategies.save_as_edit_copy(missing, {"INAM": "X"})

    assert result.success is False
    assert "does not exist" in result.error_message


def test_save_as_edit_copy_validation_error_bad_extension(tmp_path):
    not_wav = tmp_path / "file.txt"
    not_wav.write_text("hello")

    result = wss.WavSaveStrategies.save_as_edit_copy(str(not_wav), {"INAM": "X"})

    assert result.success is False
    assert "must be WAV format" in result.error_message


def test_save_as_edit_copy_write_error_is_reported(source_wav):
    with mock.patch(
        "wav_save_strategies.inject_info_chunk", side_effect=OSError("disk full")
    ):
        result = wss.WavSaveStrategies.save_as_edit_copy(source_wav, {"INAM": "X"})

    assert result.success is False
    assert "disk full" in result.error_message
    # No half-written edit copy should remain.
    base = os.path.splitext(source_wav)[0]
    assert not os.path.exists(base + "_edit.wav")


# ---------------------------------------------------------------------------
# save_in_place
# ---------------------------------------------------------------------------


def test_save_in_place_success(source_wav):
    original_size = os.path.getsize(source_wav)

    result = wss.WavSaveStrategies.save_in_place(source_wav, {"INAM": "In Place"})

    assert result.success is True
    assert result.output_path == source_wav
    assert os.path.getsize(source_wav) > original_size


def test_save_in_place_cancelled_by_confirm_callback(source_wav):
    original_bytes = open(source_wav, "rb").read()

    result = wss.WavSaveStrategies.save_in_place(
        source_wav, {"INAM": "X"}, confirm_callback=lambda: False
    )

    assert result.success is False
    assert "cancelled" in result.error_message.lower()
    assert open(source_wav, "rb").read() == original_bytes


def test_save_in_place_write_error_rolls_back_and_cleans_temp_file(source_wav):
    original_bytes = open(source_wav, "rb").read()

    with mock.patch(
        "wav_save_strategies.inject_info_chunk", side_effect=OSError("disk full")
    ):
        result = wss.WavSaveStrategies.save_in_place(source_wav, {"INAM": "X"})

    assert result.success is False
    assert "disk full" in result.error_message
    # Original file must be untouched (os.replace never ran).
    assert open(source_wav, "rb").read() == original_bytes
    # Temp file must be cleaned up.
    assert not os.path.exists(source_wav + ".tmp")


def test_save_in_place_output_is_re_parseable(source_wav):
    import wav_analyzer as wa

    result = wss.WavSaveStrategies.save_in_place(source_wav, {"INAM": "Parseable"})

    assert result.success is True
    parsed = wa.wav_analyze(source_wav)
    assert parsed["info"]["INAM"] == "Parseable"


# ---------------------------------------------------------------------------
# save_with_backup
# ---------------------------------------------------------------------------


def test_save_with_backup_success_creates_backup_and_updates_original(source_wav):
    original_bytes = open(source_wav, "rb").read()

    result = wss.WavSaveStrategies.save_with_backup(source_wav, {"INAM": "Backed up"})

    assert result.success is True
    assert result.backup_path == source_wav + ".bak"
    assert os.path.exists(result.backup_path)
    # Backup preserves the pre-save content.
    assert open(result.backup_path, "rb").read() == original_bytes
    # Original path now contains the mutated content.
    import wav_analyzer as wa

    assert wa.wav_analyze(source_wav)["info"]["INAM"] == "Backed up"


def test_save_with_backup_write_error_preserves_original_and_cleans_temp(source_wav):
    original_bytes = open(source_wav, "rb").read()

    with mock.patch(
        "wav_save_strategies.inject_info_chunk", side_effect=OSError("disk full")
    ):
        result = wss.WavSaveStrategies.save_with_backup(source_wav, {"INAM": "X"})

    assert result.success is False
    assert open(source_wav, "rb").read() == original_bytes
    assert not os.path.exists(source_wav + ".tmp")


def test_save_with_backup_validation_error_creates_no_backup(tmp_path):
    missing = str(tmp_path / "missing.wav")

    result = wss.WavSaveStrategies.save_with_backup(missing, {"INAM": "X"})

    assert result.success is False
    assert not os.path.exists(missing + ".bak")


# ---------------------------------------------------------------------------
# save_with_custom_name
# ---------------------------------------------------------------------------


def test_save_with_custom_name_success(source_wav, tmp_path):
    result = wss.WavSaveStrategies.save_with_custom_name(
        source_wav, {"INAM": "Custom"}, custom_name="my_recording"
    )

    assert result.success is True
    assert os.path.basename(result.output_path) == "my_recording.wav"
    assert os.path.exists(result.output_path)


def test_save_with_custom_name_adds_wav_extension_if_missing(source_wav):
    result = wss.WavSaveStrategies.save_with_custom_name(
        source_wav, {"INAM": "X"}, custom_name="no_extension"
    )

    assert result.success is True
    assert result.output_path.endswith("no_extension.wav")


def test_save_with_custom_name_rejects_empty_name(source_wav):
    result = wss.WavSaveStrategies.save_with_custom_name(
        source_wav, {"INAM": "X"}, custom_name="   "
    )

    assert result.success is False
    assert "empty" in result.error_message.lower()


def test_save_with_custom_name_increments_on_existing_file(source_wav, tmp_path):
    existing = tmp_path / "taken.wav"
    existing.write_bytes(b"already here")

    result = wss.WavSaveStrategies.save_with_custom_name(
        source_wav, {"INAM": "X"}, custom_name="taken"
    )

    assert result.success is True
    assert result.output_path != str(existing)
    assert result.output_path.endswith("taken_1.wav")


# ---------------------------------------------------------------------------
# SaveResult.files_created bookkeeping
# ---------------------------------------------------------------------------


def test_save_result_tracks_output_and_backup_paths(source_wav):
    result = wss.WavSaveStrategies.save_with_backup(source_wav, {"INAM": "X"})

    assert result.output_path in result.files_created
    assert result.backup_path in result.files_created


def test_save_result_failure_has_no_files_created(tmp_path):
    missing = str(tmp_path / "missing.wav")

    result = wss.WavSaveStrategies.save_as_edit_copy(missing, {"INAM": "X"})

    assert result.files_created == []
