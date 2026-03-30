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
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from wav_analyzer import inject_ixml_chunk, remove_ixml_chunk, wav_analyze

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
_COL_IXML = 6

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
                alt = None
                if _GPS_ALT in gps_info:
                    alt = _rational_to_float(gps_info[_GPS_ALT])
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


def _propagate_gps(matches: list, max_gap_hours: float) -> list:
    """Fill GPS for unmatched WAV files from the nearest matched file.

    For each WAV without a GPS match, finds the temporally nearest WAV that
    does have GPS and copies its coordinates, provided the time gap is within
    ``max_gap_hours``.  The returned dicts are copies; the originals are not
    mutated.

    Args:
        matches:       List of match dicts as returned by :class:`PhotoScanWorker`.
        max_gap_hours: Maximum allowed time gap (hours) for propagation.

    Returns:
        New list of match dicts; propagated entries have ``"propagated": True``
        and ``"propagated_from"`` set to the source WAV basename.
    """
    max_gap = timedelta(hours=max_gap_hours)
    matched = [m for m in matches if m["gps"] and m["datetime"]]

    result = []
    for m in matches:
        if m["gps"] or not m["datetime"]:
            result.append({**m, "propagated": False, "propagated_from": None})
            continue

        # Prefer the most recent matched WAV *before* this one (photographer arrived
        # at a location and all subsequent files inherit that GPS).  Only fall back to
        # a future match when no earlier one exists within the max gap.
        before = [s for s in matched if s["datetime"] <= m["datetime"]
                  and (m["datetime"] - s["datetime"]) <= max_gap]
        if before:
            nearest = max(before, key=lambda s: s["datetime"])
        else:
            after = [s for s in matched if s["datetime"] > m["datetime"]
                     and (s["datetime"] - m["datetime"]) <= max_gap]
            nearest = min(after, key=lambda s: s["datetime"], default=None)
        if nearest:
            photo_dt = nearest.get("photo_datetime")
            diff = abs(m["datetime"] - photo_dt) if photo_dt else None
            result.append({
                **m,
                "gps": nearest["gps"],
                "photo_path": nearest.get("photo_path"),
                "photo_datetime": photo_dt,
                "diff": diff,
                "propagated": True,
                "propagated_from": os.path.basename(nearest["path"]),
            })
        else:
            result.append({**m, "propagated": False, "propagated_from": None})

    return result


def _reverse_geocode_sync(lat: float, lon: float) -> str:
    """Synchronous Nominatim reverse-geocode. Returns display_name or empty string."""
    try:
        params = urllib.parse.urlencode({
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 10,
            "addressdetails": 0,
        })
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "FieldRecordingApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json  # noqa: PLC0415
            data = json.loads(resp.read())
            return data.get("display_name", "")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Sync reverse geocode failed: %s", exc)
        return ""


def load_photo_pixmap(path: str, max_size: int) -> "QPixmap | None":
    """Load a photo as a scaled QPixmap, with Pillow fallback for HEIC.

    Args:
        path:     Absolute path to the photo file.
        max_size: Maximum width and height in pixels.

    Returns:
        Scaled :class:`QPixmap` or ``None`` on failure.
    """
    pixmap = QPixmap(path)
    if pixmap.isNull():
        try:
            from PIL import Image  # noqa: PLC0415
            import io  # noqa: PLC0415
            img = Image.open(path).convert("RGB")
            img.thumbnail((max_size, max_size))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Pillow fallback failed for %s: %s", os.path.basename(path), exc)
            return None
    if not pixmap.isNull():
        return pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class ReverseGeocodeWorker(QThread):
    """Background thread: reverse-geocode a lat/lon via Nominatim.

    Emits ``finished`` with a human-readable place string or an empty string
    on failure.  No Qt widgets are accessed in ``run()``.
    """

    finished = pyqtSignal(str)

    def __init__(self, lat: float, lon: float) -> None:
        super().__init__()
        self._lat = lat
        self._lon = lon

    def run(self) -> None:
        """Query Nominatim and emit the display_name on success."""
        try:
            params = urllib.parse.urlencode({
                "format": "json",
                "lat": self._lat,
                "lon": self._lon,
                "zoom": 10,
                "addressdetails": 0,
            })
            url = f"https://nominatim.openstreetmap.org/reverse?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "FieldRecordingApp/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                import json  # noqa: PLC0415
                data = json.loads(resp.read())
                self.finished.emit(data.get("display_name", ""))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Reverse geocode failed: %s", exc)
            self.finished.emit("")


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
        _geocode_cache: dict[tuple, str] = {}
        for i, task in enumerate(self._tasks):
            wav_path = task["wav_path"]
            gps_data = dict(task["gps_data"])
            # Fetch location name if not already present
            if "location_name" not in gps_data:
                lat, lon = gps_data["latitude"], gps_data["longitude"]
                cache_key = (round(lat, 4), round(lon, 4))
                if cache_key not in _geocode_cache:
                    _geocode_cache[cache_key] = _reverse_geocode_sync(lat, lon)
                if _geocode_cache[cache_key]:
                    gps_data["location_name"] = _geocode_cache[cache_key]
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


