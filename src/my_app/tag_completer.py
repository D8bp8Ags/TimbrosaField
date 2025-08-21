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
    logger.debug(f"Current tags: {tags}")
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
    """Intelligent autocomplete widget for comprehensive field recording tag management.

    This widget provides a sophisticated tagging interface with real-time autocomplete,
    category-based filtering, keyboard navigation, and template shortcuts. It's designed
    specifically for field recording workflows where precise and consistent metadata
    tagging is essential for organization and retrieval.

    Key Features:
    - Real-time tag suggestions with partial matching
    - Category-based filtering for focused tag selection
    - Keyboard navigation with arrow keys and Enter
    - Template system for quick tag application
    - Duplicate prevention and tag validation
    - Clean, intuitive user interface with visual feedback

    Keyboard Shortcuts:
    - Ctrl+1-4: Apply template 1-4 respectively
    - F9: Open template manager dialog
    - Up/Down arrows: Navigate suggestions
    - Enter: Apply selected suggestion
    - Escape: Return focus to input field

    Attributes:
        tag_categories: Dictionary mapping category names to tag lists.
        all_tags: Flattened list of all available tags across categories.
        category_combo: Dropdown for category filtering.
        tag_input: Main text input field for tag entry.
        suggestions_widget: List widget displaying tag suggestions.
        tags_display: Label showing current tags summary.
        template_buttons: Quick template application buttons.
    """

    def __init__(self) -> None:
        """Initialize the FileTagAutocomplete widget with categories and UI setup.

        Loads tag categories from tag_definitions module, sorts them alphabetically
        (excluding emoji prefixes), creates a flattened tag list, and initializes
        the complete user interface including category filtering, input field,
        suggestions display, and template shortcuts.

        The initialization process:
        1. Loads and sorts tag categories by name (excluding emoji)
        2. Creates flattened list of all available tags
        3. Initializes UI components and layout
        4. Sets up keyboard shortcuts for template application
        5. Shows initial tag suggestions

        Note:
            Categories are sorted alphabetically by their text content, ignoring
            emoji prefixes for better usability. All tags within categories are
            also sorted alphabetically.
        """
        super().__init__()
        logger.info("Initializing FileTagAutocomplete widget")

        # Sort categories alphabetically by text (excluding emoji)
        self.tag_categories: dict[str, list[str]] = {}

        def sort_key(category: str) -> str:
            """Extract sortable text from category name for alphabetical sorting.

            Removes emoji prefixes from category names to enable proper alphabetical
            sorting based on the text content rather than Unicode emoji values.

            Args:
                category (str): Category name potentially prefixed with emoji.
                               Example: "🌲 Nature Locations"

            Returns:
                str: Text portion of category name for sorting.
                     Example: "Nature Locations"

            Note:
                If no space is found, returns the entire category name unchanged.
            """
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
        """Initialize and configure all user interface components.

        Creates the complete UI layout including category filter dropdown,
        template quick buttons, tag input field, suggestions list, and current
        tags display. All components are properly connected with event handlers
        and styled for optimal user experience.

        UI Components Created:
        - Category filter dropdown with "All categories" and individual categories
        - Template quick buttons widget for rapid template application
        - Tag input field with placeholder text and change detection
        - Suggestions list widget with click handling
        - Current tags display label with truncation for long lists

        Note:
            After UI setup, shows all available tags in the suggestions list
            to provide immediate feedback to the user.
        """
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
        """Configure keyboard shortcuts for template operations (currently disabled).

        This method contains the infrastructure for setting up keyboard shortcuts
        for template application (Ctrl+1-4) and template manager access (F9).
        Currently commented out to avoid conflicts with global shortcut management.

        Intended shortcuts:
        - Ctrl+1-4: Apply templates 1-4 respectively
        - F9: Open template manager dialog

        Note:
            This functionality is currently handled by the global shortcut manager
            in the main application to avoid duplicate shortcut registration and
            ensure consistent behavior across the application.
        """
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
        """Apply a template by its zero-based index in the template list.

        Retrieves the template at the specified index from the available templates
        and applies its tags to the current tag input field. This method is typically
        called by keyboard shortcuts (Ctrl+1-4) for quick template application.

        Args:
            template_index (int): Zero-based index of template to apply.
                                 Index 0 corresponds to Ctrl+1, index 1 to Ctrl+2, etc.

        Note:
            If the template index is out of range, no templates are available,
            or the template data is missing, the operation fails silently.
            Template application includes incrementing usage count for popularity tracking.
        """
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
            logger.error(f"Template data not found for: {template_name}")

    def open_template_manager(self):
        """Open the template manager dialog via F9 keyboard shortcut.

        Displays the comprehensive template manager dialog that allows users to
        create, edit, delete, import, and export tag templates. This provides
        advanced template management beyond the quick application buttons.

        Note:
            The template manager is accessed through the template_buttons widget.
            If template buttons are not available, the operation fails silently
            with a console message.
        """
        if hasattr(self, "template_buttons") and self.template_buttons:
            self.template_buttons.show_template_manager()
        else:
            logger.error("Template buttons not available")

    def _handle_category_change(self, category: str) -> None:
        """Handle changes in the category filter dropdown selection.

        Updates the tag suggestions display when the user selects a different
        category filter. Triggers a refresh of the suggestions list to show
        only tags from the selected category or all categories.

        Args:
            category (str): Selected category name from dropdown.
                           "All categories" shows all tags,
                           specific category names filter to that category only.

        Note:
            After filtering, the current input text is re-processed to update
            suggestions appropriately for the new category context.
        """
        logger.debug(f"Category filter changed to: '{category}'")
        filtered_tags = self._get_filtered_tags_by_category()
        logger.debug(
            f"Filtered to {len(filtered_tags)} tags for " f"category '{category}'"
        )
        self._handle_text_change(self.tag_input.text())

    def _get_filtered_tags_by_category(self) -> list[str]:
        """Retrieve tags filtered by the currently selected category.

        Returns the appropriate tag list based on the current category filter
        selection. Used throughout the application to respect user's category
        filtering preference.

        Returns:
            list[str]: List of tags from the selected category.
                      If "All categories" is selected, returns all available tags.
                      If a specific category is selected, returns only tags from that category.
                      Returns empty list if selected category doesn't exist.

        Note:
            Tags within each category are pre-sorted alphabetically during initialization.
        """
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
        """Display all available tags filtered by category, excluding already used tags.

        Populates the suggestions widget with all available tags from the current
        category filter, excluding tags that have already been entered. Tags are
        formatted with category information when "All categories" is selected.

        The display format varies based on category selection:
        - All categories: "emoji tag · Category Name"
        - Specific category: "tag" (no category info)

        Used tags are determined by parsing completed entries (those followed by commas)
        in the input field. This prevents duplicate tag suggestions and maintains
        a clean, relevant suggestions list.

        Note:
            Updates the suggestions widget immediately and logs statistics about
            the filtering process for debugging purposes.
        """
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
        """Handle real-time changes in the tag input field text.

        Processes text changes to provide intelligent autocomplete suggestions.
        Extracts the current word being typed, filters available tags by category
        and usage, then displays relevant suggestions with exact matches prioritized.

        Args:
            text (str): Current complete text in the input field.
                       May contain multiple comma-separated tags.

        Processing steps:
        1. Extract current word being typed (after last comma)
        2. If no current word, show all available unused tags
        3. Filter tags by category and exclude already used tags
        4. Separate exact matches from partial matches
        5. Update suggestions display with prioritized results

        Note:
            Suggestions are updated in real-time as the user types, providing
            immediate feedback and reducing the need for manual browsing.
        """
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
        """Retrieve current tags as a cleaned list of strings.

        Parses the tag input field text and returns a list of individual tags,
        excluding empty entries and whitespace-only entries.

        Returns:
            list[str]: List of current tags with whitespace stripped.
                      Empty list if no tags are present.
                      Incomplete tags (not followed by comma) are included.

        Example:
            Input: "forest, bird, wind, " -> ["forest", "bird", "wind"]
            Input: "nature, quiet" -> ["nature", "quiet"]
            Input: "" -> []

        Note:
            This method is commonly used by parent widgets to retrieve the
            current tagging state for saving to files or other operations.
        """
        text = self.tag_input.text()
        if not text.strip():
            return []
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return parts

    def set_tags(self, tags: list[str]) -> None:
        """Set tags programmatically, replacing current tags with trailing comma.

        Clears the current input and sets new tags with proper formatting.
        Automatically adds a trailing comma and space for easy extension,
        and positions the cursor at the end for continued typing.

        Args:
            tags (list[str]): List of tag strings to set.
                             Empty strings and whitespace-only entries are filtered out.

        Behavior:
        - Empty list clears the input field
        - Non-empty list joins tags with ", " and adds trailing ", "
        - Cursor is positioned at the end of the text
        - Input field receives focus for immediate editing
        - Suggestions and display are refreshed

        Example:
            set_tags(["forest", "bird"]) -> "forest, bird, " (with cursor at end)
            set_tags([]) -> "" (empty field)

        Note:
            This method is typically used by template application and external
            tag loading operations.
        """
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
        """Clear all current tags and reset the interface.

        Removes all text from the input field, resets the tags display,
        and refreshes the suggestions to show all available tags.
        Provides a quick way to start fresh with tag entry.

        Actions performed:
        - Clears tag input field text
        - Resets current tags display label
        - Refreshes suggestions to show all available tags
        - Logs the clearing operation

        Note:
            This operation is immediate and cannot be undone. Used by
            clear buttons and keyboard shortcuts throughout the application.
        """
        logger.info("Clearing all tags")
        self.tag_input.setText("")
        self._refresh_tags_display()
        self._show_all_available_tags()
        logger.debug("All tags cleared successfully")


