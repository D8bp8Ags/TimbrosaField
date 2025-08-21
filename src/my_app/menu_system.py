"""Menu System Module for TimbrosaField Audio Analysis Application.

This module provides a comprehensive menu system architecture that separates menu
logic from the main window through specialized menu handlers. Each handler manages
a specific functional area (File, Edit, View, Audio, Analysis, Help) and routes
operations through the main window's command interface system.

The module follows a clean separation of concerns pattern:
- MenuBarManager: Central coordinator for all menu systems
- MenuHandlerBase: Common functionality mixin for all handlers
- Specialized Handlers: Domain-specific menu management (FileMenuHandler, etc.)

All menu operations are routed through command interfaces for:
- Consistent error handling and logging
- Progress indication for long-running operations
- Centralized shortcut management
- Clean separation between UI and business logic

Typical usage:
    manager = MenuBarManager(main_window)
    manager.setup_all_menus()
"""

import logging
import os

# from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QActionGroup
from PyQt5.QtGui import QKeySequence

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

## TEST
class MenuHandlerBase:
    """Base class providing common functionality for menu handlers.
    
    This mixin class provides shared methods that can be used by all menu handler
    classes to maintain consistency and reduce code duplication across the menu system.
    """
    
    def _apply_shortcut(self, action, command_group, command_name):
        """Apply keyboard shortcut from GlobalShortcutManager to a QAction.
        
        Retrieves the keyboard shortcut associated with a specific command from
        the global shortcut manager and applies it to the given QAction.
        
        Args:
            action (QAction): The menu action to assign the shortcut to.
            command_group (str): Name of the command group (e.g., "file_commands").
            command_name (str): Specific command name within the group.
            
        Note:
            If no shortcut is found for the command, the action remains without
            a keyboard shortcut. This allows for flexible shortcut assignment
            without breaking menu functionality.
        """
        shortcut = self.main_window.shortcut_manager.get_shortcut_for_command(command_group, command_name)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))

