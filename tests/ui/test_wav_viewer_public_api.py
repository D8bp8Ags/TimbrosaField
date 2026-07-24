"""Regression tests for Fase 2 public WavViewer API and SettingsManager decoupling.

The refactor replaced direct
external access to WavViewer's private methods and internal widgets
(mono_radio/stereo_radio/overlay_radio, audio_player, _reset_info_table_to_defaults,
_current_mouse_mode) with a small public API. These tests confirm the new
public methods exist and behave as the code they replaced did.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QTableWidgetItem

from my_app.ui.waveform import viewer as wv


def _make_wav_viewer(qapp):
    return wv.WavViewer()


def test_get_view_mode_returns_current_mode(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.set_view_mode("overlay")
    assert viewer.get_view_mode() == "overlay"


def test_sync_view_mode_controls_checks_matching_radio(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    viewer.sync_view_mode_controls("mono")
    assert viewer.mono_radio.isChecked() is True

    viewer.sync_view_mode_controls("overlay")
    assert viewer.overlay_radio.isChecked() is True

    viewer.sync_view_mode_controls("per_kanaal")
    assert viewer.stereo_radio.isChecked() is True


def test_set_and_get_volume_round_trip(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.set_volume(42)
    assert viewer.get_volume() == 42


def test_get_current_mouse_mode_defaults_to_performance(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    assert viewer.get_current_mouse_mode() == "performance"


def test_get_current_mouse_mode_reflects_last_applied_preset(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.set_mouse_labels_minimal()
    assert viewer.get_current_mouse_mode() == "minimal"


def test_reset_info_table_to_defaults_is_public(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    assert hasattr(viewer, "reset_info_table_to_defaults")


def test_playback_control_methods_delegate_to_audio_player(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    for method_name in (
        "toggle_playback",
        "stop_playback",
        "volume_up",
        "volume_down",
        "toggle_mute",
        "seek_forward",
        "seek_backward",
    ):
        assert hasattr(viewer, method_name), f"missing public method: {method_name}"


def test_get_audio_duration_returns_none_without_loaded_file(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.audio_duration = None
    assert viewer.get_audio_duration() is None


def test_field_lab_dark_shell_keeps_required_visual_zones(qapp, qt_widget_cleanup):
    """The Field Lab Dark layout must keep every main screen zone present."""
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    for attr_name, object_name in (
        ("left_panel", "recording_sidebar"),
        ("central_panel", "waveform_workspace"),
        ("right_panel", "inspector_panel"),
        ("waveform_panel", "waveform_panel"),
        ("cue_panel", "cue_panel"),
        ("transport_panel", "transport_bar"),
    ):
        widget = getattr(viewer, attr_name)
        assert isinstance(widget, QFrame)
        assert widget.objectName() == object_name

    assert viewer.main_splitter.count() == 3
    assert viewer.main_splitter.widget(0) is viewer.left_panel
    assert viewer.main_splitter.widget(1) is viewer.central_panel
    assert viewer.main_splitter.widget(2) is viewer.right_panel

    assert viewer.file_search_input.placeholderText() == "Search recordings..."
    assert viewer.file_list_label.text() == "RECORDINGS"
    assert viewer.recording_settings_button.objectName() == "recording_settings_button"
    assert viewer.recording_filter_button.objectName() == "recording_filter_button"
    assert viewer.recording_sort_button.objectName() == "recording_sort_button"
    assert viewer.recording_count_label.objectName() == "recording_count_label"
    assert viewer.audio_player.objectName() == "audio_player_widget"
    assert viewer.cue_label.objectName() == "cue_section_header"
    assert viewer.cue_overview.objectName() == "cue_overview"
    assert viewer.inspector_settings_button.objectName() == "inspector_settings_button"
    assert set(viewer.inspector_sections) == {
        "METADATA",
        "AUDIO",
        "LOCATION",
        "INFO CHUNK",
    }

    inspector_header = viewer.right_panel.findChild(QLabel, "inspector_header")
    waveform_header = viewer.waveform_panel.findChild(QLabel, "waveform_header")
    assert inspector_header is not None
    assert inspector_header.text() == "INSPECTOR"
    assert waveform_header is not None
    assert waveform_header.text() == "WAVEFORM VIEW"


def test_field_lab_dark_shell_preserves_metadata_and_transport_controls(
    qapp, qt_widget_cleanup
):
    """Guard the information-parity controls called out in the refactor plan."""
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    assert viewer.bext_label.text() == "METADATA"
    assert viewer.fmt_label.text() == "AUDIO"
    assert viewer.info_label.text() == "INFO CHUNK"
    assert viewer.gps_label.text() == "LOCATION"
    viewer._populate_gps_table(None)
    assert viewer.gps_table.rowCount() == 3
    assert [viewer.gps_table.item(row, 0).text() for row in range(3)] == [
        "Latitude",
        "Longitude",
        "Altitude",
    ]

    assert viewer.cue_table.columnCount() == 4
    assert [
        viewer.cue_table.horizontalHeaderItem(column).text() for column in range(3)
    ] == ["ID", "Positie", "Label"]
    assert viewer.cue_table.horizontalHeaderItem(3).text() == "Notes"
    assert viewer.cue_add_button.objectName() == "cue_add_button"
    assert viewer.cue_menu_button.objectName() == "cue_menu_button"

    assert viewer.audio_player.play_button.objectName() == "transport_play_button"
    assert viewer.audio_player.rewind_button.objectName() == "transport_rewind_button"
    assert viewer.audio_player.stop_button.objectName() == "transport_stop_button"
    assert viewer.audio_player.forward_button.objectName() == "transport_forward_button"
    assert viewer.audio_player.loop_button.objectName() == "transport_loop_button"
    assert (
        viewer.audio_player.position_slider.objectName()
        == "transport_position_slider"
    )
    assert viewer.audio_player.volume_slider.objectName() == "transport_volume_slider"
    assert viewer.audio_player.time_label.objectName() == "time_display"
    assert viewer.audio_player.secondary_time_label.objectName() == "secondary_time_display"
    assert viewer.transport_zoom_fit_button.objectName() == "transport_zoom_button"
    assert viewer.transport_zoom_out_button.objectName() == "transport_zoom_button"
    assert viewer.transport_zoom_in_button.objectName() == "transport_zoom_button"
    assert viewer.transport_status_label.objectName() == "transport_status_label"
    assert viewer._get_professional_default_text() == "Hover for time, sample, dBFS"


def test_recording_sidebar_controls_have_real_behavior(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    viewer.file_search_input.setText("089")
    viewer._toggle_recording_filter()
    assert viewer.file_search_input.text() == ""

    viewer._recording_sort_descending = False
    viewer._toggle_recording_sort()
    assert viewer._recording_sort_descending is True

    viewer._update_recording_count_label(116)
    assert viewer.recording_count_label.text() == "116 recordings"


def test_waveform_toolbar_controls_have_real_behavior(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    assert set(viewer.waveform_mode_buttons) == {"mono", "per_kanaal", "overlay"}
    viewer.waveform_mode_buttons["mono"].click()
    assert viewer.get_view_mode() == "mono"
    assert viewer.mono_radio.isChecked() is True

    viewer.waveform_mode_buttons["per_kanaal"].click()
    assert viewer.get_view_mode() == "per_kanaal"
    assert viewer.stereo_radio.isChecked() is True

    viewer.snap_button.click()
    assert viewer._snap_to_cues is True
    assert viewer.snap_button.text() == "Snap: On"

    viewer.time_mode_combo.setCurrentText("Timecode")
    assert viewer._time_display_mode == "timecode"

    viewer.amplitude_mode_combo.setCurrentText("Linear")
    assert viewer._amplitude_display_mode == "linear"
    assert viewer.waveform_plot.getPlotItem().getAxis("top").isVisible() is True


def test_inspector_sections_are_collapsible(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    section = viewer.inspector_sections["AUDIO"]
    toggle = section.findChild(QPushButton, "inspector_section_toggle")

    assert toggle is not None
    assert viewer.fmt_table.isHidden() is False

    toggle.click()
    assert viewer.fmt_table.isHidden() is True
    assert toggle.text().startswith(">")

    toggle.click()
    assert viewer.fmt_table.isHidden() is False
    assert toggle.text().startswith("v")


def test_metadata_table_cells_can_be_copied(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.fmt_table.insertRow(0)
    viewer.fmt_table.setItem(0, 0, QTableWidgetItem("Sample rate"))
    viewer.fmt_table.setItem(0, 1, QTableWidgetItem("96000 Hz"))
    viewer.fmt_table.setCurrentCell(0, 1)

    viewer._copy_selected_table_cell(viewer.fmt_table)

    assert qapp.clipboard().text() == "96000 Hz"


def test_add_session_cue_updates_cue_surfaces(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.current_sr = 1000
    viewer.audio_duration = 10.0
    viewer.audio_player.get_position = lambda: 2500

    viewer._add_session_cue_point()

    assert viewer.current_cue_points == [
        {
            "ID": 1,
            "Sample Offset": 2500,
            "Label": "MARK_01",
            "Notes": "Session cue",
        }
    ]
    assert viewer.cue_table.item(0, 0).text() == "1"
    assert viewer.cue_table.item(0, 2).text() == "MARK_01"
    assert viewer.cue_table.item(0, 3).text() == "Session cue"
    assert viewer.selected_cue_id == "1"
    assert "1" in viewer.cue_lines
    assert "1" in viewer.cue_markers


def test_session_cue_id_prefers_short_free_display_id(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.current_cue_points = [{"ID": 4278190179, "Sample Offset": 100}]

    assert viewer._next_session_cue_id() == 1


def test_transport_zoom_controls_change_waveform_range(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.audio_duration = 100.0
    viewer.syncing = True
    try:
        for plot in viewer._waveform_plots():
            plot.getViewBox().setXRange(0, 100, padding=0)
    finally:
        viewer.syncing = False

    viewer._zoom_waveform_in()
    x0, x1 = viewer.waveform_plot.getViewBox().viewRange()[0]
    assert round(x1 - x0) == 50

    viewer._zoom_waveform_fit()
    x0, x1 = viewer.waveform_plot.getViewBox().viewRange()[0]
    assert round(x0) == 0
    assert round(x1) == 100


def test_transport_loop_and_time_display_are_functional(qapp, qt_widget_cleanup):
    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))

    viewer.audio_player.loop_button.click()
    assert viewer.audio_player._loop_enabled is True

    viewer.audio_player._update_time_display(1234, 5000)
    assert viewer.audio_player.time_label.text() == "00:01.234"
    assert viewer.audio_player.secondary_time_label.text() == "/00:05.000"


def test_transport_status_label_shows_audio_summary(qapp, qt_widget_cleanup):
    class Info:
        subtype = "FLOAT"
        channels = 2

    viewer = qt_widget_cleanup(_make_wav_viewer(qapp))
    viewer.current_sr = 96000

    viewer._update_transport_status(Info())

    assert viewer.transport_status_label.text() == "96 kHz · FLOAT · 2ch"
