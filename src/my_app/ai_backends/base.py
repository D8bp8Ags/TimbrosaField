"""Compatibility shim; remove in phase 9.

ai_backends/base.py moved to ai/backends/base.py (Fase 7).
"""
from ai.backends.base import *  # noqa: F401,F403
