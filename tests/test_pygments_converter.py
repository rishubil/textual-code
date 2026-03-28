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


# ---------------------------------------------------------------------------
# Group 6: Hierarchical capture names get styles via prefix fallback
# ---------------------------------------------------------------------------


def test_hierarchical_keyword_captures_have_styles():
    """keyword.conditional, keyword.repeat etc. must inherit from keyword."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    # These hierarchical captures are used in real queries but not explicitly mapped
    assert "keyword.conditional" in styles, (
        "keyword.conditional should inherit from keyword"
    )
    assert "keyword.repeat" in styles, "keyword.repeat should inherit from keyword"
    assert "keyword.exception" in styles, (
        "keyword.exception should inherit from keyword"
    )
    assert "keyword.import" in styles, "keyword.import should inherit from keyword"
    assert "keyword.modifier" in styles, "keyword.modifier should inherit from keyword"
    assert "keyword.coroutine" in styles, (
        "keyword.coroutine should inherit from keyword"
    )
    # They should have the same color as the base keyword
    assert styles["keyword.conditional"].color == styles["keyword"].color
    assert styles["keyword.repeat"].color == styles["keyword"].color


def test_hierarchical_function_captures_have_styles():
    """function.method, function.method.call must inherit from function."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "function.method" in styles, "function.method should inherit from function"
    assert "function.method.call" in styles
    assert styles["function.method"].color == styles["function"].color


def test_hierarchical_variable_captures_have_styles():
    """variable.parameter, variable.member must inherit from variable."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "variable.parameter" in styles
    assert "variable.member" in styles
    assert styles["variable.parameter"].color == styles["variable"].color
    assert styles["variable.member"].color == styles["variable"].color


def test_hierarchical_string_captures_have_styles():
    """string.escape, string.regex must inherit from string."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "string.escape" in styles
    assert "string.regex" in styles


def test_hierarchical_comment_captures_have_styles():
    """comment.documentation must inherit from comment."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "comment.documentation" in styles
    assert styles["comment.documentation"].color == styles["comment"].color


def test_hierarchical_number_captures_have_styles():
    """number.float must inherit from number."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "number.float" in styles
    assert styles["number.float"].color == styles["number"].color


# ---------------------------------------------------------------------------
# Group 7: Legacy nvim-treesitter captures get styles
# ---------------------------------------------------------------------------


def test_legacy_conditional_capture_has_style():
    """@conditional (legacy) should map to keyword style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "conditional" in styles
    assert styles["conditional"].color == styles["keyword"].color


def test_legacy_repeat_capture_has_style():
    """@repeat (legacy) should map to keyword style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "repeat" in styles
    assert styles["repeat"].color == styles["keyword"].color


def test_legacy_exception_capture_has_style():
    """@exception (legacy) should map to keyword style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "exception" in styles


def test_legacy_include_capture_has_style():
    """@include (legacy) should map to keyword style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "include" in styles


def test_legacy_field_capture_has_style():
    """@field (legacy) should map to property/attribute style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "field" in styles
    assert styles["field"].color == styles["property"].color


def test_legacy_storageclass_capture_has_style():
    """@storageclass (legacy) should map to keyword style."""
    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles
    assert "storageclass" in styles


# ---------------------------------------------------------------------------
# Group 8: Pygments color accuracy — specific tokens must match originals
# ---------------------------------------------------------------------------


def _get_hex(style_color) -> str:
    """Extract lowercase hex color string from a Rich Color object."""
    assert style_color is not None
    assert style_color.triplet is not None
    return style_color.triplet.hex.lower()


def test_monokai_keyword_color_matches_pygments():
    """Monokai keyword color must be #66d9ef (from Pygments monokai style)."""
    from pygments.styles import get_style_by_name
    from pygments.token import Keyword

    pygments_style = get_style_by_name("monokai")
    expected_color = "#" + pygments_style.style_for_token(Keyword)["color"]

    theme = pygments_to_textarea_theme("monokai")
    assert _get_hex(theme.syntax_styles["keyword"].color) == expected_color.lower()


def test_monokai_string_color_matches_pygments():
    """Monokai string color must match Pygments."""
    from pygments.styles import get_style_by_name
    from pygments.token import String

    pygments_style = get_style_by_name("monokai")
    expected_color = "#" + pygments_style.style_for_token(String)["color"]

    theme = pygments_to_textarea_theme("monokai")
    assert _get_hex(theme.syntax_styles["string"].color) == expected_color.lower()


def test_monokai_function_color_matches_pygments():
    """Monokai function color must match Pygments Name.Function."""
    from pygments.styles import get_style_by_name
    from pygments.token import Name

    pygments_style = get_style_by_name("monokai")
    expected_color = "#" + pygments_style.style_for_token(Name.Function)["color"]

    theme = pygments_to_textarea_theme("monokai")
    assert _get_hex(theme.syntax_styles["function"].color) == expected_color.lower()


def test_solarized_dark_colors_match_pygments():
    """Solarized-dark theme colors must match Pygments style."""
    from pygments.styles import get_style_by_name
    from pygments.token import Comment, Keyword, String

    pygments_style = get_style_by_name("solarized-dark")
    theme = pygments_to_textarea_theme("solarized-dark")

    for token, capture in [
        (Keyword, "keyword"),
        (String, "string"),
        (Comment, "comment"),
    ]:
        expected = pygments_style.style_for_token(token)["color"]
        if expected:
            actual_hex = _get_hex(theme.syntax_styles[capture].color)
            assert actual_hex == f"#{expected.lower()}", (
                f"{capture}: expected #{expected}, got {actual_hex}"
            )


# ---------------------------------------------------------------------------
# Group 9: All used captures must have styles (comprehensive check)
# ---------------------------------------------------------------------------


def test_all_query_captures_have_styles():
    """Every capture name used in loaded queries should have a style in the theme.

    Captures starting with '_' or that are language-internal predicates are excluded.
    """
    import re

    from textual_code.widgets.code_editor import _CUSTOM_LANGUAGE_QUERIES

    # Collect all capture names from loaded queries
    all_captures: set[str] = set()
    for query in _CUSTOM_LANGUAGE_QUERIES.values():
        found = re.findall(r"@([\w.]+)", query)
        all_captures.update(found)

    theme = pygments_to_textarea_theme("monokai")
    styles = theme.syntax_styles

    # Filter to only meaningful captures (skip internal/predicate names)
    skip_prefixes = ("_", "spell", "nospell", "none", "conceal", "error.")
    meaningful = {
        c
        for c in all_captures
        if not any(c.startswith(p) for p in skip_prefixes)
        and "." not in c
        or c.split(".")[0]
        in {
            "keyword",
            "function",
            "variable",
            "string",
            "comment",
            "number",
            "type",
            "constant",
            "operator",
            "punctuation",
            "tag",
            "attribute",
            "property",
            "module",
            "namespace",
            "label",
            "text",
            "heading",
            "link",
            "markup",
        }
    }

    missing = {c for c in meaningful if c not in styles}
    # Allow some threshold — not every obscure capture needs a style
    # But the core ones must be there
    core_captures = {
        "keyword.conditional",
        "keyword.repeat",
        "keyword.import",
        "keyword.exception",
        "keyword.modifier",
        "function.method",
        "variable.parameter",
        "variable.member",
        "string.escape",
        "comment.documentation",
        "number.float",
        "type.definition",
        "conditional",
        "repeat",
        "include",
        "exception",
        "field",
    }
    missing_core = core_captures & missing
    assert not missing_core, f"Core captures missing from theme: {sorted(missing_core)}"
