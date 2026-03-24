# Editor Features

Core editing capabilities of the Textual Code editor: file management, text editing, multiple cursors, and find/replace.

## File Management: open, save, close, delete, reload, external change detection

### New File (Ctrl+N)

Creates an untitled tab with application defaults (encoding, indentation, line ending, word wrap from user/project settings). The tab title shows "Untitled". Saving requires Save As (prompted on first Ctrl+S). Available via the command palette ("New file") or Ctrl+N; when the explorer sidebar is focused, Ctrl+N triggers "Create file" instead (creates a file on disk in the selected directory).

### Open File: CLI args, command palette, explorer double-click

Files can be opened through three paths:

- **CLI arguments**: `textual-code file.py` or `textual-code --workspace /project file.py`. The `--workspace` / `-w` flag overrides the sidebar root directory independently of the target file path.
- **Command palette**: "Open file" enumerates workspace files (skipping hidden paths and directories) and fuzzy-matches on relative paths.
- **Explorer double-click**: double-clicking a file node in the sidebar opens it in the active split. If the file is already open in a tab, that tab is focused instead.

Binary files (null byte detected in the first 8 KiB) cannot be edited. Image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.tiff`, `.tif`) open in a read-only image preview tab; all other binary files show a warning tab ("Binary file -- not supported"). The same file cannot be opened twice in the same split pane.

### Save (Ctrl+S) / Save As

- **Ctrl+S** writes the current buffer to disk using the detected encoding. If the file has no path (untitled), Save As is triggered automatically.
- **Save As** opens a modal dialog for entering a file path. The target path must not already exist (error notification otherwise). On success, the editor's path updates to the new location.
- **Encoding preservation**: the file is saved in its detected encoding (UTF-8, UTF-8 BOM, UTF-16, Latin-1, Shift-JIS, GBK, etc.). The encoding can be changed via the footer encoding button or the command palette.
- **EditorConfig save-time transformations**: `trim_trailing_whitespace=true` strips trailing spaces/tabs from all lines; `insert_final_newline=true` ensures the file ends with a newline; `insert_final_newline=false` removes trailing newlines. The editor buffer is updated to reflect the saved content.
- **Line ending conversion**: internal text (always LF) is converted to the file's line ending style (LF, CRLF, or CR) before writing.

**Keybinding:** `Ctrl+S` (save), Save As via command palette or prompted on first save of untitled file.

### Save All (Ctrl+Shift+S)

Saves all modified tabs across all split panes. Tabs without unsaved changes are skipped. Untitled tabs without a path cannot be batch-saved and are skipped silently.

**Keybinding:** `Ctrl+Shift+S` (hidden from footer bar to reduce clutter).

### Close (Ctrl+W) / Close All (Ctrl+Shift+W)

- **Ctrl+W** closes the active tab. If the tab has unsaved changes, a modal dialog offers three choices: Save, Don't Save, Cancel. Choosing Save writes the file and then closes; Don't Save discards changes and closes; Cancel aborts.
- **Ctrl+Shift+W** closes all open tabs with individual unsaved-change prompts for each dirty tab.
- Closing the last tab in a split pane auto-collapses that split.

**Keybinding:** `Ctrl+W` (close), `Ctrl+Shift+W` (close all, hidden from footer).

### Delete File/Folder: sidebar and command palette

- **From sidebar**: press the `Delete` key on a selected node in the explorer tree. A confirmation modal shows the path and warns "This action cannot be undone." Directories prompt with "Permanently delete this directory and ALL its contents?"
- **From command palette**: "Delete file" deletes the active editor's file with the same confirmation modal.
- On successful deletion, the editor tab is closed and a notification confirms.

### Reload File: command palette, discard confirmation

Triggered via the command palette ("Reload file"). If the buffer has unsaved changes, a "Discard & Reload" confirmation modal appears. Reloading re-reads the file from disk, re-detects encoding and line ending, and replaces the editor text. A notification confirms "File reloaded."

If no file is associated with the tab (untitled), an error notification is shown.

### External Change Detection: 2-second mtime polling, auto-reload or warning

The editor polls each open file's `mtime` every 2 seconds (polling is disabled in headless/test mode):

- **Clean buffer** (no unsaved changes): the file is silently auto-reloaded.
- **Dirty buffer** (unsaved changes): a persistent warning notification appears ("File changed externally. Reload to apply changes."). This notification is shown only once and persists until the user saves or reloads. The notification is dismissed automatically on save or reload.

### Overwrite Confirmation: modal when saving over externally modified file

When saving (Ctrl+S), if the file's `mtime` on disk differs from the last known `mtime`, an "Overwrite" confirmation modal appears: "The file was modified externally. Overwrite with your changes?" with Overwrite and Cancel buttons.

### Binary File Detection: null byte in first 8 KiB, image file routing

`is_binary_file()` reads the first 8,192 bytes and checks for a null byte (`\x00`). If found, the file is classified as binary. Image files with recognized extensions (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.tiff`, `.tif`) are routed to the image preview pane (see [ui.md#image-preview](ui.md#image-preview-terminal-rendering-rich-pixels-resize-debounce)); all other binary files show a warning tab ("Binary file -- not supported") and cannot be edited.

### Known Limitations

- No auto-save feature.
- File rename is available via F2 or the command palette "Rename file" command.
- Non-image binary files cannot be edited; they are display-only with a warning notice. Image files are previewed but not editable.
- Save As rejects paths that already exist (no overwrite option in Save As).
- Untitled files are skipped by Save All.

**Implementation:** `code_editor.py`, `main_view.py`, `app.py`, `modals.py`, `utils.py`

## Text Editing: selection, copy/cut, move line, indent, sort lines, word wrap, undo/redo

### Basic Text Editing: insert, delete, backspace

Standard character insertion at the cursor position, `Delete` key removes the character to the right, `Backspace` removes the character to the left. All operations work with multi-cursor when active (see Multiple Cursors section).

### Undo (Ctrl+Z) / Redo (Ctrl+Shift+Z or Ctrl+Y)

Undo reverses the last text edit. Redo re-applies it. Two redo keybindings are supported: `Ctrl+Shift+Z` (VS Code default) and `Ctrl+Y` (Textual built-in). Undo/redo is handled by the underlying Textual `TextArea` widget.

**Keybinding:** `Ctrl+Z` (undo), `Ctrl+Shift+Z` or `Ctrl+Y` (redo).

### Selection: click, Shift+click, Shift+arrows

- **Click**: places cursor at click position, clears selection and any active extra cursors.
- **Shift+Click**: extends selection from current cursor to click position.
- **Shift+Arrow keys**: extends selection character by character (left/right) or line by line (up/down).
- **Home**: moves cursor to first non-whitespace character on the line; press again to toggle to column 0 (VS Code smart home).
- **Shift+Home/End**: extends selection to start/end of current line.
- **Shift+PageUp/PageDown**: extends selection one page up or down. Works with both single cursor and multi-cursor.
- **Ctrl+Shift+Left/Right**: extends selection word by word.
- **Ctrl+Shift+Home/End**: extends selection to start/end of document.

### Double-Click: selects word at cursor

Double-clicking selects the word under the cursor using `\w+` boundaries (word characters: letters, digits, underscore). Also clears any active extra cursors.

### Triple-Click: selects entire line

Triple-clicking selects the entire content of the line at the cursor position. Also clears any active extra cursors.

### Select All (Ctrl+A)

Selects all text in the document and clears any active extra cursors in one operation.

**Keybinding:** `Ctrl+A`.

### Copy/Cut with No Selection: VS Code line-copy behavior

- **Ctrl+C with no selection**: copies the entire current line including its trailing newline character to the clipboard.
- **Ctrl+C with selection**: copies the selected text as usual.
- **Ctrl+X with no selection**: cuts the entire current line (copies to clipboard and deletes).
- **Ctrl+X with selection**: cuts the selected text as usual.

This matches VS Code's behavior where empty-selection copy/cut operates on the whole line.

**Keybinding:** `Ctrl+C` (copy), `Ctrl+X` (cut).

### Paste Line-Copied Text: VS Code line-paste behavior

When pasting text that was copied or cut without a selection (whole-line copy/cut), the pasted line is inserted **above** the current cursor line instead of at the cursor position. The cursor follows the original line down, maintaining its column position.

- **Ctrl+V after line-copy/cut**: inserts the copied line above the current line; cursor stays on the original line.
- **Ctrl+V after selection copy**: inserts at the cursor position as usual.
- **Ctrl+V with active selection**: replaces the selection regardless of how text was copied.

The editor tracks whether the last copy/cut was a whole-line operation. This metadata is shared across all editor tabs. If the clipboard content is changed by another operation (e.g., "Copy File Path"), the line-paste mode is automatically deactivated and normal paste behavior is used.

Both paste paths are supported: the `Ctrl+V` key binding (`action_paste`) and terminal bracketed paste events (`_on_paste`). The latter is the active path on Windows Terminal and other terminals that intercept `Ctrl+V` to send system clipboard content as a Paste event. CRLF line endings from the system clipboard are normalized to LF.

**Keybinding:** `Ctrl+V` (paste).

### Move Line Up/Down (Alt+Up / Alt+Down)

Moves the current line (or all lines touched by the selection) up or down by one row. Supports multi-cursor: ranges from all cursors are collected, merged when overlapping or adjacent, and moved together. Follows the VS Code convention of excluding the last row when a multi-line selection ends at column 0.

Movement is blocked (no-op) when any block would move past the first or last line of the document.

**Keybinding:** `Alt+Up` (move up), `Alt+Down` (move down).

### Scroll Viewport (Ctrl+Up / Ctrl+Down)

Scrolls the editor viewport by one line up or down without moving the cursor position. Useful for peeking at nearby code without losing your editing position.

**Keybinding:** `Ctrl+Up` (scroll up), `Ctrl+Down` (scroll down).

### Indent (Tab) / Dedent (Shift+Tab)

- **Tab**: with a multi-line selection, inserts one indent level (spaces or tab character depending on `indent_type` setting) at the start of each selected line. With a single cursor or no selection, inserts the indent at the cursor position.
- **Shift+Tab**: removes up to one indent level of leading whitespace from each selected line. For tab-indented files, removes one leading tab. For space-indented files, removes up to `indent_size` leading spaces.

Both operations respect `indent_size` and `indent_type` settings from EditorConfig, the Change Indentation modal, or application defaults.

**Keybinding:** `Tab` (indent), `Shift+Tab` (dedent).

### Sort Lines: ascending/descending via command palette

Sorts the selected lines alphabetically (ascending) or in reverse order (descending). Available via the command palette only ("Sort lines ascending" / "Sort lines descending") — no default keybinding. Uses case-sensitive sorting matching VS Code's default behavior.

Supports multi-cursor: ranges from all cursors are collected, merged when overlapping or adjacent, and each merged range is sorted independently. Single-line selections are a no-op (nothing to sort). The selection is preserved after sorting.

**Command palette:** "Sort lines ascending", "Sort lines descending".

### Word Wrap: toggleable via command palette or settings

Soft word wrap can be toggled per-file via the command palette ("Toggle word wrap"). The default for new files is controlled by the `word_wrap` setting (default: `true`). Word wrap state is per-editor-tab and does not affect the underlying file content.

### Indentation Guides: toggleable via command palette or settings

Vertical guide lines are displayed at each indent level within leading whitespace, making code structure easier to follow. Toggle per-file via the command palette ("Toggle indentation guides"). The default is controlled by the `show_indentation_guides` setting (default: `true`). Guides automatically adapt their color to dark and light themes.

### Render Whitespace: select mode via command palette or settings

Whitespace characters (spaces and tabs) can be displayed as visible markers: spaces appear as `·` (middle dot) and tabs as `→` (arrow). Select a mode via the command palette ("Set render whitespace"). The default is controlled by the `render_whitespace` setting (default: `"none"`).

| Mode | Description |
|------|-------------|
| `none` | No whitespace rendering (default) |
| `all` | Render all spaces and tabs |
| `boundary` | Render leading and trailing whitespace only |
| `trailing` | Render trailing whitespace only |

When both render whitespace and indentation guides are enabled, guide characters (`│`) take priority at guide positions, and whitespace markers fill the remaining whitespace. Markers automatically adapt their color to dark and light themes.

### Known Limitations

- No block/column selection mode.
- No minimap or scroll overview.
- No code folding.
- No auto-indent or smart indent (no bracket-aware indentation).

See [editor-vscode-differences.md](editor-vscode-differences.md) for a comprehensive list of behavioral differences from VS Code discovered during test porting.

**Implementation:** `multi_cursor_text_area.py`, `code_editor.py`

## Multiple Cursors: add cursor, Ctrl+D next occurrence, Ctrl+Shift+L select all occurrences

### Add Cursor Below (Ctrl+Alt+Down) / Above (Ctrl+Alt+Up)

Adds an extra cursor one line below or above the primary cursor, at the same column. If the target position already has a cursor or matches the primary cursor, the operation is a no-op. Also available via the command palette ("Add cursor below" / "Add cursor above").

**Keybinding:** `Ctrl+Alt+Down` (below), `Ctrl+Alt+Up` (above).

### Add Next Occurrence (Ctrl+D): VS Code style

Incrementally selects occurrences of the current word or selection:

1. **First press (no selection)**: selects the word under the cursor using `\w+` boundaries. The primary selection spans the matched word. This activates **word mode**: subsequent Ctrl+D presses use whole-word (`\b`) matching, case-sensitive.
2. **Subsequent presses (word mode)**: searches forward from the last cursor's position for the next whole-word occurrence. Adds a new cursor at the match with selection spanning the matched text. Search wraps around to the beginning of the document.
3. **From existing selection (substring mode)**: if the user manually selects text and then presses Ctrl+D, the search uses case-insensitive substring matching instead of word boundaries. This allows selecting partial words or mixed-case variants.
4. **All selected**: when the search wraps back to an already-selected match, a notification shows "All occurrences already selected."

Extra cursor direction matches the primary selection direction (handles both forward and reverse selections correctly). When the newly added cursor is off-screen, the viewport automatically scrolls to bring it into view.

**Keybinding:** `Ctrl+D`.

### Select All Occurrences (Ctrl+Shift+L)

Selects every occurrence of the current selection (or word under cursor if no selection) in the entire document. Matching VSCode behavior, uses two modes: from a collapsed cursor, uses whole-word (`\b`) case-sensitive matching; from an existing selection, uses case-insensitive substring matching. The primary selection is set to the first match, and extra cursors with selections are added at all remaining matches.

Shows a notification with the count (e.g., "5 occurrences selected"). If no matches are found, shows a warning notification.

**Keybinding:** `Ctrl+Shift+L`.

### Multi-Cursor Editing: typing, backspace, delete at all cursors

When extra cursors are active, the following edits are applied simultaneously to all cursor positions:

- **Character insertion**: the typed character is inserted at every cursor.
- **Backspace**: deletes one character to the left at every cursor. If any cursor is at column 0 (line merge scenario) and others are not, extra cursors are cleared and the edit falls back to single-cursor behavior.
- **Delete**: deletes one character to the right at every cursor. Same mixed-position clearing behavior as backspace.
- **Selection replacement**: when any cursor has an active selection, typing/backspace/delete replaces all selections with the typed character (or empty string for backspace/delete). Overlapping selections are merged before editing.

### Movement Keys with Multi-Cursor

Arrow keys, Home/End, Ctrl+Left/Right/Home/End, Page Up/Down, and their Shift variants move all cursors simultaneously:

- **Without Shift**: moves all cursors; anchors reset (selections cleared).
- **With Shift**: extends selection per cursor independently (each cursor has its own anchor).

Cursors that collide after movement are automatically deduplicated.

### Escape Clears Extra Cursors

Pressing `Escape` when extra cursors are active removes all extra cursors, returning to single-cursor mode. This is the primary way to exit multi-cursor editing.

### Footer Cursor Count Display

The footer shows `Ln X, Col Y` for single cursor mode. When multiple cursors are active, it shows `Ln X, Col Y [N]` where N is the total cursor count (primary + extras). The cursor button has `max-width: 28` to prevent long multi-cursor labels from crowding the path display.

### Known Limitations

- **Enter clears extra cursors**: pressing Enter inserts newlines at all cursor positions but the multi-cursor positions may become inconsistent in edge cases.
- **Backspace at column 0 with mixed positions**: when some cursors are at column 0 and others are not, extra cursors are cleared and the operation falls back to single-cursor.
- **Delete at end-of-line with mixed positions**: same clearing behavior as backspace at column 0.
- No multi-cursor support for Tab/Shift+Tab indent operations (uses single-cursor indent logic).

**Implementation:** `multi_cursor_text_area.py`, `code_editor.py`

## Find & Replace: inline bar, regex, case sensitivity, select all matches

### Find (Ctrl+F): inline bar docked to top of editor

Opens the inline find bar docked to the top of the editor (VS Code style). The find input is focused automatically. The bar stays open while editing, allowing iterative searching without reopening.

**Keybinding:** `Ctrl+F`.

### Replace (Ctrl+H): extends find bar with replace input

Opens the find bar in replace mode, showing an additional row with a "Replace with..." input field, a "Replace" button, and a "Replace All" button. The find input is focused.

**Keybinding:** `Ctrl+H`.

### Find Next: Enter or button

Pressing `Enter` in the find input or clicking the "Next" button searches for the next match from the current cursor position. The search wraps around to the beginning of the document when it reaches the end. The matched text is selected (primary cursor moves to the match). Sequential "Next" clicks advance through matches without reopening the bar.

If no match is found, a warning notification shows "'query' not found".

### Regex Mode: toggle via `.*` checkbox

The `.*` checkbox enables full Python regex pattern matching. When regex is on, the find query is compiled as-is (not escaped). Invalid regex patterns produce an error notification ("Invalid regex: ...").

In replace mode, regex capture groups are supported in the replacement string (e.g., `\1`, `\2`).

### Case Sensitivity: toggle via `Aa` checkbox

The `Aa` checkbox controls case sensitivity for find and replace. Default is case-sensitive (checkbox checked).

When regex mode is turned on, the `Aa` checkbox is automatically disabled because regex controls its own case sensitivity via inline flags (e.g., `(?i)`). Internally, when regex is on, `case_sensitive` is always forced to `True` to avoid double-applying `re.IGNORECASE`.

### Select All: button for multi-cursor selection of all matches

The "Select All" button in the find bar selects all matches in the document using multi-cursors. The primary selection is set to the first match, and extra cursors with selections are placed at all remaining matches. Respects the current regex and case sensitivity settings.

After selecting, focus moves to the editor for immediate multi-cursor editing. The find bar stays open so the query can be refined. A notification shows the count of occurrences selected.

### Replace: single replacement at current match

Pressing `Enter` in the replace input or clicking the "Replace" button replaces the current match (the text currently selected that matches the find query) with the replacement text. After replacement, the next match is automatically found and selected.

If the current selection does not match the find query, Replace first advances to the next match without replacing.

### Replace All: batch replacement

The "Replace All" button replaces all occurrences of the find query in the document with the replacement text in one operation. A notification shows the count (e.g., "Replaced 5 occurrence(s)"). Respects regex and case sensitivity settings.

### Escape Closes the Bar

Pressing `Escape` while the find bar is focused closes it and returns focus to the editor. The find offset is reset so the next Ctrl+F search starts from the cursor position.

### Known Limitations

- No multi-line search patterns (patterns are matched within single lines by default, though regex `.` does not match `\n`).
- No search history (previous queries are not remembered across sessions).
- No "find in selection" mode (search always covers the entire document).
- No match count indicator in the find bar (only notification on Select All).
- No incremental/live highlighting of all matches while typing the query.

**Implementation:** `find_replace_bar.py`, `code_editor.py`
