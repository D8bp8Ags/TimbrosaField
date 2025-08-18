"""Dialog Manager Module for Field Recorder Analyzer.

This module provides a comprehensive dialog management system for the Field Recorder
Analyzer application. It offers a streamlined help system with consolidated dialogs
designed to reduce menu clutter while providing comprehensive user assistance.

The module manages three main dialog types:
1. Help & Quick Start - Consolidated user guidance and feature overview
2. Keyboard Shortcuts - Comprehensive shortcut reference with categorization
3. About - Application information and version details

Classes:
    DialogManager: Centralized manager for all application dialogs
    KeyboardShortcutsDialog: Comprehensive keyboard shortcuts reference
    AboutDialog: Application information and version details
    HelpAndQuickStartDialog: Consolidated help and quick start guide

Features:
    - Streamlined user experience with consolidated dialogs
    - Scrollable content for comprehensive information display
    - Rich text formatting with tables and structured layout
    - Professional help system with categorized shortcuts
    - Quick start guides with step-by-step instructions
    - Pro tips and workflow recommendations
    - Version information and application details
"""

import logging
import os

import app_config
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
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


class DialogManager:
    """Centralized manager for all application dialogs.

    Provides a unified interface for managing and displaying all application dialogs
    including help, shortcuts, and about information. The manager maintains references
    to the main window and creates dialog instances on demand.

    The streamlined dialog system consolidates multiple help functions into a
    coherent user experience with three main dialog types:
    - Help & Quick Start: Comprehensive user guidance combining features,
      quick start instructions, and technical documentation
    - Keyboard Shortcuts: Detailed shortcut reference with categorization
    - About: Application version and basic information

    Attributes:
        main_window: Reference to the main application window for dialog parenting

    Args:
        main_window: Main application window instance for dialog integration
    """

    def __init__(self, main_window):
        """Initialize dialog manager with reference to main window.

        Sets up the dialog manager with a reference to the main application
        window for proper dialog parenting and integration.

        Args:
            main_window: Main application window instance used as parent
                for all managed dialogs
        """
        self.main_window = main_window

    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts reference dialog.

        Creates and displays a comprehensive keyboard shortcuts reference dialog with
        categorized shortcuts for all application functions including audio playback,
        file operations, editing, viewing, and analysis tools.

        The dialog includes pro tips and workflow recommendations for efficient use of
        keyboard shortcuts in field recording workflows.
        """
        dialog = KeyboardShortcutsDialog(self.main_window)
        dialog.exec_()

    def show_about(self):
        """Show about application dialog.

        Creates and displays the application about dialog containing version
        information, application name, and basic description. Provides a link to the
        main help system for detailed assistance.
        """
        dialog = AboutDialog(self.main_window)
        dialog.exec_()

    def show_help_and_quickstart(self):
        """Show consolidated help and quick start guide dialog.

        Creates and displays the comprehensive help dialog that consolidates
        quick start instructions, feature descriptions, and technical documentation
        into a single, scrollable interface.

        The dialog includes:
        - Application overview and purpose
        - Step-by-step getting started guide
        - Complete feature descriptions
        - Tagging system categories and workflow
        - Pro tips for efficient operation
        - File organization guidelines
        - Important notes and best practices
        """
        dialog = HelpAndQuickStartDialog(self.main_window)
        dialog.exec_()


class KeyboardShortcutsDialog(QDialog):
    """Dialog showing comprehensive keyboard shortcuts reference with scrolling.

    A detailed keyboard shortcuts reference dialog that presents all application
    shortcuts in categorized tables with rich text formatting. The dialog uses
    a scrollable layout to accommodate comprehensive shortcut documentation.

    The shortcuts are organized into logical categories:
    - Audio Playback & Control
    - File Operations
    - Edit Operations
    - View & Zoom
    - Analysis & Tools
    - Tagging System
    - Template Shortcuts
    - Mouse Actions
    - Help & Information

    Features include pro tips for shortcut chaining and workflow optimization.

    Args:
        parent (QWidget, optional): Parent widget for the dialog. Defaults to None.
    """

    def __init__(self, parent=None):
        """Initialize the keyboard shortcuts dialog.

        Sets up the dialog with fixed dimensions and initializes the UI
        components for displaying comprehensive keyboard shortcut information.

        Args:
            parent (QWidget, optional): Parent widget for proper dialog
                positioning and behavior. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedSize(600, 800)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the keyboard shortcuts UI with scrollable content.

        Creates the complete user interface including header, scrollable content
        area, and action buttons. The content area contains categorized tables
        of keyboard shortcuts with rich text formatting and professional styling.

        UI Components:
        - Header with dialog title
        - Scrollable content area with comprehensive shortcut tables
        - Categorized shortcut sections with visual table formatting
        - Pro tips section with workflow recommendations
        - OK button for dialog dismissal
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h2>Keyboard Shortcuts</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Content widget that goes inside scroll area
        content_widget = QLabel()
        content_widget.setWordWrap(True)
        content_widget.setTextFormat(Qt.RichText)
        content_widget.setAlignment(Qt.AlignTop)
        content_widget.setMargin(10)  # Add some padding

        # COMPREHENSIVE Content - ALL shortcuts from the codebase
        shortcuts_text = """
<h3>🎵 Audio Playback & Control</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Space</b></td><td style="padding:8px; border:1px solid #ddd;">Play/Pause audio</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Escape</b></td><td style="padding:8px; border:1px solid #ddd;">Stop audio playback</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>← →</b></td><td style="padding:8px; border:1px solid #ddd;">Seek ±10 seconds</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>= (Plus)</b></td><td style="padding:8px; border:1px solid #ddd;">Volume +10</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>- (Minus)</b></td><td style="padding:8px; border:1px solid #ddd;">Volume -10</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>M</b></td><td style="padding:8px; border:1px solid #ddd;">Toggle Mute</td></tr>
</table>

<h3>📁 File Operations</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+O</b></td><td style="padding:8px; border:1px solid #ddd;">Open Directory</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>F5</b></td><td style="padding:8px; border:1px solid #ddd;">Reload Directory</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+E</b></td><td style="padding:8px; border:1px solid #ddd;">Export to Ableton Live</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+Q</b></td><td style="padding:8px; border:1px solid #ddd;">Exit Application</td></tr>
</table>

<h3>✏️ Edit Operations</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+,</b></td><td style="padding:8px; border:1px solid #ddd;">Open User Config</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+Shift+C</b></td><td style="padding:8px; border:1px solid #ddd;">Clear Current Tags</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+R</b></td><td style="padding:8px; border:1px solid #ddd;">Reset to Defaults</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+B</b></td><td style="padding:8px; border:1px solid #ddd;">Batch Tag Editor</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>F9</b></td><td style="padding:8px; border:1px solid #ddd;">Template Manager</td></tr>
</table>

<h3>👁️ View & Zoom</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl++</b></td><td style="padding:8px; border:1px solid #ddd;">Zoom In</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+-</b></td><td style="padding:8px; border:1px solid #ddd;">Zoom Out</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+0</b></td><td style="padding:8px; border:1px solid #ddd;">Fit to Window</td></tr>
</table>

<h3>📊 Analysis & Tools</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+A</b></td><td style="padding:8px; border:1px solid #ddd;">Analytics Dashboard</td></tr>
</table>

<h3>🏷️ Tagging System</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Type in tag field</b></td><td style="padding:8px; border:1px solid #ddd;">Show autocomplete suggestions</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>↑ ↓ in suggestions</b></td><td style="padding:8px; border:1px solid #ddd;">Navigate suggestions</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Enter</b></td><td style="padding:8px; border:1px solid #ddd;">Select first suggestion</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Escape</b></td><td style="padding:8px; border:1px solid #ddd;">Return to tag input field</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Tab</b></td><td style="padding:8px; border:1px solid #ddd;">Complete current suggestion</td></tr>
</table>

<h3>🎯 Template Shortcuts</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+1</b></td><td style="padding:8px; border:1px solid #ddd;">Apply Template 1</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+2</b></td><td style="padding:8px; border:1px solid #ddd;">Apply Template 2</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+3</b></td><td style="padding:8px; border:1px solid #ddd;">Apply Template 3</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Ctrl+4</b></td><td style="padding:8px; border:1px solid #ddd;">Apply Template 4</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>F9</b></td><td style="padding:8px; border:1px solid #ddd;">Open Template Manager</td></tr>
</table>

<h3>🖱️ Mouse Actions</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Click waveform</b></td><td style="padding:8px; border:1px solid #ddd;">Seek to position</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Hover waveform</b></td><td style="padding:8px; border:1px solid #ddd;">Show time/amplitude info</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Click cue table row</b></td><td style="padding:8px; border:1px solid #ddd;">Highlight cue marker</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Scroll wheel</b></td><td style="padding:8px; border:1px solid #ddd;">Zoom in/out on waveform</td></tr>
<tr><td style="padding:8px; border:1px solid #ddd;"><b>Drag waveform</b></td><td style="padding:8px; border:1px solid #ddd;">Pan left/right</td></tr>
</table>

<h3>❓ Help & Information</h3>
<table style="width:100%; border-collapse: collapse;">
<tr><td style="padding:8px; border:1px solid #ddd;"><b>F1</b></td><td style="padding:8px; border:1px solid #ddd;">Show this help dialog</td></tr>
</table>

<h3>💡 Pro Tips</h3>
<ul>
<li><b>Chain shortcuts:</b> Use F5 → Ctrl+1 → Space for quick reload → apply template → play workflow</li>
<li><b>Template workflow:</b> Create templates with F9, then use Ctrl+1-4 for instant application</li>
<li><b>Quick navigation:</b> Click waveform to jump, then use ← → for fine-tuning position</li>
<li><b>Batch operations:</b> Use Ctrl+B for tagging multiple files efficiently</li>
<li><b>Export workflow:</b> Tag files → Ctrl+A (analytics) → Ctrl+E (export to Ableton)</li>
</ul>

<hr>
<p><i>💡 Most shortcuts work globally when the main window has focus. Template shortcuts (Ctrl+1-4) work when the tag input area is active.</i></p>
        """

        content_widget.setText(shortcuts_text)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        # OK Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)


