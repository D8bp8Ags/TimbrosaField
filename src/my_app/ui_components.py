"""UI Components Module for Field Recorder Analyzer.

This module extracts all UI component functionality from MainWindow to improve code
organization and maintainability. Includes status bar, activity indicator, and styling
management.

Phase 3 of MainWindow refactoring - removes ~200 lines from main.py
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


class ModernStatusBar(QStatusBar):
    """Enhanced status bar met progress tracking en visual feedback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_timers()

    def setup_ui(self):
        """Setup status bar components."""
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
        """Setup auto-hide timers."""
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self.clear_temporary_message)
        self.message_timer.setSingleShot(True)

    def show_message(self, message, timeout=3000, icon=None):
        """Show temporary message with optional icon."""
        if icon:
            self.status_label.setText(f"{icon} {message}")
        else:
            self.status_label.setText(message)

        if timeout > 0:
            self.message_timer.start(timeout)

    def clear_temporary_message(self):
        """Clear temporary message and return to ready state."""
        self.status_label.setText("Ready")

    def show_progress(self, title, maximum=100):
        """Show progress bar with title."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.activity_indicator.setVisible(True)
        self.activity_indicator.start()
        self.show_message(title, 0)  # No timeout

    def update_progress(self, value, message=None):
        """Update progress value and optional message."""
        self.progress_bar.setValue(value)
        if message:
            self.show_message(message, 0)

    def hide_progress(self):
        """Hide progress bar and stop activity indicator."""
        self.progress_bar.setVisible(False)
        self.activity_indicator.setVisible(False)
        self.activity_indicator.stop()
        self.show_message("Ready")

    def update_file_count(self, count):
        """Update file counter."""
        if count == 1:
            self.file_counter.setText("1 file")
        else:
            self.file_counter.setText(f"{count} files")

    def update_audio_status(self, status):
        """Update audio playback status."""
        # todo
        # icons = {"playing": "▶️", "paused": "⏸️", "stopped": "⏹️"}
        # icon = icons.get(status.lower(), "♪")
        # Icons don't work yet in some environments
        self.audio_status.setText(f"{status.title()}")

    def update_file_info(self, filename=None, duration=None, size=None):
        """Update current file information."""
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
    """Animated activity indicator for long operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.movie = None
        self.setup_animation()

    def setup_animation(self):
        """Setup spinning animation."""
        # Create simple spinning animation using QPainter
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        self.is_active = False

    def rotate(self):
        """Rotate the indicator."""
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        """Paint the spinning indicator."""
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
        """Start animation."""
        self.is_active = True
        self.timer.start(100)  # 100ms intervals

    def stop(self):
        """Stop animation."""
        self.is_active = False
        self.timer.stop()
        self.update()


class StatusBarManager:
    """Coordinator for status bar updates from different components.

    This class acts as the central hub for all status updates, making it easy to track
    what's happening in the application and provide user feedback.
    """

    def __init__(self, main_window):
        """Initialize status bar manager."""
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
        """Connect to various component signals for automatic updates."""
        try:
            # Connect audio player state changes
            if hasattr(self.wav_viewer, "audio_player"):
                self.wav_viewer.audio_player.stateChanged.connect(
                    self._on_audio_state_changed
                )
                print("🎵 Audio player status connected to status bar")

            # Connect file list changes
            if hasattr(self.wav_viewer, "file_list"):
                self.wav_viewer.file_list.currentRowChanged.connect(
                    self._on_file_selection_changed
                )
                print("📁 File list status connected to status bar")

        except Exception as e:
            print(f"⚠️ Error connecting status bar signals: {e}")

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
        """Handle audio player state changes."""
        status_map = {
            QMediaPlayer.PlayingState: "playing",
            QMediaPlayer.PausedState: "paused",
            QMediaPlayer.StoppedState: "stopped",
        }

        status = status_map.get(state, "stopped")
        self.status_bar.update_audio_status(status)

    def _on_file_selection_changed(self, row):
        """Handle file selection changes."""
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
            print(f"⚠️ Error updating file info: {e}")

    # === PUBLIC INTERFACE METHODS ===

    def show_message(self, message, timeout=3000):
        """Show message in status bar with optional icon detection."""
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
        """Update file counter in status bar."""
        self._update_initial_file_count()

    def show_progress(self, title, maximum=100):
        """Show progress bar for long operations."""
        self.status_bar.show_progress(title, maximum)

    def update_progress(self, value, message=None):
        """Update progress bar."""
        self.status_bar.update_progress(value, message)

    def hide_progress(self):
        """Hide progress bar."""
        self.status_bar.hide_progress()

    def update_file_info(self, filename=None, duration=None, size=None):
        """Update current file information display."""
        self.status_bar.update_file_info(filename, duration, size)

    def get_status_bar(self):
        """Get reference to the status bar widget."""
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

        print("🎨 Professional application styling applied")

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
        palette.setColor(QPalette.Base, QColor(ApplicationStylist.COLORS["input_background"]))
        palette.setColor(
            QPalette.AlternateBase, QColor(ApplicationStylist.COLORS["surface"])
        )

        # Text colors
        palette.setColor(
            QPalette.Text, QColor(ApplicationStylist.COLORS["text_primary"])
        )
        palette.setColor(QPalette.BrightText, QColor(ApplicationStylist.COLORS["selection_text"]))

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
        print("☀️ Light theme applied")

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
        print("🌙 Dark theme applied")

    @staticmethod
    def apply_macos_dark_theme(app):
        """Apply macOS-style dark theme."""
        macos_dark_colors = ApplicationStylist.COLORS.copy()
        macos_dark_colors.update({
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
        })

        ApplicationStylist.COLORS.update(macos_dark_colors)
        ApplicationStylist.apply_complete_styling(app)
        print("🍎 macOS Dark theme applied")

    @staticmethod
    def set_custom_theme(app, color_overrides):
        """Allow custom theme colors while maintaining design consistency."""
        custom_colors = ApplicationStylist.COLORS.copy()
        custom_colors.update(color_overrides)

        # Regenerate stylesheet with custom colors
        print("🎨 Custom theme applied")

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

        print("🎨 UIComponentManager initialized")

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
            print(f"⚠️ Fallback file count update failed: {e}")
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
