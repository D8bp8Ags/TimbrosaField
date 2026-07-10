"""Shared pytest fixtures for the TimbrosaField test suite."""

import gc
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def isolated_qsettings(tmp_path):
    """Isolate QSettings to a throwaway directory for the duration of a test.

    Uses the supported ``QSettings.setDefaultFormat``/``setPath`` mechanism
    (no monkeypatching of the QSettings constructor) so that production code
    calling the parameterless ``QSettings()`` transparently writes into an
    IniFormat file under ``tmp_path`` instead of the developer's real,
    machine-local native settings store (e.g. ~/Library/Preferences on
    macOS or the registry on Windows). Global QSettings state is restored
    after the test so later tests/processes are unaffected.
    """
    from PyQt5.QtCore import QSettings

    original_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

    try:
        yield tmp_path
    finally:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, None)
        QSettings.setDefaultFormat(original_format)


@pytest.fixture(scope="session")
def qapp():
    """Provide a single, session-wide QApplication instance for widget tests.

    Reusing one QApplication (rather than creating a new one per test)
    avoids the native-widget resource accumulation that caused a
    segmentation fault in pyqtgraph after repeatedly constructing and
    tearing down full MainWindow instances within a single offscreen
    Qt process (see architecture notes,
    Fase 1 section).
    """
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def qt_widget_cleanup(qapp):
    """Track top-level widgets created during a test and dispose of them.

    Yields a callable that tests should invoke with each widget they
    construct (e.g. a ``MainWindow``). On teardown, every registered widget
    is closed and scheduled for deletion via ``deleteLater()``, and pending
    Qt deferred-deletion events are processed before the next test runs.
    This keeps native widget/plot resources from accumulating across tests
    in the same process.
    """
    from PyQt5.QtWidgets import QApplication

    widgets = []

    def _register(widget):
        widgets.append(widget)
        return widget

    yield _register

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    QApplication.processEvents()
    gc.collect()
    QApplication.processEvents()


@pytest.fixture
def write_wav(tmp_path):
    """Write raw WAV bytes to a real temp file and return its path (as str).

    Several wav_analyzer.py/wav_save_strategies.py functions operate on file
    paths rather than in-memory streams, so tests need a real file on disk.
    Each call creates a uniquely named file under pytest's per-test tmp_path,
    which is cleaned up automatically by pytest.
    """
    counter = {"n": 0}

    def _write(wav_bytes: bytes, name: str | None = None) -> str:
        if name is None:
            counter["n"] += 1
            name = f"fixture_{counter['n']}.wav"
        path = tmp_path / name
        path.write_bytes(wav_bytes)
        return str(path)

    return _write
