# 설정 가이드 (Settings Guide)

Textual Code stores settings in TOML files. There are two levels of configuration:
user-level (applies to all workspaces) and project-level (applies to one workspace only).

## Config File Locations: platform-specific paths

### User settings file

| Platform | Path |
|----------|------|
| Linux / macOS | `$XDG_CONFIG_HOME/textual-code/settings.toml` (defaults to `~/.config/textual-code/settings.toml`) |
| Windows | `%APPDATA%\textual-code\settings.toml` |

Open from the editor: **Command Palette → "Open user settings"**

### Project settings file

```
{workspace}/.textual-code.toml
```

Open from the editor: **Command Palette → "Open project settings"**

### Keybindings file

Stored in the same directory as the user settings file:

```
~/.config/textual-code/keybindings.toml   (Linux / macOS)
%APPDATA%\textual-code\keybindings.toml   (Windows)
```

Access via **F1** or **Command Palette → "Show keyboard shortcuts"**.

## Settings Priority: defaults < user config < project config

Settings are merged in this order — later sources override earlier ones:

1. **Hardcoded defaults** (built into the app)
2. **User config** (`~/.config/textual-code/settings.toml`)
3. **Project config** (`{workspace}/.textual-code.toml`)

This means a project config can override a user config for a specific workspace,
while the user config applies everywhere else.

## Editor Settings: [editor] section keys

All editor settings go under the `[editor]` TOML table.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `indent_type` | string | `"spaces"` | `"spaces"` or `"tabs"` |
| `indent_size` | integer | `4` | Number of spaces per indent level |
| `line_ending` | string | `"lf"` | `"lf"`, `"crlf"`, or `"cr"` |
| `encoding` | string | `"utf-8"` | `"utf-8"`, `"utf-8-bom"`, `"utf-16"`, or `"latin-1"` |
| `syntax_theme` | string | `"monokai"` | Syntax highlighting theme (e.g. `"dracula"`, `"github-dark"`) |
| `word_wrap` | boolean | `true` | Wrap long lines at the editor boundary |
| `ui_theme` | string | `"textual-dark"` | UI colour theme: `"textual-dark"` or `"textual-light"` |
| `warn_line_ending` | boolean | `true` | Show warning toast when file uses non-LF line endings (CRLF, CR) |

### Example: user settings file

```toml
[editor]
indent_type = "spaces"
indent_size = 2
line_ending = "lf"
encoding = "utf-8"
syntax_theme = "dracula"
word_wrap = true
ui_theme = "textual-dark"
warn_line_ending = true
```

### Example: project settings file (override only what differs)

```toml
[editor]
indent_size = 4
word_wrap = false
```

## Keybindings Customization: [bindings] section

Custom keybindings are stored under the `[bindings]` TOML table, keyed by action name.

```toml
[bindings]
save_file = "ctrl+s"
find = "ctrl+f"
toggle_sidebar = "ctrl+b"
```

### How to rebind a key

1. Press **F1** (or open Command Palette → "Show keyboard shortcuts")
2. Select the action you want to rebind
3. Press the new key combination
4. The binding is saved immediately; restart the app to apply

### Warning: restart required

Custom keybindings take effect after restarting Textual Code.
The app shows a notification: *"Shortcut saved. Restart to apply changes."*

### Finding action names

Action names shown in the F1 shortcuts screen match the keys used in `keybindings.toml`.
For example, the action displayed as `save_file` maps to the key `save_file` in the TOML file.
