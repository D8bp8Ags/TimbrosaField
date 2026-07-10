"""Targeted tests for the versioned UI-resource path helpers in app_config.py.

Covers: get_resources_dir()/get_resource_path() resolution in normal
(non-frozen) execution, the PyInstaller sys._MEIPASS override, and that the
known resource files actually exist on the resolved package path.
"""

from __future__ import annotations

import my_app.app_config as app_config


def test_resources_dir_points_at_package_resources_directory():
    resources_dir = app_config.get_resources_dir()
    assert resources_dir.name == "resources"
    assert resources_dir.parent.name == "my_app"
    assert resources_dir.is_dir()


def test_icon_and_background_exist_on_resolved_path():
    assert app_config.get_resource_path("icon.png").is_file()
    assert app_config.get_resource_path("background.png").is_file()


def test_get_resource_path_joins_resources_dir_and_name():
    assert app_config.get_resource_path("background.png") == (
        app_config.get_resources_dir() / "background.png"
    )


def test_resources_dir_prefers_frozen_meipass_when_present(monkeypatch, tmp_path):
    frozen_resources = tmp_path / "my_app" / "resources"
    frozen_resources.mkdir(parents=True)
    monkeypatch.setattr(app_config.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert app_config.get_resources_dir() == frozen_resources


def test_resources_dir_falls_back_when_meipass_has_no_resources(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config.sys, "_MEIPASS", str(tmp_path), raising=False)

    resources_dir = app_config.get_resources_dir()
    assert resources_dir.name == "resources"
    assert resources_dir.is_dir()
