# Settings Guide

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

## Settings Priority: defaults < user/project config < auto-detection < .editorconfig

App settings are merged in this order — later sources override earlier ones:

1. **Hardcoded defaults** (built into the app)
2. **User config** (`~/.config/textual-code/settings.toml`)
3. **Project config** (`{workspace}/.textual-code.toml`)

This means a project config can override a user config for a specific workspace,
while the user config applies everywhere else.

### When opening an existing file

Per-file properties have additional sources beyond app settings:

1. **File auto-detection** — `encoding` is detected from file content (BOM, UTF-8 decode,
   charset-normalizer), and `line_ending` is detected from line break characters.
2. **`.editorconfig`** — overrides auto-detected values and defaults for supported properties.
   See [EditorConfig in config.md](features/config.md#editorconfig-editorconfig-discovery-glob-matching-property-application-auto-reload) for full details on discovery, glob matching, and property application.

App settings (`word_wrap`, `syntax_theme`, `ui_theme`, etc.) still apply regardless of
EditorConfig.

### When creating a new file

Only app settings apply. There is no file content to auto-detect from and no file path
for EditorConfig matching.

### Property source reference

| Setting | App config | Auto-detection | EditorConfig |
|---------|:----------:|:--------------:|:------------:|
| `indent_type` / `indent_size` | new files only | — | yes |
| `encoding` | new files only | yes | yes |
| `line_ending` | new files only | yes | yes |
| `trim_trailing_whitespace` | — | — | yes |
| `insert_final_newline` | — | — | yes |
| `word_wrap`, `syntax_theme`, `ui_theme`, `warn_line_ending`, `show_hidden_files`, `dim_gitignored`, `dim_hidden_files`, `show_git_status`, `path_display_mode`, `sidebar_width` | always | — | — |

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
| `warn_line_ending` | boolean | `true` | Show warning toast when copying/cutting/pasting multiline text in non-LF files |
| `show_hidden_files` | boolean | `true` | Show dotfiles and dotfolders in the Explorer sidebar |
| `dim_gitignored` | boolean | `true` | Dim files matching .gitignore patterns in the Explorer sidebar |
| `dim_hidden_files` | boolean | `false` | Dim dotfiles and dotfolders in the Explorer sidebar |
| `show_git_status` | boolean | `true` | Highlight modified and untracked git files in the Explorer sidebar (requires `.git` directory) |
| `path_display_mode` | string | `"absolute"` | File path display in footer: `"absolute"` or `"relative"` (relative to workspace root) |
| `sidebar_width` | integer or string | `28` | Initial sidebar width: integer for cells (min 5), or `"30%"` for percentage (1%-90%) |

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
2. Select the action you want to configure
3. Click **Change Key...** and press the new key combination
4. The binding is saved immediately; restart the app to apply

### Warning: restart required

Custom keybindings take effect after restarting Textual Code.
The app shows a notification: *"Shortcut saved. Restart to apply changes."*

### Finding action names

Action names shown in the F1 shortcuts screen match the keys used in `keybindings.toml`.
For example, the action displayed as `save_file` maps to the key `save_file` in the TOML file.

## Shortcut Display Preferences: [display] sections

Control whether each shortcut appears in the footer bar and command palette, and set footer display priority.

```toml
[display.save]
footer = true
palette = true
footer_priority = 1

[display.toggle_sidebar]
footer = false
```

### How to configure display

1. Press **F1** to open the shortcuts screen
2. Select the action you want to configure
3. Toggle the **Show in footer** and **Show in command palette** checkboxes
4. Optionally set a **Footer priority** (1-999, lower = higher priority)
5. Click **Save**; restart the app to apply

### Available fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `footer` | bool | binding's `show` attribute | Show in the footer bar |
| `palette` | bool | `true` | Show in the command palette |
| `footer_priority` | int (1-999) | `ACTION_ORDER` index | Display order in footer |

All fields are optional. Omitted fields use the default value.
