"""
Menu System Module for Field Recorder Analyzer - UPDATED.

This module extracts all menu functionality from MainWindow with proper delegation to
specialized managers. Updated for Phase 4 with FileManager delegation and proper logging
throughout.

Phase 2-4 of MainWindow refactoring - removes ~400 lines from main.py
"""

import logging
import os

# from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QActionGroup

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


class MenuBarManager:
    """Main coordinator for all menu systems.

    This class sets up the menu bar and coordinates between different menu handlers
    while keeping MainWindow clean.
    """

    def __init__(self, main_window):
        """Initialize menu bar manager with reference to main window."""
        self.main_window = main_window
        #        self.wav_viewer = main_window.wav_viewer

        # Initialize menu handlers
        self.file_handler = FileMenuHandler(main_window)
        self.edit_handler = EditMenuHandler(main_window)
        self.view_handler = ViewMenuHandler(main_window)
        self.audio_handler = AudioMenuHandler(main_window)
        self.analysis_handler = AnalysisMenuHandler(main_window)
        self.help_handler = HelpMenuHandler(main_window)

        logger.info("MenuBarManager initialized with all handlers")

    def setup_all_menus(self):
        """Setup complete menu bar with all menus."""
        menubar = self.main_window.menuBar()

        # Clear existing menus if any
        menubar.clear()

        # Setup each menu
        self.file_handler.setup_file_menu(menubar)
        self.edit_handler.setup_edit_menu(menubar)
        self.view_handler.setup_view_menu(menubar)
        self.audio_handler.setup_audio_menu(menubar)
        self.analysis_handler.setup_analysis_menu(menubar)
        self.help_handler.setup_help_menu(menubar)

        logger.info("Complete menu bar setup finished")


# done
class FileMenuHandler:
    """Handles all File menu operations - CLEAN via command interface."""

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("FileMenuHandler initialized")

    def setup_file_menu(self, menubar):
        """Setup File menu with all actions."""
        file_menu = menubar.addMenu("&File")

        # Open directory
        open_dir_action = QAction("&Open Directory...", self.main_window)
        # open_dir_action.setShortcut(QKeySequence('Ctrl+O'))
        open_dir_action.setStatusTip("Open a different WAV directory")
        open_dir_action.triggered.connect(
            lambda: self._execute_file_command("open_directory")
        )
        file_menu.addAction(open_dir_action)

        # Reload
        reload_action = QAction("&Reload Directory", self.main_window)
        # reload_action.setShortcut(QKeySequence('F5'))
        reload_action.triggered.connect(
            lambda: self._execute_file_command("reload_directory")
        )
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        # Import/Export submenu
        import_export_menu = file_menu.addMenu("📥📤 &Import/Export")

        batch_import_action = QAction("Batch Import WAV Files...", self.main_window)
        batch_import_action.triggered.connect(
            lambda: self._execute_file_command("batch_import_files")
        )
        import_export_menu.addAction(batch_import_action)

        export_ableton_action = QAction("🎛️ Export to Ableton Live...", self.main_window)
        # export_ableton_action.setShortcut(QKeySequence('Ctrl+E'))
        export_ableton_action.triggered.connect(
            lambda: self._execute_file_command("export_to_ableton")
        )
        import_export_menu.addAction(export_ableton_action)

        export_metadata_action = QAction(
            "📋 Export Metadata to CSV...", self.main_window
        )
        export_metadata_action.triggered.connect(
            lambda: self._execute_file_command("export_metadata_csv")
        )
        import_export_menu.addAction(export_metadata_action)

        file_menu.addSeparator()

        # Recent directories (special handling - not via command interface)
        self.recent_menu = file_menu.addMenu("📁 &Recent Directories")
        self.update_recent_directories_menu()

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("E&xit", self.main_window)
        # exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        exit_action.triggered.connect(
            lambda: self._execute_file_command("exit_application")
        )
        file_menu.addAction(exit_action)

        logger.debug("File menu setup completed")

    def _execute_file_command(self, command_name, *args):
        """Execute file command with optional parameters."""
        try:
            command_func = self.main_window.file_commands.get(command_name)
            if command_func:
                if args:
                    result = command_func(*args)
                else:
                    result = command_func()

                # Auto-update recent menu after directory operations
                if (
                    command_name
                    in ["open_directory", "reload_directory", "open_recent_directory"]
                    and result
                ):
                    self.update_recent_directories_menu()
                return result
            else:
                logger.error(f"File command '{command_name}' not available")
                return False
        except Exception as e:
            logger.error(f"File command '{command_name}' failed: {e}")
            return False

    def update_recent_directories_menu(self):
        """Update recent directories menu via command interface."""
        self.recent_menu.clear()

        try:
            # Get recent directories via command interface
            recent_dirs = self._execute_file_command("get_recent_directories")

            if not recent_dirs:
                no_recent = QAction("No recent directories", self.main_window)
                no_recent.setEnabled(False)
                self.recent_menu.addAction(no_recent)
                return

            for i, directory in enumerate(recent_dirs[:10]):
                if os.path.exists(directory):
                    action = QAction(
                        f"{i + 1}. {os.path.basename(directory)}", self.main_window
                    )
                    action.setStatusTip(directory)
                    action.triggered.connect(
                        lambda checked, d=directory: self._execute_file_command(
                            "load_directory", d
                        )
                    )
                    self.recent_menu.addAction(action)
                else:
                    # Remove non-existent directory
                    self._execute_file_command("remove_recent_directory", directory)

        except Exception as e:
            logger.error(f"Error updating recent directories menu: {e}")
            error_action = QAction("Error loading recent directories", self.main_window)
            error_action.setEnabled(False)
            self.recent_menu.addAction(error_action)


