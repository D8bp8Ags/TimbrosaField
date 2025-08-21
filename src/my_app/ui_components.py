"""UI Components Module for TimbrosaField Audio Analysis Application.

This module provides a comprehensive set of UI components and styling systems that
enhance the user experience of the TimbrosaField application. It includes modern
status bars, activity indicators, progress tracking, and professional application
styling with theme support.

The module is organized into several key components:
- ModernStatusBar: Enhanced status bar with progress tracking and visual feedback
- ActivityIndicator: Animated spinner for long-running operations
- StatusBarManager: Centralized coordinator for status updates across components
- ApplicationStylist: Professional styling system with theme management
- UIComponentManager: Main coordinator for all UI component managers

Key Features:
- Modern, professional application styling with consistent design principles
- Dark/Light theme support with macOS dark theme variant
- Responsive UI components with accessibility considerations
- Centralized status and progress management
- Animated activity indicators for user feedback
- Professional typography and color schemes
- Component-based architecture for maintainability

The styling system uses a comprehensive color palette and design tokens to ensure
visual consistency across all application components. It supports custom themes
and provides programmatic access to design elements for dynamic styling.

Typical usage:
    # Initialize UI manager
    ui_manager = UIComponentManager(main_window)

    # Apply application styling
    ApplicationStylist.apply_complete_styling(app)

    # Show status messages
    ui_manager.show_message("Operation completed", 3000)

    # Control progress indicators
    ui_manager.show_progress("Processing files...", 100)
    ui_manager.update_progress(50, "Half way done")
    ui_manager.hide_progress()
"""

import logging
import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPalette
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QStatusBar,
)

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

import app_config
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QVBoxLayout, QWidget


