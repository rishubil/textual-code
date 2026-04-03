# UI Features

## Markdown Preview: live preview tab, auto-update, debounced rendering, Ctrl+Shift+M

The Markdown Preview renders a live HTML preview of Markdown files inside a regular editor tab. It is not a side panel; the preview occupies its own tab within the tabbed content area, and can be moved across splits like any other tab.

### Opening and focusing

- **Keybinding:** `Ctrl+Shift+M` (also available via command palette: "Toggle markdown preview").
- Opens a new tab titled `Preview: <filename>` containing the rendered Markdown.
- If a preview tab already exists for the same source file, pressing `Ctrl+Shift+M` again focuses the existing tab instead of creating a duplicate.
- The preview pane is auto-focused when first opened, with a visible focus border (`border: tall $accent` on `:focus`).

### Supported file types

Only files with one of these extensions trigger the preview:

- `.md`
- `.markdown`
- `.mkd`

Pressing `Ctrl+Shift+M` on a non-Markdown file is a no-op.

### Auto-update with debouncing

- The preview subscribes to the source editor's `TextChanged` events.
- Updates are debounced at **300 ms** (`PREVIEW_DEBOUNCE_DELAY = 0.3`) so rapid typing does not block the UI.
- Each debounce timer is file-specific and named `preview-update-<filename>` to avoid cross-file conflicts.
- Previous pending timers are cancelled when a new edit arrives within the debounce window.

### GFM rendering

The preview uses a `markdown-it` parser configured with the `gfm-like` preset. Supported elements include:

- Tables, strikethrough (`~~text~~`), links, bold, italic, code blocks
- A custom core rule (`_move_trailing_spaces`) fixes a rendering quirk where rsvg-convert collapses leading spaces after bold/italic/strikethrough close tokens.

### Scrolling

The preview pane extends `VerticalScroll`, enabling keyboard-driven scrolling:

- Arrow keys, Page Up/Down, Home/End

Mouse scrolling is handled by the Textual framework.

### Lifecycle

- **Closing the source editor also closes the linked preview tab.** This is handled in `on_code_editor_closed`, which pops the preview pane ID from `_preview_pane_ids` and closes the preview pane.
- A placeholder message ("Open a Markdown file in an editor tab to see a preview.") is shown when no Markdown file is active or the preview receives a non-Markdown path.

### Known Limitations

- No side-by-side preview mode; the preview always occupies a separate tab.
- No preview for other markup formats (HTML, RST, AsciiDoc).
- No export to HTML or PDF.
- No synchronized scroll position between editor and preview.

**Implementation:** `widgets/markdown_preview.py`, `widgets/main_view.py`

---

## Image Preview: terminal rendering, rich-pixels, resize debounce

The Image Preview displays image files directly in the terminal using half-cell character rendering. When a recognized image file is opened (via CLI, explorer, or command palette), an `ImagePreviewPane` tab is created instead of a text editor tab. The preview is read-only.

### Supported file types

Files with the following extensions are recognized as images:

- `.png`
- `.jpg`, `.jpeg`
- `.gif`
- `.bmp`
- `.webp`
- `.tiff`, `.tif`

### Rendering

- Uses the `rich-pixels` library to convert image data into Rich renderables using half-cell characters (upper/lower block elements), achieving 2 vertical pixels per terminal row.
- Rendering runs in a background worker thread so the UI remains responsive. A loading spinner is displayed while rendering is in progress.
- The image is never upscaled beyond its native 1:1 pixel ratio. If the terminal area is larger than the image, the image is displayed at its original size.

### File size limit

Images larger than **10 MB** are not rendered. Instead, the pane displays an "Image too large to preview" message. This prevents excessive memory usage and long render times for very large files.

### Resize behavior

- When the pane is resized (e.g., terminal resize, split drag), the image is re-rendered to fit the new dimensions.
- Re-rendering is debounced to avoid excessive computation during continuous resize operations.

### Known Limitations

- Animated GIFs display only the first frame.
- No zoom, pan, or scroll controls.
- No image metadata display (dimensions, color depth, etc.).
- Image quality depends on terminal capabilities and font aspect ratio.

**Implementation:** `widgets/image_preview.py`, `widgets/main_view.py`

---

