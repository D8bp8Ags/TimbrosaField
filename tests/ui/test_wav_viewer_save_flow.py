"""Regression test for Fase 5: WavViewer's save-dialog choice reaches WavSaveManager.

Confirms save_info_from_info_table_to_file() correctly translates the
user's WavSaveOptionsDialog choice into the WavSaveManager.execute_save()
call, and that cancelling the dialog makes no save call at all.
"""

from __future__ import annotations

from unittest import mock

from PyQt5.QtWidgets import QDialog, QMessageBox

from my_app.ui.waveform import viewer as wv
from tests.fixtures.wav import builder as wavbuild


def test_save_dialog_choice_is_passed_to_save_manager(
    qapp, qt_widget_cleanup, isolated_qsettings, write_wav
):
    viewer = qt_widget_cleanup(wv.WavViewer())

    source = write_wav(
        wavbuild.make_minimal_wav(
            extra_chunks=[wavbuild.make_list_info_chunk({"INAM": "Original"})]
        )
    )
    viewer.filename = source
    viewer._metadata_presenter.populate_info_table({"INAM": "Changed Name"}, {})
    viewer._metadata_presenter.populate_gps_table_rows(None)

    fake_result = mock.Mock(
        success=True, output_path=source, backup_path="", operation_type="edit_copy"
    )

    with mock.patch.object(
        wv.WavSaveOptionsDialog, "exec_", return_value=QDialog.Accepted
    ), mock.patch.object(
        wv.WavSaveOptionsDialog, "get_save_method", return_value=3
    ), mock.patch.object(
        wv.WavSaveOptionsDialog, "get_custom_name", return_value=""
    ), mock.patch.object(
        wv.WavSaveOptionsDialog, "should_merge_tags", return_value=True
    ), mock.patch.object(
        wv.WavSaveManager, "execute_save", return_value=fake_result
    ) as mock_execute, mock.patch.object(
        viewer, "load_wav_files"
    ), mock.patch.object(
        QMessageBox, "information", return_value=QMessageBox.Ok
    ):
        viewer.save_info_from_info_table_to_file()

    assert mock_execute.called
    _, kwargs = mock_execute.call_args
    assert kwargs["save_method"] == 3
    assert kwargs["merge_tags"] is True
    assert kwargs["filename"] == source


def test_cancelling_save_dialog_does_not_call_save_manager(
    qapp, qt_widget_cleanup, isolated_qsettings, write_wav
):
    viewer = qt_widget_cleanup(wv.WavViewer())

    source = write_wav(
        wavbuild.make_minimal_wav(
            extra_chunks=[wavbuild.make_list_info_chunk({"INAM": "Original"})]
        )
    )
    viewer.filename = source
    viewer._metadata_presenter.populate_info_table({"INAM": "Changed"}, {})
    viewer._metadata_presenter.populate_gps_table_rows(None)

    original_bytes = open(source, "rb").read()

    with mock.patch.object(
        wv.WavSaveOptionsDialog, "exec_", return_value=QDialog.Rejected
    ), mock.patch.object(wv.WavSaveManager, "execute_save") as mock_execute:
        viewer.save_info_from_info_table_to_file()

    assert not mock_execute.called
    assert open(source, "rb").read() == original_bytes
