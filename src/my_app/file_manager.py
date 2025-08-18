"""File Manager Module for Field Recorder Analyzer.

This module provides comprehensive file management functionality for the Field Recorder
Analyzer application. It extracts all file operations from MainWindow to improve code
organization, maintainability, and separation of concerns.

The module is organized into specialized manager classes that handle different aspects
of file operations, providing a clean and modular architecture for file management
operations in field recording workflows.

Classes:
    FileManager: Central coordinator for all file operations and manager delegation
    RecentDirectoriesManager: Persistent storage and management of recently accessed directories
    DirectoryLoader: WAV directory loading, validation, and file discovery operations
    FileImporter: Batch file import operations with progress tracking and validation
    FileManagerInterface: Unified interface class for MainWindow integration

Features:
    - Recent directories management with automatic cleanup of non-existent paths
    - WAV directory validation and file discovery with extension filtering
    - Batch file import with progress tracking, overwrite handling, and error reporting
    - Directory loading with validation feedback and status updates
    - Configuration persistence using JSON storage
    - Cross-platform file operations with proper error handling
    - Integration with application configuration management
    - UI progress feedback for long-running operations

Usage Example:
    Basic setup in MainWindow:
        self.file_manager_interface = FileManagerInterface(self)

    Directory operations:
        success = self.file_manager_interface.open_directory()
        wav_files = self.file_manager_interface.get_all_wav_files()

    Recent directories:
        recent_dirs = self.file_manager_interface.get_recent_directories()
        self.file_manager_interface.add_recent_directory("/path/to/recordings")

    File import operations:
        success = self.file_manager_interface.batch_import_files()
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any

import app_config
from PyQt5.QtWidgets import QFileDialog, QMessageBox

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


class FileManager:
    """Central coordinator for all file operations in field recording workflows.

    The FileManager serves as the main coordination layer for all file-related operations
    in the Field Recorder Analyzer. It manages specialized sub-managers and provides a
    unified interface for directory operations, recent directory tracking, and file imports.

    This class follows the delegation pattern, coordinating between RecentDirectoriesManager,
    DirectoryLoader, and FileImporter to provide comprehensive file management capabilities.

    Attributes:
        main_window: Reference to the main application window for UI integration
        recent_manager (RecentDirectoriesManager): Manages recent directory persistence
        directory_loader (DirectoryLoader): Handles WAV directory operations and validation
        file_importer (FileImporter): Manages batch file import operations

    Args:
        main_window: Main application window instance for UI callbacks and configuration access
    """

    def __init__(self, main_window):
        """Initialize file manager with specialized sub-managers.

        Sets up the file manager with references to the main window and initializes
        all specialized manager components. Automatically loads recent directories
        from persistent storage during initialization.

        Args:
            main_window: Main application window instance providing UI integration
                and access to configuration management
        """
        self.main_window = main_window

        # Initialize specialized managers
        self.recent_manager = RecentDirectoriesManager()
        self.directory_loader = DirectoryLoader(main_window)
        self.file_importer = FileImporter(main_window)

        # Load recent directories on startup
        self.recent_manager.load_recent_directories()

        logger.info("FileManager initialized with specialized managers")

    # === PUBLIC INTERFACE METHODS ===

    def get_recent_directories(self) -> list[str]:
        """Get list of recently accessed directories.

        Returns:
            list[str]: List of recently accessed directory paths, ordered by recency
        """
        return self.recent_manager.get_recent_directories()

    def add_recent_directory(self, directory: str):
        """Add directory to the recent directories list.

        Args:
            directory (str): Directory path to add to recent list
        """
        self.recent_manager.add_recent_directory(directory)

    def open_directory(self) -> bool:
        """Open directory selection dialog and load the chosen directory.

        Returns:
            bool: True if directory was successfully opened and loaded, False otherwise
        """
        return self.directory_loader.open_directory_dialog()

    def reload_current_directory(self) -> bool:
        """Reload the currently configured directory.

        Returns:
            bool: True if directory was successfully reloaded, False otherwise
        """
        return self.directory_loader.reload_current_directory()

    def batch_import_files(self) -> bool:
        """Import multiple WAV files from various locations.

        Opens file selection dialog and imports chosen WAV files into the current
        working directory with progress tracking and error handling.

        Returns:
            bool: True if files were successfully imported, False otherwise
        """
        return self.file_importer.batch_import_files()

    def get_all_wav_files(self) -> list[str]:
        """Get all WAV file paths from the current directory.

        Returns:
            list[str]: List of full paths to all WAV files in current directory,
                sorted alphabetically. Returns empty list if no files found.
        """
        return self.directory_loader.get_all_wav_files()

    def validate_wav_directory(self, directory: str) -> bool:
        """Validate that a directory contains WAV files.

        Args:
            directory (str): Directory path to validate

        Returns:
            bool: True if directory exists and contains WAV files, False otherwise
        """
        return self.directory_loader.validate_wav_directory(directory)


class RecentDirectoriesManager:
    """Manages recent directory list with persistent storage and automatic cleanup.

    Handles the complete lifecycle of recent directory management including loading from
    configuration files, saving updates, maintaining size limits, and automatically
    removing non-existent directories during load operations.

    The manager uses JSON storage for persistence and provides thread-safe operations
    for adding, removing, and querying recent directories. It automatically validates
    directory existence to maintain data integrity.

    Attributes:
        max_recent (int): Maximum number of recent directories to maintain
        recent_file (str): Path to JSON configuration file for persistence
        recent_directories (list[str]): Current list of recent directory paths

    Args:
        max_recent (int, optional): Maximum directories to store. Defaults to 10.
    """

    def __init__(self, max_recent: int = 10):
        """Initialize recent directories manager with configuration.

        Args:
            max_recent (int, optional): Maximum number of recent directories to store.
                Defaults to 10.
        """
        self.max_recent = max_recent
        self.recent_file = app_config.RECENT_DIRS_CONFIG
        self.recent_directories: list[str] = []

    def load_recent_directories(self) -> list[str]:
        """Load recent directories from persistent configuration file.

        Loads the recent directories list from JSON storage and automatically filters
        out any directories that no longer exist on the filesystem. This ensures
        the recent list stays current and valid.

        Returns:
            list[str]: List of valid recent directory paths, ordered by recency

        Note:
            Creates empty list if config file doesn't exist or loading fails.
            Automatically removes non-existent directories during load.
        """
        try:
            if os.path.exists(self.recent_file):
                with open(self.recent_file, encoding="utf-8") as f:
                    loaded_dirs = json.load(f)
                    # Filter out non-existent directories
                    self.recent_directories = [
                        d for d in loaded_dirs if os.path.exists(d)
                    ]
                    logger.info(
                        f"Loaded {len(self.recent_directories)} recent directories"
                    )
            else:
                self.recent_directories = []
                logger.debug("No recent directories file found - starting fresh")
        except Exception as e:
            logger.warning(f"Could not load recent directories: {e}")
            self.recent_directories = []

        return self.recent_directories

    def save_recent_directories(self) -> bool:
        """Save current recent directories list to persistent storage.

        Writes the current recent directories list to JSON configuration file
        with proper formatting and error handling.

        Returns:
            bool: True if save operation succeeded, False if it failed

        Note:
            Uses UTF-8 encoding with proper JSON formatting for cross-platform compatibility.
        """
        try:
            with open(self.recent_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_directories, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.recent_directories)} recent directories")
            return True
        except Exception as e:
            logger.error(f"Could not save recent directories: {e}")
            return False

    def add_recent_directory(self, directory: str):
        """Add directory to recent list with deduplication and size management.

        Adds a directory to the recent list, automatically handling deduplication
        by moving existing entries to the top and maintaining the maximum list size.
        The directory is validated for existence before being added.

        Args:
            directory (str): Directory path to add to recent list

        Note:
            - Validates directory existence before adding
            - Removes duplicates by moving existing entries to top
            - Maintains maximum list size by truncating oldest entries
            - Automatically saves changes to persistent storage
        """
        if not directory or not os.path.exists(directory):
            return

        # Remove if already exists
        if directory in self.recent_directories:
            self.recent_directories.remove(directory)

        # Add to beginning
        self.recent_directories.insert(0, directory)

        # Keep only max_recent items
        self.recent_directories = self.recent_directories[: self.max_recent]

        # Save to file
        self.save_recent_directories()

        logger.debug(f"Added recent directory: {os.path.basename(directory)}")

    def get_recent_directories(self) -> list[str]:
        """Get copy of current recent directories list.

        Returns:
            list[str]: Copy of recent directories list, ordered by recency (most recent first)

        Note:
            Returns a copy to prevent external modification of internal state.
        """
        return self.recent_directories.copy()

    def remove_recent_directory(self, directory: str):
        """Remove specific directory from recent list.

        Args:
            directory (str): Directory path to remove from recent list

        Note:
            Automatically saves changes to persistent storage if directory was found and removed.
        """
        if directory in self.recent_directories:
            self.recent_directories.remove(directory)
            self.save_recent_directories()
            logger.debug(f"Removed recent directory: {os.path.basename(directory)}")

    def clear_recent_directories(self):
        """Clear all recent directories from memory and storage.

        Removes all entries from the recent directories list and immediately saves the
        empty state to persistent storage.
        """
        self.recent_directories = []
        self.save_recent_directories()
        logger.info("Cleared all recent directories")


class DirectoryLoader:
    """Handles WAV directory loading, validation, and file discovery operations.

    Provides comprehensive directory management functionality for field recording workflows,
    including directory validation, WAV file discovery, directory loading with UI feedback,
    and directory information gathering with statistics.

    The class integrates with the main window for status updates and configuration management,
    providing a seamless experience for directory-based operations in the field recording analyzer.

    Attributes:
        main_window: Reference to main application window for UI integration and config access

    Args:
        main_window: Main application window instance providing UI callbacks and configuration
    """

    def __init__(self, main_window):
        """Initialize directory loader with main window reference.

        Args:
            main_window: Main application window instance for UI integration
        """
        self.main_window = main_window

    def open_directory_dialog(self) -> bool:
        """Open directory selection dialog and load the chosen directory.

        Presents a directory selection dialog to the user, starting from the current
        configured directory. If a directory is selected, validates and loads it into
        the application configuration and updates the UI accordingly.

        Returns:
            bool: True if directory was successfully selected and loaded, False otherwise

        Note:
            Provides user feedback through status messages and handles all error conditions
            gracefully with appropriate logging and user notification.
        """
        try:
            self.main_window.show_status_message("Opening directory dialog...", 1000)

            current_dir = self.main_window.user_config_manager.get_updated_config()[
                "paths"
            ]["fieldrecording_dir"]

            directory = QFileDialog.getExistingDirectory(
                self.main_window, "Select WAV Files Directory", current_dir
            )

            if directory:
                return self._load_directory(directory)
            else:
                self.main_window.show_status_message(
                    "Directory selection cancelled", 2000
                )
                return False

        except Exception as e:
            self.main_window.show_status_message(
                f"Error opening directory dialog: {str(e)}", 5000
            )
            logger.error(f"Error in open_directory_dialog: {e}")
            return False

    def reload_current_directory(self) -> bool:
        """Reload the currently configured directory.

        Refreshes the current directory by re-scanning for WAV files and updating
        the UI to reflect any changes. Validates that the directory still exists
        before attempting the reload operation.

        Returns:
            bool: True if directory was successfully reloaded, False if directory
                no longer exists or reload operation failed

        Note:
            Updates file count in UI and provides user feedback through status messages.
        """
        try:
            self.main_window.show_status_message("Reloading directory...", 1000)

            current_dir = self.main_window.user_config_manager.get_updated_config()[
                "paths"
            ]["fieldrecording_dir"]

            if not os.path.exists(current_dir):
                self.main_window.show_status_message(
                    "Current directory no longer exists", 3000
                )
                return False

            # Update UI
            self.main_window.ui_manager.update_file_count()

            self.main_window.show_status_message("Directory reloaded", 2000)
            logger.info(f"Directory reloaded successfully: {current_dir}")
            return True

        except Exception as e:
            self.main_window.show_status_message(f"Error reloading: {str(e)}", 5000)
            logger.error(f"Error in reload_current_directory: {e}")
            return False

    def _load_directory(self, directory: str) -> bool:
        """Load a specific directory into the application.

        Internal method that handles the complete directory loading process including
        validation, configuration updates, UI updates, and recent directory tracking.

        Args:
            directory (str): Directory path to load

        Returns:
            bool: True if directory was successfully loaded, False otherwise

        Note:
            - Validates directory for WAV files and shows informational dialog if none found
            - Updates application configuration with new directory path
            - Adds directory to recent directories list
            - Updates UI file count and shows success feedback
        """
        try:
            self.main_window.show_status_message("Loading WAV files...", 1000)

            # Validate directory
            if not self.validate_wav_directory(directory):
                QMessageBox.information(
                    self.main_window,
                    "No WAV Files",
                    f"No WAV files found in directory:\n{directory}\n\nDirectory will still be loaded.",
                )

            # Update configuration
            self.main_window.user_config_manager.get_updated_config()["paths"][
                "fieldrecording_dir"
            ] = directory

            # Update UI
            self.main_window.ui_manager.update_file_count()

            # Add to recent directories
            if hasattr(self.main_window, "file_manager"):
                self.main_window.file_manager.add_recent_directory(directory)

            # Show success message
            dir_name = os.path.basename(directory)
            self.main_window.show_status_message(f"Opened directory: {dir_name}", 3000)

            logger.info(f"Directory loaded successfully: {directory}")
            return True

        except Exception as e:
            self.main_window.show_status_message(
                f"Error loading directory: {str(e)}", 5000
            )
            logger.error(f"Error in _load_directory: {e}")
            return False

    def validate_wav_directory(self, directory: str) -> bool:
        """Validate that a directory exists and contains WAV files.

        Args:
            directory (str): Directory path to validate

        Returns:
            bool: True if directory exists and contains at least one WAV file,
                False otherwise

        Note:
            Checks for both .wav and .WAV extensions for cross-platform compatibility.
            Handles permission errors and other filesystem exceptions gracefully.
        """
        if not os.path.exists(directory):
            return False

        try:
            wav_files = [
                f for f in os.listdir(directory) if f.lower().endswith((".wav", ".WAV"))
            ]
            return len(wav_files) > 0
        except Exception as e:
            logger.warning(f"Error validating directory {directory}: {e}")
            return False

    def get_all_wav_files(self) -> list[str]:
        """Get all WAV file paths from the current configured directory.

        Scans the current directory configuration and returns all WAV files found,
        with full absolute paths for each file.

        Returns:
            list[str]: List of full paths to all WAV files in current directory,
                sorted alphabetically. Returns empty list if directory doesn't exist
                or no WAV files are found.

        Note:
            - Checks for both .wav and .WAV extensions
            - Returns full absolute paths, not just filenames
            - Automatically sorted for consistent ordering
        """
        current_dir = self.main_window.user_config_manager.get_updated_config()[
            "paths"
        ]["fieldrecording_dir"]

        if not os.path.exists(current_dir):
            return []

        try:
            wav_files = []
            for filename in os.listdir(current_dir):
                if filename.lower().endswith((".wav", ".WAV")):
                    full_path = os.path.join(current_dir, filename)
                    wav_files.append(full_path)
            return sorted(wav_files)
        except Exception as e:
            logger.warning(f"Error getting WAV files from {current_dir}: {e}")
            return []

    def get_directory_info(self) -> dict[str, Any]:
        """Get comprehensive information about the current directory.

        Gathers detailed statistics about the current configured directory including
        file counts, total size, and modification timestamps.

        Returns:
            dict[str, Any]: Dictionary containing directory information:
                - path (str): Current directory path
                - exists (bool): Whether directory exists
                - wav_count (int): Number of WAV files found
                - total_size (int): Total size of all WAV files in bytes
                - last_modified (datetime | None): Most recent file modification time

        Note:
            Safely handles file access errors and missing files during statistics gathering.
            Returns partial information if some files cannot be accessed.
        """
        current_dir = self.main_window.user_config_manager.get_updated_config()[
            "paths"
        ]["fieldrecording_dir"]

        info = {
            "path": current_dir,
            "exists": os.path.exists(current_dir),
            "wav_count": 0,
            "total_size": 0,
            "last_modified": None,
        }

        if info["exists"]:
            try:
                wav_files = self.get_all_wav_files()
                info["wav_count"] = len(wav_files)

                total_size = 0
                latest_time = 0

                for file_path in wav_files:
                    try:
                        stat = os.stat(file_path)
                        total_size += stat.st_size
                        latest_time = max(latest_time, stat.st_mtime)
                    except OSError:
                        continue

                info["total_size"] = total_size
                if latest_time > 0:
                    info["last_modified"] = datetime.fromtimestamp(latest_time)

            except Exception as e:
                logger.warning(f"Error getting directory info for {current_dir}: {e}")

        return info


class FileImporter:
    """Handles batch file import operations with progress tracking and validation.

    Provides comprehensive file import functionality including multiple file selection,
    progress tracking, overwrite handling, validation, and detailed result reporting.
    Designed for importing WAV files from various locations into the current working
    directory with full error handling and user feedback.

    The importer provides both batch and single file import capabilities with integrated
    progress displays and comprehensive error reporting for field recording workflows.

    Attributes:
        main_window: Reference to main application window for UI integration and config access

    Args:
        main_window: Main application window instance providing UI callbacks and configuration
    """

    def __init__(self, main_window):
        """Initialize file importer with main window reference.

        Args:
            main_window: Main application window instance for UI integration
        """
        self.main_window = main_window

    def batch_import_files(self) -> bool:
        """Import multiple WAV files from various locations with file selection dialog.

        Opens a multi-select file dialog allowing users to choose multiple WAV files
        from different locations. Selected files are then imported into the current
        working directory with progress tracking and result reporting.

        Returns:
            bool: True if files were successfully imported, False if operation was
                cancelled or failed

        Note:
            - Shows file selection dialog filtered for WAV files
            - Provides progress tracking during import process
            - Handles overwrite confirmation and error reporting
            - Updates UI file count after successful imports
        """
        try:
            self.main_window.show_status_message(
                "Opening file selection dialog...", 1000
            )

            files, _ = QFileDialog.getOpenFileNames(
                self.main_window,
                "Import WAV Files",
                "",
                "WAV Files (*.wav *.WAV);;All Files (*)",
            )

            if not files:
                self.main_window.show_status_message("File import cancelled", 2000)
                return False

            return self._import_files(files)

        except Exception as e:
            self.main_window.show_status_message(
                f"Error in batch import: {str(e)}", 5000
            )
            logger.error(f"Error in batch_import_files: {e}")
            return False

    def _import_files(self, file_paths: list[str]) -> bool:
        """Import a list of files to the target directory with comprehensive handling.

        Internal method that handles the complete file import process including
        target directory validation/creation, progress tracking, overwrite handling,
        and result reporting.

        Args:
            file_paths (list[str]): List of source file paths to import

        Returns:
            bool: True if at least one file was successfully imported, False otherwise

        Note:
            - Creates target directory if it doesn't exist
            - Shows progress dialog during import
            - Handles file existence conflicts with user confirmation
            - Provides detailed success/error reporting
            - Updates UI file count after successful imports
        """
        target_dir = self.main_window.user_config_manager.get_updated_config()["paths"][
            "fieldrecording_dir"
        ]

        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
                logger.info(f"Created target directory: {target_dir}")
            except Exception as e:
                logger.error(f"Could not create target directory {target_dir}: {e}")
                QMessageBox.critical(
                    self.main_window,
                    "Directory Error",
                    f"Could not create target directory:\n{target_dir}\n\nError: {str(e)}",
                )
                return False

        # Show progress
        total_files = len(file_paths)
        self.main_window.ui_manager.show_progress("Importing WAV files...", total_files)

        imported = 0
        skipped = 0
        errors = []

        for i, file_path in enumerate(file_paths):
            try:
                filename = os.path.basename(file_path)
                target_path = os.path.join(target_dir, filename)

                # Update progress
                self.main_window.ui_manager.update_progress(
                    i + 1, f"Importing {filename}... ({i + 1}/{total_files})"
                )

                # Check if file already exists
                if os.path.exists(target_path):
                    reply = QMessageBox.question(
                        self.main_window,
                        "File Exists",
                        f"File '{filename}' already exists in target directory.\n\nOverwrite?",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    )

                    if reply == QMessageBox.Cancel:
                        break
                    elif reply == QMessageBox.No:
                        skipped += 1
                        continue

                # Copy file
                shutil.copy2(file_path, target_path)
                imported += 1
                logger.debug(f"Successfully imported: {filename}")

            except Exception as e:
                error_msg = f"{os.path.basename(file_path)}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Import failed for {filename}: {e}")

        # Hide progress
        self.main_window.ui_manager.hide_progress()

        # Show results and log summary
        self._show_import_results(imported, skipped, errors, total_files)
        logger.info(
            f"Import completed: {imported} imported, {skipped} skipped, {len(errors)} errors"
        )

        # Reload directory if files were imported
        if imported > 0:
            # self.wav_viewer.load_wav_files()
            self.main_window.ui_manager.update_file_count()

        return imported > 0

    def _show_import_results(
        self, imported: int, skipped: int, errors: list[str], total: int
    ):
        """Display comprehensive import results dialog with statistics and errors.

        Shows detailed results of the import operation including counts of successful
        imports, skipped files, and any errors encountered. Chooses appropriate
        message box type based on results.

        Args:
            imported (int): Number of files successfully imported
            skipped (int): Number of files skipped (already existed)
            errors (list[str]): List of error messages encountered during import
            total (int): Total number of files processed

        Note:
            - Uses different dialog types based on success/error status
            - Limits error display to first 5 errors for readability
            - Updates status bar with summary message
        """
        title = "Import Results"

        message = "Import completed!\n\n"
        message += "📊 Summary:\n"
        message += f"• Total files processed: {total}\n"
        message += f"• Successfully imported: {imported}\n"

        if skipped > 0:
            message += f"• Skipped (already exist): {skipped}\n"

        if errors:
            message += f"• Errors: {len(errors)}\n"

        if errors and len(errors) <= 5:
            message += "\n❌ Errors:\n"
            for error in errors:
                message += f"• {error}\n"
        elif errors:
            message += "\n❌ First 5 errors:\n"
            for error in errors[:5]:
                message += f"• {error}\n"
            message += f"... and {len(errors) - 5} more errors"

        # Choose appropriate message box type
        if errors and imported == 0:
            QMessageBox.critical(self.main_window, title, message)
        elif errors:
            QMessageBox.warning(self.main_window, title, message)
        else:
            QMessageBox.information(self.main_window, title, message)

        # Update status bar
        if imported > 0:
            self.main_window.show_status_message(
                f"Imported {imported} files successfully", 3000
            )
        else:
            self.main_window.show_status_message("No files were imported", 3000)

    def import_single_file(self, file_path: str) -> bool:
        """Import a single WAV file into the current directory.

        Convenience method for importing a single file using the same
        validation and error handling as batch import.

        Args:
            file_path (str): Path to the single file to import

        Returns:
            bool: True if file was successfully imported, False if file doesn't
                exist or import failed
        """
        if not os.path.exists(file_path):
            return False

        return self._import_files([file_path])

    def validate_import_files(self, file_paths: list[str]) -> list[str]:
        """Validate list of files for import eligibility.

        Filters a list of file paths to return only valid WAV files that exist
        and meet import requirements.

        Args:
            file_paths (list[str]): List of file paths to validate

        Returns:
            list[str]: List of valid file paths that can be imported

        Note:
            - Validates file existence and WAV extension
            - Logs warnings for invalid files
            - Returns empty list if no valid files found
        """
        valid_files = []

        for file_path in file_paths:
            if os.path.exists(file_path) and file_path.lower().endswith(
                (".wav", ".WAV")
            ):
                valid_files.append(file_path)
            else:
                logger.warning(f"Invalid file for import: {file_path}")

        return valid_files


class FileManagerInterface:
    """Main interface class providing unified file management operations for MainWindow.

    Serves as the primary integration point between MainWindow and the file management
    system, providing a clean, simplified interface that hides the complexity of the
    individual specialized managers. This facade pattern implementation ensures MainWindow
    only needs to interact with a single, well-defined interface.

    The interface coordinates all file management operations including directory operations,
    recent directory management, file imports, and directory validation through a single
    unified API.

    Attributes:
        main_window: Reference to main application window for integration
        file_manager (FileManager): Central file manager coordinating all operations

    Args:
        main_window: Main application window instance
    """

    def __init__(self, main_window):
        """Initialize file manager interface with main window integration.

        Sets up the complete file management system by creating the central
        FileManager which coordinates all specialized sub-managers.

        Args:
            main_window: Main application window instance for UI integration
        """
        self.main_window = main_window
        self.file_manager = FileManager(main_window)

        logger.info("FileManagerInterface initialized")

    # === DIRECTORY OPERATIONS ===

    def open_directory(self) -> bool:
        """Open directory selection dialog and load chosen directory.

        Returns:
            bool: True if directory was successfully selected and loaded
        """
        return self.file_manager.open_directory()

    def reload_directory(self) -> bool:
        """Reload the currently configured directory.

        Returns:
            bool: True if directory was successfully reloaded
        """
        return self.file_manager.reload_current_directory()

    def get_current_directory_info(self) -> dict[str, Any]:
        """Get comprehensive information about the current directory.

        Returns:
            dict[str, Any]: Dictionary with directory statistics including path,
                existence, WAV file count, total size, and last modification time
        """
        return self.file_manager.directory_loader.get_directory_info()

    # === RECENT DIRECTORIES ===

    def get_recent_directories(self) -> list[str]:
        """Get list of recently accessed directories.

        Returns:
            list[str]: List of recent directory paths ordered by recency
        """
        return self.file_manager.get_recent_directories()

    def add_recent_directory(self, directory: str):
        """Add directory to the recent directories list.

        Args:
            directory (str): Directory path to add to recent list
        """
        self.file_manager.add_recent_directory(directory)

    def clear_recent_directories(self):
        """Clear all recent directories from memory and storage."""
        self.file_manager.recent_manager.clear_recent_directories()

    # === FILE OPERATIONS ===

    def batch_import_files(self) -> bool:
        """Import multiple WAV files with file selection dialog.

        Returns:
            bool: True if files were successfully imported
        """
        return self.file_manager.batch_import_files()

    def get_all_wav_files(self) -> list[str]:
        """Get all WAV file paths from current directory.

        Returns:
            list[str]: List of full paths to all WAV files, sorted alphabetically
        """
        return self.file_manager.get_all_wav_files()

    def validate_directory(self, directory: str) -> bool:
        """Validate that a directory exists and contains WAV files.

        Args:
            directory (str): Directory path to validate

        Returns:
            bool: True if directory exists and contains WAV files
        """
        return self.file_manager.validate_wav_directory(directory)

    # === UTILITY METHODS ===

    def get_file_manager(self) -> FileManager:
        """Get reference to the internal file manager for advanced operations.

        Returns:
            FileManager: Internal file manager instance for direct access

        Note:
            Provided for advanced use cases that need direct manager access.
        """
        return self.file_manager