class FieldRecorderTagger(QWidget):
    """Standalone main application window for the field recorder tagger.

    This class provides a complete standalone application interface for field
    recording tagging. It wraps the FileTagAutocomplete widget with a title,
    instructions, and proper window setup for independent operation.

    The window includes:
    - Application title and version display
    - Usage instructions with keyboard shortcuts
    - Full FileTagAutocomplete widget integration
    - Proper window sizing and layout

    Attributes:
        tagger_widget (FileTagAutocomplete): The main tagging interface widget.
    """

    def __init__(self) -> None:
        """Initialize the main tagger application window with title and layout.

        Creates a complete standalone window containing the FileTagAutocomplete widget
        along with application branding and usage instructions.
        """
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the complete user interface for the standalone tagger window.

        Sets up the window layout with:
        - Application title with version and styling
        - Usage instructions including keyboard shortcuts
        - Embedded FileTagAutocomplete widget
        - Proper spacing and alignment

        The window provides a complete standalone tagging experience
        with clear instructions for new users.
        """
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
    """Central template management system for tag templates.

    This class provides comprehensive template management functionality including
    creation, storage, retrieval, and usage tracking of tag templates. Templates
    allow users to quickly apply predefined sets of tags to recordings, improving
    workflow efficiency and tagging consistency.

    Key features:
    - Persistent JSON-based template storage
    - Default template initialization
    - Usage tracking and popularity sorting
    - Template CRUD operations (Create, Read, Update, Delete)
    - Import/export functionality
    - Automatic fallback to defaults on corruption

    Attributes:
        template_file (str): Path to the JSON template storage file.
        templates (dict): Loaded template data with usage statistics.
    """

    # def __init__(self, template_file="tag_templates.json"):
    def __init__(self):
        """Initialize the TemplateManager with configuration-based file path.

        Sets up the template manager using the configured template file path
        from app_config and immediately loads existing templates or creates
        defaults if no template file exists.

        The initialization process:
        1. Sets template file path from app configuration
        2. Loads existing templates from file
        3. Falls back to creating default templates if loading fails
        4. Ensures template file exists for future operations

        Note:
            Template file location is determined by app_config.TEMPLATE_CONFIG
            to maintain consistency with application configuration management.
        """
        # self.template_file = template_file
        self.template_file = app_config.TEMPLATE_CONFIG  # ✅

        self.templates = self.load_templates()

    def get_default_templates(self) -> dict[str, Any]:
        """Generate a comprehensive set of default templates for recording scenarios.

        Creates predefined templates covering typical field recording situations,
        each with carefully selected tags, descriptions, and initialized usage counts.
        These templates provide immediate value for new users and serve as examples
        for custom template creation.

        Returns:
            dict[str, Any]: Dictionary mapping template names to template data.
                           Each template contains:
                           - tags: List of tag strings
                           - description: Human-readable description
                           - usage_count: Initial usage count (0 for defaults)

        Default templates included:
        - 🌲 Forest Morning: Early forest recordings with birds
        - 🏙️ Busy Street: Urban street recordings with traffic
        - 🌧️ Rain Shower: Weather recordings with rain and wind
        - 🦅 Bird Concert: Rich birdsong in natural environments
        - 🌊 Seashore: Coastal recordings with waves and wind
        - 🐄 Farm: Agricultural recordings with animal sounds
        - 🌙 Silent Night: Peaceful nighttime atmosphere
        - 🦗 Summer Insects: Lively summer insect recordings

        Note:
            These templates are designed to cover common field recording scenarios
            while demonstrating effective tag combinations and naming conventions.
        """
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
        """Load templates from persistent storage with automatic fallback.

        Attempts to load templates from the configured JSON file. If loading
        fails due to missing file, corruption, or other errors, automatically
        creates and saves default templates to ensure the system remains functional.

        Returns:
            dict[str, Any]: Loaded template data from file, or default templates
                           if file loading failed.

        Loading process:
        1. Check if template file exists
        2. Parse JSON template data
        3. Return loaded templates if successful
        4. On any failure, generate and save default templates
        5. Return default templates as fallback

        Note:
            All errors are caught and handled gracefully to ensure the template
            system remains operational even with corrupted or missing files.
            Error messages are logged for debugging purposes.
        """
        try:
            if os.path.exists(self.template_file):
                with open(self.template_file, encoding="utf-8") as f:
                    loaded = json.load(f)
                    # print(f"Loaded {len(loaded)} templates from "
                    #       f"{self.template_file}")
                    return loaded
        except Exception as e:
            logger.error(f"Error loading templates: {e}")

        # Fallback to defaults
        defaults = self.get_default_templates()
        self.save_templates(defaults)
        logger.info(f"Created default templates ({len(defaults)} templates)")
        return defaults

    def save_templates(self, templates=None):
        """Save templates to persistent JSON storage.

        Writes the current template data to the configured JSON file with proper
        UTF-8 encoding and formatting. If no templates are specified, saves the
        current instance templates.

        Args:
            templates (dict, optional): Template data to save.
                                      If None, uses self.templates.

        File format:
            JSON with 2-space indentation and Unicode preservation for emoji
            template names and international characters in descriptions.

        Note:
            All save operations include error handling with console logging.
            The ensure_ascii=False parameter preserves emoji and international
            characters in template names and descriptions.
        """
        if templates is None:
            templates = self.templates

        try:
            with open(self.template_file, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)
            logger.info(f"Templates saved to {self.template_file}")
        except Exception as e:
            logger.error(f"Error saving templates: {e}")

    def get_template(self, name: str) -> dict[str, Any]:
        """Retrieve a specific template by name.

        Args:
            name (str): Exact name of the template to retrieve.
                       Template names are case-sensitive.

        Returns:
            dict[str, Any]: Template data containing tags, description, and usage_count.
                           Empty dictionary if template name doesn't exist.

        Template data structure:
            {
                "tags": ["tag1", "tag2", ...],
                "description": "Template description",
                "usage_count": int
            }

        Note:
            Returns empty dict rather than None for easier error handling
            in calling code.
        """
        return self.templates.get(name, {})

    def add_template(self, name: str, tags: list[str], description: str = ""):
        """Add a new template to the collection.

        Creates a new template with the specified name, tags, and description.
        Automatically initializes usage count to 0 and saves to persistent storage.

        Args:
            name (str): Unique name for the template. Will overwrite if name exists.
            tags (list[str]): List of tag strings for the template.
            description (str, optional): Human-readable description. Defaults to empty string.

        Actions performed:
        1. Creates template data structure
        2. Adds to templates collection
        3. Saves to persistent storage
        4. Logs creation confirmation

        Note:
            If a template with the same name already exists, it will be overwritten
            without warning. Check existence first if overwriting is a concern.
        """
        self.templates[name] = {
            "tags": tags,
            "description": description,
            "usage_count": 0,
        }
        self.save_templates()
        logger.info(f"Template added: {name}")

    def update_template(self, name: str, tags: list[str], description: str = ""):
        """Update an existing template's tags and description.

        Modifies the specified template's tags and description while preserving
        the usage count. Only updates if the template exists.

        Args:
            name (str): Name of existing template to update.
            tags (list[str]): New list of tag strings.
            description (str, optional): New description. Defaults to empty string.

        Actions performed:
        1. Verifies template exists
        2. Updates tags and description
        3. Preserves existing usage_count
        4. Saves to persistent storage
        5. Logs update confirmation

        Note:
            If the template doesn't exist, the operation fails silently.
            Usage count is preserved to maintain popularity statistics.
        """
        if name in self.templates:
            self.templates[name]["tags"] = tags
            self.templates[name]["description"] = description
            self.save_templates()
            logger.info(f"Template updated: {name}")

    def delete_template(self, name: str):
        """Delete a template from the collection.

        Removes the specified template from the collection and updates
        persistent storage. This operation cannot be undone.

        Args:
            name (str): Name of template to delete.

        Actions performed:
        1. Verifies template exists
        2. Removes from templates collection
        3. Saves updated collection to storage
        4. Logs deletion confirmation

        Note:
            If the template doesn't exist, the operation fails silently.
            This operation cannot be undone - consider export backup before
            bulk deletions.
        """
        if name in self.templates:
            del self.templates[name]
            self.save_templates()
            logger.info(f"Template deleted: {name}")

    def increment_usage(self, name: str):
        """Increment the usage count for a template to track popularity.

        Increases the usage count by 1 and saves to persistent storage.
        This data is used for sorting templates by popularity and providing
        usage statistics in the template manager interface.

        Args:
            name (str): Name of template whose usage count should be incremented.

        Actions performed:
        1. Verifies template exists
        2. Increments usage_count (defaults to 0 if missing)
        3. Saves updated data to storage

        Note:
            If the template doesn't exist, the operation fails silently.
            Usage count starts at 0 for new templates and is automatically
            initialized if the field is missing from older template data.
        """
        if name in self.templates:
            self.templates[name]["usage_count"] = (
                self.templates[name].get("usage_count", 0) + 1
            )
            self.save_templates()

    def get_popular_templates(self, limit: int = 4) -> list[str]:
        """Retrieve the most frequently used templates sorted by popularity.

        Returns template names sorted by usage count in descending order,
        limited to the specified number of templates. Used for populating
        quick access buttons and highlighting commonly used templates.

        Args:
            limit (int, optional): Maximum number of templates to return.
                                 Defaults to 4 for quick access buttons.

        Returns:
            list[str]: Template names sorted by usage count (highest first).
                      Limited to the specified count.
                      Empty list if no templates exist.

        Note:
            Templates with missing usage_count are treated as having 0 uses.
            If multiple templates have the same usage count, their relative
            order is not guaranteed to be consistent.
        """
        sorted_templates = sorted(
            self.templates.items(),
            key=lambda x: x[1].get("usage_count", 0),
            reverse=True,
        )
        return [name for name, _ in sorted_templates[:limit]]


class TemplateQuickButtons(QWidget):
    """Quick template application buttons widget with template management integration.

    Provides a horizontal row of buttons for applying the most popular templates
    quickly, along with a settings button for accessing the full template manager.
    Automatically updates button layout based on template popularity and usage.

    Key features:
    - Dynamic button creation based on popular templates
    - Keyboard shortcut tooltips (Ctrl+1-4)
    - Usage statistics in button tooltips
    - Template manager access button
    - Automatic refresh after template usage

    Attributes:
        parent_tagger: Reference to the parent FileTagAutocomplete widget.
        template_manager: TemplateManager instance for template operations.
        buttons_layout: Layout containing the template buttons.
    """

    def __init__(self, parent_tagger):
        """Initialize the template quick buttons widget.

        Args:
            parent_tagger: Parent FileTagAutocomplete widget to apply templates to.
                          Must support set_tags() method for template application.
        """
        super().__init__()
        self.parent_tagger = parent_tagger
        self.template_manager = TemplateManager()
        self.buttons_layout = None  # Store reference
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface with label and button layout.

        Creates the widget layout including:
        - Styled label for the quick templates section
        - Horizontal layout for template buttons
        - Initial template button creation
        - Proper spacing and margins
        """
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
        """Apply template tags to the parent tagger widget with proper formatting.

        Takes template data and applies its tags to the parent tagger widget,
        ensuring proper comma formatting for continued editing. Also increments
        usage count and refreshes button layout for popularity tracking.

        Args:
            template_data (dict): Template data containing tags list and metadata.
            template_name (str): Name of template for usage tracking and logging.

        Actions performed:
        1. Extract tags from template data
        2. Add trailing comma for continued editing
        3. Apply tags to parent tagger widget
        4. Increment template usage count
        5. Refresh buttons to reflect new popularity order
        6. Log application success
        """
        tags = template_data.get("tags", [])

        # Add trailing comma
        tags_with_comma = tags.copy()
        if tags_with_comma:
            tags_with_comma.append("")  # Empty string creates trailing comma

        self.parent_tagger.set_tags(tags_with_comma)

        # Increment usage count
        self.template_manager.increment_usage(template_name)

        logger.info(
            f"Template '{template_name}' applied: {tags} " "(with trailing comma)"
        )

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

            logger.info(f"Loaded template for editing: {template_name}")

    def new_template(self):
        """Clear editor for new template."""
        self.current_template_name = None
        self.name_input.clear()
        self.tags_input.clear()
        self.description_input.clear()
        self.name_input.setFocus()
        logger.info("Ready to create new template")

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
                logger.info(
                    f"Template '{self.current_template_name}' applied " "via F9 manager"
                )
                self.accept()  # Close dialog
            else:
                logger.error("Could not find parent apply_template function")


def main() -> None:
    """Main function for standalone field recorder tagger application execution.

    Creates and displays the complete standalone tagger application with
    proper Qt application lifecycle management. Used when the module is
    executed directly rather than imported as a component.

    Application lifecycle:
    1. Create QApplication instance
    2. Initialize FieldRecorderTagger window
    3. Show window to user
    4. Enter Qt event loop
    5. Exit with appropriate code when closed

    Note:
        This function does not return until the application is closed.
        All logging and error handling is performed within the function.
    """
    logger.info("Starting Field Recorder Tagger application")
    app = QApplication(sys.argv)
    window = FieldRecorderTagger()
    window.show()
    logger.info("Application window shown, entering event loop")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
