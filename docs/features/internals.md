# Implementation Internals

Design decisions, rationale, and internal architecture details for contributors.
For feature specifications, see the other files in this folder:
[editor.md](editor.md), [workspace.md](workspace.md), [config.md](config.md), [ui.md](ui.md).

## Language Detection: why filename takes priority over extension

Dotfiles like `.bashrc` have no extension, so extension lookup would always return `None`.
Filename lookup must run first to catch these files before the extension fallback.

### Adding new mappings

- Same file format, new extension → add to `LANGUAGE_EXTENSIONS`
- Exact filename (dotfile or config file with no extension) → add to `LANGUAGE_FILENAMES`
- Do not add "close enough" language mappings (e.g. TypeScript → JavaScript); only identical formats

## Cursor Button: why Button instead of Label

A `Label` has no click semantics; using `Button` gives free keyboard accessibility,
hover styling, and the standard `Button.Pressed` event without custom mouse handling.

`Button.label` is a reactive property (not a method), so updates use assignment
(`self.cursor_button.label = ...`), unlike `Label.update(text)`.

### Why min-width: 20 on cursor_btn

`Button.label` changes trigger `refresh(repaint=True, layout=False)` by default — the grid
column width is fixed at the initial render width. `min-width: 20` reserves enough space
for `"Ln 9999, Col 9999"` and prevents truncation.

## EditorConfig: why stdlib-only implementation

No additional dependency is needed. `configparser`-style line parsing, `re` for glob-to-regex
conversion, and `pathlib` for directory traversal cover the full EditorConfig spec.

