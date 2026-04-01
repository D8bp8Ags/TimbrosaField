"""AI Analysis Dialog for field recordings.

Copyright (c) TimbrosaField — all rights reserved.

Provides a backend-agnostic dialog and background worker for AI analysis of
WAV files.  The actual model code lives in :mod:`ai_backends`; this module
only contains UI, orchestration, and sidecar-cache logic.

Results are cached in a sidecar JSON file (``<name>_ai.json``) next to the
WAV so analysis only runs once per file.

Classes:
    AiAnalysisWorker: Background QThread that drives registered backends.
    AiAnalysisDialog: Dialog showing detections and selectable tags.

Functions:
    show_ai_analysis: Open the analysis dialog for a WAV file.
"""

import json
import logging
import os

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active backends — add or remove entries here to control which AI models run.
# Each backend file carries its own licence notice.
# ---------------------------------------------------------------------------

def _load_backends() -> list:
    """Import and instantiate all enabled backends.

    Backends that fail to import (missing optional dependency) are silently
    skipped so the app still starts without every model installed.

    Returns:
        List of :class:`~ai_backends.base.AiBackend` instances.
    """
    backends = []
    try:
        from ai_backends.birdnet_backend import BirdnetBackend  # noqa: PLC0415
        backends.append(BirdnetBackend())
    except ImportError:
        logger.info("BirdNET backend not available (birdnetlib not installed)")
    try:
        from ai_backends.ast_backend import AstBackend  # noqa: PLC0415
        backends.append(AstBackend())
    except ImportError:
        logger.info("AST backend not available (transformers not installed)")
    return backends


# ---------------------------------------------------------------------------
# Sidecar JSON helpers
# ---------------------------------------------------------------------------

def _sidecar_path(wav_path: str) -> str:
    """Return the sidecar JSON path for a WAV file.

    Args:
        wav_path: Absolute path to the WAV file.

    Returns:
        Path string with ``_ai.json`` suffix.
    """
    base, _ = os.path.splitext(wav_path)
    return base + "_ai.json"


