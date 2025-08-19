"""Intelligent Tag Autocomplete Widget for Field Recording Applications.

This module provides a sophisticated tagging interface with category-based
autocomplete functionality. It's designed specifically for field recording
workflows where precise metadata tagging is essential for organization.

Key Features:
- Category-based tag filtering and suggestions
- Intelligent autocomplete with partial matching
- Real-time tag validation and duplicate prevention
- Keyboard navigation support
- Clean, user-friendly interface with emoji categorization

The widget supports comma-separated tag entry with smart completion,
allowing users to quickly and accurately tag their field recordings
with consistent terminology.

Basic usage in a PyQt5 application:
    app = QApplication([])
    tagger = FileTagAutocomplete()
    tagger.show()

Getting current tags:
    tagger = FileTagAutocomplete()
    tags = tagger.get_current_tags()
    print(f"Current tags: {tags}")
"""

import json
import logging
import os
import sys
from typing import Any

import app_config
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from tag_definitions import tag_categories

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


class FileTagAutocomplete(QWidget):
    """Intelligent autocomplete widget for field recording tag management.

    Provides a complete tagging interface with category filtering, intelligent
    suggestions, keyboard navigation, and template shortcuts.

    Keyboard Shortcuts: - Ctrl+1: Apply first template - Ctrl+2: Apply second template -
    Ctrl+3: Apply third template - Ctrl+4: Apply fourth template - F9: Open template
    manager
    """

    def __init__(self) -> None:
        """Initialize the autocomplete widget with sorted categories."""
        super().__init__()
        logger.info("Initializing FileTagAutocomplete widget")

        # Sort categories alphabetically by text (excluding emoji)
        self.tag_categories: dict[str, list[str]] = {}

        def sort_key(category: str) -> str:
            """Extract sortable text from category name."""
            if " " in category:
                return " ".join(category.split(" ")[1:])  # Skip emoji part
            return category

        logger.debug(
            f"Loading {len(tag_categories)} categories from " "tag_definitions"
        )
        for category in sorted(tag_categories.keys(), key=sort_key):
            self.tag_categories[category] = sorted(tag_categories[category])
            logger.debug(
                f"Category '{category}': " f"{len(tag_categories[category])} tags"
            )

        # Create flat list of all tags (now sorted)
        self.all_tags: list[str] = []
        for _category, tags in self.tag_categories.items():
            self.all_tags.extend(tags)

        logger.info(
            f"Loaded total of {len(self.all_tags)} tags across "
            f"{len(self.tag_categories)} categories"
        )

        # Initialize UI
        self._init_ui()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        logger.info("UI initialization completed with shortcuts")

    def _init_ui(self) -> None:
        """Initialize the user interface components."""
        logger.debug("Setting up UI components")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Category filter section
        category_layout = QHBoxLayout()
        category_label = QLabel("Category filter:")

        self.category_combo = QComboBox()
        self.category_combo.addItem("All categories")
        for category in self.tag_categories.keys():
            self.category_combo.addItem(category)
        self.category_combo.currentTextChanged.connect(self._handle_category_change)
        logger.debug(
            f"Category combo populated with " f"{self.category_combo.count()} items"
        )

        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        category_layout.addStretch()
        layout.addLayout(category_layout)

        # Template quick buttons
        self.template_buttons = TemplateQuickButtons(self)
        layout.addWidget(self.template_buttons)

        # Tag input field
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Type tags for your recording...")
        self.tag_input.textChanged.connect(self._handle_text_change)
        # self.tag_input.keyPressEvent = self._handle_input_keypress
        layout.addWidget(self.tag_input)
        logger.debug("Tag input field created")

        # Tag suggestions list
        self.suggestions_widget = QListWidget()
        self.suggestions_widget.itemClicked.connect(self._handle_tag_click)
        # self.suggestions_widget.keyPressEvent = (self._handle_suggestions_keypress)
        self.suggestions_widget.show()
        layout.addWidget(self.suggestions_widget)
        logger.debug("Suggestions widget created")

        # Current tags display
        self.tags_display = QLabel("Current tags: ")
        layout.addWidget(self.tags_display)

        self.setLayout(layout)

        # Show all tags on startup
        self._show_all_available_tags()
        logger.info("UI initialization completed")

    def _setup_shortcuts(self):
        """Setup template keyboard shortcuts."""
        """
        parent_window = self.window()
        if not parent_window:
            return

        # Template shortcuts Ctrl+1 to Ctrl+4
        self.template_shortcuts = []
        for i in range(1, 5):  # 1, 2, 3, 4
            key_combo = f'Ctrl+{i}'
            shortcut = QShortcut(QKeySequence(key_combo), parent_window)

            # Use proper lambda with default parameter
            shortcut.activated.connect(
                lambda checked=False, idx=i - 1:
                self.apply_template_by_index(idx)
            )

            self.template_shortcuts.append(shortcut)

        # Template Manager shortcut
        self.f9_shortcut = QShortcut(QKeySequence('F9'), parent_window)
        self.f9_shortcut.activated.connect(self.open_template_manager)
        """

    def apply_template_by_index(self, template_index):
        """Apply template by index (0-based)."""
        if not hasattr(self, "template_buttons") or not self.template_buttons:
            return

        # Get available templates
        templates = list(self.template_buttons.template_manager.templates.keys())

        if template_index >= len(templates):
            return

        if not templates:
            return

        # Apply the template
        template_name = templates[template_index]
        template_data = self.template_buttons.template_manager.get_template(
            template_name
        )

        if template_data:
            self.template_buttons.apply_template(template_data, template_name)
        else:
            print(f"Template data not found for: {template_name}")

    def open_template_manager(self):
        """Open template manager via F9."""
        if hasattr(self, "template_buttons") and self.template_buttons:
            self.template_buttons.show_template_manager()
        else:
            print("Template buttons not available")

    def _handle_category_change(self, category: str) -> None:
        """Handle category filter selection changes."""
        logger.debug(f"Category filter changed to: '{category}'")
        filtered_tags = self._get_filtered_tags_by_category()
        logger.debug(
            f"Filtered to {len(filtered_tags)} tags for " f"category '{category}'"
        )
        self._handle_text_change(self.tag_input.text())

    def _get_filtered_tags_by_category(self) -> list[str]:
        """Get tags filtered by currently selected category."""
        selected_category = self.category_combo.currentText()

        if selected_category == "All categories":
            return self.all_tags
        else:
            return self.tag_categories.get(selected_category, [])

    def _handle_input_keypress(self, event) -> None:
        """Handle keyboard input in the tag input field."""
        key_name = event.key()
        logger.debug(f"Key pressed in input field: {key_name}")

        if event.key() == Qt.Key_Down:
            if (
                self.suggestions_widget.isVisible()
                and self.suggestions_widget.count() > 0
            ):
                logger.debug("Moving focus to suggestions list (down arrow)")
                self.suggestions_widget.setFocus()
                self.suggestions_widget.setCurrentRow(0)
                return
        elif event.key() == Qt.Key_Up:
            if (
                self.suggestions_widget.isVisible()
                and self.suggestions_widget.count() > 0
            ):
                logger.debug("Moving focus to suggestions list (up arrow)")
                self.suggestions_widget.setFocus()
                self.suggestions_widget.setCurrentRow(
                    self.suggestions_widget.count() - 1
                )
                return
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if (
                self.suggestions_widget.isVisible()
                and self.suggestions_widget.count() > 0
            ):
                first_item = self.suggestions_widget.item(0)
                tag_text = first_item.text()
                logger.debug(
                    f"Enter pressed - selecting first suggestion: " f"'{tag_text}'"
                )
                # Parse tag name from display text
                if " · " in tag_text:
                    parts = tag_text.split(" · ")[0]  # "🌲 forest"
                    tag_text = " ".join(parts.split(" ")[1:])  # "forest"
                    logger.debug(f"Parsed tag from formatted display: " f"'{tag_text}'")
                self._apply_tag_selection(tag_text)
                return

        QLineEdit.keyPressEvent(self.tag_input, event)

    def _handle_suggestions_keypress(self, event) -> None:
        """Handle keyboard input in the suggestions list."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current_item = self.suggestions_widget.currentItem()
            if current_item:
                tag_text = current_item.text()
                # Parse tag name from display text
                if " · " in tag_text:
                    parts = tag_text.split(" · ")[0]  # "🌲 forest"
                    tag_text = " ".join(parts.split(" ")[1:])  # "forest"
                self._apply_tag_selection(tag_text)
                return
        elif event.key() == Qt.Key_Escape:
            self.tag_input.setFocus()
            return

        QListWidget.keyPressEvent(self.suggestions_widget, event)

    def _show_all_available_tags(self) -> None:
        """Display all available tags filtered by category and unused tags."""
        used_tags = self._get_used_tags()
        available_tags = self._get_filtered_tags_by_category()
        logger.debug(
            f"Showing all available tags. Used: {len(used_tags)}, "
            f"Available: {len(available_tags)}"
        )

        # Filter out only used tags
        filtered_tags = []
        for tag in available_tags:
            if tag not in used_tags:
                # Find category for this tag
                tag_category = None
                category_emoji = ""

                for category, tags in self.tag_categories.items():
                    if tag in tags:
                        tag_category = category
                        # Extract emoji from category name
                        if " " in category:
                            category_emoji = category.split(" ")[0]
                            category_name = " ".join(category.split(" ")[1:])
                        else:
                            category_emoji = ""
                            category_name = category
                        break

                # Format: emoji first, then tag, then category
                if (
                    tag_category
                    and self.category_combo.currentText() == "All categories"
                ):
                    filtered_tags.append(f"{category_emoji} {tag} · {category_name}")
                else:
                    filtered_tags.append(tag)

        logger.debug(f"Filtered to {len(filtered_tags)} unused tags")
        self.suggestions_widget.clear()
        for tag in filtered_tags:
            item = QListWidgetItem(tag)
            self.suggestions_widget.addItem(item)

        logger.debug(
            f"Updated suggestions widget with "
            f"{self.suggestions_widget.count()} items"
        )

    def _handle_text_change(self, text: str) -> None:
        """Handle changes in the tag input text."""
        current_word = self._extract_current_word()
        logger.debug(f"Text changed: '{text}' -> current word: '{current_word}'")

        if not current_word:
            logger.debug("No current word - showing all available tags")
            self._show_all_available_tags()
            return

        used_tags = self._get_used_tags()
        available_tags = self._get_filtered_tags_by_category()
        logger.debug(
            f"Used tags: {list(used_tags)}, available: {len(available_tags)} tags"
        )

        # Filter suggestions
        exact_matches = []
        partial_matches = []

        for tag in available_tags:
            if tag not in used_tags:
                display_tag = self._format_tag_for_display(tag)
                self._add_tag_to_matches(
                    tag, current_word, display_tag, exact_matches, partial_matches
                )

        # Combine and display results
        self._update_suggestions_display(exact_matches, partial_matches)

    def _format_tag_for_display(self, tag: str) -> str:
        """Format tag for display with category info if needed."""
        # Find category for this tag
        for category, tags in self.tag_categories.items():
            if tag in tags:
                # Only show category info when "All categories" is selected
                if self.category_combo.currentText() == "All categories":
                    category_emoji = category.split(" ")[0] if " " in category else ""
                    category_name = (
                        " ".join(category.split(" ")[1:])
                        if " " in category
                        else category
                    )
                    return f"{category_emoji} {tag} · {category_name}"
                break

        return tag

    def _add_tag_to_matches(
        self,
        tag: str,
        current_word: str,
        display_tag: str,
        exact_matches: list,
        partial_matches: list,
    ) -> None:
        """Add tag to appropriate match list based on match type."""
        current_lower = current_word.lower()
        tag_lower = tag.lower()

        if current_lower == tag_lower:
            exact_matches.append(display_tag)
            logger.debug(f"Exact match found: '{tag}' -> '{display_tag}'")
        elif current_lower in tag_lower:
            partial_matches.append(display_tag)

    def _update_suggestions_display(
        self, exact_matches: list, partial_matches: list
    ) -> None:
        """Update the suggestions widget with filtered matches."""
        filtered_tags = exact_matches + partial_matches
        logger.debug(
            f"Found {len(exact_matches)} exact matches, {len(partial_matches)} partial matches"
        )

        self.suggestions_widget.clear()
        for tag in filtered_tags:
            item = QListWidgetItem(tag)
            # Apply special formatting for tags with category info
            if " · " in tag:
                font = item.font()
                font.setPointSize(font.pointSize() - 1)
                item.setFont(font)
            self.suggestions_widget.addItem(item)

        logger.debug(f"Updated suggestions list with {len(filtered_tags)} items")

    def _extract_current_word(self) -> str:
        """Extract the current word being worked on."""
        text = self.tag_input.text()
        cursor_pos = self.tag_input.cursorPosition()

        text_before_cursor = text[:cursor_pos]
        parts = text_before_cursor.split(",")
        current_part = parts[-1].strip()

        return current_part

    def _get_used_tags(self) -> set[str]:
        """Get all already used tags (completed with comma)."""
        text = self.tag_input.text()
        if not text.strip():
            return set()

        # Split on commas and take only parts that are not the last part
        # (unless the last part ends with a comma)
        parts = text.split(",")

        # If text ends with comma, all parts are completed
        if text.endswith(","):
            return {part.strip() for part in parts if part.strip()}
        # The last part is not completed, so skip it
        elif len(parts) > 1:
            return {part.strip() for part in parts[:-1] if part.strip()}
        else:
            return set()  # Only one incomplete word

    def _handle_tag_click(self, item: QListWidgetItem) -> None:
        """Handle clicking on a suggestion item."""
        tag_text = item.text()
        # Extract real tag name from formatted display
        if " · " in tag_text:
            # Format: "🌲 forest · Nature Locations" -> extract "forest"
            parts = tag_text.split(" · ")[0]  # "🌲 forest"
            tag_text = " ".join(parts.split(" ")[1:])  # "forest" (skip emoji)

        self._apply_tag_selection(tag_text)

    def _apply_tag_selection(self, selected_tag: str) -> None:
        """Apply the selected tag to the input field."""
        logger.info(f"Applying tag selection: '{selected_tag}'")
        text = self.tag_input.text()
        cursor_pos = self.tag_input.cursorPosition()
        logger.debug(f"Current text: '{text}', cursor at position " f"{cursor_pos}")

        text_before_cursor = text[:cursor_pos]
        text_after_cursor = text[cursor_pos:]

        last_comma_pos = text_before_cursor.rfind(",")
        if last_comma_pos == -1:

            word_before = ""
        else:

            word_before = text_before_cursor[: last_comma_pos + 1]

        next_comma_pos = text_after_cursor.find(",")
        if next_comma_pos == -1:

            word_after = ""
        else:

            word_after = text_after_cursor[next_comma_pos:]

        # Ensure proper spacing
        if word_before and not word_before.endswith(" "):
            word_before += " "

        new_text = word_before + selected_tag + ", " + word_after
        logger.debug(f"New text will be: '{new_text}'")

        self.tag_input.setText(new_text)
        new_cursor_pos = len(word_before + selected_tag + ", ")
        self.tag_input.setCursorPosition(new_cursor_pos)
        logger.debug(f"Cursor moved to position {new_cursor_pos}")

        self._show_all_available_tags()
        self.tag_input.setFocus()
        self._refresh_tags_display()

        # Log current tag state
        current_tags = self.get_current_tags()
        logger.info(f"Tag successfully applied. Current tags: {current_tags}")

    def _refresh_tags_display(self) -> None:
        """Update the current tags display label."""
        text = self.tag_input.text()
        if text.strip():
            parts = [part.strip() for part in text.split(",") if part.strip()]
            if parts:
                # Show max. 5 tags, rest abbreviated
                display_tags = parts[:5]
                remaining = len(parts) - len(display_tags)

                if remaining > 0:
                    tag_text = (
                        f"Current tags: {', '.join(display_tags)} " f"+{remaining} more"
                    )
                else:
                    tag_text = f"Current tags: {', '.join(display_tags)}"

                self.tags_display.setText(tag_text)

                # Tooltip with all tags
                self.tags_display.setToolTip(f"All tags:\n{', '.join(parts)}")
            else:
                self.tags_display.setText("Current tags:")
                self.tags_display.setToolTip("")
        else:
            self.tags_display.setText("Current tags:")
            self.tags_display.setToolTip("")

    def get_current_tags(self) -> list[str]:
        """Get current tags as a list."""
        text = self.tag_input.text()
        if not text.strip():
            return []
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return parts

    def set_tags(self, tags: list[str]) -> None:
        """Set tags programmatically with trailing comma."""
        logger.info(f"Setting tags programmatically: {tags}")

        if not tags:
            self.tag_input.setText("")
            logger.debug("Tag input cleared (empty tags list)")
        else:
            # Filter empty strings and whitespace
            clean_tags = [tag.strip() for tag in tags if tag.strip()]

            if clean_tags:
                # Add trailing comma for easy extension
                tag_string = ", ".join(clean_tags) + ", "

                self.tag_input.setText(tag_string)

                # Place cursor at the end
                self.tag_input.setFocus()
                self.tag_input.setCursorPosition(len(tag_string))

                logger.debug(
                    f"Tag input set to: '{tag_string}' " "(with trailing comma)"
                )
            else:
                self.tag_input.setText("")
                logger.debug("No valid tags after cleaning")

        # Update display and suggestions
        self._refresh_tags_display()
        self._show_all_available_tags()

    def clear_tags(self) -> None:
        """Clear all current tags."""
        logger.info("Clearing all tags")
        self.tag_input.setText("")
        self._refresh_tags_display()
        self._show_all_available_tags()
        logger.debug("All tags cleared successfully")


class FieldRecorderTagger(QWidget):
    """Main application window for the field recorder tagger."""

    def __init__(self) -> None:
        """Initialize the main tagger application window."""
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the user interface for the main window."""
        self.setWindowTitle("Field Recorder File Tagger v1")

        # Create the file tagger widget
        self.tagger_widget = FileTagAutocomplete()

        # Layout setup
        layout = QVBoxLayout()

        # Title section
        title = QLabel("Field Recorder File Tagger v1")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Info section
        info = QLabel(
            "Tag your recordings for easy organization and retrieval\n"
            "Ctrl+1=First Template, Ctrl+2=Second Template, F9=Template Manager"
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        # Add the tagger widget
        layout.addWidget(self.tagger_widget)

        self.setLayout(layout)


class TemplateManager:
    """Central template management class."""

    # def __init__(self, template_file="tag_templates.json"):
    def __init__(self):
        """Initialize template manager with file path."""
        # self.template_file = template_file
        self.template_file = app_config.TEMPLATE_CONFIG  # ✅

        self.templates = self.load_templates()

    def get_default_templates(self) -> dict[str, Any]:
        """Get default templates based on existing tag definitions."""
        return {
            "🌲 Forest Morning": {
                "tags": ["forest", "bird", "wind", "morning", "silence", "clear"],
                "description": "Early morning in the forest with birdsong",
                "usage_count": 0,
            },
            "🏙️ Busy Street": {
                "tags": ["street", "traffic", "voices", "busy", "city", "close"],
                "description": "Busy urban street with traffic",
                "usage_count": 0,
            },
            "🌧️ Rain Shower": {
                "tags": ["rain", "wind", "storm", "water", "ambient", "distant"],
                "description": "Rain shower and wind sounds",
                "usage_count": 0,
            },
            "🦅 Bird Concert": {
                "tags": ["bird", "woodpecker", "song", "nature", "morning", "clear"],
                "description": "Rich birdsong in natural environment",
                "usage_count": 0,
            },
            "🌊 Seashore": {
                "tags": ["sea", "beach", "waves", "wind", "ambient", "distant"],
                "description": "Peaceful coastal sounds",
                "usage_count": 0,
            },
            "🐄 Farm": {
                "tags": ["cow", "horse", "dog", "field", "close", "clear"],
                "description": "Lively farm sounds",
                "usage_count": 0,
            },
            "🌙 Silent Night": {
                "tags": ["night", "silence", "owl", "distant", "ambient", "quiet"],
                "description": "Peaceful nighttime atmosphere",
                "usage_count": 0,
            },
            "🦗 Summer Insects": {
                "tags": ["cricket", "bee", "fly", "summer", "close", "clear"],
                "description": "Lively summer insect sounds",
                "usage_count": 0,
            },
        }

    def load_templates(self) -> dict[str, Any]:
        """Load templates from file, with fallback to defaults."""
        try:
            if os.path.exists(self.template_file):
                with open(self.template_file, encoding="utf-8") as f:
                    loaded = json.load(f)
                    # print(f"Loaded {len(loaded)} templates from "
                    #       f"{self.template_file}")
                    return loaded
        except Exception as e:
            print(f"Error loading templates: {e}")

        # Fallback to defaults
        defaults = self.get_default_templates()
        self.save_templates(defaults)
        print(f"Created default templates ({len(defaults)} templates)")
        return defaults

    def save_templates(self, templates=None):
        """Save templates to file."""
        if templates is None:
            templates = self.templates

        try:
            with open(self.template_file, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)
            print(f"Templates saved to {self.template_file}")
        except Exception as e:
            print(f"Error saving templates: {e}")

    def get_template(self, name: str) -> dict[str, Any]:
        """Get specific template by name."""
        return self.templates.get(name, {})

    def add_template(self, name: str, tags: list[str], description: str = ""):
        """Add new template."""
        self.templates[name] = {
            "tags": tags,
            "description": description,
            "usage_count": 0,
        }
        self.save_templates()
        print(f"Template added: {name}")

    def update_template(self, name: str, tags: list[str], description: str = ""):
        """Update existing template."""
        if name in self.templates:
            self.templates[name]["tags"] = tags
            self.templates[name]["description"] = description
            self.save_templates()
            print(f"Template updated: {name}")

    def delete_template(self, name: str):
        """Delete template."""
        if name in self.templates:
            del self.templates[name]
            self.save_templates()
            print(f"Template deleted: {name}")

    def increment_usage(self, name: str):
        """Increment usage count for template."""
        if name in self.templates:
            self.templates[name]["usage_count"] = (
                self.templates[name].get("usage_count", 0) + 1
            )
            self.save_templates()

    def get_popular_templates(self, limit: int = 4) -> list[str]:
        """Get most used templates."""
        sorted_templates = sorted(
            self.templates.items(),
            key=lambda x: x[1].get("usage_count", 0),
            reverse=True,
        )
        return [name for name, _ in sorted_templates[:limit]]


class TemplateQuickButtons(QWidget):
    """Quick template apply buttons."""

    def __init__(self, parent_tagger):
        """Initialize template quick buttons."""
        super().__init__()
        self.parent_tagger = parent_tagger
        self.template_manager = TemplateManager()
        self.buttons_layout = None  # Store reference
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Label
        label = QLabel("Quick Templates:")
        label.setStyleSheet("font-weight: bold; color: #666; font-size: 10pt;")
        layout.addWidget(label)

        # Buttons layout
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(2)

        # Create initial buttons
        self._create_template_buttons()

        layout.addLayout(self.buttons_layout)

    def _create_template_buttons(self):
        """Create template buttons with correct keyboard shortcut tooltips."""
        # Clear existing buttons
        while self.buttons_layout.count():
            child = self.buttons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get templates
        if hasattr(self.template_manager, "get_recent_templates"):
            templates = self.template_manager.get_recent_templates(4)
        else:
            templates = self.template_manager.get_popular_templates(4)

        # Shortcut keys mapping (corrected to match actual shortcuts)
        shortcut_keys = ["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"]

        # Create buttons for templates
        for i, name in enumerate(templates):
            template_data = self.template_manager.get_template(name)
            if template_data:
                btn = QPushButton(name)
                btn.setMaximumHeight(28)
                btn.setStyleSheet(
                    """QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4a4a, stop:1 #3a3a3a); border: 1px solid #666666; border-
                    radius: 6px; padding: 6px 12px; font-size: 9pt; color: #ffffff; }
                    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0,
                    y2:1, stop:0 #5a5a5a, stop:1 #4a4a4a); border-color: #888888; }
                    QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0,
                    y2:1, stop:0 #2a2a2a, stop:1 #1a1a1a); }
                    """
                )

                # Connect button click
                btn.clicked.connect(
                    lambda checked, data=template_data, n=name: self.apply_template(
                        data, n
                    )
                )

                # Enhanced tooltip with correct shortcut
                tags_preview = ", ".join(template_data["tags"][:5])
                if len(template_data["tags"]) > 5:
                    tags_preview += f" (+{len(template_data['tags']) - 5} more)"

                # Use correct Ctrl+1-4 shortcuts
                shortcut_hint = (
                    f" ({shortcut_keys[i]})" if i < len(shortcut_keys) else ""
                )
                tooltip_text = (
                    f"Tags: {tags_preview}\n"
                    f"Used: {template_data.get('usage_count', 0)} "
                    f"times{shortcut_hint}"
                )
                btn.setToolTip(tooltip_text)

                self.buttons_layout.addWidget(btn)

        # More/Manage button
        more_btn = QPushButton("⚙️")
        more_btn.setMaximumWidth(35)
        more_btn.setMaximumHeight(28)
        more_btn.setToolTip("Template Manager (F9)")
        more_btn.setStyleSheet(
            """QPushButton { background-color: #e8f4fd; border: 1px solid #bee5eb;
            border-radius: 4px; font-weight: bold; } QPushButton:hover { background-
            color: #d1ecf1; }
            """
        )
        more_btn.clicked.connect(self.show_template_manager)
        self.buttons_layout.addWidget(more_btn)

        self.buttons_layout.addStretch()

    def show_template_manager(self):
        """Show template manager dialog."""
        dialog = TemplateManagerDialog(self, self.template_manager)
        if dialog.exec_() == dialog.Accepted:
            # Refresh buttons if templates were modified
            self._create_template_buttons()

    def apply_template(self, template_data, template_name):
        """Apply template tags to tagger with trailing comma."""
        tags = template_data.get("tags", [])

        # Add trailing comma
        tags_with_comma = tags.copy()
        if tags_with_comma:
            tags_with_comma.append("")  # Empty string creates trailing comma

        self.parent_tagger.set_tags(tags_with_comma)

        # Increment usage count
        self.template_manager.increment_usage(template_name)

        print(f"Template '{template_name}' applied: {tags} " "(with trailing comma)")

        # Safe refresh - recreate buttons to show new popularity order
        self._create_template_buttons()


class TemplateManagerDialog(QDialog):
    """Complete template manager dialog."""

    def __init__(self, parent=None, template_manager=None):
        """Initialize template manager dialog."""
        super().__init__(parent)
        self.template_manager = template_manager or TemplateManager()
        self.setWindowTitle("Template Manager")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self.current_template_name = None
        self.setup_ui()
        self.refresh_template_list()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(self._create_header())

        # Main content with left and right panels
        main_layout = QHBoxLayout()
        main_layout.addLayout(self._create_left_panel(), stretch=1)
        main_layout.addLayout(self._create_right_panel(), stretch=1)
        layout.addLayout(main_layout)

        # Close button
        layout.addLayout(self._create_close_section())

    def _create_header(self):
        """Create and return header widget."""
        header = QLabel("<h2>🎯 Template Manager</h2>")
        header.setAlignment(Qt.AlignCenter)
        return header

    def _create_left_panel(self):
        """Create and return left panel layout."""
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>📂 Available Templates:</b>"))

        self.template_list = QListWidget()
        self.template_list.itemClicked.connect(self.load_template_for_editing)
        self.template_list.itemDoubleClicked.connect(self.apply_selected_template)
        left_layout.addWidget(self.template_list)

        self.stats_label = QLabel("Loading statistics...")
        self.stats_label.setStyleSheet("color: #666; font-size: 9pt;")
        left_layout.addWidget(self.stats_label)

        return left_layout

    def _create_right_panel(self):
        """Create and return right panel layout."""
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("<b>✏️ Edit Template:</b>"))

        # Form inputs
        self._add_form_inputs(right_layout)

        # Button sections
        right_layout.addLayout(self._create_action_buttons())
        right_layout.addLayout(self._create_import_export_buttons())
        right_layout.addStretch()

        return right_layout

    def _add_form_inputs(self, layout):
        """Add form input fields to layout."""
        # Template name
        layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("🏷️ Template name...")
        layout.addWidget(self.name_input)

        # Template tags
        layout.addWidget(QLabel("Tags:"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("🏷️ tags, separated, by, commas")
        layout.addWidget(self.tags_input)

        # Template description
        layout.addWidget(QLabel("Description:"))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "📝 Description of this template (optional)"
        )
        self.description_input.setMaximumHeight(60)
        layout.addWidget(self.description_input)

    def _create_action_buttons(self):
        """Create and return action buttons layout."""
        action_layout = QHBoxLayout()

        buttons = [
            ("💾 Save", self.save_template),
            ("➕ New", self.new_template),
            ("🗑️ Delete", self.delete_template),
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            action_layout.addWidget(btn)

            # Store save button reference
            if "Save" in text:
                self.save_btn = btn
            elif "New" in text:
                self.new_btn = btn
            elif "Delete" in text:
                self.delete_btn = btn

        return action_layout

    def _create_import_export_buttons(self):
        """Create and return import/export buttons layout."""
        io_layout = QHBoxLayout()

        buttons = [
            ("📥 Import", self.import_templates),
            ("📤 Export", self.export_templates),
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            io_layout.addWidget(btn)

        return io_layout

    def _create_close_section(self):
        """Create and return close button section."""
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        close_layout.addWidget(close_btn)

        return close_layout

    def refresh_template_list(self):
        """Refresh the template list display."""
        self.template_list.clear()

        total_usage = 0
        templates = list(self.template_manager.templates.items())

        # Sort by usage count (most used first)
        templates.sort(key=lambda x: x[1].get("usage_count", 0), reverse=True)

        for name, data in templates:
            tags = data.get("tags", [])
            usage_count = data.get("usage_count", 0)
            total_usage += usage_count
            description = data.get("description", "")

            # Create display text
            tags_preview = ", ".join(tags[:4])
            if len(tags) > 4:
                tags_preview += f" (+{len(tags) - 4})"

            display_text = f"{name}\n"
            display_text += f"   Tags: {tags_preview}\n"
            display_text += f"   Used: {usage_count}x"
            if description:
                display_text += (
                    f"\n   {description[:50]}"
                    f"{'...' if len(description) > 50 else ''}"
                )

            item = QListWidgetItem(display_text)

            # Color code by popularity
            if usage_count > 5:
                item.setBackground(QColor(200, 255, 200))  # Green for popular
            elif usage_count > 0:
                item.setBackground(QColor(255, 255, 200))  # Yellow for used

            self.template_list.addItem(item)

        # Update statistics
        total_templates = len(templates)
        used_templates = len([t for _, t in templates if t.get("usage_count", 0) > 0])
        self.stats_label.setText(
            f"📊 {total_templates} templates • {used_templates} used • "
            f"{total_usage} total usage"
        )

    def load_template_for_editing(self, item):
        """Load selected template into editor."""
        if not item:
            return

        # Extract template name from item text (first line)
        template_name = item.text().split("\n")[0]
        self.current_template_name = template_name

        template_data = self.template_manager.get_template(template_name)
        if template_data:
            self.name_input.setText(template_name)
            self.tags_input.setText(", ".join(template_data.get("tags", [])))
            self.description_input.setPlainText(template_data.get("description", ""))

            print(f"Loaded template for editing: {template_name}")

    def new_template(self):
        """Clear editor for new template."""
        self.current_template_name = None
        self.name_input.clear()
        self.tags_input.clear()
        self.description_input.clear()
        self.name_input.setFocus()
        print("Ready to create new template")

    def save_template(self):
        """Save current template."""
        name = self.name_input.text().strip()
        tags_text = self.tags_input.text().strip()
        description = self.description_input.toPlainText().strip()

        if not name:
            QMessageBox.warning(
                self, "No name", "Please provide a name for the template."
            )
            return

        if not tags_text:
            QMessageBox.warning(
                self, "No tags", "Please provide tags for the template."
            )
            return

        # Parse tags
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

        # Check if name changed (rename operation)
        if self.current_template_name and self.current_template_name != name:
            if name in self.template_manager.templates:
                reply = QMessageBox.question(
                    self,
                    "Template exists",
                    f"Template '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            # Delete old template
            self.template_manager.delete_template(self.current_template_name)

        # Save template
        if self.current_template_name:
            self.template_manager.update_template(name, tags, description)
        else:
            self.template_manager.add_template(name, tags, description)

        self.current_template_name = name
        self.refresh_template_list()

        QMessageBox.information(self, "Saved", f"Template '{name}' has been saved!")

    def delete_template(self):
        """Delete selected template."""
        if not self.current_template_name:
            QMessageBox.warning(
                self, "No selection", "Please select a template to delete first."
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete template",
            f"Are you sure you want to delete template "
            f"'{self.current_template_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.template_manager.delete_template(self.current_template_name)
            self.new_template()  # Clear editor
            self.refresh_template_list()
            QMessageBox.information(self, "Deleted", "Template has been deleted.")

    def import_templates(self):
        """Import templates from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Templates", "", "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, encoding="utf-8") as f:
                    imported_templates = json.load(f)

                imported_count = 0
                for name, data in imported_templates.items():
                    if name not in self.template_manager.templates:
                        self.template_manager.templates[name] = data
                        imported_count += 1

                if imported_count > 0:
                    self.template_manager.save_templates()
                    self.refresh_template_list()
                    QMessageBox.information(
                        self,
                        "Import completed",
                        f"{imported_count} new templates imported!",
                    )
                else:
                    QMessageBox.information(
                        self, "No new templates", "All templates already existed."
                    )

            except Exception as e:
                QMessageBox.critical(
                    self, "Import error", f"Error importing:\n{str(e)}"
                )

    def export_templates(self):
        """Export templates to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Templates",
            "tag_templates_export.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.template_manager.templates, f, indent=2, ensure_ascii=False
                    )

                QMessageBox.information(
                    self, "Export completed", f"Templates exported to:\n{file_path}"
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export error", f"Error exporting:\n{str(e)}"
                )

    def apply_selected_template(self):
        """Apply selected template to main tagger from manager."""
        if not self.current_template_name:
            QMessageBox.warning(self, "No selection", "Please select a template first.")
            return

        template_data = self.template_manager.get_template(self.current_template_name)
        if template_data:
            # Find the TemplateQuickButtons parent
            parent_widget = self.parent()
            if hasattr(parent_widget, "apply_template"):
                # Use existing apply_template function
                parent_widget.apply_template(template_data, self.current_template_name)
                print(
                    f"Template '{self.current_template_name}' applied " "via F9 manager"
                )
                self.accept()  # Close dialog
            else:
                print("Could not find parent apply_template function")


def main() -> None:
    """Main function for standalone application execution."""
    logger.info("Starting Field Recorder Tagger application")
    app = QApplication(sys.argv)
    window = FieldRecorderTagger()
    window.show()
    logger.info("Application window shown, entering event loop")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