class MenuBarManager:
    """Central coordinator for the application's complete menu system.

    This class orchestrates the creation and management of all menu bars and their
    handlers, providing a clean separation between the main window and menu logic.
    It initializes specialized menu handlers for different functional areas and
    coordinates their setup and state synchronization.
    
    The manager maintains references to:
    - FileMenuHandler: File operations (open, save, export, recent directories)
    - EditMenuHandler: Editing operations (tags, templates, configuration)
    - ViewMenuHandler: Display and visualization controls
    - AudioMenuHandler: Audio playback and control functions
    - AnalysisMenuHandler: Analysis tools and dashboards
    - HelpMenuHandler: Help system and documentation
    
    Attributes:
        main_window: Reference to the main application window.
        file_handler: Handler for file menu operations.
        edit_handler: Handler for edit menu operations.
        view_handler: Handler for view menu operations.
        audio_handler: Handler for audio menu operations.
        analysis_handler: Handler for analysis menu operations.
        help_handler: Handler for help menu operations.
    """

    def __init__(self, main_window):
        """Initialize the MenuBarManager with specialized menu handlers.
        
        Creates instances of all menu handlers and establishes the connection
        to the main window for command execution and state management.
        
        Args:
            main_window: The main application window that provides command
                        interfaces and serves as the parent for menu actions.
                        
        Note:
            All menu handlers are initialized immediately but the actual menu
            setup is deferred until setup_all_menus() is called.
        """
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
        """Configure and display the complete application menu bar.
        
        Creates all menu categories and their associated actions by delegating
        to the appropriate specialized handlers. After setup, synchronizes all
        menu states with current application settings.
        
        The menu setup order is:
        1. File menu (open, save, export, recent directories)
        2. Edit menu (tags, templates, configuration)
        3. View menu (display modes, themes, panels)
        4. Audio menu (playback controls, volume)
        5. Analysis menu (dashboards, analytics)
        6. Help menu (documentation, shortcuts, about)
        
        Note:
            Clears any existing menu bar content before setup to ensure
            clean state. All menu states are synchronized with current
            application settings after creation.
        """
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

        self.sync_all_menu_states()

        logger.info("Complete menu bar setup finished")

    def sync_all_menu_states(self):
        """Synchronize all menu item states with current application settings.
        
        Updates checkable menu items to reflect the current application state
        by reading settings from the settings manager and updating menu handlers
        accordingly. This ensures menu items accurately show current modes and preferences.
        
        Synchronized states include:
        - Theme selection (light, dark, macOS dark)
        - View mode (mono, stereo, overlay)
        - Mouse label presets (minimal, performance, professional)
        - Panel visibility states
        
        Note:
            Called automatically after menu setup and should be called whenever
            application settings change to keep menus in sync.
        """
        settings = self.main_window.settings_manager

        # Theme
        theme = settings.get_theme("light")
        self.set_theme_checked(theme)

        # View mode
        view_mode = settings.get_view_mode("per_kanaal")
        self.set_view_mode_checked(view_mode)

        # Mouse preset
        mouse_preset = settings.get_mouse_labels_preset("performance")
        self.set_mouse_preset_checked(mouse_preset)

        # # Metadata visibility
        # show_metadata = settings.get_show_metadata(True)
        # self.set_metadata_toggle_checked(show_metadata)

    def set_theme_checked(self, theme):
        """Update theme menu items to reflect the currently active theme.
        
        Searches through theme action group and sets the appropriate action
        as checked based on the theme name. Uses object names for reliable matching.
        
        Args:
            theme (str): Name of the active theme ("light", "dark", or "macos_dark").
                        Must match the objectName of the corresponding theme action.
                        
        Note:
            Only one theme action can be checked at a time due to the QActionGroup
            mutual exclusivity. Invalid theme names are silently ignored.
        """
        if hasattr(self.view_handler, 'theme_group'):
            for action in self.view_handler.theme_group.actions():
                # Match op object name in plaats van text
                should_check = action.objectName() == f"{theme}_theme"
                action.setChecked(should_check)

    def set_view_mode_checked(self, mode):
        """Update view mode menu items to reflect the current display mode.
        
        Searches through view mode actions and checks the appropriate item
        based on the current waveform display mode.
        
        Args:
            mode (str): Current view mode identifier:
                       - "mono": Single channel view
                       - "per_kanaal": Stereo/per-channel view
                       - "overlay": Overlay view mode
                       
        Note:
            Uses text matching to identify the correct action since view mode
            actions don't use object names. Only one mode can be active at a time.
        """
        if hasattr(self.view_handler, 'view_group'):
            for action in self.view_handler.view_group.actions():
                if mode == "mono" and "Mono" in action.text():
                    action.setChecked(True)
                elif mode == "per_kanaal" and "Stereo" in action.text():
                    action.setChecked(True)
                elif mode == "overlay" and "Overlay" in action.text():
                    action.setChecked(True)

    def set_mouse_preset_checked(self, preset):
        """Update mouse label preset menu items to reflect the active preset.
        
        Sets the appropriate mouse label preset action as checked based on
        the current preset configuration.
        
        Args:
            preset (str): Name of the active mouse label preset:
                         - "minimal": Minimal information display
                         - "performance": Balanced info and performance
                         - "professional": Complete professional info
                         - "professional_advanced": All features enabled
                         
        Note:
            Uses object name matching for reliable preset identification.
            Only one preset can be active at a time due to QActionGroup exclusivity.
        """

        if hasattr(self.view_handler, 'mouse_preset_group'):
            # for action in self.view_handler.mouse_preset_group.actions():
            #     action.setChecked(preset.lower() in action.text().lower())
            for action in self.view_handler.mouse_preset_group.actions():
                action.setChecked(action.objectName() == preset)

