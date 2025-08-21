"""Settings Manager Module for TimbrosaField Application.

This module provides centralized settings management for the TimbrosaField audio
analysis application. It handles persistent storage and retrieval of all application
settings including window geometry, view preferences, audio settings, UI preferences,
and theme configurations using Qt's QSettings system.

The SettingsManager class encapsulates all settings operations and provides a clean
interface for saving and restoring application state across sessions. It supports
automatic fallbacks for first-time runs and graceful handling of missing or
corrupted settings.

Key features:
- Window geometry persistence
- View mode and display preferences
- Audio playback settings
- Theme and UI customizations
- Mouse label preset configurations
- Automatic first-run initialization

Typical usage:
    settings = SettingsManager()
    settings.restore_all_settings(main_window)
    # ... application usage ...
    settings.save_all_settings(main_window)
"""

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
    """Centralized settings management system for the TimbrosaField application.

    This class provides a comprehensive interface for persisting and restoring all
    application settings using Qt's QSettings system. It manages window geometry,
    view preferences, audio settings, theme configurations, and UI customizations
    across application sessions.

    The manager organizes settings into logical categories:
    - Window settings: Geometry, position, and size
    - View settings: Display modes, themes, and panel visibility
    - Audio settings: Volume levels and playback preferences
    - UI preferences: Mouse labels, confirmations, and behavior

    All settings are stored persistently using the system's native settings
    storage (registry on Windows, preferences on macOS, config files on Linux).

    Attributes:
        settings (QSettings): Qt settings instance for persistent storage.
    """

    def __init__(self):
        """Initialize the SettingsManager with Qt settings backend.

        Creates a QSettings instance using the application's default settings
        format and location. The settings will be stored in the system's
        standard location for application preferences.

        Note:
            The QSettings instance uses the application name and organization
            name set in the main application for proper settings scoping.
        """
        self.settings = QSettings()
        logger.debug("SettingsManager initialized")

    # ========== WINDOW SETTINGS ==========

    def save_window_geometry(self, window):
        """Save the current window geometry and state to persistent storage.

        Captures and stores the window's size, position, and state (maximized,
        minimized, etc.) so it can be restored in future application sessions.

        Args:
            window (QMainWindow): The main window whose geometry should be saved.
                                 Must be a QMainWindow or compatible widget with
                                 saveGeometry() method.

        Note:
            The geometry is saved as a binary blob that includes window size,
            position, maximized state, and other window-specific properties.
        """
        self.settings.setValue("window/geometry", window.saveGeometry())
        logger.debug("Window geometry saved")

    def restore_window_geometry(self, window):
        """Restore previously saved window geometry or center window on first run.

        Attempts to restore the window to its previously saved size, position,
        and state. If no saved geometry exists (first run), centers the window
        on screen with default dimensions.

        Args:
            window (QMainWindow): The main window to restore geometry for.
                                 Must support restoreGeometry() method.

        Returns:
            bool: True if geometry was successfully restored from saved settings,
                  False if this is a first run and window was centered with defaults.

        Note:
            For first-time runs, the window is set to 1400x900 pixels and
            centered on the primary display.
        """
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
        """Center the window on the primary screen with default dimensions.

        Sets the window to a default size and positions it in the center of
        the primary display. Used for first-time application runs when no
        saved geometry is available.

        Args:
            window (QWidget): The window widget to center and resize.
                             Must support resize() and move() methods.

        Note:
            Default window size is set to 1400x900 pixels, which provides
            a good balance for audio analysis tasks on most displays.
        """
        window.resize(1400, 900)
        screen = QDesktopWidget().screenGeometry()
        size = window.geometry()
        window.move(
            (screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2
        )

    # ========== VIEW SETTINGS ==========

    def save_view_settings(self, view_mode, show_metadata=True):
        """Save view and display configuration settings.

        Persists the current view mode and metadata panel visibility settings
        for restoration in future application sessions.

        Args:
            view_mode (str): Current waveform display mode. Common values:
                           - "mono": Single channel view
                           - "per_kanaal": Per-channel stereo view
                           - "overlay": Overlaid stereo channels
            show_metadata (bool, optional): Whether metadata panels are visible.
                                          Defaults to True.

        Note:
            These settings affect the main waveform display and information
            panel visibility in the application interface.
        """
        self.settings.setValue("view/waveform_mode", view_mode)
        self.settings.setValue("view/show_metadata", show_metadata)
        logger.debug(f"View settings saved: {view_mode}")
        logger.debug(f"View settings saved: {show_metadata}")

    def get_view_mode(self, default="per-kanaal"):
        """Retrieve the saved waveform display mode setting.

        Args:
            default (str, optional): Fallback value if no saved setting exists.
                                   Defaults to "per-kanaal" (stereo per-channel view).

        Returns:
            str: The saved view mode identifier, or the default value if no
                 setting has been saved previously.

        Note:
            Common return values include "mono", "per_kanaal", and "overlay".
        """
        return self.settings.value("view/waveform_mode", default)

    def get_show_metadata(self, default=True):
        """Retrieve the saved metadata panel visibility setting.

        Args:
            default (bool, optional): Fallback value if no saved setting exists.
                                    Defaults to True (panels visible).

        Returns:
            bool: True if metadata panels should be visible, False if hidden.
                  Returns default value if no setting has been saved.

        Note:
            This setting affects the visibility of format, broadcast extension,
            and info metadata tables in the main interface.
        """
        return self.settings.value("view/show_metadata", default, type=bool)

    def get_mouse_labels_preset(self, default="performance"):
        """Retrieve the saved mouse label information preset.

        Args:
            default (str, optional): Fallback preset if no saved setting exists.
                                   Defaults to "performance" for balanced functionality.

        Returns:
            str: The saved mouse label preset identifier. Common values:
                 - "minimal": Essential info only, best performance
                 - "performance": Balanced info and performance
                 - "professional": Complete professional audio info
                 - "professional_advanced": All features including analysis

        Note:
            Mouse label presets control the amount and type of information
            displayed in hover tooltips over waveform plots.
        """
        preset = self.settings.value("view/mouse_labels_preset", default)
        return preset

    def save_mouse_labels_preset(self, preset, config):
        """Save the current mouse label preset configuration.

        Persists the mouse label preset setting for restoration in future sessions.
        The configuration parameter is reserved for future extensibility.

        Args:
            preset (str): Mouse label preset identifier to save. Should be one of:
                         "minimal", "performance", "professional", "professional_advanced".
            config: Reserved for future use. Configuration details for the preset.
                   Currently not used but maintained for API compatibility.

        Note:
            Only the preset identifier is currently persisted. The config parameter
            is included for future extensibility when custom preset configurations
            may be supported.
        """
        self.settings.setValue("view/mouse_labels_preset", preset)
        logger.debug(f"Mouse labels preset saved: {preset}")

    def save_theme_settings(self, theme_name="light"):
        """Save the current application theme preference.

        Persists the theme setting so the application can restore the user's
        preferred appearance in future sessions.

        Args:
            theme_name (str, optional): Theme identifier to save. Defaults to "light".
                                      Common values:
                                      - "light": Standard light theme
                                      - "dark": Dark mode theme
                                      - "macos_dark": macOS-style dark theme

        Note:
            Theme changes affect the overall application appearance including
            backgrounds, text colors, and UI element styling.
        """
        self.settings.setValue("ui/theme", theme_name)
        logger.debug(f"Theme setting saved: {theme_name}")

    def get_theme(self, default="light"):
        """Retrieve the saved application theme preference.

        Args:
            default (str, optional): Fallback theme if no saved setting exists.
                                   Defaults to "light" theme.

        Returns:
            str: The saved theme identifier, or the default value if no theme
                 has been previously saved. Common values include "light",
                 "dark", and "macos_dark".

        Note:
            The returned theme name should match one of the supported theme
            identifiers in the application's theme system.
        """
        return self.settings.value("ui/theme", default)

    # ========== AUDIO SETTINGS ==========

    def save_audio_settings(self, volume, auto_play=False, seek_step=10):
        """Save audio playback configuration settings.

        Persists audio-related settings for restoration in future sessions.
        Currently only volume is actively saved; other parameters are reserved
        for future functionality.

        Args:
            volume (int): Audio volume level to save (typically 0-100).
            auto_play (bool, optional): Reserved for future auto-play functionality.
                                      Defaults to False. Currently not persisted.
            seek_step (int, optional): Reserved for future seek step configuration.
                                     Defaults to 10 seconds. Currently not persisted.

        Note:
            Only the volume parameter is currently persisted to settings.
            The auto_play and seek_step parameters are included for future
            extensibility but are not yet implemented in the settings system.
        """
        self.settings.setValue("audio/volume", volume)
        # self.settings.setValue("audio/auto_play", auto_play)
        # self.settings.setValue("audio/seek_step_seconds", seek_step)
        logger.debug(f"Audio settings saved: volume={volume}")

    def get_volume(self, default=70):
        """Retrieve the saved audio volume level.

        Args:
            default (int, optional): Fallback volume level if no saved setting exists.
                                   Defaults to 70 (70% volume).

        Returns:
            int: The saved volume level as an integer (typically 0-100),
                 or the default value if no volume has been previously saved.

        Note:
            Volume levels are stored as integers with 0 representing mute
            and 100 representing maximum volume. The default of 70 provides
            a reasonable starting volume for most users.
        """
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
        """Restore all saved settings to the main window and its components.

        This comprehensive method restores all categories of settings from persistent
        storage and applies them to the appropriate components of the main window.
        It handles window geometry, view modes, themes, mouse label presets, and
        audio settings with graceful error handling for missing components.

        Args:
            main_window: The main application window to restore settings to.
                        Must have the following attributes/components available:
                        - wav_viewer: For view mode and audio player settings
                        - view_commands: For theme application
                        - current_theme: For theme state tracking

        Settings restored:
        - Window geometry and position
        - Waveform display mode (mono, stereo, overlay)
        - Application theme (light, dark, macOS dark)
        - Mouse label preset configuration
        - Audio volume level

        Note:
            All setting applications are wrapped in try-catch blocks to handle
            cases where components may not be fully initialized. Warnings are
            logged for any settings that cannot be applied.
        """
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
        logger.debug(f"Mouse labels preset loaded: {mouse_preset}")

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
        """Save all current application settings from the main window state.

        This comprehensive method captures the current state of all application
        settings from the main window and its components, persisting them for
        restoration in future sessions. It handles window geometry, view preferences,
        theme settings, audio configuration, and UI preferences.

        Args:
            main_window: The main application window to save settings from.
                        Settings are extracted from various window attributes:
                        - Window geometry via saveGeometry()
                        - wav_viewer for view mode and audio settings
                        - current_theme for theme preference
                        - _current_mouse_mode for mouse label preset

        Settings saved:
        - Window size, position, and state
        - Current waveform display mode
        - Active theme selection
        - Mouse label preset configuration
        - Audio volume level

        Note:
            After saving all settings, sync() is called to ensure immediate
            persistence to storage. Audio settings extraction is wrapped in
            error handling for cases where the audio player is not available.
        """
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
        current_preset = getattr(
            main_window.wav_viewer, "_current_mouse_mode", "performance"
        )
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
        self.settings.sync()  # Force immediate write to persistent storage

        logger.debug("All settings saved successfully")