class SplashScreen(QWidget):
    """Professional splash screen with background image and loading states."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.loading_label = None
        self.version_label = None
        self.setup_ui()
        self.setup_styling()
        self.center_on_screen()

    def setup_ui(self):
        """Setup the splash screen UI components."""
        self.setFixedSize(400, 250)
        self.setWindowFlags(Qt.SplashScreen | Qt.WindowStaysOnTopHint)

        # Create layout (mainly for structure, we use absolute positioning)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        layout.addStretch()
        layout.addStretch()

        # Background image
        bg_image = QLabel(self)
        bg_image.setPixmap(
            QPixmap("./background.png").scaled(
                600, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        bg_image.setAlignment(Qt.AlignCenter)
        bg_image.setGeometry(0, 0, 400, 250)
        bg_image.lower()

        # Loading text (absolute positioning)
        self.loading_label = QLabel("Loading application...", self)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setProperty("class", "subtitle")
        self.loading_label.setGeometry(50, 210, 300, 30)

        # Version label (bottom right)
        self.version_label = QLabel(f"Version {app_config.APP_VERSION}", self)
        self.version_label.setProperty("class", "caption")
        self.version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.version_label.setGeometry(250, 210, 140, 30)

    def setup_styling(self):
        """Apply custom styling to the splash screen."""
        self.setStyleSheet(
            """
            QWidget {
                background:
                    qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                  stop: 0 #4a7c59,
                                  stop: 1 #4a7c59);
                border-radius: 16px;
            }
            QLabel {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
            }
            QLabel[class="caption"] {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                font-size: 9pt;
            }
        """
        )

    def center_on_screen(self):
        """Center the splash screen on the primary screen."""
        screen = self.app.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2
        )

    def update_message(self, message):
        """Update the loading message."""
        if self.loading_label:
            self.loading_label.setText(message)
            self.app.processEvents()

    def set_ready(self):
        """Set the splash to ready state."""
        if self.loading_label:
            self.loading_label.setProperty("class", "success-message")
            self.loading_label.setText("Ready!")
            self.app.processEvents()

    def show_and_process(self):
        """Show the splash screen and process events."""
        self.show()
        self.app.processEvents()


class ModernStatusBar(QStatusBar):
    """Enhanced status bar with progress tracking and comprehensive visual feedback.

    This modern status bar provides a professional interface for displaying application
    status, progress tracking, file information, and audio playback status. It features
    animated activity indicators, temporary message display with auto-hide timers,
    and comprehensive file statistics.

    Key features:
    - Temporary status messages with automatic timeout
    - Progress bar with animation for long operations
    - Activity indicator with smooth spinning animation
    - File counter with proper pluralization
    - Audio status display with state tracking
    - Current file information display
    - Professional visual design with separators

    The status bar automatically handles message timeouts, progress visibility,
    and provides consistent visual feedback for all application operations.

    Attributes:
        status_label (QLabel): Main status message display.
        progress_bar (QProgressBar): Progress indicator for operations.
        activity_indicator (ActivityIndicator): Animated spinner widget.
        audio_status (QLabel): Audio playback state display.
        file_info (QLabel): Current file information display.
        file_counter (QLabel): Total file count display.
        message_timer (QTimer): Auto-hide timer for temporary messages.
    """

    def __init__(self, parent=None):
        """Initialize the modern status bar with all components.

        Creates and configures all status bar widgets including labels,
        progress indicators, activity animations, and auto-hide timers.
        The layout is designed for professional appearance with proper
        spacing and visual hierarchy.

        Args:
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setup_ui()
        self.setup_timers()

    def setup_ui(self):
        """Setup and configure all status bar UI components.

        Creates the complete status bar layout with:
        - Main status label for messages
        - Progress bar (initially hidden)
        - Animated activity indicator
        - File counter with proper formatting
        - Visual separators for organization

        The layout follows professional design principles with appropriate
        spacing, sizing constraints, and visual hierarchy. Components are
        positioned for optimal user experience and information density.

        Note:
            Some components like audio_status and file_info are created but
            not initially added to layout - they can be enabled later.
        """
        # Main status label
        self.status_label = QLabel("Ready")
        self.addWidget(self.status_label)

        # Separator
        # separator1 = QFrame()
        # separator1.setFrameShape(QFrame.VLine)
        # separator1.setFrameShadow(QFrame.Sunken)
        # self.addPermanentWidget(separator1)

        # # File counter
        # self.file_counter = QLabel("0 files")
        # self.addPermanentWidget(self.file_counter)

        # # Separator
        # separator2 = QFrame()
        # separator2.setFrameShape(QFrame.VLine)
        # separator2.setFrameShadow(QFrame.Sunken)
        # self.addPermanentWidget(separator2)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.addPermanentWidget(self.progress_bar)

        # Activity indicator
        self.activity_indicator = ActivityIndicator()
        self.addPermanentWidget(self.activity_indicator)
        self.activity_indicator.setVisible(False)

        # Audio status
        self.audio_status = QLabel("♪ Stopped")
        # self.addPermanentWidget(self.audio_status)

        # Current file info
        self.file_info = QLabel("")
        # self.addPermanentWidget(self.file_info)

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        self.addPermanentWidget(separator2)

        # # File counter
        self.file_counter = QLabel("0 files")
        self.addPermanentWidget(self.file_counter)

    def setup_timers(self):
        """Setup automatic timer systems for status message management.

        Configures the message timer system that automatically clears
        temporary status messages after a specified timeout period.
        The timer is single-shot to prevent message flickering and
        provides smooth user experience.

        Timers configured:
        - message_timer: Auto-hide for temporary messages

        Note:
            The timer is connected to clear_temporary_message() slot
            and set to single-shot mode for proper behavior.
        """
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self.clear_temporary_message)
        self.message_timer.setSingleShot(True)

    def show_message(self, message, timeout=3000, icon=None):
        """Display a temporary status message with optional icon and auto-hide.

        Shows a status message in the main status label with optional
        emoji icon prefix. The message can have an automatic timeout
        for temporary notifications, or stay visible indefinitely.

        Args:
            message (str): The status message text to display.
            timeout (int, optional): Auto-hide timeout in milliseconds.
                                   Use 0 for permanent messages. Defaults to 3000.
            icon (str, optional): Emoji or icon to prefix the message.
                                Defaults to None (no icon).

        Example:
            show_message("✅ File saved successfully", 2000, "✅")
            show_message("Processing...", 0)  # No timeout

        Note:
            If a timeout is specified (> 0), the message will automatically
            clear after the specified duration and revert to "Ready" state.
        """
        if icon:
            self.status_label.setText(f"{icon} {message}")
        else:
            self.status_label.setText(message)

        if timeout > 0:
            self.message_timer.start(timeout)

    def clear_temporary_message(self):
        """Clear the current temporary message and restore ready state.

        Resets the status label to the default "Ready" state after
        a temporary message timeout expires. This provides consistent
        user feedback and indicates the application is ready for new
        operations.

        Note:
            This method is automatically called by the message timer.
            It can also be called manually to force message clearing.
        """
        self.status_label.setText("Ready")

    def show_progress(self, title, maximum=100):
        """Display progress bar and activity indicator for long operations.

        Shows the progress tracking components including progress bar
        and animated activity indicator. This provides comprehensive
        visual feedback for operations that take significant time.

        Args:
            title (str): Descriptive title for the operation being tracked.
            maximum (int, optional): Maximum progress value. Defaults to 100.
                                   Use for percentage-based progress (0-100)
                                   or custom scales.

        Features activated:
        - Progress bar becomes visible and resets to 0
        - Activity indicator starts spinning animation
        - Status message shows operation title

        Example:
            show_progress("Analyzing audio files", 100)
            show_progress("Exporting data", 50)  # Custom scale

        Note:
            The progress bar starts at 0 and must be updated using
            update_progress() calls. The title is shown without timeout.
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.activity_indicator.setVisible(True)
        self.activity_indicator.start()
        self.show_message(title, 0)  # No timeout

    def update_progress(self, value, message=None):
        """Update the current progress value and optional status message.

        Updates the progress bar value to reflect operation advancement.
        Optionally updates the status message to provide more detailed
        feedback about the current operation phase.

        Args:
            value (int): New progress value (should be within 0 to maximum range).
            message (str, optional): Updated status message describing current
                                   operation phase. Defaults to None (no change).

        Example:
            update_progress(25, "Processing file 1 of 4")
            update_progress(50)  # Just update value
            update_progress(75, "Almost finished...")

        Note:
            If a message is provided, it's displayed without timeout
            (permanent until next message or progress completion).
        """
        self.progress_bar.setValue(value)
        if message:
            self.show_message(message, 0)

    def hide_progress(self):
        """Hide progress components and restore normal status display.

        Completes the progress tracking by hiding the progress bar
        and stopping the activity indicator animation. Resets the
        status to ready state to indicate operation completion.

        Actions performed:
        - Progress bar becomes invisible
        - Activity indicator stops animation and hides
        - Status message resets to "Ready"

        Note:
            Call this method when a long operation completes successfully
            or is cancelled. Always pair with show_progress() calls.
        """
        self.progress_bar.setVisible(False)
        self.activity_indicator.setVisible(False)
        self.activity_indicator.stop()
        self.show_message("Ready")

    def update_file_count(self, count):
        """Update the file counter display with proper pluralization.

        Updates the file counter widget to show the current number of
        files with grammatically correct singular/plural text formatting.
        Provides users with immediate feedback about collection size.

        Args:
            count (int): Number of files currently available in the collection.
                        Can be 0 for empty collections.

        Display format:
        - 0 files: "0 files"
        - 1 file: "1 file" (singular)
        - Multiple: "N files" (plural)

        Example:
            update_file_count(0)   # "0 files"
            update_file_count(1)   # "1 file"
            update_file_count(42)  # "42 files"

        Note:
            The counter should be updated whenever the file collection
            changes (files added, removed, or collection refreshed).
        """
        if count == 1:
            self.file_counter.setText("1 file")
        else:
            self.file_counter.setText(f"{count} files")

    def update_audio_status(self, status):
        """Update the audio playback status indicator.

        Updates the audio status display to reflect the current playback
        state. Provides immediate visual feedback about audio operations.

        Args:
            status (str): Current audio state. Common values:
                         - "playing": Audio is currently playing
                         - "paused": Audio is paused
                         - "stopped": Audio is stopped
                         - Custom status strings are supported

        Display format:
        Status text is title-cased ("Playing", "Paused", "Stopped")

        Example:
            update_audio_status("playing")  # Shows "Playing"
            update_audio_status("paused")   # Shows "Paused"

        Note:
            Emoji icons are commented out due to environment compatibility
            but can be enabled in suitable environments. The status should
            be updated whenever audio player state changes.
        """
        # todo
        # icons = {"playing": "▶️", "paused": "⏸️", "stopped": "⏹️"}
        # icon = icons.get(status.lower(), "♪")
        # Icons don't work yet in some environments
        self.audio_status.setText(f"{status.title()}")

    def update_file_info(self, filename=None, duration=None, size=None):
        """Update the current file information display with comprehensive details.

        Shows detailed information about the currently selected or playing
        audio file including filename, duration, and file size with intelligent
        formatting for optimal readability.

        Args:
            filename (str, optional): Full path to the audio file.
                                    Only basename is displayed. Defaults to None.
            duration (float, optional): Audio duration in seconds.
                                      Formatted as M:SS.s or SS.s. Defaults to None.
            size (int, optional): File size in bytes.
                                Formatted as KB or MB appropriately. Defaults to None.

        Display format:
        - "filename.wav | 2:34.5 | 4.2MB" (all info)
        - "filename.wav | 1.2MB" (no duration)
        - "filename.wav" (filename only)
        - "" (clear display if no filename)

        Duration formatting:
        - < 60 seconds: "34.5s"
        - >= 60 seconds: "2:34.5" (M:SS.s format)

        Size formatting:
        - < 1MB: "1024.0KB"
        - >= 1MB: "4.2MB"

        Example:
            update_file_info("recording.wav", 123.45, 2048000)
            # Shows: "recording.wav | 2:03.4 | 2.0MB"

        Note:
            Pass None for filename to clear the display entirely.
            Duration and size are optional and gracefully omitted if not provided.
        """
        if not filename:
            self.file_info.setText("")
            return

        info_parts = [os.path.basename(filename)]

        if duration:
            if duration < 60:
                info_parts.append(f"{duration:.1f}s")
            else:
                minutes = int(duration // 60)
                seconds = duration % 60
                info_parts.append(f"{minutes}:{seconds:04.1f}")

        if size:
            if size > 1024**2:  # MB
                info_parts.append(f"{size / (1024 ** 2):.1f}MB")
            else:
                info_parts.append(f"{size / 1024:.1f}KB")

        self.file_info.setText(" | ".join(info_parts))


class ActivityIndicator(QLabel):
    """Animated spinning activity indicator for visual feedback during operations.

    This widget provides a smooth, animated spinner that indicates when the
    application is performing background operations. It uses custom painting
    with QPainter to create a professional spinning animation with gradual
    opacity changes for visual appeal.

    Features:
    - Smooth rotation animation (30-degree increments)
    - Gradient opacity effect for professional appearance
    - Configurable animation speed and appearance
    - Automatic start/stop control
    - Minimal resource usage when inactive

    The indicator draws 8 circular segments arranged in a circle, with each
    segment having decreasing opacity to create a "trailing" effect as it spins.

    Attributes:
        angle (int): Current rotation angle (0-360 degrees).
        timer (QTimer): Animation timer for rotation updates.
        is_active (bool): Whether the animation is currently running.
    """

    def __init__(self, parent=None):
        """Initialize the activity indicator with fixed size and animation setup.

        Creates a compact 16x16 pixel activity indicator widget with
        custom animation system. The size is optimized for status bar
        and toolbar integration.

        Args:
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.movie = None
        self.setup_animation()

    def setup_animation(self):
        """Configure the spinning animation system with timer and state tracking.

        Initializes the animation properties and timer for smooth rotation.
        The animation uses 30-degree increments for smooth visual progression
        and 100ms intervals for optimal performance.

        Animation properties:
        - 30-degree rotation increments (12 steps per full rotation)
        - 100ms timer intervals (10 FPS)
        - Boolean state tracking for efficient rendering

        Note:
            The animation timer is not started automatically - use start()
            method to begin animation when needed.
        """
        # Create simple spinning animation using QPainter
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        self.is_active = False

    def rotate(self):
        """Advance the rotation angle and trigger a repaint.

        Updates the rotation angle by 30 degrees and wraps around
        at 360 degrees to create continuous spinning motion. Triggers
        a widget repaint to show the updated rotation.

        Rotation behavior:
        - Increments by 30 degrees per call
        - Wraps from 330 to 0 degrees for seamless looping
        - Immediately triggers visual update via update()

        Note:
            This method is called automatically by the animation timer
            and should not be called manually during normal operation.
        """
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        """Custom paint implementation for the spinning activity indicator.

        Renders the animated spinner using QPainter with 8 circular segments
        arranged around a center point. Each segment has decreasing opacity
        to create a smooth "trailing" visual effect as it rotates.

        Args:
            event (QPaintEvent): Paint event containing update region information.
                               Required by Qt paint system but not directly used.

        Rendering details:
        - 8 segments positioned at 45-degree intervals
        - Gradient opacity from 255 to minimum 50
        - Antialiasing enabled for smooth appearance
        - Blue color scheme (100, 150, 255) with alpha blending
        - 2x4 pixel elliptical segments positioned radially

        Note:
            Returns early if animation is not active to optimize performance.
            The painter coordinate system is translated to widget center
            and rotated by the current angle for easy segment positioning.
        """
        if not self.is_active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Move to center
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)

        # Draw spinning circle segments
        painter.setPen(QColor(100, 100, 100))
        painter.setBrush(QColor(150, 150, 150))

        for i in range(8):
            painter.rotate(45)
            opacity = 255 - (i * 30)
            painter.setBrush(QColor(100, 150, 255, max(50, opacity)))
            painter.drawEllipse(-1, -6, 2, 4)

    def start(self):
        """Start the spinning animation with timer-based updates.

        Activates the activity indicator by setting the active state
        and starting the animation timer. The spinner will begin
        rotating immediately with smooth 10 FPS animation.

        Animation settings:
        - Timer interval: 100ms (10 FPS)
        - Rotation: 30 degrees per frame
        - Full rotation: 1.2 seconds

        Note:
            The indicator will continue spinning until stop() is called.
            Multiple start() calls are safe and will not create duplicate timers.
        """
        self.is_active = True
        self.timer.start(100)  # 100ms intervals

    def stop(self):
        """Stop the spinning animation and clear the display.

        Deactivates the activity indicator by stopping the animation
        timer and clearing the active state. Triggers a final repaint
        to clear the spinner graphics.

        Cleanup actions:
        - Sets is_active to False
        - Stops the animation timer
        - Triggers repaint to clear graphics

        Note:
            After stopping, the widget appears blank until start() is
            called again. Multiple stop() calls are safe.
        """
        self.is_active = False
        self.timer.stop()
        self.update()