class AboutDialog(QDialog):
    """Dialog showing application information - SIMPLIFIED.

    A streamlined about dialog that displays essential application information
    including name, version, and basic description. The dialog maintains a
    minimal design focused on version identification and includes a reference
    to the comprehensive help system.

    The dialog dynamically pulls application information from the app_config
    module to ensure version consistency across the application.

    Args:
        parent (QWidget, optional): Parent widget for the dialog. Defaults to None.
    """

    def __init__(self, parent=None):
        """Initialize the about dialog.

        Sets up the dialog with application-specific title, fixed dimensions,
        and initializes the UI components for displaying application information.

        Args:
            parent (QWidget, optional): Parent widget for proper dialog
                positioning and behavior. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle(f"About {app_config.APP_NAME}")
        self.setFixedSize(450, 350)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the about dialog UI.

        Creates the complete user interface including application header,
        version information, description text, and action button. The content
        is dynamically populated from application configuration.

        UI Components:
        - Application name header with dynamic title
        - Version information from app_config
        - Application description and purpose
        - Reference to comprehensive help system
        - OK button for dialog dismissal
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<h2>{app_config.APP_NAME}</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Content - SIMPLIFIED
        about_text = f"""
<p><b>Version: </b>{app_config.ORG_NAME} {app_config.APP_VERSION}</p>
<p>A comprehensive tool for analyzing and organizing field recordings.</p>

