"""Metadata table presentation for the waveform viewer.

Owns population/formatting/reset logic for the FMT, BEXT, INFO, GPS, and
cue-point metadata tables. Operates purely on Qt table widgets passed in
via the constructor and plain data dicts/lists passed to each method — no
WAV parsing, no file I/O, no save logic, and no MainWindow access. Parser
output (the dicts produced by wav_analyze()) is displayed as-is; only
presentation (row/cell construction, formatting, tooltips, styling) lives
here.
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem


class MetadataPresenter:
    """Populates and resets the WAV metadata display tables.

    Args:
        fmt_table: Table for audio format (fmt chunk) information.
        bext_table: Table for BEXT (Broadcast Wave) metadata.
        info_table: Table for LIST-INFO chunk metadata (editable, with
            user-config defaults merged in).
        gps_table: Table for GPS/iXML location data (editable).
        cue_table: Table for labeled cue points.
    """

    def __init__(
        self,
        fmt_table: QTableWidget,
        bext_table: QTableWidget,
        info_table: QTableWidget,
        gps_table: QTableWidget,
        cue_table: QTableWidget,
    ):
        self.fmt_table = fmt_table
        self.bext_table = bext_table
        self.info_table = info_table
        self.gps_table = gps_table
        self.cue_table = cue_table

    def clear_all(self) -> None:
        """Clear all metadata tables (does not touch photo preview widgets)."""
        for table in (
            self.fmt_table,
            self.bext_table,
            self.info_table,
            self.gps_table,
            self.cue_table,
        ):
            table.setRowCount(0)

    def populate_fmt_table(self, fmt_data: dict[str, Any]) -> None:
        """Populate FMT chunk information table.

        Args:     fmt_data: FMT chunk data dictionary
        """
        self.populate_two_column_table(self.fmt_table, fmt_data)

    def populate_bext_table(self, bext_data: dict[str, Any]) -> None:
        """Populate BEXT chunk information table.

        Args:     bext_data: BEXT chunk data dictionary
        """
        self.populate_two_column_table(self.bext_table, bext_data)

    def populate_info_table(
        self, info_data: dict[str, Any], user_config_defaults: dict[str, Any]
    ) -> None:
        """Populate INFO chunk information table, merging user-config defaults.

        Args:
            info_data: INFO chunk data dictionary from the parsed WAV file.
            user_config_defaults: Default tag values (e.g. from
                user_config["wav_tags"]) shown when the WAV file has no
                value for a given key.
        """
        self.populate_two_column_table_with_defaults(
            self.info_table, info_data, user_config_defaults
        )

    def populate_gps_table_rows(self, gps_data: dict | None) -> None:
        """Populate the editable Latitude/Longitude/Altitude/Photo/Location rows.

        Always shows 3 editable rows (Latitude, Longitude, Altitude) so the
        user can fill them in even when no GPS data is present in the
        file, plus optional read-only Photo/Location rows when present.

        Photo preview widget updates are not handled here — that stays in
        WavViewer since it involves other widgets and the current filename.

        Args:     gps_data: Dict with 'latitude', 'longitude', 'altitude', or None.
        """
        self.populate_two_column_table_editable(self.gps_table, {
            "Latitude": str(gps_data["latitude"]) if gps_data else "",
            "Longitude": str(gps_data["longitude"]) if gps_data else "",
            "Altitude": str(gps_data.get("altitude", "")) if gps_data else "",
        })

        photo_ref = gps_data.get("photo_ref") if gps_data else None
        location_name = gps_data.get("location_name") if gps_data else None
        for label, value in [("Photo", photo_ref), ("Location", location_name)]:
            if value:
                row = self.gps_table.rowCount()
                self.gps_table.insertRow(row)
                key_item = QTableWidgetItem(label)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                self.gps_table.setItem(row, 0, key_item)
                val_item = QTableWidgetItem(value)
                val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
                self.gps_table.setItem(row, 1, val_item)

    def populate_two_column_table(
        self, table: QTableWidget, data: dict[str, Any]
    ) -> None:
        """Populate a two-column table with key-value data.

        Args:     table: Table widget to populate     data: Dictionary of key-value
        pairs
        """
        for i, (key, value) in enumerate((data or {}).items()):
            table.insertRow(i)

            key_item = QTableWidgetItem(str(key))
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(i, 0, key_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(i, 1, value_item)

            table.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def populate_two_column_table_editable(
        self, table: QTableWidget, data: dict[str, Any]
    ) -> None:
        """Populate a two-column table with editable value cells.

        Args:
            table: Table widget to populate.
            data: Dictionary of key-value pairs.
        """
        for i, (key, value) in enumerate((data or {}).items()):
            table.insertRow(i)

            key_item = QTableWidgetItem(str(key))
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 0, key_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(i, 1, value_item)

        table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )

    def populate_two_column_table_with_defaults(
        self,
        table: QTableWidget,
        data: dict[str, Any],
        defaults: dict[str, Any],
    ) -> None:
        """Populate a two-column table with key-value data, merging defaults.

        1. Merge defaults with actual data (actual data overwrites defaults)
        2. Populate table normally
        3. Style default (unset) values differently from actual WAV data
        4. Make the table editable if its objectName contains "info"

        Args:
            table: Table widget to populate.
            data: Dictionary of key-value pairs from the WAV file.
            defaults: Default values to show for keys missing from ``data``.
        """
        merged_data = defaults.copy()
        if data:
            merged_data.update(data)

        table.setRowCount(0)

        for i, (key, value) in enumerate(merged_data.items()):
            table.insertRow(i)

            key_item = QTableWidgetItem(str(key))
            key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 0, key_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            original_value = data.get(key, "") if data else ""
            default_value = defaults.get(key, "")

            if not original_value and default_value:
                value_item.setToolTip(
                    f"Default value: {default_value}\nDouble-click to edit"
                )
                value_item.setForeground(QColor(180, 180, 180))
                font = value_item.font()
                font.setItalic(True)
                value_item.setFont(font)
            else:
                value_item.setToolTip(
                    "Original value from WAV file\nDouble-click to edit"
                )

            table.setItem(i, 1, value_item)

        if hasattr(table, "objectName") and "info" in table.objectName().lower():
            table.setEditTriggers(
                QTableWidget.DoubleClicked | QTableWidget.SelectedClicked
            )

    def populate_cue_table(
        self,
        cue_points: list[dict[str, Any]],
        cue_labels: dict[str, str],
        sample_rate: int | None,
    ) -> None:
        """Populate cue points table with labeled cue points only.

        Args:
            cue_points: List of cue point dictionaries.
            cue_labels: Mapping of cue ID (as string) to label text.
            sample_rate: Audio sample rate in Hz, used to convert sample
                offsets to a time display. If None, the raw sample offset
                is shown instead.
        """
        self.cue_table.setRowCount(0)

        row = 0
        for cue in cue_points:
            cue_id = str(cue.get("ID", ""))
            label = (cue_labels.get(cue_id) or cue.get("Label", "") or "").strip()
            if not label:
                continue

            self.cue_table.insertRow(row)

            id_item = QTableWidgetItem(cue_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self.cue_table.setItem(row, 0, id_item)

            offset = cue.get("Sample Offset", 0)
            if sample_rate:
                time_pos = offset / sample_rate
                pos_text = f"{time_pos:.3f}s"
            else:
                pos_text = f"{offset} samples"

            pos_item = QTableWidgetItem(pos_text)
            pos_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cue_table.setItem(row, 1, pos_item)

            label_item = QTableWidgetItem(label)
            label_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.cue_table.setItem(row, 2, label_item)

            row += 1

        if row == 0:
            self.cue_table.setRowCount(1)
            msg_item = QTableWidgetItem("No labeled cue points found.")
            msg_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            msg_item.setFlags(Qt.ItemIsEnabled)
            self.cue_table.setItem(0, 0, msg_item)
            self.cue_table.setItem(0, 1, QTableWidgetItem(""))
            self.cue_table.setItem(0, 2, QTableWidgetItem(""))

        self.cue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
