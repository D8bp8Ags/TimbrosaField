"""WAV Save Manager Module.

Centralizes all save-related UI logic including dialogs, user confirmations,
and success/error feedback. Removes ~170 lines from WavViewer while providing
reusable save functionality across the application.

Usage:
    from wav_save_manager import WavSaveManager

    # In WavViewer.save_tags():
    manager = WavSaveManager(parent=self)
    result = manager.show_save_dialog_and_execute(
        filename=self.filename,
        metadata=metadata,
        new_tags=['nature', 'birds'],
        existing_tags='forest, morning',
        user_config=self.user_config
    )

    if result:
        self.load_wav_files(select_path=result.output_path)
        if hasattr(self, 'tagger_widget'):
            self.tagger_widget.clear_tags()
"""

import logging
import os
from typing import Any, Optional

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)
from wav_analyzer import wav_analyze
from wav_save_strategies import SaveResult, WavSaveStrategies

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


class WavSaveManager:
    """Centralized manager for WAV file save operations with UI.

    This class handles the complete save workflow: 1. Shows save options dialog 2.
    Handles user confirmations 3. Executes save via WavSaveStrategies 4. Shows
    success/error feedback 5. Returns result for further processing

    Eliminates ~170 lines from WavViewer while providing reusable save functionality for
    other parts of the application.
    """

    def __init__(self, parent=None):
        """Initialize the save manager.

        Args:     parent: Parent widget for dialogs (usually WavViewer instance)
        """
        self.parent = parent
        logger.debug("WavSaveManager initialized")

    def show_save_dialog_and_execute(
        self,
        filename: str,
        metadata: dict[str, str],
        new_tags: list[str] = None,
        existing_tags: str = "",
        user_config: dict[str, Any] = None,
    ) -> Optional["SaveResult"]:
        """Show save dialog and execute chosen save operation.

        This is the main entry point that handles the complete save workflow.

        Args:     filename: Path to current WAV file     metadata: Metadata dictionary
        to save     new_tags: List of new tags to add     existing_tags: String of
        existing tags     user_config: User configuration dictionary

        Returns:     SaveResult object if successful, None if cancelled or failed
        """
        try:
            # Import here to avoid circular imports

            # Validate inputs
            if not filename or not os.path.exists(filename):
                self._show_error("Invalid file", f"File does not exist: {filename}")
                return None

            if not metadata:
                self._show_error("No metadata", "No metadata to save")
                return None

            # Prepare new tags string
            new_tags_string = ", ".join(new_tags) if new_tags else ""

            # Check if there's anything to save
            has_metadata_changes = self._check_metadata_changes(filename, metadata)

            if not new_tags_string and not has_metadata_changes:
                self._show_info(
                    "Nothing to Save",
                    "No new tags entered and no metadata changes detected.",
                )
                return None

            # Show save options dialog
            dialog = WavSaveOptionsDialog(
                parent=self.parent,
                filename=filename,
                new_tags=(
                    new_tags_string
                    if new_tags_string
                    else "No new tags (metadata changes only)"
                ),
                existing_tags=existing_tags,
            )

            if dialog.exec_() != QDialog.Accepted:
                logger.debug("Save cancelled by user")
                return None

            # Get user choices
            save_method = dialog.get_save_method()
            custom_name = dialog.get_custom_name()
            merge_tags = dialog.should_merge_tags()

            logger.debug(
                f"Save options: method={save_method}, custom='{custom_name}', merge={merge_tags}"
            )

            # Process tags if there are new ones
            if new_tags_string:
                metadata = self._merge_tags_if_needed(
                    metadata, new_tags_string, existing_tags, merge_tags
                )

            # Execute save operation
            result = self._execute_save_strategy(
                save_method=save_method,
                filename=filename,
                metadata=metadata,
                custom_name=custom_name,
                user_config=user_config,
            )

            # Show result to user
            if result and result.success:
                self._show_save_success(result, new_tags_string, has_metadata_changes)
                logger.info(f"Save successful: {result.operation_type}")
            else:
                error_msg = result.error_message if result else "Unknown error"
                self._show_error("Save Error", f"Error saving file:\n{error_msg}")
                logger.error(f"Save failed: {error_msg}")
                result = None

            return result

        except Exception as e:
            self._show_error(
                "Unexpected Error", f"An unexpected error occurred:\n{str(e)}"
            )
            logger.error(f"Unexpected error in save workflow: {e}")
            return None

    def _check_metadata_changes(self, filename: str, metadata: dict[str, str]) -> bool:
        """Check if metadata has changes compared to original file.

        Args:     filename: Path to WAV file     metadata: Current metadata dictionary

        Returns:     True if there are changes, False otherwise
        """
        try:

            result = wav_analyze(filename)
            original_info = result.get("info", {})

            return any(
                metadata.get(key, "") != original_info.get(key, "")
                for key in metadata.keys()
            )
        except Exception as e:
            logger.warning(f"Could not check metadata changes: {e}")
            return True  # Assume changes if we can't check

    def _merge_tags_if_needed(
        self,
        metadata: dict[str, str],
        new_tags_string: str,
        existing_tags: str,
        merge_tags: bool,
    ) -> dict[str, str]:
        """Merge or replace tags based on user choice.

        Args:     metadata: Current metadata dictionary     new_tags_string: New tags as
        comma-separated string     existing_tags: Existing tags as comma-separated
        string     merge_tags: Whether to merge (True) or replace (False)

        Returns:     Updated metadata dictionary
        """
        if merge_tags and existing_tags.strip():
            # Merge tags without duplicates
            existing_list = [
                tag.strip() for tag in existing_tags.split(",") if tag.strip()
            ]
            new_list = [
                tag.strip() for tag in new_tags_string.split(",") if tag.strip()
            ]

            combined = existing_list.copy()
            for tag in new_list:
                if tag not in combined:
                    combined.append(tag)

            metadata["ICMT"] = ", ".join(combined)
            logger.debug(f"Tags merged: '{metadata['ICMT']}'")
        else:
            # Replace tags
            metadata["ICMT"] = new_tags_string
            logger.debug(f"Tags replaced: '{metadata['ICMT']}'")

        return metadata

    def _execute_save_strategy(
        self,
        save_method: int,
        filename: str,
        metadata: dict[str, str],
        custom_name: str,
        user_config: dict[str, Any],
    ) -> Optional["SaveResult"]:
        """Execute the chosen save strategy.

        Args:     save_method: Chosen save method (1-4)     filename: Source file path
        metadata: Metadata to save     custom_name: Custom filename (if method 4)
        user_config: User configuration

        Returns:     SaveResult object or None if failed
        """
        try:

            # Get output directory from config
            output_dir = None
            if user_config and "paths" in user_config:
                output_dir = user_config["paths"].get("fieldrecording_dir")

            # Create strategy mapping
            strategies = {
                1: lambda: WavSaveStrategies.save_as_edit_copy(
                    filename, metadata, output_dir
                ),
                2: lambda: WavSaveStrategies.save_in_place(
                    filename, metadata, self._confirm_overwrite
                ),
                3: lambda: WavSaveStrategies.save_with_backup(filename, metadata),
                4: lambda: WavSaveStrategies.save_with_custom_name(
                    filename, metadata, custom_name, output_dir
                ),
            }

            if save_method not in strategies:
                logger.error(f"Unknown save method: {save_method}")
                return None

            return strategies[save_method]()

        except Exception as e:
            logger.error(f"Error executing save strategy: {e}")
            return None

    def _confirm_overwrite(self) -> bool:
        """Show confirmation dialog for overwrite operations.

        Returns:     True if user confirms, False otherwise
        """
        reply = QMessageBox.question(
            self.parent,
            "Overwrite Original?",
            "Are you sure you want to overwrite the original file?\n\n"
            "This CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default to No for safety
        )

        confirmed = reply == QMessageBox.Yes
        logger.debug(f"Overwrite confirmation: {confirmed}")
        return confirmed

    def _show_save_success(
        self, result: "SaveResult", new_tags_string: str, has_metadata_changes: bool
    ) -> None:
        """Show success message based on save result.

        Args:     result: SaveResult from save operation     new_tags_string: New tags
        that were saved     has_metadata_changes: Whether metadata was changed
        """
        # Determine what was saved
        if new_tags_string and has_metadata_changes:
            save_type = "Tags and metadata"
        elif new_tags_string:
            save_type = "Tags"
        else:
            save_type = "Metadata"

        # Create message based on operation type
        messages = {
            "edit_copy": f"{save_type} successfully saved!\n\nFile saved as:\n{os.path.basename(result.output_path)}",
            "in_place": f"{save_type} successfully saved!\n\nOriginal file has been updated.",
            "with_backup": f"{save_type} successfully saved!\n\nOriginal file updated.\nBackup saved as: {os.path.basename(result.backup_path)}",
            "custom_name": f"{save_type} successfully saved!\n\nFile saved as:\n{os.path.basename(result.output_path)}",
        }

        message = messages.get(
            result.operation_type, f"{save_type} successfully saved!"
        )
        self._show_info("Save Successful", message)

    def _show_error(self, title: str, message: str) -> None:
        """Show error message dialog."""
        QMessageBox.critical(self.parent, title, message)

    def _show_info(self, title: str, message: str) -> None:
        """Show information message dialog."""
        QMessageBox.information(self.parent, title, message)


