"""Tree-sitter grammar composition and custom language loading."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from tree_sitter import Language
    from tree_sitter_language_pack import SupportedLanguage

_log = logging.getLogger(__name__)

# Map custom language name -> highlight query string (loaded at import time)
_CUSTOM_LANGUAGE_QUERIES: dict[str, str] = {}
# Map custom language name -> tree-sitter Language object (loaded at import time)
_CUSTOM_LANGUAGES: dict[str, Language] = {}

_CUSTOM_GRAMMAR_NAMES = [
    "dockerfile",
    "typescript",
    "tsx",
    "c",
    "cpp",
    "ruby",
    "kotlin",
    "lua",
    "php",
    "make",
]

_GRAMMARS_DIR = Path(__file__).parent.parent / "grammars"

# Earlier entries have higher priority in tree-sitter pattern matching.
_GRAMMAR_COMPOSITION: dict[str, list[str]] = {}


def _resolve_highlight_query(
    name: str,
    visited: set[str] | None = None,
    *,
    composition: dict[str, list[str]] | None = None,
    grammars_dir: Path | None = None,
) -> str:
    """Resolve a highlight query, recursively composing from composition.json.

    Raises:
        ValueError: If a circular reference is detected.
        KeyError: If the language is not defined in the composition map.
    """
    if composition is None:
        composition = _GRAMMAR_COMPOSITION
    if grammars_dir is None:
        grammars_dir = _GRAMMARS_DIR
    if visited is None:
        visited = set()
    if name in visited:
        raise ValueError(f"Circular reference in grammar composition: {name}")
    visited.add(name)

    if name not in composition:
        raise KeyError(f"Language '{name}' not found in composition map")

    parts = []
    for entry in composition[name]:
        if entry.startswith("@"):
            # .copy() allows diamond-shaped deps (e.g. TS and TSX both @javascript)
            parts.append(
                _resolve_highlight_query(
                    entry[1:],
                    visited.copy(),
                    composition=composition,
                    grammars_dir=grammars_dir,
                )
            )
        else:
            parts.append((grammars_dir / entry).read_text(encoding="utf-8"))
    return "\n".join(parts)


try:
    from tree_sitter_language_pack import get_language as _get_ts_language

    _GRAMMAR_COMPOSITION = json.loads(
        (_GRAMMARS_DIR / "composition.json").read_text(encoding="utf-8")
    )
    for _lang_name in _CUSTOM_GRAMMAR_NAMES:
        try:
            _query = _resolve_highlight_query(_lang_name)
            _lang_obj = _get_ts_language(cast("SupportedLanguage", _lang_name))
            _CUSTOM_LANGUAGE_QUERIES[_lang_name] = _query
            _CUSTOM_LANGUAGES[_lang_name] = _lang_obj
        except Exception as _e:
            _log.warning("Failed to load custom language %s: %s", _lang_name, _e)
except ImportError:
    _log.warning("tree-sitter-language-pack not available; custom languages disabled")