# class FileMenuHandler:
class FileMenuHandler(MenuHandlerBase):
    """Specialized handler for all file-related menu operations.
    
    This class manages the File menu and all its associated actions, routing
    commands through the main window's file_commands interface. It handles
    directory operations, import/export functionality, recent directories,
    and application exit.
    
    Key responsibilities:
    - Directory opening and reloading
    - Batch file import operations
    - Export to Ableton Live and CSV formats
    - Recent directories management and display
    - Application exit with proper cleanup
    
    All operations are executed through the command interface for consistent
    error handling and progress indication.
    """

    def __init__(self, main_window):
        """Initialize the FileMenuHandler with main window reference.
        
        Args:
            main_window: Main application window that provides the file_commands
                        interface for executing file operations.
        """
        self.main_window = main_window
        logger.debug("FileMenuHandler initialized")

    def setup_file_menu(self, menubar):
        """Create and configure the complete File menu with all actions.
        
        Sets up the File menu with organized sections:
        - Directory operations (open, reload)
        - Import/Export submenu (batch import, Ableton export, CSV export)
        - Recent directories dynamic submenu
        - Application exit
        
        Args:
            menubar (QMenuBar): The main menu bar to add the File menu to.
            
        Note:
            All actions are connected to the command interface for consistent
            behavior. Shortcuts are applied automatically from the global
            shortcut manager. Recent directories are populated dynamically.
        """
        file_menu = menubar.addMenu("&File")

        # Open directory
        open_dir_action = QAction("&Open Directory...", self.main_window)
        # open_dir_action.setShortcut(QKeySequence('Ctrl+O'))
        self._apply_shortcut(open_dir_action, 'file_commands', 'open_directory')  
        open_dir_action.setStatusTip("Open a different WAV directory")
        open_dir_action.triggered.connect(
            lambda: self._execute_file_command("open_directory")
        )
        file_menu.addAction(open_dir_action)

        # Reload
        reload_action = QAction("&Reload Directory", self.main_window)
        # reload_action.setShortcut(QKeySequence('F5'))
        self._apply_shortcut(reload_action, 'file_commands', 'reload_directory')  
        reload_action.triggered.connect(
            lambda: self._execute_file_command("reload_directory")
        )
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        # Import/Export submenu
        import_export_menu = file_menu.addMenu("📥📤 &Import/Export")

        batch_import_action = QAction("Batch Import WAV Files...", self.main_window)
        self._apply_shortcut(batch_import_action, 'file_commands', 'batch_import_files')
        batch_import_action.triggered.connect(
            lambda: self._execute_file_command("batch_import_files")
        )
        import_export_menu.addAction(batch_import_action)

        export_ableton_action = QAction("🎛️ Export to Ableton Live...", self.main_window)
        # export_ableton_action.setShortcut(QKeySequence('Ctrl+E'))
        self._apply_shortcut(export_ableton_action, 'file_commands', 'export_to_ableton')  
        export_ableton_action.triggered.connect(
            lambda: self._execute_file_command("export_to_ableton")
        )
        import_export_menu.addAction(export_ableton_action)

        export_metadata_action = QAction(
            "📋 Export Metadata to CSV...", self.main_window
        )
        self._apply_shortcut(export_metadata_action, 'file_commands', 'export_metadata_csv')
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
        self._apply_shortcut(exit_action, 'file_commands', 'exit_application')  
        exit_action.triggered.connect(
            lambda: self._execute_file_command("exit_application")
        )
        file_menu.addAction(exit_action)

        logger.debug("File menu setup completed")

    def _execute_file_command(self, command_name, *args):
        """Execute a file operation command through the command interface.
        
        Looks up and executes the specified command from the main window's
        file_commands dictionary. Provides automatic recent directories menu
        updates for relevant operations.
        
        Args:
            command_name (str): Name of the command to execute from file_commands.
            *args: Optional arguments to pass to the command function.
            
        Returns:
            The return value of the executed command, or False if the command
            fails or is not available.
            
        Note:
            Automatically updates the recent directories menu after directory
            operations (open_directory, reload_directory, open_recent_directory)
            if the operation succeeds.
        """
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
        """Refresh the recent directories submenu with current directory history.
        
        Clears the existing recent directories menu and repopulates it with
        the current list of recently accessed directories. Non-existent
        directories are automatically removed from the list.
        
        The menu shows up to 10 most recent directories with:
        - Numbered entries (1-10) showing directory basename
        - Full path in status tip for reference
        - Automatic cleanup of non-existent directories
        - Disabled placeholder when no recent directories exist
        
        Note:
            Called automatically after directory operations and can be called
            manually to refresh the menu state. Uses the command interface
            to maintain consistency with the rest of the application.
        """
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