class WavSaveOptionsDialog(QDialog):
    """Enhanced save options dialog.

    Replaces SimpleSaveDialog with better integration and cleaner code. This dialog
    handles all user choices for save operations.
    """

    def __init__(
        self,
        parent=None,
        filename: str = "",
        new_tags: str = "",
        existing_tags: str = "",
    ):
        """Initialize the save options dialog.

        Args:     parent: Parent widget     filename: Current filename     new_tags: New
        tags to display     existing_tags: Existing tags to display
        """
        super().__init__(parent)
        self.filename = filename
        self.new_tags = new_tags
        self.existing_tags = existing_tags

        self.setWindowTitle("Save Options")
        self.setModal(True)
        self.setFixedSize(520, 380)

        self._setup_ui()
        logger.debug("WavSaveOptionsDialog initialized")

    def _setup_ui(self) -> None:
        """Setup the dialog user interface."""
        layout = QVBoxLayout(self)

        # Header information
        filename_display = os.path.basename(self.filename)
        layout.addWidget(QLabel(f"<b>File:</b> {filename_display}"))
        layout.addWidget(QLabel(f"<b>New tags:</b> {self.new_tags}"))

        if self.existing_tags:
            layout.addWidget(QLabel(f"<b>Existing tags:</b> {self.existing_tags}"))

        layout.addWidget(QLabel(""))  # Spacer
        layout.addWidget(QLabel("<b>How do you want to save?</b>"))

        # Save method options
        self.button_group = QButtonGroup()

        # Option 1: Edit copy (default, safest)
        self.edit_radio = QRadioButton("As copy with _edit suffix (safest)")
        self.edit_radio.setChecked(True)
        self.button_group.addButton(self.edit_radio, 1)
        layout.addWidget(self.edit_radio)

        # Option 2: In-place overwrite
        self.inplace_radio = QRadioButton("Overwrite original file (PERMANENT)")
        self.button_group.addButton(self.inplace_radio, 2)
        layout.addWidget(self.inplace_radio)

        # Option 3: Backup and replace
        self.backup_radio = QRadioButton("Create backup (.bak) then replace original")
        self.button_group.addButton(self.backup_radio, 3)
        layout.addWidget(self.backup_radio)

        # Option 4: Custom name
        custom_layout = QHBoxLayout()
        self.custom_radio = QRadioButton("Custom name:")
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("e.g., forest_recording_final")
        custom_layout.addWidget(self.custom_radio)
        custom_layout.addWidget(self.custom_input)
        self.button_group.addButton(self.custom_radio, 4)
        layout.addLayout(custom_layout)

        layout.addWidget(QLabel(""))  # Spacer

        # Tag handling options
        self.merge_tags_checkbox = QCheckBox("Add to existing tags (don't replace)")
        if self.existing_tags:
            self.merge_tags_checkbox.setChecked(True)
        layout.addWidget(self.merge_tags_checkbox)

        # Info and tips
        info_label = QLabel(
            "<i>💡 Tip: Backup option is safest for important files</i>"
        )
        layout.addWidget(info_label)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def get_save_method(self) -> int:
        """Get the chosen save method (1-4)."""
        return self.button_group.checkedId()

    def get_custom_name(self) -> str:
        """Get the custom filename if chosen."""
        return self.custom_input.text().strip()

    def should_merge_tags(self) -> bool:
        """Check if tags should be merged with existing."""
        return self.merge_tags_checkbox.isChecked()


