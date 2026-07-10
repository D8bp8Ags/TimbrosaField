"""PyQt model-management dialog for TimbrosaField AI models."""

from __future__ import annotations

import traceback

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from ai_model_manager import (
    AIModelError,
    ModelStatus,
    find_existing_cache_source,
    get_model_dir,
    get_model_status,
    import_existing_model,
    install_model,
    iter_model_definitions,
    read_install_metadata,
    remove_model,
    validate_model,
)


_HEADERS = (
    "Model",
    "Backend",
    "Version",
    "Status",
    "Size",
    "Local path",
    "License",
    "Source",
)


class _InstallWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, bool, str)

    def __init__(self, model_id: str, action: str) -> None:
        super().__init__()
        self._model_id = model_id
        self._action = action

    def run(self) -> None:
        try:
            if self._action == "install":
                path = install_model(self._model_id, self.progress.emit)
            elif self._action == "import":
                path = import_existing_model(self._model_id, self.progress.emit)
            elif self._action == "verify":
                validate_model(self._model_id, full_hash=True)
                path = get_model_dir(self._model_id)
            else:
                raise AIModelError(self._model_id, "Unknown model action.", self._action)
            self.finished.emit(self._model_id, True, str(path))
        except Exception as exc:
            details = getattr(exc, "details", "") or traceback.format_exc(limit=3)
            self.finished.emit(self._model_id, False, f"{exc}\n{details}")


class _ModelTable(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.definitions = list(iter_model_definitions())

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.definitions)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.UserRole):
            return None
        definition = self.definitions[index.row()]
        if role == Qt.UserRole:
            return definition.model_id
        status = get_model_status(definition.model_id)
        metadata = read_install_metadata(definition.model_id)
        values = (
            definition.display_name,
            definition.backend,
            definition.version,
            status.value.replace("_", " "),
            self._size_text(definition.model_id),
            str(get_model_dir(definition.model_id)),
            definition.license,
            metadata.get("source") or definition.source,
        )
        return values[index.column()]

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    @staticmethod
    def _size_text(model_id: str) -> str:
        path = get_model_dir(model_id)
        if not path.exists():
            return "-"
        total = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        if total >= 1024 * 1024:
            return f"{total / (1024 * 1024):.1f} MB"
        return f"{total / 1024:.1f} KB"


class AiModelDialog(QDialog):
    """Standalone model manager dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Model Manager")
        self.setMinimumSize(1120, 520)
        self._worker: _InstallWorker | None = None
        self._setup_ui()
        self._refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

        self._table_model = _ModelTable()
        self._table = QTableView()
        self._table.setModel(self._table_model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._table, 1)

        row = QHBoxLayout()
        self._install_btn = QPushButton("Installeren")
        self._install_btn.clicked.connect(lambda: self._run_action("install"))
        row.addWidget(self._install_btn)

        self._import_btn = QPushButton("Importeren")
        self._import_btn.clicked.connect(lambda: self._run_action("import"))
        row.addWidget(self._import_btn)

        self._verify_btn = QPushButton("Verifiëren")
        self._verify_btn.clicked.connect(lambda: self._run_action("verify"))
        row.addWidget(self._verify_btn)

        self._delete_btn = QPushButton("Verwijderen")
        self._delete_btn.clicked.connect(self._delete_selected)
        row.addWidget(self._delete_btn)

        self._retry_btn = QPushButton("Opnieuw proberen")
        self._retry_btn.clicked.connect(lambda: self._run_action("install"))
        row.addWidget(self._retry_btn)

        row.addStretch()
        self._close_btn = QPushButton("Sluiten")
        self._close_btn.clicked.connect(self.accept)
        row.addWidget(self._close_btn)
        root.addLayout(row)

    def _selected_model_id(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._table_model.definitions[rows[0].row()].model_id

    def _run_action(self, action: str) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            QMessageBox.information(self, "Geen model geselecteerd", "Selecteer eerst een model.")
            return
        if action == "import" and find_existing_cache_source(model_id) is None:
            QMessageBox.information(self, "Geen cache gevonden", "Er is geen bestaande package-cache gevonden voor dit model.")
            return
        self._set_busy(True)
        self._worker = _InstallWorker(model_id, action)
        self._worker.progress.connect(self._status_label.setText)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, model_id: str, ok: bool, message: str) -> None:
        self._set_busy(False)
        self._refresh()
        if ok:
            self._status_label.setText(f"{model_id}: klaar")
        else:
            self._status_label.setText(f"{model_id}: fout")
            QMessageBox.warning(self, "Modelactie mislukt", message)
        self._worker = None

    def _delete_selected(self) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            QMessageBox.information(self, "Geen model geselecteerd", "Selecteer eerst een model.")
            return
        answer = QMessageBox.question(
            self,
            "Model verwijderen",
            "Alleen de TimbrosaField-modelmap wordt verwijderd. Externe caches blijven staan.",
        )
        if answer != QMessageBox.Yes:
            return
        remove_model(model_id)
        self._refresh()

    def _refresh(self) -> None:
        self._table_model.refresh()
        self._table.resizeColumnsToContents()
        installed = sum(
            1
            for definition in iter_model_definitions()
            if get_model_status(definition.model_id) == ModelStatus.INSTALLED
        )
        self._status_label.setText(f"{installed}/{len(iter_model_definitions())} modellen geïnstalleerd")

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self._install_btn,
            self._import_btn,
            self._verify_btn,
            self._delete_btn,
            self._retry_btn,
            self._close_btn,
        ):
            button.setEnabled(not busy)

    def closeEvent(self, event) -> None:
        """Prevent closing while a package call or verification is still running."""
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Modelactie loopt",
                "Wacht tot de huidige modelactie klaar is. Package-downloads zijn niet veilig direct te annuleren.",
            )
            event.ignore()
            return
        super().closeEvent(event)
