"""Application configuration management for Timbrosa Field Recorder Analyzer.

This module handles configuration paths, file locations, and application metadata
for the Timbrosa Field Recorder Analyzer. It provides centralized configuration
management including user settings, templates, recent directories, and application
constants.

The module automatically creates the necessary config directory structure and
provides consistent paths for all configuration files across the application.

Constants:
    TEMPLATE_CONFIG (str): Path to tag templates configuration file
    USER_CONFIG (str): Path to user preferences configuration file
    RECENT_DIRS_CONFIG (str): Path to recent directories configuration file
    APP_NAME (str): Application display name
    APP_VERSION (str): Current application version
    ORG_NAME (str): Organization name for settings storage

Functions:
    get_config_path: Generate paths for configuration files
"""

import os


def get_config_path(filename):
    """Get path to config file relative to script location.

    Creates a config directory adjacent to the current script and generates
    the full path to a configuration file within that directory. The config
    directory is created automatically if it doesn't exist.

    Args:
        filename (str): Name of the configuration file (including extension)

    Returns:
        str: Absolute path to the configuration file in the config directory

    Example:
        >>> get_config_path("settings.json")
        '/path/to/app/config/settings.json'
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(script_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, filename)


# Configuration file paths - automatically generated using get_config_path()
# These paths are relative to the script location in a 'config' subdirectory

TEMPLATE_CONFIG = get_config_path("tag_templates.json")
"""str: Path to the tag templates configuration file.

Stores user-defined tag templates and presets for quick tagging of audio files.
Contains JSON data with template definitions, categories, and metadata.
"""

USER_CONFIG = get_config_path("user_config.json")
"""str: Path to the user preferences configuration file.

Stores user-specific settings and preferences including UI state, default values,
and application behavior customizations. Contains JSON data with user preferences.
"""

RECENT_DIRS_CONFIG = get_config_path("recent_directories.json")
"""str: Path to the recent directories configuration file.

Maintains a list of recently accessed directories for quick navigation.
Contains JSON data with directory paths and access timestamps.
"""

# SETTINGS_CONFIG = get_config_path("app_settings.json")
# Reserved for future application settings if needed

# Application metadata constants

APP_NAME = "Timbrosa Field Recorder Analyzer"
"""str: Display name of the application.

Used in window titles, dialog boxes, and system integration.
"""

APP_VERSION = "1.0.0"
"""str: Current version of the application.

Follows semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes or major feature releases
- MINOR: New features that are backward compatible
- PATCH: Bug fixes and minor improvements
"""

ORG_NAME = "Timbrosa"
"""str: Organization name for the application.

Used for system settings storage, application data directories,
and organizational identification in system integration.
"""


# Version history and semantic versioning guide:
# 1.0.0 = Initial release (Eerste release)
# 1.0.1 = Bug fixes and patches
# 1.1.0 = New features (Nieuwe features)
# 2.0.0 = Breaking changes or major architectural updates
