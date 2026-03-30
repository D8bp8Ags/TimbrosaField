"""Photo GPS Matcher for Field Recording applications.

Matches WAV files to photos by timestamp (BWF origination date/time vs. EXIF
DateTimeOriginal) and injects the photo's GPS coordinates into the WAV iXML
chunk.

Classes:
    PhotoGpsMatcher: Main dialog for photo-to-WAV GPS matching
    PhotoScanWorker:  Background thread for scanning a photo folder
    GpsApplyWorker:   Background thread for injecting GPS into WAV files

Functions:
    read_photo_exif:     Extract datetime and GPS from a photo's EXIF data
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from wav_analyzer import inject_ixml_chunk, wav_analyze

logger = logging.getLogger(__name__)

# EXIF tag IDs (TIFF/JPEG standard)
_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_GPS_INFO = 34853

# GPSInfo sub-tag IDs
_GPS_LAT_REF = 1
_GPS_LAT = 2
_GPS_LON_REF = 3
_GPS_LON = 4
_GPS_ALT_REF = 5
_GPS_ALT = 6

# Table column indices
_COL_WAV = 0
_COL_WAV_TIME = 1
_COL_PHOTO = 2
_COL_PHOTO_TIME = 3
_COL_DIFF = 4
_COL_GPS = 5

# Photo file extensions to scan
_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".heic", ".png", ".tif", ".tiff")


# ---------------------------------------------------------------------------
# EXIF helpers
# ---------------------------------------------------------------------------

def _rational_to_float(value) -> float:
    """Convert an EXIF rational value (IFDRational or (num, den) tuple) to float."""
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return value.numerator / value.denominator if value.denominator else 0.0
    if isinstance(value, tuple) and len(value) == 2:
        return value[0] / value[1] if value[1] else 0.0
    return float(value)


def _dms_to_decimal(dms, ref: str) -> float:
    """Convert a DMS tuple from EXIF to decimal degrees.

    Args:
        dms: Three-element sequence of (degrees, minutes, seconds) rationals.
        ref: Hemisphere reference character ('N', 'S', 'E', 'W').

    Returns:
        Decimal degrees as float; negative for S/W hemispheres.
    """
    d, m, s = (_rational_to_float(v) for v in dms)
    decimal = d + m / 60 + s / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def read_photo_exif(photo_path: str) -> dict:
    """Extract datetime and GPS from a photo's EXIF data.

    Args:
        photo_path: Absolute path to the photo file.

    Returns:
        Dict with keys:
            ``datetime``: :class:`datetime` object or ``None`` if unavailable.
            ``gps``: Dict with ``latitude``, ``longitude``, ``altitude`` or ``None``.
    """
    result = {"datetime": None, "gps": None}
    try:
        from PIL import Image  # noqa: PLC0415  (lazy import — Pillow optional)

        img = Image.open(photo_path)
        exif = img._getexif()  # returns None when no EXIF present
        if not exif:
            return result

        # --- Datetime ---
        raw_dt = exif.get(_EXIF_DATETIME_ORIGINAL)
        if raw_dt:
            try:
                result["datetime"] = datetime.strptime(raw_dt, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                logger.debug("Unexpected EXIF datetime format in %s: %r", os.path.basename(photo_path), raw_dt)

        # --- GPS ---
        gps_info = exif.get(_EXIF_GPS_INFO)
        if gps_info:
            try:
                lat = _dms_to_decimal(gps_info[_GPS_LAT], gps_info[_GPS_LAT_REF])
                lon = _dms_to_decimal(gps_info[_GPS_LON], gps_info[_GPS_LON_REF])
                alt = _rational_to_float(gps_info.get(_GPS_ALT, 0))
                if gps_info.get(_GPS_ALT_REF) == b"\x01":
                    alt = -alt
                result["gps"] = {"latitude": lat, "longitude": lon, "altitude": alt}
            except (KeyError, TypeError, ZeroDivisionError) as exc:
                logger.debug("GPS parse error in %s: %s", os.path.basename(photo_path), exc)

    except Exception as exc:  # noqa: BLE001
        logger.debug("Cannot read EXIF from %s: %s", os.path.basename(photo_path), exc)

    return result


def _parse_wav_datetime(bext: dict) -> datetime | None:
    """Parse origination date/time from a bext metadata dict.

    Handles the BWF standard format ``YYYY-MM-DD`` / ``HH:MM:SS`` as well as
    the compact ``YYYYMMDD`` / ``HHMMSS`` variant used by some recorders.

    Args:
        bext: Dict returned by :func:`wav_analyzer.parse_bext_chunk`.

    Returns:
        :class:`datetime` or ``None`` if the fields are missing or unparseable.
    """
    date_str = bext.get("Origination Date", "").strip()
    time_str = bext.get("Origination Time", "").strip()
    if not date_str or not time_str:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H%M%S", "%Y-%m-%d %H%M%S", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{date_str} {time_str}", fmt)
        except ValueError:
            continue

    logger.debug("Cannot parse WAV datetime: date=%r time=%r", date_str, time_str)
    return None


def _format_diff(diff: timedelta) -> str:
    """Format a timedelta as a human-readable offset string (e.g. '+2m 15s')."""
    total = int(diff.total_seconds())
    if total < 60:
        return f"+{total}s"
    return f"+{total // 60}m {total % 60}s"


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class PhotoScanWorker(QThread):
    """Background thread: scan a photo folder and build match proposals.

    Emits ``progress`` after each photo is processed and ``finished`` with the
    list of match dicts when complete.  No Qt widgets are accessed in ``run()``.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, wav_entries: list, photo_dir: str, tolerance_minutes: float) -> None:
        """Initialize the worker.

        Args:
            wav_entries:       List of dicts with keys ``path`` and ``datetime``.
            photo_dir:         Directory to scan for photo files.
            tolerance_minutes: Maximum time difference (in minutes) for a match.
        """
        super().__init__()
        self._wav_entries = wav_entries
        self._photo_dir = photo_dir
        self._tolerance = timedelta(minutes=tolerance_minutes)

    def run(self) -> None:
        """Scan photos and match to WAV entries."""
        photo_files = [
            os.path.join(self._photo_dir, f)
            for f in sorted(os.listdir(self._photo_dir))
            if f.lower().endswith(_PHOTO_EXTENSIONS)
        ]

        photo_data = []
        for i, path in enumerate(photo_files):
            exif = read_photo_exif(path)
            if exif["datetime"]:
                photo_data.append({
                    "path": path,
                    "datetime": exif["datetime"],
                    "gps": exif["gps"],
                })
            self.progress.emit(i + 1)

        matches = []
        for wav in self._wav_entries:
            if not wav["datetime"]:
                matches.append({**wav, "photo_path": None, "photo_datetime": None, "diff": None, "gps": None})
                continue

            best = min(
                (p for p in photo_data if abs(wav["datetime"] - p["datetime"]) <= self._tolerance),
                key=lambda p: abs(wav["datetime"] - p["datetime"]),
                default=None,
            )
            matches.append({
                **wav,
                "photo_path": best["path"] if best else None,
                "photo_datetime": best["datetime"] if best else None,
                "diff": abs(wav["datetime"] - best["datetime"]) if best else None,
                "gps": best["gps"] if best else None,
            })

        self.finished.emit(matches)