See [config.md#editorconfig](config.md#editorconfig--editorconfig-discovery-glob-matching-property-application-auto-reload) for the full behavioral spec.

### Comment and value parsing: no inline comments

Per spec, `;` and `#` are comment markers **only at the start of a line** (after optional
whitespace stripping). `indent_style = space # not inline` → value is `space # not inline`.
Keys and values are normalized to lowercase.

### Auto-reload: safe vs unsafe properties

| Property | Re-applied on change? | Why |
|----------|----------------------|-----|
| indent_type, indent_size | YES | Editor behavior, no text corruption |
| trim_trailing_whitespace, insert_final_newline | YES | Save-time only |
| charset/encoding | NO | Would corrupt in-memory text |
| end_of_line | NO | Would cause inconsistency |

When properties are removed from `.editorconfig`, indent settings stay at their current value
(no "unset" concept for reactives), while save-time settings reset to `None`.

## Tab Performance: lazy mounting, central poll timer, footer batch update

Three architectural choices keep per-tab overhead constant:

### Lazy tab mounting: only the active CodeEditor is in the DOM

When a tab is deactivated, its `CodeEditor` is removed from the DOM and its full state
(text, cursor, scroll, encoding, EditorConfig caches, etc.) is serialized into an `EditorState`
dataclass stored in `MainView._editor_states[pane_id]`. On re-activation the editor is
re-mounted from that state, skipping all file I/O.

Binary-file panes, image preview panes, and Markdown preview panes are exempt — they have
no `CodeEditor` to unmount and must stay mounted so event propagation (`TextChanged`,
`Closed`) continues.

The swap runs inside `app.batch_update()` to suppress intermediate repaints.

`_prev_active_pane_ids[leaf_id]` tracks the last active pane per split leaf so the outgoing
editor can be identified precisely when `TabbedContent.TabActivated` fires.

**Gotcha: custom languages must not be passed to `compose()`.**
Custom tree-sitter languages (from `_CUSTOM_LANGUAGES`) require `register_language()` before
TextArea can use them. Because `compose()` runs before `on_mount()`, passing a custom language
name to `MultiCursorTextArea.code_editor()` in `compose()` raises `LanguageDoesNotExist`.
The fix: `compose()` passes `None` for custom languages; `watch_language()` handles
registration and assignment after mount. See issue #15.

### Central polling timer

A single `set_interval(2.0, …)` in `MainView.on_mount()` calls `_poll_active_editor()`,
which polls only the currently active editor's `_poll_file_change()` and
`_poll_editorconfig_change()`. No per-editor timers exist.

The timer is skipped in headless mode (`if not self.app.is_headless`) to keep tests fast
and deterministic — tests call the poll methods directly.

### Footer batch update

`_sync_footer_to_active_editor()` uses `set_reactive()` (bypasses watchers) to assign all
eight footer reactive properties, then calls `footer.refresh_all_buttons()` once. This
produces a single `refresh(layout=True)` instead of up to eight on each tab switch.

## File Watcher: why mtime polling instead of watchdog

No additional dependency needed — the existing `pyproject.toml` only has `textual[syntax]` and `typer`.
The central poll timer (see above) runs inside Textual's single-threaded event loop, so
there is no race condition with reactive updates or `notify` calls.
`Path.stat().st_mtime` has negligible I/O cost on a 2-second interval.

### _file_mtime tracking rules

`_file_mtime` must be updated after every disk write to prevent a false-positive overwrite prompt:

- `__init__`: set after initial file read
- `_write_to_disk`: set after `path.write_bytes()`
- `action_save_as` / `do_save_as`: set after `new_path.write_bytes()`
- `_reload_file`: set after `path.read_bytes()`

### Why the overwrite confirmation modal exists

If `current_mtime != _file_mtime` at save time, the file was changed externally. Silently
overwriting could destroy those external changes, so the user is asked to confirm.

## Multiple Cursors: why subclassing TextArea

Key events reach `TextArea._on_key` (the widget's internal handler) before they bubble up
to the parent widget. Subclassing allows overriding `on_key` which runs *before* `_on_key`,
so `event.prevent_default()` successfully suppresses the built-in insertion.

### Extra-cursor state: why a plain list, not reactive

`_extra_cursors: list[tuple[int, int]]` is a plain Python attribute. If it were a Textual
`reactive`, list-mutation operations (`.append`) would not trigger `watch_*` because Textual
compares by identity. Every state change instead calls `post_message(CursorsChanged(...))`
and `refresh()` explicitly.

### Column-position maths after multi-cursor edits

Processing edits right-to-left within each row keeps earlier indices valid.
After all edits the new column for cursor `(row, col)` is:

| Operation | new_col formula |
|---|---|
| Insert char | `col + 1 + num_cursors_on_same_row_with_col' < col` |
| Backspace | `col - 1 - num_cursors_on_same_row_with_col' < col` |
| Delete | `col - num_cursors_on_same_row_with_col' < col` |

### Visual rendering: get_line override

`get_line(line_index)` applies `self._theme.cursor_style` to extra-cursor positions in the
`rich.Text` object returned by the base `TextArea`. `refresh()` must be called explicitly
after mutating `_extra_cursors` to trigger a re-render.

## Encoding: why charset-normalizer was added

BOM inspection + UTF-8 decode only detected 4 encodings (UTF-8, UTF-8 BOM, UTF-16, Latin-1).
Multi-byte CJK/Cyrillic/etc. files were silently decoded as Latin-1 (mojibake).
`charset-normalizer` (the same library used by `requests`) provides statistical detection
for 40+ encodings without GPL restrictions.

## Indentation Size: why Select was replaced with Input

The old `Select` offered only 2/4/8 choices. Many projects use 3-space, 6-space, or other
non-standard sizes. Switching to `Input` removes the fixed-option restriction — any positive
integer is accepted.

## Split View Resize: why right panel takes remainder

`#split_right` keeps `width: 1fr` in TCSS. Once `#split_left.styles.width` is set to a fixed
or percentage value, the right panel automatically fills the remaining space — no explicit
right-panel update needed.

## Git Diff Gutter: why `_render_line` override, not a separate widget

Textual's `TextArea` provides no public API for custom gutter decorations. The gutter is
built inside `_render_line()` as a `Segment` with line numbers + 2 spaces of margin. To
inject colored indicators (▎/▔/▁), `MultiCursorTextArea` overrides `_render_line()` and
uses `Strip.crop` + `Strip.join` to replace the last margin cell.

**Private API coupling**: `_render_line` and `wrapped_document._offset_to_line_info` are
internal Textual APIs. Snapshot tests guard against breakage on Textual updates.

### Diff computation: `difflib.SequenceMatcher`

`_compute_line_changes(old_lines, new_lines)` maps `SequenceMatcher.get_opcodes()` to
`LineChangeType` values. Files exceeding 10,000 lines are skipped for performance.

### Data flow: background fetch, synchronous recompute

1. `on_mount` triggers `_refresh_git_diff()` (`@work(thread=True, exclusive=True)`)
2. The worker runs `git show HEAD:<path>` in a background thread
3. `call_from_thread` delivers `head_lines` to `_apply_git_diff` on the main thread
4. `_recompute_git_diff()` diffs `head_lines` vs current editor text
5. `set_line_changes()` stores the result, clears `_line_cache`, and refreshes

On each keystroke, only step 4-5 run (no subprocess — cached `_git_head_lines` is reused).
The `show_git_status` user setting controls whether git diff runs at all.
