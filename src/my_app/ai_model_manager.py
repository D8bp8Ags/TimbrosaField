"""Central model storage, validation, import, and installation helpers."""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import shutil
import queue as queue_mod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

_INSTALL_WORKER_TIMEOUT_SECONDS = 900


class ModelStatus(Enum):
    """Installation state for a managed AI model."""

    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLED = "installed"
    CORRUPT = "corrupt"
    ERROR = "error"


class AIModelError(Exception):
    """Base exception carrying user-facing and technical model details."""

    def __init__(self, model_id: str, message: str, details: str = "") -> None:
        super().__init__(message)
        self.model_id = model_id
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message


class ModelMissingError(AIModelError):
    """Raised when a required model is not installed."""


class ModelCorruptError(AIModelError):
    """Raised when a model exists but fails validation."""


class ModelInstallError(AIModelError):
    """Raised when installation or import fails."""


@dataclass(frozen=True)
class ModelDefinition:
    """Immutable description of a managed model."""

    model_id: str
    display_name: str
    backend: str
    version: str
    relative_dir: str
    source: str
    license: str
    required_files: tuple[str, ...]
    revision: str = ""
    repo_id: str = ""
    slug: str = ""
    kaggle_version: int | None = None
    model_type: str = ""
    package_backend: str = ""
    precision: str = ""
    primary_file: str = ""
    primary_size: int | None = None
    primary_sha256: str = ""
    label_file: str = ""


AST_MODEL = ModelDefinition(
    model_id="ast_audioset",
    display_name="AST AudioSet",
    backend="AST",
    version="76516f20",
    relative_dir="ast/ast-finetuned-audioset-10-10-0.448__76516f20",
    source="Hugging Face: MIT/ast-finetuned-audioset-10-10-0.448",
    license="Apache-2.0",
    repo_id="MIT/ast-finetuned-audioset-10-10-0.448",
    revision="76516f20c86ec66e559eb81b47c608d4580763dd",
    required_files=("config.json", "preprocessor_config.json", "model.safetensors"),
    primary_file="model.safetensors",
    primary_size=346404948,
    primary_sha256="79035191dbd2263b338beb72f52c963c2da578b327b6e980670ea372e732d452",
)

PERCH_MODEL = ModelDefinition(
    model_id="perch_v2_cpu",
    display_name="Perch v2 CPU",
    backend="Perch",
    version="1",
    relative_dir="perch/perch_v2_cpu_1",
    source="Kaggle Models: google/bird-vocalization-classifier/tensorFlow2/perch_v2_cpu/1",
    license="Apache-2.0",
    slug="google/bird-vocalization-classifier/tensorFlow2/perch_v2_cpu",
    kaggle_version=1,
    required_files=(
        "saved_model.pb",
        "fingerprint.pb",
        "variables/variables.data-00000-of-00001",
        "variables/variables.index",
        "assets/labels.csv",
        "assets/perch_v2_ebird_classes.csv",
    ),
)

BIRDNET_ACOUSTIC_MODEL = ModelDefinition(
    model_id="birdnet_acoustic",
    display_name="BirdNET Acoustic 2.4",
    backend="BirdNET",
    version="2.4",
    relative_dir="birdnet/acoustic/acoustic_2.4_tf_fp32",
    source="Official birdnet package / Zenodo model mirror",
    license="BirdNET package/model license",
    model_type="acoustic",
    package_backend="tf",
    precision="fp32",
    required_files=("model-fp32.tflite", "labels/en_us.txt"),
    primary_file="model-fp32.tflite",
    primary_size=51726412,
    label_file="labels/en_us.txt",
)

BIRDNET_GEO_MODEL = ModelDefinition(
    model_id="birdnet_geo",
    display_name="BirdNET Geo 2.4",
    backend="BirdNET",
    version="2.4",
    relative_dir="birdnet/geo/geo_2.4_tf_fp32",
    source="Official birdnet package / Zenodo model mirror",
    license="BirdNET package/model license",
    model_type="geo",
    package_backend="tf",
    precision="fp32",
    required_files=("model-fp32.tflite", "labels/en_us.txt"),
    primary_file="model-fp32.tflite",
    primary_size=29526096,
    label_file="labels/en_us.txt",
)

MODEL_DEFINITIONS: tuple[ModelDefinition, ...] = (
    AST_MODEL,
    PERCH_MODEL,
    BIRDNET_ACOUSTIC_MODEL,
    BIRDNET_GEO_MODEL,
)
_MODEL_BY_ID = {definition.model_id: definition for definition in MODEL_DEFINITIONS}


