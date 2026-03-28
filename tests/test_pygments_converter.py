"""Tests for Pygments → TextAreaTheme converter.

Red tests: these should all FAIL before implementation because
the module `textual_code.pygments_theme_converter` does not exist yet.
"""

from textual_code.pygments_theme_converter import (
    get_all_pygments_theme_names,
    pygments_to_textarea_theme,
)

# ---------------------------------------------------------------------------
# Group 1: Theme name listing
# ---------------------------------------------------------------------------


def test_get_all_pygments_theme_names():
    """Should return a list of at least 49 Pygments style names."""
    names = get_all_pygments_theme_names()
    assert isinstance(names, list)
    assert len(names) >= 49
    assert "monokai" in names
    assert "solarized-dark" in names


# ---------------------------------------------------------------------------
# Group 2: Single theme conversion
# ---------------------------------------------------------------------------


def test_pygments_to_textarea_theme_returns_theme():
    """Should return a TextAreaTheme object."""
    from textual._text_area_theme import TextAreaTheme

    theme = pygments_to_textarea_theme("monokai")
    assert isinstance(theme, TextAreaTheme)
    assert theme.name == "monokai"


def test_theme_has_base_style_with_colors():
    """Converted theme must have foreground and background in base_style."""
    theme = pygments_to_textarea_theme("monokai")
    assert theme.base_style is not None
    assert theme.base_style.color is not None
    assert theme.base_style.bgcolor is not None


def test_theme_has_syntax_styles():
    """Converted theme must have at least 40 syntax style entries."""
    theme = pygments_to_textarea_theme("monokai")
    assert len(theme.syntax_styles) >= 40


def test_theme_has_gutter_style():
    """Converted theme must have a gutter style."""
    theme = pygments_to_textarea_theme("monokai")
    assert theme.gutter_style is not None


def test_theme_has_cursor_style():
    """Converted theme must have a cursor style."""
    theme = pygments_to_textarea_theme("monokai")
    assert theme.cursor_style is not None


def test_theme_has_selection_style():
    """Converted theme must have a selection style."""
    theme = pygments_to_textarea_theme("monokai")
    assert theme.selection_style is not None


# ---------------------------------------------------------------------------
# Group 3: Smoke test all styles
# ---------------------------------------------------------------------------


def test_all_styles_convert_without_error():
    """Every Pygments style should convert without raising an exception."""
    names = get_all_pygments_theme_names()
    for name in names:
        theme = pygments_to_textarea_theme(name)
        assert theme.name == name
        assert theme.base_style is not None
        assert theme.base_style.color is not None
        assert theme.base_style.bgcolor is not None


# ---------------------------------------------------------------------------
# Group 4: Caching
# ---------------------------------------------------------------------------


def test_conversion_is_cached():
    """Calling pygments_to_textarea_theme twice returns the same object."""
    theme1 = pygments_to_textarea_theme("monokai")
    theme2 = pygments_to_textarea_theme("monokai")
    assert theme1 is theme2


# ---------------------------------------------------------------------------
# Group 5: Integration — theme available in modals
# ---------------------------------------------------------------------------


def test_available_themes_includes_pygments():
    """AVAILABLE_SYNTAX_THEMES in modals should include Pygments themes."""
    from textual_code.modals import AVAILABLE_SYNTAX_THEMES

    assert "solarized-dark" in AVAILABLE_SYNTAX_THEMES
    assert "monokai" in AVAILABLE_SYNTAX_THEMES
    assert len(AVAILABLE_SYNTAX_THEMES) >= 49