class IxmlRemoveWorker(QThread):
    """Background thread: remove iXML chunks from WAV files.

    Emits ``progress`` after each file and ``finished`` with success count and
    error list when the loop completes.  No Qt widgets are accessed in ``run()``.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(int, list)

    def __init__(self, wav_paths: list, use_backup: bool) -> None:
        super().__init__()
        self._wav_paths = wav_paths
        self._use_backup = use_backup

    def run(self) -> None:
        """Remove iXML chunk from each WAV file."""
        success_count = 0
        errors = []
        for i, wav_path in enumerate(self._wav_paths):
            try:
                if self._use_backup:
                    shutil.copy2(wav_path, wav_path + ".bak")
                fd, tmp = tempfile.mkstemp(suffix=".wav", dir=os.path.dirname(wav_path))
                os.close(fd)
                try:
                    remove_ixml_chunk(wav_path, tmp)
                    os.replace(tmp, wav_path)
                except Exception:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    raise
                logger.debug("iXML removed: %s", os.path.basename(wav_path))
                success_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("iXML remove failed for %s: %s", os.path.basename(wav_path), exc)
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

    def __init__(self, parent=None, wav_files=None, settings=None) -> None:
        super().__init__(parent)
        self.wav_files = wav_files or []
        self._settings = settings
        self._photo_dir: str | None = None
        self._wav_entries: list = []
        self._matches: list = []
        self._scan_worker: PhotoScanWorker | None = None
        self._apply_worker: GpsApplyWorker | None = None
        self._remove_worker: IxmlRemoveWorker | None = None
        self._geocode_worker: ReverseGeocodeWorker | None = None
        self._geocode_cache: dict[tuple, str] = {}

        self.setWindowTitle("Photo GPS Matcher")
        self.setModal(True)
        self.setMinimumSize(1200, 680)

        self._build_wav_entries()
        self._setup_ui()

        # Enable remove button immediately if any WAV already has iXML
        if any(e.get("has_ixml") for e in self._wav_entries):
            self._remove_btn.setEnabled(True)

        # Restore last used photo folder
        if self._settings:
            saved = self._settings.get_photo_folder()
            if saved and os.path.isdir(saved):
                self._photo_dir = saved
                self._folder_label.setText(saved)
                self._folder_label.setStyleSheet("")
                self._scan_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        """Stop background workers before closing."""
        for worker in (self._scan_worker, self._apply_worker, self._remove_worker, self._geocode_worker):
            if worker and worker.isRunning():
                worker.quit()
                worker.wait()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_wav_entries(self) -> None:
        """Read origination datetime and existing iXML status from each WAV file."""
        for path in self.wav_files:
            dt = None
            has_ixml = False
            try:
                result = wav_analyze(path)
                if result:
                    dt = _parse_wav_datetime(result.get("bext", {}))
                    has_ixml = result.get("gps") is not None
            except Exception as exc:  # noqa: BLE001
                logger.debug("Cannot read bext from %s: %s", os.path.basename(path), exc)
            self._wav_entries.append({"path": path, "datetime": dt, "has_ixml": has_ixml})

    def _setup_ui(self) -> None:
        """Build all UI components."""
        outer = QVBoxLayout(self)

        # Header
        outer.addWidget(QLabel(f"<h3>📸 Photo GPS Matcher — {len(self.wav_files)} WAV files</h3>"))

        # Photo folder selector
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Photo folder:"))
        self._folder_label = QLabel("(not selected)")
        self._folder_label.setStyleSheet("color: grey;")
        folder_row.addWidget(self._folder_label, 1)
        browse_btn = QPushButton("📂 Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        outer.addLayout(folder_row)

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
        outer.addLayout(options_row)

        # GPS propagation option
        propagate_row = QHBoxLayout()
        self._propagate_checkbox = QCheckBox("Propagate GPS to unmatched files")
        self._propagate_checkbox.setChecked(True)
        propagate_row.addWidget(self._propagate_checkbox)
        propagate_row.addWidget(QLabel("max gap:"))
        self._max_gap_spin = QDoubleSpinBox()
        self._max_gap_spin.setRange(0.5, 24.0)
        self._max_gap_spin.setValue(4.0)
        self._max_gap_spin.setSuffix(" hrs")
        self._max_gap_spin.setMaximumWidth(100)
        propagate_row.addWidget(self._max_gap_spin)
        propagate_row.addStretch()
        outer.addLayout(propagate_row)

        # Progress bar (hidden until needed)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        outer.addWidget(self._progress)

        # Splitter: table (left) | preview (right)
        splitter = QSplitter(Qt.Horizontal)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["WAV", "Rec. Time", "Photo", "Photo Time", "Diff", "GPS", "iXML"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(_COL_WAV, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_WAV_TIME, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_PHOTO, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_PHOTO_TIME, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_DIFF, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_GPS, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_IXML, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        # Preview panel
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(8, 0, 0, 0)

        self._preview_image = QLabel()
        self._preview_image.setAlignment(Qt.AlignCenter)
        self._preview_image.setMinimumSize(280, 200)
        self._preview_image.setMaximumHeight(320)
        self._preview_image.setFrameShape(QFrame.StyledPanel)
        self._preview_image.setText("Select a row\nfor a preview")
        self._preview_image.setStyleSheet("color: grey;")
        preview_layout.addWidget(self._preview_image)

        self._preview_info = QLabel()
        self._preview_info.setWordWrap(True)
        self._preview_info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._preview_info.setTextFormat(Qt.RichText)
        preview_layout.addWidget(self._preview_info)
        preview_layout.addStretch()

        splitter.addWidget(preview_widget)
        splitter.setSizes([650, 350])
        outer.addWidget(splitter, 1)

        # Backup + action buttons
        button_row = QHBoxLayout()
        self._backup_checkbox = QCheckBox("Create backup (.bak)")
        self._backup_checkbox.setChecked(True)
        button_row.addWidget(self._backup_checkbox)
        button_row.addStretch()

        self._remove_btn = QPushButton("🗑 Remove iXML")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._remove_ixml)
        button_row.addWidget(self._remove_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton("Apply GPS →")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_gps)
        button_row.addWidget(self._apply_btn)

        outer.addLayout(button_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select photo folder")
        if folder:
            self._photo_dir = folder
            self._folder_label.setText(folder)
            self._folder_label.setStyleSheet("")
            self._scan_btn.setEnabled(True)
            if self._settings:
                self._settings.save_photo_folder(folder)

    def _on_row_selected(self) -> None:
        """Show photo preview and info for the selected row."""
        rows = self._table.selectionModel().selectedRows()
        if not rows or not self._matches:
            return
        row = rows[0].row()
        if row >= len(self._matches):
            return
        m = self._matches[row]

        # --- Photo thumbnail ---
        photo_path = m.get("photo_path")
        if photo_path and os.path.exists(photo_path):
            pixmap = self._load_pixmap(photo_path, 300)
            if pixmap:
                self._preview_image.setPixmap(pixmap)
            else:
                self._preview_image.setText("(cannot load photo)")
        else:
            self._preview_image.clear()
            self._preview_image.setText("No photo found")

        # --- Info text ---
        wav_name = os.path.basename(m["path"])
        wav_time = m["datetime"].strftime("%Y-%m-%d %H:%M:%S") if m["datetime"] else "—"
        photo_name = os.path.basename(photo_path) if photo_path else "—"
        photo_time = m["photo_datetime"].strftime("%Y-%m-%d %H:%M:%S") if m.get("photo_datetime") else "—"
        diff_str = _format_diff(m["diff"]) if m.get("diff") is not None else "—"
        propagated = m.get("propagated", False)

        gps = m.get("gps")
        if gps:
            coords_str = f"{gps['latitude']:.6f}, {gps['longitude']:.6f}"
            alt = gps.get("altitude")
            alt_str = f"{alt:.1f} m" if alt is not None else "not available"
        else:
            coords_str = "—"
            alt_str = "—"

        source_label = "↑ propagated from" if propagated else "Photo"
        source_value = m.get("propagated_from", photo_name) if propagated else photo_name

        info = (
            f"<b>WAV:</b> {wav_name}<br>"
            f"<b>Rec. time:</b> {wav_time}<br>"
            f"<b>{source_label}:</b> {source_value}<br>"
            f"<b>Photo time:</b> {photo_time}<br>"
            f"<b>Time diff:</b> {diff_str}<br>"
            f"<b>GPS:</b> {coords_str}<br>"
            f"<b>Altitude:</b> {alt_str}<br>"
        )
        self._preview_info.setText(info)

        # --- Reverse geocoding (async, cached) ---
        if gps:
            cache_key = (round(gps["latitude"], 4), round(gps["longitude"], 4))
            if cache_key in self._geocode_cache:
                self._preview_info.setText(info + f"<b>Location:</b> {self._geocode_cache[cache_key] or '—'}")
            else:
                self._preview_info.setText(info + "<b>Location:</b> fetching…")
                if self._geocode_worker and self._geocode_worker.isRunning():
                    self._geocode_worker.quit()
                self._geocode_worker = ReverseGeocodeWorker(gps["latitude"], gps["longitude"])
                self._geocode_worker.finished.connect(
                    lambda place, i=info, k=cache_key: (
                        self._geocode_cache.update({k: place}),
                        self._preview_info.setText(i + f"<b>Location:</b> {place or '—'}"),
                    )
                )
                self._geocode_worker.start()

    def _load_pixmap(self, path: str, max_size: int) -> QPixmap | None:
        return load_photo_pixmap(path, max_size)

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
        if self._propagate_checkbox.isChecked():
            matches = _propagate_gps(matches, self._max_gap_spin.value())
        else:
            matches = [{**m, "propagated": False, "propagated_from": None} for m in matches]
        self._matches = matches
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._populate_table(matches)
        self._apply_btn.setEnabled(any(m["gps"] for m in matches))
        self._remove_btn.setEnabled(any(m.get("has_ixml") for m in matches))

    def _populate_table(self, matches: list) -> None:
        self._table.setRowCount(len(matches))
        for row, m in enumerate(matches):
            wav_name = os.path.basename(m["path"])
            wav_time = m["datetime"].strftime("%H:%M:%S") if m["datetime"] else "—"

            if m.get("propagated"):
                photo_name = f"← {m['propagated_from']}"
                photo_time = "—"
                diff_str = _format_diff(m["diff"]) if m["diff"] is not None else "—"
                gps_str = "↑"
            else:
                photo_name = os.path.basename(m["photo_path"]) if m["photo_path"] else "no match"
                photo_time = m["photo_datetime"].strftime("%H:%M:%S") if m["photo_datetime"] else "—"
                diff_str = _format_diff(m["diff"]) if m["diff"] is not None else "—"
                gps_str = "✓" if m["gps"] else "✗"

            ixml_str = "✓" if m.get("has_ixml") else "—"
            for col, text in enumerate([wav_name, wav_time, photo_name, photo_time, diff_str, gps_str, ixml_str]):
                self._table.setItem(row, col, QTableWidgetItem(text))

    def _apply_gps(self) -> None:
        tasks = []
        for m in self._matches:
            if not m["gps"]:
                continue
            gps_data = dict(m["gps"])
            photo_path = m.get("photo_path")
            if photo_path and os.path.exists(photo_path):
                gps_data["photo_ref"] = os.path.relpath(
                    photo_path, os.path.dirname(m["path"])
                )
            # Pass cached location name to avoid redundant geocode requests
            cache_key = (round(gps_data["latitude"], 4), round(gps_data["longitude"], 4))
            if cache_key in self._geocode_cache and self._geocode_cache[cache_key]:
                gps_data["location_name"] = self._geocode_cache[cache_key]
            tasks.append({"wav_path": m["path"], "gps_data": gps_data})
        if not tasks:
            QMessageBox.information(self, "No matches", "No WAV files with a GPS match found.")
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
            msg = f"{success_count} files updated, {len(errors)} error(s):\n\n"
            msg += "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n… and {len(errors) - 5} more"
            QMessageBox.warning(self, "Done with errors", msg)
        else:
            QMessageBox.information(self, "Done", f"GPS added to {success_count} WAV files.")
        self.accept()

    def _remove_ixml(self) -> None:
        targets = [m["path"] for m in self._matches if m.get("has_ixml")]
        if not targets:
            return
        answer = QMessageBox.question(
            self,
            "Remove iXML",
            f"Remove iXML chunk from {len(targets)} file(s)?\n\nThis cannot be undone unless a backup is made.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._progress.setMaximum(len(targets))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._remove_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)

        self._remove_worker = IxmlRemoveWorker(targets, self._backup_checkbox.isChecked())
        self._remove_worker.progress.connect(self._progress.setValue)
        self._remove_worker.finished.connect(self._on_remove_done)
        self._remove_worker.start()

    def _on_remove_done(self, success_count: int, errors: list) -> None:
        self._progress.setVisible(False)
        if errors:
            msg = f"{success_count} files cleaned, {len(errors)} error(s):\n\n"
            msg += "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n… and {len(errors) - 5} more"
            QMessageBox.warning(self, "Done with errors", msg)
        else:
            QMessageBox.information(self, "Done", f"iXML removed from {success_count} WAV files.")
        self.accept()