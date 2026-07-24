"""Regression tests for Fase 2 public WavViewer API and SettingsManager decoupling.

The refactor replaced direct
external access to WavViewer's private methods and internal widgets
(mono_radio/stereo_radio/overlay_radio, audio_player, _reset_info_table_to_defaults,
_current_mouse_mode) with a small public API. These tests confirm the new
public methods exist and behave as the code they replaced did.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QFrame, QLabel

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
    assert viewer.audio_player.objectName() == "audio_player_widget"
    assert viewer.cue_label.objectName() == "cue_section_header"
    assert viewer.cue_overview.objectName() == "cue_overview"

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

    assert viewer.cue_table.columnCount() == 3
    assert [
        viewer.cue_table.horizontalHeaderItem(column).text() for column in range(3)
    ] == ["ID", "Positie", "Label"]

    assert viewer.audio_player.play_button.objectName() == "transport_play_button"
    assert viewer.audio_player.stop_button.objectName() == "transport_stop_button"
    assert (
        viewer.audio_player.position_slider.objectName()
        == "transport_position_slider"
    )
    assert viewer.audio_player.volume_slider.objectName() == "transport_volume_slider"
    assert viewer.audio_player.time_label.objectName() == "time_display"
    assert viewer._get_professional_default_text() == "Hover for time, sample, dBFS"
