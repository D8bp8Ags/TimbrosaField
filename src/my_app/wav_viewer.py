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
from typing import Any

import numpy as np
import pyqtgraph as pg
import soundfile as sf

# Local imports
from audio_player import AudioPlayer
from PyQt5 import QtCore
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor, QFont, QMouseEvent
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from tag_completer import FileTagAutocomplete
from ui_components import ApplicationStylist
from user_config_manager import load_user_config
from wav_analyzer import wav_analyze
from wav_save_manager import WavSaveManager


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


# Configure logging
logging.basicConfig(
    level=getattr(
        logging,
        os.getenv("LOG_LEVEL", "DEBUG").upper(),
        logging.INFO,
    ),
    format="[%(levelname)s] %(name)s: %(message)s",
)
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

        # UI state flags
        self._sync_connected: bool = False
        self._hover_connected: bool = False
        self._click_handlers_setup: bool = False

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

        # Setup metadata tables
        self._setup_metadata_tables()

        # Setup tag input system
        self._setup_tag_input()

        # Setup view mode controls
        self._setup_view_controls()

        logger.debug("UI setup completed")

    def _create_main_layout(self) -> None:
        """Create the main three-panel layout structure for the application.

        Establishes the fundamental layout architecture with:
        - Left panel: Fixed-width file browser and controls (240px)
        - Center panel: Metadata displays and input controls (max 400px)
        - Right panel: Expandable waveform visualization area (flexible)

        The layout uses QHBoxLayout for horizontal organization and QFrame containers
        for visual separation. Stretch factors ensure proper resizing behavior when
        the window is resized.

        Note:
            Margins and spacing are minimized to maximize available space for
            waveform visualization while maintaining clear visual separation.
        """
        # Main layout: left | center | right
        self.main_layout = QHBoxLayout(self)
        # self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ════════════════ 1. LEFT PANEL ════════════════
        self.left_panel = QFrame()
        self.left_panel.setFrameShape(QFrame.StyledPanel)
        self.left_panel.setFixedWidth(240)  # fixed width

        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(5, 0, 0, 10)

        # ════════════════ 2. CENTER PANEL ═════════════
        self.central_panel = QFrame()
        self.central_panel.setFrameShape(QFrame.StyledPanel)
        self.central_panel.setMaximumWidth(400)

        self.central_layout = QVBoxLayout(self.central_panel)

        # ── 2a. CENTRAL-TOP  (grows with window) ──────────
        self.central_top_layout = QVBoxLayout()
        self.central_layout.addLayout(self.central_top_layout, stretch=1)

        # ── 2b. CENTRAL-BOTTOM  (fixed height) ─────
        self.central_bottom_layout = QVBoxLayout()
        self.central_layout.addLayout(self.central_bottom_layout, stretch=0)

        # -- 3c. Central-Bottom Controls
        self.central_controls_layout = QHBoxLayout()
        self.central_layout.addLayout(self.central_controls_layout)

        self.central_layout.setContentsMargins(0, 0, 0, 0)

        # ════════════════ 3. RIGHT PANEL ═══════════════
        self.right_panel = QFrame()
        self.right_panel.setFrameShape(QFrame.StyledPanel)

        self.right_layout = QVBoxLayout(self.right_panel)

        self.right_layout.setContentsMargins(0, 0, 0, 0)

        self.right_layout.addStretch()

        # Add panels to main_layout
        self.main_layout.addWidget(self.left_panel, stretch=0)
        self.main_layout.addWidget(self.central_panel, stretch=2)  # moderate space
        self.main_layout.addWidget(self.right_panel, stretch=4)

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
        # File list label and widget
        file_label = QLabel("WAV Files:")
        file_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        self.left_layout.addWidget(file_label)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list.currentRowChanged.connect(self.plot_selected_wav)
        self.left_layout.addWidget(self.file_list)

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
        # Waveform plots label
        plots_label = QLabel("Waveform Visualization:")
        self.right_layout.addWidget(plots_label)

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
        self.waveform_plot = pg.PlotWidget(**plot_config)
        self.waveform_plot.setLabel("left", "Amplitude")
        self.waveform_plot.setLabel("bottom", "Time (s)")
        # self.waveform_plot.setMinimumHeight(120)
        self.right_layout.addWidget(self.waveform_plot, stretch=50)

        # Channel 1 (left) plot
        self.waveform_plot_top = pg.PlotWidget(**plot_config)
        self.waveform_plot_top.setLabel("left", "Left Ch")
        # self.waveform_plot_top.setMinimumHeight(100)
        self.right_layout.addWidget(self.waveform_plot_top, stretch=50)

        # Channel 2 (right) plot
        self.waveform_plot_bottom = pg.PlotWidget(**plot_config)
        self.waveform_plot_bottom.setLabel("left", "Right Ch")
        self.waveform_plot_bottom.setLabel("bottom", "Time (s)")
        # self.waveform_plot_bottom.setMinimumHeight(100)

        self.right_layout.addWidget(self.waveform_plot_bottom, stretch=50)

        # self.waveform_plot.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)
        # self.waveform_plot_top.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)
        # self.waveform_plot_bottom.getViewBox().sigXRangeChanged.connect(
        #     self.update_plot_for_view_range)

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
        # Metadata section label
        metadata_label = QLabel("Metadata:")
        # metadata_label.setStyleSheet("font-weight: bold; margin: 10px 0 5px 0;")

        # Create horizontal layout for tables
        # tables_layout = QHBoxLayout()

        # FMT table
        self.fmt_label = QLabel("Format Info:")
        self.fmt_table = self._create_metadata_table(["Key", "Value"])

        # BEXT table
        self.bext_label = QLabel("Bext Info:")
        self.bext_table = self._create_metadata_table(["Key", "Value"])

        # INFO table
        self.info_label = QLabel("INFO Chunk:")
        self.info_table = self._create_metadata_table(["Key", "Value"])

        # Cue points table
        self.cue_label = QLabel("Cue Points:")
        self.cue_table = self._create_metadata_table(["ID", "Positie", "Label"])
        self.cue_table.cellClicked.connect(self.highlight_cue_line)
        self.cue_table.setFixedHeight(200)

        self.central_top_layout.addWidget(metadata_label)

        self.central_top_layout.addWidget(self.bext_label)
        self.central_top_layout.addWidget(self.bext_table)

        self.central_top_layout.addWidget(self.fmt_label)
        self.central_top_layout.addWidget(self.fmt_table)

        self.central_top_layout.addWidget(self.info_label)
        self.central_top_layout.addWidget(self.info_table)

        self.right_layout.addWidget(self.cue_label)
        self.right_layout.addWidget(self.cue_table)

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
        # table.setMaximumHeight(150)
        # table.setFixedHeight(200)
        table.setMinimumHeight(175)
        # table.setMaximumWidth(50)
        return table

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
        # Tag input section
        tag_label = QLabel("Tags and Metadata:")
        # tag_label.setStyleSheet("font-weight: bold; margin: 10px 0 5px 0;")
        self.central_bottom_layout.addWidget(tag_label)

        # Create tag input widget
        self.tagger_widget = FileTagAutocomplete()
        self.central_bottom_layout.addWidget(self.tagger_widget)

        self.reset_tags_button = QPushButton("Reset")
        self.reset_tags_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.reset_tags_button.setToolTip("Reset tags to default")
        self.reset_tags_button.clicked.connect(self._reset_info_table_to_defaults)
        self.central_controls_layout.addWidget(self.reset_tags_button)

        self.save_tags_button = QPushButton("Save")
        self.save_tags_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.save_tags_button.setToolTip("Save tags to file")
        self.save_tags_button.clicked.connect(self.save_info_from_info_table_to_file)
        self.central_controls_layout.addWidget(self.save_tags_button)

        self.central_controls_layout.addStretch(1)

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
        self.left_layout.addWidget(view_label)

        # Create view mode controls
        view_layout = QHBoxLayout()

        self.view_group = QButtonGroup(self)

        # Mono view radio button
        self.mono_radio = QRadioButton("Mono")
        self.mono_radio.clicked.connect(lambda: self.set_view_mode("mono"))
        self.view_group.addButton(self.mono_radio)
        view_layout.addWidget(self.mono_radio)

        # Stereo view radio button (default)
        self.stereo_radio = QRadioButton("Stereo")
        self.stereo_radio.setChecked(True)
        self.stereo_radio.clicked.connect(lambda: self.set_view_mode("per_kanaal"))
        self.view_group.addButton(self.stereo_radio)
        view_layout.addWidget(self.stereo_radio)

        # Overlay view radio button
        self.overlay_radio = QRadioButton("Overlay")
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

            self.right_layout.addWidget(self.audio_player)
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

        # Create directory if it doesn't exist
        if not os.path.exists(wav_dir):
            try:
                os.makedirs(wav_dir)
                logger.info(f"Created directory: {wav_dir}")
            except OSError as exc:
                logger.error("Cannot create directory %s: %s", wav_dir, exc)
                raise  # re-raise dezelfde OSError (B904 is hier niet van toepassing)

        # Clear existing file list
        self.file_list.clear()

        # Find all WAV files
        try:
            all_files = os.listdir(wav_dir)
            wav_files = sorted([f for f in all_files if f.lower().endswith(".wav")])
        except OSError as exc:
            logger.error(f"Cannot read directory {wav_dir}: {exc}")
            wav_files = []

        # Handle empty directory
        if not wav_files:
            self.file_list.addItem("No WAV files found")
            self.file_list.setEnabled(False)
            logger.info(f"No WAV files found in {wav_dir}")
            return

        # Populate file list
        for wav_file in wav_files:
            full_path = os.path.join(wav_dir, wav_file)

            # Create list item with filename visible, full path in data
            item = QListWidgetItem(wav_file)
            item.setData(Qt.UserRole, full_path)
            item.setToolTip(full_path)
            self.file_list.addItem(item)

        self.file_list.setEnabled(True)

        # Select specific file if requested
        if select_path:
            self._select_file_by_path(select_path)
        else:
            self.file_list.setCurrentRow(0)

        logger.debug(f"Loaded {len(wav_files)} WAV files")

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

        # Pre-calculate mono signal for performance
        self.cached_mean_signal = 0.5 * (data[:, 0] + data[:, 1])

        logger.debug(
            f"Loaded audio: {duration:.2f}s, {sample_rate}Hz, "
            f"{data.shape[1]} channels"
        )

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

        Args:     clipped_samples: Boolean array of clipped samples

        Returns: list of (start_sample, end_sample) tuples for raw clipping regions
        """
        regions = []

        if len(clipped_samples.shape) > 1:
            # If multi-channel, combine all channels
            clipped_any_channel = np.any(clipped_samples, axis=1)
        else:
            # Single channel
            clipped_any_channel = clipped_samples

        # Find where clipping starts and stops
        clip_changes = np.diff(clipped_any_channel.astype(int))

        clip_starts = np.where(clip_changes == 1)[0] + 1
        clip_ends = np.where(clip_changes == -1)[0] + 1

        # Handle edge cases
        if clipped_any_channel[0]:
            clip_starts = np.concatenate([[0], clip_starts])
        if clipped_any_channel[-1]:
            clip_ends = np.concatenate([clip_ends, [len(clipped_any_channel)]])

        # Pair starts and ends
        for start, end in zip(clip_starts, clip_ends, strict=False):
            if end > start:  # Valid region
                regions.append((start, end))

        return regions

    def _merge_nearby_clipping_regions(
        self,
        regions: list[tuple[int, int]],
        gap_tolerance_ms: float = 5.0,
        min_duration_ms: float = 1.0,
    ) -> list[tuple[int, int]]:
        """Merge clipping regions that are close together.

        Args:     regions: list of (start_sample, end_sample) tuples gap_tolerance_ms:
        Maximum gap in milliseconds to bridge     min_duration_ms: Minimum duration in
        milliseconds to keep region

        Returns: list of merged clipping regions
        """
        if not regions:
            return []

        # Convert tolerances to samples
        gap_tolerance_samples = int(gap_tolerance_ms * self.current_sr / 1000.0)
        min_duration_samples = int(min_duration_ms * self.current_sr / 1000.0)

        # Sort regions by start time
        regions = sorted(regions, key=lambda x: x[0])

        # Merge nearby regions
        merged = [regions[0]]

        for start, end in regions[1:]:
            last_start, last_end = merged[-1]

            # If gap between regions is small enough, merge them
            gap_size = start - last_end
            if gap_size <= gap_tolerance_samples:
                # Extend the previous region to include this one
                merged[-1] = (last_start, end)
            else:
                # Keep as separate region
                merged.append((start, end))

        # Filter out regions that are too short (likely noise)
        filtered_regions = []
        for start, end in merged:
            duration_samples = end - start
            if duration_samples >= min_duration_samples:
                filtered_regions.append((start, end))

        return filtered_regions

    def get_clipping_summary(self) -> dict:
        """Get a summary of clipping detection results.

        Returns:     Dictionary with clipping statistics per channel using merged
        regions
        """
        if self.current_data is None:
            return {}

        # Use same threshold logic as clipping detection
        is_float = getattr(self, "is_float_format", True)
        clip_threshold = 0.99 if is_float else 0.95

        left_channel = self.current_data[:, 0]
        right_channel = self.current_data[:, 1]
        mono_mix = self.cached_mean_signal

        left_clipped = np.abs(left_channel) >= clip_threshold
        right_clipped = np.abs(right_channel) >= clip_threshold
        mono_clipped = np.abs(mono_mix) >= clip_threshold

        # Get merged regions for each channel
        left_regions = self._merge_nearby_clipping_regions(
            self._find_raw_clipping_regions(left_clipped), gap_tolerance_ms=5.0
        )
        right_regions = self._merge_nearby_clipping_regions(
            self._find_raw_clipping_regions(right_clipped), gap_tolerance_ms=5.0
        )
        mono_regions = self._merge_nearby_clipping_regions(
            self._find_raw_clipping_regions(mono_clipped), gap_tolerance_ms=5.0
        )

        def calculate_region_stats(regions, clipped_array):
            total_duration_ms = sum(
                (end - start) / self.current_sr * 1000 for start, end in regions
            )
            return {
                "samples_clipped": int(np.sum(clipped_array)),
                "regions_count": len(regions),
                "total_duration_ms": round(total_duration_ms, 1),
                "regions_detail": [
                    {
                        "start_time": start / self.current_sr,
                        "end_time": end / self.current_sr,
                        "duration_ms": (end - start) / self.current_sr * 1000,
                    }
                    for start, end in regions
                ],
            }

        return {
            "left_channel": calculate_region_stats(left_regions, left_clipped),
            "right_channel": calculate_region_stats(right_regions, right_clipped),
            "mono_mix": calculate_region_stats(mono_regions, mono_clipped),
            "threshold_used": clip_threshold,
            "format_type": "float" if is_float else "integer",
            "gap_tolerance_ms": 5.0,
            "min_duration_ms": 1.0,
        }

    #######
    def _process_file_metadata(self, filename: str) -> None:
        """Process and display file metadata and cue points.

        Args:     filename: Path to WAV file to analyze
        """
        try:
            # Analyze WAV file structure
            analysis_result = wav_analyze(filename)

            # Process cue points if present
            self._process_cue_markers(analysis_result)

            # Display metadata in tables
            self.show_metadata(analysis_result)

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.warning(f"Could not process metadata for {filename}: {exc}")

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
        label = self.cue_labels.get(cue_id_str, "")

        # Choose marker appearance based on label
        if label.startswith("MARK_"):
            pen = self.get_pen("cue_mark", width=2)
        elif label.startswith("PEAK_"):
            pen = self.get_pen("cue_peak", width=2)
        else:
            pen = self.get_pen("cue_default", width=2)

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
        self._populate_cue_table(analysis_result.get("cue_points", []))

        # Resize tables to fit content
        #
        # self._resize_metadata_tables()

    def _clear_all_metadata_tables(self) -> None:
        """Clear all metadata tables."""
        for table in [self.fmt_table, self.bext_table, self.info_table, self.cue_table]:
            table.setRowCount(0)

    def _populate_fmt_table(self, fmt_data: dict[str, Any]) -> None:
        """Populate FMT chunk information table.

        Args:     fmt_data: FMT chunk data dictionary
        """
        self._populate_two_column_table(self.fmt_table, fmt_data)

    def _populate_bext_table(self, bext_data: dict[str, Any]) -> None:
        """Populate BEXT chunk information table.

        Args:     bext_data: BEXT chunk data dictionary
        """
        self._populate_two_column_table(self.bext_table, bext_data)

    def _populate_info_table(self, info_data: dict[str, Any]) -> None:
        """Populate INFO chunk information table.

        Args:     info_data: INFO chunk data dictionary
        """
        self._populate_two_column_table_with_defaults_test(self.info_table, info_data)
        # self._populate_two_column_table(self.info_table, info_data)

    def _populate_two_column_table(
        self, table: QTableWidget, data: dict[str, Any]
    ) -> None:
        """Populate a two-column table with key-value data.

        Args:     table: Table widget to populate     data: Dictionary of key-value
        pairs
        """
        # for i, (key, value) in enumerate(data.items()):
        for i, (key, value) in enumerate((data or {}).items()):
            table.insertRow(i)

            # Create and configure key item
            key_item = QTableWidgetItem(str(key))
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(i, 0, key_item)

            # Create and configure value item
            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(i, 1, value_item)

            table.setEditTriggers(QAbstractItemView.NoEditTriggers)

    #####
    def _populate_two_column_table_with_defaults_test(
        self, table: QTableWidget, data: dict[str, Any]
    ) -> None:
        """Populate a two-column table with key-value data, merging defaults.

        This test function shows how we can implement default values in a simple way: 1.
        Get defaults from user_config 2. Merge with actual data (actual data overwrites
        defaults) 3. Populate table normally 4. Make INFO table editable for user
        modifications

        Args:     table: Table widget to populate     data: Dictionary of key-value
        pairs from WAV file
        """
        defaults = self.user_config.get("wav_tags", {})

        merged_data = defaults.copy()  # Start with defaults
        if data:
            merged_data.update(data)  # Overwrite with actual WAV data

        table.setRowCount(0)

        for i, (key, value) in enumerate(merged_data.items()):
            table.insertRow(i)

            # Create and configure key item (non-editable)
            key_item = QTableWidgetItem(str(key))
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
            table.setItem(i, 0, key_item)

            # Create and configure value item (editable)
            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            # Optional: Visual hint if this is a default value
            original_value = data.get(key, "") if data else ""
            default_value = defaults.get(key, "")

            if not original_value and default_value:
                # This is a default value - could add visual styling
                value_item.setToolTip(
                    f"Default value: {default_value}\nDouble-click to edit"
                )
                # Optional: different color for defaults

                value_item.setForeground(
                    QColor(180, 180, 180)
                )  # Light gray for defaults

                font = value_item.font()
                font.setItalic(True)
                value_item.setFont(font)

            else:
                # This is actual WAV data
                value_item.setToolTip(
                    "Original value from WAV file\nDouble-click to edit"
                )

            table.setItem(i, 1, value_item)

        # Step 5: Make table editable if it's the INFO table
        if hasattr(table, "objectName") and "info" in table.objectName().lower():
            table.setEditTriggers(
                QTableWidget.DoubleClicked | QTableWidget.SelectedClicked
            )

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
            self._populate_two_column_table_with_defaults_test(self.info_table, {})

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

    def save_info_from_info_table_to_file(self) -> None:
        """Save tags using the new save manager."""
        if not self.filename:
            QMessageBox.warning(self, "No File", "No WAV file loaded.")
            return

        # if quick_save_with_dialog is None:
        #     QMessageBox.critical(
        #         self, "Save Unavailable", "Saving module not available."
        #     )
        #     return

        # Haal metadata uit tabel + tags uit tagger
        metadata = self.get_info_from_info_table()
        new_tags = getattr(self.tagger_widget, "get_current_tags", lambda: [])()
        existing_tags = metadata.get("ICMT", "")

        # result = quick_save_with_dialog(
        #     parent=self,
        #     filename=self.filename,
        #     metadata=metadata,
        #     new_tags=new_tags,
        #     existing_tags=existing_tags,
        #     user_config=self.user_config,
        # )
        manager = WavSaveManager(parent=self)
        result = manager.show_save_dialog_and_execute(
            filename=self.filename,
            metadata=metadata,
            new_tags=new_tags,
            existing_tags=existing_tags,
            user_config=self.user_config,
        )

        # Als succesvol, refresh file list en clear tags
        if result:
            self.load_wav_files(select_path=result.output_path)
            if hasattr(self, "tagger_widget"):
                self.tagger_widget.clear_tags()

    def _populate_cue_table(self, cue_points: list[dict[str, Any]]) -> None:
        """Populate cue points table.

        Args:     cue_points: list of cue point dictionaries
        """
        self.cue_table.setRowCount(0)

        row = 0
        for cue in cue_points:
            cue_id = str(cue.get("ID", ""))
            # Pak label uit self.cue_labels; val desnoods terug op het cue-dict
            label = (self.cue_labels.get(cue_id) or cue.get("Label", "") or "").strip()
            if not label:
                continue  # overslaan als label leeg is

            self.cue_table.insertRow(row)

            # Cue ID
            id_item = QTableWidgetItem(cue_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self.cue_table.setItem(row, 0, id_item)

            # Position (samples -> tijd)
            offset = cue.get("Sample Offset", 0)
            if getattr(self, "current_sr", None):
                time_pos = offset / self.current_sr
                pos_text = f"{time_pos:.3f}s"
            else:
                pos_text = f"{offset} samples"

            pos_item = QTableWidgetItem(pos_text)
            pos_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cue_table.setItem(row, 1, pos_item)

            # Label
            label_item = QTableWidgetItem(label)
            label_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.cue_table.setItem(row, 2, label_item)

            row += 1

        # If nothing was added: show single row with message
        if row == 0:
            self.cue_table.setRowCount(1)
            msg_item = QTableWidgetItem("No labeled cue points found.")
            msg_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # Optional: make item non-editable/selectable
            msg_item.setFlags(Qt.ItemIsEnabled)
            self.cue_table.setItem(0, 0, msg_item)
            # Empty cells for the remaining columns
            self.cue_table.setItem(0, 1, QTableWidgetItem(""))
            self.cue_table.setItem(0, 2, QTableWidgetItem(""))

        self.cue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # logger.debug(f"Cue points: {cue_points}")
        #
        # # labeled = [(str(int(cid)), label) for cid, label in cue_labels.items()
        # #            if label.strip()]
        # #
        #
        #
        # for i, cue in enumerate(cue_points):
        #     self.cue_table.insertRow(i)
        #
        #     # Cue ID
        #     cue_id = str(cue.get("ID", ""))
        #     id_item = QTableWidgetItem(cue_id)
        #     id_item.setTextAlignment(Qt.AlignCenter)
        #     self.cue_table.setItem(i, 0, id_item)
        #
        #     # Position (convert samples to time)
        #     offset = cue.get("Sample Offset", 0)
        #     if self.current_sr:
        #         time_pos = offset / self.current_sr
        #         pos_text = f"{time_pos:.3f}s"
        #     else:
        #         pos_text = f"{offset} samples"
        #
        #     pos_item = QTableWidgetItem(pos_text)
        #     pos_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        #     self.cue_table.setItem(i, 1, pos_item)
        #
        #     # Label
        #     label = self.cue_labels.get(cue_id, "")
        #     label_item = QTableWidgetItem(label)
        #     label_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        #     self.cue_table.setItem(i, 2, label_item)

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
            if label.scene() is None:
                plot.addItem(label)

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
        label.setPos(x_range[0], y_range[1])

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
        label.setColor(label_color)
        label.setPos(x_range[0], y_range[1])

    def _analyze_local_peak(self, sample_idx: int, current_amplitude: float) -> str:
        """Analyze if current position is near a local peak.

        Args:     sample_idx: Current sample index     current_amplitude: Current
        amplitude value

        Returns:     String with peak information or empty string
        """
        if not hasattr(self, "current_data") or self.current_data is None:
            return ""

        try:
            # Check 10ms window around current position
            window_size = int(self.current_sr * 0.01)
            start_idx = max(0, sample_idx - window_size)
            end_idx = min(len(self.current_data), sample_idx + window_size)

            # Use appropriate data based on current plot
            if (
                hasattr(self, "cached_mean_signal")
                and len(self.cached_mean_signal) > end_idx
            ):
                window_data = self.cached_mean_signal[start_idx:end_idx]
            else:
                return ""

            if len(window_data) == 0:
                return ""

            # Find local maximum in window
            local_max = np.max(np.abs(window_data))

            # Check if current position is near the peak (within 90%)
            if current_amplitude >= local_max * 0.9:
                peak_db = 20 * np.log10(local_max) if local_max > 1e-12 else -120
                return f"Local Peak: {peak_db:.1f} dB"

            return ""

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ):
            return ""

    def _get_channel_context_info(self, label_attr: str, sample_idx: int) -> str:
        """Get channel-specific context information.

        Args:     label_attr: Label attribute name to determine channel     sample_idx:
        Current sample index

        Returns:     Channel context string
        """
        if (
            not hasattr(self, "current_data")
            or self.current_data is None
            or sample_idx >= len(self.current_data)
        ):
            return ""

        text = ""
        try:
            if label_attr == "mouse_label_main":
                # Mono/Main plot - show L/R comparison
                left_val = self.current_data[sample_idx, 0]
                right_val = self.current_data[sample_idx, 1]

                # Stereo width analysis
                width = abs(left_val - right_val)
                if width > 0.1:
                    text = f"L:{left_val:+.3f} R:{right_val:+.3f} Wide: {width:.3f}"
                elif width < 0.01:
                    text = f"L:{left_val:+.3f} R:{right_val:+.3f} Centered"
                else:
                    text = f"L:{left_val:+.3f} R:{right_val:+.3f}"

            elif label_attr == "mouse_label_top":
                # Left channel - show correlation with right
                right_val = self.current_data[sample_idx, 1]
                text = f"Left Ch (R:{right_val:+.3f})"

            elif label_attr == "mouse_label_bottom":
                # Right channel - show correlation with left
                left_val = self.current_data[sample_idx, 0]
                text = f"Right Ch (L:{left_val:+.3f})"

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.debug("Channel context info error: %s", exc)
            text = ""

        return text

    def _get_frequency_info_at_position(self, sample_idx: int) -> str:
        """Get frequency analysis at current position (CPU intensive - optional).

        Args:     sample_idx: Current sample index

        Returns:     Frequency information string
        """
        if (
            not hasattr(self, "current_data")
            or self.current_data is None
            or not hasattr(self, "cached_mean_signal")
        ):
            return ""

        try:
            # Small FFT window for responsiveness
            window_size = 1024
            start_idx = max(0, sample_idx - window_size // 2)
            end_idx = min(len(self.cached_mean_signal), start_idx + window_size)

            window_data = self.cached_mean_signal[start_idx:end_idx]

            if len(window_data) < 256:
                return ""

            # Apply window function and FFT
            windowed = window_data * np.hanning(len(window_data))
            fft = np.fft.rfft(windowed)
            magnitude = np.abs(fft)

            # Find dominant frequency
            freqs = np.fft.rfftfreq(len(windowed), 1 / self.current_sr)
            dominant_idx = np.argmax(magnitude[1:]) + 1  # Skip DC
            dominant_freq = freqs[dominant_idx]

            if dominant_freq > 20:  # Above human hearing threshold
                return f"~{dominant_freq:.0f}Hz"

            return ""

        except (
            AttributeError,
            IndexError,
            KeyError,
            ValueError,
            TypeError,
            RuntimeError,
        ):
            return ""

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
                    x_range, y_range = plot.getViewBox().viewRange()
                    # Position label at top-left of current view
                    label.setPos(x_range[0], y_range[1])
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

        # Generate dynamic default text
        default_text = self._get_professional_default_text()

        for attr_name, plot, _color_name in default_configs:
            if hasattr(self, attr_name):
                label = getattr(self, attr_name)
                if label is None:
                    continue

                label.setText(default_text)
                label.setAnchor((0, 0))

                # Neutrale startup kleur

                label.setColor(QColor(150, 150, 150))

                # Safe positioning
                try:
                    if hasattr(plot, "getViewBox") and plot.getViewBox():
                        x_range, y_range = plot.getViewBox().viewRange()
                        if x_range and y_range:
                            label.setPos(x_range[0], y_range[1])
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
        lines = []

        # Time information
        if self.mouse_label_config.get("show_timecode", True):
            lines.append("0.000s (00:00:00.000)")
        else:
            lines.append("0.000s")

        # Sample information
        lines.append("Sample 0")

        # Remaining time (alleen als enabled)
        if self.mouse_label_config.get("show_remaining_time", True):
            lines.append("Ready...")

        # Amplitude information
        if self.mouse_label_config.get("show_percentage", True):
            lines.append("0.000 (0.0%)")
        else:
            lines.append("0.000")

        # dB information
        db_precision = self.mouse_label_config.get("db_precision", 1)
        lines.append(f"-120.{0:0{db_precision}d} dB FS")

        # Additional startup info
        if self.mouse_label_config.get("show_peak_detection", True):
            lines.append("Hover for analysis")

        if self.mouse_label_config.get("show_channel_correlation", True):
            lines.append("Ready for audio")

        return "\n".join(lines)

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

    def _update_cue_highlighting(self) -> None:
        """Update visual highlighting of cue markers."""
        for cue_id, lines in self.cue_lines.items():
            label = self.cue_labels.get(cue_id, "")
            is_selected = cue_id == self.selected_cue_id

            # Choose pen based on selection and label type
            if is_selected:
                pen = self.get_pen(
                    "cue_peak" if label.startswith("PEAK_") else "cue_mark", width=4
                )
            elif label.startswith("MARK_"):
                pen = self.get_pen("cue_mark", width=2)
            elif label.startswith("PEAK_"):
                pen = self.get_pen("cue_peak", width=2)
            else:
                pen = self.get_pen("cue_default", width=2)

            # Apply highlighting to all lines for this cue
            for line in lines:
                line.setPen(pen)

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

        logger.debug(f"View mode changed to: {mode}")

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

    viewer.setWindowTitle("WavViewer Standalone Test")
    viewer.show()

    logger.info("WavViewer standalone started successfully")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
