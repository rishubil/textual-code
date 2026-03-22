import logging
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Keys that can appear in [editor] section
EDITOR_KEYS = {
    "indent_type",
    "indent_size",
    "line_ending",
    "encoding",
    "syntax_theme",
    "word_wrap",
    "ui_theme",
    "warn_line_ending",
    "show_hidden_files",
    "path_display_mode",
    "dim_gitignored",
    "dim_hidden_files",
    "show_git_status",
    "sidebar_width",
}

DEFAULT_EDITOR_SETTINGS: dict[str, str | int | bool] = {
    "indent_type": "spaces",
    "indent_size": 4,
    "line_ending": "lf",
    "encoding": "utf-8",
    "syntax_theme": "monokai",
    "word_wrap": True,
    "ui_theme": "textual-dark",
    "warn_line_ending": True,
    "show_hidden_files": True,
    "path_display_mode": "absolute",
    "dim_gitignored": True,
    "dim_hidden_files": False,
    "show_git_status": True,
    "sidebar_width": 28,
}


def get_user_config_path() -> Path:
    """Return the user-level config path (platform-aware).

    - Windows:        %APPDATA%\\textual-code\\settings.toml
    - Linux / macOS:  $XDG_CONFIG_HOME/textual-code/settings.toml
                      (defaults to ~/.config/textual-code/settings.toml)
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "textual-code" / "settings.toml"


def get_project_config_path(workspace_path: Path) -> Path:
    """Return {workspace}/.textual-code.toml."""
    return workspace_path / ".textual-code.toml"


def _load_toml_editor_section(path: Path) -> dict[str, str | int]:
    """Load [editor] section from a TOML file. Returns {} on missing/error."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return {k: v for k, v in data.get("editor", {}).items() if k in EDITOR_KEYS}
    except (FileNotFoundError, tomllib.TOMLDecodeError, PermissionError):
        return {}


def load_editor_settings(
    workspace_path: Path,
    user_config_path: Path | None = None,
) -> dict[str, str | int]:
    """Merge defaults <- user config <- project config and return result."""
    if user_config_path is None:
        user_config_path = get_user_config_path()
    settings: dict[str, str | int] = dict(DEFAULT_EDITOR_SETTINGS)
    settings.update(_load_toml_editor_section(user_config_path))
    settings.update(_load_toml_editor_section(get_project_config_path(workspace_path)))
    return settings


@dataclass
class ShortcutDisplayEntry:
    """Per-action display preferences for the command palette."""

    palette: bool | None = None


KEYBINDINGS_FILENAME = "keybindings.toml"


def get_keybindings_path(config_path: Path | None = None) -> Path:
    """Return the keybindings config path (same directory as settings.toml)."""
    base = config_path or get_user_config_path()
    return base.with_name(KEYBINDINGS_FILENAME)


def load_keybindings(config_path: Path | None = None) -> dict[str, str]:
    """Load custom keybindings. Returns {action_name: key_string}."""
    path = config_path or get_keybindings_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return {k: str(v) for k, v in data.get("bindings", {}).items()}
    except (tomllib.TOMLDecodeError, PermissionError):
        return {}


def load_shortcut_display(
    config_path: Path | None = None,
) -> dict[str, ShortcutDisplayEntry]:
    """Load shortcut display preferences from [display.*] sections.

    Returns {action_name: ShortcutDisplayEntry}. Returns {} on missing/error.
    """
    path = config_path or get_keybindings_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, PermissionError):
        return {}
    display_section = data.get("display", {})
    if not isinstance(display_section, dict):
        return {}
    result: dict[str, ShortcutDisplayEntry] = {}
    for action, values in display_section.items():
        if not isinstance(values, dict):
            continue
        palette = values.get("palette")
        if palette is not None and not isinstance(palette, bool):
            continue
        result[action] = ShortcutDisplayEntry(palette=palette)
    return result


def _serialize_display_section(display: dict[str, ShortcutDisplayEntry]) -> str:
    """Serialize display preferences to TOML [display.*] sections."""
    lines: list[str] = []
    for action in sorted(display):
        entry = display[action]
        lines.append(f"[display.{action}]")
        if entry.palette is not None:
            lines.append(f"palette = {str(entry.palette).lower()}")
        lines.append("")
    return "\n".join(lines)


def load_footer_order(config_path: Path | None = None) -> list[str] | None:
    """Load footer action order from [footer] section.

    Returns the ordered list of action names, or None if not configured.
    """
    path = config_path or get_keybindings_path()
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, PermissionError):
        return None
    footer_section = data.get("footer", {})
    if not isinstance(footer_section, dict):
        return None
    order = footer_section.get("order")
    if not isinstance(order, list):
        return None
    return [str(item) for item in order if isinstance(item, str)]


def save_keybindings_file(
    bindings: dict[str, str],
    display: dict[str, ShortcutDisplayEntry],
    config_path: Path | None = None,
    *,
    footer_order: list[str] | None = None,
) -> bool:
    """Persist [bindings], [display.*], and [footer] sections atomically."""
    path = config_path or get_keybindings_path()
    escaped = {k: v.replace('"', '\\"') for k, v in bindings.items()}
    sections = ["[bindings]"] + [f'{k} = "{v}"' for k, v in escaped.items()]
    sections.append("")
    sections.append(_serialize_display_section(display))
    if footer_order is not None:
        items = ", ".join(f'"{a}"' for a in footer_order)
        sections.append("[footer]")
        sections.append(f"order = [{items}]")
        sections.append("")
    return _safe_write_config(path, "\n".join(sections))


def save_keybindings(
    bindings: dict[str, str],
    config_path: Path | None = None,
) -> bool:
    """Persist keybindings, preserving [display] and [footer] sections."""
    path = config_path or get_keybindings_path()
    existing_display = load_shortcut_display(path)
    existing_footer = load_footer_order(path)
    return save_keybindings_file(
        bindings, existing_display, path, footer_order=existing_footer
    )


def _serialize_editor_settings(settings: dict[str, str | int | bool]) -> str:
    """Serialize editor settings to TOML [editor] section string."""
    lines = ["[editor]"]
    for key in sorted(settings):
        value = settings[key]
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n"


def _safe_write_config(path: Path, content: str) -> bool:
    """Write *content* to *path*, creating parent dirs. Returns False on I/O error."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError:
        logger.debug("Failed to write config to %s", path)
        return False
    return True


def save_user_editor_settings(
    settings: dict[str, str | int | bool],
    config_path: Path | None = None,
) -> bool:
    """Persist [editor] settings to the user config file. Returns False on I/O error."""
    if config_path is None:
        config_path = get_user_config_path()
    return _safe_write_config(config_path, _serialize_editor_settings(settings))


def save_project_editor_settings(
    settings: dict[str, str | int | bool],
    workspace_path: Path,
) -> bool:
    """Persist [editor] settings to the project config file.

    Returns False on I/O error.
    """
    config_path = get_project_config_path(workspace_path)
    return _safe_write_config(config_path, _serialize_editor_settings(settings))