#class EditMenuHandler:
class EditMenuHandler(MenuHandlerBase):
    """Specialized handler for all editing and configuration menu operations.
    
    This class manages the Edit menu and routes all editing commands through
    the main window's edit_commands interface. It provides access to user
    configuration, tag operations, batch editing, and template management.
    
    Key responsibilities:
    - User configuration management
    - Tag clearing and resetting operations
    - Batch tag editor access
    - Template manager integration
    - Default value restoration
    
    All operations maintain consistency through the centralized command interface.
    """

    def __init__(self, main_window):
        """Initialize the EditMenuHandler with main window reference.
        
        Args:
            main_window: Main application window that provides the edit_commands
                        interface for executing editing operations.
        """
        self.main_window = main_window
        logger.debug("EditMenuHandler initialized")

    def setup_edit_menu(self, menubar):
        """Create and configure the complete Edit menu with all actions.
        
        Sets up the Edit menu with organized sections:
        - User configuration access
        - Tag operations (clear, reset to defaults)
        - Batch editing tools
        - Template management
        
        Args:
            menubar (QMenuBar): The main menu bar to add the Edit menu to.
            
        Note:
            All actions are connected through the command interface and have
            appropriate keyboard shortcuts applied from the global shortcut manager.
        """
        edit_menu = menubar.addMenu("&Edit")

        # User config
        config_action = QAction("⚙️ &User Config...", self.main_window)
        # config_action.setShortcut(QKeySequence('Ctrl+,'))
        self._apply_shortcut(config_action, 'edit_commands', 'open_user_config_manager')  
        config_action.triggered.connect(
            lambda: self._execute_edit_command("open_user_config_manager")
        )
        edit_menu.addAction(config_action)

        edit_menu.addSeparator()

        # Tag operations
        clear_tags_action = QAction("🧹 &Clear Current Tags", self.main_window)
        # clear_tags_action.setShortcut(QKeySequence('Ctrl+Shift+C'))
        self._apply_shortcut(clear_tags_action, 'edit_commands', 'clear_tags')  
        clear_tags_action.triggered.connect(
            lambda: self._execute_edit_command("clear_tags")
        )
        edit_menu.addAction(clear_tags_action)

        reset_defaults_action = QAction("🔄 &Reset to Defaults", self.main_window)
        # reset_defaults_action.setShortcut(QKeySequence('Ctrl+R'))
        self._apply_shortcut(reset_defaults_action, 'edit_commands', 'reset_defaults')
        reset_defaults_action.triggered.connect(
            lambda: self._execute_edit_command("reset_defaults")
        )
        edit_menu.addAction(reset_defaults_action)

        batch_tag_action = QAction("🏷️ &Batch Tag Editor...", self.main_window)
        # batch_tag_action.setShortcut(QKeySequence('Ctrl+B'))
        self._apply_shortcut(batch_tag_action, 'edit_commands', 'open_batch_tagger')  
        batch_tag_action.triggered.connect(
            lambda: self._execute_edit_command("open_batch_tagger")
        )
        edit_menu.addAction(batch_tag_action)

        edit_menu.addSeparator()

        # Template management
        template_action = QAction("📋 &Template Manager...", self.main_window)
        # template_action.setShortcut(QKeySequence('F9'))
        self._apply_shortcut(template_action, 'edit_commands', 'open_template_manager')  
        template_action.triggered.connect(
            lambda: self._execute_edit_command("open_template_manager")
        )
        edit_menu.addAction(template_action)

        logger.debug("Edit menu setup completed")

    def _execute_edit_command(self, command_name):
        """Execute an editing operation command through the command interface.
        
        Looks up and executes the specified command from the main window's
        edit_commands dictionary with proper error handling.
        
        Args:
            command_name (str): Name of the command to execute from edit_commands.
            
        Returns:
            The return value of the executed command, or False if the command
            fails or is not available.
            
        Note:
            All edit commands are expected to be simple callables without
            parameters. Complex operations should be handled within the
            command implementations themselves.
        """
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