class GpsApplyWorker(QThread):
    """Background thread: inject GPS coordinates into WAV files.

    Emits ``progress`` after each file and ``finished`` with success count and
    error list when the loop completes.  No Qt widgets are accessed in ``run()``.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(int, list)

    def __init__(self, tasks: list, use_backup: bool) -> None:
        """Initialize the worker.

        Args:
            tasks:      List of dicts with keys ``wav_path`` and ``gps_data``.
            use_backup: Whether to copy the original WAV to ``<name>.bak`` first.
        """
        super().__init__()
        self._tasks = tasks
        self._use_backup = use_backup

    def run(self) -> None:
        """Inject GPS into each WAV file."""
        success_count = 0
        errors = []
        for i, task in enumerate(self._tasks):
            wav_path = task["wav_path"]
            gps_data = task["gps_data"]
            try:
                if self._use_backup:
                    shutil.copy2(wav_path, wav_path + ".bak")

                fd, tmp = tempfile.mkstemp(suffix=".wav", dir=os.path.dirname(wav_path))
                os.close(fd)
                try:
                    inject_ixml_chunk(wav_path, tmp, gps_data)
                    os.replace(tmp, wav_path)
                except Exception:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    raise

                logger.debug("GPS injected: %s", os.path.basename(wav_path))
                success_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("GPS inject failed for %s: %s", os.path.basename(wav_path), exc)
                errors.append(f"{os.path.basename(wav_path)}: {exc}")
            self.progress.emit(i + 1)

        self.finished.emit(success_count, errors)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class PhotoGpsMatcher(QDialog):
    """Dialog to match WAV files to photos by timestamp and inject GPS.

    Loads origination date/time from each WAV's BWF bext chunk, scans a
    user-selected photo folder for EXIF timestamps, proposes the closest
    match within a configurable tolerance window, and writes the matched
    photo's GPS coordinates into the WAV iXML chunk.

    Attributes:
        wav_files (list[str]):       WAV file paths provided by the caller.

    Args:
        parent (QWidget, optional):  Parent widget. Defaults to ``None``.
        wav_files (list, optional):  WAV file paths to process.
    """

    def __init__(self, parent=None, wav_files=None) -> None:
        super().__init__(parent)
        self.wav_files = wav_files or []
        self._photo_dir: str | None = None
        self._wav_entries: list = []
        self._matches: list = []
        self._scan_worker: PhotoScanWorker | None = None
        self._apply_worker: GpsApplyWorker | None = None

        self.setWindowTitle("Photo GPS Matcher")
        self.setModal(True)
        self.setMinimumSize(860, 520)

        self._build_wav_entries()
        self._setup_ui()

    def closeEvent(self, event) -> None:
        """Stop background workers before closing."""
        for worker in (self._scan_worker, self._apply_worker):
            if worker and worker.isRunning():
                worker.quit()
                worker.wait()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_wav_entries(self) -> None:
        """Read origination datetime from each WAV file's bext chunk."""
        for path in self.wav_files:
            dt = None
            try:
                result = wav_analyze(path)
                if result:
                    dt = _parse_wav_datetime(result.get("bext", {}))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Cannot read bext from %s: %s", os.path.basename(path), exc)
            self._wav_entries.append({"path": path, "datetime": dt})

    def _setup_ui(self) -> None:
        """Build all UI components."""
        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(QLabel(f"<h3>📸 Photo GPS Matcher — {len(self.wav_files)} WAV files</h3>"))

        # Photo folder selector
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Photo folder:"))
        self._folder_label = QLabel("(not selected)")
        self._folder_label.setStyleSheet("color: grey;")
        folder_row.addWidget(self._folder_label, 1)
        browse_btn = QPushButton("📂 Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Tolerance + scan button
        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Time tolerance:"))
        self._tolerance_spin = QDoubleSpinBox()
        self._tolerance_spin.setRange(0.1, 60.0)
        self._tolerance_spin.setValue(5.0)
        self._tolerance_spin.setSuffix(" min")
        options_row.addWidget(self._tolerance_spin)
        options_row.addStretch()
        self._scan_btn = QPushButton("🔍 Scan")
        self._scan_btn.setEnabled(False)
        self._scan_btn.clicked.connect(self._start_scan)
        options_row.addWidget(self._scan_btn)
        layout.addLayout(options_row)

        # Progress bar (hidden until needed)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Match table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["WAV", "Opnametijd", "Foto", "Fototijd", "Verschil", "GPS"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table)

        # Backup + action buttons
        button_row = QHBoxLayout()
        self._backup_checkbox = QCheckBox("Backup maken (.bak)")
        self._backup_checkbox.setChecked(True)
        button_row.addWidget(self._backup_checkbox)
        button_row.addStretch()

        cancel_btn = QPushButton("Annuleren")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton("GPS Toepassen →")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_gps)
        button_row.addWidget(self._apply_btn)

        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecteer foto map")
        if folder:
            self._photo_dir = folder
            self._folder_label.setText(folder)
            self._folder_label.setStyleSheet("")
            self._scan_btn.setEnabled(True)

    def _start_scan(self) -> None:
        self._table.setRowCount(0)
        self._apply_btn.setEnabled(False)

        photo_count = sum(
            1 for f in os.listdir(self._photo_dir)
            if f.lower().endswith(_PHOTO_EXTENSIONS)
        )
        self._progress.setMaximum(max(photo_count, 1))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._scan_btn.setEnabled(False)

        self._scan_worker = PhotoScanWorker(
            self._wav_entries, self._photo_dir, self._tolerance_spin.value()
        )
        self._scan_worker.progress.connect(self._progress.setValue)
        self._scan_worker.finished.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, matches: list) -> None:
        self._matches = matches
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._populate_table(matches)
        self._apply_btn.setEnabled(any(m["gps"] for m in matches))

    def _populate_table(self, matches: list) -> None:
        self._table.setRowCount(len(matches))
        for row, m in enumerate(matches):
            wav_name = os.path.basename(m["path"])
            wav_time = m["datetime"].strftime("%H:%M:%S") if m["datetime"] else "—"
            photo_name = os.path.basename(m["photo_path"]) if m["photo_path"] else "geen match"
            photo_time = m["photo_datetime"].strftime("%H:%M:%S") if m["photo_datetime"] else "—"
            diff_str = _format_diff(m["diff"]) if m["diff"] is not None else "—"
            gps_str = "✓" if m["gps"] else "✗"

            for col, text in enumerate([wav_name, wav_time, photo_name, photo_time, diff_str, gps_str]):
                self._table.setItem(row, col, QTableWidgetItem(text))

    def _apply_gps(self) -> None:
        tasks = [
            {"wav_path": m["path"], "gps_data": m["gps"]}
            for m in self._matches
            if m["gps"]
        ]
        if not tasks:
            QMessageBox.information(self, "Geen matches", "Geen WAV-bestanden met GPS-match gevonden.")
            return

        self._progress.setMaximum(len(tasks))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._apply_btn.setEnabled(False)

        self._apply_worker = GpsApplyWorker(tasks, self._backup_checkbox.isChecked())
        self._apply_worker.progress.connect(self._progress.setValue)
        self._apply_worker.finished.connect(self._on_apply_done)
        self._apply_worker.start()

    def _on_apply_done(self, success_count: int, errors: list) -> None:
        self._progress.setVisible(False)
        if errors:
            msg = f"{success_count} bestanden bijgewerkt, {len(errors)} fouten:\n\n"
            msg += "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n… en {len(errors) - 5} meer"
            QMessageBox.warning(self, "Klaar met fouten", msg)
        else:
            QMessageBox.information(self, "Klaar", f"GPS toegevoegd aan {success_count} WAV-bestanden.")
        self.accept()