class EditMenuHandler:
    """Handles all Edit menu operations - CLEAN via command interface."""

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("EditMenuHandler initialized")

    def setup_edit_menu(self, menubar):
        """Setup Edit menu with all actions."""
        edit_menu = menubar.addMenu("&Edit")

        # User config
        config_action = QAction("⚙️ &User Config...", self.main_window)
        # config_action.setShortcut(QKeySequence('Ctrl+,'))
        config_action.triggered.connect(
            lambda: self._execute_edit_command("open_user_config_manager")
        )
        edit_menu.addAction(config_action)

        edit_menu.addSeparator()

        # Tag operations
        clear_tags_action = QAction("🧹 &Clear Current Tags", self.main_window)
        # clear_tags_action.setShortcut(QKeySequence('Ctrl+Shift+C'))
        clear_tags_action.triggered.connect(
            lambda: self._execute_edit_command("clear_tags")
        )
        edit_menu.addAction(clear_tags_action)

        reset_defaults_action = QAction("🔄 &Reset to Defaults", self.main_window)
        # reset_defaults_action.setShortcut(QKeySequence('Ctrl+R'))
        reset_defaults_action.triggered.connect(
            lambda: self._execute_edit_command("reset_defaults")
        )
        edit_menu.addAction(reset_defaults_action)

        batch_tag_action = QAction("🏷️ &Batch Tag Editor...", self.main_window)
        # batch_tag_action.setShortcut(QKeySequence('Ctrl+B'))
        batch_tag_action.triggered.connect(
            lambda: self._execute_edit_command("open_batch_tagger")
        )
        edit_menu.addAction(batch_tag_action)

        edit_menu.addSeparator()

        # Template management
        template_action = QAction("📋 &Template Manager...", self.main_window)
        # template_action.setShortcut(QKeySequence('F9'))
        template_action.triggered.connect(
            lambda: self._execute_edit_command("open_template_manager")
        )
        edit_menu.addAction(template_action)

        logger.debug("Edit menu setup completed")

    def _execute_edit_command(self, command_name):
        """Execute edit command via command interface."""
        try:
            command_func = self.main_window.edit_commands.get(command_name)
            if command_func:
                return command_func()
            else:
                logger.error(f"Edit command '{command_name}' not available")
                return False
        except Exception as e:
            logger.error(f"Edit command '{command_name}' failed: {e}")
            return False


