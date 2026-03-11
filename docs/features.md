# Features

## Language Detection: LANGUAGE_FILENAMES checked before LANGUAGE_EXTENSIONS

`CodeEditor.load_language_from_path` checks in this order:

1. **Full filename** (`path.name`) against `LANGUAGE_FILENAMES` — for dotfiles with no extension (e.g. `.bashrc`)
2. **File extension** (`path.suffix.lstrip(".")`) against `LANGUAGE_EXTENSIONS`

### Why filename takes priority

Dotfiles like `.bashrc` have no extension, so extension lookup would always return `None`.
Filename lookup must run first to catch these files before the extension fallback.

### Adding new mappings

- Same file format, new extension → add to `LANGUAGE_EXTENSIONS`
- Exact filename (dotfile or config file with no extension) → add to `LANGUAGE_FILENAMES`
- Do not add "close enough" language mappings (e.g. TypeScript → JavaScript); only identical formats

## Cursor Button: clickable footer position opens GotoLineModalScreen

The cursor position (`#cursor_btn`) in `CodeEditorFooter` is a `Button` rather than a plain `Label`,
so clicking it opens `GotoLineModalScreen` — the same modal as `Ctrl+G`.

### Why Button not Label

A `Label` has no click semantics; using `Button` gives free keyboard accessibility,
hover styling, and the standard `Button.Pressed` event without custom mouse handling.

### Event flow

1. User clicks `#cursor_btn` in the footer
2. `CodeEditor.on_cursor_button_pressed` handles `Button.Pressed` (CSS selector `#cursor_btn`)
3. Handler calls `self.action_goto_line()`, which pushes `GotoLineModalScreen`
4. Modal result moves `editor.cursor_location`; `TextArea.SelectionChanged` fires
5. `CodeEditor.on_text_area_selection_changed` updates `footer.cursor_location` reactive
6. `watch_cursor_location` sets `cursor_button.label` to the new `"Ln X, Col Y"` string

### Label vs Button update API

`Button.label` is a reactive property (not a method), so updates use assignment:

```python
self.cursor_button.label = f"Ln {row + 1}, Col {col + 1}"
```

This differs from `Label.update(text)`.

## EditorConfig: .editorconfig file discovery, glob matching, property override

### Why stdlib-only, no editorconfig PyPI package

No additional dependency is needed. `configparser`-style line parsing, `re` for glob-to-regex conversion, and `pathlib` for directory traversal cover the full spec.

### Discovery and precedence rules

`_read_editorconfig(path)` walks from `path.parent` upward collecting `.editorconfig` files:

- **Closer file wins**: properties from a nearer `.editorconfig` are never overwritten by a farther one
- **Later section wins within a file**: if two sections in the same file both match, the lower one's values override
- **`root = true` stops traversal**: only recognised in the preamble (before the first `[section]` header); `root = true` inside a section is ignored
- Traversal also stops at the filesystem root

### Glob pattern matching: slash rule matters

`_editorconfig_glob_to_pattern(glob)` converts EditorConfig globs to `re.Pattern`.
The critical rule from the spec:

| Glob has `/`? | Behaviour |
|--------------|-----------|
| No (`*.py`) | Prefixed with `**/` → matches at **any directory depth** |
| Yes (`src/*.py`) | Anchored to `.editorconfig` dir; `src/` prefix required |

Special tokens:

| Token | Regex |
|-------|-------|
| `**` followed by `/` | `(.*/)? ` (zero or more path components) |
| `**` otherwise | `.*` |
| `*` | `[^/]*` |
| `?` | `[^/]` |
| `[!seq]` | `[^seq]` |
| `{s1,s2}` | `(s1\|s2)` |
| `{n1..n2}` | integer alternatives `(n1\|...\|n2)` |
| `\x` | `re.escape(x)` |

### Comment and value parsing: no inline comments

Per spec, `;` and `#` are comment markers **only at the start of a line** (after optional whitespace stripping).
`indent_style = space # not inline` → value is `space # not inline`.
Keys and values are normalized to lowercase.

### Properties applied to CodeEditor reactives

| EditorConfig value | CodeEditor reactive |
|-------------------|---------------------|
| `indent_style=space` | `indent_type="spaces"` |
| `indent_style=tab` | `indent_type="tabs"` |
| `indent_size=N` (N ∈ {2,4,8}) | `indent_size=N` |
| `indent_size=tab` or `indent_style=tab` without `indent_size` | uses `tab_width` value |
| `charset=utf-8-bom` | `encoding="utf-8-sig"` |
| `charset=latin1` | `encoding="latin-1"` |
| `charset=utf-16be/le` | `encoding="utf-16"` |
| `end_of_line=lf/crlf/cr` | `line_ending=...` |
| any property `=unset` | ignored (auto-detect retained) |
| `indent_size` not in (2,4,8) | ignored |

