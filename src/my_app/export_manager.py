"""Export Manager Module for Field Recorder Analyzer.

This module provides a comprehensive export management system that handles all
field recording export operations including CSV metadata export, Ableton Live
set generation, analytics dashboard integration, and JSON tag backup.

The module is designed with a clean separation of concerns, extracting export
functionality from the main window and menu systems to improve code organization,
maintainability, and testing capabilities.

Classes:
    ExportManager: Central coordinator for all export operations
    CSVExporter: Handles CSV metadata and JSON tag export operations
    AbletonExporter: Manages Ableton Live set generation and export
    AnalyticsLauncher: Handles analytics dashboard integration
    ExportManagerInterface: Main interface for external components

Features:
    - CSV metadata export with comprehensive WAV file analysis
    - JSON tag backup and export functionality
    - Ableton Live multitrack set generation with category organization
    - Analytics dashboard integration with file statistics
    - Progress tracking and user feedback for long operations
    - Comprehensive error handling and logging
    - Export history tracking and statistics
    - Modular design for easy testing and maintenance

Export Types:
    - CSV: Complete metadata export with analysis results
    - JSON: Tag backup with statistics and file organization
    - Ableton Live: Multitrack project generation with category-based tracks
    - Analytics: Interactive dashboard for collection analysis
"""

import csv
import json
import logging
import os
import time
from collections import Counter
from datetime import datetime
from typing import Any

# from ableton_generator import AbletonLiveSetGenerator
from ableton_generator_optimized import AbletonLiveSetGeneratorV3Optimized
from analytics_dashboard import AnalyticsDashboard
from PyQt5.QtWidgets import QFileDialog, QMessageBox
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


class ExportManager:
    """Central coordinator for all export operations.

    Serves as the main coordination hub for all field recording export functionality.
    Manages specialized exporter instances and provides a unified interface for
    different export types including CSV, Ableton Live, and analytics operations.

    The manager follows a composition pattern, delegating specific export operations
    to specialized classes while maintaining overall coordination and providing
    export statistics and status information.

    Attributes:
        main_window: Reference to main application window
        csv_exporter (CSVExporter): Handles CSV and JSON export operations
        ableton_exporter (AbletonExporter): Manages Ableton Live export
        analytics_launcher (AnalyticsLauncher): Handles analytics dashboard

    Args:
        main_window: Main application window instance for UI integration
    """

    def __init__(self, main_window):
        """Initialize export manager with reference to main window.

        Sets up the export manager with specialized exporter instances
        for different export types. Each exporter handles its own specific
        functionality while the manager coordinates overall operations.

        Args:
            main_window: Main application window instance used for UI
                integration, progress feedback, and file management access
        """
        self.main_window = main_window
        # self.wav_viewer = main_window.wav_viewer

        # Initialize specialized exporters
        self.csv_exporter = CSVExporter(main_window)
        self.ableton_exporter = AbletonExporter(main_window)
        self.analytics_launcher = AnalyticsLauncher(main_window)

        logger.info("ExportManager initialized with specialized exporters")

    # === PUBLIC INTERFACE METHODS ===

    def export_metadata_csv(self) -> bool:
        """Export metadata to CSV file.

        Delegates CSV metadata export to the specialized CSVExporter instance.
        Logs the export request and returns the operation result.

        Returns:
            bool: True if export completed successfully, False otherwise
        """
        logger.debug("Export requested: Metadata CSV")
        return self.csv_exporter.export_metadata_csv()

    def export_to_ableton(self) -> bool:
        """Export to Ableton Live set."""
        logger.debug("Export requested: Ableton Live")
        return self.ableton_exporter.export_to_ableton()

    def show_analytics_dashboard(self) -> bool:
        """Show analytics dashboard.

        Delegates analytics dashboard display to the AnalyticsLauncher instance.
        Opens interactive dashboard with comprehensive collection analysis.

        Returns:
            bool: True if dashboard opened successfully, False otherwise
        """
        logger.debug("Export requested: Analytics Dashboard")
        return self.analytics_launcher.show_analytics_dashboard()

    def export_tags_json(self, output_path: str | None = None) -> bool:
        """Export all tags to JSON file.

        Delegates JSON tag export to the CSVExporter instance. Creates
        comprehensive tag backup with statistics and file organization.

        Args:
            output_path (str, optional): Custom output path for JSON file.
                If None, prompts user for file location. Defaults to None.

        Returns:
            bool: True if export completed successfully, False otherwise
        """
        logger.debug("Export requested: Tags JSON")
        return self.csv_exporter.export_tags_json(output_path)

    def get_export_statistics(self) -> dict[str, Any]:
        """Get statistics about exportable content.

        Collects comprehensive statistics about the current collection
        and available export capabilities. Useful for UI state management
        and export planning.

        Returns:
            dict[str, Any]: Statistics dictionary containing:
                - wav_files_count (int): Number of WAV files available
                - has_analytics (bool): Whether analytics dashboard is available
                - has_ableton_export (bool): Whether Ableton export is available
                - export_directory (str): Current export directory path
        """
        return {
            "wav_files_count": len(self.main_window.file_manager.get_all_wav_files()),
            "has_analytics": self.analytics_launcher.is_analytics_available(),
            "has_ableton_export": self.ableton_exporter.is_ableton_export_available(),
            "export_directory": self.main_window.user_config_manager.user_config.get(
                "paths", {}
            ).get("ableton_export_dir", "Ableton"),
        }