# ===== CONVENIENCE FUNCTION FOR EASY INTEGRATION =====


# def quick_save_with_dialog(
#     parent,
#     filename: str,
#     metadata: dict[str, str],
#     new_tags: list[str] = None,
#     existing_tags: str = "",
#     user_config: dict[str, Any] = None,
# ) -> Optional["SaveResult"]:
#     """Quick save with dialog (convenience function).
#
#     Args:
#         parent: Parent widget
#         filename: WAV file path
#         metadata: Metadata to save
#         new_tags: List of new tags
#         existing_tags: Existing tags string
#         user_config: User configuration
#
#     Returns:
#         SaveResult if successful, None if cancelled/failed
#     """
#     manager = WavSaveManager(parent)
#     return manager.show_save_dialog_and_execute(
#         filename=filename,
#         metadata=metadata,
#         new_tags=new_tags or [],
#         existing_tags=existing_tags,
#         user_config=user_config,
#     )


# ===== TESTING HELPER =====


def test_wav_save_manager():
    """Test function for WavSaveManager."""
    logger.debug("Testing WavSaveManager...")
    logger.info("WavSaveManager class loaded")
    logger.info("WavSaveOptionsDialog class loaded")
    logger.info("Convenience functions available")
    logger.info("Ready for integration into WavViewer")


if __name__ == "__main__":
    test_wav_save_manager()