class StatusBarManager:
    """Centralized coordinator for status bar updates and component integration.

    This class serves as the primary interface between the main application and
    the modern status bar system. It provides a clean API for status updates,
    progress tracking, and automatic integration with application components
    like audio players and file lists.

    Key responsibilities:
    - Initialize and manage ModernStatusBar instance
    - Coordinate status updates from multiple application components
    - Handle automatic signal connections for real-time updates
    - Provide high-level interface for common status operations
    - Manage file count updates and audio state synchronization

    The manager automatically detects and connects to available application
    components (audio player, file list) to provide seamless status updates
    without requiring manual coordination from other parts of the application.

    Attributes:
        main_window: Reference to the main application window.
        status_bar (ModernStatusBar): The managed status bar widget.

    Example:
        status_manager = StatusBarManager(main_window)
        status_manager.show_message("✅ Operation completed", 3000)
        status_manager.show_progress("Processing files...", 100)
    """

    def __init__(self, main_window):
        """Initialize the status bar manager with main window integration.

        Creates a new ModernStatusBar instance and integrates it with the
        main window. Sets up automatic signal connections for real-time
        updates from application components when available.

        Args:
            main_window: The main application window that will host the status bar.
                        Must support setStatusBar() method for integration.

        Initialization steps:
        1. Store main window reference
        2. Create ModernStatusBar instance
        3. Install status bar in main window
        4. Attempt automatic signal connections
        5. Log successful initialization

        Note:
            Signal connections are attempted but failures are handled gracefully
            to support various application configurations and initialization orders.
        """
        self.main_window = main_window
        #        self.wav_viewer = main_window.wav_viewer

        # Create modern status bar
        self.status_bar = ModernStatusBar(main_window)
        main_window.setStatusBar(self.status_bar)

        # Connect to wav_viewer signals
        # self._connect_signals()

        # Initial setup
        # self.status_bar.show_message("✅ Field Recorder Analyzer ready", 2000)
        # self._update_initial_file_count()

        logger.info("StatusBarManager initialized with ModernStatusBar")

    def _connect_signals(self):
        """Establish automatic signal connections for real-time status updates.

        Attempts to connect status bar updates to application component signals
        for seamless user feedback. Connections are made conditionally based
        on component availability to support flexible application architectures.

        Signal connections attempted:
        - Audio player state changes → audio status updates
        - File list selection changes → current file info updates
        - File list content changes → file count updates

        Error handling:
        All connection attempts are wrapped in try-catch blocks to handle
        cases where components may not be available or fully initialized.
        Connection failures are logged but do not prevent operation.

        Note:
            This method is called automatically during initialization.
            Manual status updates are always available even if automatic
            connections fail.
        """
        try:
            # Connect audio player state changes
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.stateChanged.connect(
                    self._on_audio_state_changed
                )
                logger.info("Audio player status connected to status bar")

            # Connect file list changes
            if hasattr(self.wav_viewer, "file_list"):
                self.wav_viewer.file_list.currentRowChanged.connect(
                    self._on_file_selection_changed
                )
                logger.info("File list status connected to status bar")

        except Exception as e:
            logger.warning(f"Error connecting status bar signals: {e}")

    # def _update_initial_file_count(self):
    #     """Update initial file count."""
    #     return self._execute_ui_command('update_file_count')

    # Todo
    # pass
    # if hasattr(self.wav_viewer, 'file_list'):
    #     count = self.wav_viewer.file_list.count()
    #     # Don't count the "No files found" placeholder
    #     if count == 1:
    #         item = self.wav_viewer.file_list.item(0)
    #         if item and "Geen WAV-bestanden" in item.text():
    #             count = 0
    #     self.status_bar.update_file_count(count)

    def _on_audio_state_changed(self, state):
        """Handle automatic audio player state change notifications.

        Processes QMediaPlayer state change signals and updates the status
        bar audio indicator accordingly. Provides immediate visual feedback
        for audio operations without manual coordination.

        Args:
            state (QMediaPlayer.State): New audio player state from Qt multimedia.
                                      Possible values:
                                      - QMediaPlayer.PlayingState
                                      - QMediaPlayer.PausedState
                                      - QMediaPlayer.StoppedState

        State mapping:
        - PlayingState → "playing" status
        - PausedState → "paused" status
        - StoppedState → "stopped" status
        - Unknown states → "stopped" (safe fallback)

        Note:
            This is an automatic slot method connected to audio player signals.
            The status bar audio indicator is updated immediately when called.
        """
        status_map = {
            QMediaPlayer.PlayingState: "playing",
            QMediaPlayer.PausedState: "paused",
            QMediaPlayer.StoppedState: "stopped",
        }

        status = status_map.get(state, "stopped")
        self.status_bar.update_audio_status(status)

    def _on_file_selection_changed(self, row):
        """Handle automatic file list selection change notifications.

        Processes file list selection changes and updates the status bar
        with comprehensive information about the selected file including
        size, duration, and other metadata when available.

        Args:
            row (int): Selected row index in the file list.
                      -1 indicates no selection (clears file info).

        Processing steps:
        1. Validate row index and retrieve list item
        2. Extract file path from item data (Qt.UserRole)
        3. Verify file existence on filesystem
        4. Gather file statistics (size, modification time)
        5. Extract audio duration if available from wav_viewer
        6. Update status bar file info display

        Error handling:
        - Invalid row indices are handled gracefully
        - Missing files clear the display
        - File stat errors are logged but don't crash
        - Duration extraction failures fall back to size-only display

        Note:
            This is an automatic slot method connected to file list signals.
            File info is updated immediately when selection changes.
        """
        if row < 0:
            self.status_bar.update_file_info()
            return

        item = self.wav_viewer.file_list.item(row)
        if not item:
            return

        file_path = item.data(Qt.UserRole)
        if not file_path or not os.path.exists(file_path):
            return

        try:
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size

            # Get duration if available
            duration = None
            if hasattr(self.wav_viewer, "audio_duration"):
                duration = self.wav_viewer.audio_duration

            self.status_bar.update_file_info(file_path, duration, file_size)

        except Exception as e:
            logger.error(f"Error updating file info: {e}")

    # === PUBLIC INTERFACE METHODS ===

    def show_message(self, message, timeout=3000):
        """Display a status message with intelligent icon detection and timeout.

        Shows a message in the status bar with automatic icon detection based
        on message content. Supports both explicit icons in the message text
        and keyword-based icon inference for consistent visual feedback.

        Args:
            message (str): The status message to display. Can include emoji icons
                          or trigger automatic icon detection via keywords.
            timeout (int, optional): Auto-hide timeout in milliseconds.
                                   Use 0 for permanent display. Defaults to 3000.

        Automatic icon detection:
        - "✅" or "success" → success icon
        - "❌" or "error" → error icon
        - "⚠️" or "warning" → warning icon
        - "ℹ️" or "info" → info icon

        Example:
            show_message("✅ File saved successfully")  # Uses existing icon
            show_message("Operation completed", 2000)    # No icon
            show_message("Error occurred", 5000)        # Auto-detects error icon

        Note:
            The message is passed to the underlying ModernStatusBar with
            detected icon for consistent formatting and behavior.
        """
        icon = None
        if "✅" in message or "success" in message.lower():
            icon = "✅"
        elif "❌" in message or "error" in message.lower():
            icon = "❌"
        elif "⚠️" in message or "warning" in message.lower():
            icon = "⚠️"
        elif "ℹ️" in message or "info" in message.lower():
            icon = "ℹ️"

        self.status_bar.show_message(message, timeout, icon)

    def update_file_count(self):
        """Update the file counter display based on current file collection.

        Refreshes the file count display in the status bar to reflect the
        current number of files in the application's file collection.
        Attempts to use the initial file count update method with fallback
        handling for various application states.

        Update process:
        1. Call internal _update_initial_file_count() method
        2. Handle any errors gracefully with logging
        3. Ensure display consistency regardless of update success

        Error handling:
        File count updates may fail during application initialization
        or when file collections are in transition. Failures are handled
        gracefully without affecting other status bar functionality.

        Note:
            This method should be called whenever the file collection
            changes (files added, removed, directory changed, etc.).
            The actual file counting logic is delegated to internal methods.
        """
        self._update_initial_file_count()

    def show_progress(self, title, maximum=100):
        """Initiate progress tracking for long-running operations.

        Activates the progress display system including progress bar and
        activity indicator to provide comprehensive visual feedback during
        time-consuming operations.

        Args:
            title (str): Descriptive title for the operation being tracked.
                        Displayed in the status message area.
            maximum (int, optional): Maximum progress value for the operation.
                                   Defaults to 100 for percentage-based progress.

        Visual feedback activated:
        - Progress bar becomes visible and resets to 0
        - Activity indicator starts spinning animation
        - Status message displays the operation title
        - Progress components are properly sized and positioned

        Example:
            show_progress("Analyzing audio files", 100)
            show_progress("Exporting results", 50)  # Custom scale

        Note:
            Always pair with update_progress() calls and hide_progress()
            when the operation completes. The progress system expects
            regular updates to provide meaningful user feedback.
        """
        self.status_bar.show_progress(title, maximum)

    def update_progress(self, value, message=None):
        """Update progress tracking with current operation status.

        Updates the progress bar value and optionally changes the status
        message to reflect the current phase or state of the ongoing operation.

        Args:
            value (int): Current progress value (should be within 0 to maximum range
                        set by show_progress()).
            message (str, optional): Updated status message describing current
                                   operation phase or step. Defaults to None
                                   (keeps current message).

        Update behavior:
        - Progress bar value is updated immediately
        - Activity indicator continues spinning
        - Status message is updated if provided
        - Visual changes are immediately visible to user

        Example:
            update_progress(25, "Processing file 1 of 4")
            update_progress(50)  # Value only, keep current message
            update_progress(75, "Finalizing results")

        Note:
            Progress values should be within the range established by
            show_progress(). Values outside this range may cause unexpected
            visual behavior.
        """
        self.status_bar.update_progress(value, message)

    def hide_progress(self):
        """Complete progress tracking and restore normal status display.

        Terminates the progress tracking system by hiding progress components
        and restoring the status bar to its normal operational state.
        Should be called when any long-running operation completes.

        Cleanup actions:
        - Progress bar becomes invisible
        - Activity indicator stops animation and hides
        - Status message resets to ready state
        - Status bar returns to normal appearance

        Usage pattern:
            show_progress("Processing...", 100)
            # ... operation with update_progress() calls ...
            hide_progress()  # Always call when done

        Note:
            This method should always be called to complete progress tracking,
            whether the operation completed successfully or was cancelled.
            Failure to call this method leaves the UI in an inconsistent state.
        """
        self.status_bar.hide_progress()

    def update_file_info(self, filename=None, duration=None, size=None):
        """Update the current file information display with detailed metadata.

        Updates the file information display in the status bar with comprehensive
        details about the currently selected or active audio file. Information
        is formatted for optimal readability and user understanding.

        Args:
            filename (str, optional): Full path to the audio file.
                                    Only the basename is displayed. Defaults to None.
            duration (float, optional): Audio duration in seconds.
                                      Formatted appropriately for time display.
                                      Defaults to None.
            size (int, optional): File size in bytes.
                                Formatted as KB/MB for readability. Defaults to None.

        Display behavior:
        - Pass None for filename to clear all file information
        - Missing duration/size are gracefully omitted from display
        - Information is formatted with separators for easy reading
        - Display updates immediately when called

        Example:
            update_file_info("path/to/file.wav", 123.45, 2048000)
            update_file_info("file.wav")  # Filename only
            update_file_info()           # Clear display

        Note:
            This method delegates to the underlying ModernStatusBar for
            consistent formatting and display behavior.
        """
        self.status_bar.update_file_info(filename, duration, size)

    def get_status_bar(self):
        """Get direct reference to the managed ModernStatusBar widget.

        Provides access to the underlying status bar widget for advanced
        customization or direct manipulation when the high-level interface
        is insufficient.

        Returns:
            ModernStatusBar: The managed status bar widget instance.
                           Can be used for direct widget operations,
                           custom styling, or advanced signal connections.

        Example:
            status_bar = manager.get_status_bar()
            status_bar.setStyleSheet("custom styling")
            custom_widget = QLabel("Custom")
            status_bar.addPermanentWidget(custom_widget)

        Note:
            Direct manipulation of the status bar should be done carefully
            to avoid conflicts with the manager's automatic operations.
            Prefer using the manager's high-level methods when possible.
        """
        return self.status_bar


