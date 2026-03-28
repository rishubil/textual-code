"""Convert Pygments styles to Textual TextAreaTheme objects at runtime.

Pygments is already a transitive dependency of Textual (via Rich), so no
new dependency is introduced.  This module provides:

- ``get_all_pygments_theme_names()`` — sorted list of available style names
- ``pygments_to_textarea_theme(name)`` — cached conversion to TextAreaTheme
"""

from __future__ import annotations

from functools import lru_cache

from pygments.styles import get_all_styles, get_style_by_name
from pygments.token import (
    Comment,
    Error,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Token,
)
from rich.style import Style
from textual._text_area_theme import TextAreaTheme

# ── Pygments token → tree-sitter capture name mapping ──────────────────────

# Each Pygments token maps to one or more tree-sitter capture names used by
# TextAreaTheme.syntax_styles.  When a Pygments token yields a non-trivial
# style (has color, bold, italic, or underline), the style is applied to
# every listed capture name.

_TOKEN_TO_CAPTURES: list[tuple[object, list[str]]] = [
    # Comments
    (Comment, ["comment"]),
    (Comment.Preproc, ["keyword.directive"]),
    # Strings
    (String, ["string", "string.documentation"]),
    (String.Regex, ["regex.punctuation.bracket", "regex.operator"]),
    (String.Escape, ["string.special", "punctuation.special"]),
    # Numbers
    (Number, ["number", "float"]),
    # Keywords
    (Keyword, ["keyword", "keyword.return", "keyword.operator"]),
    (Keyword.Declaration, ["keyword.function"]),
    (Keyword.Type, ["type.builtin"]),
    (Keyword.Constant, ["constant.builtin", "boolean"]),
    # Names
    (Name.Function, ["function", "function.call", "method", "method.call"]),
    (Name.Class, ["type", "type.class", "constructor"]),
    (Name.Builtin, ["function.builtin"]),
    (Name.Variable, ["variable", "variable.builtin", "parameter"]),
    (Name.Attribute, ["attribute", "property"]),
    (Name.Tag, ["tag"]),
    (Name.Decorator, ["function.macro"]),
    (Name.Namespace, ["module", "namespace"]),
    (Name.Label, ["label", "json.label", "yaml.field", "toml.type"]),
    # Operators / Punctuation
    (Operator, ["operator"]),
    (Punctuation, ["punctuation.bracket", "punctuation.delimiter"]),
    # Literal
    (Literal, ["constant"]),
    # Errors
    (Error, ["html.end_tag_error"]),
]


def _hex_color(color_str: str | None) -> str | None:
    """Normalise a Pygments hex colour (e.g. ``'ab1234'``) to ``'#ab1234'``."""
    if not color_str:
        return None
    return f"#{color_str}" if not color_str.startswith("#") else color_str


def _derive_color(base: str, factor: float) -> str:
    """Lighten or darken a hex colour by *factor* (>1 = lighten, <1 = darken)."""
    base = base.lstrip("#")
    r, g, b = int(base[:2], 16), int(base[2:4], 16), int(base[4:6], 16)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_all_pygments_theme_names() -> list[str]:
    """Return a sorted list of all available Pygments style names."""
    return sorted(get_all_styles())


