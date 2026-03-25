# Configuration Features

## Syntax Highlighting: language detection, tree-sitter grammars, theme selection

Textual Code provides syntax highlighting for 30+ languages. Language detection is automatic on file open, and the syntax theme can be changed at any time.

### Language detection priority

Detection follows a two-step priority:

1. **Full filename match** -- the entire filename (e.g. `.bashrc`, `Dockerfile`, `Makefile`) is checked against `LANGUAGE_FILENAMES` first.
2. **File extension match** -- if no filename match is found, the file extension (without leading dot) is looked up in `LANGUAGE_EXTENSIONS`.

If neither matches, the file opens with no syntax highlighting (plain text).

### Built-in languages (Textual TextArea)

These languages use highlight grammars bundled with Textual's `TextArea` widget and require no additional dependency:

Python, JavaScript, TypeScript, JSON, CSS, HTML, XML, YAML, TOML, Rust, SQL, Markdown, Regex, Bash, Java, Go

### Custom tree-sitter grammars (tree-sitter-language-pack)

Ten additional languages are provided via the `tree-sitter-language-pack` package, with custom highlight query files stored in `src/textual_code/grammars/`:

Dockerfile, C, C++, TypeScript (custom `.ts`), TSX, Ruby, Kotlin, Lua, PHP, Makefile

### Additional file extension mappings

| Extension | Detected Language |
|-----------|-------------------|
| `mjs`, `cjs` | JavaScript |
| `svg`, `xhtml` | XML |
| `bash` | Bash |
| `cc`, `cxx`, `hpp` | C++ |
| `h` | C |
| `kt`, `kts` | Kotlin |
| `mk` | Makefile |
| `htm` | HTML |
| `yml` | YAML |
| `md`, `markdown` | Markdown |

### Filename-based detection

| Filename | Detected Language |
|----------|-------------------|
| `.bashrc`, `.bash_profile`, `.bash_logout` | Bash |
| `Dockerfile` | Dockerfile |
| `Makefile`, `makefile`, `GNUmakefile` | Makefile |

### Changing language

- **Command palette**: search "Change language" to open the language selector modal.
- **Footer language button**: click the language label in the status bar to open the same modal.
- The modal lists all available languages plus "plain" (no highlighting).

### Lazy registration

Custom grammars from `tree-sitter-language-pack` are loaded into memory at import time (query files + language objects), but are **registered with the TextArea widget on demand** -- only when a file of that language type is first opened. This avoids registering all 10 custom languages for every editor instance.

### Syntax theme selection

Available syntax themes: `monokai` (default), `dracula`, `github_light`, `vscode_dark`, `css`.

- **Change theme**: command palette "Change syntax highlighting theme" opens a modal with a theme selector and a User/Project save level selector.
- The selected theme applies immediately to all open editors.
- The theme is persisted as the `syntax_theme` key in the `[editor]` section of the chosen config file.

### Known Limitations

- No custom grammar loading from user config files; only bundled grammars are supported.
- No semantic highlighting; highlighting is purely syntactic via tree-sitter.
- The set of syntax themes is hardcoded in `AVAILABLE_SYNTAX_THEMES`; users cannot add custom themes.

**Implementation:** `widgets/code_editor.py` (language maps, detection, lazy registration), `modals.py` (`ChangeLanguageModalScreen`, `ChangeSyntaxThemeModalScreen`), `grammars/*.scm` (custom highlight queries), `app.py` (`action_set_syntax_theme`)

---

## EditorConfig: .editorconfig discovery, glob matching, property application, auto-reload

