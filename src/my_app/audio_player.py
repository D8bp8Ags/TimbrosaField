"""Enhanced AudioPlayer Class with Volume Toast Feedback.

This module provides a comprehensive audio player widget specifically designed for
field recording applications. It features professional-grade audio controls,
global keyboard shortcuts, visual volume feedback, and precise time displays.

The audio player supports various audio formats and provides both GUI controls
and keyboard shortcuts for common operations like play/pause, seeking, and
volume adjustment. Visual feedback includes a toast notification system for
volume changes and comprehensive time displays with millisecond precision.

Classes:
    VolumeToast: Temporary volume indicator overlay widget
    AudioPlayer: Main enhanced audio player widget with controls

Features:
    - Play/pause/stop audio playback controls
    - Position seeking with visual slider feedback
    - Volume control with toast notification overlay
    - Global keyboard shortcuts for common operations
    - Time display with millisecond precision (MM:SS.mmm format)
    - PyQt5 signals for integration with parent applications
    - Support for various audio formats via QMediaPlayer
"""

import logging
import os

from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QWidget,
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


class VolumeToast(QLabel):
    """Temporary volume indicator overlay widget.

    A toast-style notification widget that displays volume level changes with
    appropriate icons and percentage values. The widget automatically positions
    itself in the center of its parent and disappears after a configurable timeout.

    The toast uses visual indicators (emoji icons) that correspond to different
    volume levels and provides immediate visual feedback for volume adjustments.

    Attributes:
        hide_timer (QTimer): Timer for automatically hiding the toast after display

    Args:
        parent (QWidget): Parent widget that will contain the toast overlay
    """

    def __init__(self, parent):
        """Initialize the volume toast widget.

        Sets up the toast with appropriate styling, size, positioning, and
        auto-hide timer functionality. The widget is initially hidden and
        configured with a semi-transparent dark background.

        Args:
            parent (QWidget): Parent widget for the toast overlay
        """
        super().__init__(parent)
        self.setFixedSize(120, 40)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            """QLabel { background-color: rgba(0, 0, 0, 180); color: white; border-
            radius: 8px; font-size: 14pt; font-weight: bold; padding: 8px; border: 2px
            solid rgba(255, 255, 255, 100); }
            """
        )
        self.hide()

        # Timer to hide toast
        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.hide)
        self.hide_timer.setSingleShot(True)

    def show_volume(self, volume):
        """Display volume with icon and percentage.

        Shows the toast with appropriate volume icon and percentage text,
        positions it in the center of the parent widget, and starts the
        auto-hide timer.

        Volume icons:
        - 🔇 for muted (0%)
        - 🔉 for low volume (1-29%)
        - 🔊 for medium and high volume (30%+)

        Args:
            volume (int): Volume level from 0-100
        """
        if volume == 0:
            icon = "🔇"
        elif volume < 30:
            icon = "🔉"
        elif volume < 70:
            icon = "🔊"
        else:
            icon = "🔊"

        self.setText(f"{icon} {volume}%")

        # Position in center of parent
        parent_rect = self.parent().rect()
        x = (parent_rect.width() - self.width()) // 2
        y = (parent_rect.height() - self.height()) // 2
        self.move(x, y)

        self.show()
        self.raise_()  # Ensure it appears on top

        # Hide after 1.5 seconds
        self.hide_timer.start(1500)


