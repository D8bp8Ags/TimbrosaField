# settings_manager.py
import logging
import os

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QDesktopWidget

# Configure logging
logging.basicConfig(
    level=getattr(
        logging,
        os.getenv("LOG_LEVEL", "DEBUG").upper(),
        logging.INFO,
    ),
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SettingsManager:
    """Centralized settings management for the application.

    Handles saving and restoring all application settings using QSettings. Keeps
    MainWindow clean and makes settings management reusable.
    """

    def __init__(self):
        """Initialize settings manager."""
        self.settings = QSettings()
        logger.debug("SettingsManager initialized")

    # ========== WINDOW SETTINGS ==========

    def save_window_geometry(self, window):
        """Save window geometry."""
        self.settings.setValue("window/geometry", window.saveGeometry())
        logger.debug("Window geometry saved")

    def restore_window_geometry(self, window):
        """Restore window geometry or center if first run."""
        geometry = self.settings.value("window/geometry")

        if geometry:
            window.restoreGeometry(geometry)
            logger.debug("Window geometry restored")
            return True
        else:
            # First run - center window
            self._center_window(window)
            logger.debug("Window centered (first run)")
            return False

    def _center_window(self, window):
        """Center window on screen."""
        window.resize(1400, 900)
        screen = QDesktopWidget().screenGeometry()
        size = window.geometry()
        window.move(
            (screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2
        )

    # ========== VIEW SETTINGS ==========

    def save_view_settings(self, view_mode, show_metadata=True):
        """Save view and display settings."""
        self.settings.setValue("view/waveform_mode", view_mode)
        self.settings.setValue("view/show_metadata", show_metadata)
        logger.debug(f"View settings saved: {view_mode}")
        logger.debug(f"View settings saved: {show_metadata}")

    def get_view_mode(self, default="per-kanaal"):
        """Get saved view mode."""
        return self.settings.value("view/waveform_mode", default)

    def get_show_metadata(self, default=True):
        """Get metadata panel visibility setting."""
        return self.settings.value("view/show_metadata", default, type=bool)

    def get_mouse_labels_preset(self, default="performance"):
        """Get saved mouse labels preset."""
        preset = self.settings.value("view/mouse_labels_preset", default)
        return preset

    def save_mouse_labels_preset(self, preset, config):
        """Save mouse labels preset."""
        self.settings.setValue("view/mouse_labels_preset", preset)
        logger.debug(f"Mouse labels preset saved: {preset}")

    def save_theme_settings(self, theme_name="light"):
        """Save theme preference."""
        self.settings.setValue("ui/theme", theme_name)
        logger.debug(f"Theme setting saved: {theme_name}")

    def get_theme(self, default="light"):
        """Get saved theme preference."""
        return self.settings.value("ui/theme", default)

    # ========== AUDIO SETTINGS ==========

    def save_audio_settings(self, volume, auto_play=False, seek_step=10):
        """Save audio playback settings."""
        self.settings.setValue("audio/volume", volume)
        # self.settings.setValue("audio/auto_play", auto_play)
        # self.settings.setValue("audio/seek_step_seconds", seek_step)
        logger.debug(f"Audio settings saved: volume={volume}")

    def get_volume(self, default=70):
        """Get saved volume level."""
        return self.settings.value("audio/volume", default, type=int)

    # def get_auto_play(self, default=False):
    #     """Get auto-play setting."""
    #     return self.settings.value("audio/auto_play", default, type=bool)
    #
    # def get_seek_step(self, default=10):
    #     """Get seek step size."""
    #     return self.settings.value("audio/seek_step_seconds", default, type=int)

    # ========== UI PREFERENCES ==========

    # def save_ui_preferences(self, show_mouse_labels=True, confirm_delete=True,
    #                         auto_save_tags=True):
    #     """Save UI behavior preferences."""
    #     self.settings.setValue("ui/show_mouse_labels", show_mouse_labels)
    #     self.settings.setValue("ui/confirm_delete", confirm_delete)
    #     self.settings.setValue("ui/auto_save_tags", auto_save_tags)
    #     logger.debug("UI preferences saved")

    # def get_show_mouse_labels(self, default=True):
    #     """Get mouse labels setting."""
    #     return self.settings.value("ui/show_mouse_labels", default, type=bool)

    # def get_confirm_delete(self, default=True):
    #     """Get delete confirmation setting."""
    #     return self.settings.value("ui/confirm_delete", default, type=bool)

    # def get_auto_save_tags(self, default=True):
    #     """Get auto-save tags setting."""
    #     return self.settings.value("ui/auto_save_tags", default, type=bool)

    # ========== CONVENIENCE METHODS ==========

    def restore_all_settings(self, main_window):
        """Restore all settings for main window."""
        logger.debug("Restoring all application settings...")

        # Window geometry
        self.restore_window_geometry(main_window)

        # Apply view settings
        view_mode = self.get_view_mode()
        if hasattr(main_window, "wav_viewer"):
            # todo
            try:
                main_window.wav_viewer.set_view_mode(view_mode)
                if view_mode == "mono":
                    main_window.wav_viewer.mono_radio.setChecked(True)
                elif view_mode == "per-kanaal":
                    main_window.wav_viewer.stereo_radio.setChecked(True)
                elif view_mode == "overlay":
                    main_window.wav_viewer.overlay_radio.setChecked(True)

            except Exception as e:
                logger.warning(f"Could not restore view mode: {e}")

        saved_theme = self.get_theme()
        main_window.current_theme = saved_theme

        # Theme toepassen via command interface
        if saved_theme == "dark":
            main_window.view_commands["apply_dark_theme"]()
        elif saved_theme == "macos_dark":
            main_window.view_commands["apply_macos_dark_theme"]()
        else:
            main_window.view_commands["apply_light_theme"]()

        # mouse_preset = self.get_mouse_labels_preset("performance")
        mouse_preset = self.get_mouse_labels_preset("performance")
        print(mouse_preset)

        if hasattr(main_window, "wav_viewer"):
            try:
                if mouse_preset == "minimal":
                    main_window.wav_viewer.set_mouse_labels_minimal()
                elif mouse_preset == "professional":
                    main_window.wav_viewer.set_mouse_labels_professional()
                elif mouse_preset == "performance":
                    main_window.wav_viewer.set_mouse_labels_performance()
                elif mouse_preset == "professional_advanced":
                    main_window.wav_viewer.set_mouse_labels_professional_advanced()

            except Exception as e:
                logger.warning(f"Could not restore mouse labels preset: {e}")

        # Apply audio settings
        volume = self.get_volume()
        if hasattr(main_window, "wav_viewer") and hasattr(
            main_window.wav_viewer, "audio_player"
        ):
            try:
                main_window.wav_viewer.audio_player.set_volume(volume)
            except Exception as e:
                logger.warning(f"Could not restore audio settings: {e}")

        # # Store UI preferences in main window
        # main_window.show_mouse_labels = self.get_show_mouse_labels()
        # main_window.confirm_delete = self.get_confirm_delete()
        # main_window.auto_save_tags = self.get_auto_save_tags()

        logger.debug("All settings restored successfully")

    def save_all_settings(self, main_window):
        """Save all current settings from main window."""
        logger.debug("Saving all application settings...")

        # Window geometry
        self.save_window_geometry(main_window)

        # View settings
        if hasattr(main_window, "wav_viewer"):
            view_mode = getattr(main_window.wav_viewer, "view_mode", "per-kanaal")
            self.save_view_settings(view_mode)

        current_theme = getattr(main_window, 'current_theme', 'light')
        self.save_theme_settings(current_theme)

        # current_mouse_preset = getattr(main_window.wav_viewer, "_current_mouse_mode", "performance")
        # self.settings.setValue("view/mouse_labels_preset", current_mouse_preset)
        current_preset = getattr(main_window.wav_viewer, "_current_mouse_mode", "performance")
        current_config = main_window.wav_viewer.get_mouse_label_config()
        self.save_mouse_labels_preset(current_preset, current_config)

        # Audio settings
        if hasattr(main_window, "wav_viewer") and hasattr(
            main_window.wav_viewer, "audio_player"
        ):
            try:
                volume = main_window.wav_viewer.audio_player.get_volume()
                self.save_audio_settings(volume)
            except Exception as e:
                logger.warning(f"Could not save audio settings: {e}")

        # # UI preferences
        # show_mouse_labels = getattr(main_window, 'show_mouse_labels', True)
        # confirm_delete = getattr(main_window, 'confirm_delete', True)
        # auto_save_tags = getattr(main_window, 'auto_save_tags', True)
        # self.save_ui_preferences(show_mouse_labels, confirm_delete, auto_save_tags)
        self.settings.sync()  # forceer flush

        logger.debug("All settings saved successfully")
