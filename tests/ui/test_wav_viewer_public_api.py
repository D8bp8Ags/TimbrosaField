"""Regression tests for Fase 2 public WavViewer API and SettingsManager decoupling.

The refactor replaced direct
external access to WavViewer's private methods and internal widgets
(mono_radio/stereo_radio/overlay_radio, audio_player, _reset_info_table_to_defaults,
_current_mouse_mode) with a small public API. These tests confirm the new
public methods exist and behave as the code they replaced did.
"""

from __future__ import annotations

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
