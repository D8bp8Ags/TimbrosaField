"""Tag template persistence and management.

Pure data/IO class extracted from tag_completer.py (Fase 7). No Qt
dependency — persists and retrieves tag templates as JSON.
"""

import json
import logging
import os
from typing import Any

import my_app.app_config as app_config

logger = logging.getLogger(__name__)


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
        self.template_file = app_config.TEMPLATE_CONFIG

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
            # 🌿 NATURE
            "🌲 Forest Morning": {
                "tags": ["forest", "bird", "rustling leaves", "morning", "quiet", "calm"],
                "description": "Early morning forest ambience with birds and gentle leaf movement",
                "usage_count": 0,
            },
            "🌳 Wind Through Trees": {
                "tags": ["forest", "rustling leaves", "wind", "continuous", "immersive", "calm"],
                "description": "Wind moving through trees with leaf movement",
                "usage_count": 0,
            },
            "🌊 Streamside": {
                "tags": ["stream", "running water", "forest", "morning", "continuous", "calm"],
                "description": "Forest stream ambience with flowing water",
                "usage_count": 0,
            },
            "🌊 Riverbank": {
                "tags": ["river", "running water", "afternoon", "continuous", "immersive", "calm"],
                "description": "Riverbank ambience with steady water flow",
                "usage_count": 0,
            },
            "💦 Waterfall": {
                "tags": ["waterfall", "running water", "forest", "loud", "continuous", "immersive"],
                "description": "Strong waterfall sound in a natural setting",
                "usage_count": 0,
            },
            "🌊 Seashore": {
                "tags": ["sea", "beach", "waves", "wind", "continuous", "calm"],
                "description": "Coastal ambience with waves and sea wind",
                "usage_count": 0,
            },
            "🏜️ Dune Wind": {
                "tags": ["dune", "wind", "evening", "sparse", "distant", "calm"],
                "description": "Wind across a dune landscape",
                "usage_count": 0,
            },
            "🌾 Open Meadow": {
                "tags": ["meadow", "bird", "wind", "afternoon", "immersive", "calm"],
                "description": "Open meadow ambience with birds and wind",
                "usage_count": 0,
            },
            "🌿 Heath Wind": {
                "tags": ["heath", "wind", "evening", "continuous", "quiet", "dark"],
                "description": "Wind moving across heathland",
                "usage_count": 0,
            },
            "🪨 Cave Interior": {
                "tags": ["cave", "quiet", "distant", "immersive", "dark", "stereo"],
                "description": "Dark cave interior with spacious ambience",
                "usage_count": 0,
            },

            # 🌦️ WEATHER / CONDITIONS
            "🌧️ Rain Ambience": {
                "tags": ["rain", "wind", "continuous", "quiet", "dark"],
                "description": "Steady rain with light wind",
                "usage_count": 0,
            },
            "🌧️ Rain on Leaves": {
                "tags": ["rain", "rustling leaves", "wind", "continuous", "quiet"],
                "description": "Rain falling through foliage",
                "usage_count": 0,
            },
            "🌫️ Foggy Field": {
                "tags": ["field", "fog", "morning", "quiet", "sparse", "eerie"],
                "description": "Quiet fog-covered field",
                "usage_count": 0,
            },
            "🧊 Winter Pond": {
                "tags": ["pond", "ice", "quiet", "close", "calm"],
                "description": "Frozen pond with subtle ice sounds",
                "usage_count": 0,
            },
            "🌩️ Thunderstorm": {
                "tags": ["rain", "storm", "thunder", "loud", "continuous", "tense"],
                "description": "Heavy storm with thunder and rain",
                "usage_count": 0,
            },

            # 🏙️ URBAN / HUMAN
            "🏙️ Busy Street": {
                "tags": ["street", "traffic", "voices", "busy", "close", "loud"],
                "description": "Busy street with traffic and people",
                "usage_count": 0,
            },
            "🚉 Station Crowd": {
                "tags": ["station", "crowd", "footsteps", "voices", "busy", "immersive"],
                "description": "Crowded station with movement and voices",
                "usage_count": 0,
            },
            "🛍️ Store Interior": {
                "tags": ["store", "voices", "footsteps", "close", "intermittent", "clean"],
                "description": "Indoor store ambience",
                "usage_count": 0,
            },
            "🏫 Schoolyard": {
                "tags": ["school", "playground", "voices", "crowd", "afternoon", "busy"],
                "description": "Schoolyard with active voices and play",
                "usage_count": 0,
            },
            "🚧 Construction": {
                "tags": ["construction site", "construction work", "machinery", "loud", "busy", "noisy"],
                "description": "Construction site with heavy machinery",
                "usage_count": 0,
            },

            # 🐾 ANIMALS
            "🐦 Bird Chorus": {
                "tags": ["forest", "bird", "woodpecker", "morning", "continuous", "immersive"],
                "description": "Dense bird activity in a forest",
                "usage_count": 0,
            },
            "🦆 Wetland Birds": {
                "tags": ["marsh", "duck", "bird", "frog", "continuous", "immersive"],
                "description": "Wetland ambience with birds and frogs",
                "usage_count": 0,
            },
            "🦗 Insect Chorus": {
                "tags": ["cricket", "grasshopper", "evening", "continuous", "immersive", "calm"],
                "description": "Evening insect texture",
                "usage_count": 0,
            },
            "🦇 Night Creatures": {
                "tags": ["night", "bat", "frog", "distant", "sparse", "eerie"],
                "description": "Night ambience with distant animal activity",
                "usage_count": 0,
            },
            "🐄 Farmyard": {
                "tags": ["field", "cow", "dog", "voices", "close", "busy"],
                "description": "Active farm environment with animals and people",
                "usage_count": 0,
            },
            "🐎 Meadow Horses": {
                "tags": ["meadow", "horse", "afternoon", "quiet", "close", "calm"],
                "description": "Quiet meadow with nearby horses",
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
        except (OSError, json.JSONDecodeError) as e:
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
        except OSError as e:
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

