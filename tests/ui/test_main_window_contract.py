"""Regression guards for main-window contracts preserved by the UI refactor."""

from __future__ import annotations


def test_main_window_keeps_menu_and_shortcut_command_contracts(
    qapp, isolated_qsettings, qt_widget_cleanup
):
    import my_app.main as main_mod

    window = qt_widget_cleanup(main_mod.MainWindow())

    expected_command_keys = {
        "file_commands": {
            "open_directory",
            "refresh_file_list",
            "export_to_ableton",
            "export_metadata_csv",
            "exit_application",
        },
        "edit_commands": {
            "clear_tags",
            "reset_defaults",
            "open_template_manager",
            "open_user_config_manager",
        },
        "view_commands": {
            "set_waveform_mode",
            "zoom_in",
            "zoom_out",
            "zoom_fit",
            "apply_light_theme",
            "apply_dark_theme",
            "apply_macos_dark_theme",
            "apply_native_macos_theme",
        },
        "audio_commands": {
            "play_pause",
            "stop",
            "volume_up",
            "volume_down",
            "toggle_mute",
            "seek_forward",
            "seek_backward",
        },
        "analysis_commands": {
            "show_analytics",
            "show_cue_analysis",
            "show_ai_analysis",
        },
        "help_commands": {
            "show_help_and_quickstart",
            "show_keyboard_shortcuts",
            "show_about",
        },
    }

    for group_name, expected_keys in expected_command_keys.items():
        commands = getattr(window, group_name)
        assert expected_keys <= set(commands)
        for key in expected_keys:
            assert callable(commands[key])

    assert window.menuBar().actions()

    registered_shortcuts = window.shortcut_manager.shortcuts
    for key_sequence in ("Space", "M", "F5", "Ctrl+1", "F1"):
        assert key_sequence in registered_shortcuts