## Footer Status Bar: file path, cursor position, language, encoding, indentation indicators

A single global footer bar (`CodeEditorFooter`) is owned by `MainView` and always reflects the state of the active editor. There is exactly one footer in the entire app, not one per editor tab.

### Layout

The footer is a 1-row horizontal bar docked to the bottom of the main view. It uses `layout: horizontal` with auto-width buttons so each indicator sizes to its content. The path column uses `1fr` to absorb remaining space.

Components, left to right:

1. **Path label** (`#path`)
2. **Cursor position button** (`#cursor_btn`)
3. **Line ending button** (`#line_ending_btn`)
4. **Encoding button** (`#encoding_btn`)
5. **Indentation button** (`#indent_btn`)
6. **Language button** (`#language`)

### File path display

- Shows the file path of the active editor via a `_PathLabel` widget.
- **Click behavior:** clicking the path copies the displayed path to the clipboard (respects path display mode) and shows a notification. The label shows an underline on hover (`text-style: underline` via CSS).
- **Path display mode:** absolute or relative, togglable via the command palette ("Toggle path display mode") or the `path_display_mode` setting. When relative mode is active and the file is inside the workspace, the path is shown relative to the workspace root using POSIX separators. Falls back to absolute if the file is outside the workspace.
- **Front-truncation:** when the path is longer than the available width, it is truncated from the front with `...` followed by the tail. The ellipsis is styled with theme-aware colors (`foreground-darken-3` on `surface-lighten-2`) so it is visually distinct from actual dot characters in the path.
- The path label re-truncates on every resize event.

### Cursor position

- Format: `Ln X, Col Y` (1-based display, 0-based internal).
- When multiple cursors are active, appends `[N]` showing the total cursor count (e.g., `Ln 5, Col 12 [3]`).
- The button has `max-width: 28` to prevent long multi-cursor labels from crowding the path.
- **Click behavior:** opens the Goto Line modal (`Ctrl+G`).

### Language indicator

- Displays the detected syntax language name, or `plain` if none.
- **Click behavior:** opens the Change Language modal.
- The label refreshes and triggers a layout update when the language changes.

### Encoding indicator

- Displays the file encoding using a display name mapping (e.g., `utf-8` shows as `UTF-8`).
- **Click behavior:** opens the Change Encoding modal.

### Line ending indicator

- Displays the line ending style in uppercase (`LF`, `CRLF`, `CR`).
- **Click behavior:** opens the Change Line Ending modal.

### Indentation indicator

- Displays the current indent settings, e.g., `4 Spaces` or `Tabs`.
- **Click behavior:** opens the Change Indentation modal.

### Footer sync

The footer syncs to the active editor via `_sync_footer_to_active_editor()`, which is called on:

- Tab activation (`TabActivated`)
- Editor state changes (`FooterStateChanged` — cursor move, language change, etc.)
- When no editor is active, the footer resets to defaults (empty path, `Ln 1, Col 1`, `lf`, `utf-8`, `4 Spaces`, `plain`). The `path_display_mode` is intentionally excluded from reset because it is a global setting.

### Copy path commands

Three clipboard copy commands are available via the command palette:

- **Copy relative path** — copies the active file's path relative to the workspace root. Falls back to absolute if the file is outside the workspace.
- **Copy absolute path** — copies the active file's full absolute path.
- **Copy displayed path** — copies the path as currently shown in the footer (respects path display mode).

### Known Limitations

- No word count or character count display.
- No file size indicator.
- No git branch display in the footer.

**Implementation:** `widgets/code_editor.py` (classes `_PathLabel`, `CodeEditorFooter`), `widgets/main_view.py` (footer event handlers, `_sync_footer_to_active_editor`), `style.tcss` (hover underline CSS)

---

## Shortcut Bar: per-area key binding order via OrderedFooter

The shortcut bar at the very bottom of the screen shows available key bindings. It uses `OrderedFooter`, a subclass of Textual's `Footer`, to enforce a per-area display order based on which widget is focused.

### Why a custom footer

Textual's built-in `Footer` renders bindings in the order they are collected from the active binding chain, which changes depending on focus (e.g., editor vs. explorer vs. modal). This causes shortcut labels to jump around unpredictably, making muscle-memory scanning difficult.

