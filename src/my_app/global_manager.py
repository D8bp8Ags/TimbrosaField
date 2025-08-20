# Global Shortcut Manager - alle shortcuts op één plek!

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut


class GlobalShortcutManager:
    """Centraal shortcut management - gebruikt bestaande command_interface!"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.shortcuts = {}

    def setup_all_shortcuts(self):
        """Setup ALLE shortcuts centraal via command_interface."""
        # File operations - via file_commands
        self.add_command_shortcut(
            "Ctrl+O", "file_commands", "open_directory", "Open Directory"
        )
        self.add_command_shortcut(
            "F5", "file_commands", "reload_directory", "Reload Directory"
        )
        self.add_command_shortcut("Ctrl+I", "file_commands", "batch_import_files", "Batch Import Files")  # I = Import

        self.add_command_shortcut(
            "Ctrl+E", "file_commands", "export_to_ableton", "Export to Ableton"
        )
        self.add_command_shortcut("Ctrl+Shift+E", "file_commands", "export_metadata_csv",
                                  "Export Metadata CSV")  # Shift+E = Export CSV

        self.add_command_shortcut(
            "Ctrl+Q", "file_commands", "exit_application", "Quit Application"
        )

        # Edit operations - via edit_commands
        self.add_command_shortcut(
            "Ctrl+,", "edit_commands", "open_user_config_manager", "Open User Config"
        )
        self.add_command_shortcut(
            "F9", "edit_commands", "open_template_manager", "Template Manager"
        )
        self.add_command_shortcut(
            "Ctrl+B", "edit_commands", "open_batch_tagger", "Batch Tag Editor"
        )
        self.add_command_shortcut(
            "Ctrl+Shift+C", "edit_commands", "clear_tags", "Clear Tags"
        )
        self.add_command_shortcut("Ctrl+Shift+R", "edit_commands", "reset_defaults", "Reset to Defaults")  # R = Reset

        # View operations - via view_commands
        self.add_command_shortcut("Ctrl+=", "view_commands", "zoom_in", "Zoom In")
        self.add_command_shortcut("Ctrl+-", "view_commands", "zoom_out", "Zoom Out")
        self.add_command_shortcut(
            "Ctrl+0", "view_commands", "zoom_fit", "Fit to Window"
        )
        self.add_command_shortcut("Ctrl+T", "view_commands", "toggle_metadata",
                                  "Toggle Metadata Panel")  # T = Tables/Toggle

        # Audio operations - via audio_commands
        self.add_command_shortcut("Space", "audio_commands", "play_pause", "Play/Pause")
        self.add_command_shortcut("Escape", "audio_commands", "stop", "Stop Audio")  # Standard stop key
        self.add_command_shortcut(
            "Left", "audio_commands", "seek_backward", "Seek Backward"
        )
        self.add_command_shortcut(
            "Right", "audio_commands", "seek_forward", "Seek Forward"
        )
        self.add_command_shortcut("=", "audio_commands", "volume_up", "Volume Up")
        self.add_command_shortcut("-", "audio_commands", "volume_down", "Volume Down")
        self.add_command_shortcut("M", "audio_commands", "toggle_mute", "Toggle Mute")

        # Analysis operations - via analysis_commands
        self.add_command_shortcut(
            "Ctrl+A", "analysis_commands", "show_analytics", "Analytics Dashboard"
        )
        self.add_command_shortcut("Ctrl+U", "analysis_commands", "show_cue_analysis",
                                  "Cue Point Analysis")  # U = cUe points

        # Help operations - via help_commands
        self.add_command_shortcut(
            "F1", "help_commands", "show_keyboard_shortcuts", "Show Help"
        )
        self.add_command_shortcut("Ctrl+Shift+?", "help_commands", "show_help_and_quickstart",
                                  "Help & Quick Start")  # ? = help
        self.add_command_shortcut("F12", "help_commands", "show_about", "About Application")  # F12 often used for about

        # Template shortcuts - via edit_commands met parameters
        self.add_template_shortcut("Ctrl+1", 1, "Apply Template 1")
        self.add_template_shortcut("Ctrl+2", 2, "Apply Template 2")
        self.add_template_shortcut("Ctrl+3", 3, "Apply Template 3")
        self.add_template_shortcut("Ctrl+4", 4, "Apply Template 4")

        print(
            f"🎯 {len(self.shortcuts)} global shortcuts installed via command_interface"
        )

    def add_command_shortcut(
        self, key_sequence, command_group, command_name, description=""
    ):
        def execute_command():
            command_dict = getattr(self.main_window, command_group, {})
            command_func = command_dict.get(command_name)
            if command_func:
                return command_func()
            else:
                print(f"❌ Command {command_group}.{command_name} not found")

        shortcut = QShortcut(QKeySequence(key_sequence), self.main_window)
        shortcut.activated.connect(execute_command)

        self.shortcuts[key_sequence] = {
            "shortcut": shortcut,
            "command_group": command_group,
            "command_name": command_name,
            "description": description,
        }
    def get_shortcut_for_command(self, command_group, command_name):
        """Find shortcut for a specific command."""
        for key_sequence, shortcut_info in self.shortcuts.items():
            if (shortcut_info['command_group'] == command_group and
                shortcut_info['command_name'] == command_name):
                return key_sequence
        return ""
    def add_template_shortcut(self, key_sequence, template_number, description=""):

        def apply_template():
            # Gebruik edit_commands voor template operations
            if hasattr(self.main_window, "template_manager"):
                return self.main_window.template_manager.apply_template(template_number)

        shortcut = QShortcut(QKeySequence(key_sequence), self.main_window)
        shortcut.activated.connect(apply_template)

        self.shortcuts[key_sequence] = {
            "shortcut": shortcut,
            "template_number": template_number,
            "description": description,
        }

    def get_shortcuts_list(self):
        """Get lijst van alle shortcuts voor help dialog."""
        return [(key, info["description"]) for key, info in self.shortcuts.items()]


# Usage in MainWindow.__init__():
def __init__(self):
    # ... bestaande init code ...

    # Setup global shortcut manager
    self.shortcut_manager = GlobalShortcutManager(self)
    self.shortcut_manager.setup_all_shortcuts()
