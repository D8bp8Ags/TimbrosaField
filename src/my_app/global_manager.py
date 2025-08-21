# Global Shortcut Manager - alle shortcuts op één plek!

import logging
import os

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

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


class GlobalShortcutManager:
    """Central keyboard shortcut management system for the TimbrosaField application.
    
    This class provides a unified interface for managing all keyboard shortcuts
    throughout the application. It routes shortcuts through the main window's
    command interface system, enabling centralized shortcut management and 
    consistent behavior across all application functions.
    
    The manager organizes shortcuts into functional groups:
    - File operations (open, reload, import, export)
    - Edit operations (configuration, templates, batch editing)
    - View controls (zoom, panels, display modes)
    - Audio playback controls (play, pause, seek, volume)
    - Analysis tools and help dialogs
    - Quick template application shortcuts
    
    Attributes:
        main_window: Reference to the main application window for command execution.
        shortcuts: Dictionary storing all registered shortcuts with their metadata.
    """

    def __init__(self, main_window):
        """Initialize the GlobalShortcutManager with a reference to the main window.
        
        Args:
            main_window: The main application window that hosts command interfaces
                        and provides the parent widget for QShortcut instances.
                        
        Note:
            The main window must have command dictionaries (file_commands, 
            edit_commands, etc.) available for the shortcut system to function.
        """
        self.main_window = main_window
        self.shortcuts = {}

    def setup_all_shortcuts(self):
        """Configure all application keyboard shortcuts through the command interface.
        
        Sets up comprehensive keyboard shortcuts across all functional categories
        of the application. Each shortcut is registered with the Qt widget system
        and connected to the appropriate command through the main window's
        command interface dictionaries.
        
        Shortcut categories configured:
        - File operations: Directory handling, import/export, application control
        - Edit operations: Configuration, templates, batch operations
        - View controls: Zoom, panel visibility, display modes
        - Audio controls: Playback, seeking, volume control
        - Analysis tools: Analytics dashboard, cue point analysis
        - Help system: Documentation, shortcuts reference, about dialog
        - Template shortcuts: Quick-apply tag templates (Ctrl+1-4)
        
        Note:
            Prints a summary count of installed shortcuts for debugging purposes.
            All shortcuts route through the command interface for consistent
            error handling and progress indication.
        """
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

        logger.info(
            f"{len(self.shortcuts)} global shortcuts installed via command_interface"
        )

    def add_command_shortcut(
        self, key_sequence, command_group, command_name, description=""
    ):
        """Register a keyboard shortcut that executes a command via the command interface.
        
        Creates a QShortcut that when activated looks up and executes a command
        from the main window's command interface. The command is located by
        accessing the specified command group dictionary and retrieving the
        named command function.
        
        Args:
            key_sequence (str): Qt key sequence string (e.g., "Ctrl+O", "F5", "Space").
                               Supports all standard Qt key combinations.
            command_group (str): Name of the command group attribute on main window
                               (e.g., "file_commands", "edit_commands").
            command_name (str): Specific command function name within the group
                              to execute when shortcut is activated.
            description (str, optional): Human-readable description for help dialogs
                                       and documentation. Defaults to empty string.
        
        Note:
            If the command group or command name cannot be found, an error message
            is printed to the console but the application continues normally.
            The shortcut metadata is stored for later retrieval by help systems.
        """
        def execute_command():
            """Internal function to execute the command when shortcut is activated.
            
            Looks up the command in the main window's command interface and
            executes it if found. Provides error feedback if command is missing.
            
            Returns:
                The return value of the executed command function, or None if
                the command could not be found or executed.
            """
            command_dict = getattr(self.main_window, command_group, {})
            command_func = command_dict.get(command_name)
            if command_func:
                return command_func()
            else:
                logger.error(f"Command {command_group}.{command_name} not found")

        shortcut = QShortcut(QKeySequence(key_sequence), self.main_window)
        shortcut.activated.connect(execute_command)

        self.shortcuts[key_sequence] = {
            "shortcut": shortcut,
            "command_group": command_group,
            "command_name": command_name,
            "description": description,
        }
    def get_shortcut_for_command(self, command_group, command_name):
        """Find the keyboard shortcut assigned to a specific command.
        
        Searches through all registered shortcuts to find the key sequence
        associated with a particular command group and command name combination.
        
        Args:
            command_group (str): Name of the command group to search within
                               (e.g., "file_commands", "audio_commands").
            command_name (str): Specific command name to find the shortcut for
                              (e.g., "open_directory", "play_pause").
        
        Returns:
            str: The key sequence string for the command (e.g., "Ctrl+O", "Space")
                 if found, empty string if no shortcut is assigned to this command.
                 
        Example:
            >>> manager.get_shortcut_for_command("file_commands", "open_directory")
            "Ctrl+O"
        """
        for key_sequence, shortcut_info in self.shortcuts.items():
            if (shortcut_info['command_group'] == command_group and
                shortcut_info['command_name'] == command_name):
                return key_sequence
        return ""
    def add_template_shortcut(self, key_sequence, template_number, description=""):
        """Register a keyboard shortcut for quick template application.
        
        Creates a specialized shortcut that applies a predefined tag template
        to the current file or selection. Template shortcuts provide quick access
        to frequently used tag combinations without opening the template manager.
        
        Args:
            key_sequence (str): Qt key sequence string for the shortcut
                               (e.g., "Ctrl+1", "Ctrl+2").
            template_number (int): Template number to apply (typically 1-4).
                                 Must correspond to an existing template.
            description (str, optional): Human-readable description for help systems.
                                       Defaults to empty string.
        
        Note:
            Requires the main window to have a template_manager attribute with
            an apply_template method. If the template manager is not available,
            the shortcut activation will have no effect.
            
        Example:
            >>> manager.add_template_shortcut("Ctrl+1", 1, "Nature Sounds")
        """

        def apply_template():
            """Internal function to apply the template when shortcut is activated.
            
            Checks for the template manager availability and applies the specified
            template number if the manager is present.
            
            Returns:
                The return value of the template application, or None if the
                template manager is not available.
            """
            # Use template manager for template operations
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
        """Retrieve a formatted list of all registered shortcuts for help dialogs.
        
        Compiles all registered shortcuts into a list of tuples containing
        the key sequence and description for each shortcut. This data is
        typically used by help dialogs to display available shortcuts to users.
        
        Returns:
            List[Tuple[str, str]]: List of tuples where each tuple contains:
                                  - Key sequence string (e.g., "Ctrl+O")
                                  - Description string (e.g., "Open Directory")
                                  
        Example:
            >>> shortcuts = manager.get_shortcuts_list()
            >>> shortcuts[0]
            ("Ctrl+O", "Open Directory")
            
        Note:
            The returned list includes both command shortcuts and template shortcuts.
            Order is not guaranteed and depends on dictionary iteration order.
        """
        return [(key, info["description"]) for key, info in self.shortcuts.items()]


# Usage example for integration in MainWindow.__init__():
def __init__(self):
    """Example integration of GlobalShortcutManager in MainWindow initialization.
    
    This example demonstrates the proper sequence for integrating the shortcut
    manager into the main window initialization process. The shortcut manager
    should be created after the command interface is established but before
    the UI is shown to the user.
    
    Note:
        This is documentation code and not part of the GlobalShortcutManager class.
        It shows the recommended integration pattern for the main application.
    """
    # ... existing initialization code ...
    # Command interface must be set up first
    # self._setup_command_interface()
    
    # Create and configure global shortcut manager
    self.shortcut_manager = GlobalShortcutManager(self)
    self.shortcut_manager.setup_all_shortcuts()