Textual Code reads `.editorconfig` files to apply per-file formatting settings automatically, following the [EditorConfig specification](https://editorconfig.org/).

### Discovery

Starting from the opened file's parent directory, Textual Code walks upward through each ancestor directory looking for `.editorconfig` files. The walk stops when either:

- A file containing `root = true` in its preamble (before any section header) is found, or
- The filesystem root is reached.

### Precedence

- **Closer file wins**: properties from an `.editorconfig` nearer to the target file take priority over those in a more distant ancestor.
- **Later section wins**: within a single `.editorconfig` file, if multiple `[glob]` sections match the target file, later sections override earlier ones for the same key.

### Glob pattern support

The full EditorConfig glob syntax is supported:

| Pattern | Meaning |
|---------|---------|
| `*` | Any sequence of characters except `/` |
| `**` | Any sequence of characters including `/` (any depth) |
| `?` | Any single character except `/` |
| `[seq]` | Any single character in the sequence |
| `[!seq]` | Any single character not in the sequence |
| `{s1,s2}` | Any of the comma-separated alternatives |
| `{n..m}` | Any integer in the inclusive range n to m |
| `\x` | Literal character x (backslash escaping) |

**Slash rule**: globs that contain no `/` are implicitly prefixed with `**/`, matching the filename at any directory depth. Globs containing `/` are anchored relative to the `.editorconfig` file's directory.

### Supported properties

| EditorConfig Property | Editor State | Applied At |
|-----------------------|-------------|------------|
| `indent_style` | `indent_type` (`spaces` / `tabs`) | File open, auto-reload |
| `indent_size` | `indent_size` | File open, auto-reload |
| `tab_width` | (fallback for `indent_size` only) | File open |
| `charset` | `encoding` (via `_CHARSET_MAP`) | File open only |
| `end_of_line` | `line_ending` | File open only |
| `trim_trailing_whitespace` | Applied at save time | Ctrl+S / Save As |
| `insert_final_newline` | Applied at save time | Ctrl+S / Save As |

### Property mapping details

- `indent_style = space` maps to `indent_type = "spaces"`; `indent_style = tab` maps to `indent_type = "tabs"`.
- `charset` values are mapped through `_CHARSET_MAP`: `utf-8` -> `utf-8`, `utf-8-bom` -> `utf-8-sig`, `utf-16be`/`utf-16le` -> `utf-16`, `latin1` -> `latin-1`.
- `end_of_line` values `lf`, `crlf`, `cr` map directly to the `line_ending` reactive.

### Save-time transformations

When saving (Ctrl+S or Save As):

- `trim_trailing_whitespace = true`: strips trailing spaces and tabs from every line.
- `insert_final_newline = true`: ensures the file ends with a newline character.
- `insert_final_newline = false`: removes all trailing newlines from the file.

The editor buffer is updated after saving to reflect the transformed content.

### Auto-reload

A 2-second polling interval (`set_interval(2.0, ...)`) monitors the mtime of `.editorconfig` files in all searched directories. When a change is detected:

- **Safe properties** are re-applied: `indent_style`, `indent_size`, `trim_trailing_whitespace`, `insert_final_newline`.
- **Unsafe properties** are skipped: `charset` and `end_of_line` are not re-applied to avoid corrupting the in-memory text representation.
- A toast notification "EditorConfig updated." is shown.

### Known Limitations

- `max_line_length` is not supported.
- `tab_width` is only used as a fallback when `indent_size` is set to `tab`.
- No UI for creating or editing `.editorconfig` files.

**Implementation:** `widgets/code_editor.py` (`_read_editorconfig`, `_parse_editorconfig_file`, `_editorconfig_glob_to_pattern`, `_glob_to_regex`, `_apply_editorconfig`, `_poll_editorconfig_change`, `_apply_editorconfig_changes`, `_trim_trailing_whitespace`, `_insert_final_newline`, `_remove_final_newline`)

---

## Encoding & Line Endings: auto-detection, charset-normalizer, 40+ encodings, line ending warning

### Encoding auto-detection strategy

When a file is opened, its encoding is detected in the following order:

1. **BOM check**: UTF-32 BOM (checked first to avoid false UTF-16 matches), UTF-8 BOM (`utf-8-sig`), UTF-16 BOM.
2. **UTF-8 decode attempt**: if the entire content decodes as valid UTF-8, `utf-8` is used.
3. **charset-normalizer**: for non-UTF-8 content with at least 100 bytes, `charset-normalizer` is invoked. Results with confidence > 0.7 are accepted.
4. **Latin-1 fallback**: if all above fail or the content is too short for reliable detection, `latin-1` is used.

### Supported encodings (40+)

Grouped by script/region:

| Group | Encodings |
|-------|-----------|
| Unicode | UTF-8, UTF-8 BOM, UTF-16, UTF-16 LE, UTF-16 BE, UTF-32, UTF-32 LE, UTF-32 BE |
| Western European | Latin-1 (ISO-8859-1), Windows-1252, ISO-8859-15 |
| Central/Eastern European | Windows-1250, ISO-8859-2, Windows-1257 (Baltic), ISO-8859-13 (Baltic) |
| Cyrillic | Windows-1251, ISO-8859-5, KOI8-R (Russian), KOI8-U (Ukrainian) |
| Greek | Windows-1253, ISO-8859-7 |
| Turkish | Windows-1254, ISO-8859-9 |
| Hebrew | Windows-1255 |
| Arabic | Windows-1256 |
| Vietnamese | Windows-1258 |
| Japanese | Shift-JIS, EUC-JP |
| Chinese Simplified | GBK, GB18030 |
| Chinese Traditional | Big5 |
| Korean | EUC-KR |
| Other | ASCII |

### Changing encoding

- **Command palette**: "Change Encoding" opens the encoding selector modal.
- **Footer encoding button**: click the encoding label in the status bar.
- Changing encoding re-interprets the file's raw bytes with the new encoding.
- The modal includes a User/Project save level selector when opened from the "Set default encoding" command.

### Line ending detection

On file open, the raw text (read with preserved line endings) is checked:

- `\r\n` present -> `crlf`
- `\r` present (without `\n`) -> `cr`
- Otherwise -> `lf`

### Changing line ending

- **Command palette**: "Change Line Ending" opens the line ending selector (LF, CRLF, CR).
- **Footer line ending button**: click the line ending label in the status bar.
- Internally, the editor always works with LF (`\n`). The chosen line ending style is applied at save time only.

### Non-LF warning

When a file with CRLF or CR line endings is open and the user copies, cuts, or pastes
multiline text, a toast notification is shown:

> "{ending} line endings: copied/pasted text will use LF internally."

The warning appears once per tab session (resets when the line ending setting changes).
Single-line clipboard operations do not trigger the warning.

This warning can be disabled by setting `warn_line_ending = false` in the `[editor]` section of the settings file. Default is `true`.

### Known Limitations

- No mixed line ending detection or normalization: the first match wins.
- Changing encoding re-interprets bytes, which may produce garbled text if the new encoding is incompatible with the actual file content.

**Implementation:** `widgets/code_editor.py` (`_detect_encoding`, `_detect_line_ending`, `_convert_line_ending`, `_ENCODING_DISPLAY`, `_LINE_ENDING_WARNING`), `modals.py` (`ChangeEncodingModalScreen`, `ChangeLineEndingModalScreen`)

---

## Settings & Configuration: user/project config, TOML format, save level selection

Textual Code uses TOML config files at two levels. For the complete settings reference (all keys, types, defaults, and examples), see [settings-guide.md](../settings-guide.md).

### Config file locations

| Level | Path |
|-------|------|
| User | `~/.config/textual-code/settings.toml` (Linux/macOS) or `%APPDATA%\textual-code\settings.toml` (Windows) |
| Project | `{workspace}/.textual-code.toml` |

On Linux/macOS, the user path respects `$XDG_CONFIG_HOME` if set.

### Priority order

Settings are merged in this order (later overrides earlier):

1. Hardcoded defaults (`DEFAULT_EDITOR_SETTINGS` in `config.py`)
2. User config file
3. Project config file

### Settings keys (14 keys)

All settings live under the `[editor]` TOML table: `indent_type`, `indent_size`, `line_ending`, `encoding`, `syntax_theme`, `word_wrap`, `ui_theme`, `warn_line_ending`, `show_hidden_files`, `dim_gitignored`, `dim_hidden_files`, `show_git_status`, `path_display_mode`, `sidebar_width`.

### Opening settings files

- **Command palette**: "Open user settings" or "Open project settings" opens the corresponding TOML file in the editor. The file is created automatically if it does not exist.

### Save level selection

Theme modals (UI theme, syntax theme) and editor default modals (indentation, line ending, encoding, word wrap) include a **User/Project save level selector**. Choosing "Project" writes to `{workspace}/.textual-code.toml`, which overrides user settings for that workspace only.

The following "Set default..." commands are available via the command palette:

- **Set default indentation** — opens Change Indentation modal with save level selector
- **Set default line ending** — opens Change Line Ending modal with save level selector
- **Set default encoding** — opens Change Encoding modal with save level selector
- **Set default word wrap** — opens Change Word Wrap modal with save level selector

### Runtime behavior

- Most settings take effect immediately without restart (themes, word wrap, explorer toggles).
- Custom keybindings require a restart to take effect.

### Known Limitations

- No settings UI or visual editor; settings must be edited as raw TOML.
- Invalid TOML files are silently ignored (defaults are used).

**Implementation:** `config.py` (`load_editor_settings`, `save_user_editor_settings`, `save_project_editor_settings`, `get_user_config_path`, `get_project_config_path`, `EDITOR_KEYS`, `DEFAULT_EDITOR_SETTINGS`), `app.py` (settings loading in `__init__`, `action_open_user_settings`, `action_open_project_settings`)

---

## Keyboard Shortcuts: command palette, custom keybindings, F1 shortcuts viewer

### Unified command registry: single source of truth for all commands

All bindable commands are defined in `command_registry.py` as a single `COMMAND_REGISTRY` tuple. From this registry, the app derives BINDINGS lists, command palette entries, and the F1 shortcuts viewer rows. This ensures no command can drift out of sync between the palette and keybinding system.

### Command palette (Ctrl+Shift+P)

The command palette provides fuzzy search across all registered commands. Commands that have a keybinding display the shortcut dynamically in their description (e.g. "Save the current file (Ctrl+S)"). Key hints update automatically when custom keybindings are set.

### Default keybindings

Keybindings are defined in the unified command registry (`command_registry.py`) and assigned to three contexts: App (global), Editor (active file), and Text Area (text editing). The full list of default keybindings:

| Key | Action | Context |
|-----|--------|---------|
| Ctrl+N | New file | App |
| Ctrl+B | Toggle sidebar | App |
| Ctrl+Shift+F | Find in workspace | App |
| F1 | Show keyboard shortcuts | App |
| F6 | Focus next widget | App |
| Shift+F6 | Focus previous widget | App |
| Ctrl+S | Save file | Editor |
| Ctrl+Shift+S | Save all files | Editor |
| Ctrl+W | Close tab | Editor |
| Ctrl+Shift+W | Close all tabs | Editor |
| Ctrl+G | Go to line | Editor |
| Ctrl+F | Find | Editor |
| Ctrl+H | Replace | Editor |
| Ctrl+Alt+Down | Add cursor below | Editor |
| Ctrl+Alt+Up | Add cursor above | Editor |
| Ctrl+Shift+L | Select all occurrences | Editor |
| Ctrl+D | Add next occurrence | Editor |
| Ctrl+\\ | Split editor right | Editor |
| Ctrl+Shift+\\ | Close split | Editor |
| Ctrl+Shift+M | Open markdown preview tab | Editor |
| Ctrl+Alt+\\ | Move tab to other split | Editor |
| Ctrl+Shift+Z | Redo | Text Area |
| Ctrl+A | Select all | Text Area |
| Tab | Indent line(s) | Text Area |
| Shift+Tab | Dedent line(s) | Text Area |
| Alt+Up | Move line up | Text Area |
| Alt+Down | Move line down | Text Area |
| Ctrl+Up | Scroll viewport up | Text Area |
| Ctrl+Down | Scroll viewport down | Text Area |
| Shift+PageUp | Select page up | Text Area |
| Shift+PageDown | Select page down | Text Area |

Additional shortcuts inherited from Textual's `TextArea`: Ctrl+C (copy), Ctrl+X (cut), Ctrl+V (paste), Ctrl+Z (undo), Ctrl+Y (redo).

### F1 shortcuts viewer: all commands, key rebinding, unbinding, and palette toggle

Pressing F1 (or command palette "Show Keyboard Shortcuts") opens a modal dialog listing **all** registered commands (not just those with default keybindings) in a `DataTable` with columns: Key, Description, Context. Commands without a keybinding show `(none)` in the Key column.

Clicking any row opens a **Shortcut Settings** dialog (`ShortcutSettingsScreen`) where the user can:

- **Change Key**: opens the rebind sub-dialog to reassign the shortcut key
- **Unbind**: removes the current keybinding (saves `action = ""` in `keybindings.toml`; disabled when already unbound)
- **Show in command palette**: checkbox to toggle whether the shortcut appears in the command palette

### Footer configuration: per-area modal with reorderable list

The command palette entry "Configure footer shortcuts" (or `action_configure_footer`) opens `FooterConfigScreen`, a dedicated modal for controlling which shortcuts appear in the footer bar per focus area.

- An area selector dropdown at the top: Editor / Explorer / Search / Image Preview / Markdown Preview
- Each area shows its relevant bindings in a `ListView`
- Each item shows a ✓/✗ marker indicating visibility
- **Space** toggles visibility, **Ctrl+Up/Down** reorders items
- Buttons: Move Up, Move Down, Toggle, Save, Cancel
- Area state is cached when switching between areas
- On save, the visible items (in list order) become the footer configuration for the selected area

Config is stored in `[footer.<area>]` sections of `keybindings.toml`:

```toml
[footer.editor]
order = ["save", "find", "replace", "goto_line", "close_editor", "new_untitled_file", "toggle_sidebar"]

[footer.explorer]
order = ["create_file", "create_directory", "delete_node", "rename_node", "new_untitled_file", "toggle_sidebar"]
```

Only actions listed in `order` appear in the footer for that area. When no `[footer.<area>]` section exists, the default `DEFAULT_ACTION_ORDERS[area]` is used.

### Custom keybindings: [bindings] section in keybindings.toml

Custom keybindings are stored in `~/.config/textual-code/keybindings.toml` (or `%APPDATA%\textual-code\keybindings.toml` on Windows), under the `[bindings]` section:

```toml
[bindings]
save = "ctrl+s"
toggle_sidebar = "ctrl+b"
```

Keys are action names (matching the second argument to `Binding()`). The rebind is saved immediately and a notification is shown: "Shortcut saved. Restart to apply changes."

Custom keybindings are applied at startup by regenerating class-level `BINDINGS` lists from the command registry with custom overrides. An empty string value (`action = ""`) means the shortcut is explicitly unbound.

### Command palette display: [display.*] sections in keybindings.toml

Per-action command palette visibility is stored using `[display.<action_name>]` sub-tables:

```toml
[display.save]
palette = false
```

- `palette` (bool): show in command palette. Default: `true`.

All config sections (`[bindings]`, `[display.*]`, `[footer.*]`) are saved atomically via `save_keybindings_file()`.

### Known Limitations

- Escape cannot be rebound (it is used for UI control and is in `_SKIP_KEYS`).
- Enter, Tab, and Shift+Tab are also not capturable in the rebind dialog.
- No chord/sequence keybindings (e.g. Ctrl+K, Ctrl+C).
- Keybinding changes require an app restart to take effect. Footer order changes apply immediately.

**Implementation:** `command_registry.py` (`CommandEntry`, `COMMAND_REGISTRY`, `bindings_for_context`), `config.py` (`FooterOrders`, `ShortcutDisplayEntry`, `load_keybindings`, `load_shortcut_display`, `load_footer_orders`, `save_keybindings_file`), `app.py` (`_apply_custom_keybindings`, `action_show_keyboard_shortcuts`, `action_configure_footer`, `_get_focused_area`, `_collect_bindings_for_area`, `set_keybinding`, `set_shortcut_display`, `set_footer_order`, `get_footer_order`, `get_footer_priority`), `modals.py` (`ShowShortcutsScreen`, `ShortcutSettingsScreen`, `FooterConfigScreen`, `RebindKeyScreen`)

---

## UI Themes: 20 built-in themes, runtime selection, persistence

### Available themes

Textual Code exposes all 20 built-in themes from the Textual framework:

| Theme | Theme |
|-------|-------|
| textual-dark (default) | textual-light |
| nord | gruvbox |
| catppuccin-mocha | catppuccin-latte |
| catppuccin-frappe | catppuccin-macchiato |
| dracula | tokyo-night |
| monokai | flexoki |
| solarized-light | solarized-dark |
| rose-pine | rose-pine-moon |
| rose-pine-dawn | atom-one-dark |
| atom-one-light | textual-ansi |

### Changing UI theme

- **Command palette**: "Change UI theme" opens a modal listing all available themes with a User/Project save level selector.
- The selected theme applies immediately without restart.
- The theme name is persisted as the `ui_theme` key in the `[editor]` section of the chosen config file.

### Textual built-in commands

Textual's default built-in system commands (Theme, Quit, Keys, Maximize/Minimize, Screenshot) are excluded from the command palette. The `_all_system_commands()` method does not call `super().get_system_commands()` and instead sources all commands exclusively from the project's `COMMAND_REGISTRY`.

### Known Limitations

- No custom theme creation; only the 20 built-in Textual themes are available.
- No per-editor theming; the theme applies globally to the entire application.

**Implementation:** `app.py` (`action_set_ui_theme`), `modals.py` (`ChangeUIThemeModalScreen`), `config.py` (`save_user_editor_settings`, `save_project_editor_settings`)
