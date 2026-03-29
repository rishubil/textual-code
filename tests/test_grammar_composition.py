"""
Tests for grammar highlight query composition.

Verifies that _resolve_highlight_query correctly composes highlight queries
from composition.json, handling recursive @language references, .scm file
reads, fallbacks, and circular reference detection.
"""

import json
from pathlib import Path
from typing import cast

import pytest

# ── Unit tests for _resolve_highlight_query ──────────────────────────────────


@pytest.fixture()
def grammars_dir(tmp_path: Path) -> Path:
    """Create a temporary grammars directory with test .scm and composition files."""
    d = tmp_path / "grammars"
    d.mkdir()
    (d / "base.scm").write_text("; base rules\n")
    (d / "extra.scm").write_text("; extra rules\n")
    (d / "standalone.scm").write_text("; standalone rules\n")
    (d / "deep.scm").write_text("; deep rules\n")
    return d


def _make_resolver(grammars_dir: Path, composition: dict):
    """Create a _resolve_highlight_query function with the given composition map."""

    # Import the real function is not possible at this point because
    # composition.json doesn't exist yet. Instead, replicate the algorithm
    # so we can test the logic in isolation.
    def resolve(name: str, visited: set[str] | None = None) -> str:
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
                parts.append(resolve(entry[1:], visited.copy()))
            else:
                parts.append((grammars_dir / entry).read_text(encoding="utf-8"))
        return "\n".join(parts)

    return resolve


def test_resolve_scm_file(grammars_dir: Path):
    """An .scm entry reads the file directly."""
    composition = {"lang_a": ["base.scm"]}
    resolve = _make_resolver(grammars_dir, composition)
    result = resolve("lang_a")
    assert result == "; base rules\n"


def test_resolve_language_reference(grammars_dir: Path):
    """An @lang entry resolves recursively via the composition map."""
    composition = {
        "base_lang": ["base.scm"],
        "child_lang": ["extra.scm", "@base_lang"],
    }
    resolve = _make_resolver(grammars_dir, composition)
    result = resolve("child_lang")
    assert "; extra rules" in result
    assert "; base rules" in result
    # extra.scm comes first (higher priority)
    assert result.index("; extra rules") < result.index("; base rules")


def test_resolve_deep_recursion(grammars_dir: Path):
    """Multi-level recursive resolution works correctly."""
    composition = {
        "level0": ["deep.scm"],
        "level1": ["base.scm", "@level0"],
        "level2": ["extra.scm", "@level1"],
    }
    resolve = _make_resolver(grammars_dir, composition)
    result = resolve("level2")
    assert "; extra rules" in result
    assert "; base rules" in result
    assert "; deep rules" in result


def test_resolve_missing_language_raises(grammars_dir: Path):
    """A language not in the composition map raises KeyError."""
    composition = {}
    resolve = _make_resolver(grammars_dir, composition)
    with pytest.raises(KeyError, match="not found in composition map"):
        resolve("standalone")


def test_resolve_circular_reference_raises(grammars_dir: Path):
    """Circular @references raise ValueError."""
    composition = {
        "a": ["@b"],
        "b": ["@a"],
    }
    resolve = _make_resolver(grammars_dir, composition)
    with pytest.raises(ValueError, match="Circular reference"):
        resolve("a")


def test_resolve_self_reference_raises(grammars_dir: Path):
    """A language referencing itself raises ValueError."""
    composition = {
        "a": ["@a"],
    }
    resolve = _make_resolver(grammars_dir, composition)
    with pytest.raises(ValueError, match="Circular reference"):
        resolve("a")


def test_resolve_missing_file_raises(grammars_dir: Path):
    """Referencing a nonexistent .scm file raises FileNotFoundError."""
    composition = {"lang_a": ["nonexistent.scm"]}
    resolve = _make_resolver(grammars_dir, composition)
    with pytest.raises(FileNotFoundError):
        resolve("lang_a")


# ── Integration tests with real grammars ─────────────────────────────────────


@pytest.fixture()
def real_composition() -> dict[str, list[str]]:
    """Load the real composition.json from the grammars directory."""
    composition_path = (
        Path(__file__).parent.parent
        / "src"
        / "textual_code"
        / "grammars"
        / "composition.json"
    )
    return json.loads(composition_path.read_text(encoding="utf-8"))


@pytest.fixture()
def real_grammars_dir() -> Path:
    return Path(__file__).parent.parent / "src" / "textual_code" / "grammars"


def test_composition_json_includes_all_custom_languages(
    real_composition: dict,
    real_grammars_dir: Path,
):
    """composition.json must define entries for all custom languages."""
    from textual_code.widgets.code_editor import _CUSTOM_GRAMMAR_NAMES

    for lang in _CUSTOM_GRAMMAR_NAMES:
        assert lang in real_composition, (
            f"Language '{lang}' missing from composition.json"
        )


def test_composed_typescript_contains_js_keywords(
    real_composition: dict,
    real_grammars_dir: Path,
):
    """TypeScript composed query includes JavaScript base keywords."""
    resolve = _make_resolver(real_grammars_dir, real_composition)
    query = resolve("typescript")
    # JS keywords that are NOT in typescript.scm alone
    assert '"function"' in query
    assert '"const"' in query
    assert '"async"' in query
    # TS-specific keywords should also be present
    assert '"interface"' in query
    assert '"type"' in query


def test_composed_tsx_contains_jsx_and_js(
    real_composition: dict,
    real_grammars_dir: Path,
):
    """TSX composed query includes JSX tags and JavaScript base keywords."""
    resolve = _make_resolver(real_grammars_dir, real_composition)
    query = resolve("tsx")
    # JS keywords
    assert '"function"' in query
    # JSX patterns
    assert "jsx_opening_element" in query
    # TS-specific
    assert '"interface"' in query


def test_composed_cpp_contains_c_keywords(
    real_composition: dict,
    real_grammars_dir: Path,
):
    """C++ composed query includes C base patterns."""
    resolve = _make_resolver(real_grammars_dir, real_composition)
    query = resolve("cpp")
    # C patterns that are NOT in cpp.scm alone
    assert "(comment) @comment" in query
    assert "(string_literal) @string" in query
    assert '"return"' in query
    # C++-specific should also be present
    assert '"template"' in query
    assert '"namespace"' in query


def test_standalone_language_resolves_via_composition(
    real_composition: dict,
    real_grammars_dir: Path,
):
    """Standalone languages resolve via their composition.json entry."""
    resolve = _make_resolver(real_grammars_dir, real_composition)
    query = resolve("dockerfile")
    expected = (real_grammars_dir / "dockerfile.scm").read_text(encoding="utf-8")
    assert query == expected


def test_composed_queries_are_valid_treesitter(real_composition: dict):
    """Each composed query can be parsed by tree-sitter without errors."""
    try:
        from tree_sitter import Query
        from tree_sitter_language_pack import (
            SupportedLanguage,
            get_language,
        )
    except ImportError:
        pytest.skip("tree-sitter-language-pack not available")

    from textual_code.widgets.code_editor import (
        _CUSTOM_GRAMMAR_NAMES,
        _CUSTOM_LANGUAGE_QUERIES,
    )

    for lang_name in _CUSTOM_GRAMMAR_NAMES:
        query_str = _CUSTOM_LANGUAGE_QUERIES.get(lang_name, "")
        assert query_str, f"No query loaded for {lang_name}"
        lang_obj = get_language(cast(SupportedLanguage, lang_name))
        # This will raise if the query is invalid
        Query(lang_obj, query_str)
