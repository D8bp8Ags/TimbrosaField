"""Cue Points Analysis and Management System.

This module provides comprehensive cue point analysis and navigation functionality
for field recording applications. It enables users to view, filter, analyze, and
navigate to specific cue points across their WAV file collections.

The cue points manager supports various cue point types including MARK, PEAK,
custom labels, and unlabeled points. It provides filtering capabilities, visual
color coding, navigation integration, and CSV export functionality.

Classes:
    CuePointsAnalysisDialog: Main dialog for cue point analysis and management

Functions:
    show_cue_analysis: Create and display the cue points analysis dialog

Features:
    - Comprehensive cue point analysis across WAV collections
    - Type-based filtering (MARK, PEAK, Custom, Unlabeled)
    - Visual color coding by cue point type
    - Navigation integration with main audio player
    - CSV export functionality with detailed metadata
    - Real-time statistics and filtering
    - Double-click navigation to cue points
    - Sorted display by file and timestamp
"""

import csv
import logging
import os
from collections import defaultdict
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
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


class CuePointsAnalysisDialog(QDialog):
    """Specialized dialog for cue points analysis and navigation.

    A comprehensive interface for analyzing, filtering, and navigating cue points
    across WAV file collections. Provides detailed analysis of cue point types,
    timestamps, and labels with integrated navigation capabilities.

    The dialog supports multiple cue point types (MARK, PEAK, Custom, Unlabeled)
    with visual color coding, filtering options, and direct navigation to specific
    cue points in the main audio player interface.

    Attributes:
        main_window: Reference to the main application window
        cue_data (list): Complete list of analyzed cue point data
        cue_table (QTableWidget): Main table displaying cue point information
        type_filter (QComboBox): Filter dropdown for cue point types
        show_empty_checkbox (QCheckBox): Option to show files without cue points
        stats_label (QLabel): Statistics display for cue point analysis

    Args:
        main_window: Main application window instance for navigation integration
    """

    def __init__(self, main_window):
        """Initialize the cue points analysis dialog.

        Sets up the dialog with reference to the main window and initializes
        the user interface components for cue point analysis and navigation.

        Args:
            main_window: Main application window instance used for file access
                and navigation integration
        """
        super().__init__(main_window)

        self.cue_data = []

        self.setWindowTitle("📍 Cue Points Overview & Analysis")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        self.main_window = main_window

        # self.parent_viewer = parent
        self.setup_ui()
        # self.analyze_cue_points()

    def setup_ui(self):
        """Setup the user interface components.

        Creates and arranges all UI elements including the cue points table,
        filter controls, statistics display, and navigation buttons. Configures
        table columns, headers, and visual styling.

        UI Components created:
        - Header with analysis title
        - Filter controls (type filter dropdown, empty files checkbox)
        - Statistics summary label
        - Main cue points table with color coding
        - Navigation and export action buttons
        """
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<h2>📍 Cue Points Analysis</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Filters
        filter_layout = QHBoxLayout()

        # Cue type filter
        filter_layout.addWidget(QLabel("Filter by type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(
            ["All Types", "MARK_ only", "PEAK_ only", "Unlabeled", "Custom labels"]
        )
        self.type_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.type_filter)

        # Show empty files checkbox
        self.show_empty_checkbox = QCheckBox("Show files without cue points")
        self.show_empty_checkbox.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.show_empty_checkbox)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Statistics summary
        self.stats_label = QLabel("Loading statistics...")
        layout.addWidget(self.stats_label)

        # Main table
        self.cue_table = QTableWidget(0, 6)
        self.cue_table.setHorizontalHeaderLabels(
            ["File", "Cue ID", "Label", "Time", "Type", "Actions"]
        )
        # ✅ FIXED: Set proper column resize modes for consistent behavior
        # self.cue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)  # File - can resize
        # self.cue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Cue ID - fit content
        # self.cue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)  # Label - can resize
        # self.cue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Time - fit content
        # self.cue_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Type - fit content
        self.cue_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )  # Actions - always stretch

        # ✅ ADDITIONAL: Set minimum widths to prevent squashing
        self.cue_table.setColumnWidth(0, 1250)  # File column minimum width
        self.cue_table.setColumnWidth(2, 200)  # Label column minimum width

        # self.cue_table.horizontalHeader().setStretchLastSection(True)
        self.cue_table.cellDoubleClicked.connect(self.navigate_to_cue)
        layout.addWidget(self.cue_table)

        # Buttons
        button_layout = QHBoxLayout()

        # Navigation button
        nav_button = QPushButton("🎯 Go to Selected Cue")
        nav_button.clicked.connect(self.navigate_to_selected_cue)
        button_layout.addWidget(nav_button)

        button_layout.addStretch()

        # Export cue points
        export_button = QPushButton("📤 Export Cue List")
        export_button.clicked.connect(self.export_cue_points)
        button_layout.addWidget(export_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    # def analyze_cue_points_old(self):
    #
    #     # if not self.main_window.file_manager:
    #     #     return
    #
    #     # Get all WAV files via FileManager
    #     try:
    #         wav_files = self.main_window.file_manager.get_all_wav_files()
    #     except Exception as e:
    #         print(f"❌ Error getting WAV files: {e}")
    #         return
    #
    #     # if not wav_files:
    #     #     print("📂 No WAV files found for cue analysis")
    #     #     self.stats_label.setText("📂 No WAV files available")
    #     #     return
    #
    #     # self.cue_data = []
    #     files_with_cues = 0
    #     total_cues = 0
    #     cue_types = defaultdict(int)
    #
    #     # ✅ SINGLE LOOP - All analysis logic moved here
    #     for file_path in wav_files:
    #         if not os.path.exists(file_path):
    #             continue
    #
    #         try:
    #             result = wav_analyze(file_path)
    #             cue_points = result.get("cue_points", [])
    #             cue_labels = result.get("cue_labels", {})
    #             fmt_info = result.get("fmt", {})
    #             sample_rate = fmt_info.get("Sample rate", 44100)
    #
    #             file_has_cues = False
    #
    #             for cue in cue_points:
    #                 offset = cue.get("Sample Offset", 0)
    #                 cue_id_raw = cue.get("ID", "")
    #                 cue_id = str(cue_id_raw)
    #
    #                 if offset > 0:
    #                     file_has_cues = True
    #                     total_cues += 1
    #
    #                     # Get label - try both integer and string keys
    #                     label = ""
    #                     if isinstance(cue_id_raw, int):
    #                         label = cue_labels.get(
    #                             cue_id_raw, ""
    #                         )  # Try integer key first
    #                     if not label:
    #                         label = cue_labels.get(
    #                             cue_id, ""
    #                         )  # Try string key as fallback
    #
    #                     # print(f"🔍 Debug cue {cue_id_raw}: found label '{label}'")
    #
    #                     # Determine cue type based on label
    #                     if label.startswith("MARK_"):
    #                         cue_type = "MARK"
    #                     elif label.startswith("PEAK_"):
    #                         cue_type = "PEAK"
    #                     elif label and label.strip():  # Non-empty label
    #                         cue_type = "Custom"
    #                     else:
    #                         cue_type = "Unlabeled"
    #
    #                     cue_types[cue_type] += 1
    #
    #                     # Calculate time
    #                     time_seconds = offset / sample_rate
    #                     time_str = (
    #                         f"{int(time_seconds // 60):02d}:{time_seconds % 60:05.2f}"
    #                     )
    #
    #                     self.cue_data.append(
    #                         {
    #                             "file": os.path.basename(file_path),
    #                             "file_path": file_path,
    #                             "cue_id": cue_id,
    #                             "label": label,
    #                             "time_seconds": time_seconds,
    #                             "time_str": time_str,
    #                             "type": cue_type,
    #                             "offset": offset,
    #                         }
    #                     )
    #
    #             if file_has_cues:
    #                 files_with_cues += 1
    #
    #         except Exception as e:
    #             print(f"❌ Error analyzing cues in {file_path}: {e}")
    #
    #     # Update statistics
    #     total_files = len(wav_files)
    #     stats_text = (
    #         f"📊 {total_cues} cue points in {files_with_cues}/{total_files} files | "
    #         f"Types: {dict(cue_types)}"
    #     )
    #     self.stats_label.setText(stats_text)
    #
    #     # Populate table
    #     self.populate_table()

    def analyze_cue_points(self):
        """Analyze cue points in all WAV files.

        Main analysis method that processes all WAV files to extract cue point
        information. Collects statistics, processes individual files, and updates
        the display with comprehensive cue point data.

        The method:
        1. Retrieves all WAV files from the file manager
        2. Initializes analysis statistics containers
        3. Processes each file individually for cue points
        4. Updates the display with collected data and statistics
        """
        # Get WAV files
        try:
            wav_files = self.main_window.file_manager.get_all_wav_files()
        except Exception as e:  # noqa: BLE001
            print(f"❌ Error getting WAV files: {e}")
            return

        # Initialize analysis data
        analysis_stats = {
            "files_with_cues": 0,
            "total_cues": 0,
            "cue_types": defaultdict(int),
        }

        # Process all files
        for file_path in wav_files:
            if os.path.exists(file_path):
                self._analyze_single_file_cues(file_path, analysis_stats)

        # Update display
        self._update_cue_analysis_display(analysis_stats, len(wav_files))

    def _analyze_single_file_cues(self, file_path, analysis_stats):
        """Analyze cue points in a single file.

        Processes a single WAV file to extract cue point information using
        wav_analyze. Updates analysis statistics and stores cue data for
        display and filtering.

        Args:
            file_path (str): Path to the WAV file to analyze
            analysis_stats (dict): Statistics container to update with findings
                including files_with_cues, total_cues, and cue_types counts
        """
        try:
            result = wav_analyze(file_path)
            cue_points = result.get("cue_points", [])
            cue_labels = result.get("cue_labels", {})
            sample_rate = result.get("fmt", {}).get("Sample rate", 44100)

            file_cues = self._process_file_cue_points(
                file_path, cue_points, cue_labels, sample_rate
            )

            # Update statistics
            if file_cues:
                analysis_stats["files_with_cues"] += 1
                analysis_stats["total_cues"] += len(file_cues)

                for cue_data in file_cues:
                    analysis_stats["cue_types"][cue_data["type"]] += 1

        except Exception as e:  # noqa: BLE001
            print(f"❌ Error analyzing cues in {file_path}: {e}")

    def _process_file_cue_points(self, file_path, cue_points, cue_labels, sample_rate):
        """Process cue points for a single file and return cue data.

        Converts raw cue point data from WAV analysis into structured cue data
        entries. Filters out invalid cue points and creates comprehensive data
        entries for display and navigation.

        Args:
            file_path (str): Path to the WAV file being processed
            cue_points (list): Raw cue point data from WAV analysis
            cue_labels (dict): Cue point labels indexed by cue ID
            sample_rate (int): Audio sample rate for time calculations

        Returns:
            list[dict]: List of valid cue data entries for the file
        """
        file_cues = []

        for cue in cue_points:
            cue_data = self._create_cue_data_entry(
                file_path, cue, cue_labels, sample_rate
            )

            if cue_data:  # Only add valid cues (offset > 0)
                file_cues.append(cue_data)
                self.cue_data.append(cue_data)

        return file_cues

    def _create_cue_data_entry(self, file_path, cue, cue_labels, sample_rate):
        """Create a cue data entry from raw cue point data.

        Processes a single raw cue point to create a structured data entry
        with all necessary information for display, filtering, and navigation.
        Handles label resolution, type determination, and time calculations.

        Args:
            file_path (str): Path to the WAV file containing the cue point
            cue (dict): Raw cue point data with ID and Sample Offset
            cue_labels (dict): Label lookup dictionary indexed by cue ID
            sample_rate (int): Audio sample rate for time calculations

        Returns:
            dict or None: Complete cue data entry or None for invalid cues
                Contains file info, cue ID, label, timing, and type data
        """
        offset = cue.get("Sample Offset", 0)

        # Skip invalid cues
        if offset <= 0:
            return None

        cue_id_raw = cue.get("ID", "")
        cue_id = str(cue_id_raw)

        # Get label with fallback strategy
        label = self._get_cue_label(cue_id_raw, cue_id, cue_labels)

        # Determine cue type
        cue_type = self._determine_cue_type(label)

        # Calculate time
        time_seconds = offset / sample_rate
        time_str = f"{int(time_seconds // 60):02d}:{time_seconds % 60:05.2f}"

        return {
            "file": os.path.basename(file_path),
            "file_path": file_path,
            "cue_id": cue_id,
            "label": label,
            "time_seconds": time_seconds,
            "time_str": time_str,
            "type": cue_type,
            "offset": offset,
        }

    def _get_cue_label(self, cue_id_raw, cue_id_str, cue_labels):
        """Get cue label with fallback strategy for different key types.

        Resolves cue point labels using a robust fallback strategy that handles
        both integer and string cue ID keys. Tries integer keys first if available,
        then falls back to string keys.

        Args:
            cue_id_raw: Original cue ID (may be int or string)
            cue_id_str (str): String representation of cue ID
            cue_labels (dict): Label lookup dictionary with mixed key types

        Returns:
            str: Cue point label or empty string if not found
        """
        # Try integer key first if cue_id_raw is int
        if isinstance(cue_id_raw, int):
            label = cue_labels.get(cue_id_raw, "")
            if label:
                return label

        # Fallback to string key
        return cue_labels.get(cue_id_str, "")

    def _determine_cue_type(self, label):
        """Determine cue type based on label content.

        Analyzes cue point labels to categorize them into predefined types
        for filtering and color coding. Recognizes MARK_, PEAK_ prefixes
        and categorizes custom and unlabeled cue points.

        Args:
            label (str): Cue point label text to analyze

        Returns:
            str: Cue type category ('MARK', 'PEAK', 'Custom', or 'Unlabeled')
        """
        if not label or not label.strip():
            return "Unlabeled"

        label_upper = label.upper()

        if label_upper.startswith("MARK_"):
            return "MARK"
        elif label_upper.startswith("PEAK_"):
            return "PEAK"
        else:
            return "Custom"

    def _update_cue_analysis_display(self, analysis_stats, total_files):
        """Update the display with analysis results.

        Updates the statistics label and populates the table with analyzed
        cue point data. Formats comprehensive statistics including file counts,
        cue point totals, and type distributions.

        Args:
            analysis_stats (dict): Complete analysis statistics including
                total_cues, files_with_cues, and cue_types breakdown
            total_files (int): Total number of WAV files analyzed
        """
        stats_text = (
            f"📊 {analysis_stats['total_cues']} cue points in "
            f"{analysis_stats['files_with_cues']}/{total_files} files | "
            f"Types: {dict(analysis_stats['cue_types'])}"
        )
        self.stats_label.setText(stats_text)
        self.populate_table()

    def populate_table(self, data=None):
        """Populate the cue points table with optional filtered data.

        Fills the table widget with cue point data, applying sorting and
        visual formatting. Includes color coding by cue type, data storage
        for navigation, and column resizing optimization.

        Args:
            data (list, optional): Filtered cue data to display. If None,
                uses all available cue data. Defaults to None.

        Note:
            Data is sorted by filename first, then by timestamp for
            consistent chronological display within files.
        """
        # Use provided data or fall back to all cue data
        table_data = data if data is not None else self.cue_data

        # Sort by file, then by time
        sorted_data = sorted(table_data, key=lambda x: (x["file"], x["time_seconds"]))

        self.cue_table.setRowCount(len(sorted_data))

        for i, cue in enumerate(sorted_data):
            # File name
            file_item = QTableWidgetItem(cue["file"])
            file_item.setData(Qt.UserRole, cue["file_path"])  # Store full path
            self.cue_table.setItem(i, 0, file_item)

            # Cue ID
            self.cue_table.setItem(i, 1, QTableWidgetItem(cue["cue_id"]))

            # Label
            label_item = QTableWidgetItem(cue["label"])
            self.cue_table.setItem(i, 2, label_item)

            # Time
            time_item = QTableWidgetItem(cue["time_str"])
            time_item.setData(Qt.UserRole, cue["time_seconds"])  # Store numeric time
            self.cue_table.setItem(i, 3, time_item)

            # Type with color coding
            type_item = QTableWidgetItem(cue["type"])
            if cue["type"] == "MARK":
                type_item.setBackground(QColor(255, 165, 0, 100))  # Orange
            elif cue["type"] == "PEAK":
                type_item.setBackground(QColor(255, 0, 0, 100))  # Red
            elif cue["type"] == "Custom":
                type_item.setBackground(QColor(0, 255, 0, 100))  # Green
            else:
                type_item.setBackground(QColor(128, 128, 128, 100))  # Gray
            self.cue_table.setItem(i, 4, type_item)

            # Actions (navigation hint)
            action_item = QTableWidgetItem("Double-click to navigate")
            action_item.setForeground(QColor(100, 100, 100))
            self.cue_table.setItem(i, 5, action_item)

        self.cue_table.resizeColumnsToContents()

        self.cue_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )  # Ensure Actions column always stretches

    def apply_filters(self):
        """Apply filters to the cue points table.

        Filters the cue point data based on selected type filter and empty
        files checkbox. Updates the table display and statistics to show
        only matching cue points.

        Supported filters:
        - Type filters: All Types, MARK_ only, PEAK_ only, Unlabeled, Custom labels
        - Empty files option: Show/hide files without cue points

        Updates both the table content and statistics display to reflect
        the filtered view.
        """
        """Apply filters to the cue points table."""
        print("🔍 === apply_filters() called ===")
        print(f"🔍 currentText(): '{self.type_filter.currentText()}'")
        print(f"🔍 currentIndex(): {self.type_filter.currentIndex()}")
        print(f"🔍 currentData(): {self.type_filter.currentData()}")
        """Apply filters to the cue points table."""
        if not hasattr(self, "cue_data") or not self.cue_data:
            print("📂 No cue data available for filtering")
            return

        filter_type = self.type_filter.currentText()
        show_empty = self.show_empty_checkbox.isChecked()

        print(f"🔍 Applying filters: Type='{filter_type}', Show Empty={show_empty}")

        # Start with all cue data
        filtered_data = list(self.cue_data)

        # Apply type filter
        if filter_type != "All Types":
            if filter_type == "MARK_ only":
                filtered_data = [cue for cue in filtered_data if cue["type"] == "MARK"]
            elif filter_type == "PEAK_ only":
                filtered_data = [cue for cue in filtered_data if cue["type"] == "PEAK"]
            elif filter_type == "Unlabeled":
                filtered_data = [
                    cue for cue in filtered_data if cue["type"] == "Unlabeled"
                ]
            elif filter_type == "Custom labels":
                filtered_data = [
                    cue for cue in filtered_data if cue["type"] == "Custom"
                ]

        # Todo
        # Apply empty files filter (show_empty checkbox)
        # if not show_empty:
        #     # Get files that have cue points
        #     files_with_cues = set(cue["file"] for cue in filtered_data)
        #     # Keep only cues from files that have cue points (this is redundant but matches the intent)
        #     # The "show empty files" probably means files without ANY cue points
        #     # For now, we'll just keep the current filtered data since empty files wouldn't have cues anyway
        #     pass

        print(
            f"📊 Filter result: {len(filtered_data)} cue points (from {len(self.cue_data)} total)"
        )

        # Update table with filtered data
        self.populate_table(filtered_data)

        # Update statistics for filtered view
        self._update_filtered_statistics(filtered_data)

    def _update_filtered_statistics(self, filtered_data):
        """Update statistics label for filtered view.

        Recalculates and displays statistics for the current filtered data set.
        Shows appropriate messaging for empty filter results and provides
        context about the active filter settings.

        Args:
            filtered_data (list): Current filtered cue point data set
        """
        if not filtered_data:
            self.stats_label.setText("📊 No cue points match current filters")
            return

        # Calculate statistics for filtered data
        total_cues = len(filtered_data)
        files_with_cues = len(set(cue["file"] for cue in filtered_data))

        cue_types = defaultdict(int)
        for cue in filtered_data:
            cue_types[cue["type"]] += 1

        # Get total files count (unchanged by filter)
        total_files = len(set(cue["file"] for cue in self.cue_data))

        filter_type = self.type_filter.currentText()
        if filter_type != "All Types":
            stats_text = (
                f"📊 {total_cues} {filter_type.lower()} cue points in "
                f"{files_with_cues}/{total_files} files | Types: {dict(cue_types)}"
            )
        else:
            stats_text = (
                f"📊 {total_cues} cue points in {files_with_cues}/{total_files} files | "
                f"Types: {dict(cue_types)}"
            )

        self.stats_label.setText(stats_text)

    # Todo make work / central
    def navigate_to_cue(self, row, column):
        """Navigate to the double-clicked cue point.

        Handles double-click events on table rows to navigate to the specific
        cue point in the main audio player. Extracts file path and timestamp
        from the table data and triggers navigation.

        Args:
            row (int): Table row index that was double-clicked
            column (int): Table column index (unused but required by signal)
        """
        file_item = self.cue_table.item(row, 0)
        time_item = self.cue_table.item(row, 3)

        if not file_item or not time_item:
            return

        file_path = file_item.data(Qt.UserRole)
        time_seconds = time_item.data(Qt.UserRole)

        # Navigate in parent viewer
        self.navigate_to_file_and_time(file_path, time_seconds)

    def navigate_to_selected_cue(self):
        """Navigate to currently selected cue.

        Triggers navigation to the currently selected table row without requiring a
        double-click. Uses the same navigation logic as double-click handling.
        """
        current_row = self.cue_table.currentRow()
        if current_row >= 0:
            self.navigate_to_cue(current_row, 0)

    def navigate_to_file_and_time(self, file_path, time_seconds):
        """Navigate parent viewer to specific file and time.

        Integrates with the main audio player to navigate to a specific file
        and timestamp. Selects the file in the file list, seeks to the cue point
        time, and optionally starts playback.

        Args:
            file_path (str): Full path to the WAV file to navigate to
            time_seconds (float): Timestamp in seconds to seek to

        Note:
            Closes the cue points dialog after successful navigation and
            brings the parent window to front for immediate interaction.
        """
        try:
            # Find and select the file in parent's file list
            for i in range(self.parent_viewer.file_list.count()):
                item = self.parent_viewer.file_list.item(i)
                if item and item.data(Qt.UserRole) == file_path:
                    self.parent_viewer.file_list.setCurrentRow(i)
                    break

            # Seek to the cue point time
            if hasattr(self.parent_viewer, "audio_player"):
                position_ms = int(time_seconds * 1000)
                self.parent_viewer.audio_player.seek_to_position(position_ms)

                # Start playback
                if self.parent_viewer.audio_player.is_stopped():
                    self.parent_viewer.audio_player.play()

            # Close this dialog and bring parent to front
            self.accept()
            self.parent_viewer.activateWindow()
            self.parent_viewer.raise_()

            print(
                f"🎯 Navigated to {os.path.basename(file_path)} at {time_seconds:.2f}s"
            )

        except Exception as e:
            QMessageBox.warning(
                self, "Navigation Error", f"Could not navigate to cue:\n{str(e)}"
            )

    def export_cue_points(self):
        """Export cue points list to CSV.

        Creates a CSV file containing all cue point data with comprehensive
        metadata including file names, cue IDs, labels, timestamps, and types.
        Provides user feedback about export success or failure.

        The CSV includes columns:
        - File: Filename containing the cue point
        - Cue ID: Internal cue point identifier
        - Label: Cue point label text
        - Time (s): Timestamp in seconds
        - Time (mm:ss): Human-readable timestamp
        - Type: Cue point category (MARK, PEAK, Custom, Unlabeled)
        """
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cue Points",
            f"cue_points_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "CSV Files (*.csv);;All Files (*)",
        )

        if filename:
            try:
                with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(
                        ["File", "Cue ID", "Label", "Time (s)", "Time (mm:ss)", "Type"]
                    )

                    for cue in sorted(
                        self.cue_data, key=lambda x: (x["file"], x["time_seconds"])
                    ):
                        writer.writerow(
                            [
                                cue["file"],
                                cue["cue_id"],
                                cue["label"],
                                f"{cue['time_seconds']:.2f}",
                                cue["time_str"],
                                cue["type"],
                            ]
                        )

                QMessageBox.information(
                    self, "Export Successful", f"Cue points exported to:\n{filename}"
                )

            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )


# Add this method to MainWindow class:
def show_cue_analysis(self):
    """Show cue points analysis dialog.

    Creates and displays the cue points analysis dialog for the current
    WAV file collection. Provides access to comprehensive cue point
    analysis, filtering, and navigation functionality.

    Note:
        This function is designed to be added to the MainWindow class
        as a method for menu or button integration.
    """
    dialog = CuePointsAnalysisDialog(self.wav_viewer)
    dialog.exec_()