class ViewMenuHandler(MenuHandlerBase):
    """Specialized handler for all view and display menu operations.
    
    This class manages the comprehensive View menu system, providing access to
    display modes, zoom controls, panel toggles, mouse label configurations,
    and theme selection. All operations are routed through the command interface
    for consistent behavior.
    
    Key responsibilities:
    - Waveform display mode selection (mono, stereo, overlay)
    - Zoom controls (in, out, fit to window)
    - Panel visibility toggles (metadata, analysis)
    - Mouse label preset management
    - Application theme selection
    
    The handler maintains QActionGroups for mutually exclusive options and
    provides state synchronization with application settings.
    
    Attributes:
        view_group: QActionGroup for waveform display modes.
        mouse_preset_group: QActionGroup for mouse label presets.
        theme_group: QActionGroup for theme selection.
    """

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

        self._setup_theme_menu(view_menu)

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
        self._apply_shortcut(zoom_in_action, 'view_commands', 'zoom_in')
        zoom_in_action.triggered.connect(lambda: self._execute_view_command("zoom_in"))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("🔍 Zoom &Out", self.main_window)
        # zoom_out_action.setShortcut(QKeySequence('Ctrl+-'))
        self._apply_shortcut(zoom_out_action, 'view_commands', 'zoom_out')
        zoom_out_action.triggered.connect(
            lambda: self._execute_view_command("zoom_out")
        )
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("⊞ &Fit to Window", self.main_window)
        # zoom_fit_action.setShortcut(QKeySequence('Ctrl+0'))
        self._apply_shortcut(zoom_fit_action, 'view_commands', 'zoom_fit')
        zoom_fit_action.triggered.connect(
            lambda: self._execute_view_command("zoom_fit")
        )
        view_menu.addAction(zoom_fit_action)

    def _setup_panel_toggles(self, view_menu):
        """Setup show/hide panel toggles."""
        toggle_metadata_action = QAction("Show/Hide &Metadata Tables", self.main_window)
        toggle_metadata_action.setCheckable(True)
        toggle_metadata_action.setChecked(True)
        self._apply_shortcut(toggle_metadata_action, 'view_commands', 'toggle_metadata')
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
        # self._setup_mouse_toggle_actions(mouse_labels_menu)

    def _setup_mouse_preset_actions(self, mouse_labels_menu):
        """Setup mouse label preset actions."""
        minimal_action = QAction("⚡ &Minimal (Fast)", self.main_window)
        minimal_action.setObjectName("minimal")
        minimal_action.setStatusTip("Show only essential info for better performance")
        minimal_action.setCheckable(True)
        minimal_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_minimal")
        )
        mouse_labels_menu.addAction(minimal_action)

        performance_action = QAction("⚙️ &Performance (Balanced)", self.main_window)
        performance_action.setObjectName("performance")
        performance_action.setStatusTip("Optimized balance of info and performance")
        performance_action.setCheckable(True)
        performance_action.setChecked(True)  # Default
        performance_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_performance")
        )
        mouse_labels_menu.addAction(performance_action)

        professional_action = QAction("🎛️ &Professional", self.main_window)
        professional_action.setObjectName("professional")
        professional_action.setStatusTip("Complete professional audio information")
        professional_action.setCheckable(True)
        professional_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_professional")
        )
        mouse_labels_menu.addAction(professional_action)

        professional_advanced_action = QAction("🎛️ &Professional+ (All Features)", self.main_window)
        professional_advanced_action.setObjectName("professional_advanced")
        professional_advanced_action.setStatusTip("All features including frequency analysis")
        professional_advanced_action.setCheckable(True)
        professional_advanced_action.triggered.connect(
            lambda: self._execute_view_command("set_mouse_labels_professional_advanced")
        )
        mouse_labels_menu.addAction(professional_advanced_action)


        # Group the preset actions for mutual exclusivity
        self.mouse_preset_group = QActionGroup(self.main_window)
        self.mouse_preset_group.addAction(minimal_action)
        self.mouse_preset_group.addAction(performance_action)
        self.mouse_preset_group.addAction(professional_action)
        self.mouse_preset_group.addAction(professional_advanced_action)

    def _setup_mouse_toggle_actions_old(self, mouse_labels_menu):
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

    def _setup_theme_menu(self, view_menu):
        """Setup theme selection submenu."""
        theme_menu = view_menu.addMenu("🎨 &Theme")

        # Light theme
        light_action = QAction("☀️ &Light Theme", self.main_window)
        light_action.setObjectName("light_theme")
        light_action.setCheckable(True)
        light_action.setChecked(True)  # Default
        light_action.triggered.connect(
            lambda: self._execute_view_command("apply_light_theme")
        )
        theme_menu.addAction(light_action)

        # Dark theme
        dark_action = QAction("🌙 &Dark Theme", self.main_window)
        dark_action.setObjectName("dark_theme")
        dark_action.setCheckable(True)
        dark_action.triggered.connect(
            lambda: self._execute_view_command("apply_dark_theme")
        )
        theme_menu.addAction(dark_action)

        # macOS dark theme
        macos_action = QAction("🍎 &macOS Dark", self.main_window)
        macos_action.setObjectName("macos_dark_theme")
        macos_action.setCheckable(True)
        macos_action.triggered.connect(
            lambda: self._execute_view_command("apply_macos_dark_theme")
        )
        theme_menu.addAction(macos_action)

        # Group voor mutual exclusivity
        self.theme_group = QActionGroup(self.main_window)
        self.theme_group.addAction(light_action)
        self.theme_group.addAction(dark_action)
        self.theme_group.addAction(macos_action)

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