class ViewMenuHandler:
    """Handles all View menu operations - CLEAN VERSION via command interface only."""

    def __init__(self, main_window):
        self.main_window = main_window
        # ✅ GEEN wav_viewer reference meer!
        logger.debug("ViewMenuHandler initialized")

    def setup_view_menu(self, menubar):
        """Setup View menu with all actions."""
        view_menu = menubar.addMenu("&View")

        # Setup each logical section in separate methods
        self._setup_waveform_menu(view_menu)
        view_menu.addSeparator()

        self._setup_zoom_controls(view_menu)
        view_menu.addSeparator()

        self._setup_panel_toggles(view_menu)
        view_menu.addSeparator()

        self._setup_mouse_labels_menu(view_menu)

        logger.debug("View menu setup completed")

    def _setup_waveform_menu(self, view_menu):
        """Setup waveform display options submenu."""
        waveform_menu = view_menu.addMenu("📊 &Waveform Display")

        # Create waveform view actions
        mono_action = QAction("&Mono View", self.main_window)
        mono_action.setCheckable(True)
        mono_action.triggered.connect(
            lambda: self._execute_view_command("set_waveform_mode", "mono")
        )
        waveform_menu.addAction(mono_action)

        stereo_action = QAction("&Stereo View", self.main_window)
        stereo_action.setCheckable(True)
        stereo_action.setChecked(True)
        stereo_action.triggered.connect(
            lambda: self._execute_view_command("set_waveform_mode", "per_kanaal")
        )
        waveform_menu.addAction(stereo_action)

        overlay_action = QAction("&Overlay View", self.main_window)
        overlay_action.setCheckable(True)
        overlay_action.triggered.connect(
            lambda: self._execute_view_command("set_waveform_mode", "overlay")
        )
        waveform_menu.addAction(overlay_action)

        # Group view actions for mutual exclusivity
        self.view_group = QActionGroup(self.main_window)
        self.view_group.addAction(mono_action)
        self.view_group.addAction(stereo_action)
        self.view_group.addAction(overlay_action)

    def _setup_zoom_controls(self, view_menu):
        """Setup zoom control actions."""
        zoom_in_action = QAction("🔍 Zoom &In", self.main_window)
        # zoom_in_action.setShortcut(QKeySequence('Ctrl+='))
        zoom_in_action.triggered.connect(lambda: self._execute_view_command("zoom_in"))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("🔍 Zoom &Out", self.main_window)
        # zoom_out_action.setShortcut(QKeySequence('Ctrl+-'))
        zoom_out_action.triggered.connect(
            lambda: self._execute_view_command("zoom_out")
        )
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("⊞ &Fit to Window", self.main_window)
        # zoom_fit_action.setShortcut(QKeySequence('Ctrl+0'))
        zoom_fit_action.triggered.connect(
            lambda: self._execute_view_command("zoom_fit")
        )
        view_menu.addAction(zoom_fit_action)

    def _setup_panel_toggles(self, view_menu):
        """Setup show/hide panel toggles."""
        toggle_metadata_action = QAction("Show/Hide &Metadata Tables", self.main_window)
        toggle_metadata_action.setCheckable(True)
        toggle_metadata_action.setChecked(True)
        toggle_metadata_action.triggered.connect(
            lambda checked: self._execute_view_command("toggle_metadata", checked)
        )
        view_menu.addAction(toggle_metadata_action)

    def _setup_mouse_labels_menu(self, view_menu):
        """Setup mouse labels configuration submenu."""
        mouse_labels_menu = view_menu.addMenu("🖱️ &Mouse Labels")

        # Setup preset options
        self._setup_mouse_preset_actions(mouse_labels_menu)
        mouse_labels_menu.addSeparator()

        # Setup individual toggles
        self._setup_mouse_toggle_actions(mouse_labels_menu)

    def _setup_mouse_preset_actions(self, mouse_labels_menu):
        """Setup mouse label preset actions."""
        minimal_action = QAction("⚡ &Minimal (Fast)", self.main_window)
        minimal_action.setStatusTip("Show only essential info for better performance")
        minimal_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_minimal")
        )
        mouse_labels_menu.addAction(minimal_action)

        performance_action = QAction("⚙️ &Performance (Balanced)", self.main_window)
        performance_action.setStatusTip("Optimized balance of info and performance")
        performance_action.setChecked(True)  # Default
        performance_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_performance")
        )
        mouse_labels_menu.addAction(performance_action)

        professional_action = QAction("🎛️ &Professional (Full)", self.main_window)
        professional_action.setStatusTip("Complete professional audio information")
        professional_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_professional")
        )
        mouse_labels_menu.addAction(professional_action)

        # Group the preset actions for mutual exclusivity
        self.mouse_preset_group = QActionGroup(self.main_window)
        self.mouse_preset_group.addAction(minimal_action)
        self.mouse_preset_group.addAction(performance_action)
        self.mouse_preset_group.addAction(professional_action)

    def _setup_mouse_toggle_actions(self, mouse_labels_menu):
        """Setup individual mouse label toggle actions."""
        frequency_action = QAction("🎼 &Frequency Analysis", self.main_window)
        frequency_action.setCheckable(True)
        frequency_action.setChecked(False)  # CPU intensive, off by default
        frequency_action.setStatusTip("Real-time frequency analysis (CPU intensive)")
        frequency_action.triggered.connect(
            lambda checked: self._execute_view_command("toggle_frequency", checked)
        )
        mouse_labels_menu.addAction(frequency_action)

        timecode_action = QAction("⏱️ &Timecode Format", self.main_window)
        timecode_action.setCheckable(True)
        timecode_action.setChecked(True)
        timecode_action.setStatusTip("Show time in HH:MM:SS.mmm format")
        timecode_action.triggered.connect(
            lambda checked: self._execute_view_command("toggle_timecode", checked)
        )
        mouse_labels_menu.addAction(timecode_action)

        # Store references for state management
        self.frequency_action = frequency_action
        self.timecode_action = timecode_action

    def _execute_view_command(self, command_name, *args):
        """Execute view command via command interface with error handling."""
        try:
            command_func = self.main_window.view_commands.get(command_name)
            if command_func:
                if args:
                    return command_func(*args)
                else:
                    return command_func()
            else:
                logger.error(f"View command '{command_name}' not available")
                return False
        except Exception as e:
            logger.error(f"View command '{command_name}' failed: {e}")
            return False