def get_models_root() -> Path:
    """Return the central model root."""
    override = os.environ.get("TIMBROSA_MODELS_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent / "models"


def get_downloads_dir() -> Path:
    return get_models_root() / ".downloads"


def get_staging_dir() -> Path:
    return get_models_root() / ".staging"


def get_ast_models_dir() -> Path:
    return get_models_root() / "ast"


def get_perch_models_dir() -> Path:
    return get_models_root() / "perch"


def get_birdnet_models_dir() -> Path:
    return get_models_root() / "birdnet"


def get_perch_kagglehub_cache() -> Path:
    return get_perch_models_dir() / ".kagglehub"


def get_model_definition(model_id: str) -> ModelDefinition:
    try:
        return _MODEL_BY_ID[model_id]
    except KeyError as exc:
        raise AIModelError(model_id, "Unknown model", model_id) from exc


def iter_model_definitions() -> tuple[ModelDefinition, ...]:
    return MODEL_DEFINITIONS


def get_model_dir(model_id: str) -> Path:
    return get_models_root() / get_model_definition(model_id).relative_dir


def get_ast_model_dir() -> Path:
    return get_model_dir(AST_MODEL.model_id)


def get_perch_model_dir() -> Path:
    return get_model_dir(PERCH_MODEL.model_id)


def get_birdnet_acoustic_paths() -> tuple[Path, Path]:
    base = get_model_dir(BIRDNET_ACOUSTIC_MODEL.model_id)
    return base / BIRDNET_ACOUSTIC_MODEL.primary_file, base / BIRDNET_ACOUSTIC_MODEL.label_file


def get_birdnet_geo_paths() -> tuple[Path, Path]:
    base = get_model_dir(BIRDNET_GEO_MODEL.model_id)
    return base / BIRDNET_GEO_MODEL.primary_file, base / BIRDNET_GEO_MODEL.label_file


def required_model_ids_for_backends(
    backend_names: set[str],
    backend_options: dict | None = None,
) -> list[str]:
    """Return model IDs required for selected backend display names."""
    result: list[str] = []
    normalized = {name.lower() for name in backend_names}
    if "birdnet" in normalized:
        result.append(BIRDNET_ACOUSTIC_MODEL.model_id)
        birdnet_options = (backend_options or {}).get("birdnet", {})
        if birdnet_options.get("use_geo_filter", True):
            result.append(BIRDNET_GEO_MODEL.model_id)
    if "ast" in normalized:
        result.append(AST_MODEL.model_id)
    if "perch" in normalized:
        result.append(PERCH_MODEL.model_id)
    return result


def ensure_model_installed(model_id: str) -> Path:
    """Return a local model path or raise a user-facing model error."""
    model_dir = get_model_dir(model_id)
    if not model_dir.exists():
        raise ModelMissingError(
            model_id,
            f"{get_model_definition(model_id).display_name} is not installed.",
            str(model_dir),
        )
    validate_model(model_id)
    return model_dir


def get_model_status(model_id: str) -> ModelStatus:
    model_dir = get_model_dir(model_id)
    if not model_dir.exists():
        return ModelStatus.NOT_INSTALLED
    try:
        validate_model(model_id, full_hash=False)
    except ModelCorruptError:
        return ModelStatus.CORRUPT
    except AIModelError:
        return ModelStatus.ERROR
    return ModelStatus.INSTALLED


def validate_model(model_id: str, full_hash: bool = False, base_dir: Path | None = None) -> None:
    """Validate a model directory without triggering package downloads."""
    definition = get_model_definition(model_id)
    model_dir = base_dir or get_model_dir(model_id)
    if not model_dir.is_dir():
        raise ModelMissingError(model_id, "Model directory is missing.", str(model_dir))

    for rel_path in definition.required_files:
        path = model_dir / rel_path
        if not path.is_file():
            raise ModelCorruptError(model_id, "Required model file is missing.", str(path))

    if definition.primary_file and definition.primary_size is not None:
        path = model_dir / definition.primary_file
        size = path.stat().st_size
        if size != definition.primary_size:
            raise ModelCorruptError(
                model_id,
                "Model file has the wrong size.",
                f"{path}: {size} != {definition.primary_size}",
            )

    if definition.label_file:
        label_path = model_dir / definition.label_file
        if not label_path.read_text(encoding="utf-8").strip():
            raise ModelCorruptError(model_id, "Model label file is empty.", str(label_path))

    if full_hash and definition.primary_sha256:
        path = model_dir / definition.primary_file
        digest = _sha256(path)
        if digest != definition.primary_sha256:
            raise ModelCorruptError(
                model_id,
                "Model file checksum does not match.",
                f"{path}: {digest} != {definition.primary_sha256}",
            )


def install_model(model_id: str, progress: Callable[[str], None] | None = None) -> Path:
    """Explicitly install a model using the official package download function."""
    definition = get_model_definition(model_id)
    _emit(progress, f"Installing {definition.display_name}")
    if model_id == AST_MODEL.model_id:
        return _install_ast(progress)
    if model_id == PERCH_MODEL.model_id:
        return _install_perch(progress)
    if model_id in (BIRDNET_ACOUSTIC_MODEL.model_id, BIRDNET_GEO_MODEL.model_id):
        return _install_birdnet(model_id, progress)
    raise ModelInstallError(model_id, "No installer is defined for this model.")


def import_existing_model(model_id: str, progress: Callable[[str], None] | None = None) -> Path:
    """Import a known existing package cache into the managed model directory."""
    definition = get_model_definition(model_id)
    source = find_existing_cache_source(model_id)
    if source is None:
        raise ModelMissingError(
            model_id,
            f"No existing cache found for {definition.display_name}.",
            definition.source,
        )
    _emit(progress, f"Importing {definition.display_name}")
    staging = _fresh_staging(model_id)
    try:
        if model_id == AST_MODEL.model_id:
            _copy_selected_files(source, staging, definition.required_files)
            validate_model(model_id, full_hash=True, base_dir=staging)
        else:
            _copy_tree_clean(source, staging)
            validate_model(model_id, base_dir=staging)
        return _activate_staging(model_id, staging, imported_from=str(source))
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def find_existing_cache_source(model_id: str) -> Path | None:
    """Return a usable source cache path for importing, if present."""
    if model_id == AST_MODEL.model_id:
        path = (
            Path.home()
            / ".cache/huggingface/hub/models--MIT--ast-finetuned-audioset-10-10-0.448"
            / "snapshots"
            / AST_MODEL.revision
        )
        return path if path.is_dir() else None
    if model_id == PERCH_MODEL.model_id:
        path = (
            Path.home()
            / ".cache/kagglehub/models/google/bird-vocalization-classifier"
            / "tensorFlow2/perch_v2_cpu/1"
        )
        return path if path.is_dir() else None
    if model_id == BIRDNET_ACOUSTIC_MODEL.model_id:
        return _birdnet_default_cache_dir("acoustic")
    if model_id == BIRDNET_GEO_MODEL.model_id:
        return _birdnet_default_cache_dir("geo")
    return None


def remove_model(model_id: str) -> None:
    """Remove only the managed TimbrosaField model directory."""
    model_dir = get_model_dir(model_id)
    _assert_managed_path(model_dir)
    if model_dir.exists():
        shutil.rmtree(model_dir)


def read_install_metadata(model_id: str) -> dict:
    path = get_model_dir(model_id) / "install.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _install_ast(progress: Callable[[str], None] | None) -> Path:
    model_id = AST_MODEL.model_id
    staging = _fresh_staging(model_id)
    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415

        _emit(progress, "Downloading AST snapshot")
        snapshot_download(
            repo_id=AST_MODEL.repo_id,
            revision=AST_MODEL.revision,
            local_dir=staging,
            allow_patterns=list(AST_MODEL.required_files),
        )
        _emit(progress, "Verifying AST")
        validate_model(model_id, full_hash=True, base_dir=staging)
        shutil.rmtree(staging / ".cache", ignore_errors=True)
        return _activate_staging(model_id, staging)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(exc, AIModelError):
            raise
        raise ModelInstallError(model_id, "AST installation failed.", str(exc)) from exc


def _install_perch(progress: Callable[[str], None] | None) -> Path:
    model_id = PERCH_MODEL.model_id
    source = _run_child_process(_perch_resolve_worker, (str(get_perch_kagglehub_cache()),))
    staging = _fresh_staging(model_id)
    try:
        _emit(progress, "Copying Perch model")
        _copy_tree_clean(Path(source), staging)
        _emit(progress, "Verifying Perch")
        validate_model(model_id, base_dir=staging)
        return _activate_staging(model_id, staging, imported_from=str(source))
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(exc, AIModelError):
            raise
        raise ModelInstallError(model_id, "Perch installation failed.", str(exc)) from exc


def _install_birdnet(model_id: str, progress: Callable[[str], None] | None) -> Path:
    definition = get_model_definition(model_id)
    source = _run_child_process(
        _birdnet_load_worker,
        (definition.model_type, definition.version, definition.package_backend, definition.precision),
    )
    staging = _fresh_staging(model_id)
    try:
        _emit(progress, f"Copying {definition.display_name}")
        _copy_tree_clean(Path(source), staging)
        _emit(progress, f"Verifying {definition.display_name}")
        validate_model(model_id, base_dir=staging)
        return _activate_staging(model_id, staging, imported_from=str(source))
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(exc, AIModelError):
            raise
        raise ModelInstallError(model_id, "BirdNET installation failed.", str(exc)) from exc


def _perch_resolve_worker(cache_root: str, result_queue: mp.Queue) -> None:
    try:
        os.environ["KAGGLEHUB_CACHE"] = cache_root
        from perch_hoplite.zoo import hub  # noqa: PLC0415

        path = hub.resolve(PERCH_MODEL.slug, PERCH_MODEL.kaggle_version)
        result_queue.put({"ok": True, "path": path})
    except Exception as exc:
        result_queue.put({"ok": False, "error": repr(exc)})


def _birdnet_load_worker(
    model_type: str,
    version: str,
    backend: str,
    precision: str,
    result_queue: mp.Queue,
) -> None:
    try:
        import birdnet  # noqa: PLC0415
        from birdnet.utils.local_data import get_model_root_dir  # noqa: PLC0415

        birdnet.load(model_type, version, backend, precision=precision)
        path = get_model_root_dir(model_type, version, backend)
        result_queue.put({"ok": True, "path": str(path)})
    except Exception as exc:
        result_queue.put({"ok": False, "error": repr(exc)})


def _run_child_process(target, args: tuple) -> str:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=target, args=(*args, queue))
    process.start()
    process.join(_INSTALL_WORKER_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(timeout=30)
        raise ModelInstallError(
            "child_process",
            "Model install worker timed out.",
            f">{_INSTALL_WORKER_TIMEOUT_SECONDS}s",
        )
    if process.exitcode != 0:
        raise ModelInstallError("child_process", "Model install worker failed.", f"exit code {process.exitcode}")
    try:
        result = queue.get_nowait()
    except queue_mod.Empty as exc:
        raise ModelInstallError("child_process", "Model install worker returned no result.")
    finally:
        queue.close()
        queue.join_thread()
    if not result.get("ok"):
        raise ModelInstallError("child_process", "Model install worker failed.", result.get("error", ""))
    return str(result["path"])


def _fresh_staging(model_id: str) -> Path:
    root = get_staging_dir()
    root.mkdir(parents=True, exist_ok=True)
    staging = root / model_id
    _assert_managed_path(staging)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def _activate_staging(model_id: str, staging: Path, imported_from: str = "") -> Path:
    definition = get_model_definition(model_id)
    validate_model(
        model_id,
        full_hash=model_id == AST_MODEL.model_id,
        base_dir=staging,
    )
    _write_install_metadata(staging, definition, imported_from)
    destination = get_model_dir(model_id)
    _assert_managed_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f"{destination.name}.old")
    _assert_managed_path(backup)
    shutil.rmtree(backup, ignore_errors=True)
    if destination.exists():
        destination.rename(backup)
    try:
        staging.rename(destination)
    except Exception:
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    shutil.rmtree(backup, ignore_errors=True)
    return destination