class ApplicationStylist:
    """Professional application styling manager with modern design principles.

    Features: - Modern flat design with subtle gradients - Consistent color scheme with
    brand colors - Professional typography - Responsive components - Dark/Light theme
    support - Accessibility considerations
    """

    # Color Palette
    COLORS = {
        # Primary colors
        "primary": "#2563eb",  # Professional blue
        "primary_hover": "#1d4ed8",
        "primary_pressed": "#1e40af",
        # Secondary colors
        "secondary": "#64748b",  # Slate gray
        "secondary_hover": "#475569",
        "secondary_pressed": "#334155",
        # Neutral colors
        "background": "#ffffff",
        "surface": "#f8fafc",
        "surface_elevated": "#f1f5f9",
        "border": "#e2e8f0",
        "divider": "#cbd5e1",
        # Text colors
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#64748b",
        "text_disabled": "#94a3b8",
        # Status colors
        "success": "#059669",
        "warning": "#d97706",
        "error": "#dc2626",
        "info": "#0284c7",
        # Interactive states
        "hover_overlay": "rgba(37, 99, 235, 0.1)",
        "active_overlay": "rgba(37, 99, 235, 0.2)",
        "focus_ring": "rgba(37, 99, 235, 0.3)",
        "input_background": "#ffffff",
        "selection_text": "#ffffff",
        "card_background": "#ffffff",
        "overlay_background": "rgba(255, 255, 255, 0.9)",
        "error_background": "#fef2f2",
        "error_border": "#fecaca",
        "success_background": "#f0fdf4",
        "success_border": "#bbf7d0",
        "danger_hover": "#b91c1c",
        "tooltip_background": "#0f172a",
        "tooltip_text": "#ffffff",
        "plot_background": "#ffffff",
    }

    @staticmethod
    def apply_complete_styling(app):
        """Apply comprehensive professional application styling."""
        # Set application font to modern system font
        font = QFont("Inter", 10)
        if not font.exactMatch():
            font = QFont("Segoe UI", 10)  # Windows fallback
        if not font.exactMatch():
            font = QFont("SF Pro Display", 10)  # macOS fallback
        if not font.exactMatch():
            font = QFont("Ubuntu", 10)  # Linux fallback

        app.setFont(font)

        # Apply complete stylesheet
        stylesheet = ApplicationStylist._get_complete_stylesheet()
        app.setStyleSheet(stylesheet)

        # Set application palette for consistent theming
        palette = ApplicationStylist._create_application_palette()
        app.setPalette(palette)

    @staticmethod
    def _create_application_palette():
        """Create a professional application color palette."""
        palette = QPalette()

        # Window colors
        palette.setColor(
            QPalette.Window, QColor(ApplicationStylist.COLORS["background"])
        )
        palette.setColor(
            QPalette.WindowText, QColor(ApplicationStylist.COLORS["text_primary"])
        )

        # Base colors (input fields)
        palette.setColor(
            QPalette.Base, QColor(ApplicationStylist.COLORS["input_background"])
        )
        palette.setColor(
            QPalette.AlternateBase, QColor(ApplicationStylist.COLORS["surface"])
        )

        # Text colors
        palette.setColor(
            QPalette.Text, QColor(ApplicationStylist.COLORS["text_primary"])
        )
        palette.setColor(
            QPalette.BrightText, QColor(ApplicationStylist.COLORS["selection_text"])
        )

        # Button colors
        palette.setColor(QPalette.Button, QColor(ApplicationStylist.COLORS["surface"]))
        palette.setColor(
            QPalette.ButtonText, QColor(ApplicationStylist.COLORS["text_primary"])
        )

        # Highlight colors
        palette.setColor(
            QPalette.Highlight, QColor(ApplicationStylist.COLORS["primary"])
        )
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))

        return palette

    @staticmethod
    def _get_complete_stylesheet():
        """Get comprehensive professional stylesheet."""
        return f"""
        /* ====================================================================
           PROFESSIONAL APPLICATION STYLESHEET
           Modern, clean design with consistent branding and accessibility
        ==================================================================== */

        /* === ROOT STYLING === */
        QWidget {{
            background-color: {ApplicationStylist.COLORS['background']};
            color: {ApplicationStylist.COLORS['text_primary']};
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
        }}

        /* === TYPOGRAPHY === */
        QLabel {{
            color: {ApplicationStylist.COLORS['text_primary']};
            font-size: 11pt;
            font-weight: 500;
            line-height: 1.4;
        }}

        QLabel[class="heading-1"] {{
            font-size: 24pt;
            font-weight: 700;
            color: {ApplicationStylist.COLORS['text_primary']};
            margin: 16px 0px 12px 0px;
        }}

        QLabel[class="heading-2"] {{
            font-size: 18pt;
            font-weight: 600;
            color: {ApplicationStylist.COLORS['text_primary']};
            margin: 12px 0px 8px 0px;
        }}

        QLabel[class="heading-3"] {{
            font-size: 14pt;
            font-weight: 600;
            color: {ApplicationStylist.COLORS['text_primary']};
            margin: 8px 0px 6px 0px;
        }}

        QLabel[class="subtitle"] {{
            font-size: 12pt;
            font-weight: 400;
            color: {ApplicationStylist.COLORS['text_secondary']};
            margin: 4px 0px;
        }}

        QLabel[class="caption"] {{
            font-size: 10pt;
            font-weight: 400;
            color: {ApplicationStylist.COLORS['text_muted']};
        }}

        /* === BUTTONS === */
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['primary']},
                stop:1 {ApplicationStylist.COLORS['primary_hover']});
            color: {ApplicationStylist.COLORS['selection_text']};
            border: none;
            border-radius: 8px;
            padding: 6px 6px;
            font-size: 11pt;
            font-weight: 600;
            min-height: 16px;
            outline: none;
            text-transform: none;
        }}

        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['primary_hover']},
                stop:1 {ApplicationStylist.COLORS['primary_pressed']});
        }}

        QPushButton:pressed {{
            background: {ApplicationStylist.COLORS['primary_pressed']};
        }}

        QPushButton:focus {{
            border: 2px solid {ApplicationStylist.COLORS['focus_ring']};
        }}

        QPushButton:disabled {{
            background: {ApplicationStylist.COLORS['text_disabled']};
            color: {ApplicationStylist.COLORS['background']};
        }}

        /* Secondary Button Style */
        QPushButton[class="secondary"] {{
            background: {ApplicationStylist.COLORS['surface']};
            color: {ApplicationStylist.COLORS['text_primary']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
        }}

        QPushButton[class="secondary"]:hover {{
            background: {ApplicationStylist.COLORS['surface_elevated']};
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        /* Danger Button Style */
        QPushButton[class="danger"] {{
            background: {ApplicationStylist.COLORS['error']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        QPushButton[class="danger"]:hover {{
            background: {ApplicationStylist.COLORS['danger_hover']};
        }}

        /* === INPUT FIELDS === */
        QLineEdit {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 2px 16px;
            font-size: 11pt;
            color: {ApplicationStylist.COLORS['text_primary']};
            selection-background-color: {ApplicationStylist.COLORS['primary']};
        }}

        QLineEdit:focus {{
            border-color: {ApplicationStylist.COLORS['primary']};
            background-color: {ApplicationStylist.COLORS['input_background']};
            outline: none;
        }}

        QLineEdit:disabled {{
            background-color: {ApplicationStylist.COLORS['surface']};
            color: {ApplicationStylist.COLORS['text_disabled']};
            border-color: {ApplicationStylist.COLORS['divider']};
        }}

        QLineEdit[class="error"] {{
            border-color: {ApplicationStylist.COLORS['error']};
        }}

        /* === TEXT AREAS === */
        QTextEdit, QPlainTextEdit {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 12px;
            font-size: 11pt;
            color: {ApplicationStylist.COLORS['text_primary']};
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            line-height: 1.5;
        }}

        QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        /* === COMBO BOXES === */
        QComboBox {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 2px 16px;
            font-size: 11pt;
            color: {ApplicationStylist.COLORS['text_primary']};
            min-height: 20px;
        }}

        QComboBox:hover {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QComboBox:focus {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 32px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 8px solid {ApplicationStylist.COLORS['text_secondary']};
            margin-right: 8px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
            padding: 4px;
        }}

        /* === TABLES === */
        QTableWidget {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            alternate-background-color: {ApplicationStylist.COLORS['surface']};
            gridline-color: {ApplicationStylist.COLORS['divider']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            font-size: 10pt;
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
        }}

        QTableWidget::item {{
            padding: 1px 1px;
            border-bottom: 1px solid {ApplicationStylist.COLORS['divider']};
        }}

        QTableWidget::item:selected {{
            background-color: {ApplicationStylist.COLORS['primary']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        QHeaderView::section {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface_elevated']},
                stop:1 {ApplicationStylist.COLORS['surface']});
            color: {ApplicationStylist.COLORS['text_primary']};
            padding: 1px 8px;
            border: none;
            border-bottom: 2px solid {ApplicationStylist.COLORS['border']};
            font-weight: 600;
            font-size: 10pt;
            text-align: left;
        }}

        QHeaderView::section:hover {{
            background-color: {ApplicationStylist.COLORS['surface_elevated']};
        }}

        /* === LISTS === */
        QListWidget {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            font-size: 11pt;
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
            outline: none;
        }}

        QListWidget::item {{
            padding: 4px 16px;
            border-bottom: 1px solid {ApplicationStylist.COLORS['divider']};
            border-radius: 4px;
            margin: 1px;
        }}

        QListWidget::item:hover {{
            background-color: {ApplicationStylist.COLORS['hover_overlay']};
        }}

        QListWidget::item:selected {{
            background-color: {ApplicationStylist.COLORS['primary']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        /* === TREE WIDGETS === */
        QTreeWidget {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            font-size: 11pt;
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
            outline: none;
        }}

        QTreeWidget::item {{
            padding: 8px 4px;
            border-bottom: 1px solid {ApplicationStylist.COLORS['divider']};
        }}

        QTreeWidget::item:hover {{
            background-color: {ApplicationStylist.COLORS['hover_overlay']};
        }}

        QTreeWidget::item:selected {{
            background-color: {ApplicationStylist.COLORS['primary']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        /* === SCROLL BARS === */
        QScrollBar:vertical {{
            background-color: {ApplicationStylist.COLORS['surface']};
            width: 12px;
            border-radius: 6px;
            margin: 0px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {ApplicationStylist.COLORS['text_muted']};
            border-radius: 6px;
            min-height: 20px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {ApplicationStylist.COLORS['text_secondary']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {ApplicationStylist.COLORS['surface']};
            height: 12px;
            border-radius: 6px;
            margin: 0px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {ApplicationStylist.COLORS['text_muted']};
            border-radius: 6px;
            min-width: 20px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {ApplicationStylist.COLORS['text_secondary']};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* === TAB WIDGETS === */
        QTabWidget::pane {{
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            background-color: {ApplicationStylist.COLORS['input_background']};
            margin-top: -2px;
        }}

        QTabBar::tab {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface']},
                stop:1 {ApplicationStylist.COLORS['surface_elevated']});
            color: {ApplicationStylist.COLORS['text_secondary']};
            padding: 12px 24px;
            margin-right: 2px;
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: 500;
        }}

        QTabBar::tab:selected {{
            background: white;
            color: {ApplicationStylist.COLORS['primary']};
            border-color: {ApplicationStylist.COLORS['primary']};
            border-bottom: 2px solid white;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {ApplicationStylist.COLORS['hover_overlay']};
        }}

        /* === MENU BAR === */
        QMenuBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface_elevated']},
                stop:1 {ApplicationStylist.COLORS['surface']});
            border-bottom: 2px solid {ApplicationStylist.COLORS['border']};
            color: {ApplicationStylist.COLORS['text_primary']};
            font-size: 11pt;
            font-weight: 500;
            padding: 4px 0px;
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 8px 16px;
            border-radius: 6px;
            margin: 2px;
        }}

        QMenuBar::item:selected {{
            background-color: {ApplicationStylist.COLORS['primary']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        QMenuBar::item:pressed {{
            background-color: {ApplicationStylist.COLORS['primary_pressed']};
        }}

        /* === MENUS === */
        QMenu {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 8px;
            font-size: 11pt;
        }}

        QMenu::item {{
            background: transparent;
            padding: 8px 32px 8px 16px;
            border-radius: 6px;
            margin: 2px 0px;
        }}

        QMenu::item:selected {{
            background-color: {ApplicationStylist.COLORS['primary']};
            color: {ApplicationStylist.COLORS['selection_text']};
        }}

        QMenu::separator {{
            height: 2px;
            background-color: {ApplicationStylist.COLORS['divider']};
            margin: 8px 0px;
            border-radius: 1px;
        }}

        QMenu::indicator {{
            width: 16px;
            height: 16px;
            margin-left: 4px;
        }}

        /* === STATUS BAR === */
        QStatusBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface_elevated']},
                stop:1 {ApplicationStylist.COLORS['surface']});
            border-top: 2px solid {ApplicationStylist.COLORS['border']};
            color: {ApplicationStylist.COLORS['text_secondary']};
            font-size: 10pt;
            padding: 4px 8px;
        }}

        QStatusBar::item {{
            border: none;
            padding: 4px 8px;
        }}

        QStatusBar QLabel {{
            color: {ApplicationStylist.COLORS['text_secondary']};
            font-size: 10pt;
            margin: 0px 4px;
        }}

        /* === PROGRESS BARS === */
        QProgressBar {{
            background-color: {ApplicationStylist.COLORS['surface']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            text-align: center;
            font-weight: 600;
            color: {ApplicationStylist.COLORS['text_primary']};
        }}

        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ApplicationStylist.COLORS['primary']},
                stop:1 {ApplicationStylist.COLORS['primary_hover']});
            border-radius: 6px;
            margin: 2px;
        }}

        /* === DIALOG STYLING === */
        QDialog {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 12px;
        }}

        QDialog QLabel {{
            color: {ApplicationStylist.COLORS['text_primary']};
        }}

        QDialog QPushButton {{
            min-width: 100px;
        }}

        /* === SLIDER STYLING === */
        QSlider::groove:horizontal {{
            border: none;
            height: 6px;
            background: {ApplicationStylist.COLORS['text_muted']};
            border-radius: 3px;
        }}

        QSlider::handle:horizontal {{
            background: {ApplicationStylist.COLORS['primary']};
            border: 2px solid white;
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 1px;
        }}

        QSlider::handle:horizontal:hover {{
            background: {ApplicationStylist.COLORS['primary_hover']};
        }}

        QSlider::sub-page:horizontal {{
            background: {ApplicationStylist.COLORS['primary']};
            border-radius: 3px;
        }}

        /* === CHECKBOX STYLING === */
        QCheckBox {{
            spacing: 8px;
            color: {ApplicationStylist.COLORS['text_primary']};
            font-size: 11pt;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 4px;
            background-color: {ApplicationStylist.COLORS['input_background']};
        }}

        QCheckBox::indicator:hover {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QCheckBox::indicator:checked {{
            background-color: {ApplicationStylist.COLORS['primary']};
            border-color: {ApplicationStylist.COLORS['primary']};
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMSAxTDQuNSA3LjUgMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
        }}

        /* === RADIO BUTTON STYLING === */
        QRadioButton {{
            spacing: 8px;
            color: {ApplicationStylist.COLORS['text_primary']};
            font-size: 11pt;
        }}

        QRadioButton::indicator {{
            width: 8px;
            height: 8px;
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 6px;
            background-color: {ApplicationStylist.COLORS['input_background']};
        }}

        QRadioButton::indicator:hover {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QRadioButton::indicator:checked {{
            background-color: {ApplicationStylist.COLORS['primary']};
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        /* === SPIN BOX STYLING === */
        QSpinBox, QDoubleSpinBox {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 11pt;
            color: {ApplicationStylist.COLORS['text_primary']};
        }}

        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            background: {ApplicationStylist.COLORS['surface']};
            border: none;
            border-radius: 4px;
            width: 24px;
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
            background: {ApplicationStylist.COLORS['primary']};
        }}

        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background: {ApplicationStylist.COLORS['surface']};
            border: none;
            border-radius: 4px;
            width: 24px;
        }}

        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background: {ApplicationStylist.COLORS['primary']};
        }}

        /* === TOOL BAR STYLING === */
        QToolBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface_elevated']},
                stop:1 {ApplicationStylist.COLORS['surface']});
            border: none;
            border-bottom: 2px solid {ApplicationStylist.COLORS['border']};
            spacing: 4px;
            padding: 4px;
        }}

        QToolBar::separator {{
            background-color: {ApplicationStylist.COLORS['divider']};
            width: 2px;
            margin: 4px 8px;
        }}

        QToolButton {{
            background: transparent;
            border: none;
            border-radius: 6px;
            padding: 8px;
            color: {ApplicationStylist.COLORS['text_secondary']};
        }}

        QToolButton:hover {{
            background-color: {ApplicationStylist.COLORS['hover_overlay']};
            color: {ApplicationStylist.COLORS['primary']};
        }}

        QToolButton:pressed {{
            background-color: {ApplicationStylist.COLORS['active_overlay']};
        }}

        /* === MODERN AUDIO PLAYER STYLING === */
        QWidget[objectName="audio_player_widget"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['card_background']}, stop:1 {ApplicationStylist.COLORS['surface']});
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 12px;
            margin: 8px;
            padding: 8px;
        }}

        QWidget[objectName="audio_player_widget"] QPushButton {{
            background: {ApplicationStylist.COLORS['secondary']};
            color: {ApplicationStylist.COLORS['selection_text']};
            border: none;
            border-radius: 6px;
            padding: 8px;
            font-weight: 600;
            min-width: 8px;
            min-height: 8px;
            font-size: 10pt;
            margin: 2px;
        }}

        QWidget[objectName="audio_player_widget"] QPushButton:hover {{
            background: {ApplicationStylist.COLORS['secondary_hover']};
        }}

        QWidget[objectName="audio_player_widget"] QPushButton:pressed {{
            background: {ApplicationStylist.COLORS['secondary_pressed']};
        }}

        /* Time display styling */
        QWidget[objectName="audio_player_widget"] QLabel[objectName="time_display"] {{
            font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", monospace;
            font-size: 10pt;
            font-weight: 600;
            color: {ApplicationStylist.COLORS['text_primary']};
            background: {ApplicationStylist.COLORS['surface_elevated']};
            border: 1px solid {ApplicationStylist.COLORS['border']};
            border-radius: 6px;
            padding: 6px 12px;
            margin: 4px;
            min-height: 20px;
            letter-spacing: 0.5px;
            qproperty-alignment: AlignCenter;
        }}

        /* Volume control styling */
        QWidget[objectName="audio_player_widget"] QLabel[text="♪"] {{
            font-size: 16pt;
            font-weight: 500;
            color: {ApplicationStylist.COLORS['primary']};
            background: transparent;
            border: none;
            padding: 8px;
            min-height: 32px;
            text-align: center;
        }}

        /* === TAG COMPLETER STYLING === */
        QWidget[objectName="tag_completer"] {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 12px;
            padding: 8px;
        }}

        QWidget[objectName="tag_completer"] QLineEdit {{
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            padding: 12px 16px;
            background-color: {ApplicationStylist.COLORS['input_background']};
            font-size: 11pt;
        }}

        QWidget[objectName="tag_completer"] QLineEdit:focus {{
            border-color: {ApplicationStylist.COLORS['primary']};
            background-color: {ApplicationStylist.COLORS['input_background']};
        }}

        QWidget[objectName="tag_completer"] QListWidget {{
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            background-color: {ApplicationStylist.COLORS['input_background']};
            selection-background-color: {ApplicationStylist.COLORS['primary']};
            selection-color: {ApplicationStylist.COLORS['selection_text']};
            margin-top: 4px;
        }}

        QWidget[objectName="tag_completer"] QListWidget::item {{
            padding: 12px 16px;
            border-bottom: 1px solid {ApplicationStylist.COLORS['divider']};
            border-radius: 4px;
            margin: 2px;
        }}

        QWidget[objectName="tag_completer"] QListWidget::item:hover {{
            background-color: {ApplicationStylist.COLORS['hover_overlay']};
        }}

        /* === NOTIFICATION STYLING === */
        QWidget[class="notification"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['card_background']}, stop:1 {ApplicationStylist.COLORS['surface']});
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-left: 4px solid {ApplicationStylist.COLORS['primary']};
            border-radius: 8px;
            padding: 16px;
            margin: 8px;
        }}

        QWidget[class="notification-success"] {{
            border-left-color: {ApplicationStylist.COLORS['success']};
        }}

        QWidget[class="notification-warning"] {{
            border-left-color: {ApplicationStylist.COLORS['warning']};
        }}

        QWidget[class="notification-error"] {{
            border-left-color: {ApplicationStylist.COLORS['error']};
        }}

        QWidget[class="notification-info"] {{
            border-left-color: {ApplicationStylist.COLORS['info']};
        }}

        /* === CARD STYLING === */
        QWidget[class="card"] {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 12px;
            padding: 20px;
            margin: 8px;
        }}

        QWidget[class="card"]:hover {{
            border-color: {ApplicationStylist.COLORS['primary']};
        }}

        QWidget[class="card-elevated"] {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 1px solid {ApplicationStylist.COLORS['divider']};
            border-radius: 12px;
            padding: 20px;
            margin: 8px;
        }}

        /* === TOOLTIP STYLING === */
        QToolTip {{
            background-color: {ApplicationStylist.COLORS['tooltip_background']};
            color: {ApplicationStylist.COLORS['tooltip_text']};
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 10pt;
            font-weight: 500;
            opacity: 220;
        }}

        /* === GROUP BOX STYLING === */
        QGroupBox {{
            font-size: 12pt;
            font-weight: 600;
            color: {ApplicationStylist.COLORS['text_primary']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px 0 8px;
            background-color: {ApplicationStylist.COLORS['input_background']};
            color: {ApplicationStylist.COLORS['primary']};
        }}

        /* === SPLITTER STYLING === */
        QSplitter::handle {{
            background-color: {ApplicationStylist.COLORS['border']};
            border-radius: 2px;
        }}

        QSplitter::handle:horizontal {{
            width: 4px;
            margin: 4px 0px;
        }}

        QSplitter::handle:vertical {{
            height: 4px;
            margin: 0px 4px;
        }}

        QSplitter::handle:hover {{
            background-color: {ApplicationStylist.COLORS['primary']};
        }}

        /* === DOCK WIDGET STYLING === */
        QDockWidget {{
            background-color: {ApplicationStylist.COLORS['input_background']};
            border: 2px solid {ApplicationStylist.COLORS['border']};
            border-radius: 8px;
            titlebar-close-icon: none;
            titlebar-normal-icon: none;
        }}

        QDockWidget::title {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {ApplicationStylist.COLORS['surface_elevated']},
                stop:1 {ApplicationStylist.COLORS['surface']});
            color: {ApplicationStylist.COLORS['text_primary']};
            font-weight: 600;
            font-size: 11pt;
            padding: 12px;
            border-bottom: 2px solid {ApplicationStylist.COLORS['border']};
        }}

        /* === LOADING/SPINNER STYLING === */
        QWidget[class="loading-overlay"] {{
            background-color: {ApplicationStylist.COLORS['overlay_background']};
            border-radius: 8px;
        }}

        QLabel[class="loading-text"] {{
            color: {ApplicationStylist.COLORS['text_secondary']};
            font-size: 12pt;
            font-weight: 500;
            qproperty-alignment: AlignCenter;
        }}

        /* === ERROR STATE STYLING === */
        QWidget[class="error-state"] {{
            background-color: {ApplicationStylist.COLORS['error_background']};
            border: 2px solid {ApplicationStylist.COLORS['error_border']};
            border-radius: 8px;
            padding: 16px;
        }}

        QLabel[class="error-message"] {{
            color: {ApplicationStylist.COLORS['error']};
            font-weight: 500;
        }}

        /* === SUCCESS STATE STYLING === */
        QWidget[class="success-state"] {{
            background-color: {ApplicationStylist.COLORS['success_background']};
            border: 2px solid {ApplicationStylist.COLORS['success_border']};
            border-radius: 8px;
            padding: 16px;
        }}

        QLabel[class="success-message"] {{
            color: {ApplicationStylist.COLORS['success']};
            font-weight: 500;
        }}

        /* === EMPTY STATE STYLING === */
        QWidget[class="empty-state"] {{
            background-color: {ApplicationStylist.COLORS['surface']};
            border: 2px dashed {ApplicationStylist.COLORS['divider']};
            border-radius: 12px;
            padding: 32px;
        }}

        QLabel[class="empty-state-text"] {{
            color: {ApplicationStylist.COLORS['text_muted']};
            font-size: 14pt;
            font-weight: 500;
            qproperty-alignment: AlignCenter;
        }}

        QLabel[class="empty-state-subtitle"] {{
            color: {ApplicationStylist.COLORS['text_disabled']};
            font-size: 11pt;
            qproperty-alignment: AlignCenter;
            margin-top: 8px;
        }}
        """

    @staticmethod
    def get_audio_player_styles():
        """Get audio player specific styles with modern design."""
        return ApplicationStylist._get_complete_stylesheet()

    @staticmethod
    def get_menu_styles():
        """Get menu specific styles with professional appearance."""
        return ApplicationStylist._get_complete_stylesheet()

    @staticmethod
    def get_dialog_styles():
        """Get dialog specific styles with consistent theming."""
        return ApplicationStylist._get_complete_stylesheet()

    @staticmethod
    def get_theme_colors():
        """Get the current theme colors for programmatic access."""
        return ApplicationStylist.COLORS.copy()

    @staticmethod
    def apply_light_theme(app):
        light_colors = ApplicationStylist.COLORS.copy()
        ApplicationStylist.COLORS.update(light_colors)

        ApplicationStylist.apply_complete_styling(app)
        # Apply dark theme stylesheet
        # print("☀️ Light theme applied")

    @staticmethod
    def apply_dark_theme(app):
        """Apply dark theme variant (future enhancement)."""
        dark_colors = ApplicationStylist.COLORS.copy()
        dark_colors.update(
            {
                # Primary colors - brighter for dark theme
                "primary": "#3b82f6",
                "primary_hover": "#60a5fa",
                "primary_pressed": "#2563eb",
                # Secondary colors for dark
                "secondary": "#94a3b8",
                "secondary_hover": "#cbd5e1",
                "secondary_pressed": "#e2e8f0",
                # Dark backgrounds
                "background": "#0f0f23",  # Very dark navy
                "surface": "#1a1b3a",  # Dark surface
                "surface_elevated": "#252659",  # Elevated surface
                # Dark borders and dividers
                "border": "#374151",  # Subtle border
                "divider": "#4b5563",  # Visible divider
                # Dark text hierarchy
                "text_primary": "#f9fafb",  # Almost white
                "text_secondary": "#d1d5db",  # Light gray
                "text_muted": "#9ca3af",  # Muted gray
                "text_disabled": "#6b7280",  # Disabled gray
                # Status colors - adjusted for dark
                "success": "#10b981",
                "warning": "#f59e0b",
                "error": "#ef4444",
                "info": "#06b6d4",
                # Interactive states
                "hover_overlay": "rgba(59, 130, 246, 0.15)",
                "active_overlay": "rgba(59, 130, 246, 0.25)",
                "focus_ring": "rgba(96, 165, 250, 0.4)",
                "input_background": "#1a1b3a",
                "selection_text": "#f9fafb",
                "card_background": "#1a1b3a",
                "overlay_background": "rgba(26, 27, 58, 0.9)",
                "error_background": "#2d1b1b",
                "error_border": "#4a2525",
                "success_background": "#1b2d20",
                "success_border": "#254a2a",
                "danger_hover": "#dc2626",
                "tooltip_background": "#f9fafb",
                "tooltip_text": "#0f172a",
                "plot_background": "#1a1b3a",
            }
        )
        ApplicationStylist.COLORS.update(dark_colors)
        ApplicationStylist.apply_complete_styling(app)
        # Apply dark theme stylesheet
        # print("🌙 Dark theme applied")

    @staticmethod
    def apply_macos_dark_theme(app):
        """Apply macOS-style dark theme."""
        macos_dark_colors = ApplicationStylist.COLORS.copy()
        macos_dark_colors.update(
            {
                # Primary colors - macOS blue
                "primary": "#007AFF",  # macOS system blue
                "primary_hover": "#0051D5",
                "primary_pressed": "#003D99",
                # Secondary colors
                "secondary": "#8E8E93",  # macOS secondary label
                "secondary_hover": "#AEAEB2",
                "secondary_pressed": "#6D6D70",
                # macOS dark backgrounds
                "background": "#1C1C1E",  # macOS background
                "surface": "#2C2C2E",  # macOS secondary background
                "surface_elevated": "#3A3A3C",  # macOS tertiary background
                # macOS borders and dividers
                "border": "#38383A",  # macOS separator
                "divider": "#48484A",  # macOS opaque separator
                # macOS text hierarchy
                "text_primary": "#FFFFFF",  # macOS primary label
                "text_secondary": "#EBEBF5",  # macOS secondary label (60% opacity)
                "text_muted": "#EBEBF599",  # macOS tertiary label (38% opacity)
                "text_disabled": "#EBEBF54D",  # macOS quaternary label (18% opacity)
                # macOS status colors
                "success": "#30D158",  # macOS green
                "warning": "#FF9F0A",  # macOS orange
                "error": "#FF453A",  # macOS red
                "info": "#64D2FF",  # macOS light blue
                # Interactive states
                "hover_overlay": "rgba(0, 122, 255, 0.1)",
                "active_overlay": "rgba(0, 122, 255, 0.2)",
                "focus_ring": "rgba(0, 122, 255, 0.4)",
                # Component backgrounds
                "input_background": "#2C2C2E",
                "selection_text": "#FFFFFF",
                "card_background": "#2C2C2E",
                "overlay_background": "rgba(44, 44, 46, 0.9)",
                "error_background": "#2C1B1B",
                "error_border": "#4A2525",
                "success_background": "#1B2C20",
                "success_border": "#254A2A",
                "danger_hover": "#FF453A",
                "tooltip_background": "#EBEBF5",
                "tooltip_text": "#1C1C1E",
                "plot_background": "#2C2C2E",
            }
        )

        ApplicationStylist.COLORS.update(macos_dark_colors)
        ApplicationStylist.apply_complete_styling(app)
        # print("🍎 macOS Dark theme applied")

    @staticmethod
    def set_custom_theme(app, color_overrides):
        """Allow custom theme colors while maintaining design consistency."""
        custom_colors = ApplicationStylist.COLORS.copy()
        custom_colors.update(color_overrides)

        # Regenerate stylesheet with custom colors
        logger.info("Custom theme applied")

    @staticmethod
    def get_component_styles(component_name):
        """Get specific component styles for targeted styling."""
        component_styles = {
            "button": f"""
                QPushButton {{
                    background: {ApplicationStylist.COLORS['primary']};
                    color: {ApplicationStylist.COLORS['selection_text']};
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: 600;
                }}
            """,
            "input": f"""
                QLineEdit {{
                    border: 2px solid {ApplicationStylist.COLORS['border']};
                    border-radius: 8px;
                    padding: 12px 16px;
                    font-size: 11pt;
                }}
            """,
            "table": f"""
                QTableWidget {{
                    border: 2px solid {ApplicationStylist.COLORS['border']};
                    border-radius: 8px;
                    selection-background-color: {ApplicationStylist.COLORS['primary']};
                }}
            """,
        }

        return component_styles.get(component_name, "")


class UIComponentManager:
    """Main coordinator for all UI components.

    This class brings together all UI component managers to provide a unified interface
    for MainWindow.
    """

    def __init__(self, main_window):
        """Initialize UI component manager."""
        self.main_window = main_window

        # Initialize component managers
        self.status_manager = StatusBarManager(main_window)

        # print("🎨 UIComponentManager initialized")

    def get_status_manager(self):
        """Get status bar manager."""
        return self.status_manager

    def show_message(self, message, timeout=3000):
        """Delegate to status manager."""
        self.status_manager.show_message(message, timeout)

    ####
    def update_file_count(self):
        """Delegate to main window command interface."""
        try:
            count = len(self.main_window.file_manager.get_all_wav_files())
            self.status_manager.status_bar.update_file_count(count)
            return True
        except Exception as e:
            logger.warning(f"Fallback file count update failed: {e}")
            return False

    ####
    def show_progress(self, title, maximum=100):
        """Delegate to status manager."""
        self.status_manager.show_progress(title, maximum)

    def update_progress(self, value, message=None):
        """Delegate to status manager."""
        self.status_manager.update_progress(value, message)

    def hide_progress(self):
        """Delegate to status manager."""
        self.status_manager.hide_progress()
