"""Batch Tag Editor for efficient tagging of multiple WAV files.

This module provides a comprehensive batch tagging solution for field recording
workflows. It enables users to apply tags to multiple WAV files simultaneously
with options for tag merging, backup creation, and progress tracking.

The batch tag editor integrates with the application's tag completion system
and uses centralized save strategies for consistency with the main WAV viewer.
It supports both replacement and merging of existing tags, with visual progress
feedback during processing.

Classes:
    BatchTagEditor: Main dialog for batch tagging operations

Functions:
    load_wav_files_from_config: Load WAV files from configuration directory
    main: Standalone testing and demonstration entry point

Features:
    - Multi-file selection with checkboxes
    - Tag autocompletion and validation
    - Merge or replace existing tags
    - Optional backup file creation
    - Progress tracking with visual feedback
    - Error handling and reporting
    - Integration with WavSaveStrategies
"""

import json
import logging
import os
import sys

from app_config import get_config_path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from tag_completer import FileTagAutocomplete
from wav_analyzer import wav_analyze
from wav_save_strategies import WavSaveStrategies

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


class BatchTagEditor(QDialog):
    """Dialog for batch tagging of multiple WAV files.

    A comprehensive batch tagging interface that allows users to efficiently
    apply tags to multiple WAV files simultaneously. The dialog provides
    file selection, tag input with autocompletion, and various processing
    options including tag merging and backup creation.

    The editor integrates with the application's existing tag completion
    system and uses centralized save strategies for consistency with the
    main WAV viewer functionality.

    Attributes:
        wav_files (list): List of WAV file paths to process
        file_list (QListWidget): Widget displaying files with checkboxes
        batch_tagger (FileTagAutocomplete): Tag input widget with completion
        merge_checkbox (QCheckBox): Option to merge with existing tags
        backup_checkbox (QCheckBox): Option to create backup files
        progress (QProgressBar): Visual progress indicator
        apply_btn (QPushButton): Button to start batch processing

    Args:
        parent (QWidget, optional): Parent widget. Defaults to None.
        wav_files (list, optional): List of WAV file paths to process.
            Defaults to empty list.
    """

    def __init__(self, parent=None, wav_files=None):
        """Initialize the batch tag editor dialog.

        Sets up the dialog with the provided WAV files and configures
        the user interface components for batch tagging operations.

        Args:
            parent (QWidget, optional): Parent widget for the dialog.
                Defaults to None.
            wav_files (list, optional): List of WAV file paths to process.
                Defaults to empty list if None provided.
        """
        super().__init__(parent)
        self.wav_files = wav_files or []
        self.setWindowTitle("Batch Tag Editor")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface components.

        Creates and arranges all UI elements including the file list with
        checkboxes, tag input field, processing options, progress bar,
        and control buttons. Configures layouts and connects signals.

        UI Components created:
        - Header with file count display
        - File list widget with checkbox selection
        - Tag autocomplete input field
        - Merge and backup option checkboxes
        - Progress bar (initially hidden)
        - Select all/none and action buttons
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<h3>🏷️ Batch Tag Editor - {len(self.wav_files)} files</h3>")
        layout.addWidget(header)

        # File list with checkboxes
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)

        for wav_file in self.wav_files:
            filename = os.path.basename(wav_file)
            item = QListWidgetItem(filename)
            item.setData(Qt.UserRole, wav_file)  # Store full path
            item.setCheckState(Qt.Checked)  # Default selected
            self.file_list.addItem(item)

        layout.addWidget(QLabel("Select files to tag:"))
        layout.addWidget(self.file_list)

        self.batch_tagger = FileTagAutocomplete()
        layout.addWidget(QLabel("Tags to add:"))
        layout.addWidget(self.batch_tagger)

        # Options
        options_layout = QHBoxLayout()

        self.merge_checkbox = QCheckBox("Merge with existing tags")
        self.merge_checkbox.setChecked(True)
        options_layout.addWidget(self.merge_checkbox)

        self.backup_checkbox = QCheckBox("Create backup files")
        self.backup_checkbox.setChecked(True)
        options_layout.addWidget(self.backup_checkbox)

        layout.addLayout(options_layout)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Select all/none buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(select_none_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.apply_btn = QPushButton("Apply Tags")
        self.apply_btn.clicked.connect(self.apply_tags)
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

    def select_all(self):
        """Select all files in the file list.

        Sets the check state of all file items to checked, enabling them for batch
        processing operations.
        """
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setCheckState(Qt.Checked)

    def select_none(self):
        """Deselect all files in the file list.

        Sets the check state of all file items to unchecked, excluding them from batch
        processing operations.
        """
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setCheckState(Qt.Unchecked)

    def get_selected_files(self):
        """Get list of selected files for processing.

        Iterates through the file list widget and returns the full paths
        of all files that are currently checked for processing.

        Returns:
            list[str]: List of full file paths for checked items
        """
        selected = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected

    def apply_tags(self):
        """Apply tags to selected files.

        Main batch processing method that validates selections, shows progress,
        and applies tags to all selected files. Handles errors gracefully and
        provides comprehensive feedback about the operation results.

        The method:
        1. Validates file selection and tag input
        2. Initializes progress tracking
        3. Processes each selected file individually
        4. Collects and reports errors
        5. Shows success/failure summary

        Shows warning dialogs if no files are selected or no tags provided.
        Updates progress bar during processing and displays final results.
        """
        selected_files = self.get_selected_files()
        new_tags = self.batch_tagger.get_current_tags()

        if not selected_files:
            QMessageBox.warning(self, "No Selection", "Select files to tag.")
            return

        if not new_tags:
            QMessageBox.warning(self, "No Tags", "Enter tags to apply.")
            return

        # Show progress
        self.progress.setVisible(True)
        self.progress.setMaximum(len(selected_files))
        self.apply_btn.setEnabled(False)

        success_count = 0
        errors = []

        for i, file_path in enumerate(selected_files):
            try:
                self.apply_tags_to_file(file_path, new_tags)
                success_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(file_path)}: {str(e)}")

            self.progress.setValue(i + 1)
            QApplication.processEvents()  # Keep UI responsive

        # Show results
        if errors:
            error_msg = f"✅ {success_count} files tagged\n❌ {len(errors)} errors:\n\n"
            error_msg += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more"
            QMessageBox.warning(self, "Batch Tagging Completed", error_msg)
        else:
            QMessageBox.information(
                self, "Success!", f"✅ All {success_count} files successfully tagged!"
            )

        self.accept()

    def apply_tags_to_file(self, file_path: str, new_tags: list[str]) -> None:
        """Apply tags to a single file using WavSaveStrategies.

        Processes a single WAV file by preparing metadata and using the
        centralized WavSaveStrategies for consistency with the main WAV viewer.
        Handles file validation, metadata preparation, and error reporting.

        This method replaces the old apply_tags_to_file implementation and
        provides centralized save functionality across the application.

        Args:
            file_path (str): Path to the WAV file to process
            new_tags (list[str]): List of new tags to apply to the file

        Raises:
            Exception: If file doesn't exist, isn't readable, or save operation fails.
                The exception message includes context about the specific failure.

        Note:
            Uses the backup checkbox setting to determine whether to create
            backup files during the save operation.
        """
        try:
            logger.debug(f"Starting to tag file: {file_path}")

            # Check if file exists and is readable
            if not os.path.exists(file_path):
                raise Exception(f"File does not exist: {file_path}")

            if not os.access(file_path, os.R_OK):
                raise Exception(f"File is not readable: {file_path}")

            # Prepare metadata using existing helper method
            logger.debug(f"Preparing metadata for: {os.path.basename(file_path)}")
            metadata = self._prepare_metadata(file_path, new_tags)
            logger.debug(f"Metadata prepared: {metadata}")

            # Use WavSaveStrategies for the actual save
            logger.debug(
                f"Calling WavSaveStrategies.save_batch_style for: {os.path.basename(file_path)}"
            )
            result = WavSaveStrategies.save_batch_style(
                source_path=file_path,
                metadata=metadata,
                use_backup=self.backup_checkbox.isChecked(),
            )

            logger.debug(f"WavSaveStrategies result: {result}")

            # Handle result
            if result is None:
                raise Exception("WavSaveStrategies.save_batch_style returned None")

            if not hasattr(result, "success"):
                raise Exception(
                    f"Invalid result object from WavSaveStrategies: {type(result)}"
                )

            if not result.success:
                error_msg = getattr(result, "error_message", "Unknown error")
                raise Exception(error_msg)

            # Log success (optional)
            output_path = getattr(result, "output_path", "unknown")
            logger.debug(
                f"Batch tagged: {os.path.basename(file_path)} -> {os.path.basename(output_path)}"
            )

        except Exception as e:
            logger.error(f"Failed to tag {os.path.basename(file_path)}: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error("Full traceback:", exc_info=True)
            # Re-raise with more context, chaining the original exception
            raise Exception(
                f"Failed to tag {os.path.basename(file_path)}: {str(e)}"
            ) from e

    def _prepare_metadata(self, file_path: str, new_tags: list[str]) -> dict[str, str]:
        """Prepare metadata dictionary for save operation.

        Handles tag merging, metadata extraction from existing files, and
        preparation of the complete metadata dictionary for injection into
        the WAV file. Supports both tag replacement and merging modes.

        The method:
        1. Analyzes the existing file to extract current metadata
        2. Gets default metadata from parent configuration
        3. Handles tag merging or replacement based on user settings
        4. Returns complete metadata dictionary for save operation

        Args:
            file_path (str): Path to the WAV file being processed
            new_tags (list[str]): List of new tags to apply

        Returns:
            dict[str, str]: Complete metadata dictionary with keys like
                INAM, IART, ICMT ready for WAV file injection

        Note:
            Uses wav_analyze to extract existing metadata and respects
            the merge checkbox setting for tag combination behavior.
        """
        # Try to analyze current file to get existing metadata
        current_info = {}
        if wav_analyze:
            try:
                result = wav_analyze(file_path)
                if result and isinstance(result, dict):
                    info_data = result.get("info", {})
                    # Extra safety check - ensure info_data is not None
                    current_info = info_data if info_data is not None else {}
                else:
                    logger.warning(
                        f"wav_analyze returned None or invalid result for {file_path}"
                    )
                    current_info = {}
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")
                current_info = {}

        # Get default metadata from parent's config
        if hasattr(self.parent(), "user_config"):
            defaults = self.parent().user_config.get("wav_tags", {})
        else:
            # Fallback defaults if no parent config
            defaults = {"INAM": "Recording", "IART": "Field Recorder", "ICMT": ""}

        # Prepare base metadata with defaults
        metadata = {}
        for key, default_val in defaults.items():
            metadata[key] = current_info.get(key, default_val)

        # Handle tags (ICMT field)
        new_tags_string = ", ".join(new_tags) if new_tags else ""
        existing_tags = metadata.get("ICMT", "").strip()

        if self.merge_checkbox.isChecked() and existing_tags:
            # Merge tags without duplicates
            existing_list = [t.strip() for t in existing_tags.split(",") if t.strip()]
            new_list = [t.strip() for t in new_tags if t.strip()]

            combined = existing_list.copy()
            for tag in new_list:
                if tag not in combined:
                    combined.append(tag)

            metadata["ICMT"] = ", ".join(combined)
        else:
            # Replace tags
            metadata["ICMT"] = new_tags_string

        logger.debug(f"Prepared metadata for {os.path.basename(file_path)}: {metadata}")
        return metadata


def load_wav_files_from_config() -> list[str]:
    """Load WAV files from user_config.json using the fieldrecording_dir path.

    Reads the user configuration file to determine the field recording directory
    and scans it for WAV files. Validates the directory exists and filters to
    only include existing, accessible files.

    The function expects the config file to contain a structure like:
    {
        "paths": {
            "fieldrecording_dir": "/path/to/recordings"
        }
    }

    Returns:
        list[str]: List of absolute WAV file paths from the fieldrecording_dir

    Raises:
        FileNotFoundError: If the user config file doesn't exist
        KeyError: If required keys ('paths' or 'fieldrecording_dir') are
            missing from the configuration
        ValueError: If the directory doesn't exist or no valid WAV files are found
        json.JSONDecodeError: If the config file contains invalid JSON
    """
    try:
        config_path = get_config_path("user_config.json")

        # Load user configuration
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        # Get fieldrecording_dir from paths section
        if "paths" not in config:
            raise KeyError("Config must contain 'paths' section")

        if "fieldrecording_dir" not in config["paths"]:
            raise KeyError("Config paths must contain 'fieldrecording_dir'")

        fieldrecording_dir = config["paths"]["fieldrecording_dir"]
        logger.info(f"Loading WAV files from fieldrecording_dir: {fieldrecording_dir}")

        if not os.path.exists(fieldrecording_dir):
            raise ValueError(
                f"Field recording directory does not exist: {fieldrecording_dir}"
            )

        # Scan directory for WAV files
        wav_files = []
        for filename in os.listdir(fieldrecording_dir):
            if filename.lower().endswith(".wav"):
                full_path = os.path.join(fieldrecording_dir, filename)
                wav_files.append(full_path)

        logger.info(f"Found {len(wav_files)} WAV files in fieldrecording_dir")

        # Filter to only existing files (extra safety check)
        existing_files = []
        for wav_file in wav_files:
            if os.path.exists(wav_file):
                existing_files.append(wav_file)
            else:
                logger.warning(f"File not found: {wav_file}")

        if not existing_files:
            raise ValueError("No valid WAV files found in fieldrecording_dir")

        logger.info(
            f"{len(existing_files)} valid WAV files loaded from fieldrecording_dir"
        )
        return existing_files

    except FileNotFoundError as e:
        raise FileNotFoundError(f"User config file not found: {config_path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in user config: {e}") from e


def main():
    """Standalone test for BatchTagEditor - loads from user_config.json.

    Entry point for testing and demonstration of the batch tag editor.
    Attempts to load WAV files from the user configuration and creates
    a batch tag editor dialog for testing purposes.

    If loading from configuration fails, falls back to fake file paths
    for demonstration purposes. Provides helpful tips and configuration
    guidance to the user.

    The function:
    1. Tries to load real WAV files from user_config.json
    2. Falls back to fake files if configuration loading fails
    3. Creates and displays the BatchTagEditor dialog
    4. Provides user tips and configuration guidance
    5. Runs the Qt application event loop
    """
    print("🧪 Testing BatchTagEditor with user_config.json loading...")
    app = QApplication(sys.argv)

    try:
        # Try to load WAV files from user config
        wav_files = load_wav_files_from_config()

        print(f"📁 Loaded {len(wav_files)} WAV files from user_config.json:")
        for i, path in enumerate(wav_files[:10], 1):  # Show first 10
            print(f"   {i}. {os.path.basename(path)}")

        if len(wav_files) > 10:
            print(f"   ... and {len(wav_files) - 10} more files")

    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"❌ Error loading from user_config.json: {e}")
        print("🔄 Falling back to fake WAV files for testing...")

        # Fallback to fake files for testing
        test_wav_files = [
            "test_recording_1.wav",
            "forest_sounds.wav",
            "urban_traffic.wav",
            "bird_calls_morning.wav",
            "rain_on_roof.wav",
        ]

        current_dir = os.getcwd()
        wav_files = [
            os.path.join(current_dir, "FieldRecordings", f) for f in test_wav_files
        ]

        print(f"📁 Using {len(wav_files)} fake WAV files for testing:")
        for i, path in enumerate(wav_files, 1):
            print(f"   {i}. {os.path.basename(path)}")

        print("\n💡 To use real WAV files, check your user_config.json:")
        try:

            config_path = get_config_path("user_config.json")
            print(f"   File location: {config_path}")
        except ImportError:
            print("   Check your user_config.json file")
        print(
            '   Make sure it contains: "paths": {"fieldrecording_dir": "/your/wav/directory"}'
        )

    # Create and show dialog
    dialog = BatchTagEditor(parent=None, wav_files=wav_files)
    dialog.show()

    print("✅ BatchTagEditor opened")
    print("💡 Tips:")
    print("   - Check/uncheck files to select")
    print("   - Add tags in the tag input field")
    print("   - Toggle merge/backup options")
    print("   - Click 'Apply Tags' to process files")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
