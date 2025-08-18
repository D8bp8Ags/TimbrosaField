#!/usr/bin/env python3
"""Entry point for the Field Recorder Analyzer application.

This module launches the Qt application and defines :class:`MainWindow`, which wires
together managers (file, export, dialogs, UI, etc.) and the central :class:`WavViewer`.
Public methods include PEP 257-compliant (Google-style) docstrings. Comments and user-
facing strings are standardized to English.

Typical usage::

if __name__ == "__main__":     main()
"""

# from __future__ import annotations

import logging
import os
import sys

import app_config
from batch_tageditor import BatchTagEditor
from cuepoints_manager import CuePointsAnalysisDialog
from dialog_manager import DialogManager
from export_manager import ExportManagerInterface
from file_manager import FileManagerInterface
from global_manager import GlobalShortcutManager
from menu_system import MenuBarManager
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QShortcut
from settings_manager import SettingsManager
from tag_completer import TemplateManager, TemplateManagerDialog
from ui_components import UIComponentManager
from user_config_manager import TagEditor
from wav_viewer import WavViewer

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window that coordinates all managers and UI components. This window hosts.

    :class:`WavViewer` as the central widget and exposes command dictionaries
    (file/edit/view/audio/analysis/help/ui) consumed by menus and shortcuts.

    Attributes:
        settings_manager: Persists/restores window settings.
        wav_viewer: Central widget for audio visualization.
        dialog_manager: Dialog orchestration.
        ui_manager: Status bar and general UI helpers.
        file_manager: File operations abstraction.
        export_manager: Export-related operations.
        shortcut_manager: Global shortcuts binding.
        menu_manager: Menu bar setup and actions.
        cuepoints_manager: Cue points analysis UI.
        user_config_manager: User configuration editor.
        template_manager: Tag/template management.
    """

    def __init__(self) -> None:
        """Initialize the main window and construct all managers."""
        super().__init__()

        # Window properties
        self.setWindowTitle(app_config.APP_NAME)

        # Core widgets
        self.wav_viewer = WavViewer()
        self.setCentralWidget(self.wav_viewer)

        # Managers in dependency order:
        # - DialogManager: no external dependencies
        # - UIComponentManager: status bar early
        # - FileManagerInterface: independent
        # - ExportManagerInterface: uses file/ui
        # - MenuBarManager: needs everything to be present
        # - GlobalShortcutManager: binds to command interface
        # - CuePointsAnalysisDialog / TagEditor / TemplateManager: feature UIs
        self.settings_manager = SettingsManager()
        self.dialog_manager = DialogManager(self)
        self.ui_manager = UIComponentManager(self)
        self.file_manager = FileManagerInterface(self)
        self.export_manager = ExportManagerInterface(self)

        # Commands used by menus/shortcuts
        self._setup_command_interface()

        self.shortcut_manager = GlobalShortcutManager(self)
        self.shortcut_manager.setup_all_shortcuts()

        self.menu_manager = MenuBarManager(self)
        self.cuepoints_manager = CuePointsAnalysisDialog(self)
        self.user_config_manager = TagEditor(self)
        self.template_manager = TemplateManager()

        # Initialize UI systems and restore settings
        self._initialize_all_systems()
        self.settings_manager.restore_all_settings(self)
        logger.info("MainWindow initialized.")

    # ---------------------------------------------------------------------
    # Bootstrapping
    # ---------------------------------------------------------------------
    def _initialize_all_systems(self) -> None:
        """Initialize menu system and status UI."""
        logger.debug("Initializing manager systems…")
        self.menu_manager.setup_all_menus()
        self.ui_manager.update_file_count()
        logger.debug("All systems initialized.")

    def _setup_command_interface(self) -> None:
        """Define command dictionaries used by menus and keyboard shortcuts.

        Creates comprehensive command mappings for all major application functions:
        - File operations (open, import, export, etc.)
        - Edit operations (tags, templates, configuration.)
        - View controls (zoom, panels, display modes.)
        - Audio playback controls
        - Analysis tools and help dialogs

        Long-running operations are automatically wrapped with progress indicators
        using the internal with_progress helper function.
        """

        def with_progress(func, message: str):
            """Wrap a function with a transient progress indicator.

            Args:
                func: Callable to execute with progress indication.
                message: Status message displayed while the function runs.

            Returns:
                Callable: Wrapper function that shows/hides progress and forwards
                         the original function call with all arguments.

            Note:
                The wrapper automatically shows progress before execution,
                hides it after completion, and displays a success message
                if the function returns a truthy value.
            """

            def wrapper(*args, **kwargs):
                self.ui_manager.show_progress(message, 0)
                try:
                    result = func(*args, **kwargs)
                    if result:
                        brief = message.replace("Loading", "Loaded").replace("…", "")
                        self.show_status_message(f"{brief}", 1500)
                    return result
                finally:
                    self.ui_manager.hide_progress()

            return wrapper

        # File commands
        self.file_commands = {
            "reload_directory": with_progress(
                self._reload_directory, "Loading directory…"
            ),
            "batch_import_files": with_progress(
                self._batch_import_files, "Importing files…"
            ),
            "export_to_ableton": with_progress(
                self._export_to_ableton, "Exporting to Ableton…"
            ),
            "export_metadata_csv": with_progress(
                self._export_metadata_csv, "Exporting metadata…"
            ),
            "refresh_file_list": with_progress(
                self._refresh_file_list, "Refreshing files…"
            ),
            # Dialogs / quick actions
            "open_directory": self._open_directory,
            "exit_application": self._exit_application,
            "get_recent_directories": self._get_recent_directories,
            "load_directory": self._load_recent_directory,
            "remove_recent_directory": self._remove_recent_directory,
        }

        # Edit commands
        self.edit_commands = {
            "clear_tags": self._clear_tags,
            "reset_defaults": self._reset_to_defaults,
            "open_batch_tagger": self._open_batch_tagger,
            "open_template_manager": self._open_template_manager,
            "open_user_config_manager": self._open_user_config_manager,
        }

        # View commands
        self.view_commands = {
            "set_waveform_mode": self._set_waveform_mode,
            "zoom_in": self._zoom_in,
            "zoom_out": self._zoom_out,
            "zoom_fit": self._zoom_fit_to_window,
            "toggle_metadata": self._toggle_metadata_panel,
            "toggle_frequency": self._toggle_frequency_analysis,
            "toggle_timecode": self._toggle_timecode_format,
            "set_mouse_labels_minimal": self._set_mouse_labels_minimal,
            "set_mouse_labels_performance": self._set_mouse_labels_performance,
            "set_mouse_labels_professional": self._set_mouse_labels_professional,
        }

        # Audio commands
        self.audio_commands = {
            "play_pause": self._audio_play_pause,
            "stop": self._audio_stop,
            "volume_up": self._audio_volume_up,
            "volume_down": self._audio_volume_down,
            "toggle_mute": self._audio_toggle_mute,
            "seek_forward": self._audio_seek_forward,
            "seek_backward": self._audio_seek_backward,
        }

        # Analysis commands
        self.analysis_commands = {
            "show_analytics": with_progress(
                self._show_analytics_dashboard, "Loading analytics…"
            ),
            "show_cue_analysis": with_progress(
                self._show_cue_analysis, "Analyzing cue points…"
            ),
        }

        # Help commands
        self.help_commands = {
            "show_help_and_quickstart": self._show_help_and_quickstart,
            "show_keyboard_shortcuts": self._show_keyboard_shortcuts,
            "show_about": self._show_about,
        }

        # UI commands
        self.ui_commands = {
            "update_file_count": self._ui_update_file_count,
            "get_file_count": self._ui_get_file_count,
        }

    # ---------------------------------------------------------------------
    # File menu handlers
    # ---------------------------------------------------------------------
    def _open_directory(self) -> bool:
        """Open a directory dialog and load the selected directory.

        Uses the file manager to present a directory selection dialog to the user.
        If a directory is selected, updates the user configuration and refreshes
        the WAV file list to display the new directory contents.

        Returns:
            bool: True if directory was successfully opened and loaded,
                  False otherwise.
        """
        success = self.file_manager.open_directory()
        if success:
            new_dir = self.user_config_manager.get_updated_config()["paths"][
                "fieldrecording_dir"
            ]
            self.wav_viewer.user_config["paths"]["fieldrecording_dir"] = new_dir
            self._refresh_file_list()
        return bool(success)

    def _reload_directory(self) -> bool:
        """Reload the currently opened directory and refresh the file list.

        Re-scans the current directory for WAV files, useful when files have
        been added, removed, or modified outside the application.

        Returns:
            bool: True if directory was successfully reloaded, False otherwise.
        """
        success = self.file_manager.reload_directory()
        if success:
            self._refresh_file_list()
        return bool(success)

    def _batch_import_files(self) -> bool:
        """Import multiple audio files in a single batch operation.

        Presents a file selection dialog allowing the user to select multiple
        WAV files for import. After successful import, refreshes the file list
        to display the newly imported files.

        Returns:
            bool: True if files were successfully imported, False otherwise.
        """
        success = self.file_manager.batch_import_files()
        if success:
            self._refresh_file_list()
        return bool(success)

    def _export_to_ableton(self) -> bool:
        """Export the current WAV files to Ableton Live project format.

        Creates an Ableton Live .als project file containing the currently
        loaded WAV files organized by their metadata tags and categories.

        Returns:
            bool: True if export was successful, False otherwise.
        """
        return bool(self.export_manager.export_to_ableton())

    def _export_metadata_csv(self) -> bool:
        """Export metadata from all loaded WAV files to a CSV file.

        Creates a CSV file containing comprehensive metadata for all currently
        loaded WAV files, including technical specifications, tags, and analysis data.

        Returns:
            bool: True if CSV export was successful, False otherwise.
        """
        return bool(self.export_manager.export_metadata_csv())

    def _get_recent_directories(self) -> list[str]:
        """Get the list of recently accessed directories.

        Returns:
            List[str]: List of directory paths that have been recently opened
                      by the user, ordered from most recent to oldest.
                      Returns empty list if error occurs.
        """
        try:
            return self.file_manager.get_recent_directories()
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error getting recent directories: {exc}", 3000)
            return []

    def _load_recent_directory(self, directory: str) -> bool:
        """Load a directory from the recent directories list.

        Args:
            directory: Path to the directory to load from recent history.

        Returns:
            bool: True if directory was successfully loaded, False otherwise.

        Note:
            Updates the user configuration and refreshes the file list after
            successful loading.
        """
        loader = self.file_manager.file_manager.directory_loader
        success = loader._load_directory(directory)  # noqa: SLF001
        if success:
            new_dir = self.user_config_manager.get_updated_config()["paths"][
                "fieldrecording_dir"
            ]
            self.wav_viewer.user_config["paths"]["fieldrecording_dir"] = new_dir
            self._refresh_file_list()
        return bool(success)

    def _remove_recent_directory(self, directory: str) -> bool:
        """Remove a directory from the recent directories list.

        Args:
            directory: Path of the directory to remove from recent history.

        Returns:
            bool: True if directory was successfully removed, False otherwise.
        """
        try:
            rm = self.file_manager.file_manager.recent_manager
            rm.remove_recent_directory(directory)
            return True
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error removing recent directory: {exc}", 3000)
            return False

    def _refresh_file_list(self) -> bool:
        """Refresh the WAV file list display in the main viewer.

        Re-scans the current directory and updates the file list widget to
        show any changes. This is called after directory operations to
        ensure the UI reflects the current file system state.

        Returns:
            bool: True if file list was successfully refreshed, False otherwise.
        """
        try:
            if hasattr(self.wav_viewer, "load_wav_files"):
                self.wav_viewer.load_wav_files()
                return True
            self.show_status_message("File list refresh not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error refreshing file list: {exc}", 3000)
            return False

    def _exit_application(self) -> bool:
        """Prompt user for confirmation and exit the application if approved.

        Displays a confirmation dialog with platform-appropriate keyboard shortcuts.
        If the user confirms, closes the application and saves all settings.

        Returns:
            bool: True if application was closed, False if user cancelled.

        Note:
            Sets up temporary keyboard shortcuts for the confirmation dialog:
            - Cmd/Ctrl+Q to confirm exit
            - Cmd/Ctrl+. to cancel (macOS style)
        """
        try:
            msg = QMessageBox(self)
            msg.setWindowTitle("Exit Application")
            msg.setText("Are you sure you want to quit?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)

            # Platform-friendly shortcuts
            QShortcut(
                QKeySequence.Quit, msg, activated=lambda: msg.done(QMessageBox.Yes)
            )
            QShortcut(
                QKeySequence("Meta+."), msg, activated=lambda: msg.done(QMessageBox.No)
            )

            result = msg.exec_()
            if result == QMessageBox.Yes:
                self.close()
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Exit error: {exc}", 3000)
            return False

    # ---------------------------------------------------------------------
    # Edit menu handlers
    # ---------------------------------------------------------------------
    def _clear_tags(self) -> bool:
        """Clear all tags in the current tagger widget.

        Removes all tag entries from the tagger interface, providing a quick
        way to start fresh with tag assignment.

        Returns:
            bool: True if tags were successfully cleared, False if tagger
                  not available or operation failed.
        """
        try:
            if hasattr(self.wav_viewer, "tagger_widget"):
                self.wav_viewer.tagger_widget.clear_tags()
                self.show_status_message("Tags cleared", 2000)
                return True
            self.show_status_message("Tagger not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error clearing tags: {exc}", 3000)
            return False

    def _reset_to_defaults(self) -> bool:
        """Reset INFO metadata table to default values.

        Restores the INFO metadata table to sensible default values,
        useful for clearing out unwanted or incorrect metadata.

        Returns:
            bool: True if reset was successful, False if reset function
                  not available or operation failed.
        """
        try:
            if hasattr(self.wav_viewer, "_reset_info_table_to_defaults"):
                self.wav_viewer._reset_info_table_to_defaults()  # noqa: SLF001
                self.show_status_message("Reset to defaults", 2000)
                return True
            self.show_status_message("Reset function not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error resetting: {exc}", 3000)
            return False

    def _open_batch_tagger(self) -> bool:
        """Open the batch tag editor dialog for mass tag operations.

        Launches a dialog that allows applying tags to multiple WAV files
        simultaneously. Requires at least one WAV file to be loaded.

        Returns:
            bool: True if batch tagging was completed successfully,
                  False if cancelled or no files available.

        Note:
            Shows an information dialog if no WAV files are currently loaded.
        """
        try:
            wav_files = self.file_manager.get_all_wav_files()
            if not wav_files:
                QMessageBox.information(self, "No files", "No WAV files found.")
                return False

            dialog = BatchTagEditor(self, wav_files)
            result = dialog.exec_()
            if result == dialog.Accepted:
                self.show_status_message("Batch tagging completed", 3000)
                return True
            self.show_status_message("Batch tagging cancelled", 2000)
            return False
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Error opening batch tagger: {exc}"
            self.show_status_message(error_msg, 5000)
            QMessageBox.critical(self, "Error", error_msg)
            return False

    def _open_template_manager(self) -> bool:
        """Open the tag template manager dialog.

        Launches a dialog for creating, editing, and managing tag templates
        that can be quickly applied to files during tagging workflows.

        Returns:
            bool: True if template manager completed successfully,
                  False if cancelled or error occurred.
        """
        try:
            dialog = TemplateManagerDialog(self)
            result = dialog.exec_()
            if result == dialog.Accepted:
                self.show_status_message("Template manager updated", 2000)
                return True
            self.show_status_message("Template manager cancelled", 2000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error opening template manager: {exc}", 5000)
            return False

    def _open_user_config_manager(self) -> bool:
        """Open the user configuration editor dialog.

        Launches the configuration editor where users can modify application
        settings, file paths, and preferences. If changes are accepted,
        automatically reloads the configuration and refreshes the file list.

        Returns:
            bool: True if configuration was updated successfully,
                  False if cancelled or configuration manager unavailable.
        """
        try:
            if not hasattr(self, "user_config_manager"):
                self.show_status_message("User config manager not available", 3000)
                return False

            result = self.user_config_manager.exec_()
            if result == self.user_config_manager.Accepted:
                if hasattr(self.wav_viewer, "load_user_config"):
                    self.wav_viewer.user_config = self.wav_viewer.load_user_config()
                    self.wav_viewer.load_wav_files()
                self.show_status_message("Configuration updated", 3000)
                return True
            self.show_status_message("Configuration cancelled", 2000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Could not open user config: {exc}", 5000)
            return False

    # ---------------------------------------------------------------------
    # View menu handlers
    # ---------------------------------------------------------------------
    def _set_waveform_mode(self, mode: str) -> bool:
        """Set the waveform visualization display mode.

        Args:
            mode: Display mode string (e.g., "overlay", "per_channel", "stereo").
                  Available modes depend on the WavViewer implementation.

        Returns:
            bool: True if mode was successfully set, False if WavViewer
                  doesn't support mode switching.
        """
        if hasattr(self.wav_viewer, "set_view_mode"):
            self.wav_viewer.set_view_mode(mode)
            self.show_status_message(f"Waveform mode: {mode}", 2000)
            return True
        return False

    def _zoom_in(self) -> bool:
        """Zoom in on all waveform plots by reducing the visible time range.

        Reduces the visible time range by 50% while keeping the center point
        constant. Affects all waveform plot widgets simultaneously.

        Returns:
            bool: True if zoom operation was successful, False if plots
                  not available or operation failed.
        """
        try:
            plots = [
                self.wav_viewer.waveform_plot,
                self.wav_viewer.waveform_plot_top,
                self.wav_viewer.waveform_plot_bottom,
            ]
            for plot in plots:
                if hasattr(plot, "getViewBox"):
                    vb = plot.getViewBox()
                    x0, x1 = vb.viewRange()[0]
                    center = (x0 + x1) / 2
                    width = (x1 - x0) * 0.5
                    vb.setXRange(center - width / 2, center + width / 2, padding=0)
            self.show_status_message("Zoomed in", 1000)
            return True
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Zoom error: {exc}", 3000)
            return False

    def _zoom_out(self) -> bool:
        """Zoom out on all waveform plots by expanding the visible time range.

        Doubles the visible time range while keeping the center point constant.
        Respects the total audio duration to avoid zooming beyond the actual
        audio content. Affects all waveform plot widgets simultaneously.

        Returns:
            bool: True if zoom operation was successful, False if plots
                  not available or operation failed.
        """
        try:
            plots = [
                self.wav_viewer.waveform_plot,
                self.wav_viewer.waveform_plot_top,
                self.wav_viewer.waveform_plot_bottom,
            ]
            for plot in plots:
                if hasattr(plot, "getViewBox"):
                    vb = plot.getViewBox()
                    x0, x1 = vb.viewRange()[0]
                    center = (x0 + x1) / 2
                    width = (x1 - x0) * 2.0
                    if getattr(self.wav_viewer, "audio_duration", None):
                        max_w = self.wav_viewer.audio_duration
                        width = min(width, max_w)
                        start = max(0, center - width / 2)
                        end = min(max_w, center + width / 2)
                        vb.setXRange(start, end, padding=0)
                    else:
                        vb.setXRange(center - width / 2, center + width / 2, padding=0)
            self.show_status_message("Zoomed out", 1000)
            return True
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Zoom error: {exc}", 3000)
            return False

    def _zoom_fit_to_window(self) -> bool:
        """Fit the entire audio duration into the visible plot area.

        Adjusts all waveform plots to show the complete audio file from
        start to finish. Only works when audio content is loaded.

        Returns:
            bool: True if fit operation was successful, False if no audio
                  loaded or operation failed.
        """
        try:
            if getattr(self.wav_viewer, "audio_duration", None):
                duration = self.wav_viewer.audio_duration
                plots = [
                    self.wav_viewer.waveform_plot,
                    self.wav_viewer.waveform_plot_top,
                    self.wav_viewer.waveform_plot_bottom,
                ]
                for plot in plots:
                    if hasattr(plot, "getViewBox"):
                        plot.getViewBox().setXRange(0, duration, padding=0)
                self.show_status_message("Fit to window", 1000)
                return True
            self.show_status_message("No audio loaded for zoom fit", 2000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Zoom error: {exc}", 3000)
            return False

    def _toggle_metadata_panel(self, visible: bool) -> bool:
        """Show or hide the metadata information panels.

        Args:
            visible: True to show metadata panels, False to hide them.

        Returns:
            bool: True if panel visibility was successfully changed,
                  False if operation failed.

        Note:
            Affects all metadata display widgets including format (fmt),
            broadcast extension (bext), and info tables and their labels.
        """
        try:
            tables = ["fmt_table", "bext_table", "info_table"]
            labels = ["fmt_label", "bext_label", "info_label"]
            for name in tables:
                if hasattr(self.wav_viewer, name):
                    getattr(self.wav_viewer, name).setVisible(visible)
            for name in labels:
                if hasattr(self.wav_viewer, name):
                    getattr(self.wav_viewer, name).setVisible(visible)
            status = "shown" if visible else "hidden"
            self.show_status_message(f"Metadata panel {status}", 2000)
            return True
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error toggling metadata: {exc}", 3000)
            return False

    def _toggle_frequency_analysis(self, enabled: bool) -> bool:
        """Enable or disable real-time frequency spectrum analysis.

        Args:
            enabled: True to enable frequency analysis, False to disable.

        Returns:
            bool: True if frequency analysis setting was successfully changed,
                  False if WavViewer doesn't support frequency analysis.
        """
        try:
            if hasattr(self.wav_viewer, "toggle_frequency_analysis"):
                self.wav_viewer.toggle_frequency_analysis(enabled)
                status = "enabled" if enabled else "disabled"
                self.show_status_message(f"Frequency analysis {status}", 2000)
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error toggling frequency analysis: {exc}", 3000)
            return False

    def _toggle_timecode_format(self, enabled: bool) -> bool:
        """Toggle between timecode and default time format for mouse labels.

        Args:
            enabled: True to show timecode format (HH:MM:SS:FF),
                    False for default decimal seconds.

        Returns:
            bool: True if timecode format was successfully changed,
                  False if WavViewer doesn't support timecode display.
        """
        try:
            if hasattr(self.wav_viewer, "configure_mouse_labels"):
                self.wav_viewer.configure_mouse_labels(show_timecode=enabled)
                status = "enabled" if enabled else "disabled"
                self.show_status_message(f"Timecode format {status}", 2000)
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error toggling timecode: {exc}", 3000)
            return False

    def _set_mouse_labels_minimal(self) -> bool:
        """Switch mouse labels to minimal information display mode.

        Configures the mouse hover labels to show only essential information,
        reducing visual clutter for users who prefer a cleaner interface.

        Returns:
            bool: True if minimal mode was successfully activated,
                  False if WavViewer doesn't support this preset.
        """
        try:
            if hasattr(self.wav_viewer, "set_mouse_labels_minimal"):
                self.wav_viewer.set_mouse_labels_minimal()
                self.show_status_message("Mouse labels: Minimal mode", 2000)
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error setting minimal mode: {exc}", 3000)
            return False

    def _set_mouse_labels_performance(self) -> bool:
        """Switch mouse labels to performance-oriented information display.

        Configures mouse hover labels to show information most relevant
        for live performance scenarios, such as timing and level information.

        Returns:
            bool: True if performance mode was successfully activated,
                  False if WavViewer doesn't support this preset.
        """
        try:
            if hasattr(self.wav_viewer, "set_mouse_labels_performance"):
                self.wav_viewer.set_mouse_labels_performance()
                self.show_status_message("Mouse labels: Performance mode", 2000)
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error setting performance mode: {exc}", 3000)
            return False

    def _set_mouse_labels_professional(self) -> bool:
        """Switch mouse labels to professional/detailed information display.

        Configures mouse hover labels to show comprehensive technical
        information suitable for professional audio analysis and editing.

        Returns:
            bool: True if professional mode was successfully activated,
                  False if WavViewer doesn't support this preset.
        """
        try:
            if hasattr(self.wav_viewer, "set_mouse_labels_professional"):
                self.wav_viewer.set_mouse_labels_professional()
                self.show_status_message("Mouse labels: Professional mode", 2000)
                return True
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Error setting professional mode: {exc}", 3000)
            return False

    # ---------------------------------------------------------------------
    # Audio menu handlers
    # ---------------------------------------------------------------------
    def _audio_play_pause(self) -> bool:
        """Toggle audio playback between play and pause states.

        If audio is currently playing, pauses playback at the current position.
        If audio is paused or stopped, resumes or starts playback.

        Returns:
            bool: True if playback state was successfully toggled,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.toggle_playback()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Play/pause error: {exc}", 3000)
            return False

    def _audio_stop(self) -> bool:
        """Stop audio playback and return to the beginning.

        Stops any currently playing audio and resets the playback position
        to the start of the audio file.

        Returns:
            bool: True if playback was successfully stopped,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.stop_playback()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Stop error: {exc}", 3000)
            return False

    def _audio_volume_up(self) -> bool:
        """Increase the audio output volume by one increment.

        Raises the volume level using the audio player's default increment.
        Volume changes are typically applied immediately to ongoing playback.

        Returns:
            bool: True if volume was successfully increased,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.volume_up()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Volume up error: {exc}", 3000)
            return False

    def _audio_volume_down(self) -> bool:
        """Decrease the audio output volume by one decrement.

        Lowers the volume level using the audio player's default decrement.
        Volume changes are typically applied immediately to ongoing playback.

        Returns:
            bool: True if volume was successfully decreased,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.volume_down()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Volume down error: {exc}", 3000)
            return False

    def _audio_toggle_mute(self) -> bool:
        """Toggle audio mute state between muted and unmuted.

        If audio is currently muted, unmutes and restores previous volume.
        If audio is unmuted, mutes all output while preserving volume setting.

        Returns:
            bool: True if mute state was successfully toggled,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.toggle_mute()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Mute toggle error: {exc}", 3000)
            return False

    def _audio_seek_forward(self) -> bool:
        """Seek forward in the audio by a small time increment.

        Advances the playback position forward by the audio player's
        default seek increment, typically a few seconds.

        Returns:
            bool: True if seek operation was successful,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.seek_forward()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Seek forward error: {exc}", 3000)
            return False

    def _audio_seek_backward(self) -> bool:
        """Seek backward in the audio by a small time increment.

        Moves the playback position backward by the audio player's
        default seek increment, typically a few seconds.

        Returns:
            bool: True if seek operation was successful,
                  False if audio player not available.
        """
        try:
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.seek_backward()
                return True
            self.show_status_message("Audio player not available", 3000)
            return False
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Seek backward error: {exc}", 3000)
            return False

    # ---------------------------------------------------------------------
    # Analysis & Help
    # ---------------------------------------------------------------------
    def _show_analytics_dashboard(self) -> bool:
        """Open the analytics dashboard for comprehensive file analysis.

        Launches a dialog displaying detailed analytics about the currently
        loaded WAV files, including statistics, metadata summaries, and
        various analysis charts.

        Returns:
            bool: True if analytics dashboard was successfully opened,
                  False if operation failed.
        """
        try:
            return bool(self.export_manager.show_analytics_dashboard())
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Analytics error: {exc}", 3000)
            return False

    def _show_cue_analysis(self):
        """Analyze cue points in loaded files and display the results dialog.

        Performs cue point analysis on all loaded WAV files, then presents
        a dialog with detailed cue point information, statistics, and
        navigation capabilities.

        Returns:
            Union[int, bool]: Dialog result code if successful, False if error occurred.
                             Result depends on dialog implementation (typically QDialog.Accepted/Rejected).
        """
        try:
            self.cuepoints_manager.analyze_cue_points()
            return self.cuepoints_manager.exec_()
        except Exception as exc:  # noqa: BLE001
            self.show_status_message(f"Cue analysis error: {exc}", 3000)
            return False

    def _show_help_and_quickstart(self):
        """Display the help and quickstart guide dialog.

        Shows a comprehensive help dialog containing user documentation,
        quickstart instructions, and guidance for using the application.

        Returns:
            Union[int, bool]: Dialog result if successful, False if dialog manager
                             not available.
        """
        return (
            self.dialog_manager.show_help_and_quickstart()
            if self.dialog_manager
            else False
        )

    def _show_keyboard_shortcuts(self):
        """Display the keyboard shortcuts reference dialog.

        Shows a dialog listing all available keyboard shortcuts organized
        by category (File, Edit, View, Audio, etc.).

        Returns:
            Union[int, bool]: Dialog result if successful, False if dialog manager
                             not available.
        """
        return (
            self.dialog_manager.show_keyboard_shortcuts()
            if self.dialog_manager
            else False
        )

    def _show_about(self):
        """Display the About dialog with application information.

        Shows application version, credits, license information, and
        other relevant details about the software.

        Returns:
            Union[int, bool]: Dialog result if successful, False if dialog manager
                             not available.
        """
        return self.dialog_manager.show_about() if self.dialog_manager else False

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _ui_get_file_count(self) -> int:
        """Get the current count of loaded WAV files.

        Queries the file manager to determine how many WAV files are
        currently loaded and available for analysis.

        Returns:
            int: Number of currently loaded WAV files, or 0 if error occurred.
        """
        try:
            wav_files = self.file_manager.get_all_wav_files()
            return len(wav_files)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error getting file count via file_manager: %s", exc)
            return 0

    def _ui_update_file_count(self) -> bool:
        """Update the status bar display with the current WAV file count.

        Refreshes the status bar to show the accurate number of currently
        loaded WAV files. Called automatically after file operations.

        Returns:
            bool: True if status bar was successfully updated,
                  False if operation failed.
        """
        try:
            count = self._ui_get_file_count()
            self.ui_manager.status_manager.status_bar.update_file_count(count)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("UI update file count error: %s", exc)
            return False

    # ---------------------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------------------
    def show_status_message(self, message: str, timeout: int = 3000) -> None:
        """Display a temporary message in the application status bar.

        Args:
            message: Text message to display to the user.
            timeout: Duration to show the message in milliseconds (default: 3000).
                    Message will automatically disappear after this time.

        Note:
            This is the primary method for providing user feedback about
            operations and status updates throughout the application.
        """
        self.ui_manager.show_message(message, timeout)

    def get_wav_viewer(self) -> WavViewer:
        """Get the central WavViewer widget instance.

        Returns:
            WavViewer: The main audio visualization and analysis widget
                      that serves as the central component of the application.

        Note:
            This provides access to the core functionality for audio file
            loading, visualization, playback, and metadata editing.
        """
        return self.wav_viewer

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Handle window close event by saving settings and accepting closure.

        Args:
            event: Qt close event object.

        Note:
            Automatically saves all user settings and window state before
            allowing the application to close. This ensures user preferences
            are preserved between sessions.
        """
        self.settings_manager.save_all_settings(self)
        event.accept()


def main() -> None:
    """Initialize and run the Field Recorder Analyzer Qt application.

    Creates the QApplication instance, sets up application metadata,
    initializes the main window, and starts the Qt event loop.

    Note:
        This is the main entry point for the application. The function
        will not return until the user closes the application.
    """
    logger.info("Starting Field Recorder Analyzer…")

    app = QApplication(sys.argv)
    app.setApplicationName(app_config.APP_NAME)
    app.setApplicationVersion(app_config.APP_VERSION)
    app.setOrganizationName(app_config.ORG_NAME)

    # Apply application-wide styling if desired:
    # ApplicationStylist.apply_complete_styling(app)

    main_window = MainWindow()
    main_window.show()
    logger.info("Field Recorder Analyzer started.")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
