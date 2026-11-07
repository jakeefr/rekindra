"""Standalone source-evidence index. See docs/evidence/README.md."""
from ._dossier import build_dossier
from ._search import search_dossier

__all__ = ['build_dossier', 'search_dossier']
