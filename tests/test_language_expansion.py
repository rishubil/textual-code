"""Tests for expanded language support via tslp get_highlights_query.

Red tests: these should all FAIL before implementation because
the current code only loads 10 custom languages from .scm files,
not the full set from get_highlights_query().
"""

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import (
    _CUSTOM_LANGUAGE_QUERIES,
    _CUSTOM_LANGUAGES,
    CodeEditor,
)

# ---------------------------------------------------------------------------
# Group 1: Many more languages should be loaded
# ---------------------------------------------------------------------------


def test_custom_languages_count():
    """After upgrade, _CUSTOM_LANGUAGES should have far more than the old 10."""
    assert len(_CUSTOM_LANGUAGES) > 100


def test_custom_language_queries_count():
    """After upgrade, _CUSTOM_LANGUAGE_QUERIES should match _CUSTOM_LANGUAGES."""
    assert len(_CUSTOM_LANGUAGE_QUERIES) > 100
    assert set(_CUSTOM_LANGUAGE_QUERIES.keys()) == set(_CUSTOM_LANGUAGES.keys())


# ---------------------------------------------------------------------------
# Group 2: Specific languages that should be available
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lang",
    [
        # Previously built-in via textual[syntax]
        "python",
        "javascript",
        "rust",
        "go",
        "c",
        "cpp",
        "java",
        "ruby",
        "kotlin",
        "lua",
        "bash",
        "html",
        "css",
        "json",
        "yaml",
        "toml",
        "markdown",
        "dockerfile",
        "sql",
        "make",
        "regex",
        # Previously via .scm files — now via tslp or fallback .scm
        "typescript",
        "tsx",
        "php",
        # New languages via tslp get_highlights_query
        "scala",
        "swift",
        "r",
        "perl",
        "haskell",
        "elixir",
        "erlang",
        "zig",
        "dart",
        "julia",
        "nix",
        "gleam",
        "clojure",
        "elm",
        "fortran",
    ],
)
def test_language_has_query(lang):
    """Each language should have a highlight query loaded."""
    assert lang in _CUSTOM_LANGUAGE_QUERIES, f"{lang} not in _CUSTOM_LANGUAGE_QUERIES"
    assert lang in _CUSTOM_LANGUAGES, f"{lang} not in _CUSTOM_LANGUAGES"
    assert len(_CUSTOM_LANGUAGE_QUERIES[lang]) > 0


# ---------------------------------------------------------------------------
# Group 3: LANGUAGE_EXTENSIONS expanded
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ext,expected",
    [
        # New extensions that should be added
        ("scala", "scala"),
        ("sc", "scala"),
        ("swift", "swift"),
        ("r", "r"),
        ("R", "r"),
        ("pl", "perl"),
        ("pm", "perl"),
        ("hs", "haskell"),
        ("ex", "elixir"),
        ("exs", "elixir"),
        ("erl", "erlang"),
        ("zig", "zig"),
        ("dart", "dart"),
        ("jl", "julia"),
        ("nix", "nix"),
        ("clj", "clojure"),
        ("elm", "elm"),
        ("f90", "fortran"),
    ],
)
def test_new_language_extensions(ext, expected):
    """New file extensions should map to expanded languages."""
    assert CodeEditor.LANGUAGE_EXTENSIONS.get(ext) == expected


# ---------------------------------------------------------------------------
# Group 4: Integration — new language detected from file extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("app.scala", "scala"),
        ("main.swift", "swift"),
        ("analysis.r", "r"),
        ("script.pl", "perl"),
        ("Module.hs", "haskell"),
        ("server.ex", "elixir"),
        ("gen_server.erl", "erlang"),
        ("main.zig", "zig"),
        ("app.dart", "dart"),
    ],
)
async def test_new_language_detected_from_file(workspace, filename, expected_lang):
    """Opening a file with a new extension should detect the correct language."""
    f = workspace / filename
    f.write_text("content")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


# ---------------------------------------------------------------------------
# Group 5: Old .scm-based languages still work (regression)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("Dockerfile", "dockerfile"),
        ("file.ts", "typescript"),
        ("file.tsx", "tsx"),
        ("file.c", "c"),
        ("file.cpp", "cpp"),
        ("file.rb", "ruby"),
        ("file.kt", "kotlin"),
        ("file.lua", "lua"),
        ("file.php", "php"),
        ("Makefile", "make"),
    ],
)
async def test_old_custom_languages_still_work(workspace, filename, expected_lang):
    """Languages that used to load from .scm files should still work."""
    f = workspace / filename
    f.write_text("content")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


# ---------------------------------------------------------------------------
# Group 6: watch_language always registers (no available_languages check)
# ---------------------------------------------------------------------------


async def test_custom_language_overrides_builtin(workspace):
    """Registration should happen even if in available_languages."""
    f = workspace / "test.py"
    f.write_text("print('hello')")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Python should be registered with our custom query, not the built-in
        assert "python" in _CUSTOM_LANGUAGES
        assert editor.language == "python"
