"""User configuration dialog for field recording applications.

This module provides a modal configuration dialog for managing WAV metadata tags and
directory paths. The dialog allows users to set default values for WAV file metadata
fields and configure working directories.

The configuration is stored in a JSON file and loaded automatically when the application
starts.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import app_config
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

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

# CONFIG_FILE = "user_config.json"

FIELD_DESCRIPTIONS = {
    "INAM": "Title of the recording",
    "IART": "Artist or creator",
    "ICRD": "Creation date (YYYY-MM-DD)",
    "ISFT": "Software used",
    "IENG": "Engineer name",
    "ICMT": "Additional comments",
}

DEFAULT_WAV_TAGS = {
    "INAM": "Untitled Recording",
    "IART": "Unknown Artist",
    "ICRD": "",
    "ISFT": "FieldRecording",
    "IENG": "",
    "ICMT": "",
}

DEFAULT_PATHS = {
    "fieldrecording_dir": "FieldRecordings",
    "ableton_export_dir": "Ableton",
}


class TagEditor(QDialog):
    """Modal user configuration dialog for WAV metadata and paths.

    This dialog provides a user interface for configuring default WAV
    metadata tags and setting up working directory paths. The configuration
    is automatically saved to a JSON file when the user clicks "Save & Close".

    The dialog includes:
    - WAV metadata tag fields with descriptions
    - Directory path selection with browse buttons
    - Professional OK/Cancel button layout
    - Automatic configuration loading and saving

    Usage:
        config_dialog = TagEditor(parent_window)
        if config_dialog.exec_() == QDialog.Accepted:
            # Configuration was saved
            updated_config = config_dialog.get_updated_config()
    """

    def __init__(self, parent=None):
        """Initialize the configuration dialog.

        Args:     parent: Parent widget for the dialog. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("User Config Editor")
        self.setModal(True)
        self.setMinimumWidth(500)

        # Load configuration
        # self.user_config = self.load_config()
        self.config_file = app_config.USER_CONFIG

        self.user_config = load_user_config()

        # Setup UI components
        self.layout = QVBoxLayout(self)
        self.inputs = {}
        self.path_edits = {}

        # Track if config was saved
        self.config_saved = False

        # Build the interface
        self._setup_wav_tags_section()
        self._setup_paths_section()
        self._setup_dialog_buttons()

        # print("🧪 Testing focus fix in user_config_manager...")
        #
        # # Todo Fix alle widgets die nu bestaan zorg dat labels niet in tab meegaan
        # for child in self.findChildren(object):
        #     if hasattr(child, "setFocusPolicy"):
        #         child.setFocusPolicy(Qt.StrongFocus)
        #         print(f"Fixed focus for: {child.__class__.__name__}")

    def _setup_wav_tags_section(self):
        """Set up the WAV metadata tags section of the dialog."""
        self.layout.addWidget(QLabel("<b>WAV Metadata Tags</b>"))

        for tag, description in FIELD_DESCRIPTIONS.items():
            hlayout = QHBoxLayout()
            label = QLabel(f"{tag}:")
            edit = QLineEdit(self.user_config["wav_tags"].get(tag, ""))
            edit.setPlaceholderText(description)
            hlayout.addWidget(label)
            hlayout.addWidget(edit)
            self.inputs[tag] = edit
            self.layout.addLayout(hlayout)

    def _setup_paths_section(self):
        """Set up the directory paths section of the dialog."""
        self.layout.addWidget(QLabel("<b>Paths</b>"))

        for path_key in DEFAULT_PATHS:
            hlayout = QHBoxLayout()
            label = QLabel(path_key.replace("_", " ").capitalize() + ":")
            edit = QLineEdit(self.user_config["paths"].get(path_key, ""))
            browse = QPushButton("Browse")
            browse.clicked.connect(lambda _, key=path_key: self.browse_path(key))
            hlayout.addWidget(label)
            hlayout.addWidget(edit)
            hlayout.addWidget(browse)
            self.path_edits[path_key] = edit
            self.layout.addLayout(hlayout)

    def _setup_dialog_buttons(self):
        """Set up the dialog's OK/Cancel button layout."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to right

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        # Save & Close button
        self.save_button = QPushButton("Save & Close")
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)

        self.layout.addLayout(button_layout)

    def browse_path(self, key):
        """Open directory browser for path selection.

        Args:     key: The path configuration key to update.
        """
        path = QFileDialog.getExistingDirectory(self, f"Select folder for {key}")
        if path:
            self.path_edits[key].setText(path)

    def save_config(self):
        """Save current configuration to JSON file.

        Returns:     bool: True if save successful, False otherwise.
        """
        # Update WAV tags from input fields
        for key, edit in self.inputs.items():
            self.user_config["wav_tags"][key] = edit.text().strip()

        # Update paths from input fields
        for key, edit in self.path_edits.items():
            path_value = edit.text().strip()
            self.user_config["paths"][key] = path_value or DEFAULT_PATHS[key]

        try:
            # with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            with open(
                self.config_file, "w", encoding="utf-8"
            ) as f:  # ✅ Use instance variable
                json.dump(self.user_config, f, indent=4)
            self.config_saved = True
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save config: {e}")
            return False

    def save_and_close(self):
        """Save configuration and close dialog with success message."""
        if self.save_config():
            QMessageBox.information(
                self, "Success", "Configuration saved successfully."
            )
            self.accept()  # Close with "OK" result

    def was_config_saved(self):
        """Check if configuration was successfully saved.

        Returns:     bool: True if config was saved, False otherwise.
        """
        return self.config_saved

    def get_updated_config(self):
        """Get the current configuration dictionary.

        Returns:     dict: Current configuration with all updates.
        """
        return self.user_config


def load_user_config(config_file: str = None) -> dict[str, Any]:
    """Headless variant van TagEditor.load_config."""
    cfg: dict[str, Any] = {}

    if config_file is None:
        config_file = app_config.USER_CONFIG  # ✅ Gebruik central config

    if os.path.exists(config_file):
        try:
            with open(config_file, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}  # Fallback bij corrupte JSON

    cfg.setdefault("wav_tags", {})
    for k, v in DEFAULT_WAV_TAGS.items():
        cfg["wav_tags"].setdefault(k, v)

    cfg.setdefault("paths", {})
    for k, v in DEFAULT_PATHS.items():
        raw = cfg["paths"].get(k, "") or v
        cfg["paths"][k] = str(Path(raw).expanduser().resolve())

    return cfg


def main():
    """Main function for standalone testing of the TagEditor dialog."""
    app = QApplication(sys.argv)
    editor = TagEditor()

    # Show as modal dialog
    result = editor.exec_()

    if result == QDialog.Accepted:
        print("✅ Configuration saved")
    else:
        print("❌ Configuration cancelled")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
