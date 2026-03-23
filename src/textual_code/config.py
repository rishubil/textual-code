import logging
import os
import sys
import tomllib
from dataclasses import dataclass, field
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
    "show_indentation_guides",
    "render_whitespace",
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
    "show_indentation_guides": True,
    "render_whitespace": "none",
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


def _report_config_error(
    path: Path,
    exception: Exception,
    label: str,
    error_type: str,
    warnings: list[str] | None,
) -> None:
    """Log a config loading error and optionally append a user-facing warning."""
    logger.warning("Failed to load %s: %s", path, exception)
    if warnings is not None:
        warnings.append(f"{label}: {error_type}")


def _load_toml_editor_section(
    path: Path,
    warnings: list[str] | None = None,
    label: str = "Config",
) -> dict[str, str | int]:
    """Load [editor] section from a TOML file. Returns {} on missing/error."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return {k: v for k, v in data.get("editor", {}).items() if k in EDITOR_KEYS}
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        _report_config_error(path, e, label, "parse error", warnings)
        return {}
    except PermissionError as e:
        _report_config_error(path, e, label, "permission denied", warnings)
        return {}


def load_editor_settings(
    workspace_path: Path,
    user_config_path: Path | None = None,
    warnings: list[str] | None = None,
) -> dict[str, str | int]:
    """Merge defaults <- user config <- project config and return result."""
    if user_config_path is None:
        user_config_path = get_user_config_path()
    settings: dict[str, str | int] = dict(DEFAULT_EDITOR_SETTINGS)
    settings.update(
        _load_toml_editor_section(user_config_path, warnings, "User settings")
    )
    settings.update(
        _load_toml_editor_section(
            get_project_config_path(workspace_path), warnings, "Project settings"
        )
    )
    return settings


@dataclass
class ShortcutDisplayEntry:
    """Per-action display preferences for the command palette."""

    palette: bool | None = None


KNOWN_AREAS = ("editor", "explorer", "search", "image_preview", "markdown_preview")


@dataclass
class FooterOrders:
    """Per-area footer shortcut order configuration."""

    areas: dict[str, list[str]] = field(default_factory=dict)

    def for_area(self, area: str) -> list[str] | None:
        """Return the order for *area*, or None if not configured."""
        order = self.areas.get(area)
        return list(order) if order is not None else None

    def set_area(self, area: str, order: list[str]) -> None:
        """Set the order for *area*."""
        self.areas[area] = order


KEYBINDINGS_FILENAME = "keybindings.toml"


def get_keybindings_path(config_path: Path | None = None) -> Path:
    """Return the keybindings config path (same directory as settings.toml)."""
    base = config_path or get_user_config_path()
    return base.with_name(KEYBINDINGS_FILENAME)


def load_keybindings(
    config_path: Path | None = None,
    warnings: list[str] | None = None,
) -> dict[str, str]:
    """Load custom keybindings. Returns {action_name: key_string}."""
    path = config_path or get_keybindings_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return {k: str(v) for k, v in data.get("bindings", {}).items()}
    except tomllib.TOMLDecodeError as e:
        _report_config_error(path, e, "Keybindings", "parse error", warnings)
        return {}
    except PermissionError as e:
        _report_config_error(path, e, "Keybindings", "permission denied", warnings)
        return {}


def load_shortcut_display(
    config_path: Path | None = None,
    warnings: list[str] | None = None,
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
    except tomllib.TOMLDecodeError as e:
        _report_config_error(path, e, "Keybindings", "parse error", warnings)
        return {}
    except PermissionError as e:
        _report_config_error(path, e, "Keybindings", "permission denied", warnings)
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


def load_footer_orders(
    config_path: Path | None = None,
    warnings: list[str] | None = None,
) -> FooterOrders:
    """Load per-area footer orders from [footer.<area>] sections.

    Falls back: legacy [footer] order → editor area migration.
    Returns FooterOrders (may have empty areas dict if nothing is configured).
    """
    path = config_path or get_keybindings_path()
    if not path.exists():
        return FooterOrders()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        _report_config_error(path, e, "Keybindings", "parse error", warnings)
        return FooterOrders()
    except PermissionError as e:
        _report_config_error(path, e, "Keybindings", "permission denied", warnings)
        return FooterOrders()
    footer_section = data.get("footer", {})
    if not isinstance(footer_section, dict):
        return FooterOrders()

    areas: dict[str, list[str]] = {}
    for area in KNOWN_AREAS:
        area_data = footer_section.get(area)
        if isinstance(area_data, dict):
            order = area_data.get("order")
            if isinstance(order, list):
                areas[area] = [str(item) for item in order if isinstance(item, str)]

    # Legacy migration: [footer] order → editor
    if "editor" not in areas:
        legacy_order = footer_section.get("order")
        if isinstance(legacy_order, list):
            areas["editor"] = [
                str(item) for item in legacy_order if isinstance(item, str)
            ]

    return FooterOrders(areas=areas)


def save_keybindings_file(
    bindings: dict[str, str],
    display: dict[str, ShortcutDisplayEntry],
    config_path: Path | None = None,
    *,
    footer_orders: FooterOrders | None = None,
) -> bool:
    """Persist [bindings], [display.*], and [footer.*] sections atomically."""
    path = config_path or get_keybindings_path()
    escaped = {k: v.replace('"', '\\"') for k, v in bindings.items()}
    sections = ["[bindings]"] + [f'{k} = "{v}"' for k, v in escaped.items()]
    sections.append("")
    sections.append(_serialize_display_section(display))
    if footer_orders is not None:
        for area in KNOWN_AREAS:
            order = footer_orders.areas.get(area)
            if order is not None:
                items = ", ".join(f'"{a}"' for a in order)
                sections.append(f"[footer.{area}]")
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
    existing_footer = load_footer_orders(path)
    return save_keybindings_file(
        bindings, existing_display, path, footer_orders=existing_footer
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
