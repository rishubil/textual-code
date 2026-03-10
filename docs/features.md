# Features

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