class CSVExporter:
    """Handles CSV and JSON export operations.

    Specialized exporter for CSV metadata and JSON tag operations. Provides
    comprehensive WAV file analysis with detailed metadata extraction, progress
    tracking, and robust error handling for field recording workflows.

    The exporter supports both metadata export to CSV format and tag backup
    to JSON format, with full statistics and organizational capabilities.

    Key Features:
    - Complete WAV metadata analysis and extraction
    - CSV export with detailed file information and status tracking
    - JSON tag backup with statistics and categorization
    - Progress tracking for long operations
    - Comprehensive error handling and reporting
    - User-friendly dialog integration

    Attributes:
        main_window: Reference to main application window for UI integration

    Args:
        main_window: Main application window instance for dialog and progress access
    """

    def __init__(self, main_window):
        """Initialize CSV exporter.

        Sets up the CSV and JSON exporter with reference to the main window
        for UI integration, progress feedback, and file management access.

        Args:
            main_window: Main application window instance used for dialogs,
                progress tracking, and file management operations
        """
        self.main_window = main_window
        # self.wav_viewer = main_window.wav_viewer

        logger.debug("CSVExporter initialized")

    def export_metadata_csv(self) -> bool:
        """Export all metadata to CSV file with progress tracking.

        Performs comprehensive metadata export of all WAV files to CSV format.
        Includes complete file analysis, metadata extraction, cue point counting,
        and detailed status reporting for each file.

        The export process:
        1. Prompts user for output filename
        2. Analyzes all WAV files using wav_analyze
        3. Extracts metadata including INFO and fmt chunks
        4. Counts cue points and handles errors gracefully
        5. Provides progress feedback and final results

        Returns:
            bool: True if export completed successfully, False if cancelled
                or failed. Success is determined by file creation, not individual
                file analysis results.
        """
        logger.info("Starting CSV metadata export")

        try:
            # Get output filename
            filename = self._get_csv_export_filename()
            if not filename:
                logger.debug("CSV export cancelled by user")
                return False

            # Get WAV files via FileManager
            wav_files = self.main_window.file_manager.get_all_wav_files()

            if not wav_files:
                self.main_window.show_status_message(
                    "No WAV files found for export", 3000
                )
                logger.warning("No WAV files available for CSV export")
                return False

            logger.info(f"Exporting metadata for {len(wav_files)} WAV files to CSV")

            # Show progress
            self.main_window.ui_manager.show_progress(
                "Exporting metadata...", len(wav_files) + 10
            )

            success = self._write_csv_file(filename, wav_files)

            # Hide progress
            self.main_window.ui_manager.hide_progress()

            if success:
                logger.info(f"CSV export completed successfully: {filename}")
                return True
            else:
                logger.error("CSV export failed")
                return False

        except Exception as e:
            self.main_window.ui_manager.hide_progress()
            error_msg = f"CSV export failed: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(
                self.main_window, "Export Error", f"Fout bij CSV export:\n{str(e)}"
            )
            return False

    def _get_csv_export_filename(self) -> str | None:
        """Get filename for CSV export via dialog.

        Opens a file save dialog to allow user selection of CSV output filename.
        Uses timestamp-based default naming for organization.

        Returns:
            str or None: Selected filename path if user confirms, None if cancelled
        """
        default_name = (
            f"field_recording_metadata_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Metadata to CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )

        return filename if filename else None

    def _write_csv_file(self, filename: str, wav_files: list[str]) -> bool:
        """Write metadata to CSV file with progress updates.

        Performs the actual CSV file writing with comprehensive metadata extraction
        and progress tracking. Handles individual file analysis errors gracefully
        while maintaining overall export integrity.

        Args:
            filename (str): Output CSV filename path
            wav_files (list[str]): List of WAV file paths to process

        Returns:
            bool: True if file was written successfully, False on write errors

        Note:
            Individual file analysis errors are captured in the CSV status column
            rather than failing the entire export operation.
        """
        try:
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write CSV header
                header = [
                    "Filename",
                    "INAM",
                    "IART",
                    "ICRD",
                    "ISFT",
                    "IENG",
                    "ICMT",
                    "Sample Rate",
                    "Channels",
                    "Bit Depth",
                    "Format",
                    "Cue Points",
                    "Status",
                ]
                writer.writerow(header)
                self.main_window.ui_manager.update_progress(5, "CSV header written...")

                success_count = 0
                error_count = 0

                # Process each WAV file using _analyze_wav_file
                for i, file_path in enumerate(wav_files):
                    filename_only = os.path.basename(file_path)

                    try:
                        # Update progress
                        progress = 5 + ((i + 1) / len(wav_files)) * 90
                        self.main_window.ui_manager.update_progress(
                            int(progress),
                            f"Processing {filename_only}... ({i + 1}/{len(wav_files)})",
                        )

                        # ✅ USE THE COMPLETE _analyze_wav_file METHOD
                        row_data = self._analyze_wav_file(file_path)
                        writer.writerow(row_data)

                        # Check if analysis was successful
                        if row_data[12] == "Success":  # Status column
                            success_count += 1
                            logger.debug(
                                f"Successfully processed for CSV: {filename_only}"
                            )
                        else:
                            error_count += 1
                            logger.warning(
                                f"Analysis failed for {filename_only}: {row_data[12]}"
                            )

                    except Exception as e:
                        # This shouldn't happen since _analyze_wav_file handles its own exceptions
                        # But just in case...
                        logger.error(
                            f"Unexpected error in CSV processing for {filename_only}: {e}"
                        )
                        error_row = (
                            [filename_only]
                            + [""] * 11
                            + [f"Processing error: {str(e)[:30]}"]
                        )
                        writer.writerow(error_row)
                        error_count += 1

                # Final progress update
                self.main_window.ui_manager.update_progress(95, "Finalizing CSV...")

                # Show results to user
                self._show_csv_results(
                    filename, success_count, error_count, len(wav_files)
                )

                return True

        except Exception as e:
            logger.error(f"Error writing CSV file {filename}: {e}")
            raise

    def _analyze_wav_file(self, file_path: str) -> list[str]:
        """Analyze single WAV file and return CSV row data.

        Performs comprehensive analysis of a single WAV file using wav_analyze
        and returns formatted data for CSV export. Handles various error conditions
        gracefully and provides detailed status information.

        The analysis extracts:
        - INFO chunk metadata (INAM, IART, ICRD, ISFT, IENG, ICMT)
        - Format information (sample rate, channels, bit depth, format name)
        - Cue point count (only valid cue points with offset > 0)
        - Processing status and error information

        Args:
            file_path (str): Full path to the WAV file to analyze

        Returns:
            list[str]: List of 13 strings representing CSV row data:
                [filename, INAM, IART, ICRD, ISFT, IENG, ICMT,
                 sample_rate, channels, bit_depth, format, cue_points, status]

        Note:
            Errors are captured in the status field rather than raising exceptions,
            allowing the export to continue with other files.
        """
        filename_only = os.path.basename(file_path)

        try:

            result = wav_analyze(file_path)

            # Handle case where wav_analyze returns None
            if result is None:
                logger.warning(f"wav_analyze returned None for {filename_only}")
                return [filename_only] + [""] * 11 + ["Analysis returned None"]

            # Extract data sections safely with fallbacks
            info = result.get("info", {})
            fmt = result.get("fmt", {})
            cue_points = result.get("cue_points", [])

            # Additional safety checks
            if info is None:
                info = {}
            if fmt is None:
                fmt = {}
            if cue_points is None:
                cue_points = []

            # Count valid cue points (only those with sample offset > 0)
            valid_cue_count = 0
            if isinstance(cue_points, list):
                for cp in cue_points:
                    if isinstance(cp, dict) and cp.get("Sample Offset", 0) > 0:
                        valid_cue_count += 1

            # Build CSV row data with safe extraction
            row_data = [
                filename_only,  # 0: Filename
                info.get("INAM", ""),  # 1: Title/Name
                info.get("IART", ""),  # 2: Artist
                info.get("ICRD", ""),  # 3: Creation Date
                info.get("ISFT", ""),  # 4: Software
                info.get("IENG", ""),  # 5: Engineer
                info.get("ICMT", ""),  # 6: Comments/Tags
                str(fmt.get("Sample rate", "")),  # 7: Sample Rate
                str(fmt.get("Channels", "")),  # 8: Channels
                str(fmt.get("Bits per sample", "")),  # 9: Bit Depth
                fmt.get("Audio format name", ""),  # 10: Format
                str(valid_cue_count),  # 11: Cue Points
                "Success",  # 12: Status
            ]

            return row_data

        except FileNotFoundError:
            logger.error(f"File not found: {filename_only}")
            return [filename_only] + [""] * 11 + ["File not found"]

        except PermissionError:
            logger.error(f"Permission denied reading: {filename_only}")
            return [filename_only] + [""] * 11 + ["Permission denied"]

        except ImportError as e:
            logger.error(f"wav_analyzer import failed for {filename_only}: {e}")
            return [filename_only] + [""] * 11 + ["wav_analyzer not available"]

        except Exception as e:
            logger.error(f"Unexpected error analyzing {filename_only}: {e}")
            # Truncate error message to prevent CSV formatting issues
            error_msg = str(e)[:50] + "..." if len(str(e)) > 50 else str(e)
            return [filename_only] + [""] * 11 + [f"Error: {error_msg}"]

    def _show_csv_results(
        self, filename: str, success_count: int, error_count: int, total_count: int
    ):
        """Show CSV export results to user.

        Displays comprehensive export results with success/error counts
        and provides appropriate message box type based on results.

        Args:
            filename (str): Output CSV filename for user reference
            success_count (int): Number of successfully processed files
            error_count (int): Number of files with processing errors
            total_count (int): Total number of files processed (unused)
        """
        message = "Metadata export voltooid!\n\n"
        message += f"📄 Bestand: {os.path.basename(filename)}\n"
        message += f"✅ Succesvol verwerkt: {success_count} bestanden\n"

        if error_count > 0:
            message += f"❌ Fouten: {error_count} bestanden\n"
            message += "\nCheck de Status kolom in de CSV voor details."

        # Choose appropriate message box type
        if error_count > 0 and success_count == 0:
            QMessageBox.critical(self.main_window, "Export Gefaald", message)
        elif error_count > 0:
            QMessageBox.warning(
                self.main_window, "Export Voltooid met Waarschuwingen", message
            )
        else:
            QMessageBox.information(self.main_window, "Export Voltooid", message)

        # Update status bar
        if success_count > 0:
            self.main_window.show_status_message(
                f"CSV export: {success_count} files processed", 3000
            )
        else:
            self.main_window.show_status_message("CSV export failed", 3000)

    def export_tags_json(self, output_path: str | None = None) -> bool:
        """Export all tags to JSON file for backup/analysis.

        Creates comprehensive JSON export of all tags from WAV files with
        statistics, file organization, and metadata. Useful for backup,
        analysis, and integration with other tools.

        Args:
            output_path (str, optional): Custom output path. If None,
                prompts user with file dialog. Defaults to None.

        Returns:
            bool: True if export completed successfully, False otherwise
        """
        logger.info("Starting JSON tags export")

        try:
            if not output_path:
                output_path = self._get_json_export_filename()
                if not output_path:
                    logger.debug("JSON export cancelled by user")
                    return False

            # Collect all tags from all files
            tags_data = self._collect_all_tags()

            if not tags_data["files"]:
                self.main_window.show_status_message("No tagged files found", 3000)
                logger.warning("No tagged files available for JSON export")
                return False

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(tags_data, f, indent=2, ensure_ascii=False)

            self.main_window.show_status_message(
                f"Tags exported to JSON: {len(tags_data['files'])} files", 3000
            )
            logger.info(
                f"JSON tags export completed: {output_path} ({len(tags_data['files'])} files)"
            )

            return True

        except Exception as e:
            logger.error(f"JSON tags export failed: {e}")
            QMessageBox.critical(
                self.main_window, "Export Error", f"JSON export failed:\n{str(e)}"
            )
            return False

    def _get_json_export_filename(self) -> str | None:
        """Get filename for JSON export via dialog."""
        default_name = (
            f"field_recording_tags_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Tags to JSON",
            default_name,
            "JSON Files (*.json);;All Files (*)",
        )

        return filename if filename else None

    def _collect_all_tags(self) -> dict[str, Any]:
        """Collect all tags from all WAV files."""
        wav_files = self.main_window.file_manager.get_all_wav_files()

        export_data = {
            "export_info": {
                "timestamp": datetime.now().isoformat(),
                "total_files": len(wav_files),
                "exported_by": "Field Recorder Analyzer",
            },
            "files": [],
            "tag_statistics": {},
        }

        all_tags = []

        for file_path in wav_files:
            try:

                result = wav_analyze(file_path)

                if result and result.get("info", {}).get("ICMT"):
                    tags_string = result["info"]["ICMT"].strip()
                    if tags_string:
                        file_tags = [
                            tag.strip() for tag in tags_string.split(",") if tag.strip()
                        ]

                        export_data["files"].append(
                            {
                                "filename": os.path.basename(file_path),
                                "full_path": file_path,
                                "tags": file_tags,
                                "tag_count": len(file_tags),
                            }
                        )

                        all_tags.extend(file_tags)

            except Exception as e:
                logger.warning(f"Error collecting tags from {file_path}: {e}")

        # Calculate tag statistics

        tag_counts = Counter(all_tags)
        export_data["tag_statistics"] = {
            "unique_tags": len(tag_counts),
            "total_tag_instances": len(all_tags),
            "most_common": tag_counts.most_common(10),
        }

        return export_data


class AbletonExporter:
    """Handles Ableton Live export operations.

    Specialized exporter for creating Ableton Live multitrack sets from WAV
    file collections. Provides category-based track organization, automatic
    clip placement, and comprehensive project generation with metadata integration.

    Features:
    - Multitrack Ableton Live set generation
    - Category-based track organization using tag analysis
    - Automatic clip placement with metadata annotations
    - Progress tracking and user feedback
    - Comprehensive error handling and validation
    - Configurable export directories

    Attributes:
        main_window: Reference to main application window for UI integration

    Args:
        main_window: Main application window instance for configuration and UI access
    """

    def __init__(self, main_window):
        """Initialize Ableton exporter.

        Sets up the Ableton Live exporter with reference to the main window
        for configuration access and UI integration.

        Args:
            main_window: Main application window instance used for configuration,
                progress feedback, and user interaction
        """
        self.main_window = main_window
        # self.wav_viewer = main_window.wav_viewer

        logger.debug("AbletonExporter initialized")

    def export_to_ableton(self) -> bool:
        """Export WAV files to multi-track Ableton Live Set.

        Creates comprehensive Ableton Live project with category-based track
        organization, automatic clip placement, and metadata integration.
        Uses tag analysis to organize files into logical track groupings.

        The export process:
        1. Validates WAV file availability
        2. Generates unique project name with timestamp
        3. Analyzes tags for category-based organization
        4. Creates multitrack Ableton Live set
        5. Provides comprehensive success/failure feedback

        Returns:
            bool: True if export completed successfully, False otherwise
        """
        logger.info("Starting Ableton Live export")

        def progress_callback(current, total, message):
            percent = (current / total) * 100
            self.main_window.show_status_message(
                f"Processing: {percent:.1f}% - {message}", 1000
            )

        try:
            # Check if files are available
            wav_files = self.main_window.file_manager.get_all_wav_files()

            if not wav_files:
                self.main_window.show_status_message(
                    "No WAV files found for Ableton export", 3000
                )
                logger.warning("No WAV files available for Ableton export")
                QMessageBox.warning(
                    self.main_window,
                    "Geen bestanden",
                    "Er zijn geen WAV bestanden om te exporteren.",
                )
                return False

            # Generate project name
            project_name = (
                f"FieldRecordings_MultiTrack_{datetime.now().strftime('%Y%m%d_%H%M')}"
            )
            logger.debug(f"Generated Ableton project name: {project_name}")

            # Show progress and disable button
            # self._set_export_button_state(False, "Analyseren van tags...")
            self.main_window.show_status_message("Analyseren van tags...", 1000)

            try:

                # generator = AbletonLiveSetGenerator("./default_template.als")
                # generator = AbletonLiveSetGeneratorV3Optimized("./default_template.als")

                # self._set_export_button_state(False, "Genereren van tracks...")
                self.main_window.show_status_message("Genereren van tracks...", 1000)

                source_wav_dir = (
                    self.main_window.user_config_manager.get_updated_config()["paths"][
                        "fieldrecording_dir"
                    ]
                )
                # Get export directory
                # export_dir = self.wav_viewer.user_config.get("paths", {}).get("ableton_export_dir", "Ableton")
                export_dir = self.main_window.user_config_manager.get_updated_config()[
                    "paths"
                ]["ableton_export_dir"]
                print(source_wav_dir)
                print(export_dir)
                # Perform export
                # result = generator.create_multitrack_live_set(
                #     directory=source_wav_dir,
                #     output_path=export_dir,
                #     project_name=project_name,
                # )
                # result = generator.create_multitrack_live_set(directory=source_wav_dir)
                generator = AbletonLiveSetGeneratorV3Optimized(
                    "./default_template.als",
                    enable_progress=True,  # Enable progress tracking
                    max_workers=4,  # Parallel processing (pas aan voor jouw systeem)
                )
                start_time = time.time()

                success = generator.create_live_set_from_directory_optimized(
                    directory=source_wav_dir,
                    output_path=export_dir,
                    project_name=project_name,
                    progress_callback=progress_callback,  # ← Hier gebruiken
                    batch_size=50,
                )
                end_time = time.time()

                if success:
                    print("✅ Optimized Live Set creation successful!")
                    stats = generator.get_performance_stats()
                    print(f"📊 Performance: {end_time - start_time:.2f}s total")
                    print(f"⚡ Optimizations: {', '.join(stats['optimizations'])}")
                else:
                    print("❌ Optimized Live Set creation failed!")

                # Check stats na gebruik:
                # status = generator.get_sequential_optimization_status()
                # if status['sequential_optimization_enabled']:
                #     print("🎯 Sequential optimization gebruikt!")
                #
                # if result.get("success", False):
                #     self._show_ableton_success(result, project_name)
                #     logger.info(f"Ableton export successful: {result}")
                #     return True
                # else:
                #     self._show_ableton_error(result)
                #     logger.error(f"Ableton export failed: {result}")
                #     return False
            finally:
                # self._set_export_button_state(True, "🎛️ Export to Ableton Live")
                self.main_window.show_status_message("🎛️ Export to Ableton Live", 1000)

        except ImportError as e:
            logger.error(f"Ableton generator not available: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Niet Beschikbaar",
                f"Ableton Live export is niet beschikbaar:\n{str(e)}\n\nControleer of ableton_generator.py bestaat.",
            )
            return False
        except Exception as e:
            logger.error(f"Ableton export error: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Fout",
                f"Fout tijdens Ableton export:\n{str(e)}",
            )
            return False

    # def _set_export_button_state(self, enabled: bool, text: str):
    #     """Update export button state and text."""
    #     # Try to find and update the export button
    #     try:
    #         # This assumes the button exists in the wav_viewer
    #         if hasattr(self.wav_viewer, 'export_ableton_button'):
    #             self.wav_viewer.export_ableton_button.setEnabled(enabled)
    #             self.wav_viewer.export_ableton_button.setText(text)
    #     except Exception:
    #         # If button update fails, just continue
    #         pass

    def _show_ableton_success(self, result: dict[str, Any], project_name: str):
        """Show Ableton export success dialog."""
        files_processed = result.get("files_processed", 0)
        tracks_created = result.get("tracks_created", 0)
        clips_total = result.get("clips_total", 0)
        categories = result.get("categories", [])

        message = "Ableton Live Set export voltooid! 🎛️\n\n"
        message += f"📁 Project: {project_name}.als\n\n"
        message += "📊 Statistieken:\n"
        message += f"• Bestanden verwerkt: {files_processed}\n"
        message += f"• Tracks aangemaakt: {tracks_created}\n"
        message += f"• Clips geplaatst: {clips_total}\n"

        if categories:
            message += f"• Categorieën: {', '.join(categories[:5])}"
            if len(categories) > 5:
                message += f" (+{len(categories) - 5} meer)"
            message += "\n"

        message += "\n💡 Tips:\n"
        message += "• Clips bevatten tags in de naam en annotation\n"
        message += "• Tracks zijn gegroepeerd per categorie\n"
        message += "• Scenes zijn dynamisch aangepast"

        QMessageBox.information(self.main_window, "Ableton Export Voltooid", message)
        self.main_window.show_status_message(
            f"Ableton export: {tracks_created} tracks created", 3000
        )

    def _show_ableton_error(self, result: dict[str, Any]):
        """Show Ableton export error dialog."""
        error_msg = result.get("error", "Unknown error occurred")

        QMessageBox.critical(
            self.main_window,
            "Ableton Export Gefaald",
            f"Er is een fout opgetreden tijdens het maken van de Ableton Live Set.\n\n"
            f"Error: {error_msg}\n\n"
            f"Controleer de console voor meer informatie.",
        )
        self.main_window.show_status_message("Ableton export failed", 3000)

    #
    # def is_ableton_export_available(self) -> bool:
    #     """Check if Ableton export functionality is available."""
    #     try:
    #         import ableton_generator
    #
    #         return True
    #     except ImportError:
    #         return False


class AnalyticsLauncher:
    """Handles analytics dashboard launching.

    Specialized launcher for the analytics dashboard that provides comprehensive
    WAV collection analysis. Manages dashboard initialization, file integration,
    and availability checking with robust error handling.

    Features:
    - Analytics dashboard initialization and display
    - WAV file collection integration
    - Availability checking and validation
    - Tag analysis and category detection
    - Comprehensive error handling and user feedback
    - Statistics collection for dashboard planning

    Attributes:
        main_window: Reference to main application window for file access

    Args:
        main_window: Main application window instance for file management integration
    """

    def __init__(self, main_window):
        """Initialize analytics launcher.

        Sets up the analytics dashboard launcher with reference to the main
        window for file management integration and UI feedback.

        Args:
            main_window: Main application window instance used for file access,
                status messages, and dialog integration
        """
        self.main_window = main_window
        # self.wav_viewer = main_window.wav_viewer

        logger.debug("AnalyticsLauncher initialized")

    def show_analytics_dashboard(self) -> bool:
        """Show analytics dashboard with WAV files from FileManager.

        Creates and displays the comprehensive analytics dashboard with all
        available WAV files. Provides detailed collection analysis including
        tag statistics, audio specifications, and timeline visualization.

        The process:
        1. Validates analytics dashboard availability
        2. Collects WAV files from file manager
        3. Validates file collection
        4. Creates and displays analytics dashboard
        5. Provides user feedback and status updates

        Returns:
            bool: True if dashboard opened successfully, False otherwise
        """
        logger.info("Opening analytics dashboard")

        try:
            # Check if analytics is available
            if not self.is_analytics_available():
                self.main_window.show_status_message(
                    "Analytics dashboard not available", 3000
                )
                logger.error("Analytics dashboard import failed")
                QMessageBox.warning(
                    self.main_window,
                    "Analytics Niet Beschikbaar",
                    "Analytics dashboard is niet beschikbaar.\n\nControleer of analytics_dashboard.py bestaat.",
                )
                return False

            # Get WAV files via FileManager
            wav_files = self.main_window.file_manager.get_all_wav_files()

            if not wav_files:
                self.main_window.show_status_message(
                    "No WAV files found for analysis", 3000
                )
                logger.warning("No WAV files available for analytics")
                QMessageBox.information(
                    self.main_window,
                    "Geen Data",
                    "Geen WAV bestanden gevonden voor analyse.",
                )
                return False

            logger.debug(f"Opening analytics dashboard with {len(wav_files)} files")

            # Import and show analytics dashboard

            dashboard = AnalyticsDashboard(self.main_window, wav_files)
            dashboard.exec_()

            self.main_window.show_status_message(
                f"Analytics dashboard opened ({len(wav_files)} files)", 2000
            )
            logger.info(
                f"Analytics dashboard opened successfully with {len(wav_files)} files"
            )

            return True

        except ImportError as e:
            logger.error(f"Analytics dashboard import failed: {e}")
            QMessageBox.warning(
                self.main_window,
                "Analytics Niet Beschikbaar",
                f"Analytics dashboard kon niet geladen worden:\n{str(e)}",
            )
            return False
        except Exception as e:
            logger.error(f"Analytics dashboard error: {e}")
            self.main_window.show_status_message(
                f"Error opening analytics: {str(e)}", 5000
            )
            QMessageBox.critical(
                self.main_window,
                "Analytics Fout",
                f"Fout bij openen analytics dashboard:\n{str(e)}",
            )
            return False

    #
    # def is_analytics_available(self) -> bool:
    #     """Check if analytics dashboard is available."""
    #     try:
    #         import analytics_dashboard
    #
    #         return True
    #     except ImportError:
    #         return False

    def get_analytics_info(self) -> dict[str, Any]:
        """Get information about analytics capabilities."""
        wav_files = self.main_window.file_manager.get_all_wav_files()

        return {
            "available": self.is_analytics_available(),
            "wav_files_count": len(wav_files),
            "has_tagged_files": self._count_tagged_files(wav_files),
            "categories_detected": self._detect_categories(wav_files),
        }

    def _count_tagged_files(self, wav_files: list[str]) -> int:
        """Count files that have tags."""
        tagged_count = 0

        for file_path in wav_files:
            try:
                result = wav_analyze(file_path)
                if result and result.get("info", {}).get("ICMT"):
                    tagged_count += 1
            except Exception:
                continue

        return tagged_count

    def _detect_categories(self, wav_files: list[str]) -> list[str]:
        """Detect which categories are present in the files."""
        found_categories = set()

        for file_path in wav_files:
            try:

                result = wav_analyze(file_path)

                if result and result.get("info", {}).get("ICMT"):
                    tags_string = result["info"]["ICMT"].strip()
                    if tags_string:
                        file_tags = [
                            tag.strip().lower()
                            for tag in tags_string.split(",")
                            if tag.strip()
                        ]

                        # Check which categories these tags belong to
                        for tag in file_tags:
                            for category, category_tags in tag_categories.items():
                                if tag in [ct.lower() for ct in category_tags]:
                                    found_categories.add(category)
                                    break

            except Exception:
                continue

        return list(found_categories)


class ExportManagerInterface:
    """Main interface class that MainWindow and MenuHandlers will use.

    Provides a clean, unified interface for all export operations with history
    tracking and comprehensive statistics. This interface layer hides the
    complexity of individual exporters while providing additional features
    like export history and performance tracking.

    The interface serves as the main entry point for all export functionality,
    providing a consistent API for different export types while maintaining
    comprehensive logging and statistics collection.

    Features:
    - Unified interface for all export types
    - Export history tracking with performance metrics
    - Availability checking for different export types
    - Comprehensive statistics collection
    - Clean API for MainWindow and menu integration

    Attributes:
        main_window: Reference to main application window
        export_manager (ExportManager): Core export coordination instance
        export_history (list): History of export operations with metrics

    Args:
        main_window: Main application window instance for UI integration
    """

    def __init__(self, main_window):
        """Initialize export manager interface.

        Sets up the export manager interface with history tracking and
        statistics collection capabilities.

        Args:
            main_window: Main application window instance for export
                manager initialization and UI integration
        """
        self.main_window = main_window
        self.export_manager = ExportManager(main_window)

        self.export_history = []
        logger.info("ExportManagerInterface initialized with history tracking")

    # === CSV EXPORT ===

    def export_metadata_csv(self) -> bool:
        """Export metadata to CSV with history tracking.

        Performs CSV metadata export with comprehensive history tracking
        and performance metrics collection.

        Returns:
            bool: True if export completed successfully, False otherwise
        """
        start_time = datetime.now()
        success = self.export_manager.export_metadata_csv()

        # Track export
        self.export_history.append(
            {
                "type": "CSV",
                "timestamp": start_time.isoformat(),
                "success": success,
                "duration": (datetime.now() - start_time).total_seconds(),
            }
        )

        return success

    def get_export_history(self) -> list[dict[str, Any]]:
        """Get export history for debugging/analytics.

        Returns a copy of the export history with timing and success metrics
        for debugging, performance analysis, and user feedback.

        Returns:
            list[dict[str, Any]]: List of export history entries with
                type, timestamp, success status, and duration metrics
        """
        return self.export_history.copy()

    def export_tags_json(self, output_path: str | None = None) -> bool:
        """Export tags to JSON file."""
        return self.export_manager.export_tags_json(output_path)

    # === ABLETON EXPORT ===

    def export_to_ableton(self) -> bool:
        """Export to Ableton Live set."""
        return self.export_manager.export_to_ableton()

    def is_ableton_available(self) -> bool:
        """Check if Ableton export is available."""
        return self.export_manager.ableton_exporter.is_ableton_export_available()

    # === ANALYTICS ===

    def show_analytics_dashboard(self) -> bool:
        """Show analytics dashboard."""
        return self.export_manager.show_analytics_dashboard()

    def is_analytics_available(self) -> bool:
        """Check if analytics is available."""
        return self.export_manager.analytics_launcher.is_analytics_available()

    # === UTILITY METHODS ===

    def get_export_statistics(self) -> dict[str, Any]:
        """Get comprehensive export statistics.

        Collects and returns comprehensive statistics about the current
        collection and available export capabilities.

        Returns:
            dict[str, Any]: Complete export statistics including file counts,
                availability status, and configuration information
        """
        return self.export_manager.get_export_statistics()

    def get_export_manager(self) -> ExportManager:
        """Get reference to the main export manager.

        Provides access to the underlying export manager for advanced
        operations or direct access to specialized exporters.

        Returns:
            ExportManager: The main export coordination instance
        """
        return self.export_manager
