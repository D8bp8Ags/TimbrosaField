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

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_model_manager import (
    ModelStatus,
    get_model_definition,
    get_model_status,
)
from ai_settings import load_ai_settings, save_ai_settings
from ai.registry import all_backends, load_backends, required_model_ids_for_backends

logger = logging.getLogger(__name__)


_DETECTION_HEADERS = [
    "On",
    "Time",
    "Source",
    "Scientific",
    "English",
    "Dutch",
    "Detail",
    "Level",
    "Score",
]


class DetectionTableModel(QAbstractTableModel):
    """Table model for AI detections."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_DETECTION_HEADERS)

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _DETECTION_HEADERS[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.UserRole:
            return row
        if role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if row.get("enabled", True) else Qt.Unchecked
        if role == Qt.DisplayRole:
            if col == 1:
                start_s = row["start_time"]
                end_s = row["end_time"]
                return f"{int(start_s) // 60}:{int(start_s) % 60:02d}–{int(end_s) // 60}:{int(end_s) % 60:02d}"
            if col == 2:
                return row["source"]
            if col == 3:
                return row["scientific_name"]
            if col == 4:
                return row["english_name"]
            if col == 5:
                return row["dutch_name"]
            if col == 6:
                return row["detail"]
            if col == 7:
                return row["level"]
            if col == 8:
                score = row["score"]
                return f"{score:.2f} {'█' * int(score * 10)}"
            return ""
        if role == Qt.BackgroundRole:
            c = row.get("color", [40, 40, 60, 255])
            base = (c[0] // 3, c[1] // 3, c[2] // 3)
            return QColor(*base)
        if role == Qt.ForegroundRole:
            return QColor("#e8e8e8")
        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        row = self._rows[index.row()]
        if index.column() == 0 and role == Qt.CheckStateRole:
            enabled = value == Qt.Checked
            if row.get("enabled", True) == enabled:
                return False
            row["enabled"] = enabled
            row["detection"]["enabled"] = enabled
            self.dataChanged.emit(index, index, [Qt.CheckStateRole, Qt.DisplayRole, Qt.UserRole])
            return True
        return False

    def row_data(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def set_enabled_rows(self, rows: list[int], enabled: bool) -> None:
        if not rows:
            return
        changed = []
        for row_idx in rows:
            row = self.row_data(row_idx)
            if row is None:
                continue
            row["enabled"] = enabled
            row["detection"]["enabled"] = enabled
            changed.append(row_idx)
        for row_idx in changed:
            idx = self.index(row_idx, 0)
            self.dataChanged.emit(idx, idx, [Qt.CheckStateRole, Qt.DisplayRole, Qt.UserRole])


class DetectionFilterProxyModel(QSortFilterProxyModel):
    """Proxy model for source/score/enabled filters and custom sorting."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_filter = ""
        self._min_score = 0.0
        self._enabled_only = False
        self._sort_mode = "time"
        self.setDynamicSortFilter(True)

    def set_source_filter(self, source: str) -> None:
        self._source_filter = source
        self.invalidateFilter()

    def set_min_score(self, score: float) -> None:
        self._min_score = score
        self.invalidateFilter()

    def set_enabled_only(self, enabled_only: bool) -> None:
        self._enabled_only = enabled_only
        self.invalidateFilter()

    def set_sort_mode(self, sort_mode: str) -> None:
        self._sort_mode = sort_mode

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        row = model.row_data(source_row) if model is not None else None
        if not row:
            return False
        if self._source_filter and row.get("source", "") != self._source_filter:
            return False
        if row.get("score", 0.0) < self._min_score:
            return False
        if self._enabled_only and not row.get("enabled", True):
            return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        left_row = model.row_data(left.row()) if model is not None else None
        right_row = model.row_data(right.row()) if model is not None else None
        if not left_row or not right_row:
            return super().lessThan(left, right)

        if self._sort_mode == "score":
            return (-left_row["score"], left_row["start_time"]) < (
                -right_row["score"], right_row["start_time"]
            )
        if self._sort_mode == "scientific":
            left_key = (
                left_row["scientific_name"]
                or left_row["english_name"]
                or left_row["dutch_name"]
                or left_row["source"]
            ).lower()
            right_key = (
                right_row["scientific_name"]
                or right_row["english_name"]
                or right_row["dutch_name"]
                or right_row["source"]
            ).lower()
            return (left_key, left_row["start_time"]) < (right_key, right_row["start_time"])
        if self._sort_mode == "source":
            return (
                left_row["source"].lower(),
                left_row["start_time"],
                -left_row["score"],
            ) < (
                right_row["source"].lower(),
                right_row["start_time"],
                -right_row["score"],
            )
        return (left_row["start_time"], -left_row["score"]) < (
            right_row["start_time"], -right_row["score"]
        )


# ---------------------------------------------------------------------------
# Active backends come from ai.registry.BACKEND_REGISTRY — add or remove
# entries there to control which AI models run.
# Each backend file carries its own licence notice.
# ---------------------------------------------------------------------------

def _load_backends(selected_names: set[str] | None = None) -> list:
    """Import and instantiate selected enabled backends.

    Thin wrapper delegating to ai.registry.load_backends(), the single
    source of truth for backend registration.

    Args:
        selected_names: Optional backend display names to instantiate. When
            omitted, all registered backends are imported.

    Returns:
        List of :class:`~ai_backends.base.AiBackend` instances.
    """
    return load_backends(selected_names)


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


