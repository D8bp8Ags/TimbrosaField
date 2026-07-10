"""Regression tests for the Fase 4 extraction of MetadataPresenter from WavViewer.

Confirms table reset/population/formatting behave the same as the original
WavViewer methods did.
"""

from __future__ import annotations

import pytest
from PyQt5.QtWidgets import QTableWidget

from ui.waveform.metadata_presenter import MetadataPresenter


def _make_table(headers):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    return table


@pytest.fixture
def presenter(qapp):
    fmt_table = _make_table(["Key", "Value"])
    bext_table = _make_table(["Key", "Value"])
    info_table = _make_table(["Key", "Value"])
    info_table.setObjectName("info_table")
    gps_table = _make_table(["Key", "Value"])
    cue_table = _make_table(["ID", "Positie", "Label"])
    return MetadataPresenter(fmt_table, bext_table, info_table, gps_table, cue_table)


def test_clear_all_resets_row_counts(presenter):
    presenter.populate_fmt_table({"Sample rate": 48000})
    assert presenter.fmt_table.rowCount() > 0

    presenter.clear_all()

    for table in (
        presenter.fmt_table,
        presenter.bext_table,
        presenter.info_table,
        presenter.gps_table,
        presenter.cue_table,
    ):
        assert table.rowCount() == 0


def test_populate_fmt_table_shows_representative_values(presenter):
    presenter.populate_fmt_table(
        {"Sample rate": 48000, "Channels": 2, "Audio format name": "PCM"}
    )
    assert presenter.fmt_table.rowCount() == 3
    assert presenter.fmt_table.item(0, 0).text() == "Sample rate"
    assert presenter.fmt_table.item(0, 1).text() == "48000"


def test_populate_bext_table_representative_values(presenter):
    presenter.populate_bext_table({"Description": "Field test", "Originator": "Tascam"})
    assert presenter.bext_table.rowCount() == 2
    assert presenter.bext_table.item(1, 1).text() == "Tascam"


def test_populate_info_table_merges_defaults(presenter):
    presenter.populate_info_table(
        info_data={"INAM": "Recording"}, user_config_defaults={"ICMT": "default comment"}
    )
    keys = [presenter.info_table.item(r, 0).text() for r in range(presenter.info_table.rowCount())]
    assert "INAM" in keys
    assert "ICMT" in keys


def test_populate_info_table_wav_value_overrides_default(presenter):
    presenter.populate_info_table(
        info_data={"INAM": "From WAV"}, user_config_defaults={"INAM": "Default name"}
    )
    assert presenter.info_table.item(0, 1).text() == "From WAV"


def test_populate_info_table_empty_uses_only_defaults(presenter):
    presenter.populate_info_table(info_data={}, user_config_defaults={"INAM": "Default name"})
    assert presenter.info_table.rowCount() == 1
    assert presenter.info_table.item(0, 1).text() == "Default name"


def test_populate_gps_table_rows_always_shows_three_base_rows(presenter):
    presenter.populate_gps_table_rows(None)
    assert presenter.gps_table.rowCount() == 3
    assert presenter.gps_table.item(0, 0).text() == "Latitude"
    assert presenter.gps_table.item(0, 1).text() == ""


def test_populate_gps_table_rows_with_data(presenter):
    presenter.populate_gps_table_rows(
        {"latitude": 52.37, "longitude": 4.9, "altitude": 5.0}
    )
    assert presenter.gps_table.item(0, 1).text() == "52.37"
    assert presenter.gps_table.item(2, 1).text() == "5.0"


def test_populate_gps_table_rows_adds_photo_and_location_when_present(presenter):
    presenter.populate_gps_table_rows(
        {
            "latitude": 1.0,
            "longitude": 2.0,
            "photo_ref": "../Photos/IMG_1.jpg",
            "location_name": "Forest",
        }
    )
    assert presenter.gps_table.rowCount() == 5
    labels = [presenter.gps_table.item(r, 0).text() for r in range(5)]
    assert "Photo" in labels
    assert "Location" in labels


def test_populate_cue_table_shows_labeled_cue_points(presenter):
    cue_points = [{"ID": 1, "Sample Offset": 48000}]
    presenter.populate_cue_table(cue_points, cue_labels={"1": "Bird call"}, sample_rate=48000)
    assert presenter.cue_table.rowCount() == 1
    assert presenter.cue_table.item(0, 1).text() == "1.000s"
    assert presenter.cue_table.item(0, 2).text() == "Bird call"


def test_populate_cue_table_skips_unlabeled_cue_points(presenter):
    cue_points = [{"ID": 1, "Sample Offset": 100}, {"ID": 2, "Sample Offset": 200}]
    presenter.populate_cue_table(cue_points, cue_labels={"1": "Only this one"}, sample_rate=1000)
    assert presenter.cue_table.rowCount() == 1
    assert presenter.cue_table.item(0, 0).text() == "1"


def test_populate_cue_table_empty_shows_placeholder_message(presenter):
    presenter.populate_cue_table([], cue_labels={}, sample_rate=48000)
    assert presenter.cue_table.rowCount() == 1
    assert presenter.cue_table.item(0, 0).text() == "No labeled cue points found."


def test_populate_cue_table_without_sample_rate_shows_raw_samples(presenter):
    cue_points = [{"ID": 1, "Sample Offset": 500}]
    presenter.populate_cue_table(cue_points, cue_labels={"1": "X"}, sample_rate=None)
    assert presenter.cue_table.item(0, 1).text() == "500 samples"
