"""Standalone, read-only source intake. See docs/intake/README.md."""
from ._archive import inspect_archive
from ._text import inspect_text

__all__ = ['inspect_archive', 'inspect_text']
