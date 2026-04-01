"""AI Analysis Dialog for field recordings.

Provides BirdNET (bird species detection) and AST (soundscape classification)
analysis for a single WAV file, with a timeline view of detections and
tag export to WAV metadata via the existing WavSaveManager.

Results are cached in a sidecar JSON file next to the WAV so analysis only
runs once per file.

Classes:
    AiAnalysisWorker: Background QThread that runs BirdNET and AST.
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
# Dutch species names (BirdNET provides English + scientific only)
# ---------------------------------------------------------------------------

DUTCH_NAMES = {
    "Alopochen aegyptiaca": "Nijlgans",
    "Anas platyrhynchos": "Wilde Eend",
    "Anas crecca": "Wintertaling",
    "Anas acuta": "Pijlstaart",
    "Anas querquedula": "Zomertaling",
    "Anas clypeata": "Slobeend",
    "Anas penelope": "Smient",
    "Anas strepera": "Krakeend",
    "Aythya fuligula": "Kuifeend",
    "Aythya ferina": "Tafeleend",
    "Anser anser": "Grauwe Gans",
    "Anser albifrons": "Kolgans",
    "Anser brachyrhynchus": "Kleine Rietgans",
    "Branta canadensis": "Canadese Gans",
    "Branta leucopsis": "Brandgans",
    "Branta bernicla": "Rotgans",
    "Cygnus olor": "Knobbelzwaan",
    "Cygnus cygnus": "Wilde Zwaan",
    "Chroicocephalus ridibundus": "Kokmeeuw",
    "Larus argentatus": "Zilvermeeuw",
    "Larus michahellis": "Geelpootmeeuw",
    "Larus fuscus": "Kleine Mantelmeeuw",
    "Larus marinus": "Grote Mantelmeeuw",
    "Larus canus": "Stormmeeuw",
    "Hydrocoloeus minutus": "Dwergmeeuw",
    "Sterna hirundo": "Visdief",
    "Scolopax rusticola": "Houtsnip",
    "Gallinago gallinago": "Watersnip",
    "Vanellus vanellus": "Kievit",
    "Pluvialis apricaria": "Goudplevier",
    "Charadrius hiaticula": "Bontbekplevier",
    "Haematopus ostralegus": "Scholekster",
    "Tringa totanus": "Tureluur",
    "Tringa nebularia": "Groenpootruiter",
    "Actitis hypoleucos": "Oeverloper",
    "Numenius arquata": "Wulp",
    "Limosa limosa": "Grutto",
    "Ardea cinerea": "Blauwe Reiger",
    "Ardea alba": "Grote Zilverreiger",
    "Egretta garzetta": "Kleine Zilverreiger",
    "Nycticorax nycticorax": "Kwak",
    "Ciconia ciconia": "Ooievaar",
    "Phalacrocorax carbo": "Aalscholver",
    "Podiceps cristatus": "Fuut",
    "Fulica atra": "Meerkoet",
    "Gallinula chloropus": "Waterhoen",
    "Rallus aquaticus": "Waterral",
    "Alcedo atthis": "IJsvogel",
    "Columba palumbus": "Houtduif",
    "Columba livia": "Stadsduif",
    "Streptopelia decaocto": "Turkse Tortel",
    "Streptopelia turtur": "Tortelduif",
    "Cuculus canorus": "Koekoek",
    "Apus apus": "Gierzwaluw",
    "Hirundo rustica": "Boerenzwaluw",
    "Delichon urbicum": "Huiszwaluw",
    "Riparia riparia": "Oeverzwaluw",
    "Picus viridis": "Groene Specht",
    "Dendrocopos major": "Grote Bonte Specht",
    "Dendrocopos minor": "Kleine Bonte Specht",
    "Dryocopus martius": "Zwarte Specht",
    "Falco tinnunculus": "Torenvalk",
    "Falco subbuteo": "Boomvalk",
    "Falco peregrinus": "Slechtvalk",
    "Accipiter nisus": "Sperwer",
    "Accipiter gentilis": "Havik",
    "Buteo buteo": "Buizerd",
    "Pernis apivorus": "Wespendief",
    "Milvus milvus": "Rode Wouw",
    "Circus aeruginosus": "Bruine Kiekendief",
    "Haliaeetus albicilla": "Zeearend",
    "Corvus corax": "Raaf",
    "Corvus corone": "Zwarte Kraai",
    "Corvus monedula": "Kauw",
    "Corvus frugilegus": "Roek",
    "Pica pica": "Ekster",
    "Garrulus glandarius": "Vlaamse Gaai",
    "Parus major": "Koolmees",
    "Cyanistes caeruleus": "Pimpelmees",
    "Periparus ater": "Zwarte Mees",
    "Lophophanes cristatus": "Kuifmees",
    "Poecile palustris": "Glanskop",
    "Poecile montanus": "Matkop",
    "Aegithalos caudatus": "Staartmees",
    "Sitta europaea": "Boomklever",
    "Certhia familiaris": "Boomkruiper",
    "Troglodytes troglodytes": "Winterkoning",
    "Erithacus rubecula": "Roodborst",
    "Luscinia megarhynchos": "Nachtegaal",
    "Phoenicurus ochruros": "Zwarte Roodstaart",
    "Phoenicurus phoenicurus": "Gekraagde Roodstaart",
    "Saxicola rubetra": "Paapje",
    "Saxicola torquatus": "Roodborsttapuit",
    "Turdus merula": "Merel",
    "Turdus philomelos": "Zanglijster",
    "Turdus iliacus": "Koperwiek",
    "Turdus pilaris": "Kramsvogel",
    "Turdus viscivorus": "Grote Lijster",
    "Muscicapa striata": "Grauwe Vliegenvanger",
    "Ficedula hypoleuca": "Bonte Vliegenvanger",
    "Sylvia atricapilla": "Zwartkop",
    "Sylvia communis": "Grasmus",
    "Sylvia borin": "Tuinfluiter",
    "Curruca curruca": "Braamsluiper",
    "Acrocephalus scirpaceus": "Kleine Karekiet",
    "Acrocephalus arundinaceus": "Grote Karekiet",
    "Acrocephalus palustris": "Bosrietzanger",
    "Locustella naevia": "Sprinkhaanzanger",
    "Phylloscopus collybita": "Tjiftjaf",
    "Phylloscopus trochilus": "Fitis",
    "Regulus regulus": "Goudhaan",
    "Regulus ignicapilla": "Vuurgoudhaan",
    "Fringilla coelebs": "Vink",
    "Fringilla montifringilla": "Keep",
    "Chloris chloris": "Groenling",
    "Carduelis carduelis": "Putter",
    "Spinus spinus": "Sijs",
    "Linaria cannabina": "Kneu",
    "Pyrrhula pyrrhula": "Goudvink",
    "Coccothraustes coccothraustes": "Appelvink",
    "Emberiza citrinella": "Geelgors",
    "Emberiza schoeniclus": "Rietgors",
    "Passer domesticus": "Huismus",
    "Passer montanus": "Ringmus",
    "Sturnus vulgaris": "Spreeuw",
    "Motacilla alba": "Witte Kwikstaart",
    "Motacilla flava": "Gele Kwikstaart",
    "Motacilla cinerea": "Grote Gele Kwikstaart",
    "Anthus pratensis": "Graspieper",
    "Anthus trivialis": "Boompieper",
    "Anthus spinoletta": "Waterpieper",
    "Lanius collurio": "Grauwe Klauwier",
    "Lanius excubitor": "Klapekster",
    "Oriolus oriolus": "Wielewaal",
}


# ---------------------------------------------------------------------------
# Sidecar JSON helpers
# ---------------------------------------------------------------------------

def _sidecar_path(wav_path: str) -> str:
    """Return the path for the AI analysis sidecar JSON next to the WAV.

    Args:
        wav_path: Absolute path to the WAV file.

    Returns:
        Path string with ``_ai.json`` suffix.
    """
    base, _ = os.path.splitext(wav_path)
    return base + "_ai.json"


def _load_sidecar(wav_path: str) -> dict | None:
    """Load cached AI results from sidecar JSON if it exists.

    Args:
        wav_path: Absolute path to the WAV file.

    Returns:
        Parsed dict or None if not found / unreadable.
    """
    path = _sidecar_path(wav_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
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
    """Background thread that runs BirdNET and AST analysis without blocking the UI.

    Emits ``status`` with a human-readable progress string during analysis and
    ``finished`` with the complete results dict when done. No Qt widgets are
    touched inside ``run()``; all UI updates happen in connected slots on the
    main thread.
    """

    status = pyqtSignal(str)    # progress message shown in loading label
    finished = pyqtSignal(dict) # {wav_path, birdnet: [...], ast: [...]}

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
        """Run BirdNET then AST; emit finished with combined results."""
        import torch  # noqa: PLC0415

        ast_device = "MPS (GPU)" if torch.backends.mps.is_available() else "CPU"
        results = {
            "wav_path": self._wav_path,
            "birdnet": None,
            "ast": None,
            "devices": {"birdnet": "CPU (TFLite)", "ast": ast_device},
        }

        self.status.emit("BirdNET: analysing species (CPU / TFLite)...")
        try:
            results["birdnet"] = self._run_birdnet()
            count = len(results["birdnet"] or [])
            self.status.emit(f"BirdNET: {count} detections — starting AST ({ast_device})...")
        except Exception as exc:
            logger.error("BirdNET analysis failed: %s", exc)
            self.status.emit(f"BirdNET failed — starting AST ({ast_device})...")

        self.status.emit(f"AST: classifying soundscape on {ast_device} (this may take a minute)...")
        try:
            results["ast"] = self._run_ast()
        except Exception as exc:
            logger.error("AST analysis failed: %s", exc)

        self.finished.emit(results)

    def _run_birdnet(self) -> list:
        """Run BirdNET with GPS and date filters from WAV metadata.

        Returns:
            List of detection dicts with common_name, scientific_name,
            confidence, start_time, end_time.
        """
        from birdnetlib import Recording  # noqa: PLC0415
        from birdnetlib.analyzer import Analyzer  # noqa: PLC0415

        analyzer = Analyzer()
        kwargs = {"min_conf": 0.25}

        gps = self._metadata.get("gps") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if lat and lon:
            kwargs["lat"] = float(lat)
            kwargs["lon"] = float(lon)

        bext = self._metadata.get("bext") or {}
        date_str = bext.get("OriginationDate", "")
        if date_str and len(date_str) >= 10:
            try:
                from datetime import date as dt  # noqa: PLC0415
                d = dt.fromisoformat(date_str[:10])
                kwargs["week"] = min(max(round(d.timetuple().tm_yday / 7.25), 1), 48)
            except ValueError:
                pass

        recording = Recording(analyzer, self._wav_path, **kwargs)
        recording.analyze()
        return [
            {
                "common_name": det["common_name"],
                "scientific_name": det["scientific_name"],
                "confidence": det["confidence"],
                "start_time": det["start_time"],
                "end_time": det["end_time"],
            }
            for det in recording.detections
        ]

    def _run_ast(self) -> list:
        """Run AST with a 10s sliding window (50% overlap) over the full WAV.

        Returns:
            List of dicts with label, score, start_time, end_time; sorted by
            start_time.
        """
        import numpy as np  # noqa: PLC0415
        import soundfile as sf  # noqa: PLC0415
        import torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            ASTForAudioClassification,
            AutoFeatureExtractor,
        )

        model_id = "MIT/ast-finetuned-audioset-10-10-0.448"
        extractor = AutoFeatureExtractor.from_pretrained(model_id)
        model = ASTForAudioClassification.from_pretrained(model_id)
        model.eval()
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        model = model.to(device)

        audio, sr = sf.read(self._wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        target_sr = extractor.sampling_rate
        if sr != target_sr:
            import librosa  # noqa: PLC0415
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        chunk_samples = sr * 10
        step_samples = sr * 5
        results = []

        for start in range(0, len(audio), step_samples):
            chunk = audio[start : start + chunk_samples]
            if len(chunk) < sr * 2:
                break
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

            inputs = extractor(chunk, sampling_rate=sr, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = model(**inputs).logits[0]

            scores = torch.sigmoid(logits).cpu().numpy()
            start_s = start / sr
            end_s = min((start + chunk_samples) / sr, len(audio) / sr)

            top_indices = scores.argsort()[::-1][:5]
            for idx in top_indices:
                score = float(scores[idx])
                if score < 0.05:
                    continue
                results.append({
                    "label": model.config.id2label[idx],
                    "score": score,
                    "start_time": start_s,
                    "end_time": end_s,
                })

        return sorted(results, key=lambda x: x["start_time"])


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class AiAnalysisDialog(QDialog):
    """Dialog showing BirdNET and AST results for a single WAV file.

    Displays a two-tab interface: a chronological detection table and a
    tag-selection panel. The user can tick tags and apply them to the WAV
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
        self._results = None
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
            ["Time", "Source", "Label", "Dutch / Scientific", "Conf"]
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

        # Device info label (shown after analysis)
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
        """Slot called on the main thread when the worker finishes.

        Args:
            results: Dict with keys wav_path, birdnet, ast.
        """
        self._results = results
        _save_sidecar(self._wav_path, results)

        self._loading_label.setVisible(False)
        self._tabs.setVisible(True)
        self._apply_btn.setEnabled(True)
        self._reanalyze_btn.setEnabled(True)

        self._populate_detections(results)
        self._populate_tags(results)

        devices = results.get("devices") or {}
        birdnet_dev = devices.get("birdnet", "CPU")
        ast_dev = devices.get("ast", "CPU")
        self._device_label.setText(f"BirdNET: {birdnet_dev}  |  AST: {ast_dev}")

        # Refresh waveform overlay and hide progress spinner
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

    def _populate_detections(self, results: dict) -> None:
        """Fill the detections table with BirdNET and AST rows.

        Args:
            results: Results dict from the worker.
        """
        birdnet = results.get("birdnet") or []
        ast = results.get("ast") or []

        rows = []
        for det in birdnet:
            dutch = DUTCH_NAMES.get(det["scientific_name"], "–")
            rows.append((
                det["start_time"], det["end_time"],
                "BirdNET", det["common_name"], dutch, det["confidence"],
            ))
        for det in ast:
            rows.append((
                det["start_time"], det["end_time"],
                "AST", det["label"], "", det["score"],
            ))
        rows.sort(key=lambda r: r[0])

        self._detection_table.setRowCount(len(rows))
        birdnet_color = QColor("#1a3d2b")
        ast_color = QColor("#1a2540")

        for row_idx, (start_s, end_s, src, label, detail, conf) in enumerate(rows):
            start_fmt = f"{int(start_s) // 60}:{int(start_s) % 60:02d}"
            end_fmt = f"{int(end_s) // 60}:{int(end_s) % 60:02d}"
            cells = [
                QTableWidgetItem(f"{start_fmt} – {end_fmt}"),
                QTableWidgetItem(src),
                QTableWidgetItem(label),
                QTableWidgetItem(detail),
                QTableWidgetItem(f"{conf:.2f}"),
            ]
            bg = birdnet_color if src == "BirdNET" else ast_color
            for col, cell in enumerate(cells):
                cell.setBackground(bg)
                cell.setForeground(QColor("#e8e8e8"))
                self._detection_table.setItem(row_idx, col, cell)

        self._detection_table.resizeColumnsToContents()

    def _populate_tags(self, results: dict) -> None:
        """Fill the Tags tab with deduplicated, checkable tag labels.

        BirdNET species are shown with their Dutch name; AST labels are shown
        only when their score exceeds 0.20. Tags with high confidence are
        pre-checked.

        Args:
            results: Results dict from the worker.
        """
        # Clear previous state
        while self._tag_layout.count():
            child = self._tag_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._tag_checkboxes.clear()

        birdnet = results.get("birdnet") or []
        ast = results.get("ast") or []

        def _add_tag(tag: str, label_text: str, checked: bool) -> None:
            cb = QCheckBox(label_text)
            cb.setChecked(checked)
            self._tag_layout.addWidget(cb)
            self._tag_checkboxes.append((cb, tag))

        # BirdNET — one entry per unique species, best confidence
        seen: dict[str, float] = {}
        for det in sorted(birdnet, key=lambda d: -d["confidence"]):
            sci = det["scientific_name"]
            if sci not in seen:
                seen[sci] = det["confidence"]
                dutch = DUTCH_NAMES.get(sci)
                tag = dutch or det["common_name"]
                label = f"{tag}  [{det['common_name']}]  — BirdNET {det['confidence']:.2f}"
                _add_tag(tag, label, checked=True)

        # AST — one entry per unique label above 0.20, best score
        seen_ast: dict[str, float] = {}
        for det in sorted(ast, key=lambda d: -d["score"]):
            lbl = det["label"]
            if det["score"] >= 0.20 and lbl not in seen_ast:
                seen_ast[lbl] = det["score"]
                label = f"{lbl}  — AST {det['score']:.2f}"
                _add_tag(lbl, label, checked=det["score"] >= 0.40)

    # ------------------------------------------------------------------
    # Tag application
    # ------------------------------------------------------------------

    def _on_apply_tags(self) -> None:
        """Collect checked tags and emit ``tags_selected`` signal."""
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
