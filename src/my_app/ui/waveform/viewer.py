"""WAV Viewer module for analyzing and visualizing field recordings.

This module defines :class:`WavViewer`, a widget that offers audio analysis, waveform
visualisation and tagging features.  Responsibilities outside of audio processing are
delegated to dedicated manager classes:

* Menu operations -> ``MenuBarManager`` * File operations -> ``FileManager`` * Export
operations -> ``ExportManager`` * Dialog operations -> ``DialogManager`` * UI components
-> ``UIComponentManager``
"""

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pyqtgraph as pg
import soundfile as sf

# Local imports
import my_app.app_config as app_config
from my_app.audio.player import AudioPlayer
from PyQt5 import QtCore
from PyQt5.QtCore import QEvent, QModelIndex, QPoint, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QPolygon
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QAction,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from my_app.ui.components import load_photo_pixmap, ApplicationStylist
from my_app.tags.ui import FileTagAutocomplete
from my_app.user_config_manager import load_user_config
from my_app.wav.analyzer import wav_analyze
from my_app.wav.save_manager import WavSaveManager
from my_app.wav.save_strategies import SaveResult
from my_app.analysis import clipping as clipping_analysis
from my_app.analysis import waveform_inspector
from my_app.ui.waveform.ai_overlay import AiOverlayController
from my_app.ui.waveform.metadata_presenter import MetadataPresenter
from my_app.ui.dialogs.wav_save_dialog import WavSaveOptionsDialog


class WavAnalysisWorker(QThread):
    """Background thread for running wav_analyze() without blocking the UI.

    Emits ``finished`` with the analysis result dict on success, or ``error``
    with an exception message on failure.  The ``filename`` attribute lets the
    caller verify the result still matches the currently selected file.
    """

    finished = pyqtSignal(str, dict)   # (filename, analysis_result)
    error = pyqtSignal(str, str)       # (filename, error_message)

    def __init__(self, filename: str) -> None:
        """Initialize the worker with the file to analyse.

        Args:
            filename: Absolute path to the WAV file to analyse.
        """
        super().__init__()
        self.filename = filename

    def run(self) -> None:
        """Run wav_analyze in the background thread."""
        try:
            result = wav_analyze(self.filename)
            self.finished.emit(self.filename, result)
        except Exception as exc:  # noqa: BLE001 — worker must never crash silently
            self.error.emit(self.filename, str(exc))


@dataclass
class ClippingRegionInfo:
    """Data structure for representing audio clipping region information.

    Contains comprehensive metadata about detected clipping regions in audio files,
    used for visualization, analysis, and quality assessment in professional field
    recording workflows. This dataclass provides structured storage for temporal
    and contextual information about clipping incidents.

    Attributes:
        start_time: Beginning of the clipping region in seconds from file start.
                   Provides precise temporal positioning for visualization and navigation.
        end_time: End of the clipping region in seconds from file start.
                 Used with start_time to define the complete temporal span of clipping.
        region_idx: Zero-based index of this region within the total sequence.
                   Enables identification and navigation between multiple clipping regions.
        total_regions: Total number of clipping regions detected in the audio file.
                      Provides context for the significance of this particular region.
        channel_name: Human-readable identifier for the affected audio channel.
                     Examples: "Left Channel", "Right Channel", "Mono Mix"
        duration_ms: Duration of the clipping region in milliseconds.
                    Calculated value for quick assessment of clipping severity.

    Note:
        This dataclass is immutable by design to ensure data integrity during
        analysis operations. Duration values are pre-calculated for performance
        optimization in visualization and reporting workflows.
    """

    start_time: float
    end_time: float
    region_idx: int
    total_regions: int
    channel_name: str
    duration_ms: float


