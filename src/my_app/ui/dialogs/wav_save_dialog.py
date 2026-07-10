"""Save options dialog for WAV metadata/tag save operations.

Pure UI: collects the user's save choices (save method, custom filename,
tag-merge preference) and returns them via getter methods. Contains no
save orchestration or file I/O — that lives in wav_save_manager.py.
"""

import os

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


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
        gps_info: str = "",
    ):
        """Initialize the save options dialog.

        Args:     parent: Parent widget     filename: Current filename     new_tags: New
        tags to display     existing_tags: Existing tags to display
        """
        super().__init__(parent)
        self.filename = filename
        self.new_tags = new_tags
        self.existing_tags = existing_tags
        self.gps_info = gps_info

        self.setWindowTitle("Save Options")
        self.setModal(True)
        self.setFixedSize(520, 300)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the dialog user interface."""
        layout = QVBoxLayout(self)

        # Header information (hidden for now — re-enable if needed)
        filename_display = os.path.basename(self.filename)
        # layout.addWidget(QLabel(f"<b>File:</b> {filename_display}"))
        # layout.addWidget(QLabel(f"<b>New tags:</b> {self.new_tags}"))
        # if self.gps_info:
        #     layout.addWidget(QLabel(f"<b>GPS:</b> {self.gps_info}"))
        # if self.existing_tags:
        #     layout.addWidget(QLabel(f"<b>Existing tags:</b> {self.existing_tags}"))

        layout.addWidget(QLabel(f"<b>{filename_display}</b>"))
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