class AudioMenuHandler:
    """Handles all Audio menu operations - CLEAN via command interface."""

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("AudioMenuHandler initialized")

    def setup_audio_menu(self, menubar):
        """Setup Audio menu with all actions."""
        audio_menu = menubar.addMenu("&Audio")

        # Playback controls
        play_pause_action = QAction("⏯️ &Play/Pause", self.main_window)
        play_pause_action.triggered.connect(
            lambda: self._execute_audio_command("play_pause")
        )
        audio_menu.addAction(play_pause_action)

        stop_action = QAction("⏹️ &Stop", self.main_window)
        # stop_action.setShortcut(QKeySequence(Qt.Key_Escape))
        stop_action.triggered.connect(lambda: self._execute_audio_command("stop"))
        audio_menu.addAction(stop_action)

        audio_menu.addSeparator()

        # Volume controls
        volume_up_action = QAction("🔊 Volume +", self.main_window)
        # volume_up_action.setShortcut(QKeySequence(Qt.Key_PageUp))
        volume_up_action.triggered.connect(
            lambda: self._execute_audio_command("volume_up")
        )
        audio_menu.addAction(volume_up_action)

        volume_down_action = QAction("🔉 Volume -", self.main_window)
        # volume_down_action.setShortcut(QKeySequence(Qt.Key_PageDown))
        volume_down_action.triggered.connect(
            lambda: self._execute_audio_command("volume_down")
        )
        audio_menu.addAction(volume_down_action)

        mute_action = QAction("🔇 &Mute", self.main_window)
        # mute_action.setShortcut(QKeySequence(Qt.Key_M))
        mute_action.triggered.connect(
            lambda: self._execute_audio_command("toggle_mute")
        )
        audio_menu.addAction(mute_action)

        logger.debug("Audio menu setup completed")

    def _execute_audio_command(self, command_name):
        """Execute audio command via command interface."""
        try:
            command_func = self.main_window.audio_commands.get(command_name)
            if command_func:
                return command_func()
            else:
                logger.error(f"Audio command '{command_name}' not available")
                return False
        except Exception as e:
            logger.error(f"Audio command '{command_name}' failed: {e}")
            return False