class RecordingListRow(QWidget):
    """Compact visual row for a recording list item."""

    def __init__(
        self,
        filename: str,
        duration_text: str = "",
        date_text: str = "",
        show_details: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recording_row")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 14, 2)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setObjectName("recording_row_icon")
        icon_label.setFixedWidth(16)
        icon_label.setPixmap(UiIconFactory.pixmap("waveform", 14))
        layout.addWidget(icon_label)

        name_label = QLabel(filename)
        name_label.setObjectName("recording_row_name")
        name_label.setToolTip(filename)
        name_label.setMinimumWidth(0)
        layout.addWidget(name_label, stretch=1)

        if show_details:
            meta_layout = QVBoxLayout()
            meta_layout.setContentsMargins(0, 0, 0, 0)
            meta_layout.setSpacing(0)

            duration_label = QLabel(duration_text)
            duration_label.setObjectName("recording_row_duration")
            duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            duration_label.setMinimumWidth(52)
            meta_layout.addWidget(duration_label)

            date_label = QLabel(date_text)
            date_label.setObjectName("recording_row_date")
            date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            date_label.setMinimumWidth(92)
            meta_layout.addWidget(date_label)

            layout.addLayout(meta_layout)


class MinuteSecondAxis(pg.AxisItem):
    """Axis that formats seconds as compact minute:second labels."""

    def tickStrings(self, values, scale, spacing):  # noqa: N802 - pyqtgraph API
        labels = []
        for value in values:
            seconds_value = max(0, int(round(value * scale)))
            minutes, seconds = divmod(seconds_value, 60)
            labels.append(f"{minutes}:{seconds:02d}")
        return labels


class UiIconFactory:
    """Small painted icons that avoid platform font fallback issues."""

    @staticmethod
    def icon(name: str, size: int = 16, color: str | None = None) -> QIcon:
        return QIcon(UiIconFactory.pixmap(name, size, color))

    @staticmethod
    def pixmap(name: str, size: int = 16, color: str | None = None) -> QPixmap:
        color = color or "#c8d0cc"
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color), max(1, size // 12))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if name == "waveform":
            y = size // 2
            for x, amp in ((3, 2), (6, 4), (9, 3), (12, 5)):
                painter.drawLine(x, y - amp, x, y + amp)
        elif name == "stereo":
            for y in (size // 3, (size * 2) // 3):
                painter.drawLine(3, y, size - 3, y)
                painter.drawLine(5, y - 2, 5, y + 2)
                painter.drawLine(size - 5, y - 2, size - 5, y + 2)
        elif name == "overlay":
            painter.drawRect(4, 4, 7, 7)
            painter.drawRect(7, 7, 7, 7)
        elif name == "settings":
            center = size // 2
            painter.drawEllipse(center - 3, center - 3, 6, 6)
            for dx, dy in ((0, -6), (0, 6), (-6, 0), (6, 0)):
                painter.drawLine(center, center, center + dx, center + dy)
        elif name == "menu":
            painter.setBrush(QColor(color))
            for x in (5, 8, 11):
                painter.drawEllipse(x - 1, size // 2 - 1, 2, 2)
        elif name == "zoom_fit":
            painter.drawEllipse(3, 3, 7, 7)
            painter.drawLine(9, 9, 13, 13)
            painter.drawLine(5, 6, 8, 6)
            painter.drawLine(6, 5, 6, 8)
        elif name == "minus":
            painter.drawLine(4, size // 2, size - 4, size // 2)
        elif name == "plus":
            painter.drawLine(4, size // 2, size - 4, size // 2)
            painter.drawLine(size // 2, 4, size // 2, size - 4)

        painter.end()
        return pixmap


class CueOverviewWidget(QWidget):
    """Compact cue overview strip shown beside the cue table."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("cue_overview")
        self._duration: float = 0.0
        self._markers: list[tuple[str, float, str]] = []
        self._waveform_peaks: list[float] = []
        self._selected_id: str | None = None
        self.setMinimumHeight(80)

    def set_waveform_data(self, data: np.ndarray | None) -> None:
        """Update the compact waveform shown behind cue markers."""
        self._waveform_peaks = []
        if data is not None and len(data) > 0:
            signal = data.mean(axis=1) if data.ndim > 1 else data
            bin_count = min(160, max(24, self.width() // 4))
            chunks = np.array_split(np.abs(signal), bin_count)
            peaks = [float(chunk.max()) if len(chunk) else 0.0 for chunk in chunks]
            peak_max = max(peaks) if peaks else 0.0
            if peak_max > 0:
                self._waveform_peaks = [peak / peak_max for peak in peaks]
        self.update()

    def set_cues(
        self,
        cue_points: list[dict[str, Any]],
        cue_labels: dict[str, str],
        sample_rate: int | None,
        duration: float | None,
    ) -> None:
        """Update the overview marker positions."""
        self._duration = float(duration or 0.0)
        self._markers = []
        if sample_rate and self._duration > 0:
            for cue in cue_points:
                cue_id = str(cue.get("ID", ""))
                offset = cue.get("Sample Offset", 0)
                if cue_id and offset >= 0:
                    label = cue_labels.get(cue_id, "")
                    if not label:
                        continue
                    time_s = max(0.0, min(offset / sample_rate, self._duration))
                    self._markers.append((cue_id, time_s, label))
        if self._selected_id and not any(
            cue_id == self._selected_id for cue_id, _time_s, _label in self._markers
        ):
            self._selected_id = None
        self.update()

    def set_selected_cue(self, cue_id: str | None) -> None:
        """Set the selected cue marker."""
        self._selected_id = cue_id
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(14, 16, -14, -20)
        baseline_y = rect.center().y()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#111516"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)

        axis_pen = QPen(QColor("#53605a"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(rect.left(), baseline_y, rect.right(), baseline_y)

        if self._duration <= 0:
            painter.setPen(QColor("#76837c"))
            painter.drawText(rect, Qt.AlignCenter, "No cue timeline")
            return

        painter.setPen(QColor("#9ba8a1"))
        painter.drawText(
            rect.left(),
            rect.bottom() + 14,
            "0:00",
        )
        painter.drawText(
            rect.right() - 44,
            rect.bottom() + 14,
            self._format_duration(self._duration),
        )

        if self._waveform_peaks:
            wave_pen = QPen(QColor("#4d8f74"))
            wave_pen.setWidth(1)
            painter.setPen(wave_pen)
            peak_count = max(1, len(self._waveform_peaks) - 1)
            for index, peak in enumerate(self._waveform_peaks):
                if peak <= 0:
                    continue
                x = rect.left() + int((index / peak_count) * rect.width())
                half_height = max(1, int(peak * rect.height() * 0.42))
                painter.drawLine(
                    x, baseline_y - half_height, x, baseline_y + half_height
                )

        if not self._markers:
            painter.setPen(QColor("#9ba8a1"))
            painter.drawText(rect, Qt.AlignCenter, "No labeled cue points")
            return

        for cue_id, time_s, label in self._markers:
            x = rect.left() + int((time_s / self._duration) * rect.width())
            selected = cue_id == self._selected_id
            label = label if len(label) <= 22 else f"{label[:19]}..."
            marker_pen = QPen(QColor("#e05b4f" if selected else "#f0b84b"))
            marker_pen.setWidth(3 if selected else 2)
            painter.setPen(marker_pen)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            if selected:
                painter.setPen(QColor("#e6ece8"))
                label_rect = rect.adjusted(6, 0, -6, 0)
                label_rect.setLeft(min(x + 5, rect.right() - 120))
                painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignTop, label)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds for the compact cue overview axis."""
        total_seconds = max(0, int(round(seconds)))
        minutes, secs = divmod(total_seconds, 60)
        return f"{minutes}:{secs:02d}"


logger = logging.getLogger(__name__)


# Configuration
CONFIG_FILE = "user_config.json"
DEFAULT_LINE_WIDTH = 0.8
MAX_RECENT_FILES = 10


def downsample_min_max(
    data: np.ndarray, sr: int, x_min: float, x_max: float, width_pixels: int
) -> tuple[np.ndarray, np.ndarray]:
    """Downsample audio data using min-max algorithm to reduce aliasing artifacts.

    Performs intelligent downsampling of audio data for efficient waveform visualization
    by calculating minimum and maximum values within pixel-aligned blocks. Uses slight
    overlap between blocks to ensure smooth transitions and reduce visual artifacts.

    Args:
        data: Audio data array to downsample.
        sr: Sample rate of the audio data in Hz.
        x_min: Start time position in seconds for the visible range.
        x_max: End time position in seconds for the visible range.
        width_pixels: Target width in pixels for the downsampled output.

    Returns:
        Tuple[np.ndarray, np.ndarray]: Two arrays containing:
            - x_plot: Time positions for plotting (interleaved for min/max pairs)
            - y_plot: Amplitude values (interleaved min/max for proper waveform rendering)

    Note:
        The function ensures at least 2 samples per pixel for smooth visualization
        and applies block overlap to prevent temporal artifacts. Returns empty arrays
        if the input segment is empty or invalid.
    """
    start_sample = int(x_min * sr)
    end_sample = int(x_max * sr)
    start_sample = max(start_sample, 0)
    end_sample = min(end_sample, len(data))
    segment = data[start_sample:end_sample]
    if len(segment) == 0:
        return np.array([]), np.array([])

    # Ensure at least two samples per pixel for smoother curves
    samples_per_pixel = max(2, int(len(segment) / width_pixels))

    # Use slight overlap between blocks for smoother transitions
    min_vals = []
    max_vals = []

    for i in range(0, len(segment), samples_per_pixel):
        # Apply a small overlap for smoother transitions
        block_start = max(0, i - 1)
        block_end = min(len(segment), i + samples_per_pixel + 1)
        block = segment[block_start:block_end]

        if len(block) > 0:
            min_vals.append(block.min())
            max_vals.append(block.max())

    if not min_vals:
        return np.array([]), np.array([])

    min_vals = np.array(min_vals)
    max_vals = np.array(max_vals)
    x_vals = np.linspace(x_min, x_max, len(min_vals))

    # Interleave min/max values for proper waveform rendering
    x_plot = np.empty((len(min_vals) * 2,), dtype=float)
    y_plot = np.empty((len(min_vals) * 2,), dtype=float)
    x_plot[0::2] = x_vals
    y_plot[0::2] = min_vals
    x_plot[1::2] = x_vals
    y_plot[1::2] = max_vals

    return x_plot, y_plot


class WavViewer(QWidget):
    """Manage WAV file analysis and visualization.

    This widget provides comprehensive audio analysis capabilities including: - Multi-
    channel waveform visualization with real-time zoom/pan - Metadata display (FMT,
    BEXT, INFO chunks, cue points) - Audio playback integration with visual cursor
    tracking - Tag management and batch editing capabilities - Professional field
    recording workflow optimization

    The widget follows the single responsibility principle, focusing purely on audio-
    related functionality. All other concerns (menus, exports, dialogs) are handled by
    specialized manager classes.

    Attributes:     filename (Optional[str]): Path to currently loaded WAV file
    current_data (Optional[np.ndarray]): Loaded audio data array     current_sr
    (Optional[int]): Sample rate of loaded audio     audio_duration (Optional[float]):
    Duration in seconds     user_config (dict[str, Any]): User configuration dictionary
    view_mode (str): Waveform display mode ('mono', 'per_kanaal', 'overlay') plot_colors
    (dict[str, str]): Color scheme for different plot elements

    Signals:     None - Uses Qt's standard widget signals

    Thread Safety:     This widget is not thread-safe and should only be used from the
    main GUI thread.
    """

    def __init__(self) -> None:
        """Initialize the WAV viewer widget.

        Sets up the complete user interface, loads user configuration, initializes audio
        components, and prepares for file loading.

        Raises:     RuntimeError: If audio components cannot be initialized     IOError:
        If user configuration cannot be loaded
        """
        super().__init__()
        logger.info("Initializing WavViewer with focused core functionality")

        # Load user configuration with error handling
        try:
            self.user_config = load_user_config()
        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.error(f"Failed to load user config: {exc}")
            self.user_config = self._get_default_config()

        # Initialize core state variables
        self._initialize_state_variables()

        # Initialize color scheme and styling
        self._initialize_color_scheme()

        # Setup complete user interface
        self._setup_ui()

        # Initialize audio components
        self._initialize_audio_components()

        # Load initial file data
        self._load_initial_data()

        logger.info("WavViewer initialization completed successfully")

    def _initialize_state_variables(self) -> None:
        """Initialize all instance state variables to their default values.

        Sets up the complete state management system for the WAV viewer including:
        - Audio file properties (filename, data, sample rate, duration)
        - Playback and visualization state (cursor lines, synchronization flags)
        - Cue point management (markers, labels, selection state)
        - UI interaction flags (connection states, handler setup status)
        - View configuration (display mode, styling, mouse interaction settings)

        Note:
            This method is called during initialization and establishes the
            foundation for all subsequent audio analysis and visualization operations.
        """
        # Audio file state
        self.filename: str | None = None
        self.current_data: np.ndarray | None = None
        self.current_sr: int | None = None
        self.audio_duration: float | None = None
        self.cached_mean_signal: np.ndarray | None = None

        # Playback and visualization state
        self.playback_line: list[pg.InfiniteLine] | None = None
        # self.playback_line = []
        self.syncing: bool = False

        # Cue point management
        self.cue_lines: dict[str, list[pg.PlotDataItem]] = {}
        self.selected_cue_line: pg.PlotDataItem | None = None
        self.selected_cue_id: str | None = None
        self.cue_labels: dict[str, str] = {}
        self.cue_markers: dict[str, Any] = {}
        self.current_cue_points: list[dict[str, Any]] = []

        # AI detection overlay is managed by self._ai_overlay
        # (AiOverlayController), constructed in _setup_ui() once the
        # waveform plots and toggle layout exist.

        # UI state flags
        self._sync_connected: bool = False
        self._hover_connected: bool = False
        self._click_handlers_setup: bool = False
        self._snap_to_cues: bool = False
        self._time_display_mode: str = "time"
        self._amplitude_display_mode: str = "dbfs"

        # View configuration
        self.view_mode: str = "per_kanaal"
        # self.view_mode = "mono"

        self.line_width_default: float = DEFAULT_LINE_WIDTH

        self.mouse_label_config = {
            "show_timecode": True,  # Show HH:MM:SS format
            "show_remaining_time": True,  # Show time remaining
            "show_percentage": True,  # Show amplitude as percentage
            "show_peak_detection": True,  # Analyze local peaks
            "show_channel_correlation": True,  # Show L/R correlation
            "show_frequency_analysis": False,  # CPU intensive - disabled by default
            "show_cue_proximity": True,  # Show nearby cue points
            "show_clipping_detection": True,  # Show if in clipping region
            "decimal_precision": 3,  # Decimal places for time
            "db_precision": 1,  # Decimal places for dB values
        }

    def _initialize_color_scheme(self) -> None:
        """Initialize the complete color scheme for all plot elements.

        Establishes a comprehensive color palette for different visualization components:
        - Waveform colors for mono and stereo channel display
        - Label colors for text overlays and annotations
        - Clipping indicator colors for different clipping types (float/integer)
        - Cue point marker colors for different cue types (marks, peaks, defaults)

        Note:
            Colors are chosen for optimal visibility, accessibility, and professional
            appearance in field recording analysis workflows. Uses web-safe hex colors
            for consistent cross-platform rendering.
        """
        self.plot_colors: dict[str, str] = {
            # Waveform colors
            "mono_waveform": "#2ca02c",  # Green for mono
            "channel_1_waveform": "#d62728",  # Red for left channel
            "channel_2_waveform": "#1f77b4",  # Blue for right channel
            # Label colors
            "mono_waveform_label": "#7f7f7f",  # Gray for labels
            "channel_1_waveform_label": "#7f7f7f",
            "channel_2_waveform_label": "#7f7f7f",
            # Clipping indicator colors
            # 'clip_float': '#7f7f7f',  # Gray for float clipping
            # 'clip_int': '#d62728',  # Red for integer clipping
            "clipping_float_start": "#FF0000",
            "clipping_float_end": "#32CD32",
            "clip_int_start": "#FF0000",
            "clip_int_end": "#32CD32",
            # Cue point colors
            "cue_mark": "#ff7f0e",  # Orange for markers
            "cue_peak": "#d62728",  # Red for peaks
            "cue_default": "#bcbd22",  # Olive for default
        }

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration when user config cannot be loaded.

        Provides a comprehensive fallback configuration containing safe default values
        for all application settings. Used when the user configuration file is missing,
        corrupted, or cannot be parsed.

        Returns:
            Dict[str, Any]: Complete default configuration dictionary containing:
                - wav_tags: Default INFO chunk metadata fields
                - paths: Default directory paths for file operations
                - view_settings: Default visualization preferences
                - All other application settings with sensible defaults

        Note:
            These defaults ensure the application remains functional even when
            user customizations are unavailable, providing a consistent baseline
            experience for new users.
        """
        return {
            "wav_tags": {
                "INAM": "Untitled Recording",
                "IART": "Unknown Artist",
                "ICRD": "",
                "ISFT": "FieldRecording",
                "IENG": "",
                "ICMT": "",
            },
            "paths": {
                "fieldrecording_dir": "FieldRecordings",
                "ableton_export_dir": "Ableton",
            },
        }

    def _setup_ui(self) -> None:
        """Set up the complete user interface layout and components.

        Creates and configures all UI widgets, layouts, and connections for the WAV viewer.
        The interface is organized into three main panels:
        - Left panel: File list and navigation
        - Center panel: Metadata tables and controls
        - Right panel: Waveform visualization plots

        This method coordinates the setup by calling specialized setup methods for
        each major UI component, ensuring proper initialization order and dependencies.

        Note:
            This method is broken down into logical sections for maintainability
            and clear separation of concerns. Each subsection handles a specific
            aspect of the user interface.
        """
        logger.debug("Setting up WAV viewer user interface")

        # Create main layout
        self._create_main_layout()

        # Setup file list widget
        self._setup_file_list()

        # Setup waveform plots
        self._setup_waveform_plots()

        # AI detection overlay controller (owns overlay items + toggles)
        self._ai_overlay = AiOverlayController(
            plots=[self.waveform_plot, self.waveform_plot_top, self.waveform_plot_bottom],
            label_plot=self.waveform_plot,
            toggle_layout=self._ai_toggle_layout,
        )

        # Setup metadata tables
        self._setup_metadata_tables()

        # Setup tag input system
        self._setup_tag_input()

        # Setup view mode controls
        self._setup_view_controls()

        logger.debug("UI setup completed")

    def _create_main_layout(self) -> None:
        """Create the Field Lab shell: sidebar | waveform workspace | inspector.

        Phase 1 keeps the existing widgets and data flow intact, but changes the
        visual ownership: metadata moves to a right inspector, while waveform,
        cue points, and transport become the central workspace.
        """
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_layout.addWidget(self.main_splitter)

        # 1. LEFT SIDEBAR: recordings, tags, templates, view mode
        self.left_panel = QFrame()
        self.left_panel.setFrameShape(QFrame.StyledPanel)
        self.left_panel.setObjectName("recording_sidebar")
        self.left_panel.setMinimumWidth(260)
        self.left_panel.setMaximumWidth(340)

        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(8, 8, 8, 8)
        self.left_layout.setSpacing(8)

        # 2. CENTER WORKSPACE: waveform, cue points, transport
        self.central_panel = QFrame()
        self.central_panel.setFrameShape(QFrame.StyledPanel)
        self.central_panel.setObjectName("waveform_workspace")

        self.central_layout = QVBoxLayout(self.central_panel)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        self.waveform_panel = QFrame()
        self.waveform_panel.setObjectName("waveform_panel")
        self.waveform_layout = QVBoxLayout(self.waveform_panel)
        self.waveform_layout.setContentsMargins(8, 8, 8, 6)
        self.waveform_layout.setSpacing(6)
        self.central_layout.addWidget(self.waveform_panel, stretch=7)

        self.cue_panel = QFrame()
        self.cue_panel.setObjectName("cue_panel")
        self.cue_layout = QVBoxLayout(self.cue_panel)
        self.cue_layout.setContentsMargins(8, 6, 8, 6)
        self.cue_layout.setSpacing(4)
        self.central_layout.addWidget(self.cue_panel, stretch=2)

        self.transport_panel = QFrame()
        self.transport_panel.setObjectName("transport_bar")
        self.transport_layout = QVBoxLayout(self.transport_panel)
        self.transport_layout.setContentsMargins(8, 4, 8, 6)
        self.transport_layout.setSpacing(0)
        self.central_layout.addWidget(self.transport_panel, stretch=0)

        # Compatibility layout aliases used by existing setup helpers.
        self.central_top_layout = self.waveform_layout
        self.central_bottom_layout = self.cue_layout
        self.central_controls_layout = QHBoxLayout()

        # 3. RIGHT INSPECTOR: metadata, audio format, location, info/photo
        self.right_panel = QFrame()
        self.right_panel.setFrameShape(QFrame.StyledPanel)
        self.right_panel.setObjectName("inspector_panel")
        self.right_panel.setMinimumWidth(260)
        self.right_panel.setMaximumWidth(360)

        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(8, 8, 8, 8)
        self.right_layout.setSpacing(8)

        inspector_header_row = QHBoxLayout()
        inspector_header_row.setContentsMargins(0, 0, 0, 0)
        inspector_header_row.setSpacing(6)

        inspector_header = QLabel("INSPECTOR")
        inspector_header.setObjectName("inspector_header")
        inspector_header_row.addWidget(inspector_header, stretch=1)

        self.inspector_settings_button = QPushButton()
        self.inspector_settings_button.setObjectName("inspector_settings_button")
        self.inspector_settings_button.setIcon(UiIconFactory.icon("settings"))
        self.inspector_settings_button.setIconSize(QSize(14, 14))
        self.inspector_settings_button.setToolTip("Collapse or expand inspector sections")
        self.inspector_settings_button.clicked.connect(self._toggle_all_inspector_sections)
        inspector_header_row.addWidget(self.inspector_settings_button)
        self.right_layout.addLayout(inspector_header_row)

        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.inspector_content = QWidget()
        self.inspector_layout = QVBoxLayout(self.inspector_content)
        self.inspector_layout.setContentsMargins(0, 0, 0, 0)
        self.inspector_layout.setSpacing(8)
        self.inspector_scroll.setWidget(self.inspector_content)
        self.right_layout.addWidget(self.inspector_scroll, stretch=1)

        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.central_panel)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([310, 1100, 300])

    def _setup_file_list(self) -> None:
        """Set up the file list widget for WAV file selection and navigation.

        Creates a styled list widget that displays available WAV files from the
        configured directory. The widget supports:
        - Single selection mode for focused file analysis
        - Automatic connection to waveform plotting functionality
        - Visual styling for professional appearance
        - Integration with file loading and analysis workflow

        The list widget is added to the left panel and automatically populates
        when WAV files are loaded into the application.

        Note:
            Selection changes trigger immediate waveform analysis and display
            updates for the selected file.
        """
        self._recording_sort_descending = False
        self._recording_details_visible = True

        # File list header with settings action
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.file_list_label = QLabel("RECORDINGS")
        self.file_list_label.setObjectName("sidebar_section_header")
        self.file_list_label.setToolTip("")
        header_row.addWidget(self.file_list_label, stretch=1)

        self.recording_settings_button = QPushButton()
        self.recording_settings_button.setObjectName("recording_settings_button")
        self.recording_settings_button.setIcon(UiIconFactory.icon("settings"))
        self.recording_settings_button.setIconSize(QSize(14, 14))
        self.recording_settings_button.setToolTip(
            "Toggle recording duration/date details"
        )
        self.recording_settings_button.clicked.connect(self._toggle_recording_details)
        header_row.addWidget(self.recording_settings_button)
        self.left_layout.addLayout(header_row)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(6)

        self.file_search_input = QLineEdit()
        self.file_search_input.setObjectName("recording_search")
        self.file_search_input.setPlaceholderText("Search recordings...")
        search_icon = QAction(self._make_search_icon(), "Search", self.file_search_input)
        self.file_search_input.addAction(search_icon, QLineEdit.LeadingPosition)
        self.file_search_input.textChanged.connect(self._filter_file_list)
        search_row.addWidget(self.file_search_input, stretch=1)

        self.recording_filter_button = QPushButton()
        self.recording_filter_button.setObjectName("recording_filter_button")
        self.recording_filter_button.setIcon(self._make_funnel_icon())
        self.recording_filter_button.setToolTip("Focus or clear recording filter")
        self.recording_filter_button.clicked.connect(self._toggle_recording_filter)
        search_row.addWidget(self.recording_filter_button)

        self.recording_sort_button = QPushButton()
        self.recording_sort_button.setObjectName("recording_sort_button")
        self.recording_sort_button.setIcon(self._make_sort_icon())
        self.recording_sort_button.setToolTip("Toggle recording sort order")
        self.recording_sort_button.clicked.connect(self._toggle_recording_sort)
        search_row.addWidget(self.recording_sort_button)
        self.left_layout.addLayout(search_row)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list.currentRowChanged.connect(self.plot_selected_wav)
        self.file_list.setUniformItemSizes(True)
        self.left_layout.addWidget(self.file_list)

        self.recording_count_label = QLabel("0 recordings")
        self.recording_count_label.setObjectName("recording_count_label")
        self.recording_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.left_layout.addWidget(self.recording_count_label)

    def _setup_waveform_plots(self) -> None:
        """Set up waveform plot widgets with optimized configuration.

        Creates three synchronized PyQtGraph plot widgets for comprehensive
        waveform visualization:
        - Main plot: Mono/overlay display for combined channel visualization
        - Top plot: Left channel isolated display
        - Bottom plot: Right channel isolated display

        Each plot is configured with:
        - White background for professional appearance
        - Antialiasing enabled for smooth waveform rendering
        - OpenGL disabled for maximum compatibility
        - Appropriate axis labels and stretch factors

        The plots are added to the right panel with proportional sizing
        to maximize available visualization space.

        Note:
            Plot synchronization is handled separately in the interaction
            setup methods to avoid circular dependencies during initialization.
        """
        # Waveform plots label + dynamic AI overlay toggles
        header_row = QHBoxLayout()
        plots_label = QLabel("WAVEFORM VIEW")
        plots_label.setObjectName("waveform_header")
        header_row.addWidget(plots_label)

        self.waveform_toolbar_controls = QHBoxLayout()
        self.waveform_toolbar_controls.setSpacing(6)

        self.waveform_mode_buttons: dict[str, QPushButton] = {}
        for mode, icon_name, tooltip in (
            ("mono", "waveform", "Mono waveform view"),
            ("per_kanaal", "stereo", "Stereo lane view"),
            ("overlay", "overlay", "Overlay waveform view"),
        ):
            button = QPushButton()
            button.setObjectName("waveform_mode_button")
            button.setIcon(UiIconFactory.icon(icon_name))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, m=mode: self._set_toolbar_view_mode(m))
            self.waveform_mode_buttons[mode] = button
            self.waveform_toolbar_controls.addWidget(button)

        self.time_mode_combo = QComboBox()
        self.time_mode_combo.setObjectName("waveform_toolbar_combo")
        self.time_mode_combo.addItems(["Time", "Timecode"])
        self.time_mode_combo.currentTextChanged.connect(self._set_time_display_mode)
        self.waveform_toolbar_controls.addWidget(self.time_mode_combo)

        self.snap_button = QPushButton("Snap: Off")
        self.snap_button.setObjectName("waveform_toolbar_button")
        self.snap_button.setCheckable(True)
        self.snap_button.setToolTip("Toggle cue snap state")
        self.snap_button.toggled.connect(self._set_snap_to_cues)
        self.waveform_toolbar_controls.addWidget(self.snap_button)

        self.amplitude_mode_combo = QComboBox()
        self.amplitude_mode_combo.setObjectName("waveform_toolbar_combo")
        self.amplitude_mode_combo.addItems(["dBFS", "Linear"])
        self.amplitude_mode_combo.currentTextChanged.connect(self._set_amplitude_display_mode)
        self.waveform_toolbar_controls.addWidget(self.amplitude_mode_combo)

        self.waveform_settings_button = QPushButton()
        self.waveform_settings_button.setObjectName("waveform_settings_button")
        self.waveform_settings_button.setIcon(UiIconFactory.icon("settings"))
        self.waveform_settings_button.setIconSize(QSize(14, 14))
        self.waveform_settings_button.setToolTip("Waveform display settings")
        self.waveform_settings_button.clicked.connect(self._focus_waveform_workspace)
        self.waveform_toolbar_controls.addWidget(self.waveform_settings_button)
        header_row.addLayout(self.waveform_toolbar_controls)
        header_row.addStretch()

        # Checkboxes are built dynamically when a layer is loaded
        self._ai_toggle_layout = QHBoxLayout()
        self._ai_toggle_layout.setSpacing(8)
        header_row.addLayout(self._ai_toggle_layout)

        self.waveform_layout.addLayout(header_row)

        # Create plot widgets with optimized settings
        # plot_config = {
        #     "background": "w",
        #     "antialias": True,
        #     "useOpenGL": False,  # Disable for better compatibility
        # }
        plot_config = {
            "background": ApplicationStylist.COLORS['plot_background'],
            "antialias": True,
            "useOpenGL": False,
        }

        # Main mono/overlay plot
        self.waveform_plot = pg.PlotWidget(
            axisItems={
                "bottom": MinuteSecondAxis("bottom"),
                "top": MinuteSecondAxis("top"),
            },
            **plot_config,
        )
        self.waveform_plot.setLabel("left", "Amplitude")
        self.waveform_plot.setLabel("bottom", "Time (s)")
        self.waveform_plot.getPlotItem().showAxis("top", True)
        self.waveform_plot.getPlotItem().setLabel("top", "Time")
        # self.waveform_plot.setMinimumHeight(120)
        self.waveform_layout.addWidget(self.waveform_plot, stretch=50)

        # Channel 1 (left) plot
        self.waveform_plot_top = pg.PlotWidget(
            axisItems={"bottom": MinuteSecondAxis("bottom")},
            **plot_config,
        )
        self.waveform_plot_top.setLabel("left", "Left Ch")
        # self.waveform_plot_top.setMinimumHeight(100)
        self.waveform_layout.addWidget(self.waveform_plot_top, stretch=50)

        # Channel 2 (right) plot
        self.waveform_plot_bottom = pg.PlotWidget(
            axisItems={"bottom": MinuteSecondAxis("bottom")},
            **plot_config,
        )
        self.waveform_plot_bottom.setLabel("left", "Right Ch")
        self.waveform_plot_bottom.setLabel("bottom", "Time (s)")
        # self.waveform_plot_bottom.setMinimumHeight(100)

        self.waveform_layout.addWidget(self.waveform_plot_bottom, stretch=50)
        self.apply_waveform_plot_theme()
        self._update_toolbar_mode_buttons()

        # self.waveform_plot.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)
        # self.waveform_plot_top.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)
        # self.waveform_plot_bottom.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)

    def apply_waveform_plot_theme(self, bg_color: QColor | str | None = None) -> None:
        """Apply theme-aware visual styling to all waveform plot widgets."""
        background = bg_color or ApplicationStylist.COLORS["plot_background"]
        axis_pen = pg.mkPen(ApplicationStylist.COLORS["divider"], width=1)
        grid_pen = pg.mkPen(ApplicationStylist.COLORS["border"], width=1)
        text_pen = pg.mkPen(ApplicationStylist.COLORS["text_muted"], width=1)
        tick_font = QFont()
        tick_font.setPointSize(8)
        label_font = QFont()
        label_font.setPointSize(9)
        label_font.setWeight(QFont.Medium)

        for plot in (
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ):
            plot.setBackground(background)
            plot.showGrid(x=True, y=True, alpha=0.22)
            plot.getViewBox().setBackgroundColor(background)

            plot_item = plot.getPlotItem()
            plot_item.getViewBox().setBorder(grid_pen)
            for axis_name in ("left", "bottom"):
                axis = plot_item.getAxis(axis_name)
                axis.setPen(axis_pen)
                axis.setTextPen(text_pen)
                axis.setTickFont(tick_font)
                axis.setStyle(tickTextOffset=6)
                axis.label.setFont(label_font)
                axis.label.setDefaultTextColor(
                    QColor(ApplicationStylist.COLORS["text_muted"])
                )
            top_axis = plot_item.getAxis("top")
            if top_axis:
                top_axis.setPen(axis_pen)
                top_axis.setTextPen(text_pen)
                top_axis.setTickFont(tick_font)
                top_axis.setStyle(tickTextOffset=6)
                top_axis.label.setFont(label_font)
                top_axis.label.setDefaultTextColor(
                    QColor(ApplicationStylist.COLORS["text_muted"])
                )

    def _set_toolbar_view_mode(self, mode: str) -> None:
        """Apply a waveform view mode from the mockup toolbar controls."""
        self.set_view_mode(mode)
        self.sync_view_mode_controls(mode)
        self._update_toolbar_mode_buttons()

    def _update_toolbar_mode_buttons(self) -> None:
        """Reflect the active waveform mode in toolbar icon buttons."""
        for mode, button in getattr(self, "waveform_mode_buttons", {}).items():
            button.setProperty("active", mode == self.view_mode)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_time_display_mode(self, label: str) -> None:
        """Switch time display mode state and update axis labels."""
        self._time_display_mode = "timecode" if label == "Timecode" else "time"
        axis_label = "Timecode" if self._time_display_mode == "timecode" else "Time (s)"
        for plot in (self.waveform_plot, self.waveform_plot_top, self.waveform_plot_bottom):
            plot.setLabel("bottom", axis_label)
        self.waveform_plot.getPlotItem().setLabel("top", "Time")

    def _set_snap_to_cues(self, enabled: bool) -> None:
        """Store cue-snap state for toolbar parity and future click behavior."""
        self._snap_to_cues = enabled
        self.snap_button.setText("Snap: On" if enabled else "Snap: Off")

    def _set_amplitude_display_mode(self, label: str) -> None:
        """Switch amplitude display state and update lane labels."""
        self._amplitude_display_mode = "linear" if label == "Linear" else "dbfs"
        main_label = "Linear" if self._amplitude_display_mode == "linear" else "dBFS"
        self.waveform_plot.setLabel("left", main_label)

    def _focus_waveform_workspace(self) -> None:
        """Focus the waveform workspace from the toolbar settings action."""
        self.waveform_plot.setFocus(Qt.ShortcutFocusReason)

    def _setup_metadata_tables(self) -> None:
        """Set up comprehensive metadata display tables for WAV file information.

        Creates four specialized tables for displaying different types of metadata:
        - FMT table: Audio format information (sample rate, bit depth, channels)
        - BEXT table: Broadcast Wave extension metadata (BWF specification)
        - INFO table: LIST-INFO chunk metadata (title, artist, comments, etc.)
        - Cue table: Cue point information with navigation capabilities

        Each table is configured with:
        - Standardized two-column layout (Key/Value or specialized columns)
        - Alternating row colors for improved readability
        - Resizable columns with automatic content fitting
        - Professional styling for field recording workflows

        The cue table includes click handling for navigation to specific
        time positions within the audio file.

        Note:
            Tables are distributed between center and right panels based on
            their relevance to the current workflow and available space.
        """
        # FMT table
        self.fmt_label = QLabel("AUDIO")
        self.fmt_table = self._create_metadata_table(["Key", "Value"])

        # BEXT table
        self.bext_label = QLabel("METADATA")
        self.bext_table = self._create_metadata_table(["Key", "Value"])

        # INFO table
        self.info_label = QLabel("INFO CHUNK")
        self.info_table = self._create_metadata_table(["Key", "Value"])

        # GPS table (always 3 editable rows)
        self.gps_label = QLabel("LOCATION")
        self.gps_table = self._create_metadata_table(["Key", "Value"])
        # self.gps_table.setFixedHeight(90)


        # Cue points table
        self.cue_label = QLabel("Cue Points:")
        self.cue_label.setObjectName("cue_section_header")
        self.cue_add_button = QPushButton("+ Add Cue")
        self.cue_add_button.setObjectName("cue_add_button")
        self.cue_add_button.setToolTip("Add a session cue at the current playhead")
        self.cue_add_button.clicked.connect(self._add_session_cue_point)
        self.cue_menu_button = QPushButton()
        self.cue_menu_button.setObjectName("cue_menu_button")
        self.cue_menu_button.setIcon(UiIconFactory.icon("menu"))
        self.cue_menu_button.setIconSize(QSize(14, 14))
        self.cue_menu_button.setToolTip("Copy selected cue")
        self.cue_menu_button.clicked.connect(
            lambda: self._copy_selected_table_cell(self.cue_table)
        )
        self.cue_table = self._create_metadata_table(["ID", "Positie", "Label", "Notes"])
        self.cue_table.cellClicked.connect(self.highlight_cue_line)
        self.cue_table.setFixedHeight(200)

        self._metadata_presenter = MetadataPresenter(
            fmt_table=self.fmt_table,
            bext_table=self.bext_table,
            info_table=self.info_table,
            gps_table=self.gps_table,
            cue_table=self.cue_table,
        )

        self.inspector_sections: dict[str, QFrame] = {}
        self.inspector_section_toggles: dict[str, QPushButton] = {}
        self.inspector_section_tables: dict[str, QTableWidget] = {}
        self._add_inspector_section(self.bext_label, self.bext_table)
        self._add_inspector_section(self.fmt_label, self.fmt_table)
        self._add_inspector_section(self.gps_label, self.gps_table)
        self._add_inspector_section(self.info_label, self.info_table)

        # Photo preview (shown when WAV has a PHOTO_REF in iXML)
        self.photo_preview_label = QLabel("Photo:")
        self.photo_preview_label.setVisible(False)
        self.photo_preview_image = QLabel()
        self.photo_preview_image.setAlignment(Qt.AlignLeft)
        self.photo_preview_image.setVisible(False)
        self.inspector_layout.addWidget(self.photo_preview_label)
        self.inspector_layout.addWidget(self.photo_preview_image)
        self.inspector_layout.addStretch()

        self.cue_header_layout = QHBoxLayout()
        self.cue_header_layout.setContentsMargins(0, 0, 0, 0)
        self.cue_header_layout.setSpacing(6)
        self.cue_header_layout.addWidget(self.cue_label, stretch=1)
        self.cue_header_layout.addWidget(self.cue_add_button)
        self.cue_header_layout.addWidget(self.cue_menu_button)
        self.cue_layout.addLayout(self.cue_header_layout)
        self.cue_body_layout = QHBoxLayout()
        self.cue_body_layout.setContentsMargins(0, 0, 0, 0)
        self.cue_body_layout.setSpacing(8)
        self.cue_body_layout.addWidget(self.cue_table, stretch=3)
        self.cue_overview = CueOverviewWidget()
        self.cue_body_layout.addWidget(self.cue_overview, stretch=2)
        self.cue_layout.addLayout(self.cue_body_layout)

    def _create_metadata_table(self, headers: list[str]) -> QTableWidget:
        """Create a standardized metadata table widget with consistent styling.

        Args:
            headers: List of column header labels for the table.

        Returns:
            QTableWidget: Fully configured table widget with:
                - Professional appearance with alternating row colors
                - Resizable first column, stretchable last column
                - Hidden vertical headers for clean appearance
                - Row selection behavior for better user interaction
                - Minimum height to ensure visibility of content

        Note:
            This factory method ensures all metadata tables have consistent
            appearance and behavior throughout the application.
        """
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents  # kolom-index
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setShowGrid(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(24)
        copy_action = QAction("Copy selected cell", table)
        copy_action.triggered.connect(
            lambda checked=False, t=table: self._copy_selected_table_cell(t)
        )
        table.addAction(copy_action)
        table.setContextMenuPolicy(Qt.ActionsContextMenu)
        # table.setMaximumHeight(150)
        # table.setFixedHeight(200)
        # table.setMinimumHeight(175)
        table.setMinimumHeight(145)
        # table.setMaximumWidth(50)
        return table

    def _copy_selected_table_cell(self, table: QTableWidget) -> None:
        """Copy the selected table cell value to the clipboard."""
        item = table.currentItem()
        if item is None:
            return
        QApplication.clipboard().setText(item.text())

    def _add_inspector_section(self, label: QLabel, table: QTableWidget) -> None:
        """Add a titled metadata table to the right inspector."""
        section = QFrame()
        section.setObjectName("inspector_section")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)
        label.setVisible(False)
        section_button = QPushButton(f"v {label.text()}")
        section_button.setObjectName("inspector_section_toggle")
        section_button.setCheckable(True)
        section_button.setChecked(True)
        section_button.clicked.connect(
            lambda checked, b=section_button, t=table, title=label.text(): (
                self._toggle_inspector_section(b, t, title, checked)
            )
        )
        section_layout.addWidget(section_button)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        section_layout.addWidget(table)
        self.inspector_layout.addWidget(section)
        self.inspector_sections[label.text()] = section
        self.inspector_section_toggles[label.text()] = section_button
        self.inspector_section_tables[label.text()] = table

    def _toggle_inspector_section(
        self, button: QPushButton, table: QTableWidget, title: str, expanded: bool
    ) -> None:
        """Expand or collapse an inspector section."""
        table.setVisible(expanded)
        button.setText(f"{'v' if expanded else '>'} {title}")

    def _focus_inspector(self) -> None:
        """Focus the inspector scroll area from the header gear action."""
        self.inspector_scroll.setFocus(Qt.ShortcutFocusReason)

    def _toggle_all_inspector_sections(self) -> None:
        """Collapse all inspector sections, or expand all when already collapsed."""
        if not self.inspector_section_tables:
            return
        should_expand = all(
            table.isHidden() for table in self.inspector_section_tables.values()
        )
        for title, table in self.inspector_section_tables.items():
            button = self.inspector_section_toggles[title]
            button.setChecked(should_expand)
            self._toggle_inspector_section(button, table, title, should_expand)

    def _setup_tag_input(self) -> None:
        """Set up the tag input system with intelligent autocomplete functionality.

        Creates a comprehensive tagging interface including:
        - FileTagAutocomplete widget with category-based suggestions
        - Reset button to restore default INFO chunk metadata
        - Save button to write tags back to the WAV file
        - Professional workflow integration for field recording tagging

        The tagging system supports:
        - Real-time autocomplete suggestions based on predefined categories
        - Template-based tagging for consistent metadata application
        - Direct integration with WAV file INFO chunk editing
        - Batch tagging capabilities through connected dialogs

        All controls are added to the center panel's bottom section for
        easy access during the audio analysis workflow.

        Note:
            The tag input widget automatically loads existing tags from
            the currently selected WAV file and provides intelligent
            suggestions based on established field recording categories.
        """
        # Tag input section — placed in left panel, between file list and view controls
        tag_label = QLabel("Tags and Metadata:")
        tag_label.setObjectName("sidebar_section_header")
        self.left_layout.addWidget(tag_label)

        self.tagger_widget = FileTagAutocomplete()
        self.left_layout.addWidget(self.tagger_widget)

        tag_buttons_layout = QHBoxLayout()

        self.reset_tags_button = QPushButton("Reset")
        self.reset_tags_button.setObjectName("tag_reset_button")
        self.reset_tags_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.reset_tags_button.setToolTip("Reset tags to default")
        self.reset_tags_button.clicked.connect(self._reset_info_table_to_defaults)
        tag_buttons_layout.addWidget(self.reset_tags_button)

        self.save_tags_button = QPushButton("Save")
        self.save_tags_button.setObjectName("tag_save_button")
        self.save_tags_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.save_tags_button.setToolTip("Save tags to file")
        self.save_tags_button.clicked.connect(self.save_info_from_info_table_to_file)
        tag_buttons_layout.addWidget(self.save_tags_button)

        tag_buttons_layout.addStretch()
        self.left_layout.addLayout(tag_buttons_layout)

    def _setup_view_controls(self) -> None:
        """Set up view mode controls for waveform display configuration.

        Creates radio button controls for switching between three waveform
        visualization modes:
        - Mono: Single combined waveform showing mixed channels
        - Stereo: Separate displays for left and right channels (default)
        - Overlay: Both channels overlaid on the same plot for comparison

        The controls are organized using QButtonGroup for mutual exclusion
        and connected to the set_view_mode() method for immediate visualization
        updates. The stereo mode is selected by default as it provides the
        most detailed view for professional field recording analysis.

        Controls are positioned in the left panel for easy access without
        interfering with the main waveform visualization area.

        Note:
            View mode changes trigger immediate re-rendering of all waveform
            plots to reflect the selected visualization approach.
        """
        # View controls section
        view_label = QLabel("View Mode:")
        view_label.setObjectName("sidebar_section_header")
        self.left_layout.addWidget(view_label)

        # Create view mode controls
        view_layout = QHBoxLayout()

        self.view_group = QButtonGroup(self)

        # Mono view radio button
        self.mono_radio = QRadioButton("Mono")
        self.mono_radio.setObjectName("view_mode_option")
        self.mono_radio.clicked.connect(lambda: self.set_view_mode("mono"))
        self.view_group.addButton(self.mono_radio)
        view_layout.addWidget(self.mono_radio)

        # Stereo view radio button (default)
        self.stereo_radio = QRadioButton("Stereo")
        self.stereo_radio.setObjectName("view_mode_option")
        self.stereo_radio.setChecked(True)
        self.stereo_radio.clicked.connect(lambda: self.set_view_mode("per_kanaal"))
        self.view_group.addButton(self.stereo_radio)
        view_layout.addWidget(self.stereo_radio)

        # Overlay view radio button
        self.overlay_radio = QRadioButton("Overlay")
        self.overlay_radio.setObjectName("view_mode_option")
        self.overlay_radio.clicked.connect(lambda: self.set_view_mode("overlay"))
        self.view_group.addButton(self.overlay_radio)
        view_layout.addWidget(self.overlay_radio)

        view_layout.addStretch()
        self.left_layout.addLayout(view_layout)

    def _initialize_audio_components(self) -> None:
        """Initialize audio playback components with waveform synchronization.

        Sets up the AudioPlayer widget and establishes signal connections for
        synchronized playback tracking with waveform visualization:
        - Position change signals for cursor movement
        - State change signals for play/pause/stop indication
        - Integration with the right panel layout

        The audio player provides professional playback controls including:
        - Play/pause/stop functionality
        - Volume control with mute capability
        - Seek/scrub controls for precise positioning
        - Real-time position feedback for cursor synchronization

        Raises:
            RuntimeError: If audio components cannot be initialized due to
                         system audio issues or missing dependencies.

        Note:
            Audio initialization errors are logged but don't prevent the
            application from starting - visualization features remain available.
        """
        try:
            self.audio_player = AudioPlayer()

            # Connect audio player signals
            self.audio_player.positionChanged.connect(self.update_waveform_cursor)
            self.audio_player.stateChanged.connect(self.handle_playback_state)

            self.transport_controls_layout = QHBoxLayout()
            self.transport_controls_layout.setContentsMargins(0, 0, 0, 0)
            self.transport_controls_layout.setSpacing(6)
            self.transport_controls_layout.addWidget(self.audio_player, stretch=1)

            self.transport_zoom_fit_button = QPushButton()
            self.transport_zoom_fit_button.setObjectName("transport_zoom_button")
            self.transport_zoom_fit_button.setIcon(UiIconFactory.icon("zoom_fit"))
            self.transport_zoom_fit_button.setIconSize(QSize(14, 14))
            self.transport_zoom_fit_button.setToolTip("Fit waveform to window")
            self.transport_zoom_fit_button.clicked.connect(self._zoom_waveform_fit)
            self.transport_controls_layout.addWidget(self.transport_zoom_fit_button)

            self.transport_zoom_out_button = QPushButton()
            self.transport_zoom_out_button.setObjectName("transport_zoom_button")
            self.transport_zoom_out_button.setIcon(UiIconFactory.icon("minus"))
            self.transport_zoom_out_button.setIconSize(QSize(14, 14))
            self.transport_zoom_out_button.setToolTip("Zoom waveform out")
            self.transport_zoom_out_button.clicked.connect(self._zoom_waveform_out)
            self.transport_controls_layout.addWidget(self.transport_zoom_out_button)

            self.transport_zoom_in_button = QPushButton()
            self.transport_zoom_in_button.setObjectName("transport_zoom_button")
            self.transport_zoom_in_button.setIcon(UiIconFactory.icon("plus"))
            self.transport_zoom_in_button.setIconSize(QSize(14, 14))
            self.transport_zoom_in_button.setToolTip("Zoom waveform in")
            self.transport_zoom_in_button.clicked.connect(self._zoom_waveform_in)
            self.transport_controls_layout.addWidget(self.transport_zoom_in_button)

            self.transport_status_label = QLabel("No audio loaded")
            self.transport_status_label.setObjectName("transport_status_label")
            self.transport_controls_layout.addWidget(self.transport_status_label)

            self.transport_layout.addLayout(self.transport_controls_layout)
            logger.debug("Audio components initialized successfully")
        except Exception as exc:  # of specifieker dan Exception
            logger.error("Failed to initialize audio components: %s", exc)
            raise RuntimeError("Audio initialization failed") from exc

    def _load_initial_data(self) -> None:
        """Load initial WAV file data and populate the file list widget.

        Performs the initial loading sequence when the application starts:
        - Calls load_wav_files() to scan the configured directory
        - Populates the file list widget with available WAV files
        - Automatically selects the first file if any files are found
        - Handles initialization errors gracefully with logging

        This method is called during widget initialization to provide immediate
        access to available audio files. If no files are found or errors occur,
        the application remains functional but shows an empty file list.

        Note:
            Exceptions during initial loading are caught and logged but don't
            prevent the application from starting. Users can manually load
            files or configure directories through the interface.
        """
        try:
            self.load_wav_files()
            if self.file_list.count() > 0:
                self.file_list.setCurrentRow(0)
                logger.debug("Initial data loaded successfully")
        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.warning(f"Could not load initial data: {exc}")

    # ========== FILE MANAGEMENT METHODS ==========

    def load_wav_files(self, select_path: str | None = None) -> None:
        """Load and display WAV files from the configured directory.

        Scans the configured fieldrecording directory for WAV files and populates
        the file list widget. This method handles various scenarios:
        - Creates missing directories automatically
        - Filters files to show only WAV format audio files
        - Sorts files alphabetically for consistent ordering
        - Updates UI state based on file availability
        - Optionally selects a specific file after loading

        The method provides robust error handling for common issues like
        missing directories, permission problems, or empty directories.

        Args:
            select_path: Optional file path to automatically select after
                        loading completes. Used for maintaining selection
                        state after directory refreshes.

        Raises:
            OSError: If the directory cannot be created or accessed due to
                    permission issues or filesystem problems.

        Note:
            If no WAV files are found, the file list shows a "No WAV files found"
            message and is disabled until files become available.
        """
        logger.debug("Loading WAV files from directory")

        wav_dir = self.user_config["paths"]["fieldrecording_dir"]
        #     wav_dir = self.user_config["paths"]["fieldrecording_dir"]

        # Skip silently if directory doesn't exist yet (first run or misconfigured path).
        # The user will be prompted to open a directory via the first-run welcome dialog.
        if not os.path.exists(wav_dir):
            logger.debug("WAV directory does not exist, skipping load: %s", wav_dir)
            return

        # Clear existing file list
        self.file_list.clear()

        # Find all WAV files
        try:
            all_files = os.listdir(wav_dir)
            wav_files = sorted(
                [f for f in all_files if f.lower().endswith(".wav")],
                reverse=getattr(self, "_recording_sort_descending", False),
            )
        except OSError as exc:
            logger.error(f"Cannot read directory {wav_dir}: {exc}")
            wav_files = []

        # Keep the mockup header text stable; expose the real folder as tooltip.
        folder_name = os.path.basename(os.path.normpath(wav_dir))
        self.file_list_label.setText("RECORDINGS")
        self.file_list_label.setToolTip(f"{folder_name}: {wav_dir}")
        self._update_recording_count_label(len(wav_files))

        # Handle empty directory
        if not wav_files:
            self.file_list.addItem("No WAV files found")
            self.file_list.setEnabled(False)
            logger.info(f"No WAV files found in {wav_dir}")
            return

        # Populate file list
        for wav_file in wav_files:
            full_path = os.path.join(wav_dir, wav_file)
            duration_text = self._get_file_duration_text(full_path)
            date_text = self._get_file_modified_text(full_path)

            # Keep path data stable; visual text is rendered by RecordingListRow.
            item = QListWidgetItem("")
            item.setData(Qt.UserRole, full_path)
            item.setData(Qt.UserRole + 1, wav_file)
            item.setToolTip(full_path)
            item.setSizeHint(
                QSize(0, 34 if getattr(self, "_recording_details_visible", True) else 28)
            )
            self.file_list.addItem(item)
            self.file_list.setItemWidget(
                item, RecordingListRow(
                    wav_file,
                    duration_text,
                    date_text,
                    getattr(self, "_recording_details_visible", True),
                    self.file_list,
                )
            )

        self.file_list.setEnabled(True)

        # Select specific file if requested
        if select_path:
            self._select_file_by_path(select_path)
        else:
            self.file_list.setCurrentRow(0)

        logger.debug(f"Loaded {len(wav_files)} WAV files")

    @staticmethod
    def _format_duration_for_list(duration_seconds: float) -> str:
        """Format a WAV duration for compact recording-list display."""
        total_seconds = max(0, int(round(duration_seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _get_file_duration_text(self, full_path: str) -> str:
        """Return compact duration text for a file list row."""
        try:
            info = sf.info(full_path)
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not read duration for %s: %s", full_path, exc)
            return ""
        if not info.samplerate:
            return ""
        return self._format_duration_for_list(info.frames / info.samplerate)

    @staticmethod
    def _get_file_modified_text(full_path: str) -> str:
        """Return compact modified date/time text for a recording list row."""
        try:
            modified = datetime.fromtimestamp(os.path.getmtime(full_path))
        except OSError as exc:
            logger.debug("Could not read modified time for %s: %s", full_path, exc)
            return ""
        return modified.strftime("%d %b %Y %H:%M")

    @staticmethod
    def _make_search_icon(size: int = 16) -> QIcon:
        """Create a small magnifying-glass icon for the search input."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(ApplicationStylist.COLORS["text_secondary"]), 1)
        painter.setPen(pen)
        painter.drawEllipse(3, 3, 7, 7)
        painter.drawLine(9, 9, 13, 13)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _make_funnel_icon(size: int = 16) -> QIcon:
        """Create a small funnel icon for the recording filter button."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(ApplicationStylist.COLORS["text_secondary"]), 1))
        painter.setBrush(QColor(ApplicationStylist.COLORS["text_secondary"]))
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(3, 4),
                    QPoint(size - 3, 4),
                    QPoint(10, 9),
                    QPoint(10, 13),
                    QPoint(6, 13),
                    QPoint(6, 9),
                ]
            )
        )
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _make_sort_icon(size: int = 16) -> QIcon:
        """Create a compact sort/sync-style icon for recording order."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(ApplicationStylist.COLORS["text_secondary"]), 1)
        painter.setPen(pen)
        painter.drawLine(5, 3, 5, 12)
        painter.drawLine(5, 3, 2, 6)
        painter.drawLine(5, 3, 8, 6)
        painter.drawLine(11, 4, 11, 13)
        painter.drawLine(11, 13, 8, 10)
        painter.drawLine(11, 13, 14, 10)
        painter.end()
        return QIcon(pixmap)

    def _update_recording_count_label(self, count: int | None = None) -> None:
        """Update the recording-list footer count."""
        if count is None:
            count = sum(
                1
                for row in range(self.file_list.count())
                if self.file_list.item(row) and self.file_list.item(row).data(Qt.UserRole)
            )
        label = "recording" if count == 1 else "recordings"
        self.recording_count_label.setText(f"{count} {label}")

    def _focus_recording_search(self) -> None:
        """Focus the recording search field from the sidebar gear action."""
        self.file_search_input.setFocus(Qt.ShortcutFocusReason)

    def _toggle_recording_details(self) -> None:
        """Show or hide recording duration/date details in the file list."""
        self._recording_details_visible = not getattr(
            self, "_recording_details_visible", True
        )
        selected_path = self.get_selected_file_path()
        self.load_wav_files(select_path=selected_path)

    def _toggle_recording_filter(self) -> None:
        """Focus the active filter, or clear it when already filtering."""
        if self.file_search_input.text():
            self.file_search_input.clear()
        else:
            self._focus_recording_search()

    def _toggle_recording_sort(self) -> None:
        """Toggle recording sort direction and reload while preserving selection."""
        selected_path = self._get_selected_file_path()
        self._recording_sort_descending = not getattr(
            self, "_recording_sort_descending", False
        )
        self.load_wav_files(select_path=selected_path)

    def _get_selected_file_path(self) -> str | None:
        """Return the currently selected recording path, if any."""
        item = self.file_list.currentItem()
        if item is None:
            return None
        path = item.data(Qt.UserRole)
        return path if path else None

    def _filter_file_list(self, query: str) -> None:
        """Filter visible recording rows by filename."""
        needle = query.strip().lower()
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item is None:
                continue
            filename = item.data(Qt.UserRole + 1) or os.path.basename(
                item.data(Qt.UserRole) or ""
            )
            item.setHidden(bool(needle) and needle not in filename.lower())

    def _select_file_by_path(self, target_path: str) -> bool:
        """Select a specific file in the file list by matching its full path.

        Searches through the file list widget to find an item with the specified
        path stored in its UserRole data, then selects that item. This method is
        used to maintain file selection state after directory refreshes or when
        programmatically selecting specific files.

        Args:
            target_path: Complete file path to search for and select.
                        Must match exactly with the stored path data.

        Returns:
            bool: True if the file was found and successfully selected,
                  False if the file was not found in the current list.

        Note:
            This method performs a linear search through the file list, so
            performance is O(n) where n is the number of files. For large
            directories, consider optimizing with a path-to-index mapping.
        """
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item and item.data(Qt.UserRole) == target_path:
                self.file_list.setCurrentRow(i)
                return True
        return False

    def plot_selected_wav(self, index: int) -> None:
        """Plot the selected WAV file with comprehensive analysis and visualization.

        This is the main orchestration method for complete audio file analysis.
        It coordinates multiple subsystems to provide a comprehensive view of
        the selected audio file:

        1. Audio file loading and validation
        2. Waveform plot setup and configuration
        3. Signal connection for plot synchronization
        4. Waveform rendering with optimization
        5. Visual enhancement application (clipping, cues, etc.)
        6. Metadata extraction and display
        7. Interactive handler setup
        8. Audio playback initialization

        Args:
            index: Zero-based index of the selected file in the file list widget.
                   Must be a valid index with an associated file path.

        Note:
            This method implements comprehensive error handling to ensure the
            application remains stable even with corrupted files or system issues.
            Each major step is separated into specialized methods for maintainability.

            The method handles both mono and stereo files automatically and
            configures the visualization based on the detected audio format.
        """
        # Validate list state and selection
        if not self.file_list.isEnabled():
            return

        item = self.file_list.item(index)
        if item is None:
            logger.warning(f"No item found at index {index}")
            return

        # Get file path
        filename = item.data(Qt.UserRole)
        if not filename:
            logger.warning("No filename data in list item")
            return

        self.filename = filename
        logger.debug(f"Plotting WAV file: {os.path.basename(filename)}")

        try:
            # Load audio file with validation
            self._load_audio_file(filename)

            # Setup and configure plots
            self._setup_plot_visualization()

            # Connect synchronization signals
            self._connect_plot_signals()

            # Render waveforms
            self._render_waveforms()

            # Add visual enhancements
            self._add_visual_enhancements()

            # Process metadata and cue points
            self._process_file_metadata(filename)

            # Setup interaction handlers
            self._setup_interaction_handlers()

            # Initialize audio playback
            self._initialize_file_playback(filename)

            logger.debug(f"Successfully plotted {os.path.basename(filename)}")

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            self._handle_plot_error(filename, exc)

    def _load_audio_file(self, filename: str) -> None:
        """Load and validate audio file data for visualization and analysis.

        Performs comprehensive audio file loading with format detection and
        data preparation:
        - Reads audio file information (format, sample rate, channels)
        - Detects float vs integer sample formats for proper processing
        - Loads audio data with 2D array formatting for consistent handling
        - Calculates duration and caches mean signal for performance
        - Validates data integrity and format compatibility

        The method ensures consistent data structures regardless of the source
        file format (mono/stereo, different bit depths, sample rates).

        Args:
            filename: Complete file path to the WAV file to load.
                     Must be a valid, accessible audio file.

        Raises:
            RuntimeError: If the file cannot be loaded due to format issues,
                         corruption, access permissions, or insufficient memory.

        Note:
            Audio data is always loaded as a 2D array (frames x channels) for
            consistent processing. Mono files are converted to 2D format with
            a single channel. The mean signal is cached for performance during
            visualization operations.
        """
        # Get file information
        info = sf.info(filename)
        is_float = info.subtype.startswith("FLOAT")

        # Guard against loading files that would exhaust RAM.
        # soundfile normalises PCM to float64 (8 bytes/sample).
        estimated_mb = (info.frames * info.channels * 8) / (1024 ** 2)
        limit_mb = app_config.MAX_WAVEFORM_RAM_MB
        if estimated_mb > limit_mb:
            from PyQt5.QtWidgets import QMessageBox
            answer = QMessageBox.question(
                None,
                "Large File Warning",
                f"This file requires approximately {estimated_mb:.0f} MB of RAM to display "
                f"(limit: {limit_mb} MB).\n\nLoading it may slow down or crash the application.\n\n"
                "Load anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                raise RuntimeError(
                    f"File loading cancelled: estimated RAM usage {estimated_mb:.0f} MB "
                    f"exceeds limit of {limit_mb} MB."
                )

        # Load audio data
        data, sample_rate = sf.read(filename, always_2d=True)

        # Ensure stereo format for consistent processing
        if data.shape[1] > 2:
            data = data[:, :2]  # Take first two channels
        elif data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)  # Duplicate mono to stereo

        # Calculate derived values
        duration = len(data) / sample_rate

        # Store audio data and metadata
        self.current_data = data
        self.current_sr = sample_rate
        self.audio_duration = duration
        self.is_float_format = is_float
        self._update_transport_status(info)

        # Pre-calculate mono signal for performance
        self.cached_mean_signal = 0.5 * (data[:, 0] + data[:, 1])

        logger.debug(
            f"Loaded audio: {duration:.2f}s, {sample_rate}Hz, "
            f"{data.shape[1]} channels"
        )

    def _update_transport_status(self, info: Any | None = None) -> None:
        """Update the compact technical summary in the transport bar."""
        if not hasattr(self, "transport_status_label"):
            return
        if info is None or self.current_sr is None:
            self.transport_status_label.setText("No audio loaded")
            return

        format_text = getattr(info, "subtype", "") or "unknown"
        channels = getattr(info, "channels", None)
        sample_text = (
            f"{self.current_sr / 1000:g} kHz"
            if self.current_sr >= 1000
            else f"{self.current_sr} Hz"
        )
        channel_text = f"{channels}ch" if channels else ""
        text = " · ".join(
            part for part in [sample_text, format_text, channel_text] if part
        )
        self.transport_status_label.setText(text)
        self.transport_status_label.setToolTip(text)

    def _setup_plot_visualization(self) -> None:
        """Set up and clear all plots for new audio file visualization.

        Prepares the visualization environment for a new audio file by:
        - Clearing all existing plot items from all three plot widgets
        - Resetting cue point tracking and selection states
        - Configuring appropriate plot ranges based on the loaded audio data

        This method ensures a clean slate for each new file analysis,
        preventing visual artifacts or data from previous files from
        interfering with the current visualization.

        Note:
            Must be called after successful audio file loading but before
            waveform rendering to ensure proper plot initialization.
        """
        # Clear all existing plot items
        plots = [self.waveform_plot, self.waveform_plot_top, self.waveform_plot_bottom]

        for plot in plots:
            plot.clear()

        # Clear cue point tracking
        self.cue_lines.clear()
        self.selected_cue_line = None
        self.selected_cue_id = None
        self.cue_markers.clear()
        self.current_cue_points = []

        # Clear AI overlay
        self._clear_ai_overlay()

        # Configure plot ranges
        self._configure_plot_ranges()

    def _configure_plot_ranges(self) -> None:
        """Configure plot axis ranges and interaction limits based on loaded audio data.

        Calculates and applies optimal visualization ranges for all plot widgets:
        - X-axis: Time range from 0 to audio duration with zoom limits
        - Y-axis: Amplitude range with margins for visual clarity and clipping indicators
        - Mouse interaction: Horizontal scrolling/zooming only for time navigation
        - Auto-range: Disabled to maintain consistent manual control

        The method calculates intelligent margins and buffers:
        - 5% visual margin around peak amplitude for clarity
        - 15% extra buffer for clipping indicator visualization
        - Zoom limits prevent excessive zoom-in (0.2% minimum) or zoom-out (full duration)
        - Y-axis scaling with 10x zoom factors for amplitude analysis

        All three plot widgets (main, top channel, bottom channel) receive
        identical range configurations to ensure synchronized behavior.

        Note:
            Requires valid audio data to be loaded before calling. Falls back
            gracefully if no audio data is available.
        """
        if self.current_data is None or self.audio_duration is None:
            return
        data = self.current_data
        duration = self.audio_duration

        # --- Amplitude-berekening -------------------------------
        min_val, max_val = float(np.min(data)), float(np.max(data))
        peak_val = max(abs(min_val), abs(max_val))
        display_peak = max(peak_val, 1.0)  # fallback for very quiet signals
        margin = 0.05 * display_peak  # 5% visual margin
        clip_buffer = 0.15  # extra space for clip indicator
        y_min = -display_peak - margin - clip_buffer
        y_max = display_peak + margin + clip_buffer

        # --- Range & interactie-limieten -------------------------
        for plot in (
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ):
            vb = plot.getViewBox()
            vb.setMouseEnabled(x=True, y=False)  # alleen horizontaal scroll/zoom
            vb.enableAutoRange(x=False, y=False)  # handmatig bereik heeft voorrang

            vb.setLimits(
                # X-as
                xMin=0,
                xMax=duration,
                minXRange=duration / 500,  # niet verder inzoomen dan 0,2 %
                maxXRange=duration,  # niet verder uitzoomen dan volledige duur
                # Y-as
                yMin=y_min,
                yMax=y_max,
                minYRange=(y_max - y_min) / 10,  # zoom-min-factor 10×
                maxYRange=(y_max - y_min) * 10,  # zoom-max-factor 10×
            )
            vb.setXRange(0, duration, padding=0)
            vb.setYRange(y_min, y_max, padding=0)

        # return self._configure_plot_ranges1(self.current_data, self.audio_duration)

        # # Calculate amplitude ranges
        # data_max = np.abs(self.current_data).max()
        # y_margin = data_max * 0.1  # 10% margin
        # y_range = [-data_max - y_margin, data_max + y_margin]
        #
        # # Set X range (time) for all plots
        # x_range = [0, self.audio_duration]
        #
        # # Configure each plot
        # plots = [self.waveform_plot, self.waveform_plot_top,
        #          self.waveform_plot_bottom]
        #
        # for plot in plots:
        #     vb = plot.getViewBox()
        #     vb.setMouseEnabled(x=True, y=False)
        #     vb.enableAutoRange(x=False, y=False)
        #
        #     plot.setXRange(*x_range, padding=0)
        #     plot.setYRange(*y_range, padding=0)
        #
        #
        #     # Set axis limits to prevent excessive zooming
        #     plot.setLimits(xMin=0, xMax=self.audio_duration,
        #                    yMin=y_range[0], yMax=y_range[1])

    def _connect_plot_signals(self) -> None:
        """Connect plot synchronization signals for coordinated pan/zoom behavior.

        Establishes signal connections between the three plot widgets to ensure
        synchronized navigation behavior:
        - Main plot X-range changes sync to top and bottom channel plots
        - Top channel plot changes sync to main and bottom plots
        - Bottom channel plot changes sync to main and top plots

        Uses a connection guard to prevent duplicate signal connections during
        multiple file loads. The synchronization ensures that zooming or panning
        in any plot automatically updates all other plots to maintain temporal
        alignment across all visualization channels.

        Note:
            Signal connections are established only once per widget lifetime
            to prevent signal multiplication and potential performance issues.
            The _sync_connected flag tracks connection state.
        """
        if hasattr(self, "_sync_connected") and self._sync_connected:
            return

        # Connect X-range synchronization signals
        self.waveform_plot.getViewBox().sigXRangeChanged.connect(
            self._sync_x_range_from_main
        )
        self.waveform_plot_top.getViewBox().sigXRangeChanged.connect(
            self._sync_x_range_from_top
        )
        self.waveform_plot_bottom.getViewBox().sigXRangeChanged.connect(
            self._sync_x_range_from_bottom
        )

        self.waveform_plot.getViewBox().sigXRangeChanged.connect(
            self.update_plot_for_view_range
        )
        self.waveform_plot_top.getViewBox().sigXRangeChanged.connect(
            self.update_plot_for_view_range
        )
        self.waveform_plot_bottom.getViewBox().sigXRangeChanged.connect(
            self.update_plot_for_view_range
        )

        self.waveform_plot.getViewBox().sigXRangeChanged.connect(
            self._update_mouse_labels_position
        )
        self.waveform_plot_top.getViewBox().sigXRangeChanged.connect(
            self._update_mouse_labels_position
        )
        self.waveform_plot_bottom.getViewBox().sigXRangeChanged.connect(
            self._update_mouse_labels_position
        )

        self._sync_connected = True
        logger.debug("Plot synchronization signals connected")

    def _render_waveforms123(self) -> None:
        """Legacy waveform rendering method with optimized downsampling.

        Performs optimized rendering of audio waveforms across all plot widgets
        using intelligent downsampling for efficient display at different zoom levels.
        This method renders three specific visualizations:
        - Main plot: Mono/averaged signal from both channels
        - Top plot: Left channel (channel 0) isolated waveform
        - Bottom plot: Right channel (channel 1) isolated waveform

        The rendering process uses cached mean signal for performance and applies
        appropriate color schemes for visual distinction between channels.

        Note:
            This is a legacy method maintained for compatibility. The current
            implementation uses _render_waveforms() which provides more flexible
            view mode support and better performance optimizations.
        """
        if (
            self.current_data is None
            or self.current_sr is None
            or self.audio_duration is None
        ):
            return

        # Get current view ranges for each plot
        plots_info = [
            (self.waveform_plot, self.cached_mean_signal, "mono_waveform"),
            (self.waveform_plot_top, self.current_data[:, 0], "channel_1_waveform"),
            (self.waveform_plot_bottom, self.current_data[:, 1], "channel_2_waveform"),
        ]

        # Render each plot with appropriate data
        for plot, data, color_key in plots_info:
            self._render_single_plot(plot, data, color_key)

    def _render_waveforms(self) -> None:
        """Render waveforms based on current view mode with optimized performance.

        Performs intelligent waveform rendering that adapts to the selected view mode:
        - Mono mode: Single averaged waveform in main plot only
        - Per-channel mode: Mono average plus separate left/right channel plots
        - Overlay mode: Both channels overlaid in main plot for comparison

        The method implements performance optimizations:
        - Cleans up previous plot items to prevent memory leaks
        - Uses cached view configuration for consistent rendering
        - Preserves persistent markers (cue points, cursors) during updates
        - Applies appropriate color schemes for channel identification

        Each rendering pass removes old waveform data while preserving user
        interface elements like cue markers and playback cursors.

        Note:
            Requires valid audio data to be loaded. Falls back gracefully
            if audio data is unavailable or incomplete.
        """
        if (
            self.current_data is None
            or self.current_sr is None
            or self.audio_duration is None
        ):
            return

        plots_info = self._get_view_config()

        for plot in [
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ]:
            for item in list(plot.listDataItems()):
                # Remove items that are not part of the persistent markers
                if isinstance(item, pg.PlotDataItem) and not hasattr(item, "plot_ref"):
                    plot.removeItem(item)

        for plot, data, color_key in plots_info:
            self._render_single_plot(plot, data, color_key)

    def _get_view_config(self):
        """Get plot configuration tuples based on current view mode setting.

        Returns appropriate plot configuration for the selected visualization mode:
        - 'mono': Single plot with averaged mono signal
        - 'per_kanaal': Three plots (mono average, left channel, right channel)
        - 'overlay': Both channels overlaid in main plot for direct comparison

        Returns:
            List[Tuple]: List of (plot_widget, data_array, color_key) tuples
                        where each tuple defines:
                        - plot_widget: PyQtGraph PlotWidget to render on
                        - data_array: NumPy array containing waveform data
                        - color_key: String key for color scheme lookup

        Note:
            The configuration determines which plots are active and what data
            they display. This allows for flexible visualization modes without
            duplicating rendering logic.
        """
        if self.view_mode == "mono":
            return [
                (self.waveform_plot, self.cached_mean_signal, "mono_waveform"),
            ]
        elif self.view_mode == "per_kanaal":
            # Render mono plus left and right channels
            return [
                (self.waveform_plot, self.cached_mean_signal, "mono_waveform"),
                (self.waveform_plot_top, self.current_data[:, 0], "channel_1_waveform"),
                (
                    self.waveform_plot_bottom,
                    self.current_data[:, 1],
                    "channel_2_waveform",
                ),
            ]
        elif self.view_mode == "overlay":
            # Render only the left and right channels in the main plot
            return [
                (self.waveform_plot, self.current_data[:, 0], "channel_1_waveform"),
                (self.waveform_plot, self.current_data[:, 1], "channel_2_waveform"),
            ]
        else:
            # Fallback to mono view for unknown modes
            return [
                (self.waveform_plot, self.cached_mean_signal, "mono_waveform"),
            ]

    def _render_single_plot(
        self, plot: pg.PlotWidget, data: np.ndarray, color_key: str
    ) -> None:
        """Render a single waveform plot with optimization and adaptive sampling.

        Performs intelligent waveform rendering with dynamic optimization based on:
        - Current zoom level and visible time span
        - Plot widget dimensions and pixel density
        - Audio data density in the visible range
        - Adaptive pixel allocation for detail preservation

        The method implements several performance optimizations:
        - Minimum 1200 pixel base resolution for quality
        - 2x oversampling for high-quality rendering
        - Adaptive pixel count increase when zoomed in deeply
        - Intelligent sampling ratio based on data density

        Args:
            plot: PyQtGraph PlotWidget to render the waveform on.
            data: NumPy array containing audio waveform data to visualize.
            color_key: String key for color lookup in the plot_colors scheme.

        Note:
            The adaptive sampling ensures optimal quality at all zoom levels
            while maintaining smooth performance. Deep zoom operations automatically
            increase detail resolution for precise audio analysis.
        """
        # Get current view range
        view_box = plot.getViewBox()
        x_range, _ = view_box.viewRange()

        # Use a minimum number of pixels to ensure adequate sampling
        # Increase pixel count when zoomed in for higher quality
        plot_width = max(1200, plot.width() * 2)

        # Ensure we have enough samples for smooth rendering
        time_span = x_range[1] - x_range[0]
        if time_span > 0:
            samples_in_view = int(time_span * self.current_sr)
            # When zoomed in deeply, use more pixels for detail
            if samples_in_view < plot_width * 4:
                plot_width = max(plot_width, samples_in_view // 2)

        # Downsample data for current view
        x_plot, y_plot = downsample_min_max(
            data, self.current_sr, x_range[0], x_range[1], plot_width
        )

        # Render if we have data
        if len(x_plot) > 0:
            pen = self.get_pen(color_key)
            plot.plot(x_plot, y_plot, pen=pen)

    def _add_visual_enhancements(self) -> None:
        """Add comprehensive visual enhancements for professional audio analysis.

        Analyzes the loaded audio data and adds various visual indicators to assist
        with quality assessment and professional field recording analysis:
        - Clipping detection indicators for both float and integer formats
        - Reference lines for standard audio levels (0dB, -6dB, etc.)
        - Channel-specific analysis for stereo recordings
        - Format-aware threshold detection

        The enhancements provide immediate visual feedback about potential audio
        issues, allowing for quick quality assessment without detailed inspection.
        All indicators are color-coded and positioned for minimal interference
        with waveform visualization.

        Note:
            Requires valid audio data and format detection to be completed.
            Falls back gracefully if format information is unavailable.
        """
        if not hasattr(self, "is_float_format"):
            return

        self._add_channel_specific_clipping_indicators(self.is_float_format)
        self._add_simple_reference_lines()

    def _add_channel_specific_clipping_indicators(self, is_float: bool) -> None:
        """Add intelligent clipping detection indicators for each audio channel.

        Performs comprehensive clipping analysis with channel-specific detection:
        - Float format: 0.99 threshold for near-clipping detection
        - Integer format: 0.95 threshold for conservative clipping detection
        - Separate analysis for left channel, right channel, and mono mix
        - Visual indicators adapted to current view mode (mono/stereo/overlay)

        The method implements enhanced visualization features:
        - Clears previous clipping visualizations to prevent overlap
        - Adds transparent background regions for clipping areas
        - Color-coded indicators (red for start, green for end of clipping)
        - Channel-specific placement based on active view mode

        Args:
            is_float: True if audio uses floating-point format, False for integer.
                     Determines appropriate clipping thresholds and detection sensitivity.

        Note:
            Clipping detection adapts to different audio formats and provides
            conservative thresholds to catch potential issues before they become
            audible distortion. Visual indicators are optimized for each view mode.
        """
        if self.current_data is None:
            return

        # Clear any existing clipping visualizations first
        if hasattr(self, "clear_clipping_visualizations"):
            self.clear_clipping_visualizations()

        # Rest of your existing logic stays the same...
        if is_float:
            clip_threshold = 0.99
            start_color = "clipping_float_start"
            end_color = "clipping_float_end"
        else:
            clip_threshold = 0.95
            start_color = "clip_int_start"
            end_color = "clip_int_end"

        # Analyze each channel separately
        left_channel = self.current_data[:, 0]
        right_channel = self.current_data[:, 1]
        mono_mix = self.cached_mean_signal

        # Find clipping samples per channel
        left_clipped = np.abs(left_channel) >= clip_threshold
        right_clipped = np.abs(right_channel) >= clip_threshold
        mono_clipped = np.abs(mono_mix) >= clip_threshold

        # Add clipping indicators based on view mode (existing logic)
        if hasattr(self, "view_mode"):
            if self.view_mode == "per_kanaal":
                if np.any(left_clipped):
                    self._draw_clipping_region_markers(
                        left_clipped,
                        start_color,
                        end_color,
                        [self.waveform_plot_top],
                        "Left Channel",
                    )

                if np.any(right_clipped):
                    self._draw_clipping_region_markers(
                        right_clipped,
                        start_color,
                        end_color,
                        [self.waveform_plot_bottom],
                        "Right Channel",
                    )

                if np.any(mono_clipped):
                    self._draw_clipping_region_markers(
                        mono_clipped,
                        start_color,
                        end_color,
                        [self.waveform_plot],
                        "Mono Mix",
                    )

            elif self.view_mode == "overlay":
                any_channel_clipped = left_clipped | right_clipped
                if np.any(any_channel_clipped):
                    self._draw_clipping_region_markers(
                        any_channel_clipped,
                        start_color,
                        end_color,
                        [self.waveform_plot_top, self.waveform_plot],
                        "Any Channel",
                    )
            elif np.any(mono_clipped):
                self._draw_clipping_region_markers(
                    mono_clipped,
                    start_color,
                    end_color,
                    [self.waveform_plot],
                    "Mono Mix",
                )

    def _add_simple_reference_lines(self) -> None:
        """Add reference lines at +1 and -1.

        Dotted gray for 32-bit float, solid black for integer.
        """
        if self.is_float_format:
            # 32-bit float: dotted gray
            pen = pg.mkPen(color=(150, 150, 150), width=2, style=QtCore.Qt.DotLine)
        else:
            # 16/24-bit integer: solid black
            pen = pg.mkPen(color=(0, 0, 0), width=2, style=QtCore.Qt.SolidLine)

        for plot in [
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ]:
            # +1 line
            plot.addItem(pg.InfiniteLine(pos=1.0, angle=0, pen=pen, movable=False))
            # -1 line
            plot.addItem(pg.InfiniteLine(pos=-1.0, angle=0, pen=pen, movable=False))

    def _draw_clipping_region_markers(
        self,
        clipped_samples: np.ndarray,
        start_color_key: str,
        end_color_key: str,
        target_plots: list,
        channel_name: str = "",
    ) -> None:
        """Draw clipping region markers with transparent background regions.

        ENHANCED VERSION: Now includes transparent regions between markers.
        """
        if self.current_sr is None:
            return

        # Find raw clipping regions
        raw_regions = self._find_raw_clipping_regions(clipped_samples)

        if not raw_regions:
            return

        # Merge nearby regions with gap tolerance
        merged_regions = self._merge_nearby_clipping_regions(
            raw_regions, gap_tolerance_ms=5.0, min_duration_ms=1.0
        )

        if not merged_regions:
            return

        # Log clipping detection summary
        total_clipped_samples = np.sum(clipped_samples)
        total_duration_ms = sum(
            (end - start) / self.current_sr * 1000 for start, end in merged_regions
        )

        logger.debug(
            f"Clipping detected in {channel_name}: "
            f"{len(merged_regions)} regions, "
            f"{total_clipped_samples} samples total, "
            f"{total_duration_ms:.1f}ms duration"
        )

        # Create pens for start and end markers
        start_pen = (
            self.get_pen(start_color_key, width=3)
            if hasattr(self, "get_pen")
            else pg.mkPen("green", width=3)
        )
        end_pen = (
            self.get_pen(end_color_key, width=3)
            if hasattr(self, "get_pen")
            else pg.mkPen("red", width=3)
        )

        # Draw markers AND background regions for each merged region
        for region_idx, (start_sample, end_sample) in enumerate(merged_regions):
            start_time = start_sample / self.current_sr
            end_time = end_sample / self.current_sr
            duration_ms = (end_sample - start_sample) / self.current_sr * 1000

            # Add markers and regions to specified plots only
            # for plot in target_plots:
            #     # Add transparent background region to show duration
            #     self._add_clipping_background_region(
            #         plot,
            #         start_time,
            #         end_time,
            #         region_idx,
            #         len(merged_regions),
            #         channel_name,
            #         duration_ms,
            #     )
            for plot in target_plots:
                # Add transparent background region to show duration
                region_info = ClippingRegionInfo(
                    start_time=start_time,
                    end_time=end_time,
                    region_idx=region_idx,
                    total_regions=len(merged_regions),
                    channel_name=channel_name,
                    duration_ms=duration_ms,
                )
                self._add_clipping_background_region(plot, region_info)

                # START marker (green line)
                start_line = pg.InfiniteLine(pos=start_time, angle=90, pen=start_pen)
                start_line.setToolTip(
                    f"CLIPPING START\n"
                    f"Channel: {channel_name}\n"
                    f"Time: {start_time:.3f}s\n"
                    f"Duration: {duration_ms:.1f}ms\n"
                    f"Region {region_idx + 1}/{len(merged_regions)}"
                )

                # END marker (red line)
                end_line = pg.InfiniteLine(pos=end_time, angle=90, pen=end_pen)
                end_line.setToolTip(
                    f"CLIPPING END\n"
                    f"Channel: {channel_name}\n"
                    f"Time: {end_time:.3f}s\n"
                    f"Duration: {duration_ms:.1f}ms\n"
                    f"Region {region_idx + 1}/{len(merged_regions)}"
                )

                # Set Z-values for proper layering
                start_line.setZValue(15)  # Markers on top
                end_line.setZValue(15)

                plot.addItem(start_line)
                plot.addItem(end_line)

    def clear_clipping_visualizations(self) -> None:
        """Clear all clipping visualizations from plots.

        Call this before adding new ones to prevent accumulation.
        """
        # Initialize if doesn't exist
        if not hasattr(self, "clipping_regions"):
            self.clipping_regions = []
            return

        # Clear existing regions
        for region in self.clipping_regions:
            try:
                if hasattr(region, "scene") and region.scene():
                    region.scene().removeItem(region)
            except (
                AttributeError,
                IndexError,
                KeyError,
                ValueError,
                TypeError,
                RuntimeError,
            ):
                pass  # Ignore errors during cleanup

        self.clipping_regions.clear()

    def _add_clipping_background_region(
        self,
        plot: pg.PlotWidget,
        region_info: ClippingRegionInfo,
    ) -> None:
        """Add a transparent background region to visualize clipping duration."""
        try:
            # Create brush for transparent red background
            clip_brush = pg.mkBrush(color=(255, 0, 0, 50))  # Red with 50/255 alpha

            # Create rectangular region using LinearRegionItem
            region = pg.LinearRegionItem(
                values=[region_info.start_time, region_info.end_time],
                orientation="vertical",
                brush=clip_brush,
                pen=None,  # No border
                movable=False,  # Don't allow user to move it
                bounds=[region_info.start_time, region_info.end_time],  # Lock bounds
            )

            # Set Z-value so it's behind waveform but above grid
            region.setZValue(-5)

            # Enhanced tooltip
            region.setToolTip(
                f"CLIPPING REGION\n"
                f"Channel: {region_info.channel_name}\n"
                f"Start: {region_info.start_time:.3f}s\n"
                f"End: {region_info.end_time:.3f}s\n"
                f"Duration: {region_info.duration_ms:.1f}ms\n"
                f"Region {region_info.region_idx + 1} of {region_info.total_regions}\n"
                f"\nTip: This area contains clipped audio samples\n"
                f"that may cause distortion or artifacts."
            )

            # Add to plot
            plot.addItem(region)

            # Store reference for later removal
            if not hasattr(self, "clipping_regions"):
                self.clipping_regions = []
            self.clipping_regions.append(region)

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.warning(f"Could not add clipping background region: {exc}")

    def _find_raw_clipping_regions(
        self, clipped_samples: np.ndarray
    ) -> list[tuple[int, int]]:
        """Find all raw clipping regions without merging.

        Thin wrapper delegating to the Qt-free analysis.clipping module.

        Args:     clipped_samples: Boolean array of clipped samples

        Returns: list of (start_sample, end_sample) tuples for raw clipping regions
        """
        return clipping_analysis.find_raw_clipping_regions(clipped_samples)

    def _merge_nearby_clipping_regions(
        self,
        regions: list[tuple[int, int]],
        gap_tolerance_ms: float = 5.0,
        min_duration_ms: float = 1.0,
    ) -> list[tuple[int, int]]:
        """Merge clipping regions that are close together.

        Thin wrapper delegating to the Qt-free analysis.clipping module.

        Args:     regions: list of (start_sample, end_sample) tuples gap_tolerance_ms:
        Maximum gap in milliseconds to bridge     min_duration_ms: Minimum duration in
        milliseconds to keep region

        Returns: list of merged clipping regions
        """
        return clipping_analysis.merge_nearby_clipping_regions(
            regions, self.current_sr, gap_tolerance_ms, min_duration_ms
        )

    def get_clipping_summary(self) -> dict:
        """Get a summary of clipping detection results.

        Collects the current audio state and delegates the pure
        calculation to the Qt-free analysis.clipping module.

        Returns:     Dictionary with clipping statistics per channel using merged
        regions
        """
        if self.current_data is None:
            return {}

        is_float = getattr(self, "is_float_format", True)

        return clipping_analysis.get_clipping_summary(
            left_channel=self.current_data[:, 0],
            right_channel=self.current_data[:, 1],
            mono_mix=self.cached_mean_signal,
            sample_rate=self.current_sr,
            is_float_format=is_float,
        )

    #######
    def _process_file_metadata(self, filename: str) -> None:
        """Start background analysis of WAV metadata.

        Launches a :class:`WavAnalysisWorker` thread.  Results are delivered to
        :meth:`_on_metadata_ready`; errors to :meth:`_on_metadata_error`.
        Any previously running worker for a different file is stopped first.

        Args:
            filename: Path to WAV file to analyse.
        """
        # Stop any in-flight worker so stale results don't overwrite new selection
        if hasattr(self, "_metadata_worker") and self._metadata_worker is not None:
            self._metadata_worker.finished.disconnect()
            self._metadata_worker.error.disconnect()
            self._metadata_worker.quit()
            self._metadata_worker = None

        worker = WavAnalysisWorker(filename)
        worker.finished.connect(self._on_metadata_ready)
        worker.error.connect(self._on_metadata_error)
        # Keep a reference so we can cancel it on next selection
        self._metadata_worker = worker
        worker.start()

    def _on_metadata_ready(self, filename: str, analysis_result: dict) -> None:
        """Handle completed background WAV analysis.

        Called on the UI thread via Qt signal.  Ignored if the file no longer
        matches the currently selected file (user moved on).

        Args:
            filename: File that was analysed.
            analysis_result: Result dict from :func:`wav_analyze`.
        """
        if filename != self.filename:
            logger.debug(f"Discarding stale metadata result for {os.path.basename(filename)}")
            return

        self._process_cue_markers(analysis_result)
        self.show_metadata(analysis_result)
        self._load_ai_overlay(filename)

    # ------------------------------------------------------------------
    # AI detection overlay
    # ------------------------------------------------------------------

    def _clear_ai_overlay(self) -> None:
        """Remove all AI detection overlay items from all plots.

        Thin wrapper delegating to AiOverlayController.
        """
        self._ai_overlay.clear()

    def _load_ai_overlay(self, wav_path: str) -> None:
        """Load AI detection layers from the sidecar JSON and draw them.

        Sidecar I/O stays in WavViewer; only overlay item management is
        delegated to AiOverlayController.

        Args:
            wav_path: Absolute path to the WAV file.
        """
        from my_app.ai.ui.analysis_dialog import _load_sidecar  # noqa: PLC0415

        self._ai_overlay.clear()
        data = _load_sidecar(wav_path)
        if not data:
            return
        self.load_ai_overlay(data.get("layers") or [])

    def load_ai_overlay(self, layers: list[dict]) -> None:
        """Draw AI detection layers on the waveform.

        Thin wrapper delegating to AiOverlayController.

        Args:
            layers: List of layer dicts as produced by :class:`AiAnalysisWorker`.
        """
        self._ai_overlay.load_layers(layers)

    def refresh_ai_overlay(self, layers: list[dict] | None = None) -> None:
        """Refresh the AI overlay for the current file.

        Args:
            layers: Optional in-memory analysis layers. When provided, these are
                drawn directly without reloading the sidecar from disk.
        """
        if layers is not None:
            self.load_ai_overlay(layers)
            return
        if self.filename:
            self._load_ai_overlay(self.filename)

    def _toggle_ai_layer(self, layer_name: str, visible: bool) -> None:
        """Show or hide all overlay items for a given layer.

        Thin wrapper delegating to AiOverlayController.

        Args:
            layer_name: Name of the layer to toggle.
            visible: True to show, False to hide.
        """
        self._ai_overlay.toggle_layer(layer_name, visible)

    def _on_metadata_error(self, filename: str, message: str) -> None:
        """Handle a failed background WAV analysis.

        Args:
            filename: File that failed analysis.
            message: Error description.
        """
        logger.warning(f"Could not process metadata for {os.path.basename(filename)}: {message}")

    def _process_cue_markers(self, analysis_result: dict[str, Any]) -> None:
        """Process and display cue point markers.

        Args:     analysis_result: Result from wav_analyze containing cue points
        """
        if self.current_sr is None:
            return

        cue_points = analysis_result.get("cue_points", [])
        self.cue_labels = {
            str(int(k)): v for k, v in analysis_result.get("cue_labels", {}).items()
        }

        # Add cue markers to plots
        for cue in cue_points:
            self._add_single_cue_marker(cue)

    def _add_single_cue_marker(self, cue: dict[str, Any]) -> None:
        """Add a single cue marker to all plots.

        Args:     cue: Cue point information dictionary
        """
        offset = cue.get("Sample Offset", 0)
        cue_id = cue.get("ID")

        if offset <= 0 or cue_id is None or self.current_sr is None:
            return

        # Convert to time position
        x_pos = offset / self.current_sr
        cue_id_str = str(int(cue_id))
        pen = pg.mkPen("#ff334d", width=2)

        # Add marker to all plots
        for plot in [
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ]:
            line = self.create_cue_marker(x_pos=x_pos, height=1.0, pen=pen)
            line.plot_ref = plot  # Store reference for later use
            plot.addItem(line)

            # Track marker for selection highlighting
            self.cue_lines.setdefault(cue_id_str, []).append(line)

            number = cue_id_str[-2:] if len(cue_id_str) > 2 else cue_id_str
            cap = pg.TextItem(
                html=(
                    "<div style='background:#d83a4a;color:#f4f8f5;"
                    "padding:1px 4px;border-radius:2px;font-weight:700;'>"
                    f"{number}</div>"
                ),
                anchor=(0.5, 0.0),
            )
            cap.plot_ref = plot
            cap.setPos(x_pos, self._cue_marker_cap_y(plot))
            cap.setZValue(20)
            plot.addItem(cap)
            self.cue_markers.setdefault(cue_id_str, []).append(cap)

    @staticmethod
    def _cue_marker_cap_y(plot: pg.PlotWidget) -> float:
        """Return a cap label Y position that stays inside the visible plot."""
        y_min, y_max = plot.getViewBox().viewRange()[1]
        y_span = max(0.001, y_max - y_min)
        return y_max - (y_span * 0.08)

    def _setup_interaction_handlers(self) -> None:
        """Set up comprehensive mouse interaction handlers for all plot widgets.

        Establishes complete mouse interaction functionality including:
        - Mouse movement tracking for real-time position feedback
        - Click handlers for waveform navigation and cue point creation
        - Hover events for detailed audio analysis information
        - Professional labeling system with multiple information modes

        The interaction system provides:
        - Real-time mouse position tracking with audio context
        - Intelligent information display based on zoom level and content
        - Click-to-seek functionality for precise audio navigation
        - Professional mouse labels with configurable detail levels

        Note:
            This method coordinates both mouse movement and click handling
            setup to provide a unified interaction experience across all
            three plot widgets (main, top channel, bottom channel).
        """
        self._setup_mouse_interaction()
        self._setup_click_handlers()

    def _initialize_file_playback(self, filename: str) -> None:
        """Initialize audio playback system for the currently loaded file.

        Sets up the audio player component with the loaded file for synchronized
        playback and waveform cursor tracking. This integration enables:
        - Visual playback cursor synchronized with audio position
        - Seek functionality through waveform clicking
        - Real-time position feedback during playback
        - Professional audio playback controls integration

        Args:
            filename: Complete file path to the audio file for playback initialization.
                     Must be a valid audio file supported by the AudioPlayer component.

        Note:
            Gracefully handles initialization errors without affecting visualization
            functionality. If playback initialization fails, the visualization
            remains fully functional but without audio playback capabilities.
        """
        if hasattr(self, "audio_player"):
            try:
                self.audio_player.load_file(filename)
                logger.debug(f"Audio playback initialized for {filename}")
            except (
                AttributeError,
                IndexError,
                KeyError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as exc:
                logger.warning(f"Could not initialize playback: {exc}")

    def _handle_plot_error(self, filename: str, error: Exception) -> None:
        """Handle and recover from errors during audio file plotting and analysis.

        Provides robust error handling for file loading and visualization issues:
        - Clears all plot widgets to prevent corrupted display states
        - Adds minimal error indicators to show that plots are active
        - Logs detailed error information for debugging and troubleshooting
        - Maintains application stability despite individual file failures

        Args:
            filename: Complete path to the file that caused the error.
                     Used for error logging and user feedback.
            error: Exception object containing details about the failure.
                  Logged for debugging and potential user notification.

        Note:
            This method ensures the application remains functional even when
            individual files cannot be loaded due to corruption, format issues,
            or system problems. The UI is left in a clean state for the next file.
        """
        # Clear plots and show error state
        for plot in [
            self.waveform_plot,
            self.waveform_plot_top,
            self.waveform_plot_bottom,
        ]:
            plot.clear()
            # Add minimal error indicator
            plot.plot([0], [0])

        logger.error(f"Error loading {os.path.basename(filename)}: {error}")

    # ========== PLOT SYNCHRONIZATION METHODS ==========

    def _sync_x_range_from_main(
        self, view_box: pg.ViewBox, x_range: tuple[float, float]
    ) -> None:
        """Synchronize X-axis range changes from main plot to channel plots.

        Propagates pan and zoom operations from the main waveform plot to the
        top and bottom channel plots, ensuring all visualizations remain
        temporally aligned during navigation.

        Args:
            view_box: ViewBox that initiated the range change (not used but
                     required by PyQtGraph signal signature).
            x_range: New X-axis range as (minimum_time, maximum_time) tuple
                    in seconds.

        Note:
            Uses synchronization guard (self.syncing) to prevent infinite
            signal loops between connected plots. The synchronization ensures
            consistent temporal alignment across all waveform visualizations.
        """
        if self.syncing:
            return

        self.syncing = True
        try:
            self.waveform_plot_top.setXRange(*x_range, padding=0)
            self.waveform_plot_bottom.setXRange(*x_range, padding=0)
        finally:
            self.syncing = False

    def _sync_x_range_from_top(
        self, view_box: pg.ViewBox, x_range: tuple[float, float]
    ) -> None:
        """Synchronize X-range from top plot to other plots.

        Args:     view_box: ViewBox that initiated the change     x_range: New X-range
        as (min, max) tuple
        """
        if self.syncing:
            return

        self.syncing = True
        try:
            self.waveform_plot.setXRange(*x_range, padding=0)
            self.waveform_plot_bottom.setXRange(*x_range, padding=0)
        finally:
            self.syncing = False

    def _sync_x_range_from_bottom(
        self, view_box: pg.ViewBox, x_range: tuple[float, float]
    ) -> None:
        """Synchronize X-range from bottom plot to other plots.

        Args:     view_box: ViewBox that initiated the change     x_range: New X-range
        as (min, max) tuple
        """
        if self.syncing:
            return

        self.syncing = True
        try:
            self.waveform_plot.setXRange(*x_range, padding=0)
            self.waveform_plot_top.setXRange(*x_range, padding=0)
        finally:
            self.syncing = False

    # ========== METADATA DISPLAY METHODS ==========

    def show_metadata(self, analysis_result: dict[str, Any]) -> None:
        """Display comprehensive metadata from WAV file analysis in organized tables.

        Processes and displays detailed metadata extracted from the WAV file
        across multiple specialized tables:
        - FMT table: Audio format information (sample rate, bit depth, channels)
        - BEXT table: Broadcast Wave extension metadata (BWF specifications)
        - INFO table: LIST-INFO chunk metadata (title, artist, comments, etc.)
        - Cue table: Cue point information with navigation capabilities

        Args:
            analysis_result: Dictionary containing complete analysis results from
                           wav_analyze() function, including:
                           - 'fmt': Audio format information
                           - 'bext': Broadcast extension metadata
                           - 'info': LIST-INFO chunk data
                           - 'cue': Cue point information
                           - Other chunks as available

        Note:
            Clears existing table content before populating new data to prevent
            data mixing between files. Each table is populated independently
            with appropriate error handling for missing metadata sections.
        """
        logger.debug("Displaying metadata in tables")

        # Clear all existing table data
        self._clear_all_metadata_tables()

        # Populate each metadata table
        self._populate_fmt_table(analysis_result.get("fmt", {}))
        self._populate_bext_table(analysis_result.get("bext", {}))

        # defaults = self.user_config.get("wav_tags", {})
        # merged_data = defaults.copy()
        # info_data = analysis_result.get("info")
        # if info_data:
        #     merged_data.update(info_data)
        # self._populate_info_table(merged_data)
        # self._populate_info_table(analysis_result.get("info", {}))
        # self._populate_two_column_table_with_defaults_test(
        # self.info_table, analysis_result.get("info", {}))
        self._populate_info_table(analysis_result.get("info", {}))
        self._populate_gps_table(analysis_result.get("gps", None))
        self._populate_cue_table(analysis_result.get("cue_points", []))

        # Resize tables to fit content
        #
        # self._resize_metadata_tables()

    def _clear_all_metadata_tables(self) -> None:
        """Clear all metadata tables.

        Thin wrapper delegating table clearing to MetadataPresenter; photo
        preview widgets are not part of the metadata tables and stay here.
        """
        self._metadata_presenter.clear_all()
        self.photo_preview_label.setVisible(False)
        self.photo_preview_image.setVisible(False)
        self.photo_preview_image.setToolTip("")

    def _populate_fmt_table(self, fmt_data: dict[str, Any]) -> None:
        """Populate FMT chunk information table.

        Thin wrapper delegating to MetadataPresenter.

        Args:     fmt_data: FMT chunk data dictionary
        """
        self._metadata_presenter.populate_fmt_table(fmt_data)

    def _populate_bext_table(self, bext_data: dict[str, Any]) -> None:
        """Populate BEXT chunk information table.

        Thin wrapper delegating to MetadataPresenter.

        Args:     bext_data: BEXT chunk data dictionary
        """
        self._metadata_presenter.populate_bext_table(bext_data)

    def _populate_info_table(self, info_data: dict[str, Any]) -> None:
        """Populate INFO chunk information table.

        Thin wrapper delegating to MetadataPresenter.

        Args:     info_data: INFO chunk data dictionary
        """
        defaults = self.user_config.get("wav_tags", {})
        self._metadata_presenter.populate_info_table(info_data, defaults)

    def _populate_gps_table(self, gps_data: dict | None) -> None:
        """Populate GPS location table from iXML GPS data.

        Table row population is delegated to MetadataPresenter; the photo
        preview widgets stay here since they involve the current filename
        and widgets outside the metadata tables.

        Args:     gps_data: Dict with 'latitude', 'longitude', 'altitude', or None.
        """
        self._metadata_presenter.populate_gps_table_rows(gps_data)

        # Photo preview
        photo_ref = gps_data.get("photo_ref") if gps_data else None
        if photo_ref and self.filename:
            abs_path = os.path.normpath(
                os.path.join(os.path.dirname(self.filename), photo_ref)
            )
            pixmap = load_photo_pixmap(abs_path, 220) if os.path.exists(abs_path) else None
            if pixmap:
                self.photo_preview_image.setPixmap(pixmap)
                self.photo_preview_image.setFixedSize(pixmap.size())
                self.photo_preview_image.setCursor(Qt.PointingHandCursor)
                self.photo_preview_image.setToolTip(f'<img src="{abs_path}" width="480">')
                self.photo_preview_label.setVisible(True)
                self.photo_preview_image.setVisible(True)
                return
        self.photo_preview_image.setToolTip("")
        self.photo_preview_label.setVisible(False)
        self.photo_preview_image.setVisible(False)

    def _reset_info_table_to_defaults(self) -> None:
        """Reset INFO table to show only defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            (
                "Reset all INFO metadata fields to default values?"
                "This will clear any custom values."
            ),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Re-populate table with empty WAV data (= only defaults)
            defaults = self.user_config.get("wav_tags", {})
            self._metadata_presenter.populate_two_column_table_with_defaults(
                self.info_table, {}, defaults
            )

    def get_info_from_info_table(self) -> dict[str, str]:
        """Extract info data with smart default handling."""
        info_data = {}

        for row in range(self.info_table.rowCount()):
            key_item = self.info_table.item(row, 0)
            val_item = self.info_table.item(row, 1)

            if key_item and val_item:
                key = key_item.text()
                current_text = val_item.text().strip()

                # Gebruik de huidige tekst uit de tabel
                info_data[key] = current_text

        return info_data

    def _get_gps_from_gps_table(self) -> dict[str, float] | None | bool:
        """Read and validate GPS values from the GPS table.

        Returns:
            dict  — valid GPS data
            None  — all GPS fields empty (no GPS to save, continue normally)
            False — validation failed, warning already shown (caller should abort)
        """
        def cell(row: int) -> str:
            item = self.gps_table.item(row, 1)
            return item.text().strip() if item else ""

        lat_str, lon_str, alt_str = cell(0), cell(1), cell(2)

        if not lat_str and not lon_str:
            logger.debug("GPS fields empty — no GPS to save")
            return None  # Empty — nothing to save, no warning needed

        if not lat_str or not lon_str:
            logger.debug("GPS validation failed: only one of lat/lon filled (lat=%r, lon=%r)", lat_str, lon_str)
            QMessageBox.warning(self, "Missing GPS", "Both Latitude and Longitude are required.")
            return False

        try:
            gps_data = {
                "latitude": float(lat_str),
                "longitude": float(lon_str),
                "altitude": float(alt_str) if alt_str else 0.0,
            }

        except ValueError:
            logger.debug("GPS validation failed: non-numeric value (lat=%r, lon=%r, alt=%r)", lat_str, lon_str, alt_str)
            QMessageBox.warning(self, "Invalid GPS", "Latitude, Longitude and Altitude must be numbers.")
            return False

        if not (-90 <= gps_data["latitude"] <= 90):
            logger.debug("GPS validation failed: latitude %s out of range", gps_data["latitude"])
            QMessageBox.warning(self, "Invalid GPS", "Latitude must be between -90 and 90.")
            return False
        if not (-180 <= gps_data["longitude"] <= 180):
            logger.debug("GPS validation failed: longitude %s out of range", gps_data["longitude"])
            QMessageBox.warning(self, "Invalid GPS", "Longitude must be between -180 and 180.")
            return False

        logger.debug("GPS parsed: lat=%s, lon=%s, alt=%s", gps_data["latitude"], gps_data["longitude"], gps_data["altitude"])
        return gps_data

    def save_info_from_info_table_to_file(self) -> None:
        """Save INFO metadata and GPS coordinates in one operation.

        UI orchestration only: opens the save dialog, collects the user's
        choice, calls WavSaveManager (UI-free), and shows the resulting
        success/error message. All save orchestration lives in
        WavSaveManager/WavSaveStrategies.
        """
        if not self.filename:
            QMessageBox.warning(self, "No File", "No WAV file loaded.")
            return

        metadata = self.get_info_from_info_table()
        new_tags = getattr(self.tagger_widget, "get_current_tags", lambda: [])()
        existing_tags = metadata.get("ICMT", "")
        logger.debug("Save triggered: %d metadata fields, %d new tags", len(metadata), len(new_tags))

        gps_data = self._get_gps_from_gps_table()

        if gps_data is False:  # validation failed, warning already shown
            return

        # Read existing iXML so we can preserve photo_ref / location_name
        existing_gps = None
        try:
            existing_gps = wav_analyze(self.filename).get("gps") or {}
        except Exception:
            existing_gps = {}

        if gps_data is None:
            # Check if file currently has GPS — if so, user intentionally cleared it
            if existing_gps:
                logger.debug("GPS fields cleared — will remove GPS from file")
                gps_data = {}  # signal: remove GPS from file
        else:
            # Carry over read-only iXML fields the user cannot edit in the table
            for key in ("photo_ref", "location_name"):
                if key in existing_gps:
                    gps_data[key] = existing_gps[key]

        if gps_data is None and not metadata and not new_tags:
            return

        if gps_data:
            gps_info = f"Lat: {gps_data['latitude']}, Lon: {gps_data['longitude']}, Alt: {gps_data.get('altitude', 0.0)}"
        elif gps_data is not None:  # {} → removal
            gps_info = "GPS location will be removed"
        else:
            gps_info = ""

        if not metadata and not gps_info:
            QMessageBox.critical(self, "No metadata", "No metadata to save")
            return

        manager = WavSaveManager()
        new_tags_string = ", ".join(new_tags) if new_tags else ""

        if not manager.has_anything_to_save(self.filename, metadata, new_tags, gps_info):
            logger.debug("Nothing to save: no tag changes, no metadata changes, no GPS changes")
            QMessageBox.information(
                self,
                "Nothing to Save",
                "No new tags entered and no metadata changes detected.",
            )
            return

        dialog = WavSaveOptionsDialog(
            parent=self,
            filename=self.filename,
            new_tags=(
                new_tags_string
                if new_tags_string
                else "No new tags (metadata changes only)"
            ),
            existing_tags=existing_tags,
            gps_info=gps_info,
        )

        if dialog.exec_() != QDialog.Accepted:
            logger.debug("Save cancelled by user")
            return

        save_method = dialog.get_save_method()
        custom_name = dialog.get_custom_name()
        merge_tags = dialog.should_merge_tags()

        logger.debug(
            f"Save options: method={save_method}, custom='{custom_name}', merge={merge_tags}"
        )

        has_metadata_changes = manager.check_metadata_changes(self.filename, metadata)

        try:
            result = manager.execute_save(
                save_method=save_method,
                filename=self.filename,
                metadata=metadata,
                new_tags=new_tags,
                existing_tags=existing_tags,
                merge_tags=merge_tags,
                custom_name=custom_name,
                user_config=self.user_config,
                gps_data=gps_data,
                confirm_overwrite=lambda: self._confirm_overwrite_original(),
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Unexpected Error", f"An unexpected error occurred:\n{str(e)}"
            )
            logger.error(f"Unexpected error in save workflow: {e}")
            return

        if result and result.success:
            self._show_save_success_message(result, new_tags_string, has_metadata_changes)
            logger.info(f"Save successful: {result.operation_type}")
            self.load_wav_files(select_path=result.output_path)
            if hasattr(self, "tagger_widget"):
                self.tagger_widget.clear_tags()
        else:
            error_msg = result.error_message if result else "Unknown error"
            QMessageBox.critical(self, "Save Error", f"Error saving file:\n{error_msg}")
            logger.error(f"Save failed: {error_msg}")

    def _confirm_overwrite_original(self) -> bool:
        """Show confirmation dialog for in-place overwrite operations.

        Returns:     True if user confirms, False otherwise
        """
        reply = QMessageBox.question(
            self,
            "Overwrite Original?",
            "Are you sure you want to overwrite the original file?\n\n"
            "This CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default to No for safety
        )
        confirmed = reply == QMessageBox.Yes
        logger.debug(f"Overwrite confirmation: {confirmed}")
        return confirmed

    def _show_save_success_message(
        self, result: "SaveResult", new_tags_string: str, has_metadata_changes: bool
    ) -> None:
        """Show success message based on save result.

        Args:     result: SaveResult from save operation     new_tags_string: New tags
        that were saved     has_metadata_changes: Whether metadata was changed
        """
        if new_tags_string and has_metadata_changes:
            save_type = "Tags and metadata"
        elif new_tags_string:
            save_type = "Tags"
        else:
            save_type = "Metadata"

        messages = {
            "edit_copy": f"{save_type} successfully saved!\n\nFile saved as:\n{os.path.basename(result.output_path)}",
            "in_place": f"{save_type} successfully saved!\n\nOriginal file has been updated.",
            "with_backup": f"{save_type} successfully saved!\n\nOriginal file updated.\nBackup saved as: {os.path.basename(result.backup_path)}",
            "custom_name": f"{save_type} successfully saved!\n\nFile saved as:\n{os.path.basename(result.output_path)}",
        }

        message = messages.get(
            result.operation_type, f"{save_type} successfully saved!"
        )
        QMessageBox.information(self, "Save Successful", message)

    def _populate_cue_table(self, cue_points: list[dict[str, Any]]) -> None:
        """Populate cue points table.

        Thin wrapper delegating to MetadataPresenter.

        Args:     cue_points: list of cue point dictionaries
        """
        self.current_cue_points = list(cue_points or [])
        self._metadata_presenter.populate_cue_table(
            self.current_cue_points, self.cue_labels, getattr(self, "current_sr", None)
        )
        self.cue_overview.set_waveform_data(getattr(self, "current_data", None))
        self.cue_overview.set_cues(
            self.current_cue_points,
            self.cue_labels,
            getattr(self, "current_sr", None),
            getattr(self, "audio_duration", None),
        )

    def _resize_metadata_tables12(self) -> None:
        """Resize all metadata tables to fit their content."""
        for table in [self.fmt_table, self.bext_table, self.info_table, self.cue_table]:
            table.resizeRowsToContents()
            table.setFixedHeight(
                table.verticalHeader().length() + table.horizontalHeader().height() + 2
            )

    # ========== MOUSE INTERACTION METHODS ==========

    def _setup_mouse_interaction(self) -> None:
        """Set up mouse interaction for all plots.

        Creates mouse position labels and connects hover events to display real-time
        position and amplitude information.
        """
        # Create mouse labels for each plot if they don't exist
        self._create_mouse_labels()

        # Set default label values
        # self._set_default_mouse_labels()
        self._set_default_mouse_labels_dynamic()

        # Connect hover events if not already connected
        if not getattr(self, "_hover_connected", False):
            self._connect_hover_events()
            self._hover_connected = True

    def _create_mouse_labels(self) -> None:
        """Create mouse position labels for all plots."""
        label_configs = [
            ("mouse_label_main", self.waveform_plot),
            ("mouse_label_top", self.waveform_plot_top),
            ("mouse_label_bottom", self.waveform_plot_bottom),
        ]

        for attr_name, plot in label_configs:
            if not hasattr(self, attr_name):
                label = pg.TextItem("", anchor=(1, 0))
                setattr(self, attr_name, label)

            label = getattr(self, attr_name)
            self._apply_mouse_label_style(label)
            if label.scene() is None:
                plot.addItem(label)

    @staticmethod
    def _apply_mouse_label_style(label: pg.TextItem, point_size: int = 8) -> None:
        """Apply stable pyqtgraph text styling independent of the app font."""
        font = QFont()
        font.setPointSize(point_size)
        font.setWeight(QFont.DemiBold)
        label.setFont(font)

    @staticmethod
    def _mouse_label_position(
        plot: pg.PlotWidget,
        left_margin_ratio: float = 0.004,
        top_margin_ratio: float = 0.06,
    ) -> tuple[float, float]:
        """Return a top-left label position inside the current plot range."""
        x_range, y_range = plot.getViewBox().viewRange()
        x_span = max(0.001, x_range[1] - x_range[0])
        y_span = max(0.001, y_range[1] - y_range[0])
        return (
            x_range[0] + (x_span * left_margin_ratio),
            y_range[1] - (y_span * top_margin_ratio),
        )

    def _connect_hover_events(self) -> None:
        """Connect mouse hover events to plots."""
        self.waveform_plot.scene().sigMouseMoved.connect(self._on_mouse_moved_main)
        self.waveform_plot_top.scene().sigMouseMoved.connect(self._on_mouse_moved_top)
        self.waveform_plot_bottom.scene().sigMouseMoved.connect(
            self._on_mouse_moved_bottom
        )

    def _on_mouse_moved_main(self, mouse_event: QEvent) -> None:
        """Handle mouse movement over main waveform plot.

        Args:     mouse_event: Qt mouse event containing position information
        """
        self._handle_mouse_moved(
            mouse_event, self.waveform_plot, "mouse_label_main", "mono_waveform_label"
        )

    def _on_mouse_moved_top(self, mouse_event: QEvent) -> None:
        """Handle mouse movement over top waveform plot.

        Args:     mouse_event: Qt mouse event containing position information
        """
        self._handle_mouse_moved(
            mouse_event,
            self.waveform_plot_top,
            "mouse_label_top",
            "channel_1_waveform_label",
        )

    def _on_mouse_moved_bottom(self, mouse_event: QEvent) -> None:
        """Handle mouse movement over bottom waveform plot.

        Args:     mouse_event: Qt mouse event containing position information
        """
        self._handle_mouse_moved(
            mouse_event,
            self.waveform_plot_bottom,
            "mouse_label_bottom",
            "channel_2_waveform_label",
        )

    def _handle_mouse_moved_old(
        self, mouse_event: QEvent, plot: pg.PlotWidget, label_attr: str, color_name: str
    ) -> None:
        """Handle generic mouse movement for waveform plots.

        Displays real-time position, amplitude, and dB information as the mouse moves
        over the waveform plots.

        Args:     mouse_event: Qt mouse event     plot: Plot widget being hovered over
        label_attr: Attribute name for the mouse label     color_name: Color name for
        the label styling
        """
        label = getattr(self, label_attr, None)
        if not label or not hasattr(self, "current_sr") or not self.current_sr:
            return

        # Check if mouse is within plot bounds
        if not plot.sceneBoundingRect().contains(mouse_event):
            return

        # Convert scene position to plot coordinates
        point = plot.getViewBox().mapSceneToView(mouse_event)
        x_pos, y_pos = point.x(), point.y()

        # Validate coordinates are within view range
        x_range, y_range = plot.getViewBox().viewRange()
        if not (
            x_range[0] <= x_pos <= x_range[1] and y_range[0] <= y_pos <= y_range[1]
        ):
            return

        # Calculate derived values
        sample_idx = int(x_pos * self.current_sr)
        db_value = 20 * np.log10(abs(y_pos)) if abs(y_pos) > 1e-12 else -120
        #
        # eps = 0.01  # 1 % FS  ⇒  –40 dB
        # db_value = -120.0 if abs(y) < eps else 20 * np.log10(abs(y))
        #

        # Update label with current information
        label_text = (
            f"t = {x_pos:.3f}s\n"
            f"y = {y_pos:.3f}\n"
            f"idx = {sample_idx}\n"
            f"dB = {db_value:.1f}"
        )

        label.setText(label_text)
        label.setAnchor((0, 0))
        label.setColor(self.get_color(color_name))
        label.setPos(*self._mouse_label_position(plot))

    def _handle_mouse_moved(
        self, mouse_event: QEvent, plot: pg.PlotWidget, label_attr: str, color_name: str
    ) -> None:
        """Professional mouse movement handler with comprehensive audio information."""
        label = getattr(self, label_attr, None)

        # COMBINED GUARD CLAUSES (2 branches → 1 branch)
        if (
            not label
            or not hasattr(self, "current_sr")
            or not self.current_sr
            or not plot.sceneBoundingRect().contains(mouse_event)
        ):
            return

        # Convert scene position to plot coordinates
        point = plot.getViewBox().mapSceneToView(mouse_event)
        x_pos, y_pos = point.x(), point.y()
        x_range, y_range = plot.getViewBox().viewRange()

        # COMBINED RANGE CHECK (1 branch)
        if not (
            x_range[0] <= x_pos <= x_range[1] and y_range[0] <= y_pos <= y_range[1]
        ):
            return

        # Basic calculations
        sample_idx, amplitude_linear = int(x_pos * self.current_sr), abs(y_pos)
        label_lines = []

        # TIME SECTION - COMBINED LOGIC (2 branches → 1 branch)
        if self.mouse_label_config.get("show_timecode", True):
            hours, minutes, seconds = (
                int(x_pos // 3600),
                int((x_pos % 3600) // 60),
                x_pos % 60,
            )
            timecode = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
            label_lines.append(f"{x_pos:.3f}s ({timecode})")
        else:
            label_lines.append(f"{x_pos:.3f}s")

        label_lines.append(f"Sample {sample_idx:,}")

        # REMAINING TIME - COMBINED CONDITIONS (3 branches → 1 branch)
        if (
            self.mouse_label_config.get("show_remaining_time", True)
            and hasattr(self, "audio_duration")
            and self.audio_duration
            and (remaining_time := self.audio_duration - x_pos) > 0
        ):
            label_lines.append(f"-{remaining_time:.3f}s")

        # AMPLITUDE SECTION - COMBINED (2 branches → 1 branch)
        amplitude_percent = amplitude_linear * 100
        amplitude_text = (
            f"{y_pos:+.4f} ({amplitude_percent:.1f}%)"
            if self.mouse_label_config.get("show_percentage", True)
            else f"{y_pos:+.4f}"
        )
        label_lines.append(amplitude_text)

        # dB calculation
        db_precision = self.mouse_label_config.get("db_precision", 1)
        db_fs = 20 * np.log10(amplitude_linear) if amplitude_linear > 1e-12 else -120
        label_lines.append(f"{db_fs:.{db_precision}f} dB FS")

        # ANALYSIS FEATURES - DICTIONARY APPROACH (6 branches → 1 loop)
        analysis_functions = {
            "show_peak_detection": lambda: self._analyze_local_peak(
                sample_idx, amplitude_linear
            ),
            "show_channel_correlation": lambda: self._get_channel_context_info(
                label_attr, sample_idx
            ),
            "show_frequency_analysis": lambda: self._get_frequency_info_at_position(
                sample_idx
            ),
        }

        for config_key, func in analysis_functions.items():
            if self.mouse_label_config.get(
                config_key, config_key == "show_peak_detection"
            ):
                if info := func():
                    label_lines.append(info)

        # CONTEXT AND WARNINGS - COMBINED (3 branches → 2 branches)
        if context_info := self._get_recording_context_info(x_pos):
            label_lines.append(context_info)

        if db_fs > -3:
            label_lines.append("HOT SIGNAL")

        # Update label
        label_text = "\n".join(label_lines)
        label_color = self._get_label_color_for_level(db_fs)
        label.setText(label_text)
        label.setAnchor((0, 0))
        self._apply_mouse_label_style(label)
        label.setColor(label_color)
        label.setOpacity(1.0)
        label.setPos(*self._mouse_label_position(plot))

    def _analyze_local_peak(self, sample_idx: int, current_amplitude: float) -> str:
        """Analyze if current position is near a local peak.

        Thin wrapper delegating to the Qt-free analysis.waveform_inspector
        module.

        Args:     sample_idx: Current sample index     current_amplitude: Current
        amplitude value

        Returns:     String with peak information or empty string
        """
        if not hasattr(self, "current_data") or self.current_data is None:
            return ""

        cached_mean_signal = getattr(self, "cached_mean_signal", None)
        return waveform_inspector.analyze_local_peak(
            sample_idx, current_amplitude, cached_mean_signal, self.current_sr
        )

    def _get_channel_context_info(self, label_attr: str, sample_idx: int) -> str:
        """Get channel-specific context information.

        Thin wrapper delegating to the Qt-free analysis.waveform_inspector
        module.

        Args:     label_attr: Label attribute name to determine channel     sample_idx:
        Current sample index

        Returns:     Channel context string
        """
        return waveform_inspector.get_channel_context_info(
            label_attr, sample_idx, self.current_data
        )

    def _get_frequency_info_at_position(self, sample_idx: int) -> str:
        """Get frequency analysis at current position (CPU intensive - optional).

        Thin wrapper delegating to the Qt-free analysis.waveform_inspector
        module.

        Args:     sample_idx: Current sample index

        Returns:     Frequency information string
        """
        if not hasattr(self, "current_data") or self.current_data is None:
            return ""
        if not hasattr(self, "cached_mean_signal"):
            return ""

        return waveform_inspector.get_frequency_info_at_position(
            sample_idx, self.cached_mean_signal, self.current_sr
        )

    def _get_recording_context_info(self, time_pos: float) -> str:
        """Get recording context information (cue points, clipping regions, etc).

        Args:     time_pos: Current time position in seconds

        Returns:     Context information string
        """
        context_info = []

        # Check proximity to cue points
        if (
            self.mouse_label_config.get("show_cue_proximity", True)
            and hasattr(self, "cue_lines")
            and self.cue_lines
        ):
            for cue_id, lines in self.cue_lines.items():
                if lines:
                    try:
                        # Get cue position from first line in list
                        cue_time = (
                            lines[0].value() if hasattr(lines[0], "value") else None
                        )
                        if (
                            cue_time and abs(time_pos - cue_time) < 1.0
                        ):  # Within 1 second
                            label = self.cue_labels.get(cue_id, f"Cue {cue_id}")
                            context_info.append(f"Near: {label}")
                            break
                    except (AttributeError, KeyError, TypeError, IndexError):
                        pass

        # Check for clipping regions
        if (
            self.mouse_label_config.get("show_clipping_detection", True)
            and hasattr(self, "clipping_regions")
            and self.clipping_regions
        ):
            for region in self.clipping_regions:
                try:
                    if hasattr(region, "getRegion"):
                        region_bounds = region.getRegion()
                        if region_bounds[0] <= time_pos <= region_bounds[1]:
                            # context_info.append("CLIPPING REGION")
                            context_info.append("CLIPPING REGION")

                            break
                except (AttributeError, KeyError, TypeError, IndexError):
                    pass

        # File format info at beginning
        if time_pos < 1.0 and hasattr(self, "is_float_format"):
            format_type = "Float" if self.is_float_format else "Integer"
            bit_depth = "32-bit" if self.is_float_format else "16/24-bit"
            context_info.append(f"{format_type} {bit_depth}")

        return " | ".join(context_info)

    def _get_label_color_for_level(self, db_level: float) -> QColor:
        """Get color for label based on signal level for professional feedback.

        Args:     db_level: Signal level in dB FS

        Returns:     QColor based on signal level
        """
        if db_level > -3:  # Hot signal (red) - danger zone
            return QColor(255, 100, 100)
        elif db_level > -6:  # Very good signal (orange) - caution
            return QColor(255, 200, 100)
        elif db_level > -12:  # Good signal (green) - optimal
            return QColor(100, 255, 100)
        elif db_level > -24:  # Moderate signal (yellow) - acceptable
            return QColor(255, 255, 100)
        elif db_level > -48:  # Low signal (light blue) - quiet
            return QColor(150, 200, 255)
        else:  # Very low signal (gray) - very quiet
            return QColor(150, 150, 150)

    def _update_mouse_labels_position(self) -> None:
        """Update mouse label positions and styling after zoom/pan operations.

        Repositions all mouse information labels to maintain visibility and
        appropriate positioning after view range changes. This method ensures:
        - Labels remain at the top-left corner of the visible area
        - Colors are refreshed to maintain visibility
        - Positioning adapts to current zoom level and view range
        - Graceful error handling for plot state issues

        The method processes all three mouse labels (main, top channel, bottom channel)
        and updates their positions based on the current view range of their
        associated plot widgets.

        Note:
            Called automatically by plot synchronization signals to maintain
            label visibility during navigation. Falls back gracefully if plot
            view ranges are unavailable or invalid.
        """
        if not hasattr(self, "current_data") or self.current_data is None:
            return

        # Update positions for all mouse labels
        label_configs = [
            ("mouse_label_main", self.waveform_plot, "mono_waveform_label"),
            ("mouse_label_top", self.waveform_plot_top, "channel_1_waveform_label"),
            (
                "mouse_label_bottom",
                self.waveform_plot_bottom,
                "channel_2_waveform_label",
            ),
        ]

        for attr_name, plot, _color_name in label_configs:
            if hasattr(self, attr_name):
                label = getattr(self, attr_name)
                try:
                    label.setPos(*self._mouse_label_position(plot))
                    # Refresh color in case it got lost
                    label.setColor(self.get_color(_color_name))
                except (
                    AttributeError,
                    IndexError,
                    KeyError,
                    ValueError,
                    TypeError,
                    RuntimeError,
                ) as exc:
                    logger.debug(
                        f"Could not update label position for {attr_name}: {exc}"
                    )

    # old
    def _set_default_mouse_labels(self) -> None:
        """Set default values and positioning for all mouse information labels.

        Initializes mouse labels with standard default information and positions
        them appropriately within the current view ranges:
        - Sets standard default text with basic audio parameters
        - Positions labels at top-left corner of visible area
        - Applies appropriate colors for visibility
        - Handles positioning errors with safe fallback coordinates

        Default display includes:
        - Time position (t = 0.000s)
        - Amplitude value (y = 0.000)
        - Sample index (idx = 0)
        - dB level (dB = -120.0)

        Note:
            This is the legacy method for basic label initialization.
            Current implementation uses _set_default_mouse_labels_dynamic()
            for enhanced configuration-based label setup.
        """
        default_configs = [
            ("mouse_label_main", self.waveform_plot, "mono_waveform_label"),
            ("mouse_label_top", self.waveform_plot_top, "channel_1_waveform_label"),
            (
                "mouse_label_bottom",
                self.waveform_plot_bottom,
                "channel_2_waveform_label",
            ),
        ]

        default_text = "t = 0.000s\ny = 0.000\nidx = 0\ndB = -120.0"

        for attr_name, plot, _color_name in default_configs:
            if hasattr(self, attr_name):
                label = getattr(self, attr_name)
                label.setText(default_text)
                label.setAnchor((0, 0))
                label.setColor(self.get_color(_color_name))

                # Use the current view range to position the label
                try:
                    x_range, y_range = plot.getViewBox().viewRange()
                    label.setPos(x_range[0], y_range[1])
                except (
                    AttributeError,
                    IndexError,
                    KeyError,
                    ValueError,
                    TypeError,
                    RuntimeError,
                ):
                    # Fallback to safe default
                    label.setPos(0, 1)

    def _set_default_mouse_labels_dynamic(self) -> None:
        """Set default labels with dynamic text based on current configuration.

        Initializes mouse labels with configuration-aware default text and
        intelligent positioning. This enhanced method provides:
        - Dynamic text generation based on mouse_label_config settings
        - Professional styling with neutral startup colors
        - Robust positioning with multiple fallback strategies
        - Configuration-adaptive information density

        The method respects user configuration preferences for:
        - Timecode format display (HH:MM:SS vs. decimal seconds)
        - Information detail level (minimal, performance, professional)
        - Precision settings for time and amplitude values
        - Color schemes and visibility preferences

        Note:
            Uses neutral gray color for startup state and generates
            professional default text through _get_professional_default_text().
            Provides multiple fallback strategies for safe label positioning.
        """
        default_configs = [
            ("mouse_label_main", self.waveform_plot, "mono_waveform_label"),
            ("mouse_label_top", self.waveform_plot_top, "channel_1_waveform_label"),
            (
                "mouse_label_bottom",
                self.waveform_plot_bottom,
                "channel_2_waveform_label",
            ),
        ]

        for attr_name, plot, _color_name in default_configs:
            if hasattr(self, attr_name):
                label = getattr(self, attr_name)
                if label is None:
                    continue

                label.setText(
                    self._get_professional_default_text()
                    if attr_name == "mouse_label_main"
                    else ""
                )
                label.setAnchor((0, 0))
                self._apply_mouse_label_style(label)

                # Neutrale startup kleur

                label.setColor(QColor(150, 150, 150))
                label.setOpacity(0.52)

                # Safe positioning
                try:
                    if hasattr(plot, "getViewBox") and plot.getViewBox():
                        if plot.getViewBox().viewRange():
                            label.setPos(*self._mouse_label_position(plot))
                        else:
                            label.setPos(0, 1)
                    else:
                        label.setPos(0, 1)
                except (
                    AttributeError,
                    IndexError,
                    KeyError,
                    ValueError,
                    TypeError,
                    RuntimeError,
                ):
                    label.setPos(0, 1)

    def _get_professional_default_text(self) -> str:
        """Generate professional default text based on current configuration settings.

        Creates intelligent default text for mouse labels that adapts to user
        configuration preferences and provides appropriate information density
        for professional audio analysis workflows.

        The generated text includes:
        - Time information (with optional timecode formatting)
        - Sample index and amplitude values
        - dB level information for signal assessment
        - Optional enhanced features based on configuration

        Returns:
            str: Multi-line string containing formatted default information
                 appropriate for the current mouse label configuration.

        Note:
            Text content adapts to mouse_label_config settings including
            timecode display, precision values, and feature enablement.
            Provides consistent baseline information for all label modes.
        """
        return "Hover for time, sample, dBFS"

    # ========== CLICK HANDLER METHODS ==========

    def _setup_click_handlers(self) -> None:
        """Set up click handlers for waveform plots."""
        if getattr(self, "_click_handlers_setup", False):
            return

        self.waveform_plot.scene().sigMouseClicked.connect(
            self._on_waveform_clicked_main
        )
        self.waveform_plot_top.scene().sigMouseClicked.connect(
            self._on_waveform_clicked_top
        )
        self.waveform_plot_bottom.scene().sigMouseClicked.connect(
            self._on_waveform_clicked_bottom
        )

        self._click_handlers_setup = True

    def _on_waveform_clicked_main(self, mouse_event: QMouseEvent) -> None:
        """Handle clicks on main waveform plot.

        Args:     mouse_event: Qt mouse click event
        """
        if mouse_event.button() == Qt.LeftButton:
            self._handle_waveform_click(self.waveform_plot, mouse_event)

    def _on_waveform_clicked_top(self, mouse_event: QMouseEvent) -> None:
        """Handle clicks on top waveform plot.

        Args:     mouse_event: Qt mouse click event
        """
        if mouse_event.button() == Qt.LeftButton:
            self._handle_waveform_click(self.waveform_plot_top, mouse_event)

    def _on_waveform_clicked_bottom(self, mouse_event: QMouseEvent) -> None:
        """Handle clicks on bottom waveform plot.

        Args:     mouse_event: Qt mouse click event
        """
        if mouse_event.button() == Qt.LeftButton:
            self._handle_waveform_click(self.waveform_plot_bottom, mouse_event)

    def _handle_waveform_click(
        self, plot_widget: pg.PlotWidget, mouse_event: QMouseEvent
    ) -> None:
        """Process waveform click and seek audio to that position.

        Converts click position to time and seeks the audio player to that position,
        starting playback if stopped.

        Args:     plot_widget: Plot widget that was clicked     mouse_event: Mouse click
        event
        """
        if (
            not hasattr(self, "audio_player")
            or not hasattr(self, "audio_duration")
            or not self.audio_duration
        ):
            return

        scene_pos = mouse_event.scenePos()
        view_box = plot_widget.getViewBox()

        # Check if click is within plot bounds
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return

        # Convert to plot coordinates
        view_pos = view_box.mapSceneToView(scene_pos)
        clicked_time = max(0, min(view_pos.x(), self.audio_duration))

        # Seek audio to clicked position
        position_ms = int(clicked_time * 1000)
        self.audio_player.seek_to_position(position_ms)

        logger.debug(f"Seeking to {clicked_time:.2f}s (waveform click)")

        # Start playback if currently stopped
        if self.audio_player.is_stopped():
            self.audio_player.play()

    # ========== CUE POINT METHODS ==========

    def create_cue_marker(
        self, x_pos: float, height: float = 0.4, pen=None
    ) -> pg.PlotDataItem:
        """Create a cue marker line at the specified position.

        Args:     x_pos: X position for the marker in time coordinates     height:
        Height of the marker relative to plot     pen: Pen for drawing the marker (uses
        default if None)

        Returns:     PlotDataItem representing the cue marker
        """
        if pen is None:
            pen = pg.mkPen("y", width=12)

        # Create vertical line marker
        line = pg.PlotDataItem(x=[x_pos, x_pos], y=[-height / 2, height / 2], pen=pen)

        return line

    def highlight_cue_line(self, row: int, column: int) -> None:
        """Highlight the selected cue line in waveform plots.

        Called when a cue point is selected in the cue table. Updates the visual
        highlighting of cue markers.

        Args:     row: Selected row in the cue table     column: Selected column in the
        cue table (unused)
        """
        cue_id_item = self.cue_table.item(row, 0)
        if not cue_id_item:
            return

        try:
            cue_id = str(int(cue_id_item.text().strip()))
        except (ValueError, AttributeError):
            logger.warning(f"Invalid cue ID in row {row}")
            return

        # Update selected cue ID and refresh highlighting
        self.selected_cue_id = cue_id
        self._update_cue_highlighting()
        self.cue_overview.set_selected_cue(cue_id)

    def _add_session_cue_point(self) -> None:
        """Add a non-persistent cue at the current playhead position."""
        if self.current_sr is None or not self.audio_duration:
            logger.info("Cannot add cue without a loaded audio file")
            return

        position_seconds = max(0.0, self.audio_player.get_position() / 1000.0)
        position_seconds = min(position_seconds, self.audio_duration)
        offset = int(position_seconds * self.current_sr)
        cue_id = self._next_session_cue_id()
        label = f"MARK_{cue_id:02d}"
        cue = {
            "ID": cue_id,
            "Sample Offset": offset,
            "Label": label,
            "Notes": "Session cue",
        }

        self.cue_labels[str(cue_id)] = label
        self.current_cue_points.append(cue)
        self._add_single_cue_marker(cue)
        self._populate_cue_table(self.current_cue_points)
        self.selected_cue_id = str(cue_id)
        self._update_cue_highlighting()
        self.cue_overview.set_selected_cue(str(cue_id))

    def _next_session_cue_id(self) -> int:
        """Return the next cue ID for a session-created cue."""
        existing_ids = set()
        for cue in self.current_cue_points:
            try:
                existing_ids.add(int(cue.get("ID", 0)))
            except (TypeError, ValueError):
                continue
        for candidate in range(1, 10000):
            if candidate not in existing_ids:
                return candidate
        return max(existing_ids) + 1 if existing_ids else 1

    def _update_cue_highlighting(self) -> None:
        """Update visual highlighting of cue markers."""
        for cue_id, lines in self.cue_lines.items():
            is_selected = cue_id == self.selected_cue_id

            pen = pg.mkPen(
                "#ff6b7d" if is_selected else "#ff334d",
                width=4 if is_selected else 2,
            )

            # Apply highlighting to all lines for this cue
            for line in lines:
                line.setPen(pen)

            for cap in self.cue_markers.get(cue_id, []):
                plot = getattr(cap, "plot_ref", None)
                if plot is not None:
                    cap.setPos(cap.pos().x(), self._cue_marker_cap_y(plot))
                cap.setOpacity(1.0 if is_selected else 0.82)

    # ========== AUDIO PLAYBACK INTEGRATION METHODS ==========

    def update_waveform_cursor(self, position_ms: int) -> None:
        """Update waveform cursor position synchronized with audio player.

        Called automatically by the audio player component when playback position
        changes to maintain visual synchronization between audio playback and
        waveform visualization. Updates the red playback cursor across all three
        plot widgets simultaneously.

        Args:
            position_ms: Current playback position in milliseconds from the
                        audio player. Converted to seconds for plot positioning.

        Note:
            Requires valid sample rate information to function properly.
            The cursor position is synchronized across all waveform plots
            (main, top channel, bottom channel) to maintain temporal alignment
            during playback operations.
        """
        if not hasattr(self, "current_sr") or not self.current_sr:
            return

        position_seconds = position_ms / 1000.0
        # logger.debug('Updating playback position')
        # logger.debug(f'Playback line status: {self.playback_line}')
        # Update cursor position on all plots if cursor exists
        if self.playback_line:
            for line in self.playback_line:
                line.setPos(position_seconds)

    def handle_playback_state(self, state: QMediaPlayer.State) -> None:
        """Handle playback state changes and manage visual feedback accordingly.

        Responds to audio player state changes to provide appropriate visual
        feedback in the waveform display:
        - Playing: Shows playback cursor for position tracking
        - Paused: Maintains cursor visibility at current position
        - Stopped: Removes cursor and resets visual state

        Args:
            state: New playback state from QMediaPlayer enumeration:
                  - QMediaPlayer.PlayingState: Audio is actively playing
                  - QMediaPlayer.PausedState: Audio is paused at current position
                  - QMediaPlayer.StoppedState: Audio playback has stopped

        Note:
            This method provides the visual bridge between audio playback state
            and waveform visualization, ensuring users have clear feedback about
            current playback status through cursor visibility management.
        """
        if state == QMediaPlayer.PlayingState:
            self.show_playback_cursor()
        elif state == QMediaPlayer.PausedState:
            # Keep cursor visible during pause
            pass
        elif state == QMediaPlayer.StoppedState:
            self.remove_playback_cursor()

    def show_playback_cursor(self) -> None:
        """Create and display red playback cursor across all waveform plots.

        Creates a synchronized vertical line cursor that tracks playback position
        across all three plot widgets. The cursor provides:
        - Bright red color (#ff0000) for high visibility
        - 2-pixel width for clear visual presence
        - Solid line style for professional appearance
        - Z-order positioning above waveform data
        - Synchronized positioning across all plots

        The cursor is created once and reused across playback sessions until
        explicitly removed. Position updates are handled by update_waveform_cursor().

        Note:
            Requires valid sample rate information and audio player component.
            Creates cursor elements only if they don't already exist to prevent
            duplicate cursor instances during repeated playback operations.
        """
        if not hasattr(self, "current_sr") or not self.current_sr:
            return

        # Create playback cursor if it doesn't exist
        if self.playback_line is None:
            self.playback_line = []
            cursor_pen = pg.mkPen("#ff0000", width=2, style=Qt.SolidLine)

            # Add cursor line to each plot
            for plot in [
                self.waveform_plot,
                self.waveform_plot_top,
                self.waveform_plot_bottom,
            ]:
                line = pg.InfiniteLine(pos=0, angle=90, pen=cursor_pen)
                line.setZValue(100)  # Ensure cursor appears on top
                plot.addItem(line)
                self.playback_line.append(line)

        # Update cursor to current playback position
        if hasattr(self, "audio_player"):
            current_position_ms = self.audio_player.get_position()
            current_position_seconds = current_position_ms / 1000.0

            for line in self.playback_line:
                line.setPos(current_position_seconds)

    def remove_playback_cursor(self) -> None:
        """Remove playback cursor from all plots and clean up resources.

        Performs complete cleanup of the playback cursor system:
        - Removes cursor lines from all plot widget scenes
        - Clears cursor references to prevent memory leaks
        - Resets cursor state for future playback sessions
        - Handles safe removal even if cursor is already removed

        This method ensures clean visual state when audio playback stops
        and prepares the visualization for subsequent playback operations
        without visual artifacts from previous sessions.

        Note:
            Safe to call multiple times - checks for cursor existence before
            attempting removal operations. Cursor references are set to None
            after removal to indicate clean state.
        """
        if self.playback_line:
            for line in self.playback_line:
                if line.scene():
                    line.scene().removeItem(line)
            self.playback_line = None

    def _waveform_plots(self) -> list[pg.PlotWidget]:
        """Return all waveform plots controlled by transport zoom."""
        return [self.waveform_plot, self.waveform_plot_top, self.waveform_plot_bottom]

    def _zoom_waveform_in(self) -> None:
        """Zoom in around the current visible center."""
        self._zoom_waveform_by_factor(0.5)

    def _zoom_waveform_out(self) -> None:
        """Zoom out around the current visible center."""
        self._zoom_waveform_by_factor(2.0)

    def _zoom_waveform_fit(self) -> None:
        """Fit the visible waveform range to the loaded audio duration."""
        if not self.audio_duration:
            return
        self.syncing = True
        try:
            for plot in self._waveform_plots():
                plot.getViewBox().setXRange(0, self.audio_duration, padding=0)
        finally:
            self.syncing = False

    def _zoom_waveform_by_factor(self, factor: float) -> None:
        """Apply a horizontal zoom factor to all waveform plots."""
        duration = self.audio_duration or 0.0
        x0, x1 = self.waveform_plot.getViewBox().viewRange()[0]
        center = (x0 + x1) / 2
        width = max(0.05, (x1 - x0) * factor)
        if duration:
            width = min(width, duration)
            start = max(0.0, center - width / 2)
            end = min(duration, center + width / 2)
            if end - start < width:
                start = max(0.0, end - width)
                end = min(duration, start + width)
        else:
            start = center - width / 2
            end = center + width / 2

        self.syncing = True
        try:
            for plot in self._waveform_plots():
                plot.getViewBox().setXRange(start, end, padding=0)
        finally:
            self.syncing = False

    # ========== VIEW MODE CONTROL METHODS ==========

    def set_view_mode(self, mode: str) -> None:
        """Set the waveform visualization display mode for optimal analysis workflow.

        Controls plot visibility and data presentation across three professional
        visualization modes optimized for different analysis needs:

        - 'mono': Single plot showing averaged mono mix for overview analysis
        - 'per_kanaal': Three separate plots (mono + individual channels) for
                       detailed stereo analysis and channel comparison
        - 'overlay': Both channels overlaid in main plot for direct A/B comparison

        Args:
            mode: View mode identifier as string. Must be one of the supported
                 visualization modes: 'mono', 'per_kanaal', or 'overlay'.

        Raises:
            ValueError: If the specified mode is not one of the supported
                       visualization modes.

        Note:
            Mode changes trigger immediate re-rendering of all waveform data
            using the _render_waveforms() method to reflect the new visualization
            configuration. Visual enhancements are also re-applied to ensure
            consistent analysis capabilities across all modes.
        """
        valid_modes = {"mono", "per_kanaal", "overlay"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid view mode: {mode}. Must be one of {valid_modes}")

        self.view_mode = mode

        # Update plot visibility based on mode
        if mode == "mono":
            self.waveform_plot.setVisible(True)
            self.waveform_plot_top.setVisible(False)
            self.waveform_plot_bottom.setVisible(False)
        elif mode == "per_kanaal":
            self.waveform_plot.setVisible(True)
            self.waveform_plot_top.setVisible(True)
            self.waveform_plot_bottom.setVisible(True)
        elif mode == "overlay":
            self.waveform_plot.setVisible(True)
            self.waveform_plot_top.setVisible(False)
            self.waveform_plot_bottom.setVisible(False)

        # Re-render with new mode if we have data
        if self.current_data is not None:
            self._render_waveforms()

        self._update_toolbar_mode_buttons()
        logger.debug(f"View mode changed to: {mode}")

    def get_view_mode(self) -> str:
        """Get the current waveform visualization display mode.

        Returns:
            Current view mode identifier: 'mono', 'per_kanaal', or 'overlay'.
        """
        return self.view_mode

    def sync_view_mode_controls(self, mode: str) -> None:
        """Check the radio button matching the given view mode, if any.

        Public entry point for callers (e.g. SettingsManager restoring a
        saved view mode) that need to keep the view-mode radio buttons in
        sync without reaching into WavViewer's internal widgets directly.

        Args:
            mode: View mode identifier: 'mono', 'per_kanaal', or 'overlay'.
                 Unrecognized values are ignored (no control is checked).
        """
        if mode == "mono":
            self.mono_radio.setChecked(True)
        elif mode == "per_kanaal":
            self.stereo_radio.setChecked(True)
        elif mode == "overlay":
            self.overlay_radio.setChecked(True)

    def get_current_mouse_mode(self) -> str:
        """Get the identifier of the currently active mouse label preset.

        Returns:
            Preset identifier: 'minimal', 'performance', 'professional', or
            'professional_advanced'. Defaults to 'performance' if no preset
            has been explicitly applied yet (matches the pre-existing
            fallback used by callers before this method existed).
        """
        return getattr(self, "_current_mouse_mode", "performance")

    def set_volume(self, volume: int) -> None:
        """Set the audio playback volume.

        Args:
            volume: Volume level, typically 0-100.
        """
        self.audio_player.set_volume(volume)

    def get_volume(self) -> int:
        """Get the current audio playback volume.

        Returns:
            Current volume level, typically 0-100.
        """
        return self.audio_player.get_volume()

    def toggle_playback(self) -> None:
        """Toggle audio playback between play and pause states."""
        self.audio_player.toggle_playback()

    def stop_playback(self) -> None:
        """Stop audio playback and reset position to the start."""
        self.audio_player.stop_playback()

    def volume_up(self) -> None:
        """Increase the audio output volume by one increment."""
        self.audio_player.volume_up()

    def volume_down(self) -> None:
        """Decrease the audio output volume by one decrement."""
        self.audio_player.volume_down()

    def toggle_mute(self) -> None:
        """Toggle audio mute state between muted and unmuted."""
        self.audio_player.toggle_mute()

    def seek_forward(self) -> None:
        """Seek forward in the audio by the player's default increment."""
        self.audio_player.seek_forward()

    def seek_backward(self) -> None:
        """Seek backward in the audio by the player's default increment."""
        self.audio_player.seek_backward()

    def reset_info_table_to_defaults(self) -> None:
        """Reset the INFO metadata table to default values (public entry point).

        Prompts the user for confirmation, then clears the INFO table to
        show only default values. Delegates to the existing internal
        implementation.
        """
        self._reset_info_table_to_defaults()

    def get_audio_duration(self) -> float | None:
        """Get the duration of the currently loaded audio file.

        Returns:
            Duration in seconds, or None if no audio is loaded.
        """
        return self.audio_duration

    def connect_audio_state_changed(self, slot) -> None:
        """Connect a slot to the audio player's stateChanged signal.

        Public entry point so callers do not need to reach into the
        internal ``audio_player`` widget directly just to observe playback
        state changes.

        Args:
            slot: Callable to invoke when the audio player's playback state
                 changes (receives a QMediaPlayer.State value).
        """
        self.audio_player.stateChanged.connect(slot)

    def get_selected_file_list_item_path(self, row: int) -> str | None:
        """Get the file path stored on the file list item at the given row.

        Args:
            row: Row index in the file list.

        Returns:
            The file path (Qt.UserRole data) for the item at ``row``, or
            None if there is no item at that row.
        """
        item = self.file_list.item(row)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def connect_file_list_selection_changed(self, slot) -> None:
        """Connect a slot to the file list's currentRowChanged signal.

        Args:
            slot: Callable to invoke when the file list selection changes
                 (receives the new row index).
        """
        self.file_list.currentRowChanged.connect(slot)

    def get_all_file_list_paths(self) -> list[str]:
        """Get the file paths of all items currently shown in the file list.

        Only paths that still exist on disk are included, matching the
        existing filtering behavior of callers that read the file list
        directly.

        Returns:
            List of existing file paths, in file list order.
        """
        paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item:
                file_path = item.data(Qt.UserRole)
                if file_path and os.path.exists(file_path):
                    paths.append(file_path)
        return paths

    def select_file_by_path(self, target_path: str) -> bool:
        """Select a specific file in the file list by matching its full path.

        Public entry point delegating to the existing internal
        _select_file_by_path() implementation.

        Args:
            target_path: Complete file path to search for and select.

        Returns:
            True if the file was found and successfully selected, False
            otherwise.
        """
        return self._select_file_by_path(target_path)

    def seek_and_play(self, time_seconds: float) -> None:
        """Seek to a timestamp and start playback if not already playing.

        Args:
            time_seconds: Timestamp in seconds to seek to.
        """
        position_ms = int(time_seconds * 1000)
        self.audio_player.seek_to_position(position_ms)
        if self.audio_player.is_stopped():
            self.audio_player.play()

    # ========== UTILITY AND HELPER METHODS ==========

    def get_color(self, color_name: str) -> QColor:
        """Get QColor object from the plot color scheme.

        Args:     color_name: Name of the color in the color scheme

        Returns:     QColor object for the requested color, black if not found
        """
        hex_color = self.plot_colors.get(color_name, "#000000")
        return QColor(hex_color)

    def get_pen(
        self,
        color_name: str,
        width: float | None = None,
        style: QtCore.Qt.PenStyle = QtCore.Qt.SolidLine,
    ) -> pg.mkPen:
        """Get a PyQtGraph pen with specified color and style.

        Args:     color_name: Name of color in the color scheme     width: Line width
        (uses default if None)     style: Qt pen style for line appearance

        Returns:     PyQtGraph pen object configured with specified properties
        """
        if width is None:
            width = self.line_width_default

        color = self.plot_colors.get(color_name, "#000000")
        return pg.mkPen(color, width=width, style=style)

    def update_plot_for_view_range(self) -> None:
        """Update plot data and preserve all markers."""
        if (
            not hasattr(self, "current_data")
            or not hasattr(self, "current_sr")
            or self.current_data is None
            or self.current_sr is None
        ):
            return

        if getattr(self, "syncing", False):
            return

        # view_configs = [
        #     (self.waveform_plot, self.cached_mean_signal, 'mono_waveform'),
        #     (self.waveform_plot_top, self.current_data[:, 0], 'channel_1_waveform'),
        #     (self.waveform_plot_bottom, self.current_data[:, 1], 'channel_2_waveform')
        # ]
        view_configs = self._get_view_config()

        for plot, _, _ in view_configs:
            plot.setUpdatesEnabled(False)

        try:
            # Only remove items that represent waveform data
            for plot, _, _ in view_configs:
                items_to_remove = []

                for item in plot.listDataItems():
                    # Only remove PlotDataItems that don't have special markers
                    if (
                        isinstance(item, pg.PlotDataItem)
                        and not getattr(item, "cue_marker", False)
                        and not hasattr(item, "plot_ref")
                    ):
                        items_to_remove.append(item)

                for item in items_to_remove:
                    plot.removeItem(item)

            # Re-render waveforms
            for plot, data, color_key in view_configs:
                if plot.isVisible():
                    self._render_single_plot(plot, data, color_key)

            # Apply cue highlighting (should be redundant now but good for safety)
            if hasattr(self, "_update_cue_highlighting"):
                self._update_cue_highlighting()

        finally:
            for plot, _, _ in view_configs:
                plot.setUpdatesEnabled(True)

    def toggle_frequency_analysis(self, enabled: bool) -> None:
        """Toggle real-time frequency analysis (CPU intensive).

        Args:     enabled: Whether to enable frequency analysis
        """
        self.mouse_label_config["show_frequency_analysis"] = enabled
        logger.info(f"Frequency analysis {'enabled' if enabled else 'disabled'}")

    def set_label_precision(
        self, time_precision: int = 3, db_precision: int = 1
    ) -> None:
        """Set decimal precision for time and dB values in mouse labels.

        Args:     time_precision: Decimal places for time values     db_precision:
        Decimal places for dB values
        """
        self.mouse_label_config["decimal_precision"] = time_precision
        self.mouse_label_config["db_precision"] = db_precision
        logger.info(f"Label precision set to: time={time_precision}, dB={db_precision}")

    def configure_mouse_labels(self, **config) -> None:
        """Configure mouse label features.

        Examples:     # Disable CPU intensive features
        self.configure_mouse_labels(show_frequency_analysis=False)

        # Minimal display self.configure_mouse_labels(     show_timecode=False,
        show_remaining_time=False,     show_percentage=False )

        # Professional audio engineer setup self.configure_mouse_labels(
        show_peak_detection=True,     show_channel_correlation=True,
        show_cue_proximity=True,     db_precision=2  # More precise dB readings )

        Args:     **config: Configuration options:         - show_timecode: bool - Show
        HH:MM:SS format         - show_remaining_time: bool - Show time remaining -
        show_percentage: bool - Show amplitude as percentage         -
        show_peak_detection: bool - Analyze local peaks         -
        show_channel_correlation: bool - Show L/R correlation         -
        show_frequency_analysis: bool - CPU intensive frequency analysis         -
        show_cue_proximity: bool - Show nearby cue points         -
        show_clipping_detection: bool - Show if in clipping region         -
        decimal_precision: int - Decimal places for time         - db_precision: int -
        Decimal places for dB values
        """
        for key, value in config.items():
            if key in self.mouse_label_config:
                self.mouse_label_config[key] = value
                logger.info(f"Mouse label config: {key} = {value}")
            else:
                logger.warning(f"Unknown mouse label config option: {key}")

    def get_mouse_label_config(self) -> dict[str, Any]:
        """Get current mouse label configuration.

        Returns:     Dictionary with current configuration settings
        """
        return self.mouse_label_config.copy()

    def reset_mouse_label_config(self) -> None:
        """Reset mouse label configuration to defaults."""
        self.mouse_label_config = {
            "show_timecode": True,
            "show_remaining_time": True,
            "show_percentage": True,
            "show_peak_detection": True,
            "show_channel_correlation": True,
            "show_frequency_analysis": False,  # CPU intensive
            "show_cue_proximity": True,
            "show_clipping_detection": True,
            "decimal_precision": 3,
            "db_precision": 1,
        }
        logger.info("Mouse label configuration reset to defaults")

    # Convenience presets for mouse labels
    def set_mouse_labels_minimal(self) -> None:
        """Set mouse labels to minimal display for better performance."""
        self.configure_mouse_labels(
            show_timecode=False,
            show_remaining_time=False,
            show_percentage=False,
            show_peak_detection=False,
            show_channel_correlation=False,
            show_frequency_analysis=False,
            show_cue_proximity=False,
            show_clipping_detection=False,
        )

        # Update default labels as well
        self._current_mouse_mode = "minimal"
        self._set_default_mouse_labels_dynamic()

        logger.info("Mouse labels set to minimal mode")

    def set_mouse_labels_professional(self) -> None:
        """Set mouse labels to full professional audio engineer display."""
        self.configure_mouse_labels(
            show_timecode=True,
            show_remaining_time=True,
            show_percentage=True,
            show_peak_detection=True,
            show_channel_correlation=True,
            show_frequency_analysis=False,  # Still CPU intensive
            show_cue_proximity=True,
            show_clipping_detection=True,
            decimal_precision=3,
            db_precision=2,  # More precise dB readings
        )

        # Update default labels as well
        self._current_mouse_mode = "professional"
        self._set_default_mouse_labels_dynamic()

        logger.info("Mouse labels set to professional mode")

    def set_mouse_labels_professional_advanced(self) -> None:
        """Set mouse labels with all advanced features enabled."""
        self.configure_mouse_labels(
            show_timecode=True,
            show_remaining_time=True,
            show_percentage=True,
            show_peak_detection=True,
            show_channel_correlation=True,
            show_frequency_analysis=True,
            show_cue_proximity=True,
            show_clipping_detection=True,
            decimal_precision=3,
            db_precision=2,
        )
        self._current_mouse_mode = "professional_advanced"
        self._set_default_mouse_labels_dynamic()
        logger.info("Mouse labels set to professional advanced mode")

    def set_mouse_labels_performance(self) -> None:
        """Set mouse labels optimized for performance while keeping essential info."""
        self.configure_mouse_labels(
            show_timecode=True,
            show_remaining_time=False,
            show_percentage=True,
            show_peak_detection=False,
            show_channel_correlation=True,
            show_frequency_analysis=False,
            show_cue_proximity=False,
            show_clipping_detection=True,
            decimal_precision=2,
            db_precision=1,
        )

        # Update default labels as well
        self._current_mouse_mode = "performance"
        self._set_default_mouse_labels_dynamic()

        logger.info("Mouse labels set to performance mode")


def main() -> None:
    """Test function to run WavViewer standalone."""
    logger.info("Starting WavViewer standalone test")

    app = QApplication(sys.argv)

    # Apply same styling as MainWindow
    font = QFont("Arial", 14)
    app.setFont(font)

    # Create standalone WavViewer
    viewer = WavViewer()
    viewer.setGeometry(100, 100, 1200, 800)  # x, y, width, height
    #viewer.setGeometry(100, 100, 200, 400)  # x, y, width, height

    viewer.setWindowTitle("WavViewer Standalone Test")
    viewer.show()

    logger.info("WavViewer standalone started successfully")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