`OrderedFooter` sorts bindings by a per-area priority list before rendering, so each focus area shows its most relevant shortcuts first.

### Focus areas and default display orders

Each focus area has its own default action order defined in `DEFAULT_ACTION_ORDERS`:

| Area | Default order |
|------|---------------|
| **editor** | Save, Find, Replace, Goto line, Close tab, New file, Toggle sidebar |
| **explorer** | Create file, Create directory, Delete, Rename, New file, Toggle sidebar |
| **search** | New file, Toggle sidebar |
| **image_preview** | Close tab, New file, Toggle sidebar |
| **markdown_preview** | Close tab, New file, Toggle sidebar |

Users can override the order per area via `[footer.<area>]` sections in `keybindings.toml`.

### Area detection

The area is determined by walking the focused widget's ancestor chain:

- `Explorer` ancestor → `explorer`
- `WorkspaceSearchPane` ancestor → `search`
- `ImagePreviewPane` ancestor → `image_preview`
- `MarkdownPreviewPane` ancestor → `markdown_preview`
- `Sidebar` ancestor (e.g. tab strip) → active tab determines area
- Otherwise → `editor` (default)

**Implementation:** `widgets/ordered_footer.py`, `app.py` (`_get_focused_area`)

---

## Command-Line Interface: open files/folders, --workspace option

The CLI is the primary entry point for launching Textual Code. It is built with Typer and registered as the `textual-code` console script.

### Entry point

- **Command:** `textual-code` (registered in `pyproject.toml` under `[project.scripts]`).
- Internally calls `typer.run(typer_main)`.

### Positional argument: target path

The first positional argument specifies what to open:

- **File:** `textual-code path/to/file.py` -- opens the file in an editor tab, with the sidebar rooted at the file's parent directory.
- **Directory:** `textual-code path/to/dir/` -- opens the directory in the explorer sidebar with no file initially open.
- **Default:** if no argument is given, opens the current working directory.
- **Non-existent file:** if the target does not exist and is not a directory, the CLI attempts to create it with `touch()`. On failure, it prints an error and exits with code 1.
- All paths are resolved to absolute form via `Path.resolve()`.

### Version flag

- **Flag:** `--version`
- Prints the installed version of Textual Code and exits immediately.

### Workspace option

- **Flag:** `--workspace` / `-w`
- Overrides the sidebar root directory independently of the target file.
- Use case: in a monorepo, open a file deep in a subdirectory while keeping the sidebar rooted at the project root.
- Example: `textual-code src/module/file.py --workspace /project/root`
- The workspace path is resolved to absolute form.
- **Error handling:** if the workspace path is not an existing directory, prints an error message and exits with code 1.

### Known Limitations

- No `--line` / `--column` option for opening at a specific cursor position.
- No support for multiple file arguments in a single invocation.
- No `--diff` mode for comparing two files.
- No `tc` short alias is registered; only `textual-code` is available as a console script.

**Implementation:** `__init__.py` (CLI definition), `app.py` (`TextualCode` app constructor accepting `workspace_path` and `with_open_file`)

---

## Drag-and-Drop Visual Feedback: drop hints, target highlights, edge zone indicators

Tab drag-and-drop supports reordering tabs within the same split and moving tabs across splits. The visual feedback system uses a transparent overlay screen so that pane content remains visible during the drag operation.

### Drag initiation

- A drag starts when the user presses and holds a `ContentTab` header.
- A **3-pixel threshold** (`DRAG_THRESHOLD = 3`, euclidean distance) must be exceeded before the drag activates. This prevents accidental drags from normal clicks.
- Once active, the mouse is captured to the source `DraggableTabbedContent`, and the overlay screen is pushed.

### Dragged tab highlight

- The dragged tab receives the `-dragging` CSS class, which applies:
  - `background: $accent` (accent-colored background)
  - `color: $background` (inverted text color)
  - `text-style: bold`
- The class is removed on mouse up, regardless of whether the drop was successful.

### Drop target screen (transparent overlay)

