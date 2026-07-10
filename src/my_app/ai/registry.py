"""Single source of truth for AI backend registration.

Replaces the previously parallel, independently-maintained registers:
  - ai_analyzer.py's _BACKEND_SPECS (backend display name -> module/class)
  - ai_model_manager.py's per-backend if/elif in required_model_ids_for_backends()

Adding a new backend requires exactly one BackendRegistration entry here
plus one backend implementation module — no other file needs a matching
if/elif branch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendCapabilities:
    """Optional capabilities a backend may support.

    Attributes:
        supports_geo_filter: Whether this backend has an optional
            geo-filtering model/feature that only applies when the
            recording's metadata (GPS + date) makes it usable.
        supports_gpu: Whether this backend can use GPU acceleration
            (reported via AiBackend.device_label at runtime; this flag
            only indicates the capability exists, not that it is active).
    """

    supports_geo_filter: bool = False
    supports_gpu: bool = False


@dataclass(frozen=True)
class BackendRegistration:
    """Single registry entry describing one AI backend.

    Attributes:
        backend_id: Stable identifier used for settings keys and
            model-requirement lookups (lowercase, e.g. "birdnet").
        display_name: Human-readable name shown in the UI (e.g. "BirdNET").
            Matches AiBackend.name on the concrete backend class.
        module_name: Dotted module path containing the backend class
            (e.g. "my_app.ai.backends.birdnet_backend").
        class_name: Name of the AiBackend subclass within that module.
        model_ids: Model IDs (from ai_model_manager.MODEL_DEFINITIONS)
            required for this backend's default operation.
        capabilities: Optional feature flags for this backend.
        settings_key: Key used in ai_settings.DEFAULT_AI_SETTINGS for this
            backend's runtime options (defaults to backend_id).
    """

    backend_id: str
    display_name: str
    module_name: str
    class_name: str
    model_ids: tuple[str, ...] = ()
    capabilities: BackendCapabilities = field(default_factory=BackendCapabilities)
    settings_key: str = ""

    def __post_init__(self) -> None:
        if not self.settings_key:
            object.__setattr__(self, "settings_key", self.backend_id)

    def create_backend(self):
        """Import the backend module and instantiate the backend class.

        Raises:
            ImportError: If the backend's optional dependency is not
                installed. Callers should catch this to skip unavailable
                backends, matching existing behavior.
        """
        module = __import__(self.module_name, fromlist=[self.class_name])
        backend_cls = getattr(module, self.class_name)
        return backend_cls()


BACKEND_REGISTRY: tuple[BackendRegistration, ...] = (
    BackendRegistration(
        backend_id="birdnet",
        display_name="BirdNET",
        module_name="my_app.ai.backends.birdnet_backend",
        class_name="BirdnetBackend",
        model_ids=("birdnet_acoustic", "birdnet_geo"),
        capabilities=BackendCapabilities(supports_geo_filter=True),
    ),
    BackendRegistration(
        backend_id="ast",
        display_name="AST",
        module_name="my_app.ai.backends.ast_backend",
        class_name="AstBackend",
        model_ids=("ast_audioset",),
    ),
    BackendRegistration(
        backend_id="perch",
        display_name="Perch",
        module_name="my_app.ai.backends.perch_backend",
        class_name="PerchBackend",
        model_ids=("perch_v2_cpu",),
    ),
)

_BY_ID = {reg.backend_id: reg for reg in BACKEND_REGISTRY}
_BY_DISPLAY_NAME = {reg.display_name: reg for reg in BACKEND_REGISTRY}


def all_backends() -> tuple[BackendRegistration, ...]:
    """Return all registered backends, in registration order."""
    return BACKEND_REGISTRY


def get_by_id(backend_id: str) -> BackendRegistration | None:
    """Look up a registration by its stable backend_id (case-insensitive)."""
    return _BY_ID.get(backend_id.lower())


def get_by_display_name(display_name: str) -> BackendRegistration | None:
    """Look up a registration by its UI display name (exact match)."""
    return _BY_DISPLAY_NAME.get(display_name)


def load_backends(selected_names: set[str] | None = None) -> list:
    """Import and instantiate selected enabled backends.

    Backends that fail to import (missing optional dependency) are
    silently skipped so the app still starts without every model
    installed — same behavior as the previous ai_analyzer._load_backends().

    Args:
        selected_names: Optional backend display names to instantiate.
            When omitted, all registered backends are instantiated.

    Returns:
        List of AiBackend instances.
    """
    backends = []
    for registration in BACKEND_REGISTRY:
        if selected_names is not None and registration.display_name not in selected_names:
            continue
        try:
            backends.append(registration.create_backend())
        except ImportError:
            logger.info("Backend not available: %s", registration.module_name)
    return backends


def required_model_ids_for_backends(
    backend_names: set[str],
    backend_options: dict | None = None,
) -> list[str]:
    """Return model IDs required for the given backend display names.

    Geo-filter models are only included when the owning backend declares
    supports_geo_filter and the caller's settings enable it (defaulting to
    enabled, matching prior behavior). This is capability-driven rather
    than a hardcoded "birdnet" name check.

    Args:
        backend_names: Backend display names (e.g. {"BirdNET", "AST"}).
        backend_options: Optional per-backend settings dict, keyed by
            settings_key (e.g. {"birdnet": {"use_geo_filter": True}}).

    Returns:
        List of required model IDs, in registry order.
    """
    result: list[str] = []
    normalized = {name.lower() for name in backend_names}

    for registration in BACKEND_REGISTRY:
        if registration.backend_id not in normalized:
            continue
        for model_id in registration.model_ids:
            if model_id.endswith("_geo") and registration.capabilities.supports_geo_filter:
                options = (backend_options or {}).get(registration.settings_key, {})
                if not options.get("use_geo_filter", True):
                    continue
            result.append(model_id)

    return result
