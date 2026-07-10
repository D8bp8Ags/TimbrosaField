"""Compatibility shim; remove in phase 9.

tag_completer.py split into tags/templates.py (TemplateManager, pure
data/IO) and tags/ui.py (FileTagAutocomplete, FieldRecorderTagger,
TemplateQuickButtons, TemplateManagerDialog) in Fase 7.
"""
from tags.templates import TemplateManager  # noqa: F401
from tags.ui import *  # noqa: F401,F403