`trim_trailing_whitespace` and `insert_final_newline` are parsed but not applied (feature unsupported by the editor).

### Override is applied once at open time

EditorConfig is read in `CodeEditor.__init__` after the auto-detect block (encoding, line endings). It does not re-apply on save or on `.editorconfig` file changes.

---

## File Watcher: mtime polling, auto-reload, manual reload

### Why mtime polling instead of watchdog

No additional dependency needed — the existing `pyproject.toml` only has `textual[syntax]` and `typer`.
`set_interval` runs inside Textual's single-threaded event loop, so there is no race condition with reactive updates or `notify` calls.
`Path.stat().st_mtime` has negligible I/O cost on an interval of 2 seconds.

### How external change detection works

On mount, each `CodeEditor` registers a 2-second polling timer via `set_interval(2.0, self._poll_file_change)`.

`_poll_file_change` compares `path.stat().st_mtime` against the stored `_file_mtime` value. Three outcomes:

| Condition | Action |
|-----------|--------|
| mtime unchanged | do nothing |
| mtime changed, no unsaved edits | auto-reload (`_reload_file`) |
| mtime changed, unsaved edits exist | warning notification only — user must reload manually |

### _file_mtime tracking rules

`_file_mtime` must be updated after every disk write to prevent a false-positive overwrite prompt on the next save:

- `__init__`: set after initial file read
- `_write_to_disk`: set after `path.write_bytes()`
- `action_save_as` / `do_save_as`: set after `new_path.write_bytes()`
- `_reload_file`: set after `path.read_bytes()`

### Overwrite confirm on save: WHY the modal exists

If `current_mtime != _file_mtime` at save time, the file was changed externally since it was opened or last saved. Silently overwriting could destroy those external changes, so the user is asked to confirm.

### Manual reload via command palette

`action_reload_file_cmd` in `app.py` is wired to the "Reload file" `SystemCommand`.
It delegates to `code_editor.action_reload_file`, which:

- Shows `DiscardAndReloadModalScreen` when there are unsaved changes
- Calls `_reload_file` directly when the editor is clean

---

## Multiple Cursors: MultiCursorTextArea subclass, extra_cursors list

### Why subclassing TextArea instead of intercepting in CodeEditor

