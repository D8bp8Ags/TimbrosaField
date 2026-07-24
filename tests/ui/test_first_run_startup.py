"""Regression tests for the first-run startup crash.

``SettingsManager.get_view_mode()`` used to default to the misspelled
"per-kanaal" (hyphen), while ``WavViewer.set_view_mode()`` only accepts
"per_kanaal" (underscore). ``restore_all_settings()`` only caught
``AttributeError``, so the resulting ``ValueError`` propagated out of
``MainWindow.__init__`` on every clean/first-run profile.
"""

import pytest

from my_app.ui.settings import DEFAULT_VIEW_MODE, VALID_VIEW_MODES, SettingsManager


def test_default_view_mode_is_a_valid_wav_viewer_mode():
    """The SettingsManager default must be a mode WavViewer actually accepts."""
    assert DEFAULT_VIEW_MODE in VALID_VIEW_MODES


def test_get_view_mode_fresh_profile_returns_canonical_default(isolated_qsettings):
    """A clean QSettings store (first run) must yield a canonical view mode."""
    settings = SettingsManager()

    view_mode = settings.get_view_mode()

    assert view_mode in VALID_VIEW_MODES
    assert view_mode == DEFAULT_VIEW_MODE


def test_get_view_mode_normalizes_legacy_hyphen_value(isolated_qsettings):
    """A previously saved legacy "per-kanaal" value must still resolve correctly."""
    settings = SettingsManager()
    settings.settings.setValue("view/waveform_mode", "per-kanaal")

    view_mode = settings.get_view_mode()

    assert view_mode == "per_kanaal"
    assert view_mode in VALID_VIEW_MODES


def test_get_view_mode_preserves_canonical_value(isolated_qsettings):
    """An already-canonical stored value must be returned unchanged."""
    settings = SettingsManager()
    settings.settings.setValue("view/waveform_mode", "per_kanaal")

    assert settings.get_view_mode() == "per_kanaal"


def test_get_view_mode_falls_back_on_unknown_value(isolated_qsettings):
    """A corrupted/unknown stored value must fall back to a valid default."""
    settings = SettingsManager()
    settings.settings.setValue("view/waveform_mode", "totally-unknown-mode")

    view_mode = settings.get_view_mode()

    assert view_mode in VALID_VIEW_MODES
    assert view_mode == DEFAULT_VIEW_MODE


@pytest.mark.parametrize(
    "stored_value",
    [
        pytest.param(None, id="fresh_profile"),
        pytest.param("per-kanaal", id="legacy_hyphen_value"),
        pytest.param("per_kanaal", id="canonical_value"),
        pytest.param("mono", id="mono_value"),
        pytest.param("overlay", id="overlay_value"),
        pytest.param("garbage", id="unknown_value"),
    ],
)
def test_main_window_restores_settings_without_raising(
    qapp, isolated_qsettings, qt_widget_cleanup, stored_value
):
    """MainWindow construction must never raise while restoring view settings.

    This is the actual regression scenario: on the pre-fix code, the
    fresh-profile case (nothing ever saved, ``stored_value=None``) raised an
    uncaught ValueError from deep inside
    ``SettingsManager.restore_all_settings()``, crashing app startup. The
    other cases cover a profile saved by a pre-fix build (legacy hyphen
    value), an already-canonical value, each other valid mode, and a
    corrupted/unknown stored value.

    Each MainWindow is registered with the ``qt_widget_cleanup`` fixture,
    which closes and schedules deletion of widgets after every test; without
    this, repeated MainWindow construction within a single offscreen Qt
    process caused a segmentation fault in pyqtgraph after a few iterations.
    """
    if stored_value is not None:
        settings = SettingsManager()
        settings.settings.setValue("view/waveform_mode", stored_value)
        settings.settings.sync()

    import my_app.main as main_mod

    window = qt_widget_cleanup(main_mod.MainWindow())
    assert window.wav_viewer.view_mode in VALID_VIEW_MODES
