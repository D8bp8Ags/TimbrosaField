"""Shared pytest fixtures for the TimbrosaField test suite."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def isolated_qsettings(tmp_path, monkeypatch):
    """Isolate QSettings to a throwaway INI file for the duration of a test.

    Ensures tests never read or write the developer's real, machine-local
    QSettings store (native format under e.g. ~/Library/Preferences on
    macOS or the registry on Windows). Each test gets its own empty
    settings file that is discarded when ``tmp_path`` is cleaned up.
    """
    from PyQt5.QtCore import QSettings

    ini_path = tmp_path / "settings.ini"
    QSettings.setDefaultFormat(QSettings.IniFormat)
    monkeypatch.setattr(QSettings, "__new__", QSettings.__new__)

    original_init = QSettings.__init__

    def _isolated_init(self, *args, **kwargs):
        if not args and not kwargs:
            original_init(self, str(ini_path), QSettings.IniFormat)
        else:
            original_init(self, *args, **kwargs)

    monkeypatch.setattr(QSettings, "__init__", _isolated_init)
    yield ini_path


@pytest.fixture
def qapp():
    """Provide a single QApplication instance for widget-based tests."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
