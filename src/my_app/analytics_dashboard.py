"""Analytics Dashboard for field recording statistics.

This module provides a comprehensive analytics dashboard for analyzing
WAV file collections, including tag statistics, audio specifications,
and timeline analysis.

The dashboard supports:
    - File overview statistics (count, duration, size)
    - Tag frequency analysis and categorization
    - Audio specification distribution (sample rate, bit depth, etc.)
    - Recording timeline visualization with BWF metadata
    - Export functionality for analysis reports

Classes:
    AnalyticsDashboard: Main dialog window for displaying analytics

Functions:
    show_analytics_dashboard: Display dashboard for WAV viewer files
    select_wav_directory: Directory selection dialog for WAV files
    main: Standalone execution entry point
"""

import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

import soundfile as sf
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from tag_definitions import tag_categories
from wav_analyzer import wav_analyze

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


class AnalyticsDashboard(QDialog):
    """Dashboard for field recording statistics and analytics.

    A PyQt5 dialog window that provides comprehensive analysis of WAV file
    collections. The dashboard presents data in multiple tabs covering different
    aspects of the audio file collection.

    Features:
        - Overview tab with summary statistics
        - Tags tab with frequency analysis and categorization
        - Audio tab with technical specification distribution
        - Timeline tab with chronological recording data
        - Export functionality for generating text reports

    Attributes:
        wav_files (list): List of WAV file paths to analyze
        tabs (QTabWidget): Main tab container for different views
        overview_tab (QWidget): Overview statistics tab
        tags_tab (QWidget): Tag analysis tab
        audio_tab (QWidget): Audio specifications tab
        timeline_tab (QWidget): Timeline analysis tab

    Args:
        parent (QWidget, optional): Parent widget. Defaults to None.
        wav_files (list, optional): List of WAV file paths to analyze.
            Defaults to empty list.
    """

    def __init__(self, parent=None, wav_files=None):
        """Initialize the analytics dashboard.

        Args:
            parent: Parent widget
            wav_files: List of WAV file paths to analyze
        """
        super().__init__(parent)
        self.wav_files = wav_files or []
        self.setWindowTitle("Recording Analytics Dashboard")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.analyze_files()

    def setup_ui(self):
        """Set up the user interface components.

        Creates the main layout with header, tabbed interface, and action buttons.
        Initializes all four analysis tabs: Overview, Tags, Audio, and Timeline.
        Sets up export and close button functionality.
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h2>Field Recording Analytics</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Tab widget for different views
        self.tabs = QTabWidget()

        # Tab 1: Overview
        self.overview_tab = self.create_overview_tab()
        self.tabs.addTab(self.overview_tab, "Overview")

        # Tab 2: Tags analysis
        self.tags_tab = self.create_tags_tab()
        self.tabs.addTab(self.tags_tab, "Tags")

        # Tab 3: Audio specs
        self.audio_tab = self.create_audio_tab()
        self.tabs.addTab(self.audio_tab, "Audio")

        # Tab 4: Timeline
        self.timeline_tab = self.create_timeline_tab()
        self.tabs.addTab(self.timeline_tab, "Timeline")

        layout.addWidget(self.tabs)

        # Export and close buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        export_btn = QPushButton("Export Report")
        export_btn.clicked.connect(self.export_report)
        button_layout.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_overview_tab(self):
        """Create overview statistics tab.

        Builds the overview tab with summary statistics including total files,
        duration, size, average duration, and most common tags. All labels are
        initialized with placeholder text and will be updated during analysis.

        Returns:
            QWidget: Configured widget containing overview statistics labels
            with bold formatting.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Statistics labels with proper initialization
        self.total_files_label = QLabel("Total files: -")
        self.total_duration_label = QLabel("Total duration: -")
        self.total_size_label = QLabel("Total size: -")
        self.avg_duration_label = QLabel("Average duration: -")
        self.most_common_tags_label = QLabel("Most common tags: -")

        # Set font for all labels
        for label in [
            self.total_files_label,
            self.total_duration_label,
            self.total_size_label,
            self.avg_duration_label,
            self.most_common_tags_label,
        ]:
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            label.setFont(font)
            layout.addWidget(label)

        layout.addStretch()
        return widget

    def create_tags_tab(self):
        """Create tags analysis tab.

        Builds the tags analysis tab with two main sections:
        1. Tag Statistics table - shows individual tag frequency and percentages
        2. Category Distribution table - shows file counts by tag category

        Both tables use stretch column resize mode for responsive layout.

        Returns:
            QWidget: Configured widget containing tag frequency and category
            distribution tables.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Tag statistics section
        layout.addWidget(QLabel("<b>Tag Statistics</b>"))

        # Tags frequency table
        self.tags_table = QTableWidget(0, 3)
        self.tags_table.setHorizontalHeaderLabels(["Tag", "Count", "Percentage"])
        self.tags_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tags_table)

        # Category distribution section
        layout.addWidget(QLabel("<b>Category Distribution</b>"))
        self.category_table = QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["Category", "File Count"])
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.category_table)

        return widget

    def create_audio_tab(self):
        """Create audio specifications tab.

        Builds the audio specifications tab containing a table that displays
        the distribution of audio properties across all analyzed files.
        Properties include sample rate, channels, bit depth, and format.

        Returns:
            QWidget: Configured widget containing audio specifications
            distribution table.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("<b>Audio Specifications</b>"))

        # Audio specs table
        self.audio_specs_table = QTableWidget(0, 2)
        self.audio_specs_table.setHorizontalHeaderLabels(["Property", "Distribution"])
        self.audio_specs_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        layout.addWidget(self.audio_specs_table)

        return widget

    def create_timeline_tab(self):
        """Create timeline analysis tab.

        Builds the timeline tab with a comprehensive table showing chronological
        information for each file. Includes BWF (Broadcast Wave Format) metadata
        dates/times, file system timestamps, duration, and timestamp source.

        Table columns:
        - File: Filename
        - BWF Date: Broadcast Wave origination date
        - BWF Time: Broadcast Wave origination time
        - File Created: File system creation timestamp
        - File Modified: File system modification timestamp
        - Duration: Audio duration
        - Source: Best available timestamp source

        Returns:
            QWidget: Configured widget containing timeline analysis table.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("<b>Recording Timeline</b>"))

        # Timeline table with extended columns
        self.timeline_table = QTableWidget(0, 7)
        self.timeline_table.setHorizontalHeaderLabels(
            [
                "File",
                "BWF Date",
                "BWF Time",
                "File Created",
                "File Modified",
                "Duration",
                "Source",
            ]
        )
        self.timeline_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.timeline_table)

        return widget

    def get_file_timestamps(self, file_path, file_stat):
        """Get accurate file creation and modification timestamps.

        Attempts to get the most accurate creation time available based on
        the operating system. Uses st_birthtime on macOS, st_ctime on Windows,
        and falls back to st_ctime on Unix/Linux systems.

        Args:
            file_path (str): Path to the file being analyzed
            file_stat (os.stat_result): Result of os.stat() call for the file

        Returns:
            tuple[str, str]: Formatted timestamps as (creation_time, modification_time)
                Both in 'YYYY-MM-DD HH:MM:SS' format. Returns fallback timestamps
                if extraction fails.

        Note:
            On Linux/Unix systems, st_ctime represents metadata change time,
            not true creation time, as true creation time is not available.
        """
        try:
            # Get modification time (always available)
            mod_time = datetime.fromtimestamp(file_stat.st_mtime)
            mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")

            # Try to get creation time (platform dependent)
            creation_time = None

            # Windows: st_ctime is creation time
            # Unix/Linux: st_ctime is metadata change time, not creation
            # macOS: st_birthtime is creation time (if available)

            if hasattr(file_stat, "st_birthtime"):
                # macOS - true creation time
                creation_time = datetime.fromtimestamp(file_stat.st_birthtime)
            elif os.name == "nt":
                # Windows - st_ctime is creation time
                creation_time = datetime.fromtimestamp(file_stat.st_ctime)
            else:
                # Linux/Unix - use st_ctime as fallback (metadata change time)
                # This is not true creation time, but closest we can get
                creation_time = datetime.fromtimestamp(file_stat.st_ctime)

            creation_time_str = creation_time.strftime("%Y-%m-%d %H:%M:%S")

            return creation_time_str, mod_time_str

        except Exception as e:
            print(f"Warning: Could not get timestamps for {file_path}: {e}")
            fallback_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return fallback_time, fallback_time

    def analyze_files(self):
        """Analyze all WAV files and populate statistics.

        Main analysis method that processes all WAV files in the collection. Initializes
        statistics containers, processes each file individually, and updates all
        dashboard displays with the results.

        Handles analysis errors gracefully and displays a warning dialog if any files
        could not be processed. Updates overview, tags, audio specifications, and
        timeline displays upon completion.
        """
        if not self.wav_files:
            return

        print(f"Analyzing {len(self.wav_files)} files...")

        # Initialize statistics containers
        stats = self._initialize_analysis_stats()

        # Process each file
        for file_path in self.wav_files:
            self._process_single_file(file_path, stats)

        # Report and update displays
        self._finalize_analysis(stats)

    def _initialize_analysis_stats(self):
        """Initialize analysis statistics containers.

        Creates and returns a dictionary with empty containers for collecting
        statistics during file analysis. Includes containers for duration,
        file size, tags, audio specifications, timeline data, and error tracking.

        Returns:
            dict: Dictionary containing initialized statistics containers:
                - total_duration (float): Cumulative duration in seconds
                - total_size (int): Cumulative file size in bytes
                - all_tags (list): All extracted tags from all files
                - audio_specs (defaultdict): Audio specifications by property
                - timeline_data (list): Timeline entries for each file
                - category_counts (defaultdict): Tag category counts
                - analysis_errors (int): Number of files that failed analysis
                - successful_analyses (int): Number of successfully analyzed files
        """
        return {
            "total_duration": 0,
            "total_size": 0,
            "all_tags": [],
            "audio_specs": defaultdict(list),
            "timeline_data": [],
            "category_counts": defaultdict(int),
            "analysis_errors": 0,
            "successful_analyses": 0,
        }

    def _process_single_file(self, file_path, stats):
        """Process a single WAV file and update statistics.

        Analyzes a single WAV file using wav_analyze, extracts relevant data,
        and updates the provided statistics containers. Handles analysis failures
        gracefully by calling _handle_analysis_failure.

        Args:
            file_path (str): Absolute path to the WAV file to process
            stats (dict): Statistics containers to update (modified in-place)

        Note:
            This method modifies the stats dictionary in-place, updating
            total_duration, total_size, all_tags, audio_specs, timeline_data,
            category_counts, and error counters.
        """
        try:
            # Get basic file information
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            stats["total_size"] += file_size

            # Analyze WAV file
            result = wav_analyze(file_path)

            if result is None:
                self._handle_analysis_failure(
                    file_path, file_stat, stats, "Analysis failed"
                )
                return

            stats["successful_analyses"] += 1

            # Extract file data
            file_data = self._extract_file_data(file_path, file_stat, result, file_size)

            # Update statistics
            self._update_statistics(stats, file_data)

        except Exception as e:
            self._handle_analysis_failure(
                file_path, None, stats, f"Error: {str(e)[:30]}..."
            )

    def _extract_file_data(self, file_path, file_stat, result, file_size):
        """Extract all relevant data from a WAV file analysis result.

        Safely extracts and processes data from the wav_analyze result,
        including format information, metadata, tags, and timestamps.
        Handles missing or None data gracefully with fallbacks.

        Args:
            file_path (str): Path to the analyzed WAV file
            file_stat (os.stat_result): File system statistics
            result (dict): Result dictionary from wav_analyze
            file_size (int): File size in bytes

        Returns:
            dict: Extracted file data containing:
                - file_path (str): Original file path
                - duration (float): Audio duration in seconds
                - tags (list): Extracted tags from INFO chunk
                - fmt_info (dict): Format information from fmt chunk
                - file_created (str): File creation timestamp
                - file_modified (str): File modification timestamp
                - bwf_date (str): BWF origination date
                - bwf_time (str): BWF origination time
        """
        # Safe extraction with proper None checks
        fmt_info = result.get("fmt", {}) or {}
        info_data = result.get("info", {}) or {}
        bext_data = result.get("bext", {}) or {}

        # Calculate duration
        duration = self._calculate_duration(file_path, file_size, fmt_info)

        # Extract tags
        tags = self._extract_tags(info_data)

        # Get timestamps
        file_created, file_modified = self.get_file_timestamps(file_path, file_stat)
        bwf_date = bext_data.get("Origination Date", "").strip()
        bwf_time = bext_data.get("Origination Time", "").strip()

        return {
            "file_path": file_path,
            "duration": duration,
            "tags": tags,
            "fmt_info": fmt_info,
            "file_created": file_created,
            "file_modified": file_modified,
            "bwf_date": bwf_date,
            "bwf_time": bwf_time,
        }

    def _calculate_duration(self, file_path, file_size, fmt_info):
        """Calculate file duration with fallback methods.

        Attempts to get accurate duration using soundfile library first,
        then falls back to estimation based on format information if that fails.

        Args:
            file_path (str): Path to the WAV file
            file_size (int): File size in bytes for fallback calculation
            fmt_info (dict): Format information from WAV analysis

        Returns:
            float: Duration in seconds. Returns 0 if calculation fails.

        Note:
            Fallback calculation assumes 16-bit stereo audio, which may
            not be accurate for all files.
        """
        try:
            info = sf.info(file_path)
            duration = info.frames / info.samplerate
            print(
                f"Got duration from soundfile: {duration:.1f}s for {os.path.basename(file_path)}"
            )
            return duration
        except Exception as sf_error:
            print(f"Soundfile failed for {os.path.basename(file_path)}: {sf_error}")

            # Fallback calculation
            sample_rate = fmt_info.get("Sample rate", 44100)
            if sample_rate > 0:
                duration = file_size / (
                    sample_rate * 2 * 2
                )  # Estimate for 16-bit stereo
            else:
                duration = 0

            print(f"Using fallback duration estimate: {duration:.1f}s")
            return duration

    def _extract_tags(self, info_data):
        """Extract and clean tags from INFO chunk.

        Extracts tags from the ICMT (comment) field of the INFO chunk,
        splitting on commas and cleaning whitespace.

        Args:
            info_data (dict): INFO chunk data from WAV analysis

        Returns:
            list[str]: List of cleaned tag strings. Empty list if no
                valid tags found.
        """
        icmt = info_data.get("ICMT", "").strip()
        if not icmt:
            return []

        return [tag.strip() for tag in icmt.split(",") if tag.strip()]

    def _update_statistics(self, stats, file_data):
        """Update all statistics with data from a single file.

        Updates all statistics containers with data extracted from a single
        file. Handles duration, tags, audio specifications, and timeline data.

        Args:
            stats (dict): Statistics containers to update (modified in-place)
            file_data (dict): Extracted data from a single file
        """
        # Update totals
        stats["total_duration"] += file_data["duration"]

        # Process tags
        if file_data["tags"]:
            stats["all_tags"].extend(file_data["tags"])
            self._categorize_tags(file_data["tags"], stats["category_counts"])

        # Update audio specs
        self._update_audio_specs(stats["audio_specs"], file_data["fmt_info"])

        # Add timeline entry
        timeline_entry = self._create_timeline_entry(file_data)
        stats["timeline_data"].append(timeline_entry)

    def _categorize_tags(self, tags, category_counts):
        """Categorize tags and update counts.

        Matches tags against predefined categories from tag_definitions
        and increments category counters. Performs case-insensitive matching.

        Args:
            tags (list[str]): List of tag strings to categorize
            category_counts (defaultdict): Category counter to update (modified in-place)
        """
        for tag in tags:
            for category, category_tags in tag_categories.items():
                if tag.lower() in [ct.lower() for ct in category_tags]:
                    category_counts[category] += 1
                    break

    def _update_audio_specs(self, audio_specs, fmt_info):
        """Update audio specifications statistics.

        Extracts audio format specifications and adds them to the audio_specs
        containers for later distribution analysis.

        Args:
            audio_specs (defaultdict): Audio specifications containers (modified in-place)
            fmt_info (dict): Format information from WAV file analysis.
                Can be None or empty.
        """
        if fmt_info:
            audio_specs["Sample Rate"].append(fmt_info.get("Sample rate", "Unknown"))
            audio_specs["Channels"].append(fmt_info.get("Channels", "Unknown"))
            audio_specs["Bit Depth"].append(fmt_info.get("Bits per sample", "Unknown"))
            audio_specs["Format"].append(fmt_info.get("Audio format name", "Unknown"))
        else:
            # Add placeholder data if no format info available
            for spec in ["Sample Rate", "Channels", "Bit Depth", "Format"]:
                audio_specs[spec].append("Unknown")

    def _create_timeline_entry(self, file_data):
        """Create a timeline entry from file data.

        Creates a timeline entry dictionary with timestamps and metadata.
        Determines the best timestamp source based on available data,
        preferring BWF metadata over file system timestamps.

        Args:
            file_data (dict): Extracted file data containing timestamps and metadata

        Returns:
            dict: Timeline entry containing file name, timestamps, duration,
                and timestamp source information.
        """
        # Determine best timestamp source
        bwf_date, bwf_time = file_data["bwf_date"], file_data["bwf_time"]

        if bwf_date and bwf_time:
            timestamp_source = "BWF metadata"
        elif file_data["file_created"] != file_data["file_modified"]:
            timestamp_source = "File creation"
        else:
            timestamp_source = "File modification"

        return {
            "file": os.path.basename(file_data["file_path"]),
            "bwf_date": bwf_date if bwf_date else "Not available",
            "bwf_time": bwf_time if bwf_time else "Not available",
            "file_created": file_data["file_created"],
            "file_modified": file_data["file_modified"],
            "duration": (
                f"{file_data['duration']:.1f}s"
                if file_data["duration"] > 0
                else "Unknown"
            ),
            "source": timestamp_source,
        }

    def _handle_analysis_failure(self, file_path, file_stat, stats, error_message):
        """Handle failed file analysis gracefully.

        Records analysis failures and creates minimal timeline entries
        using only file system information when possible.

        Args:
            file_path (str): Path to the file that failed analysis
            file_stat (os.stat_result, optional): File system statistics.
                Can be None if stat call also failed.
            stats (dict): Statistics containers to update (modified in-place)
            error_message (str): Description of the analysis failure
        """
        print(f"Warning: {error_message} for {os.path.basename(file_path)}")
        stats["analysis_errors"] += 1

        try:
            if file_stat is None:
                file_stat = os.stat(file_path)

            file_created, file_modified = self.get_file_timestamps(file_path, file_stat)
            timeline_entry = {
                "file": os.path.basename(file_path),
                "bwf_date": "Error" if "Error" in error_message else "Analysis failed",
                "bwf_time": "Error" if "Error" in error_message else "Analysis failed",
                "file_created": file_created,
                "file_modified": file_modified,
                "duration": error_message,
                "source": "File system only",
            }
            stats["timeline_data"].append(timeline_entry)

        except Exception as nested_e:
            print(f"Could not even get file stats for {file_path}: {nested_e}")

    def _finalize_analysis(self, stats):
        """Complete analysis and update displays.

        Finalizes the analysis process by updating all dashboard displays
        with collected statistics and showing warning dialogs if errors occurred.

        Args:
            stats (dict): Complete statistics from analysis process

        Note:
            Displays a warning dialog if any files failed analysis, providing
            details about possible causes and successful analysis count.
        """
        # Report results
        print("Analysis complete:")
        print(f"   Successfully analyzed: {stats['successful_analyses']} files")
        print(f"   Analysis errors: {stats['analysis_errors']} files")
        print(f"   Total files processed: {len(self.wav_files)}")

        # Update displays
        self.update_overview(
            stats["total_duration"],
            stats["total_size"],
            stats["all_tags"],
            stats["analysis_errors"],
        )
        self.update_tags_analysis(stats["all_tags"], stats["category_counts"])
        self.update_audio_specs(stats["audio_specs"])
        self.update_timeline(stats["timeline_data"])

        # Show warning if errors occurred
        if stats["analysis_errors"] > 0:
            QMessageBox.warning(  # noqa: BLE001
                self,
                "Analysis Warning",
                f"{stats['analysis_errors']} of {len(self.wav_files)} files could not be fully analyzed.\n\n"
                f"{stats['successful_analyses']} files successfully analyzed.\n\n"
                f"Possible causes:\n"
                f"• Corrupted WAV files\n"
                f"• Unsupported WAV formats\n"
                f"• File access issues\n\n"
                f"Dashboard shows data from successfully analyzed files.",
            )

    def update_overview(self, total_duration, total_size, all_tags, analysis_errors=0):
        """Update overview statistics display.

        Updates all overview tab labels with calculated statistics including
        formatted duration, file size, average duration, and most common tags.
        Includes error information in the file count if applicable.

        Args:
            total_duration (float): Total duration in seconds across all files
            total_size (int): Total file size in bytes across all files
            all_tags (list[str]): List of all extracted tags from all files
            analysis_errors (int, optional): Number of files that failed analysis.
                Defaults to 0.
        """
        num_files = len(self.wav_files)

        # Format duration as HH:MM:SS
        hours = int(total_duration // 3600)
        minutes = int((total_duration % 3600) // 60)
        seconds = int(total_duration % 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Format file size
        if total_size > 1024**3:  # GB
            size_str = f"{total_size / (1024**3):.1f} GB"
        elif total_size > 1024**2:  # MB
            size_str = f"{total_size / (1024**2):.1f} MB"
        else:
            size_str = f"{total_size / 1024:.1f} KB"

        # Calculate average duration
        avg_duration = total_duration / num_files if num_files > 0 else 0
        avg_str = f"{avg_duration:.1f}s"

        # Get most common tags
        if all_tags:
            tag_counts = Counter(all_tags)
            top_tags = [f"{tag} ({count}x)" for tag, count in tag_counts.most_common(5)]
            tags_str = ", ".join(top_tags)
        else:
            tags_str = "No tags found"

        # Update labels with error info if needed
        files_text = f"Total files: {num_files}"
        if analysis_errors > 0:
            files_text += f" ({analysis_errors} errors)"

        self.total_files_label.setText(files_text)
        self.total_duration_label.setText(f"Total duration: {duration_str}")
        self.total_size_label.setText(f"Total size: {size_str}")
        self.avg_duration_label.setText(f"Average duration: {avg_str}")
        self.most_common_tags_label.setText(f"Most common tags: {tags_str}")

    def update_tags_analysis(self, all_tags, category_counts):
        """Update tags analysis tables.

        Populates the tags frequency table with individual tag counts and
        percentages, and the category distribution table with file counts
        by tag category. Shows empty state messages if no data available.

        Args:
            all_tags (list[str]): List of all extracted tags from all files
            category_counts (dict): Dictionary mapping category names to file counts
        """
        if not all_tags:
            # Show empty state
            self.tags_table.setRowCount(1)
            self.tags_table.setItem(0, 0, QTableWidgetItem("No tags found"))
            self.tags_table.setItem(0, 1, QTableWidgetItem("-"))
            self.tags_table.setItem(0, 2, QTableWidgetItem("-"))

            self.category_table.setRowCount(1)
            self.category_table.setItem(0, 0, QTableWidgetItem("No categories found"))
            self.category_table.setItem(0, 1, QTableWidgetItem("-"))
            return

        # Populate tags frequency table
        tag_counts = Counter(all_tags)
        total_tag_instances = len(all_tags)

        self.tags_table.setRowCount(len(tag_counts))
        for i, (tag, count) in enumerate(tag_counts.most_common()):
            percentage = (count / total_tag_instances) * 100

            self.tags_table.setItem(i, 0, QTableWidgetItem(tag))
            self.tags_table.setItem(i, 1, QTableWidgetItem(str(count)))
            self.tags_table.setItem(i, 2, QTableWidgetItem(f"{percentage:.1f}%"))

        # Populate category distribution table
        if category_counts:
            self.category_table.setRowCount(len(category_counts))
            sorted_categories = sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )
            for i, (category, count) in enumerate(sorted_categories):
                self.category_table.setItem(i, 0, QTableWidgetItem(category))
                self.category_table.setItem(i, 1, QTableWidgetItem(str(count)))
        else:
            self.category_table.setRowCount(1)
            self.category_table.setItem(0, 0, QTableWidgetItem("No categories found"))
            self.category_table.setItem(0, 1, QTableWidgetItem("-"))

    def update_audio_specs(self, audio_specs):
        """Update audio specifications analysis.

        Populates the audio specifications table with distribution data
        for each audio property (sample rate, channels, bit depth, format).
        Shows counts for each unique value found across all files.

        Args:
            audio_specs (dict): Dictionary mapping specification names to
                lists of values from all analyzed files
        """
        if not audio_specs:
            self.audio_specs_table.setRowCount(1)
            self.audio_specs_table.setItem(
                0, 0, QTableWidgetItem("No audio specifications")
            )
            self.audio_specs_table.setItem(0, 1, QTableWidgetItem("Analysis failed"))
            return

        self.audio_specs_table.setRowCount(len(audio_specs))

        for i, (spec_name, values) in enumerate(audio_specs.items()):
            value_counts = Counter(values)
            distribution = ", ".join(
                [f"{val}: {count}" for val, count in value_counts.most_common()]
            )

            self.audio_specs_table.setItem(i, 0, QTableWidgetItem(spec_name))
            self.audio_specs_table.setItem(i, 1, QTableWidgetItem(distribution))

    def update_timeline(self, timeline_data):
        """Update timeline analysis display.

        Populates the timeline table with chronological recording data.
        Sorts entries by BWF timestamp if available, falling back to file
        creation time. Includes comprehensive debugging output.

        Args:
            timeline_data (list[dict]): List of timeline entry dictionaries
                containing file information, timestamps, and metadata
        """
        print(f"DEBUG: update_timeline called with {len(timeline_data)} entries")

        if not timeline_data:
            print("DEBUG: No timeline data, showing empty state")
            self.timeline_table.setRowCount(1)
            for col in range(7):
                text = "No timeline data" if col == 0 else "-"
                self.timeline_table.setItem(0, col, QTableWidgetItem(text))
            return

        # Debug: print first few entries
        for i, entry in enumerate(timeline_data[:3]):
            print(f"DEBUG: Entry {i}: {entry}")

        # Sort by BWF date/time first, then file timestamps
        def sort_key(entry):
            # Try BWF timestamp first
            if entry.get("bwf_date", "") not in [
                "Not available",
                "Analysis failed",
                "Error",
                "",
            ] and entry.get("bwf_time", "") not in [
                "Not available",
                "Analysis failed",
                "Error",
                "",
            ]:
                try:
                    # BWF format: YYYY-MM-DD and HH:MM:SS
                    return f"{entry['bwf_date']} {entry['bwf_time']}"
                except Exception:
                    pass

            # Fallback to file creation time
            return entry.get("file_created", "")

        try:
            timeline_data.sort(key=sort_key)
        except Exception as e:
            print(f"DEBUG: Sort error: {e}")

        print(f"DEBUG: Setting table row count to {len(timeline_data)}")
        self.timeline_table.setRowCount(len(timeline_data))

        for i, entry in enumerate(timeline_data):
            try:
                self.timeline_table.setItem(
                    i, 0, QTableWidgetItem(entry.get("file", "Unknown"))
                )
                self.timeline_table.setItem(
                    i, 1, QTableWidgetItem(entry.get("bwf_date", "N/A"))
                )
                self.timeline_table.setItem(
                    i, 2, QTableWidgetItem(entry.get("bwf_time", "N/A"))
                )
                self.timeline_table.setItem(
                    i, 3, QTableWidgetItem(entry.get("file_created", "N/A"))
                )
                self.timeline_table.setItem(
                    i, 4, QTableWidgetItem(entry.get("file_modified", "N/A"))
                )
                self.timeline_table.setItem(
                    i, 5, QTableWidgetItem(entry.get("duration", "N/A"))
                )
                self.timeline_table.setItem(
                    i, 6, QTableWidgetItem(entry.get("source", "N/A"))
                )
                print(f"DEBUG: Added row {i} for file {entry.get('file', 'Unknown')}")
            except Exception as e:
                print(f"DEBUG: Error adding row {i}: {e}")

        print(f"DEBUG: Timeline table now has {self.timeline_table.rowCount()} rows")

    def export_report(self):
        """Export analytics report to text file.

        Opens a file save dialog and exports a comprehensive text report
        containing all dashboard data: overview statistics, tag analysis,
        category distribution, and audio specifications.

        Shows success or error messages to the user upon completion.
        The exported filename includes timestamp for uniqueness.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Analytics Report",
            f"field_recording_analytics_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            "Text Files (*.txt);;All Files (*)",
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("FIELD RECORDING ANALYTICS REPORT\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(
                        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    )

                    # Overview section
                    f.write("OVERVIEW\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"{self.total_files_label.text()}\n")
                    f.write(f"{self.total_duration_label.text()}\n")
                    f.write(f"{self.total_size_label.text()}\n")
                    f.write(f"{self.avg_duration_label.text()}\n")
                    f.write(f"{self.most_common_tags_label.text()}\n\n")

                    # Tags section
                    f.write("TAG ANALYSIS\n")
                    f.write("-" * 20 + "\n")
                    for row in range(self.tags_table.rowCount()):
                        tag = self.tags_table.item(row, 0).text()
                        count = self.tags_table.item(row, 1).text()
                        percent = self.tags_table.item(row, 2).text()
                        f.write(f"{tag}: {count} ({percent})\n")
                    f.write("\n")

                    # Category section
                    f.write("CATEGORY DISTRIBUTION\n")
                    f.write("-" * 20 + "\n")
                    for row in range(self.category_table.rowCount()):
                        category = self.category_table.item(row, 0).text()
                        count = self.category_table.item(row, 1).text()
                        f.write(f"{category}: {count} files\n")
                    f.write("\n")

                    # Audio specs section
                    f.write("AUDIO SPECIFICATIONS\n")
                    f.write("-" * 20 + "\n")
                    for row in range(self.audio_specs_table.rowCount()):
                        spec = self.audio_specs_table.item(row, 0).text()
                        dist = self.audio_specs_table.item(row, 1).text()
                        f.write(f"{spec}: {dist}\n")

                QMessageBox.information(
                    self, "Export Successful", f"Report exported to:\n{filename}"
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export report:\n{str(e)}"
                )


def show_analytics_dashboard(wav_viewer):
    """Show analytics dashboard for all WAV files in viewer.

    Collects all WAV files from the provided WavViewer instance and
    displays the analytics dashboard. Shows an information dialog if
    no WAV files are found.

    Args:
        wav_viewer (WavViewer): WavViewer instance containing file list
            in its file_list widget. Files are stored in Qt.UserRole data.
    """
    wav_files = []

    # Collect all WAV file paths
    for i in range(wav_viewer.file_list.count()):
        item = wav_viewer.file_list.item(i)
        if item:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                wav_files.append(file_path)

    if not wav_files:
        QMessageBox.information(
            wav_viewer, "No Data", "No WAV files found for analysis."
        )
        return

    dashboard = AnalyticsDashboard(wav_viewer, wav_files)
    dashboard.exec_()


def select_wav_directory():
    """Ask user to choose a directory with WAV files.

    Opens a directory selection dialog and returns a list of all WAV files
    found in the selected directory. Only includes actual files (not directories)
    with .wav extensions (case-insensitive).

    Returns:
        list[str]: List of absolute WAV file paths in selected directory.
            Returns empty list if no directory selected or no WAV files found.
    """
    folder = QFileDialog.getExistingDirectory(None, "Select directory with WAV files")
    if not folder:
        return []

    wav_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".wav") and os.path.isfile(os.path.join(folder, f))
    ]
    return wav_files


def main():
    """Main function for standalone execution.

    Entry point for running the analytics dashboard as a standalone application. Prompts
    user to select a directory containing WAV files, then displays the analytics
    dashboard. Shows information dialog if no files found.

    Creates QApplication instance and handles proper application shutdown.
    """
    app = QApplication(sys.argv)

    wav_files = select_wav_directory()
    if not wav_files:
        QMessageBox.information(None, "No Files", "No WAV files found.")
        return

    dashboard = AnalyticsDashboard(None, wav_files)
    result = dashboard.exec_()

    # Optioneel: stop de app netjes
    app.quit()
    sys.exit(result)


if __name__ == "__main__":
    main()