class AnalysisMenuHandler:
    """Handles all Analysis menu operations - CLEAN via command interface."""

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("AnalysisMenuHandler initialized")

    def setup_analysis_menu(self, menubar):
        """Setup Analysis menu with all actions."""
        analysis_menu = menubar.addMenu("&Analysis")

        # Analytics dashboard
        analytics_action = QAction("📊 &Analytics Dashboard...", self.main_window)
        # analytics_action.setShortcut(QKeySequence('Ctrl+A'))
        analytics_action.triggered.connect(
            lambda: self._execute_analysis_command("show_analytics")
        )
        analysis_menu.addAction(analytics_action)

        # Cue points analysis
        cue_analysis_action = QAction("📍 &Cue Points Overview...", self.main_window)
        cue_analysis_action.triggered.connect(
            lambda: self._execute_analysis_command("show_cue_analysis")
        )
        analysis_menu.addAction(cue_analysis_action)

        logger.debug("Analysis menu setup completed")

    def _execute_analysis_command(self, command_name):
        """Execute analysis command via command interface."""
        try:
            command_func = self.main_window.analysis_commands.get(command_name)
            if command_func:
                return command_func()
            else:
                logger.error(f"Analysis command '{command_name}' not available")
                return False
        except Exception as e:
            logger.error(f"Analysis command '{command_name}' failed: {e}")
            return False


class HelpMenuHandler:
    """Handles all Help menu operations - STREAMLINED VERSION."""

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("HelpMenuHandler initialized")

    def setup_help_menu(self, menubar):
        """Setup STREAMLINED Help menu with consolidated actions."""
        help_menu = menubar.addMenu("&Help")

        # CONSOLIDATED: Help & Quick Start (replaces 3 separate dialogs)
        help_quickstart_action = QAction("🚀 &Help & Quick Start", self.main_window)
        help_quickstart_action.triggered.connect(
            lambda: self._execute_help_command("show_help_and_quickstart")
        )
        help_menu.addAction(help_quickstart_action)

        # Keyboard shortcuts (stays separate - useful as reference during work)
        shortcuts_action = QAction("⌨️ &Keyboard Shortcuts", self.main_window)
        # shortcuts_action.setShortcut(QKeySequence(Qt.Key_F1))
        shortcuts_action.triggered.connect(
            lambda: self._execute_help_command("show_keyboard_shortcuts")
        )
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        # About (simplified)
        about_action = QAction("ℹ️ &About", self.main_window)
        about_action.triggered.connect(lambda: self._execute_help_command("show_about"))
        help_menu.addAction(about_action)

        logger.debug("Streamlined Help menu setup completed")

    def _execute_help_command(self, command_name):
        """Execute help command via command interface."""
        try:
            command_func = self.main_window.help_commands.get(command_name)
            if command_func:
                return command_func()
            else:
                logger.error(f"Help command '{command_name}' not available")
                self.main_window.show_status_message(
                    "Help function not available", 3000
                )
                return False
        except Exception as e:
            logger.error(f"Help command '{command_name}' failed: {e}")
            self.main_window.show_status_message(f"Help error: {str(e)}", 3000)
            return False