class AudioPlayer(QWidget):
    """Enhanced audio player widget with global keyboard shortcuts and volume feedback.

    A comprehensive audio playback widget designed for professional field recording
    applications. Provides full playback control, visual feedback, and keyboard shortcuts
    for efficient audio analysis and review workflows.

    The widget integrates seamlessly with parent applications through PyQt5 signals
    and provides both programmatic and user-interface control methods.

    Features:
        - Complete playback controls (play/pause/stop)
        - Position seeking with millisecond precision
        - Volume control with visual toast feedback
        - Global keyboard shortcuts for hands-free operation
        - Time display in MM:SS.mmm format
        - Real-time position and duration tracking
        - State change notifications via signals

    Attributes:
        player (QMediaPlayer): Core audio playback engine
        volume_toast (VolumeToast): Volume feedback overlay (lazy-initialized)
        play_button (QPushButton): Play/pause control button
        stop_button (QPushButton): Stop playback button
        position_slider (QSlider): Position seeking control
        volume_slider (QSlider): Volume adjustment control
        time_label (QLabel): Time display (current/total)

    Signals:
        positionChanged (int): Emitted when playback position changes (milliseconds)
        durationChanged (int): Emitted when audio duration is determined (milliseconds)
        stateChanged (QMediaPlayer.State): Emitted when playback state changes
        volumeChanged (int): Emitted when volume changes (0-100)

    Args:
        parent (QWidget, optional): Parent widget. Defaults to None.
    """

    # Custom signals for communication with parent widgets
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(object)  # QMediaPlayer.State
    volumeChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        """Initialize AudioPlayer widget.

        Sets up the complete audio player interface including media player engine,
        UI components, keyboard shortcuts, and signal connections. Initializes
        with default settings and prepares for audio file loading.

        Args:
            parent (QWidget, optional): Parent widget for the audio player.
                Defaults to None.
        """
        super().__init__(parent)

        # Setup media player
        self.player = QMediaPlayer()
        self.player.setNotifyInterval(50)  # 20fps updates for smooth playback

        # Connect internal signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.stateChanged.connect(self._on_state_changed)

        # Initialize UI
        self._setup_ui()

        # Setup global shortcuts
        self._setup_shortcuts()

        # Initialize volume toast (lazily initialized)
        self.volume_toast = None

        # Initial state
        self._current_filepath = None

    def _setup_ui(self):
        """Setup the user interface components.

        Creates and configures all UI elements including playback controls,
        position slider, volume control, and time display. Sets up the main
        horizontal layout with appropriate spacing and styling.

        UI Components created:
        - Play/pause button with dynamic icon
        - Stop button with tooltip
        - Position slider for seeking
        - Volume slider with icon
        - Time display label with current/total format
        """
        # Container styling
        self.setObjectName("audio_player_widget")

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Play/Pause button
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setToolTip("Play/Pause (Spacebar)")
        self.play_button.clicked.connect(self.toggle_playback)
        layout.addWidget(self.play_button)

        # Stop button
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.setToolTip("Stop (Esc)")
        self.stop_button.clicked.connect(self.stop_playback)
        layout.addWidget(self.stop_button)

        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.sliderMoved.connect(self.seek_to_position)
        self.position_slider.setToolTip("Seek position (←/→ for ±10sec)")
        layout.addWidget(self.position_slider, stretch=4)

        # Volume control
        volume_label = QLabel("♪")
        volume_label.setFixedWidth(12)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(60)
        self.volume_slider.setToolTip("Volume (-/+ for ±10)")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(volume_label)
        layout.addWidget(self.volume_slider)

        # Time display
        self.time_label = QLabel("00:00.000/00:00.000")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setFixedWidth(150)
        layout.addWidget(self.time_label)

    def _setup_shortcuts(self):
        """Setup global keyboard shortcuts.

        Configures keyboard shortcuts for common playback operations.
        Currently commented out but designed to provide:
        - Spacebar: Play/pause toggle
        - Escape: Stop playback
        - Left/Right arrows: Seek backward/forward (10 seconds)
        - +/- keys: Volume up/down (10% increments)
        - M key: Mute toggle

        Note:
            Shortcut implementation is currently disabled in code.
        """
        # print("🎹 AudioPlayer: Installing global shortcuts...")
        """
        parent_window = self.window() if self.window() else self.parent()
        if parent_window is None:
            print("❌ No parent window found for shortcuts")
            return

        # Space = Play/Pause
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), parent_window)
        self.space_shortcut.activated.connect(self.toggle_playback)

        # Escape = Stop
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), parent_window)
        self.escape_shortcut.activated.connect(self.stop_playback)

        # Left/Right for seek (10 seconds)
        self.seek_back_shortcut = QShortcut(QKeySequence(Qt.Key_Left), parent_window)
        self.seek_back_shortcut.activated.connect(self.seek_backward)

        self.seek_forward_shortcut = QShortcut(QKeySequence(Qt.Key_Right), parent_window)
        self.seek_forward_shortcut.activated.connect(self.seek_forward)

        # Up/Down for volume
        self.volume_up_shortcut = QShortcut(QKeySequence(Qt.Key_Equal), parent_window)
        self.volume_up_shortcut.activated.connect(self.volume_up)

        self.volume_down_shortcut = QShortcut(QKeySequence(Qt.Key_Minus), parent_window)
        self.volume_down_shortcut.activated.connect(self.volume_down)

        # M for mute toggle
        self.mute_shortcut = QShortcut(QKeySequence(Qt.Key_M), parent_window)
        self.mute_shortcut.activated.connect(self.toggle_mute)
        """

    def _ensure_volume_toast(self):
        """Create volume toast if it doesn't exist yet.

        Lazy initialization of the volume toast overlay. Creates the VolumeToast
        widget using the parent window as the container. This method ensures the
        toast is only created when needed and properly attached to a parent window.

        Note:
            The toast widget requires a valid parent window for proper positioning
            and display functionality.
        """
        if self.volume_toast is None:
            # Find the parent window for the overlay
            parent_window = self.window()
            if parent_window:
                self.volume_toast = VolumeToast(parent_window)
                print("🍞 Volume toast created")
            else:
                print("❌ No parent window found for volume toast")

    # === PUBLIC API METHODS ===

    def load_file(self, filepath):
        """Load audio file for playback.

        Validates the file path and loads the audio file into the media player.
        Sets up the media content and stores the current file path for reference.

        Args:
            filepath (str): Path to the audio file to load

        Returns:
            bool: True if file loaded successfully, False otherwise

        Note:
            The file path is converted to an absolute path and validated for
            existence before loading into the QMediaPlayer.
        """
        try:
            if not os.path.exists(filepath):
                print(f"❌ Audio file not found: {filepath}")
                return False

            url = QUrl.fromLocalFile(os.path.abspath(filepath))
            self.player.setMedia(QMediaContent(url))
            self._current_filepath = filepath

            # print(f"🎵 Audio loaded: {os.path.basename(filepath)}")
            return True

        except Exception as e:
            print(f"❌ Error loading audio: {e}")
            return False

    def play(self):
        """Start playback.

        Begins audio playback if a valid file is loaded and exists on disk.
        Validates file existence before attempting playback to prevent errors.

        Note:
            Will not start playback if no file is loaded or if the loaded
            file no longer exists on the filesystem.
        """
        if self._current_filepath and os.path.exists(self._current_filepath):
            self.player.play()
        else:
            print("❌ No audio file loaded or file not found")

    def pause(self):
        """Pause playback.

        Pauses the current audio playback, maintaining the current position. Playback
        can be resumed from the same position using play().
        """
        self.player.pause()

    def stop(self):
        """Stop playback.

        Stops audio playback and resets the position to the beginning. Unlike pause(),
        this resets the playback position to zero.
        """
        self.player.stop()

    def toggle_playback(self):
        """Toggle between play and pause.

        Switches between playing and paused states. If currently playing, pauses the
        audio. If paused or stopped, starts/resumes playback. This is the primary method
        for spacebar shortcut functionality.
        """
        print("🎵 Toggle playbook triggered")
        if self.player.state() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def toggle_mute(self):
        """Toggle mute state.

        Switches between muted (volume 0) and unmuted states. When muting, saves the
        current volume level and sets volume to 0. When unmuting, restores the
        previously saved volume level. Shows visual feedback through the volume toast
        notification.

        The pre-mute volume is stored in _pre_mute_volume attribute and defaults to 70
        if no previous volume was saved.
        """
        if not hasattr(self, "_pre_mute_volume"):
            self._pre_mute_volume = 70

        current_volume = self.volume_slider.value()

        if current_volume == 0:
            # Unmute - restore previous volume
            self.set_volume(self._pre_mute_volume)
            self._ensure_volume_toast()
            if self.volume_toast:
                self.volume_toast.show_volume(self._pre_mute_volume)
            print(f"🔊 Unmuted to {self._pre_mute_volume}%")
        else:
            # Mute - save current volume and set to 0
            self._pre_mute_volume = current_volume
            self.set_volume(0)
            self._ensure_volume_toast()
            if self.volume_toast:
                self.volume_toast.show_volume(0)
            print("🔇 Muted")

    def stop_playback(self):
        """Stop playback.

        Wrapper method for the stop() function, typically used by keyboard shortcuts and
        UI callbacks. Stops audio playback and resets position.
        """
        print("🛑 Stop playback triggered")
        self.stop()

    def seek_to_position(self, position_ms):
        """Seek to specific position.

        Sets the playback position to the specified time in milliseconds.
        The position is converted to integer to ensure compatibility with
        QMediaPlayer's setPosition method.

        Args:
            position_ms (float): Position in milliseconds to seek to
        """
        self.player.setPosition(int(position_ms))

    def set_volume(self, volume):
        """Set playback volume.

        Sets the audio volume level, clamping the value to the valid range
        of 0-100. Updates both the media player volume and the volume slider
        to maintain UI synchronization.

        Args:
            volume (int): Volume level (0-100). Values outside this range
                are automatically clamped.
        """
        volume = max(0, min(100, volume))  # Clamp to valid range
        self.player.setVolume(volume)
        if self.volume_slider.value() != volume:
            self.volume_slider.setValue(volume)

    # === SHORTCUT METHODS WITH VOLUME TOAST ===

    def seek_backward(self):
        """Seek 10 seconds backward.

        Moves the playback position 10 seconds earlier, clamped to the beginning of the
        audio (position 0). Only functions if an audio file is currently loaded.

        The seek amount is fixed at 10 seconds (10000 milliseconds).
        """
        if self._current_filepath:
            current_pos = self.player.position()
            new_pos = max(0, current_pos - 10000)  # 10 seconds = 10000ms
            self.seek_to_position(new_pos)
            print(f"⏪ Seeking backward to {new_pos/1000:.1f}s")

    def seek_forward(self):
        """Seek 10 seconds forward.

        Moves the playback position 10 seconds later, clamped to the end of the audio
        file (total duration). Only functions if an audio file is currently loaded.

        The seek amount is fixed at 10 seconds (10000 milliseconds).
        """
        if self._current_filepath:
            current_pos = self.player.position()
            duration = self.player.duration()
            new_pos = min(duration, current_pos + 10000)  # 10 seconds forward
            self.seek_to_position(new_pos)
            print(f"⏩ Seeking forward to {new_pos/1000:.1f}s")

    def volume_up(self):
        """Increase volume by 10 with visual feedback.

        Increases the volume by 10%, clamped to maximum 100%. Shows visual feedback
        through the volume toast notification with appropriate icon and percentage
        display.

        The volume increment is fixed at 10% per call.
        """
        current = self.volume_slider.value()
        new_volume = min(100, current + 10)
        self.set_volume(new_volume)

        # Show volume toast
        self._ensure_volume_toast()
        if self.volume_toast:
            self.volume_toast.show_volume(new_volume)

        print(f"🔊 Volume: {new_volume}%")

    def volume_down(self):
        """Decrease volume by 10 with visual feedback.

        Decreases the volume by 10%, clamped to minimum 0%. Shows visual feedback
        through the volume toast notification with appropriate icon and percentage
        display.

        The volume decrement is fixed at 10% per call.
        """
        current = self.volume_slider.value()
        new_volume = max(0, current - 10)
        self.set_volume(new_volume)

        # Show volume toast
        self._ensure_volume_toast()
        if self.volume_toast:
            self.volume_toast.show_volume(new_volume)

        print(f"🔉 Volume: {new_volume}%")

    # === GETTER METHODS ===

    def get_volume(self):
        """Get current volume level.

        Returns:
            int: Current volume level from the media player (0-100)
        """
        return self.player.volume()

    def get_position(self):
        """Get current playback position.

        Returns:
            int: Current playback position in milliseconds
        """
        return self.player.position()

    def get_duration(self):
        """Get audio duration.

        Returns:
            int: Total audio duration in milliseconds. Returns 0 if no
                audio is loaded or duration is not yet determined.
        """
        return self.player.duration()

    def get_state(self):
        """Get current playback state.

        Returns:
            QMediaPlayer.State: Current playback state (PlayingState,
                PausedState, or StoppedState)
        """
        return self.player.state()

    def is_playing(self):
        """Check if audio is currently playing.

        Returns:
            bool: True if currently in playing state, False otherwise
        """
        return self.player.state() == QMediaPlayer.PlayingState

    def is_paused(self):
        """Check if audio is currently paused.

        Returns:
            bool: True if currently in paused state, False otherwise
        """
        return self.player.state() == QMediaPlayer.PausedState

    def is_stopped(self):
        """Check if audio is currently stopped.

        Returns:
            bool: True if currently in stopped state, False otherwise
        """
        return self.player.state() == QMediaPlayer.StoppedState

    # === INTERNAL EVENT HANDLERS ===

    def _on_position_changed(self, position):
        """Handle position changes from QMediaPlayer.

        Updates the time display and position slider when the playback
        position changes. Avoids updating the slider if the user is
        currently dragging it to prevent interference.

        Args:
            position (int): New position in milliseconds
        """
        self._update_time_display(position, self.player.duration())

        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)

        self.positionChanged.emit(position)

    def _on_duration_changed(self, duration):
        """Handle duration changes from QMediaPlayer.

        Updates the position slider range and time display when the audio
        duration becomes available. This typically occurs shortly after
        loading a new audio file.

        Args:
            duration (int): Audio duration in milliseconds
        """
        self.position_slider.setRange(0, duration)
        self._update_time_display(self.player.position(), duration)
        self.durationChanged.emit(duration)

    def _on_state_changed(self, state):
        """Handle state changes from QMediaPlayer.

        Updates the play button icon and tooltip based on the current
        playback state. Changes between play and pause icons dynamically.

        Args:
            state (QMediaPlayer.State): New playback state
        """
        if state == QMediaPlayer.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.play_button.setToolTip("Pause (Spacebar)")

        elif state == QMediaPlayer.PausedState or state == QMediaPlayer.StoppedState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.play_button.setToolTip("Play (Spacebar)")

        self.stateChanged.emit(state)

    def _on_volume_changed(self, volume):
        """Handle volume changes from volume slider.

        Updates the media player volume when the volume slider is moved
        and emits the volumeChanged signal for parent widget notification.

        Args:
            volume (int): New volume level (0-100)
        """
        self.player.setVolume(volume)
        self.volumeChanged.emit(volume)

    def _update_time_display(self, position, duration):
        """Update the time display label.

        Formats and displays the current position and total duration
        in MM:SS.mmm format (minutes:seconds.milliseconds).

        Args:
            position (int): Current position in milliseconds
            duration (int): Total duration in milliseconds
        """
        pos_time = self._format_time(position)
        dur_time = self._format_time(duration)
        self.time_label.setText(f"{pos_time}/{dur_time}")

    def _format_time(self, ms):
        """Format milliseconds to MM:SS.mmm format.

        Converts milliseconds to a human-readable time format with
        minutes, seconds, and milliseconds precision.

        Args:
            ms (int): Time in milliseconds

        Returns:
            str: Formatted time string in MM:SS.mmm format.
                Returns "00:00.000" for zero or negative values.
        """
        if ms <= 0:
            return "00:00.000"

        total_seconds = ms // 1000
        milliseconds = ms % 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