@lru_cache(maxsize=64)
def pygments_to_textarea_theme(style_name: str) -> TextAreaTheme:
    """Convert a Pygments style to a :class:`TextAreaTheme`.

    Results are cached so repeated calls with the same name return the same
    object.
    """
    pygments_style = get_style_by_name(style_name)

    # Background and foreground from the Pygments style
    bg_color = _hex_color(pygments_style.background_color)
    # Pygments doesn't have an explicit foreground — derive from Token base
    token_style = pygments_style.style_for_token(Token)
    fg_color = _hex_color(token_style["color"]) or (
        "#f8f8f2" if _is_dark(bg_color) else "#24292e"
    )
    if not bg_color:
        bg_color = "#272822"

    base_style = Style(color=fg_color, bgcolor=bg_color)

    # Derive UI styles from background
    is_dark = _is_dark(bg_color)
    gutter_factor = 1.3 if is_dark else 0.85
    cursor_bg = "#ffffff" if is_dark else "#000000"
    cursor_fg = "#000000" if is_dark else "#ffffff"
    sel_bg = _derive_color(bg_color, 1.5 if is_dark else 0.8)

    gutter_style = Style(
        color=_derive_color(fg_color, 0.5),
        bgcolor=_derive_color(bg_color, gutter_factor),
    )
    cursor_style = Style(color=cursor_fg, bgcolor=cursor_bg)
    cursor_line_style = Style(bgcolor=_derive_color(bg_color, 1.2 if is_dark else 0.95))
    cursor_line_gutter_style = Style(
        color=fg_color,
        bgcolor=_derive_color(bg_color, 1.3 if is_dark else 0.9),
    )
    bracket_matching_style = Style(
        bold=True,
        underline=True,
    )
    selection_style = Style(bgcolor=sel_bg)

    # Build syntax_styles from token mapping
    syntax_styles: dict[str, Style] = {}

    for token_type, captures in _TOKEN_TO_CAPTURES:
        ts = pygments_style.style_for_token(token_type)
        color = _hex_color(ts["color"])
        if not color:
            continue
        style = Style(
            color=color,
            bold=ts.get("bold", False) or False,
            italic=ts.get("italic", False) or False,
            underline=ts.get("underline", False) or False,
        )
        for capture in captures:
            syntax_styles[capture] = style

    # Markdown captures — derive from keyword/string/comment styles
    kw_style = pygments_style.style_for_token(Keyword)
    str_style = pygments_style.style_for_token(String)
    cmt_style = pygments_style.style_for_token(Comment)

    heading_color = _hex_color(kw_style["color"]) or fg_color
    link_color = _hex_color(str_style["color"]) or fg_color
    code_color = _hex_color(cmt_style["color"]) or fg_color

    # Textual-style captures (used by Textual's built-in themes)
    syntax_styles["heading"] = Style(color=heading_color, bold=True)
    syntax_styles["heading.marker"] = Style(color=heading_color, bold=True)
    syntax_styles["bold"] = Style(bold=True)
    syntax_styles["italic"] = Style(italic=True)
    syntax_styles["strikethrough"] = Style(strike=True)
    syntax_styles["link.label"] = Style(color=link_color)
    syntax_styles["link.uri"] = Style(color=link_color, underline=True)
    syntax_styles["list.marker"] = Style(color=heading_color)
    syntax_styles["inline_code"] = Style(color=code_color)
    # nvim-treesitter-style captures (used by tslp bundled queries)
    syntax_styles["text.title"] = Style(color=heading_color, bold=True)
    syntax_styles["text.literal"] = Style(color=code_color)
    syntax_styles["text.emphasis"] = Style(italic=True)
    syntax_styles["text.strong"] = Style(bold=True)
    syntax_styles["text.uri"] = Style(color=link_color, underline=True)
    syntax_styles["text.reference"] = Style(color=link_color)
    syntax_styles["text.note"] = Style(color=code_color)
    syntax_styles["text.warning"] = Style(color=heading_color)
    syntax_styles["text.danger"] = Style(color=heading_color, bold=True)

    return TextAreaTheme(
        name=style_name,
        base_style=base_style,
        gutter_style=gutter_style,
        cursor_style=cursor_style,
        cursor_line_style=cursor_line_style,
        cursor_line_gutter_style=cursor_line_gutter_style,
        bracket_matching_style=bracket_matching_style,
        selection_style=selection_style,
        syntax_styles=syntax_styles,
    )


def _is_dark(hex_color: str | None) -> bool:
    """Return True if a hex colour is perceptually dark."""
    if not hex_color:
        return True
    c = hex_color.lstrip("#")
    if len(c) < 6:
        return True
    r, g, b = int(c[:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    # Perceived luminance
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128
