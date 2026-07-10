"""Compatibility shim; remove in phase 9.

ai_analyzer.py moved to ai/ui/analysis_dialog.py (Fase 7).
"""
from ai.ui.analysis_dialog import *  # noqa: F401,F403
from ai.ui.analysis_dialog import _load_sidecar  # noqa: F401