class AudioMenuHandler(MenuHandlerBase):
    """Specialized handler for all audio playback menu operations.
    
    This class manages the Audio menu and provides access to all audio
    playback and control functions through the main window's audio_commands
    interface. It handles playback control, volume adjustment, and mute functionality.
    
    Key responsibilities:
    - Playback controls (play, pause, stop)
    - Volume controls (up, down, mute)
    - Audio navigation and seeking
    
    All audio operations are routed through the command interface for
    consistent behavior and proper error handling.
    """

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("AudioMenuHandler initialized")

    def setup_audio_menu(self, menubar):
        """Setup Audio menu with all actions."""
        audio_menu = menubar.addMenu("&Audio")

        # Playback controls
        play_pause_action = QAction("⏯️ &Play/Pause", self.main_window)
        #self._apply_shortcut(play_pause_action, 'audio_commands', 'play_pause')
        play_pause_action.triggered.connect(
            lambda: self._execute_audio_command("play_pause")
        )
        audio_menu.addAction(play_pause_action)

        stop_action = QAction("⏹️ &Stop", self.main_window)
        # stop_action.setShortcut(QKeySequence(Qt.Key_Escape))
        self._apply_shortcut(stop_action, 'audio_commands', 'stop')
        stop_action.triggered.connect(lambda: self._execute_audio_command("stop"))
        audio_menu.addAction(stop_action)

        audio_menu.addSeparator()

        # Volume controls
        volume_up_action = QAction("🔊 Volume +", self.main_window)
        # volume_up_action.setShortcut(QKeySequence(Qt.Key_PageUp))
        self._apply_shortcut(volume_up_action, 'audio_commands', 'volume_up')  
        volume_up_action.triggered.connect(
            lambda: self._execute_audio_command("volume_up")
        )
        audio_menu.addAction(volume_up_action)

        volume_down_action = QAction("🔉 Volume -", self.main_window)
        # volume_down_action.setShortcut(QKeySequence(Qt.Key_PageDown))
        self._apply_shortcut(volume_down_action, 'audio_commands', 'volume_down')  
        volume_down_action.triggered.connect(
            lambda: self._execute_audio_command("volume_down")
        )
        audio_menu.addAction(volume_down_action)

        mute_action = QAction("🔇 &Mute", self.main_window)
        # mute_action.setShortcut(QKeySequence(Qt.Key_M))
        self._apply_shortcut(mute_action, 'audio_commands', 'toggle_mute')  
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


