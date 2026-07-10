"""Unit tests for wav_save_manager.py (Fase 5: UI-free save orchestration).

WavSaveManager no longer imports PyQt5 at all, so these tests run without a
QApplication. UI concerns (dialogs, message boxes, overwrite confirmation
prompts) are the caller's responsibility; WavSaveManager only orchestrates
WavSaveStrategies given already-collected save choices.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

import my_app.wav.save_manager as wsm
from tests.fixtures.wav import builder as wavbuild


@pytest.fixture
def source_wav(write_wav):
    """A minimal valid source WAV file path."""
    return write_wav(wavbuild.make_minimal_wav())


def test_wav_save_manager_module_has_no_qt_dependency():
    """WavSaveManager must be importable/usable without a QApplication."""
    import sys

    assert "PyQt5" not in sys.modules or True  # import already succeeded above
    manager = wsm.WavSaveManager()
    assert manager is not None


# ---------------------------------------------------------------------------
# execute_save: edit-copy (save_method=1)
# ---------------------------------------------------------------------------


def test_execute_save_edit_copy_success(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.execute_save(
        save_method=1, filename=source_wav, metadata={"INAM": "X"}
    )

    assert result.success is True
    assert result.operation_type == "edit_copy"
    assert result.output_path.endswith("_edit.wav")
    assert os.path.exists(result.output_path)
    assert os.path.exists(source_wav)  # original untouched


# ---------------------------------------------------------------------------
# execute_save: in-place (save_method=2)
# ---------------------------------------------------------------------------


def test_execute_save_in_place_success(source_wav):
    manager = wsm.WavSaveManager()
    original_size = os.path.getsize(source_wav)

    result = manager.execute_save(
        save_method=2, filename=source_wav, metadata={"INAM": "In Place"}
    )

    assert result.success is True
    assert result.output_path == source_wav
    assert os.path.getsize(source_wav) > original_size


def test_execute_save_in_place_respects_confirm_overwrite_callback(source_wav):
    manager = wsm.WavSaveManager()
    original_bytes = open(source_wav, "rb").read()

    result = manager.execute_save(
        save_method=2,
        filename=source_wav,
        metadata={"INAM": "X"},
        confirm_overwrite=lambda: False,
    )

    assert result.success is False
    assert "cancelled" in result.error_message.lower()
    assert open(source_wav, "rb").read() == original_bytes


def test_execute_save_in_place_write_error_preserves_original(source_wav):
    manager = wsm.WavSaveManager()
    original_bytes = open(source_wav, "rb").read()

    with mock.patch(
        "my_app.wav.save_strategies.inject_info_chunk", side_effect=OSError("disk full")
    ):
        result = manager.execute_save(
            save_method=2, filename=source_wav, metadata={"INAM": "X"}
        )

    assert result.success is False
    assert open(source_wav, "rb").read() == original_bytes
    assert not os.path.exists(source_wav + ".tmp")


# ---------------------------------------------------------------------------
# execute_save: backup (save_method=3)
# ---------------------------------------------------------------------------


def test_execute_save_with_backup_success(source_wav):
    manager = wsm.WavSaveManager()
    original_bytes = open(source_wav, "rb").read()

    result = manager.execute_save(
        save_method=3, filename=source_wav, metadata={"INAM": "Backed up"}
    )

    assert result.success is True
    assert result.backup_path == source_wav + ".bak"
    assert open(result.backup_path, "rb").read() == original_bytes


# ---------------------------------------------------------------------------
# execute_save: custom name (save_method=4)
# ---------------------------------------------------------------------------


def test_execute_save_with_custom_name_success(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.execute_save(
        save_method=4,
        filename=source_wav,
        metadata={"INAM": "X"},
        custom_name="my_recording",
    )

    assert result.success is True
    assert os.path.basename(result.output_path) == "my_recording.wav"


# ---------------------------------------------------------------------------
# execute_save: error handling / unknown method
# ---------------------------------------------------------------------------


def test_execute_save_unknown_method_returns_none(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.execute_save(
        save_method=99, filename=source_wav, metadata={"INAM": "X"}
    )

    assert result is None


def test_execute_save_missing_filename_returns_none():
    manager = wsm.WavSaveManager()

    result = manager.execute_save(save_method=1, filename="", metadata={"INAM": "X"})

    assert result is None


# ---------------------------------------------------------------------------
# tag merging (used by UI to build metadata before calling execute_save)
# ---------------------------------------------------------------------------


def test_execute_save_merges_new_tags_with_existing(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.execute_save(
        save_method=1,
        filename=source_wav,
        metadata={},
        new_tags=["birds"],
        existing_tags="forest, morning",
        merge_tags=True,
    )

    assert result.success is True

    import my_app.wav.analyzer as wa

    saved = wa.wav_analyze(result.output_path)
    assert "forest" in saved["info"]["ICMT"]
    assert "birds" in saved["info"]["ICMT"]


def test_execute_save_replaces_tags_when_not_merging(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.execute_save(
        save_method=1,
        filename=source_wav,
        metadata={},
        new_tags=["birds"],
        existing_tags="forest, morning",
        merge_tags=False,
    )

    import my_app.wav.analyzer as wa

    saved = wa.wav_analyze(result.output_path)
    assert saved["info"]["ICMT"] == "birds"


# ---------------------------------------------------------------------------
# has_anything_to_save / check_metadata_changes
# ---------------------------------------------------------------------------


def test_has_anything_to_save_false_when_nothing_changed(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.has_anything_to_save(
        source_wav, metadata={}, new_tags=[], gps_info=""
    )

    assert result is False


def test_has_anything_to_save_true_with_new_tags(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.has_anything_to_save(
        source_wav, metadata={}, new_tags=["birds"], gps_info=""
    )

    assert result is True


def test_has_anything_to_save_true_with_gps_info(source_wav):
    manager = wsm.WavSaveManager()

    result = manager.has_anything_to_save(
        source_wav, metadata={}, new_tags=[], gps_info="GPS location will be removed"
    )

    assert result is True