def _load_sidecar(
    wav_path: str,
    required_backends: set[str] | None = None,
    required_backend_options: dict | None = None,
) -> dict | None:
    """Load cached AI results from the sidecar JSON if it exists.

    Args:
        wav_path: Absolute path to the WAV file.
        required_backends: Optional set of backend names expected by the
            current run. If the cache does not contain all of them, it is
            treated as stale.
        required_backend_options: Optional backend settings expected by the
            current run. If the cache was produced with different backend
            options, it is treated as stale.

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
        if required_backends is not None:
            cached_names = set(data.get("selected_backends") or [])
            if not cached_names:
                cached_names = {
                    layer.get("name")
                    for layer in data.get("layers", [])
                    if isinstance(layer, dict)
                }
            if not required_backends.issubset(cached_names):
                return None
        if required_backend_options is not None:
            cached_options = data.get("backend_options") or {}
            if cached_options != required_backend_options:
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
            json.dump(_make_json_safe(data), f, indent=2, ensure_ascii=False)
        logger.debug("AI sidecar saved: %s", path)
    except OSError as exc:
        logger.error("Could not save AI sidecar %s: %s", path, exc)


def _make_json_safe(value):
    """Recursively convert numpy/jax scalars and arrays to JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): _make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]

    if hasattr(value, "tolist"):
        try:
            return _make_json_safe(value.tolist())
        except TypeError:
            pass

    if hasattr(value, "item"):
        try:
            return _make_json_safe(value.item())
        except (TypeError, ValueError):
            pass

    return str(value)


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
    finished = pyqtSignal(dict)  # {"wav_path": ..., "layers": [...], "errors": [...]}

    def __init__(
        self,
        wav_path: str,
        metadata: dict,
        backends: list,
        backend_options: dict,
    ) -> None:
        """Initialise with the WAV path, metadata and concrete backends.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Dict as returned by ``wav_analyze()``.
            backends: Instantiated backends to run in sequence.
        """
        super().__init__()
        self._wav_path = wav_path
        self._metadata = metadata
        self._backends = backends
        self._backend_options = backend_options

    def run(self) -> None:
        """Run each backend in sequence; emit finished with all layers."""
        layers = []
        errors = []

        for backend in self._backends:
            self.status.emit(f"{backend.name}: analysing ({backend.device_label})…")
            try:
                detections = backend.analyze(self._wav_path, self._metadata)
                layers.append({
                    "name": backend.name,
                    "color": list(backend.color),
                    "text_color": backend.text_color,
                    "device": backend.device_label,
                    "detections": detections,
                    "raw_output": backend.debug_output,
                })
                self.status.emit(
                    f"{backend.name}: {len(detections)} detections"
                    f" [{backend.device_label}]"
                )
            except Exception as exc:
                logger.error("%s analysis failed: %s", backend.name, exc)
                errors.append({"name": backend.name, "message": str(exc)})
                self.status.emit(f"{backend.name} failed")

        self.finished.emit({
            "wav_path": self._wav_path,
            "selected_backends": [backend.name for backend in self._backends],
            "backend_options": self._backend_options,
            "layers": layers,
            "errors": errors,
        })


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
        self._existing_results = _load_sidecar(self._wav_path)
        self._layers: list[dict] = []
        self._worker = None
        self._tag_checkboxes: list[tuple[QCheckBox, str]] = []
        self._backend_checkboxes: list[tuple[QCheckBox, str]] = []
        self._updating_detection_table = False
        self._all_detection_rows: list[dict] = []
        self._current_sort_mode = "time"
        self._ai_settings = load_ai_settings()
        self._current_backend_options: dict = {}
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_detection_filters)
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.timeout.connect(self._flush_ai_overlay)
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._flush_persist_current_results)
        self._pending_refresh_raw_output = False
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        self.setWindowTitle(f"AI Analysis — {os.path.basename(self._wav_path)}")
        self.setMinimumSize(1320, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.setStyleSheet(
            """
            QDialog {
                background: #181c20;
            }
            QTableView {
                background: #14181c;
                alternate-background-color: #171b20;
                gridline-color: #2b3138;
                border: 1px solid #2e353d;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid #2e353d;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #1f2328;
                color: #aeb7c2;
                padding: 8px 12px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #2b3138;
                color: #f2f4f6;
            }
            QPushButton {
                padding: 6px 12px;
            }
            """
        )

        header_card = QFrame()
        header_card.setStyleSheet(
            """
            QFrame {
                background: #1f2328;
                border: 1px solid #30363d;
                border-radius: 10px;
            }
            """
        )
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_label = QLabel("AI Analysis")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #f3f5f7;")
        title_row.addWidget(title_label)

        file_label = QLabel(os.path.basename(self._wav_path))
        file_label.setStyleSheet("color: #9aa4ad;")
        title_row.addWidget(file_label)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        module_row = QHBoxLayout()
        module_row.addWidget(QLabel("AI modules:"))
        cached_backend_names = set((self._existing_results or {}).get("selected_backends") or [])
        if not cached_backend_names:
            cached_backend_names = {
                layer.get("name")
                for layer in (self._existing_results or {}).get("layers", [])
                if isinstance(layer, dict)
            }
        for registration in all_backends():
            backend_name = registration.display_name
            cb = QCheckBox(backend_name)
            cb.setChecked(backend_name in cached_backend_names if cached_backend_names else True)
            cb.toggled.connect(self._refresh_model_status)
            module_row.addWidget(cb)
            self._backend_checkboxes.append((cb, backend_name))
        module_row.addStretch()
        self._start_btn = QPushButton("Start Analysis")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2f81f7; color: white; border: none; border-radius: 7px; font-weight: 600; }"
            "QPushButton:disabled { background: #42536b; color: #d0d7de; }"
        )
        self._start_btn.clicked.connect(self.start_analysis)
        module_row.addWidget(self._start_btn)
        self._reanalyze_btn = QPushButton("Re-analyse")
        self._reanalyze_btn.setEnabled(False)
        self._reanalyze_btn.setToolTip("Delete cache and run analysis again")
        self._reanalyze_btn.clicked.connect(self._on_reanalyze)
        module_row.addWidget(self._reanalyze_btn)
        self._manage_models_btn = QPushButton("Modellen beheren")
        self._manage_models_btn.clicked.connect(self._open_model_manager)
        module_row.addWidget(self._manage_models_btn)
        header_layout.addLayout(module_row)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Graph label:"))
        self._graph_label_mode = QComboBox()
        self._graph_label_mode.addItem("Scientific", "scientific")
        self._graph_label_mode.addItem("English", "english")
        self._graph_label_mode.addItem("Dutch", "dutch")
        index = self._graph_label_mode.findData(
            self._ai_settings.get("graph_label_mode", "scientific")
        )
        if index >= 0:
            self._graph_label_mode.setCurrentIndex(index)
        self._graph_label_mode.currentIndexChanged.connect(
            self._on_graph_label_mode_changed
        )
        settings_row.addWidget(self._graph_label_mode)
        self._settings_summary = QLabel("")
        self._settings_summary.setStyleSheet("color: #888888;")
        settings_row.addWidget(self._settings_summary, 1)
        self._toggle_settings_btn = QPushButton("Show Settings")
        self._toggle_settings_btn.clicked.connect(self._toggle_advanced_settings)
        settings_row.addWidget(self._toggle_settings_btn)
        settings_row.addStretch()
        header_layout.addLayout(settings_row)

        self._model_status_label = QLabel("")
        self._model_status_label.setStyleSheet("color: #aab4be;")
        self._model_status_label.setWordWrap(True)
        header_layout.addWidget(self._model_status_label)

        self._advanced_settings_widget = QWidget()
        advanced_layout = QVBoxLayout(self._advanced_settings_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)

        self._advanced_hint = QLabel(
            "Hover a setting for help. BirdNET values follow official package defaults; "
            "AST and Perch values are app defaults chosen for this workflow."
        )
        self._advanced_hint.setWordWrap(True)
        self._advanced_hint.setStyleSheet("color: #9aa4ad;")
        advanced_layout.addWidget(self._advanced_hint)

        backend_settings_row = QHBoxLayout()
        backend_settings_row.setContentsMargins(0, 0, 0, 0)
        backend_settings_row.setSpacing(12)
        backend_settings_row.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        backend_settings_row.addWidget(
            self._build_birdnet_settings_box(),
            0,
            Qt.AlignLeft | Qt.AlignTop,
        )
        backend_settings_row.addWidget(
            self._build_ast_settings_box(),
            0,
            Qt.AlignLeft | Qt.AlignTop,
        )
        backend_settings_row.addWidget(
            self._build_perch_settings_box(),
            0,
            Qt.AlignLeft | Qt.AlignTop,
        )
        backend_settings_row.addStretch()
        advanced_layout.addLayout(backend_settings_row)
        self._advanced_settings_widget.setVisible(False)
        header_layout.addWidget(self._advanced_settings_widget)
        self._update_settings_summary()
        self._refresh_model_status()

        root.addWidget(header_card)

        self._status_frame = QFrame()
        self._status_frame.setStyleSheet(
            "QFrame { background: #15191d; border: 1px solid #2a3138; border-radius: 8px; }"
        )
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(10)
        self._status_badge = QLabel("Idle")
        self._status_badge.setStyleSheet(
            "QLabel { background: #2d333b; color: #f0f6fc; padding: 2px 8px; border-radius: 10px; font-weight: 600; }"
        )
        status_layout.addWidget(self._status_badge)

        self._loading_label = QLabel("Preparing analysis…")
        font = QFont()
        font.setItalic(True)
        self._loading_label.setFont(font)
        self._loading_label.setStyleSheet("color: #c4ccd4;")
        status_layout.addWidget(self._loading_label, 1)
        root.addWidget(self._status_frame)

        # Tab widget — hidden until analysis is done
        self._tabs = QTabWidget()
        self._tabs.setVisible(False)
        root.addWidget(self._tabs)

        # Tab 1: chronological detections table
        detections_tab = QWidget()
        detections_layout = QVBoxLayout(detections_tab)
        detections_layout.setContentsMargins(8, 8, 8, 8)
        detections_layout.setSpacing(8)

        detection_toolbar = QHBoxLayout()
        detection_toolbar.setSpacing(8)

        self._enable_all_btn = QPushButton("Enable All")
        self._enable_all_btn.setEnabled(False)
        self._enable_all_btn.clicked.connect(self._on_enable_all)
        detection_toolbar.addWidget(self._enable_all_btn)

        self._disable_all_btn = QPushButton("Disable All")
        self._disable_all_btn.setEnabled(False)
        self._disable_all_btn.clicked.connect(self._on_disable_all)
        detection_toolbar.addWidget(self._disable_all_btn)

        self._enable_selected_btn = QPushButton("Enable Selected")
        self._enable_selected_btn.setEnabled(False)
        self._enable_selected_btn.clicked.connect(self._on_enable_selected)
        detection_toolbar.addWidget(self._enable_selected_btn)

        self._disable_selected_btn = QPushButton("Disable Selected")
        self._disable_selected_btn.setEnabled(False)
        self._disable_selected_btn.clicked.connect(self._on_disable_selected)
        detection_toolbar.addWidget(self._disable_selected_btn)
        detection_toolbar.addStretch()
        detections_layout.addLayout(detection_toolbar)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        filter_group = QHBoxLayout()
        filter_group.setSpacing(8)
        filter_group.addWidget(QLabel("Filter:"))
        self._source_filter = QComboBox()
        self._source_filter.addItem("All", "")
        self._source_filter.currentIndexChanged.connect(self._apply_detection_filters)
        filter_group.addWidget(QLabel("Source"))
        filter_group.addWidget(self._source_filter)

        filter_group.addWidget(QLabel("Min score"))
        self._score_filter = QDoubleSpinBox()
        self._score_filter.setRange(0.0, 1.0)
        self._score_filter.setDecimals(2)
        self._score_filter.setSingleStep(0.05)
        self._score_filter.setValue(0.0)
        self._score_filter.valueChanged.connect(self._schedule_detection_filter_update)
        filter_group.addWidget(self._score_filter)

        self._enabled_only_filter = QCheckBox("Enabled only")
        self._enabled_only_filter.toggled.connect(self._apply_detection_filters)
        filter_group.addWidget(self._enabled_only_filter)
        filter_row.addLayout(filter_group)

        sort_group = QHBoxLayout()
        sort_group.setSpacing(8)
        sort_group.addWidget(QLabel("Sort:"))
        self._sort_mode = QComboBox()
        self._sort_mode.addItem("Time", "time")
        self._sort_mode.addItem("Score", "score")
        self._sort_mode.addItem("Scientific", "scientific")
        self._sort_mode.addItem("Source", "source")
        self._sort_mode.currentIndexChanged.connect(self._apply_detection_filters)
        sort_group.addWidget(self._sort_mode)
        filter_row.addLayout(sort_group)
        filter_row.addStretch()
        detections_layout.addLayout(filter_row)

        detections_body = QHBoxLayout()
        detections_body.setSpacing(10)

        self._detection_model = DetectionTableModel(self)
        self._detection_proxy = DetectionFilterProxyModel(self)
        self._detection_proxy.setSourceModel(self._detection_model)

        self._detection_table = QTableView()
        self._detection_table.setModel(self._detection_proxy)
        header = self._detection_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self._detection_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._detection_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._detection_table.setAlternatingRowColors(False)
        self._detection_table.setWordWrap(False)
        self._detection_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._detection_table.verticalHeader().setDefaultSectionSize(24)
        self._detection_table.setColumnWidth(0, 44)
        self._detection_table.setColumnWidth(1, 88)
        self._detection_table.setColumnWidth(2, 110)
        self._detection_table.setColumnWidth(3, 300)
        self._detection_table.setColumnWidth(4, 240)
        self._detection_table.setColumnWidth(5, 220)
        self._detection_table.setColumnWidth(6, 160)
        self._detection_table.setColumnWidth(7, 80)
        self._detection_table.setColumnWidth(8, 120)
        self._detection_table.selectionModel().selectionChanged.connect(
            self._update_detection_detail
        )
        self._detection_model.dataChanged.connect(self._on_detection_model_changed)
        detections_body.addWidget(self._detection_table, 5)

        self._detection_detail = QPlainTextEdit()
        self._detection_detail.setReadOnly(True)
        self._detection_detail.setPlaceholderText("Select a detection to inspect its details.")
        self._detection_detail.setMinimumWidth(200)
        self._detection_detail.setMaximumWidth(260)
        self._detection_detail.setStyleSheet(
            "QPlainTextEdit { background: #111418; border: 1px solid #2e353d; border-radius: 8px; color: #dbe2ea; }"
        )
        detail_column = QVBoxLayout()
        detail_column.setSpacing(8)
        detail_actions = QHBoxLayout()
        detail_actions.setSpacing(6)
        self._disable_detail_btn = QPushButton("Disable")
        self._disable_detail_btn.setEnabled(False)
        self._disable_detail_btn.clicked.connect(self._disable_current_detection)
        detail_actions.addWidget(self._disable_detail_btn)
        self._enable_detail_btn = QPushButton("Enable")
        self._enable_detail_btn.setEnabled(False)
        self._enable_detail_btn.clicked.connect(self._enable_current_detection)
        detail_actions.addWidget(self._enable_detail_btn)
        self._copy_label_btn = QPushButton("Copy Label")
        self._copy_label_btn.setEnabled(False)
        self._copy_label_btn.clicked.connect(self._copy_current_detection_label)
        detail_actions.addWidget(self._copy_label_btn)
        detail_actions.addStretch()
        detail_column.addLayout(detail_actions)
        detail_column.addWidget(self._detection_detail, 1)
        detections_body.addLayout(detail_column, 1)
        detections_layout.addLayout(detections_body)
        self._tabs.addTab(detections_tab, "Detections")

        # Tab 2: tag checkboxes
        self._tag_container = QWidget()
        self._tag_layout = QVBoxLayout(self._tag_container)
        self._tag_layout.setAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(self._tag_container)
        scroll.setWidgetResizable(True)
        self._tabs.addTab(scroll, "Tags")

        self._raw_output_view = QPlainTextEdit()
        self._raw_output_view.setReadOnly(True)
        self._tabs.addTab(self._raw_output_view, "Raw JSON")

        # Bottom button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._apply_btn = QPushButton("Apply Selected Tags")
        self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "QPushButton { background: #238636; color: white; border: none; border-radius: 7px; font-weight: 600; }"
            "QPushButton:disabled { background: #355a3a; color: #d0d7de; }"
        )
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

    def _make_settings_card(self, title: str) -> tuple[QFrame, QFormLayout]:
        """Create a compact settings card with consistent styling."""
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        card.setMinimumWidth(260)
        card.setStyleSheet(
            """
            QFrame {
                background: #1f2328;
                border: 1px solid #343a40;
                border-radius: 8px;
            }
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #e8e8e8;")
        layout.addWidget(title_label)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        layout.addLayout(form)
        return card, form

    @staticmethod
    def _compact_field(widget: QWidget, width: int = 110) -> QWidget:
        """Apply a compact left-aligned size to form input widgets."""
        widget.setFixedWidth(width)
        widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return widget

    @staticmethod
    def _add_form_row(
        form: QFormLayout,
        label_text: str,
        field: QWidget,
        tooltip: str,
    ) -> None:
        """Add a form row with the same tooltip on label and field."""
        label = QLabel(label_text)
        label.setToolTip(tooltip)
        field.setToolTip(tooltip)
        form.addRow(label, field)

    def _build_birdnet_settings_box(self) -> QFrame:
        """Create controls for BirdNET runtime parameters."""
        box, form = self._make_settings_card("BirdNET")
        birdnet = self._ai_settings["birdnet"]

        self._birdnet_min_conf = QDoubleSpinBox()
        self._birdnet_min_conf.setRange(0.01, 0.99)
        self._birdnet_min_conf.setDecimals(2)
        self._birdnet_min_conf.setSingleStep(0.01)
        self._birdnet_min_conf.setValue(float(birdnet["min_confidence"]))
        self._add_form_row(
            form,
            "Min confidence",
            self._compact_field(self._birdnet_min_conf),
            "Minimum confidence threshold for BirdNET detections. "
            "Higher filters out more weak hits. Official BirdNET default: 0.10.",
        )

        self._birdnet_top_k = QSpinBox()
        self._birdnet_top_k.setRange(1, 20)
        self._birdnet_top_k.setValue(int(birdnet["top_k"]))
        self._add_form_row(
            form,
            "Top results",
            self._compact_field(self._birdnet_top_k),
            "Maximum number of labels BirdNET returns per analysis window. "
            "Official birdnet package default: 5.",
        )

        self._birdnet_overlap = QDoubleSpinBox()
        self._birdnet_overlap.setRange(0.0, 2.9)
        self._birdnet_overlap.setDecimals(1)
        self._birdnet_overlap.setSingleStep(0.1)
        self._birdnet_overlap.setValue(float(birdnet["overlap_duration_s"]))
        self._add_form_row(
            form,
            "Overlap (s)",
            self._compact_field(self._birdnet_overlap),
            "Overlap between BirdNET prediction segments in seconds. "
            "Higher overlap can catch short calls more reliably but produces more detections. "
            "Official default: 0.0 s.",
        )

        self._birdnet_sensitivity = QDoubleSpinBox()
        self._birdnet_sensitivity.setRange(0.5, 1.5)
        self._birdnet_sensitivity.setDecimals(2)
        self._birdnet_sensitivity.setSingleStep(0.05)
        self._birdnet_sensitivity.setValue(float(birdnet["sigmoid_sensitivity"]))
        self._add_form_row(
            form,
            "Sensitivity",
            self._compact_field(self._birdnet_sensitivity),
            "BirdNET sensitivity shift. Higher values increase confidence scores. "
            "Official default: 1.0.",
        )

        self._birdnet_fmin = QSpinBox()
        self._birdnet_fmin.setRange(0, 24000)
        self._birdnet_fmin.setValue(int(birdnet["bandpass_fmin"]))
        self._add_form_row(
            form,
            "Bandpass min",
            self._compact_field(self._birdnet_fmin),
            "Low cutoff for BirdNET bandpass filter in Hz. "
            "Use this to ignore low-frequency rumble. Official default: 0 Hz.",
        )

        self._birdnet_fmax = QSpinBox()
        self._birdnet_fmax.setRange(1000, 24000)
        self._birdnet_fmax.setValue(int(birdnet["bandpass_fmax"]))
        self._add_form_row(
            form,
            "Bandpass max",
            self._compact_field(self._birdnet_fmax),
            "High cutoff for BirdNET bandpass filter in Hz. "
            "Use this to ignore ultrasound/high noise. Official default: 15000 Hz.",
        )

        self._birdnet_geo_filter = QCheckBox("Use geo filter")
        self._birdnet_geo_filter.setChecked(bool(birdnet["use_geo_filter"]))
        self._birdnet_geo_filter.setToolTip(
            "Restrict BirdNET candidates using recording location and week when GPS/date are available. "
            "Recommended on for normal use."
        )
        form.addRow(self._birdnet_geo_filter)
        return box

    def _build_ast_settings_box(self) -> QFrame:
        """Create controls for AST runtime parameters."""
        box, form = self._make_settings_card("AST")
        ast = self._ai_settings["ast"]

        self._ast_min_score = QDoubleSpinBox()
        self._ast_min_score.setRange(0.01, 0.99)
        self._ast_min_score.setDecimals(2)
        self._ast_min_score.setSingleStep(0.01)
        self._ast_min_score.setValue(float(ast["min_score"]))
        self._add_form_row(
            form,
            "Min score",
            self._compact_field(self._ast_min_score),
            "Minimum AST confidence score to keep a label. "
            "This is an app default, not an official model default. Current recommended default: 0.05.",
        )

        self._ast_top_n = QSpinBox()
        self._ast_top_n.setRange(1, 20)
        self._ast_top_n.setValue(int(ast["top_n"]))
        self._add_form_row(
            form,
            "Top results",
            self._compact_field(self._ast_top_n),
            "Maximum number of AST labels shown per analysis window. "
            "This is an app default. Current recommended default: 5.",
        )

        self._ast_step_seconds = QSpinBox()
        self._ast_step_seconds.setRange(1, 10)
        self._ast_step_seconds.setValue(int(ast["step_seconds"]))
        self._add_form_row(
            form,
            "Step (s)",
            self._compact_field(self._ast_step_seconds),
            "How far the AST window advances each time. Lower values give denser detections but more overlap. "
            "This is an app default. Current recommended default: 5 s.",
        )
        return box

    def _build_perch_settings_box(self) -> QFrame:
        """Create controls for Perch runtime parameters."""
        box, form = self._make_settings_card("Perch")
        perch = self._ai_settings["perch"]

        self._perch_min_score = QDoubleSpinBox()
        self._perch_min_score.setRange(0.01, 0.99)
        self._perch_min_score.setDecimals(2)
        self._perch_min_score.setSingleStep(0.01)
        self._perch_min_score.setValue(float(perch["min_score"]))
        self._add_form_row(
            form,
            "Min score",
            self._compact_field(self._perch_min_score),
            "Minimum Perch confidence score to keep a label. "
            "This threshold is defined by this app, not by official Perch docs. Current recommended default: 0.10.",
        )

        self._perch_top_k = QSpinBox()
        self._perch_top_k.setRange(1, 20)
        self._perch_top_k.setValue(int(perch["top_k"]))
        self._add_form_row(
            form,
            "Top results",
            self._compact_field(self._perch_top_k),
            "Maximum number of Perch labels kept per window before score filtering. "
            "This is an app default. Current recommended default: 5.",
        )

        self._perch_overlap_ratio = QSpinBox()
        self._perch_overlap_ratio.setRange(0, 90)
        self._perch_overlap_ratio.setSuffix(" %")
        self._perch_overlap_ratio.setValue(
            int(round(float(perch.get("overlap_ratio", 0.5)) * 100))
        )
        self._add_form_row(
            form,
            "Overlap",
            self._compact_field(self._perch_overlap_ratio),
            "Overlap between consecutive Perch windows. "
            "Higher overlap improves coverage at window boundaries but increases duplicate detections. "
            "This is an app default. Current recommended default: 50%.",
        )
        return box

    def _toggle_advanced_settings(self) -> None:
        """Show or hide the advanced AI settings panel."""
        is_visible = self._advanced_settings_widget.isVisible()
        self._advanced_settings_widget.setVisible(not is_visible)
        self._toggle_settings_btn.setText(
            "Hide Settings" if not is_visible else "Show Settings"
        )

    def _update_settings_summary(self) -> None:
        """Show a compact one-line summary of active AI settings."""
        self._settings_summary.setText(
            "BirdNET:"
            f" conf≥{self._birdnet_min_conf.value():.2f},"
            f" top {self._birdnet_top_k.value()}  |  "
            "AST:"
            f" score≥{self._ast_min_score.value():.2f},"
            f" top {self._ast_top_n.value()}  |  "
            "Perch:"
            f" score≥{self._perch_min_score.value():.2f},"
            f" top {self._perch_top_k.value()},"
            f" ovl {self._perch_overlap_ratio.value()}%"
        )

    # ------------------------------------------------------------------
    # Analysis lifecycle
    # ------------------------------------------------------------------

    def _selected_backend_names(self) -> set[str]:
        """Return currently enabled backend names from the module checkboxes."""
        return {
            backend_name
            for checkbox, backend_name in self._backend_checkboxes
            if checkbox.isChecked()
        }

    def _selected_backends(self) -> list:
        """Return currently enabled backend instances from the module checkboxes."""
        backends = _load_backends(self._selected_backend_names())
        runtime_settings = self._collect_ai_settings()
        for backend in backends:
            backend.options = runtime_settings.get(backend.name.lower(), {})
        return backends

    def _collect_ai_settings(self) -> dict:
        """Collect UI settings for graph labels and per-backend runtime options."""
        return {
            "graph_label_mode": self._graph_label_mode.currentData(),
            "birdnet": {
                "top_k": self._birdnet_top_k.value(),
                "min_confidence": self._birdnet_min_conf.value(),
                "overlap_duration_s": self._birdnet_overlap.value(),
                "sigmoid_sensitivity": self._birdnet_sensitivity.value(),
                "bandpass_fmin": self._birdnet_fmin.value(),
                "bandpass_fmax": self._birdnet_fmax.value(),
                "use_geo_filter": self._birdnet_geo_filter.isChecked(),
            },
            "ast": {
                "top_n": self._ast_top_n.value(),
                "min_score": self._ast_min_score.value(),
                "step_seconds": self._ast_step_seconds.value(),
            },
            "perch": {
                "top_k": self._perch_top_k.value(),
                "min_score": self._perch_min_score.value(),
                "overlap_ratio": self._perch_overlap_ratio.value() / 100.0,
            },
        }

    def _save_runtime_settings(self) -> None:
        """Persist current AI UI/runtime settings."""
        self._ai_settings = self._collect_ai_settings()
        self._current_backend_options = {
            "birdnet": dict(self._ai_settings["birdnet"]),
            "ast": dict(self._ai_settings["ast"]),
            "perch": dict(self._ai_settings["perch"]),
        }
        save_ai_settings(self._ai_settings)
        self._update_settings_summary()
        self._refresh_model_status()

    def _selected_backend_options(self) -> dict:
        """Return persisted options limited to the currently selected backends."""
        selected = {name.lower() for name in self._selected_backend_names()}
        return {
            name: options
            for name, options in self._current_backend_options.items()
            if name in selected
        }

    def _required_model_ids(self) -> list[str]:
        """Return model IDs required by the selected AI modules."""
        model_ids = required_model_ids_for_backends(
            self._selected_backend_names(),
            self._collect_ai_settings(),
        )
        if "birdnet_geo" in model_ids and not self._birdnet_geo_context_available():
            model_ids = [model_id for model_id in model_ids if model_id != "birdnet_geo"]
        return model_ids

    def _birdnet_geo_context_available(self) -> bool:
        """Return whether BirdNET can use geo filtering for this recording."""
        gps = self._metadata.get("gps") or {}
        if gps.get("latitude") is None or gps.get("longitude") is None:
            return False
        bext = self._metadata.get("bext") or {}
        date_str = (
            bext.get("Origination Date")
            or bext.get("OriginationDate")
            or ""
        )
        return bool(date_str and len(date_str) >= 10)

    def _refresh_model_status(self) -> None:
        """Show compact model status for selected AI modules."""
        if not hasattr(self, "_model_status_label"):
            return
        parts = []
        for model_id in self._required_model_ids():
            definition = get_model_definition(model_id)
            status = get_model_status(model_id)
            parts.append(
                f"{definition.display_name}: {status.value.replace('_', ' ')}"
            )
        self._model_status_label.setText(
            "  |  ".join(parts) if parts else "Geen AI-modellen geselecteerd."
        )

    def _open_model_manager(self) -> None:
        """Open the model manager and refresh status when it closes."""
        from ai_model_dialog import AiModelDialog  # noqa: PLC0415

        dialog = AiModelDialog(self)
        dialog.exec_()
        self._refresh_model_status()

    def _preflight_models(self) -> bool:
        """Block analysis if any required model is absent or invalid."""
        problems = []
        for model_id in self._required_model_ids():
            status = get_model_status(model_id)
            if status != ModelStatus.INSTALLED:
                definition = get_model_definition(model_id)
                problems.append(
                    f"{definition.display_name}: {status.value.replace('_', ' ')}"
                )
        if not problems:
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("AI-modellen ontbreken")
        box.setText(
            "Installeer of importeer de vereiste modellen voordat analyse start."
        )
        box.setDetailedText("\n".join(problems))
        manage_btn = box.addButton("Modellen beheren", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.exec_()
        if box.clickedButton() == manage_btn:
            self._open_model_manager()
        return False

    def _on_graph_label_mode_changed(self) -> None:
        """Persist graph label preference and refresh overlay immediately."""
        self._save_runtime_settings()
        main_window = self.parent()
        if main_window and hasattr(main_window, "wav_viewer"):
            main_window.wav_viewer.refresh_ai_overlay(
                self._layers if self._layers else None
            )

    def prepare_analysis(self) -> None:
        """Initialise the dialog state before it is shown."""
        self._save_runtime_settings()
        required_backends = self._selected_backend_names()
        cached = _load_sidecar(
            self._wav_path,
            required_backends or None,
            self._selected_backend_options(),
        )
        if cached:
            self._start_btn.setVisible(False)
            self._status_badge.setText("Cached")
            self._loading_label.setText("Loaded from cache.")
            self._on_analysis_done(cached)
            return

        self._tabs.setVisible(False)
        self._tabs.setEnabled(False)
        self._status_badge.setText("Ready")
        self._apply_btn.setEnabled(False)
        self._reanalyze_btn.setEnabled(False)
        self._enable_all_btn.setEnabled(False)
        self._disable_all_btn.setEnabled(False)
        self._enable_selected_btn.setEnabled(False)
        self._disable_selected_btn.setEnabled(False)
        self._loading_label.setVisible(True)
        self._loading_label.setText("Select AI modules and click Start Analysis.")
        self._start_btn.setVisible(True)

    def start_analysis(self) -> None:
        """Start analysis — loads from sidecar cache if available."""
        self._save_runtime_settings()
        backends = self._selected_backends()
        if not backends:
            QMessageBox.information(
                self,
                "No AI modules selected",
                "Select at least one AI module before starting analysis.",
            )
            return
        required_backends = {backend.name for backend in backends}
        cached = _load_sidecar(
            self._wav_path,
            required_backends,
            self._selected_backend_options(),
        )
        if cached:
            self._start_btn.setVisible(False)
            self._status_badge.setText("Cached")
            self._loading_label.setText("Loaded from cache.")
            self._on_analysis_done(cached)
            return

        if not self._preflight_models():
            return

        self._loading_label.setVisible(True)
        self._status_badge.setText("Running")
        self._loading_label.setText("Starting analysis…")
        self._tabs.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._start_btn.setEnabled(False)
        self._reanalyze_btn.setEnabled(False)
        for checkbox, _backend in self._backend_checkboxes:
            checkbox.setEnabled(False)

        self._worker = AiAnalysisWorker(
            self._wav_path,
            self._metadata,
            backends,
            self._selected_backend_options(),
        )
        self._worker.status.connect(self._loading_label.setText)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.start()

    def _on_analysis_done(self, results: dict) -> None:
        """Handle completed analysis on the main thread.

        Args:
            results: Dict with keys ``wav_path`` and ``layers``.
        """
        self._layers = results.get("layers") or []
        errors = results.get("errors") or []
        _save_sidecar(self._wav_path, results)

        self._loading_label.setVisible(False)
        self._status_badge.setText("Done" if not errors else "Partial")
        self._tabs.setVisible(True)
        self._tabs.setEnabled(True)
        self._apply_btn.setEnabled(True)
        self._start_btn.setVisible(False)
        self._start_btn.setEnabled(True)
        self._reanalyze_btn.setEnabled(True)
        self._enable_all_btn.setEnabled(True)
        self._disable_all_btn.setEnabled(True)
        self._enable_selected_btn.setEnabled(True)
        self._disable_selected_btn.setEnabled(True)
        for checkbox, _backend in self._backend_checkboxes:
            checkbox.setEnabled(True)

        self._populate_detections()
        self._populate_tags()
        self._populate_raw_output()

        device_parts = [
            f"{layer['name']}: {layer.get('device', 'CPU')}"
            for layer in self._layers
        ]
        if errors:
            device_parts.extend(f"{error['name']}: failed" for error in errors)
        self._device_label.setText("  |  ".join(device_parts))

        if errors:
            self._status_badge.setText("Issues")
            QMessageBox.warning(
                self,
                "AI backend errors",
                "\n".join(
                    f"{error['name']}: {error['message']}"
                    for error in errors
                ),
            )

        main_window = self.parent()
        if main_window:
            if hasattr(main_window, "ui_manager"):
                main_window.ui_manager.hide_progress()
            if hasattr(main_window, "wav_viewer"):
                QTimer.singleShot(0, main_window.wav_viewer.refresh_ai_overlay)

    def _on_reanalyze(self) -> None:
        """Delete the sidecar and re-run analysis."""
        path = _sidecar_path(self._wav_path)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            logger.warning("Could not delete sidecar %s: %s", path, exc)
        self.start_analysis()

    def _flush_persist_current_results(self) -> None:
        """Persist current in-memory layers and refresh dependent UI."""
        _save_sidecar(
            self._wav_path,
            {
                "wav_path": self._wav_path,
                "selected_backends": [layer.get("name") for layer in self._layers],
                "backend_options": self._selected_backend_options(),
                "layers": self._layers,
            },
        )
        self._populate_tags()
        if self._pending_refresh_raw_output:
            self._populate_raw_output()
            self._pending_refresh_raw_output = False

    def _flush_ai_overlay(self) -> None:
        """Push current in-memory layers into the waveform overlay."""
        main_window = self.parent()
        if main_window and hasattr(main_window, "wav_viewer"):
            main_window.wav_viewer.refresh_ai_overlay(self._layers)

    def _refresh_ai_overlay(self) -> None:
        """Schedule a lightweight overlay refresh with current in-memory layers."""
        self._overlay_timer.start(40)

    def _persist_current_results(self, refresh_raw_output: bool = False) -> None:
        """Schedule persistence so the table UI stays responsive."""
        self._pending_refresh_raw_output = (
            self._pending_refresh_raw_output or refresh_raw_output
        )
        self._persist_timer.start(120)

    # ------------------------------------------------------------------
    # Populate tabs
    # ------------------------------------------------------------------

    def _populate_detections(self) -> None:
        """Fill the detections model from all layers."""
        rows = []
        for layer in self._layers:
            for det in layer["detections"]:
                rows.append({
                    "enabled": det.get("enabled", True),
                    "start_time": det["start_time"],
                    "end_time": det["end_time"],
                    "source": layer["name"],
                    "scientific_name": det.get("scientific_name", ""),
                    "english_name": det.get(
                        "english_name",
                        det["label"] if not det.get("scientific_name") else "",
                    ),
                    "dutch_name": det.get("dutch_name", ""),
                    "detail": det.get("detail", ""),
                    "level": det.get("level", ""),
                    "score": det["score"],
                    "color": layer.get("color", [40, 40, 60, 255]),
                    "detection": det,
                })
        self._all_detection_rows = rows
        self._detection_model.set_rows(rows)
        self._refresh_source_filter()
        self._apply_detection_filters()
        self._autosize_detection_columns()

    def _autosize_detection_columns(self) -> None:
        """Resize detection columns to fit current content without doing it on every filter."""
        header = self._detection_table.horizontalHeader()
        autosize_cols = (0, 1, 2, 3, 4, 5, 6, 7, 8)
        previous_modes = {
            col: header.sectionResizeMode(col)
            for col in autosize_cols
        }
        for col in autosize_cols:
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._detection_table.resizeColumnsToContents()
        for col in autosize_cols:
            width = self._detection_table.columnWidth(col)
            self._detection_table.setColumnWidth(col, width + 16)

        # Keep name columns flexible after autosize so the table can use extra width.
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        for col in (0, 1, 2, 7, 8):
            header.setSectionResizeMode(col, previous_modes[col])

    def _refresh_source_filter(self) -> None:
        """Refresh source filter choices from current layers."""
        current = self._source_filter.currentData()
        sources = sorted({layer["name"] for layer in self._layers})
        self._source_filter.blockSignals(True)
        self._source_filter.clear()
        self._source_filter.addItem("All", "")
        for source in sources:
            self._source_filter.addItem(source, source)
        index = self._source_filter.findData(current)
        self._source_filter.setCurrentIndex(index if index >= 0 else 0)
        self._source_filter.blockSignals(False)

    def _schedule_detection_filter_update(self, *_args) -> None:
        """Debounce filter updates while the score spinbox changes."""
        self._filter_timer.start(120)

    def _apply_detection_filters(self, *_args) -> None:
        """Apply source/score/enabled filters and sort order to the proxy."""
        sort_mode = self._sort_mode.currentData() or "time"
        self._current_sort_mode = sort_mode
        self._detection_proxy.set_source_filter(self._source_filter.currentData() or "")
        self._detection_proxy.set_min_score(float(self._score_filter.value()))
        self._detection_proxy.set_enabled_only(self._enabled_only_filter.isChecked())
        self._detection_proxy.set_sort_mode(sort_mode)
        self._detection_proxy.invalidate()
        column_map = {
            "time": 1,
            "score": 8,
            "scientific": 3,
            "source": 2,
        }
        self._detection_proxy.sort(
            column_map.get(sort_mode, 1),
            Qt.AscendingOrder,
        )
        self._tabs.setTabText(0, f"Detections ({self._detection_proxy.rowCount()})")
        self._update_detection_detail()

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
                if not det.get("enabled", True):
                    continue
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
        self._tabs.setTabText(1, f"Tags ({len(self._tag_checkboxes)})")

    def _populate_raw_output(self) -> None:
        """Show backend raw outputs in a read-only JSON view."""
        payload = {
            "wav_path": self._wav_path,
            "selected_backends": [layer.get("name") for layer in self._layers],
            "backend_options": self._selected_backend_options(),
            "layers": [
                {
                    "name": layer.get("name"),
                    "device": layer.get("device"),
                    "raw_output": layer.get("raw_output"),
                }
                for layer in self._layers
            ],
        }
        self._raw_output_view.setPlainText(
            json.dumps(_make_json_safe(payload), indent=2, ensure_ascii=False)
        )
        self._tabs.setTabText(2, "Debug")

    def _set_detection_enabled(self, source_row: int, enabled: bool) -> None:
        """Update one detection enable-state in the source model."""
        index = self._detection_model.index(source_row, 0)
        if index.isValid():
            self._detection_model.setData(
                index,
                Qt.Checked if enabled else Qt.Unchecked,
                Qt.CheckStateRole,
            )

    def _apply_enabled_to_rows(self, source_rows: list[int], enabled: bool) -> None:
        """Bulk-update detection checkboxes in the source model."""
        self._updating_detection_table = True
        try:
            self._detection_model.set_enabled_rows(source_rows, enabled)
        finally:
            self._updating_detection_table = False

    def _on_detection_model_changed(self, top_left, bottom_right, roles) -> None:
        """React to checkbox state changes from the detection model."""
        if self._updating_detection_table:
            return
        if top_left.column() > 0 or bottom_right.column() < 0:
            return
        if roles and Qt.CheckStateRole not in roles and Qt.DisplayRole not in roles:
            return
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._update_detection_detail()
        self._refresh_ai_overlay()
        self._persist_current_results()

    def _on_enable_all(self) -> None:
        """Enable every detection for the current file."""
        self._apply_enabled_to_rows(list(range(self._detection_model.rowCount())), True)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()

    def _on_disable_all(self) -> None:
        """Disable every detection for the current file."""
        self._apply_enabled_to_rows(list(range(self._detection_model.rowCount())), False)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()

    def _on_enable_selected(self) -> None:
        """Enable the currently selected detections."""
        source_rows = sorted(
            {
                self._detection_proxy.mapToSource(index).row()
                for index in self._detection_table.selectionModel().selectedRows()
                if self._detection_proxy.mapToSource(index).isValid()
            }
        )
        if not source_rows:
            QMessageBox.information(
                self,
                "No detections selected",
                "Select one or more detection rows to enable.",
            )
            return
        self._apply_enabled_to_rows(source_rows, True)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()

    def _on_disable_selected(self) -> None:
        """Disable the currently selected detections."""
        source_rows = sorted(
            {
                self._detection_proxy.mapToSource(index).row()
                for index in self._detection_table.selectionModel().selectedRows()
                if self._detection_proxy.mapToSource(index).isValid()
            }
        )
        if not source_rows:
            QMessageBox.information(
                self,
                "No detections selected",
                "Select one or more detection rows to disable.",
            )
            return
        self._apply_enabled_to_rows(source_rows, False)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()

    def _update_detection_detail(self, *_args) -> None:
        """Show a readable summary of the currently selected detection."""
        rows = self._detection_table.selectionModel().selectedRows()
        if not rows:
            self._detection_detail.setPlainText(
                "Select a detection to inspect its details."
            )
            self._disable_detail_btn.setEnabled(False)
            self._enable_detail_btn.setEnabled(False)
            self._copy_label_btn.setEnabled(False)
            return
        source_index = self._detection_proxy.mapToSource(rows[0])
        row_data = self._detection_model.row_data(source_index.row())
        if not row_data:
            self._detection_detail.setPlainText(
                "Select a detection to inspect its details."
            )
            self._disable_detail_btn.setEnabled(False)
            self._enable_detail_btn.setEnabled(False)
            self._copy_label_btn.setEnabled(False)
            return

        det = row_data["detection"]
        lines = [
            f"Label: {det.get('label', '')}",
            f"Scientific: {det.get('scientific_name', '') or '-'}",
            f"English: {det.get('english_name', '') or '-'}",
            f"Dutch: {det.get('dutch_name', '') or '-'}",
            f"Score: {det.get('score', 0.0):.3f}",
            f"Start: {det.get('start_time', 0.0):.2f} s",
            f"End: {det.get('end_time', 0.0):.2f} s",
            f"Enabled: {'Yes' if det.get('enabled', True) else 'No'}",
            f"Detail: {det.get('detail', '') or '-'}",
        ]
        if det.get("level"):
            lines.append(f"Level: {det.get('level')}")
        if det.get("tag"):
            lines.append(f"Tag: {det.get('tag')}")
        self._detection_detail.setPlainText("\n".join(lines))
        enabled = det.get("enabled", True)
        self._disable_detail_btn.setEnabled(enabled)
        self._enable_detail_btn.setEnabled(not enabled)
        self._copy_label_btn.setEnabled(True)

    def _current_detection(self) -> dict | None:
        """Return the currently selected detection dict, if any."""
        row_data = self._current_detection_row()
        if not row_data:
            return None
        return row_data["detection"]

    def _current_detection_row(self) -> dict | None:
        """Return the currently selected detection row wrapper, if any."""
        rows = self._detection_table.selectionModel().selectedRows()
        if not rows:
            return None
        source_index = self._detection_proxy.mapToSource(rows[0])
        return self._detection_model.row_data(source_index.row())

    def _disable_current_detection(self) -> None:
        """Disable the currently selected detection from the detail pane."""
        rows = self._detection_table.selectionModel().selectedRows()
        if not rows:
            return
        source_index = self._detection_proxy.mapToSource(rows[0])
        self._set_detection_enabled(source_index.row(), False)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()
        self._update_detection_detail()

    def _enable_current_detection(self) -> None:
        """Enable the currently selected detection from the detail pane."""
        rows = self._detection_table.selectionModel().selectedRows()
        if not rows:
            return
        source_index = self._detection_proxy.mapToSource(rows[0])
        self._set_detection_enabled(source_index.row(), True)
        if self._enabled_only_filter.isChecked():
            self._apply_detection_filters()
        self._refresh_ai_overlay()
        self._persist_current_results()
        self._update_detection_detail()

    def _copy_current_detection_label(self) -> None:
        """Copy the best available label for the selected detection."""
        det = self._current_detection()
        if not det:
            return
        text = (
            det.get("scientific_name")
            or det.get("english_name")
            or det.get("dutch_name")
            or det.get("label")
            or ""
        )
        QApplication.clipboard().setText(text)

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
    dialog.prepare_analysis()
    dialog.exec_()
