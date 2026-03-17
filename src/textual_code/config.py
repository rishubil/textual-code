import os
import sys
import tomllib
from pathlib import Path

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


def save_keybindings(
    bindings: dict[str, str],
    config_path: Path | None = None,
) -> None:
    """Persist custom keybindings to a TOML file."""
    path = config_path or get_keybindings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    escaped = {k: v.replace('"', '\\"') for k, v in bindings.items()}
    lines = ["[bindings]"] + [f'{k} = "{v}"' for k, v in escaped.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def save_user_editor_settings(
    settings: dict[str, str | int | bool],
    config_path: Path | None = None,
) -> None:
    """Persist [editor] settings to the user config file."""
    if config_path is None:
        config_path = get_user_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_serialize_editor_settings(settings), encoding="utf-8")


def save_project_editor_settings(
    settings: dict[str, str | int | bool],
    workspace_path: Path,
) -> None:
    """Persist [editor] settings to the project config file."""
    config_path = get_project_config_path(workspace_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_serialize_editor_settings(settings), encoding="utf-8")