<hr>
<p><i>For detailed help and features, use Help → Help & Quick Start.</i></p>
        """

        content_label = QLabel(about_text)
        content_label.setTextFormat(Qt.RichText)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        # OK Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)


class HelpAndQuickStartDialog(QDialog):
    """CONSOLIDATED dialog combining Quick Start + Features + Documentation.

    A comprehensive help dialog that consolidates multiple information sources
    into a single, scrollable interface. This dialog serves as the primary
    user assistance resource, providing complete guidance for field recording
    workflow management.

    The consolidated content includes:
    - Application purpose and overview
    - Step-by-step getting started guide
    - Complete feature descriptions with categorization
    - Tagging system categories and organization
    - Pro tips for efficient workflows
    - File organization recommendations
    - Important notes and best practices

    This design reduces menu clutter while ensuring users have access to
    comprehensive documentation in a single, well-organized location.

    Args:
        parent (QWidget, optional): Parent widget for the dialog. Defaults to None.
    """

    def __init__(self, parent=None):
        """Initialize the help and quick start dialog.

        Sets up the dialog with appropriate dimensions for comprehensive content
        display and initializes the UI components for the consolidated help system.

        Args:
            parent (QWidget, optional): Parent widget for proper dialog
                positioning and behavior. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Help & Quick Start")
        self.setFixedSize(800, 600)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the consolidated help UI with scrollable content.

        Creates the complete user interface for the comprehensive help system
        including header, scrollable content area with rich text formatting,
        and action buttons. The content combines quick start, features, and
        documentation into a cohesive user guide.

        UI Components:
        - Application header with dynamic title
        - Scrollable content area for comprehensive documentation
        - Rich text sections with structured information including:
          * Application overview and purpose
          * Step-by-step getting started guide
          * Feature descriptions and capabilities
          * Tagging system categories
          * Pro tips and workflow optimization
          * File organization guidelines
          * Important notes and best practices
        - OK button for dialog dismissal

        The content is dynamically formatted using HTML for professional
        presentation with proper section headers and structured lists.
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<h2>🚀 {app_config.APP_NAME} - Help & Quick Start</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Content widget that goes inside scroll area
        content_widget = QLabel()
        content_widget.setWordWrap(True)
        content_widget.setTextFormat(Qt.RichText)
        content_widget.setAlignment(Qt.AlignTop)
        content_widget.setMargin(10)  # Add some padding

        # Content - CONSOLIDATED from all 3 previous dialogs
        help_text = f"""
<h3>🎯 What is {app_config.APP_NAME}?</h3>
<p>A comprehensive tool for analyzing and organizing field recordings with professional
metadata handling, intelligent tagging, and export capabilities for audio workflows.</p>

<h3>🚀 Getting Started (5 Steps)</h3>
<ol>
<li><b>Setup:</b> Place WAV files in your directory, configure defaults in Edit → User Config</li>
<li><b>Browse:</b> Select files from the list, view waveforms and metadata</li>
<li><b>Tag:</b> Add tags using the autocomplete system (with category suggestions)</li>
<li><b>Save:</b> Save tags to embed them permanently in your files</li>
<li><b>Export:</b> Use File → Export to Ableton Live for multi-track projects</li>
</ol>

<h3>✨ Key Features</h3>
<ul>
<li><b>🎵 Audio Analysis:</b> Multi-format support (BWF, INFO, cue points), waveform visualization</li>
<li><b>🏷️ Smart Tagging:</b> Category-based autocomplete, templates, batch operations</li>
<li><b>📊 Professional Metadata:</b> BWF compliance, standard INFO fields, multiple save options</li>
<li><b>🎛️ Export Options:</b> Ableton Live sets, CSV exports, analytics dashboard</li>
<li><b>⚡ Performance:</b> Waveform caching, optimized rendering, memory management</li>
</ul>

<h3>🏷️ Tagging System Categories</h3>
<ul>
<li>🌿 <b>Nature</b> - Natural environments and locations</li>
<li>🏙️ <b>Urban</b> - Urban and human activities</li>
<li>🐦 <b>Animals</b> - Animals (wild and domestic)</li>
<li>🦗 <b>Insects</b> - Insects and small creatures</li>
<li>🌧️ <b>Weather</b> - Weather and atmospheric conditions</li>
<li>⏰ <b>Time</b> - Time of day indicators</li>
<li>🛠️ <b>Sound Type</b> - Sound type and activity</li>
<li>🎧 <b>Recording Quality</b> - Recording quality markers</li>
</ul>

<h3>💡 Pro Tips for Efficient Work</h3>
<ul>
<li>Use <b>templates</b> (Ctrl+1-4) for common tag combinations</li>
<li><b>Click waveforms</b> to jump to specific times</li>
<li>Use <b>batch editor</b> (Edit → Batch Tag Editor) for multiple files</li>
<li>Check <b>analytics</b> (Analysis → Analytics Dashboard) for collection overview</li>
<li>Set up <b>default metadata</b> in User Config to save time</li>
</ul>

<h3>📁 File Organization</h3>
<ul>
<li><code>FieldRecordings/</code> - Main WAV files directory</li>
<li><code>Ableton/</code> - Exported Ableton Live sets</li>
<li><code>user_config.json</code> - Your configuration settings</li>
<li><code>tag_templates.json</code> - Your saved tag templates</li>
</ul>

<h3>❗ Important Notes</h3>
<ul>
<li>Always <b>backup important files</b> before batch operations</li>
<li>Templates are <b>automatically saved</b> when modified</li>
<li>Waveform cache improves performance for large files</li>
<li>Use <b>F1</b> for keyboard shortcuts reference</li>
</ul>

<hr>
<p><i>💡 Need more help? Use <b>F1</b> for keyboard shortcuts or check the menu system for advanced features.</i></p>
        """

        content_widget.setText(help_text)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        # OK Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)
