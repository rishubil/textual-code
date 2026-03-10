# Features

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
