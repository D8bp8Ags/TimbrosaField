"""Targeted tests for Fase 8 user-data/cache path helpers in app_config.py.

Covers: platform-appropriate path resolution, JSON-config migration
fallback from the legacy src/my_app/config/ location, and the "no data
loss, no real home-directory writes" guarantees required by the refactor
plan (chapter 8.5).
"""

from __future__ import annotations

import importlib
import json

import pytest

import my_app.app_config as app_config


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect HOME/APPDATA/LOCALAPPDATA/XDG_* to tmp_path so no test ever
    touches the developer's real user-data or cache directories."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(app_config.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    return home


def test_user_data_dir_macos(monkeypatch, isolated_home):
    monkeypatch.setattr(app_config.sys, "platform", "darwin")
    result = app_config.get_user_data_dir()
    assert result == isolated_home / "Library" / "Application Support" / "Timbrosa" / app_config.APP_NAME


def test_cache_dir_macos(monkeypatch, isolated_home):
    monkeypatch.setattr(app_config.sys, "platform", "darwin")
    result = app_config.get_cache_dir()
    assert result == isolated_home / "Library" / "Caches" / "Timbrosa" / app_config.APP_NAME


def test_user_data_dir_windows(monkeypatch, isolated_home):
    monkeypatch.setattr(app_config.sys, "platform", "win32")
    result = app_config.get_user_data_dir()
    assert result == isolated_home / "AppData" / "Roaming" / "Timbrosa" / app_config.APP_NAME


def test_cache_dir_windows(monkeypatch, isolated_home):
    monkeypatch.setattr(app_config.sys, "platform", "win32")
    result = app_config.get_cache_dir()
    assert result == isolated_home / "AppData" / "Local" / "Timbrosa" / app_config.APP_NAME / "Cache"


def test_user_data_dir_linux_fallback(monkeypatch, isolated_home):
    monkeypatch.setattr(app_config.sys, "platform", "linux")
    result = app_config.get_user_data_dir()
    assert result == isolated_home / ".local" / "share" / "Timbrosa" / app_config.APP_NAME


def test_get_config_path_migrates_from_legacy(monkeypatch, isolated_home, tmp_path):
    """A file that only exists at the legacy src/my_app/config/ location is
    copied once to the new user-data location; the legacy file is kept."""
    monkeypatch.setattr(app_config.sys, "platform", "darwin")

    legacy_dir = tmp_path / "legacy_config"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "user_config.json"
    legacy_file.write_text(json.dumps({"wav_tags": {"foo": "bar"}}), encoding="utf-8")
    monkeypatch.setattr(
        app_config, "get_legacy_config_path", lambda filename: str(legacy_dir / filename)
    )

    new_path = app_config.get_config_path("user_config.json")

    assert new_path != str(legacy_file)
    assert isolated_home in app_config.Path(new_path).parents
    assert json.loads(app_config.Path(new_path).read_text(encoding="utf-8")) == {
        "wav_tags": {"foo": "bar"}
    }
    # Legacy file must be left untouched (no data loss / no auto-delete).
    assert legacy_file.exists()


def test_get_config_path_no_legacy_file_creates_fresh_path(monkeypatch, isolated_home, tmp_path):
    monkeypatch.setattr(app_config.sys, "platform", "darwin")
    legacy_dir = tmp_path / "legacy_config_empty"
    monkeypatch.setattr(
        app_config, "get_legacy_config_path", lambda filename: str(legacy_dir / filename)
    )

    new_path = app_config.get_config_path("recent_directories.json")

    assert not app_config.Path(new_path).exists()
    assert isolated_home in app_config.Path(new_path).parents


def test_get_config_path_prefers_existing_new_file(monkeypatch, isolated_home, tmp_path):
    """If the new-location file already exists, it is used as-is and the
    legacy file (even if present) is not consulted again."""
    monkeypatch.setattr(app_config.sys, "platform", "darwin")

    legacy_dir = tmp_path / "legacy_config"
    legacy_dir.mkdir()
    (legacy_dir / "tag_templates.json").write_text('{"old": true}', encoding="utf-8")
    monkeypatch.setattr(
        app_config, "get_legacy_config_path", lambda filename: str(legacy_dir / filename)
    )

    first_path = app_config.get_config_path("tag_templates.json")
    app_config.Path(first_path).write_text('{"new": true}', encoding="utf-8")

    second_path = app_config.get_config_path("tag_templates.json")
    assert second_path == first_path
    assert json.loads(app_config.Path(second_path).read_text(encoding="utf-8")) == {"new": True}


def test_reload_does_not_touch_real_home(monkeypatch, isolated_home):
    """Reloading app_config under an isolated HOME must not write to the
    developer's real Application Support/Caches directories."""
    monkeypatch.setattr(app_config.sys, "platform", "darwin")
    importlib.reload(app_config)
    try:
        assert str(app_config.USER_CONFIG).startswith(str(isolated_home))
    finally:
        importlib.reload(app_config)