class AnalysisMenuHandler(MenuHandlerBase):
    """Specialized handler for all analysis and reporting menu operations.
    
    This class manages the Analysis menu and provides access to analytical
    tools and dashboards through the main window's analysis_commands interface.
    It handles analytics dashboards, cue point analysis, and other analytical features.
    
    Key responsibilities:
    - Analytics dashboard access
    - Cue point analysis and overview
    - Statistical reporting tools
    
    All analysis operations are routed through the command interface for
    consistent behavior and progress indication.
    """

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("AnalysisMenuHandler initialized")

    def setup_analysis_menu(self, menubar):
        """Setup Analysis menu with all actions."""
        analysis_menu = menubar.addMenu("&Analysis")

        # Analytics dashboard
        analytics_action = QAction("📊 &Analytics Dashboard...", self.main_window)
        # analytics_action.setShortcut(QKeySequence('Ctrl+A'))
        self._apply_shortcut(analytics_action, 'analysis_commands', 'show_analytics')  
        analytics_action.triggered.connect(
            lambda: self._execute_analysis_command("show_analytics")
        )
        analysis_menu.addAction(analytics_action)

        # Cue points analysis
        cue_analysis_action = QAction("📍 &Cue Points Overview...", self.main_window)
        self._apply_shortcut(cue_analysis_action, 'analysis_commands', 'show_cue_analysis')
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


class HelpMenuHandler(MenuHandlerBase):
    """Specialized handler for help system and documentation menu operations.
    
    This class manages a streamlined Help menu that provides access to user
    documentation, keyboard shortcuts reference, and application information.
    The design consolidates help functions for better user experience.
    
    Key responsibilities:
    - Consolidated help and quick start guide
    - Keyboard shortcuts reference
    - Application about dialog
    
    All help operations are routed through the command interface with
    appropriate fallback error handling for missing help functions.
    """

    def __init__(self, main_window):
        self.main_window = main_window
        logger.debug("HelpMenuHandler initialized")

    def setup_help_menu(self, menubar):
        """Create and configure a streamlined Help menu with essential help functions.
        
        Sets up a consolidated Help menu with:
        - Help & Quick Start: Combined documentation and tutorial access
        - Keyboard Shortcuts: Reference for all application shortcuts
        - About: Application information and credits
        
        Args:
            menubar (QMenuBar): The main menu bar to add the Help menu to.
            
        Note:
            This streamlined approach consolidates multiple help functions into
            a single comprehensive help dialog for better user experience.
        """
        help_menu = menubar.addMenu("&Help")

        # CONSOLIDATED: Help & Quick Start (replaces 3 separate dialogs)
        help_quickstart_action = QAction("🚀 &Help & Quick Start", self.main_window)
        self._apply_shortcut(help_quickstart_action, 'help_commands', 'show_help_and_quickstart')
        help_quickstart_action.triggered.connect(
            lambda: self._execute_help_command("show_help_and_quickstart")
        )
        help_menu.addAction(help_quickstart_action)

        # Keyboard shortcuts (stays separate - useful as reference during work)
        shortcuts_action = QAction("⌨️ &Keyboard Shortcuts", self.main_window)
        # shortcuts_action.setShortcut(QKeySequence(Qt.Key_F1))
        self._apply_shortcut(shortcuts_action, 'help_commands', 'show_keyboard_shortcuts')  
        shortcuts_action.triggered.connect(
            lambda: self._execute_help_command("show_keyboard_shortcuts")
        )
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        # About (simplified)
        about_action = QAction("ℹ️ &About", self.main_window)
        self._apply_shortcut(about_action, 'help_commands', 'show_about')
        about_action.triggered.connect(lambda: self._execute_help_command("show_about"))
        help_menu.addAction(about_action)

        logger.debug("Streamlined Help menu setup completed")

    def _execute_help_command(self, command_name):
        """Execute a help operation command through the command interface.
        
        Looks up and executes the specified command from the main window's
        help_commands dictionary with proper error handling and user feedback.
        
        Args:
            command_name (str): Name of the command to execute from help_commands.
            
        Returns:
            The return value of the executed command, or False if the command
            fails or is not available.
            
        Note:
            Help commands may launch dialogs or display documentation. Errors
            are reported both to the log and to the user via status messages.
        """
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