- A `DropTargetScreen` is pushed on top of the main screen when a drag begins.
- The screen has `background: transparent`, so all pane content beneath is fully visible.
- All mouse events and Enter/Leave events are forwarded to the screen below via `_forward_event`, ensuring drag-and-drop continues to function through the overlay.
- Pre-creates `DropHighlight` instances for every `DraggableTabbedContent` found at push time, keyed by their DOM ID.
- A cache (`_highlight_state`) tracks `(region, mode)` per DTC to skip redundant style updates.

### Drop hint box

- `DropHintBox` is a `Static` widget styled as an accent-colored label with bold text, 3 rows tall, padded by 2 on each side.
- It is absolutely positioned within the overlay screen.
- Two display modes:
  - **Full-pane drop** (`"full"` mode): shows `"Move to this pane"`, centered within the target DTC's region.
  - **Edge-zone drop** (`"edge-<direction>"` mode): shows a directional label (`"Split left"`, `"Split right"`, `"Split up"`, `"Split down"`), positioned near the corresponding edge rather than centered. This gives a clear visual cue about where the new split will appear.
- The hint box is hidden (`display: none`) by default and shown (`display: block`) only when the cursor enters a valid drop zone.

### Edge zone detection

- Each edge zone occupies **15%** (`EDGE_ZONE_FRACTION = 0.15`) of the pane's width or height, clamped:
  - Horizontal: min 5, max 15 cells
  - Vertical: min 2, max 8 cells
- All four edges (left, right, top, bottom) are checked simultaneously.
- Edge zones are only active if they do not overlap with the opposite edge (i.e., the pane must be wide/tall enough for two non-overlapping zones).
- **Corner resolution:** when the cursor is in a corner (overlapping two edge zones), the edge with the deepest fractional penetration wins (smallest fractional distance from the edge). On ties, horizontal edges (left/right) take priority over vertical (up/down).

### Same-split reorder

- Dropping a tab on another tab within the same `DraggableTabbedContent` reorders the tab.
- Insertion position is determined by which half of the target tab the cursor lands on (left half = insert before, right half = insert after).
- After reorder, the active-tab underline indicator is resynchronized via `_move_underline` with retry logic (up to 5 retries) to handle layout propagation delays.

### Cross-split drop

- Dropping a tab onto a different `DraggableTabbedContent` moves the tab to that split.
- The `TabMovedToOtherSplit` message carries `source_pane_id`, `target_pane_id`, `target_dtc_id`, and `split_direction`.
- Edge-zone drops with no adjacent leaf create a new split in the requested direction, provided the source split has at least 2 tabs (last tab is protected).

### Active tab underline sync

- After tab reorder, the underline animation is stopped synchronously (`force_stop_animation`) to prevent a running 300ms slide animation from overriding the corrected position.
- `highlight_start` and `highlight_end` are set directly on the `Underline` widget.
- A degenerate-region check retries if the compositor has not yet updated tab positions.

### Known Limitations

- No multi-tab drag selection (only one tab can be dragged at a time).
- No drag to external applications or OS-level drag-and-drop.
- No visual preview of the tab content during drag.
- The last tab in a split cannot be edge-dragged out to create a new split (the split would become empty).

**Implementation:** `widgets/draggable_tabs_content.py` (classes `DropHintBox`, `DropHighlight`, `DropTargetScreen`, `DraggableTabbedContent`), `style.tcss` (`Tab.-dragging` styles), `widgets/main_view.py` (`on_tab_moved_to_other_split` handler)

## Modal Dialogs: Escape key dismisses non-destructive modals

Pressing `Escape` dismisses any modal where cancellation is safe and has no side effects. This includes: Save As, Rename, Go to Line, Find, Replace, Change Language, Change Indentation, Change Line Ending, Change Encoding, Change Syntax Theme, Change Word Wrap, Change UI Theme, Sidebar Resize, Split Resize, Shortcut Settings, Footer Configuration, and Show Keyboard Shortcuts.

Escape does **not** dismiss destructive confirmation modals that require a deliberate choice: Unsaved Changes, Unsaved Changes (Quit), Delete File/Folder, Overwrite Confirm, Discard & Reload, and Replace All Confirm. These require clicking the explicit Cancel button.

**Implementation:** Each non-destructive modal declares `BINDINGS = [Binding("escape", "cancel", ...)]` and an `action_cancel` method that produces the same result as clicking the Cancel button (`modals/` package).
