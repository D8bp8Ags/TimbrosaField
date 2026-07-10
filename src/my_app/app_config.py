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
import sys
from pathlib import Path

# Application metadata constants (defined early: path helpers below need them)

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


def get_legacy_config_path(filename):
    """Get path to a config file under the old, in-source-tree location.

    Fase 8: this is now only a *read fallback* for pre-migration installs.
    New config writes use get_user_data_dir() instead (see get_config_path()
    below). Kept as its own function because it must not create the legacy
    directory on every import — only get_config_path()'s migration check
    reads from here.

    Args:
        filename (str): Name of the configuration file (including extension)

    Returns:
        str: Absolute path to the configuration file in the legacy
            'src/my_app/config' directory (may not exist).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "config", filename)


def get_user_data_dir() -> Path:
    """Return the platform-appropriate directory for editable user data.

    Used for bewerkbare gebruikersconfiguratie (tag templates, recent
    directories, user config) per hoofdstuk 8.5 of the refactor plan — not
    for caches or vendored resources.

    Locations (created on first use, not on import):
        macOS:   ~/Library/Application Support/<ORG_NAME>/<APP_NAME>
        Windows: %APPDATA%/<ORG_NAME>/<APP_NAME>
        other:   ~/.local/share/<org>/<app> (XDG-style fallback)

    Returns:
        Path: Directory for user data. Not guaranteed to exist yet.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / ORG_NAME / APP_NAME


def get_cache_dir() -> Path:
    """Return the platform-appropriate directory for caches and downloaded models.

    Locations (created on first use, not on import):
        macOS:   ~/Library/Caches/<ORG_NAME>/<APP_NAME>
        Windows: %LOCALAPPDATA%/<ORG_NAME>/<APP_NAME>/Cache
        other:   ~/.cache/<org>/<app> (XDG-style fallback)

    Returns:
        Path: Directory for caches/models. Not guaranteed to exist yet.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
        return base / ORG_NAME / APP_NAME
    elif sys.platform == "win32":
        base = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        )
        return base / ORG_NAME / APP_NAME / "Cache"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
        return base / ORG_NAME / APP_NAME


def get_config_path(filename):
    """Get path to a user config file, migrating from the legacy location if needed.

    Fase 8: config JSON is user data, not source code, so it now lives under
    get_user_data_dir() instead of next to the package sources. For
    backward compatibility with pre-Fase-8 installs:
        - if the new-location file already exists, it is used as-is;
        - otherwise, if a legacy src/my_app/config/<filename> exists, its
          contents are copied once to the new location (the legacy file is
          left in place, untouched, as a safety net — no data is deleted);
        - otherwise, a fresh path in the new location is returned (the file
          itself is created by the caller on first write).

    The new user-data directory is created eagerly (mkdir), matching the
    original get_config_path() behavior of always ensuring the directory
    exists; the file itself is not created here.

    Args:
        filename (str): Name of the configuration file (including extension)

    Returns:
        str: Absolute path to the configuration file in the user-data
            config directory.

    Example:
        >>> get_config_path("settings.json")
        '/Users/name/Library/Application Support/Timbrosa/.../config/settings.json'
    """
    new_dir = get_user_data_dir() / "config"
    new_dir.mkdir(parents=True, exist_ok=True)
    new_path = new_dir / filename

    if not new_path.exists():
        legacy_path = Path(get_legacy_config_path(filename))
        if legacy_path.exists():
            try:
                new_path.write_bytes(legacy_path.read_bytes())
            except OSError:
                pass  # Fall through to returning the new (still-empty) path.

    return str(new_path)


# Configuration file paths - automatically generated using get_config_path()
# These paths point to the user-data config directory (see get_config_path()
# docstring for the one-time migration/fallback behavior from the legacy
# src/my_app/config/ location).

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

APP_LICENSE = "GPL-3.0"
"""str: SPDX identifier of the application license."""

APP_URL = "https://github.com/D8bp8Ags/TimbrosaField"
"""str: Project homepage / source repository URL."""


# Waveform viewer limits

MAX_WAVEFORM_RAM_MB = 2048
"""int: Maximum estimated RAM (in MB) allowed for loading a WAV file into the waveform viewer.

soundfile loads PCM data as float64 (8 bytes per sample).  A stereo 96 kHz file uses
~92 MB per minute, so 2048 MB covers roughly 22 minutes at 96 kHz or 48 minutes at 44.1 kHz.
Files that would exceed this limit trigger a warning dialog before loading.
"""


# Audio playback constants

DEFAULT_VOLUME = 70
"""int: Default audio volume level (0–100).

Used as the initial slider value and fallback when no saved setting exists.
"""

SEEK_STEP_MS = 10000
"""int: Seek step size in milliseconds (10 seconds).

Used by seek_backward() and seek_forward() in the audio player.
"""

MAX_FILE_COUNTER = 999
"""int: Maximum number of filename conflict retries during export.

When an output file already exists, a numeric suffix (_001, _002, …) is
appended up to this limit before giving up.
"""


# Version history and semantic versioning guide:
# 1.0.0 = Initial release (Eerste release)
# 1.0.1 = Bug fixes and patches
# 1.1.0 = New features (Nieuwe features)
# 2.0.0 = Breaking changes or major architectural updates