Key events reach `TextArea._on_key` (the widget's internal handler) before they
bubble up to the parent widget.  By the time a `CodeEditor.on_key` could react
the text has already been mutated.  Subclassing allows overriding `on_key` which
runs *before* `_on_key`, so `event.prevent_default()` successfully suppresses
the built-in insertion.

### Extra-cursor state: plain list, not reactive

`_extra_cursors: list[tuple[int, int]]` is a plain Python attribute.  If it were
a Textual `reactive`, list-mutation operations (`.append`) would not trigger
`watch_*` because Textual compares by identity.  Every state change instead calls
`post_message(CursorsChanged(...))` and `refresh()` explicitly.

### Key event routing when extra cursors are active

| Key category | Action |
|---|---|
| Escape | `prevent_default` + `stop` → `clear_extra_cursors()` |
| Movement (arrows, home, end, …) | `clear_extra_cursors()`, then TextArea moves normally |
| Printable char / backspace / delete | `prevent_default` + `stop` → `_apply_to_all_cursors` |
| Enter, tab, and anything else | `clear_extra_cursors()`, TextArea handles |

Enter and row-merge cases (backspace at col 0, delete at EOL) are not handled
in MVP — extra cursors are cleared and the base TextArea processes the key.

### Column-position maths after multi-cursor edits

Processing edits right-to-left within each row keeps earlier indices valid.
After all edits the new column for cursor `(row, col)` is:

| Operation | new_col formula |
|---|---|
| Insert char | `col + 1 + num_cursors_on_same_row_with_col' < col` |
| Backspace | `col - 1 - num_cursors_on_same_row_with_col' < col` |
| Delete | `col - num_cursors_on_same_row_with_col' < col` |

The extra shift accounts for edits performed by other cursors that sit to the
left, which displace this cursor further.

### Visual rendering: get_line override

`get_line(line_index)` is called by `TextArea._render_line`.  The override
applies `self._theme.cursor_style` to the extra-cursor positions in the
`rich.Text` object returned by the base implementation.  `refresh()` must be
called explicitly after mutating `_extra_cursors` to trigger a re-render.

### Key bindings and commands

| Action | Key | Command palette |
|---|---|---|
| Add cursor below | `Ctrl+Alt+Down` | "Add cursor below" |
| Add cursor above | `Ctrl+Alt+Up` | "Add cursor above" |
| Clear all extra cursors | `Escape` | — |

### Footer cursor count indicator

`CodeEditorFooter.cursor_count: reactive[int]` tracks the total cursor count
(primary + extra).  When `cursor_count > 1`, the cursor button label becomes
`"Ln X, Col Y [N]"` to signal multi-cursor mode.  It resets to `1` when
`CursorsChanged` fires with an empty extra-cursor list.

---

## Select All Occurrences (`Ctrl+Shift+L`)

Selects every occurrence of the current selection (or the word under the cursor
if nothing is selected) within the open file.

### Key binding and command palette

| Action | Key | Command palette |
|---|---|---|
| Select all occurrences | `Ctrl+Shift+L` | "Select all occurrences" |

### Behaviour

1. **Query resolution** — `CodeEditor._get_query_text()` returns:
   - the selected text when `selection.start != selection.end`
   - the word under the cursor (via `_get_word_at_location`) otherwise
   - an empty string if the cursor sits on whitespace (no-op)
2. **Search** — `re.finditer(re.escape(query), text)`: plain-text,
   case-sensitive, no wrap-around.
3. **Result application**:
   - 0 matches — `notify("'query' not found", severity="warning")`
   - 1 match — primary `TextArea.selection` set to match span, no extra cursors
   - N matches — primary selection = first match; extra cursors added at the
     *start* offset of each remaining match; `notify("N occurrences selected")`

### Helpers

| Helper | Location | Purpose |
|---|---|---|
| `_get_word_at_location(text, row, col)` | `code_editor.py` module level | Returns the `\w+` token containing `(row, col)`, or `""` |
| `_text_offset_to_location(text, offset)` | `code_editor.py` module level | Converts flat char offset to `(row, col)` |
| `CodeEditor._get_query_text()` | `CodeEditor` method | Resolves selection or word-under-cursor |

---

## Split View Resize: command palette sets left panel width, right takes remainder

Resizes the left split panel via the command palette "Resize split" command.
Only available when the right split panel is visible (`_split_visible is True`).

### Accepted input formats

| Input | Effect |
|-------|--------|
| `50` | Set left panel to 50 cells (absolute) |
| `+10` | Widen left panel by 10 cells (relative) |
| `-5` | Narrow left panel by 5 cells (relative) |
| `40%` | Set left panel to 40% of the split container width (percentage) |

### Constraints

| Dimension | Limit | Reason |
|-----------|-------|--------|
| Absolute min | 10 cells | Each panel must be usable |
| Absolute max | `total_width - 10` | Leave at least 10 cells for right panel |
| Percentage range | 10% – 90% | Same usability minimum |

### Why right panel always takes remainder

`#split_right` keeps `width: 1fr` in TCSS. Once `#split_left.styles.width` is
set to a fixed or percentage value, the right panel automatically fills the
remaining space — no explicit right-panel update needed.

### No-op when split is not open

If `_split_visible is False`, the command shows a `notify(..., severity="error")`
and returns without pushing the modal. This avoids confusion about resizing a
panel that isn't visible.

### Parse function

`_parse_split_resize(value, current_width, total_width) -> int | str | None`
in `app.py`. Returns `int` for absolute, `str` like `"40%"` for percentage,
`None` for invalid input.

---

## Editor Defaults with Config File Persistence

New (untitled) files use application-level defaults for indentation, line
ending, and encoding.  Existing files continue to use auto-detection and
EditorConfig (unchanged).

### Config files

| Priority | Location | Purpose |
|---|---|---|
| 1 (lowest) | hardcoded in `config.py` | fallback defaults |
| 2 | `$XDG_CONFIG_HOME/textual-code/settings.toml` (Linux/macOS) or `%APPDATA%\textual-code\settings.toml` (Windows) | user-level config |
| 3 (highest) | `{workspace}/.textual-code.toml` | project-level override |

Both files use the `[editor]` TOML section:

```toml
[editor]
indent_type = "spaces"   # "spaces" or "tabs"
indent_size = 4          # 2, 4, or 8
line_ending = "lf"       # "lf", "crlf", or "cr"
encoding = "utf-8"       # "utf-8", "utf-8-sig", "utf-16", "latin-1", etc.
```

### Implementation

| Component | File | Detail |
|---|---|---|
| `config.py` | `src/textual_code/config.py` | `load_editor_settings()`, `save_user_editor_settings()` |
| App defaults | `app.py` `TextualCode.__init__` | loads settings on startup; stores as `default_*` attributes |
| CodeEditor | `widgets/code_editor.py` `CodeEditor.__init__` | accepts `default_*` kwargs; applies them when `path is None` |
| `open_code_editor_pane` | `app.py` `MainView` | passes app `default_*` attrs to each new `CodeEditor` |
| Actions | `app.py` `TextualCode` | `action_set_default_indentation`, `action_set_default_line_ending`, `action_set_default_encoding` — open the existing change modals and persist on apply |
| Command palette | `app.py` `get_system_commands` | "Set default indentation/line ending/encoding" entries |

