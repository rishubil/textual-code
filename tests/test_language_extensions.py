"""Tests for language detection via LANGUAGE_EXTENSIONS and LANGUAGE_FILENAMES."""

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor


# Group 1: LANGUAGE_EXTENSIONS new entries
@pytest.mark.parametrize(
    "ext,expected",
    [
        ("mjs", "javascript"),
        ("cjs", "javascript"),
        ("svg", "xml"),
        ("xhtml", "xml"),
        ("bash", "bash"),
    ],
)
def test_new_extension_in_dict(ext, expected):
    assert CodeEditor.LANGUAGE_EXTENSIONS.get(ext) == expected


# Group 2: LANGUAGE_FILENAMES dict entries
@pytest.mark.parametrize(
    "filename,expected",
    [
        (".bashrc", "bash"),
        (".bash_profile", "bash"),
        (".bash_logout", "bash"),
    ],
)
def test_filename_in_dict(filename, expected):
    assert CodeEditor.LANGUAGE_FILENAMES.get(filename) == expected


# Group 3: New extensions — integration tests
@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("module.mjs", "javascript"),
        ("bundle.cjs", "javascript"),
        ("icon.svg", "xml"),
        ("page.xhtml", "xml"),
        ("deploy.bash", "bash"),
    ],
)
async def test_new_extension_detected(workspace, filename, expected_lang):
    f = workspace / filename
    f.write_text("content")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


# Group 4: Filename-based detection — integration tests
@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        (".bashrc", "bash"),
        (".bash_profile", "bash"),
        (".bash_logout", "bash"),
    ],
)
async def test_filename_detected(workspace, filename, expected_lang):
    f = workspace / filename
    f.write_text("content")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == expected_lang


# Group 5: Existing extensions regression tests
@pytest.mark.parametrize(
    "ext,expected",
    [
        ("py", "python"),
        ("json", "json"),
        ("md", "markdown"),
        ("yaml", "yaml"),
        ("yml", "yaml"),
        ("toml", "toml"),
        ("rs", "rust"),
        ("js", "javascript"),
        ("go", "go"),
        ("sh", "bash"),
    ],
)
def test_existing_extensions_unchanged(ext, expected):
    assert CodeEditor.LANGUAGE_EXTENSIONS.get(ext) == expected


# Group 6: Filename takes priority / unknown file
async def test_filename_takes_priority_over_extension(workspace):
    """load_language_from_path checks filename before extension."""
    f = workspace / ".bashrc"
    f.write_text("export PATH=...")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language == "bash"


async def test_unknown_file_returns_none(workspace):
    """Unknown extension and filename -> language is None."""
    f = workspace / "unknown.xyz"
    f.write_text("content")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.language is None