def _write_install_metadata(model_dir: Path, definition: ModelDefinition, imported_from: str = "") -> None:
    metadata = {
        "model_id": definition.model_id,
        "version": definition.version,
        "revision": definition.revision,
        "source": definition.source,
        "imported_from": imported_from,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "verification": "passed",
    }
    (model_dir / "install.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _copy_selected_files(source: Path, destination: Path, files: tuple[str, ...]) -> None:
    for rel_path in files:
        src = source / rel_path
        dst = destination / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_tree_clean(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ModelInstallError("", "Source model directory is missing.", str(source))
    for item in source.rglob("*"):
        if _is_ignored_model_file(item):
            continue
        rel = item.relative_to(source)
        target = destination / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _is_ignored_model_file(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._")


def _birdnet_default_cache_dir(model_type: str) -> Path | None:
    root = _birdnet_app_dir()
    path = root / f"{model_type}-models" / "v2.4" / "tf"
    return path if path.is_dir() else None


def _birdnet_app_dir() -> Path:
    if os.name == "nt":
        app_data = os.environ.get("APPDATA", str(Path.home()))
        return Path(app_data) / "birdnet"
    if os.name == "posix" and hasattr(os, "uname") and os.uname().sysname == "Darwin":
        return Path.home() / "Library/Application Support/birdnet"
    return Path.home() / ".local/share/birdnet"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def _assert_managed_path(path: Path) -> None:
    root = get_models_root().resolve()
    resolved = path.resolve()
    if resolved == root or root not in resolved.parents:
        raise ModelInstallError(
            "",
            "Refusing to modify a path outside the managed model root.",
            str(resolved),
        )