def _load_sidecar(wav_path: str) -> dict | None:
    """Load cached AI results from the sidecar JSON if it exists.

    Args:
        wav_path: Absolute path to the WAV file.

    Returns:
        Parsed dict or ``None`` if not found / unreadable.
    """
    path = _sidecar_path(wav_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        # Reject old-format sidecars (pre-refactor) that lack the layers key
        if "layers" not in data:
            return None
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load AI sidecar %s: %s", path, exc)
        return None


def _save_sidecar(wav_path: str, data: dict) -> None:
    """Persist AI results to a sidecar JSON file.

    Args:
        wav_path: Absolute path to the WAV file.
        data: Results dict to serialise.
    """
    path = _sidecar_path(wav_path)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug("AI sidecar saved: %s", path)
    except OSError as exc:
        logger.error("Could not save AI sidecar %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class AiAnalysisWorker(QThread):
    """Background thread that drives all registered AI backends.

    Emits :attr:`status` with a human-readable progress string and
    :attr:`finished` with the complete results dict when done.
    No Qt widgets are touched inside :meth:`run`.
    """

    status = pyqtSignal(str)
    finished = pyqtSignal(dict)  # {"wav_path": ..., "layers": [...]}

    def __init__(self, wav_path: str, metadata: dict) -> None:
        """Initialise with the WAV path and its pre-read metadata.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Dict as returned by ``wav_analyze()``.
        """
        super().__init__()
        self._wav_path = wav_path
        self._metadata = metadata

    def run(self) -> None:
        """Run each backend in sequence; emit finished with all layers."""
        backends = _load_backends()
        layers = []

        for backend in backends:
            self.status.emit(f"{backend.name}: analysing ({backend.device_label})…")
            try:
                detections = backend.analyze(self._wav_path, self._metadata)
                layers.append({
                    "name": backend.name,
                    "color": list(backend.color),
                    "text_color": backend.text_color,
                    "device": backend.device_label,
                    "detections": detections,
                })
                self.status.emit(
                    f"{backend.name}: {len(detections)} detections"
                    f" [{backend.device_label}]"
                )
            except Exception as exc:
                logger.error("%s analysis failed: %s", backend.name, exc)
                self.status.emit(f"{backend.name} failed")

        self.finished.emit({"wav_path": self._wav_path, "layers": layers})


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class AiAnalysisDialog(QDialog):
    """Dialog showing AI detection results for a single WAV file.

    Displays a two-tab interface: a chronological detection table and a
    tag-selection panel.  The user can tick tags and apply them to the WAV
    via the parent's save infrastructure.
    """

    tags_selected = pyqtSignal(list)  # emitted with [str, ...] when user applies

    def __init__(self, wav_path: str, metadata: dict, parent=None) -> None:
        """Initialise the dialog without starting analysis.

        Args:
            wav_path: Absolute path to the WAV file to analyse.
            metadata: Dict as returned by ``wav_analyze()``.
            parent: Parent widget (typically MainWindow).
        """
        super().__init__(parent)
        self._wav_path = wav_path
        self._metadata = metadata
        self._layers: list[dict] = []
        self._worker = None
        self._tag_checkboxes: list[tuple[QCheckBox, str]] = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        self.setWindowTitle(f"AI Analysis — {os.path.basename(self._wav_path)}")
        self.setMinimumSize(860, 580)
        root = QVBoxLayout(self)

        # Loading label — visible during analysis
        self._loading_label = QLabel("Preparing analysis…")
        self._loading_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setItalic(True)
        self._loading_label.setFont(font)
        root.addWidget(self._loading_label)

        # Tab widget — hidden until analysis is done
        self._tabs = QTabWidget()
        self._tabs.setVisible(False)
        root.addWidget(self._tabs)

        # Tab 1: chronological detections table
        self._detection_table = QTableWidget(0, 5)
        self._detection_table.setHorizontalHeaderLabels(
            ["Time", "Source", "Label", "Detail", "Conf"]
        )
        self._detection_table.horizontalHeader().setStretchLastSection(False)
        self._detection_table.horizontalHeader().setSectionResizeMode(
            2, self._detection_table.horizontalHeader().Stretch
        )
        self._detection_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._detection_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._detection_table.setAlternatingRowColors(False)
        self._tabs.addTab(self._detection_table, "Detections")

        # Tab 2: tag checkboxes
        self._tag_container = QWidget()
        self._tag_layout = QVBoxLayout(self._tag_container)
        self._tag_layout.setAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(self._tag_container)
        scroll.setWidgetResizable(True)
        self._tabs.addTab(scroll, "Tags")

        # Bottom button row
        btn_row = QHBoxLayout()
        self._reanalyze_btn = QPushButton("Re-analyse")
        self._reanalyze_btn.setEnabled(False)
        self._reanalyze_btn.setToolTip("Delete cache and run analysis again")
        self._reanalyze_btn.clicked.connect(self._on_reanalyze)
        btn_row.addWidget(self._reanalyze_btn)
        btn_row.addStretch()

        self._apply_btn = QPushButton("Apply Selected Tags")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply_tags)
        btn_row.addWidget(self._apply_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        # Device info label (populated after analysis)
        self._device_label = QLabel("")
        self._device_label.setStyleSheet("color: #888888; font-size: 10px;")
        self._device_label.setAlignment(Qt.AlignRight)
        root.addWidget(self._device_label)

    # ------------------------------------------------------------------
    # Analysis lifecycle
    # ------------------------------------------------------------------

    def start_analysis(self) -> None:
        """Start analysis — loads from sidecar cache if available."""
        cached = _load_sidecar(self._wav_path)
        if cached:
            self._loading_label.setText("Loaded from cache.")
            self._on_analysis_done(cached)
            return

        self._loading_label.setVisible(True)
        self._tabs.setVisible(False)
        self._apply_btn.setEnabled(False)
        self._reanalyze_btn.setEnabled(False)

        self._worker = AiAnalysisWorker(self._wav_path, self._metadata)
        self._worker.status.connect(self._loading_label.setText)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.start()

    def _on_analysis_done(self, results: dict) -> None:
        """Handle completed analysis on the main thread.

        Args:
            results: Dict with keys ``wav_path`` and ``layers``.
        """
        self._layers = results.get("layers") or []
        _save_sidecar(self._wav_path, results)

        self._loading_label.setVisible(False)
        self._tabs.setVisible(True)
        self._apply_btn.setEnabled(True)
        self._reanalyze_btn.setEnabled(True)

        self._populate_detections()
        self._populate_tags()

        device_parts = [
            f"{layer['name']}: {layer.get('device', 'CPU')}"
            for layer in self._layers
        ]
        self._device_label.setText("  |  ".join(device_parts))

        main_window = self.parent()
        if main_window:
            if hasattr(main_window, "ui_manager"):
                main_window.ui_manager.hide_progress()
            if hasattr(main_window, "wav_viewer"):
                main_window.wav_viewer.refresh_ai_overlay()

    def _on_reanalyze(self) -> None:
        """Delete the sidecar and re-run analysis."""
        path = _sidecar_path(self._wav_path)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            logger.warning("Could not delete sidecar %s: %s", path, exc)
        self.start_analysis()

    # ------------------------------------------------------------------
    # Populate tabs
    # ------------------------------------------------------------------

    def _populate_detections(self) -> None:
        """Fill the detections table from all layers, sorted by start time."""
        rows = []
        for layer in self._layers:
            for det in layer["detections"]:
                rows.append((
                    det["start_time"],
                    det["end_time"],
                    layer["name"],
                    det["label"],
                    det.get("detail", ""),
                    det["score"],
                    layer.get("color", [40, 40, 60, 255]),
                ))
        rows.sort(key=lambda r: r[0])

        self._detection_table.setRowCount(len(rows))
        for row_idx, (start_s, end_s, src, label, detail, conf, color) in enumerate(rows):
            start_fmt = f"{int(start_s) // 60}:{int(start_s) % 60:02d}"
            end_fmt = f"{int(end_s) // 60}:{int(end_s) % 60:02d}"
            bg = QColor(color[0] // 3, color[1] // 3, color[2] // 3)
            cells = [
                QTableWidgetItem(f"{start_fmt} – {end_fmt}"),
                QTableWidgetItem(src),
                QTableWidgetItem(label),
                QTableWidgetItem(detail),
                QTableWidgetItem(f"{conf:.2f}"),
            ]
            for col, cell in enumerate(cells):
                cell.setBackground(bg)
                cell.setForeground(QColor("#e8e8e8"))
                self._detection_table.setItem(row_idx, col, cell)

        self._detection_table.resizeColumnsToContents()

    def _populate_tags(self) -> None:
        """Fill the Tags tab with deduplicated, checkable tag labels."""
        while self._tag_layout.count():
            child = self._tag_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._tag_checkboxes.clear()

        # Deduplicate by (layer_name, tag_key); keep highest score
        seen: dict[tuple, float] = {}
        ordered: list[tuple] = []  # (layer_name, tag_key, tag, label_text, score)

        for layer in self._layers:
            for det in sorted(layer["detections"], key=lambda d: -d["score"]):
                if det["score"] < 0.20:
                    continue
                tag_key = det.get("tag_key") or det["label"]
                key = (layer["name"], tag_key)
                if key in seen:
                    continue
                seen[key] = det["score"]
                tag = det.get("tag") or det["label"]
                label_text = (
                    f"{tag}  [{det['label']}]  — {layer['name']} {det['score']:.2f}"
                    if tag != det["label"]
                    else f"{det['label']}  — {layer['name']} {det['score']:.2f}"
                )
                ordered.append((layer["name"], tag_key, tag, label_text, det["score"]))

        for _layer_name, _tag_key, tag, label_text, score in ordered:
            cb = QCheckBox(label_text)
            cb.setChecked(score >= 0.40)
            self._tag_layout.addWidget(cb)
            self._tag_checkboxes.append((cb, tag))

    # ------------------------------------------------------------------
    # Tag application
    # ------------------------------------------------------------------

    def _on_apply_tags(self) -> None:
        """Collect checked tags and emit :attr:`tags_selected`."""
        selected = [tag for cb, tag in self._tag_checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "No tags selected", "Select at least one tag to apply.")
            return
        self.tags_selected.emit(selected)
        logger.info("Tags selected for %s: %s", os.path.basename(self._wav_path), selected)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def show_ai_analysis(wav_path: str, metadata: dict, parent=None) -> None:
    """Open the AI analysis dialog for a single WAV file.

    Args:
        wav_path: Absolute path to the WAV file.
        metadata: Dict as returned by ``wav_analyze()``.
        parent: Parent widget (typically MainWindow).
    """
    dialog = AiAnalysisDialog(wav_path, metadata, parent=parent)
    dialog.start_analysis()
    dialog.exec_()
