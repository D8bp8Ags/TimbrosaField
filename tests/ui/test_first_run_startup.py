"""Regression tests for the first-run startup crash.

Baseline (architecture notes, section 4.2):
``SettingsManager.get_view_mode()`` used to default to the misspelled
"per-kanaal" (hyphen), while ``WavViewer.set_view_mode()`` only accepts
"per_kanaal" (underscore). ``restore_all_settings()`` only caught
``AttributeError``, so the resulting ``ValueError`` propagated out of
``MainWindow.__init__`` on every clean/first-run profile.
"""

import pytest

from settings_manager import DEFAULT_VIEW_MODE, VALID_VIEW_MODES, SettingsManager


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
    ],
)
def test_main_window_restores_settings_without_raising(
    qapp, isolated_qsettings, stored_value
):
    """MainWindow construction must never raise while restoring view settings.

    This is the actual regression scenario: on the pre-fix code, the
    fresh-profile case (nothing ever saved, ``stored_value=None``) raised an
    uncaught ValueError from deep inside
    ``SettingsManager.restore_all_settings()``, crashing app startup.
    The legacy-value case covers a profile saved by a pre-fix build.

    Kept to two cases (rather than parametrizing every view mode) because
    constructing several real ``MainWindow``/``WavViewer`` instances with
    live pyqtgraph plots in a single offscreen process is heavy; the
    remaining value permutations are covered without widget construction
    by the ``SettingsManager``-only tests above.
    """
    if stored_value is not None:
        settings = SettingsManager()
        settings.settings.setValue("view/waveform_mode", stored_value)
        settings.settings.sync()

    import main as main_mod

    window = main_mod.MainWindow()
    try:
        assert window.wav_viewer.view_mode in VALID_VIEW_MODES
    finally:
        window.close()
        window.deleteLater()
