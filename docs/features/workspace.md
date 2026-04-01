# Workspace Features

## Workspace Search: find in workspace, replace all, regex, gitignore, include/exclude filters

Workspace Search allows searching across all text files in the current workspace directory. It is accessible from the sidebar Search panel or via keyboard shortcut.

### Purpose

Provides project-wide text search and batch replace without leaving the editor. Equivalent to "Find in Files" in GUI editors. All search operations run in a background thread so the UI remains responsive during large searches.

### Behavior

**Opening the search panel:**

- `Ctrl+Shift+F` opens the sidebar (if hidden), switches to the Search tab, and focuses the query input.
- Also accessible via command palette: "Find in Files".

**Search execution:**

- Type a query and press Enter or click the Search button.
- The search runs in a background thread using a Textual `@work(thread=True, exclusive=True)` worker. A new search cancels any in-progress search.
- While the search is running, the results list shows a pulsating dots loading indicator (Textual's built-in `LoadingIndicator`).
- Results are capped at 500 matches (`max_results=500`).
- Each result shows `relative/path:line_number  line content`.
- If no matches are found, "No results" is displayed. If the worker errors unexpectedly, "Search failed" is shown.
- If some directories are inaccessible (e.g., permission denied), they are silently skipped and partial results are still displayed.

**Result navigation:**

- Click any result item to open the file at the matched line. The file opens in the active split pane and the cursor moves to the matched line number (1-based).

**Replace All:**

- Enter a replacement string in the "Replace with..." input and click "Replace All" or press Enter in the replace input.
- Before replacing, a **diff preview screen** appears showing:
  - A title bar with the number of affected files and total occurrences (shows "N+" when truncated at 100 files).
  - A left panel listing all affected files with per-file hit counts.
  - A right panel displaying a unified diff preview for the selected file, with syntax-highlighted additions (green) and removals (red).
  - Selecting a different file in the left panel updates the diff view.
- The diff preview is generated in a background thread to keep the UI responsive. If no matches are found, a "No matches found" status is shown without opening the screen.
- Each file is hash-checked (SHA-256) before applying: if a file was modified between the preview and the apply, it is skipped and reported to the user via a notification.
- After the user clicks "Apply All", the replacement modifies files on disk directly.
- A status line shows "Replaced N occurrence(s) in M file(s)" after completion. Skipped or failed files are reported separately.
- Supports regex capture groups when regex mode is enabled (e.g., replace `(\w+)` with `\1_suffix`).

**Search options (checkboxes):**

| Option | Default | Description |
|--------|---------|-------------|
| `.*` (Regex) | Off | Interpret the query as a regular expression. Invalid regex returns empty results. |
| `Aa` (Case sensitive) | On | When off, matching is case-insensitive for both plain text and regex. |
| `Gitignore` | On | Respect `.gitignore` files found at any directory level. Nested `.gitignore` files are applied relative to their own directory. |

**Include/exclude filters:**

- "Include files" input: comma-separated glob patterns (e.g., `src/**`, `*.py`). Only files matching at least one pattern are searched. Uses gitignore-style pattern syntax via the `pathspec` library.
- "Exclude files" input: comma-separated glob patterns (e.g., `node_modules`, `dist`). Files matching any pattern are skipped. Directory names without globs match at any depth.
- Both filters apply to the relative path from the workspace root.
- Pressing `Enter` in either filter input triggers a search with the current query and filter settings.

**Files skipped during search:**

- Hidden files and directories (any path component starting with `.`) when `show_hidden_files` is disabled. The `.git` directory is always excluded.
- Binary files (detected by null byte in matched content).
- Files that cannot be decoded as UTF-8.

**Responsive button labels:**

- At normal sidebar width: buttons show "Search" and "Replace All" with emoji icons.
- When sidebar width drops below 40 cells: buttons collapse to icon-only (emoji only).

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+Shift+F` | Open Find in Workspace (sidebar Search tab) |

### Known Limitations

- No incremental/live search: results do not update as you type. You must press Enter or click Search.
- Results do not auto-update when files change on disk. Re-run the search manually.
- No search history or saved queries.
- Replace All writes directly to disk; there is no undo for workspace-wide replacements. The diff preview provides review before applying but does not support per-file opt-out.
- Replace preview is limited to 100 files; additional matching files are indicated by a "+" suffix in the title.
- Maximum 500 results per search.

**Implementation:** `workspace_search.py`, `search.py`, `sidebar.py`, `app.py`

## Split View: split right/left/up/down, recursive N-way tree, focus navigation, resize, text sync

Split View allows opening the same file (or different files) side-by-side in multiple panes. The split layout uses a recursive tree data structure supporting unlimited nesting.

### Purpose

Enables comparing or referencing multiple files simultaneously without switching tabs. Edits to the same file in different splits are synchronized in real-time.

### Behavior

**Creating splits:**

- `Ctrl+\` splits the active pane to the right, opening the current file (or a new editor if no file is open) in the new pane.
- Split left, up, and down are available via the command palette ("Split editor left", "Split editor up", "Split editor down").
- After splitting, focus and `_active_leaf_id` both move to the newly created pane.

**Closing splits:**

- `Ctrl+Shift+\` closes the active split pane. All tabs in that pane are closed (with unsaved-change prompts).
- When a split is closed and its parent branch has only one remaining child, the parent collapses (the remaining child replaces it).
- Also accessible via command palette: "Close Editor Group".

**Recursive N-way split tree:**

- The split layout is a tree of `BranchNode` and `LeafNode` instances (pure data, no Textual dependency).
- A `BranchNode` has a direction (`"horizontal"` or `"vertical"`) and a list of children with associated ratios.
- A `LeafNode` holds a set of `pane_ids` and a map of `opened_files`.
- When splitting in the same direction as the parent branch, the new leaf is inserted as a sibling (flattening). Otherwise, a new `BranchNode` wraps the old leaf and the new leaf.
- There is no hard limit on nesting depth or number of splits.
- Closing a leaf from an N-child branch (N > 2) removes the child and redistributes ratios proportionally.

**Focus navigation:**

- Focus next split: cycles to the next leaf in visual order (left-to-right, top-to-bottom), wrapping around.
- Focus previous split: cycles in reverse.
- Focus left split: jumps to the first (leftmost) leaf.
- Focus right split: jumps to the second leaf (if it exists).
- All focus commands are available via command palette ("Focus next split", "Focus previous split").
- Directional focus uses `directional_leaf()` which walks up the tree to find the nearest sibling in the requested axis, then descends to the closest leaf within that subtree.

**Toggle orientation:**

- Via command palette: "Toggle split orientation" switches the top-level `SplitContainer` between horizontal (side-by-side) and vertical (top-and-bottom) layout.
- Toggles the CSS class `split-vertical` on the container and updates `_direction`.

**Drag resize:**

- A `SplitResizeHandle` widget is placed between every pair of adjacent panes in a `SplitContainer`.
- Dragging the handle resizes the child at `child_index` by setting its `styles.width` (horizontal) or `styles.height` (vertical) to the clamped screen position.
- Minimum size per pane: `SPLIT_MIN_SIZE = 10` cells.
- Handles support N-way splits: each handle tracks its `child_index` and accounts for preceding children's sizes.

**Command palette resize:**

- "Resize split" command accepts: absolute cells (`50`), relative offset (`+10`, `-5`), or percentage (`40%`).
- Percentage range: 10% to 90%. Absolute range: 10 to (total - 10) cells.
- Shows error notification for invalid or out-of-range input.

**Live text sync:**

- When the same file is open in two split panes, edits in one editor are immediately propagated to the other via `sync_text()`.
- The `on_code_editor_text_changed` handler iterates all leaves, finds other panes with the same file path, and calls `sync_text()` on them.
- When saving in one editor, the sibling editor's `initial_text` and `_file_mtime` are updated so no false "file changed externally" warnings appear.

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+\` | Split editor right |
| `Ctrl+Shift+\` | Close split |
| `Ctrl+Alt+\` | Move tab to other split |

### Known Limitations

- No named or labeled splits.
- Split layout is not persisted across sessions. Restarting the editor resets to a single pane.
- No per-split settings (e.g., different themes or font sizes per split).
- Toggle orientation only affects the top-level container, not nested containers.
- Resize via command palette operates on the left panel width only.

**Implementation:** `main_view.py`, `split_tree.py`, `split_container.py`, `split_resize_handle.py`, `app.py`

## Tab Management: reorder, drag-and-drop, directional move, edge-drag split creation

Tab Management covers all operations for rearranging tabs within and across split panes, including drag-and-drop interactions.

### Purpose

Enables flexible organization of open files across the workspace. Tabs can be reordered within a pane, dragged to another pane, or dragged to a pane edge to create a new split.

### Behavior

**New tab opening position (VSCode default):**

- New tabs are inserted immediately after the currently active tab, matching VSCode's default `openPositioning: 'right'` behavior.
- When tabs are opened sequentially (each new tab becomes active), the tab order matches the opening order.
- When a non-last tab is active, the new tab appears right after it, pushing subsequent tabs to the right.
- If no tab is active (empty pane), the new tab is appended at the end.

**Tab reorder by drag (same pane):**

- Drag a tab header left/right to reorder within the pane. Insertion position is determined by which half of the target tab the cursor lands on.
- Editor state (cursor position, content, unsaved changes) is fully preserved.

**Cross-split tab drag:**

- Drag a tab to a different split pane to move it there. If the same file is already open in the destination pane, focus moves to the existing tab instead of creating a duplicate.
- Unsaved content is preserved during cross-split moves.

**Edge-drag to create split:**

- Dragging a tab to a pane edge (15% of width/height) creates a new split in that direction.
- Requires at least 2 tabs in the source pane (the last tab is protected from being moved out).
- For visual feedback details (hint boxes, overlay, edge zone sizing), see [ui.md#drag-and-drop](ui.md#drag-and-drop-visual-feedback-drop-hints-target-highlights-edge-zone-indicators).

**Directional tab move (command palette):**

- "Move tab left/right/up/down": moves the active tab to the adjacent split pane in the specified direction.
- Uses `directional_leaf()` to find the target pane by walking the split tree spatially.
- If no adjacent pane exists in the requested direction, a new split is auto-created in that direction (as long as the source pane has more than one tab).
- After moving, focus lands on the moved tab in the destination pane.

**Tab reorder commands (command palette):**

- "Reorder tab left" / "Reorder tab right": moves the active tab one position within its tab group.
- Uses `reorder_active_tab_by_delta()` with delta -1 (left) or +1 (right).
- No-op at the boundary (first tab cannot go left, last tab cannot go right).
- Includes a defensive underline indicator update to prevent animation race conditions with command palette dismissal.

**Move tab to other split:**

- `Ctrl+Alt+\` moves the active tab to the "other" split pane (first leaf if current is not first, last leaf otherwise).
- If only one leaf exists, a new split is auto-created to the right.

**Same file protection:**

- When moving a tab to a pane that already has the same file open, the move is skipped and focus moves to the existing tab instead of duplicating.

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+Alt+\` | Move tab to other split |
| `Ctrl+W` | Close tab |

### Known Limitations

- No tab pinning or tab grouping.
- No tab close button in the tab header (use `Ctrl+W`).
- No tab preview on hover.
- Drag threshold is 3 pixels; shorter movements are interpreted as clicks.

**Implementation:** `draggable_tabs_content.py`, `main_view.py`, `app.py`

## Sidebar & File Explorer: directory tree, compact folders, git status, hidden files, resize, auto-refresh

The sidebar provides file exploration and workspace search in a collapsible panel docked to the left side of the editor.

### Purpose

Provides visual file navigation, file/folder management, and quick access to workspace search. The explorer shows a directory tree with git status indicators and gitignore-aware dimming.

### Behavior

**Sidebar structure:**

- The sidebar contains a `TabbedContent` with two tabs: Explorer (`explorer_pane`) and Search (`search_pane`).
- A `SidebarResizeHandle` is docked at the right border for drag resizing.
- Toggle visibility with `Ctrl+B` or command palette: "Toggle Sidebar".

**Directory tree:**

- The `FilteredDirectoryTree` extends Textual's `DirectoryTree` with filtering and styling capabilities.
- The workspace root is not shown (`show_root = False`); only its children are displayed.
- Folders are expandable with file/folder icons.
- Clicking a file opens it in the active editor pane.

**Compact folders:**

- `compact_folders` setting (default: `true`): when enabled, single-child directory chains are collapsed into a single tree node with a joined path label (e.g., `src/main/java/com/example` instead of five nested expandable nodes).
- A chain ends when a directory contains more than one child, exactly one file (not a directory), or no children.
- Compacting is based on **visible** children after filtering (hidden files, gitignore). A directory with one visible subdirectory and one hidden file compacts when `show_hidden_files` is `false`.
- Expanding a compact node reveals the contents of the **deepest** directory in the chain.
- Matches VS Code's "Compact Folders" (`explorer.compactFolders`) behavior.
- Toggleable via command palette: "Toggle Compact Folders".

**File creation, deletion, and clipboard operations:**

| Key | Action | Context |
|-----|--------|---------|
| `Ctrl+N` | Create file | Explorer focused, or command palette |
| `Ctrl+D` | Create directory | Explorer focused, or command palette |
| `Delete` | Delete file/folder | Explorer focused (selected node) |
| `F2` | Rename file/folder | Explorer focused, editor focused, or command palette |
| `Ctrl+C` | Copy file/folder | Explorer focused (selected node) |
| `Ctrl+X` | Cut file/folder | Explorer focused (selected node) |
| `Ctrl+V` | Paste file/folder | Explorer focused (target directory) |

- When creating a file or directory, the command palette input is pre-filled with the relative path of the currently selected folder in the explorer (or the parent folder if a file is selected). This works regardless of which widget is focused.
- File/folder deletion shows a confirmation modal with the path and an undo warning.
- File/folder renaming opens a modal pre-filled with the current name, with the filename stem (before the extension) pre-selected. Renaming a directory updates the paths of all open tabs under that directory. Path separator characters are rejected to prevent accidental file moves.
- File/folder moving opens a command palette showing all workspace directories with fuzzy search, including dot-prefixed directories (e.g. `.github/`, `.vscode/`) but excluding `.git` directories and their subtrees. The user selects a destination folder and the file or directory is moved there, keeping its original name. The workspace root is listed as `"."`. Moving a directory updates the paths of all open tabs under that directory. Destination must be within the workspace boundary.
- File/folder copy/cut/paste uses an app-level file clipboard. Copy (`Ctrl+C`) stores the selected path; the clipboard persists so the user can paste multiple times. Cut (`Ctrl+X`) stores the path and clears the clipboard after paste. Paste (`Ctrl+V`) duplicates (copy) or moves (cut) the file/folder into the currently selected directory. Name conflicts are auto-resolved with a " copy" suffix (e.g. `file.py` → `file copy.py` → `file copy 2.py`). Cutting an open file updates the editor tab path. Pasting a directory into itself is prevented. These bindings only activate when the Explorer has focus; when the editor has focus, `Ctrl+C/X/V` perform text copy/cut/paste as usual.
- Also accessible via command palette: "New File...", "New Folder...", "Delete File or Directory", "Rename File or Directory...", "Rename...", "Move File...", "Move File or Directory...", "Copy File or Directory", "Cut File or Directory", "Paste File or Directory".

**Hidden files:**

- `show_hidden_files` setting (default: `true`): when `false`, files and directories starting with `.` are filtered out of the tree entirely.
- `dim_hidden_files` setting (default: `false`): when `true`, dotfiles/dotfolders are visually dimmed using the `directory-tree--hidden` CSS component class.
- Both toggleable via command palette: "Toggle hidden files", "Toggle dim hidden files".
- Settings are persisted to user config on toggle.

**Gitignore dimming:**

- `dim_gitignored` setting (default: `true`): files and directories matching `.gitignore` patterns are visually dimmed.
- Uses the `directory-tree--gitignored` CSS component class with `text-style: dim`.
- `.gitignore` files are loaded lazily per-directory: only ancestor directories of visible files are checked, avoiding upfront workspace-wide traversal. Hidden directories (e.g., `.git/`) are skipped.
- Hidden files (dotfiles) are exempt from gitignore dimming.
- Gitignore specs are cached per-directory and invalidated on tree reload.
- Toggleable via command palette: "Toggle dim gitignored files".

**Git status highlighting:**

- `show_git_status` setting (default: `true`): requires a `.git` directory at the workspace root.
- Modified files: highlighted in yellow (`$text-warning` / `ansi_yellow`) via `directory-tree--git-modified`.
- Untracked files: highlighted in green (`$text-success` / `ansi_green`) via `directory-tree--git-untracked`.
- Parent directories inherit the highest-priority status from their children. Priority: `modified` > `untracked`.
- Status is obtained by running `git status --porcelain -z -unormal` with a 5-second timeout. On startup, git status loads in a background thread so the tree renders immediately without blocking.
- Untracked directories from `-unormal` output are detected (trailing `/`) and their children inherit the untracked status via pre-computed string prefix matching.
- Toggleable via command palette: "Toggle git status highlighting".

**Sidebar resize:**

- Drag the right border handle: width clamped between `SIDEBAR_MIN_WIDTH = 5` cells and `screen_width - 5` cells.
- Command palette: "Resize sidebar" accepts absolute cells (`30`), relative offset (`+5`, `-3`), or percentage (`30%`).
  - Percentage range: 1% to 90%.
  - Absolute range: 5 to (app width - 5) cells.
- `sidebar_width` setting: configurable initial width. Accepts an integer for absolute cells or a percentage string like `"30%"`. Default: `28`.

**Auto-refresh:**

- The explorer polls every 2 seconds for changes (timer disabled in headless/test mode).
- **Directory change detection**: stats the workspace root and all expanded directories. If any mtime changes (file/folder created, deleted, or renamed), the entire tree is reloaded.
- **Git status change detection**: stats `.git/index` and `.git/HEAD`. If either mtime changes (e.g., after `git add`, `git commit`, or branch switch), git status labels are refreshed without a full tree reload.
- Polling is paused during a reload to avoid cascading refreshes.
- Expanded directory state and cursor position are preserved across refreshes.

**Explorer cursor sync:**

- When switching between editor tabs, the explorer cursor moves to the corresponding file.
- If the file is inside a collapsed folder, the folder is expanded automatically (with retry logic up to 10 attempts).

**Responsive design (3-stage collapse):**

1. Full width: tabs show "Explorer" and "Search" with emoji prefixes; buttons show full text with icons.
2. Width < 40 cells: search buttons collapse to icon-only (emoji only).
3. Width < 15 cells: tab labels collapse to icon-only (emoji only).

**Reload explorer:**

- The command palette offers "Refresh Explorer" to manually refresh the directory tree. This re-reads all expanded directories and updates git status indicators.

**Italic rendering fix:**

- The upstream `DirectoryTree` applies italic to file extensions via a regex highlight. This is stripped unconditionally for all file and directory nodes so no name is rendered in italic.

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+B` | Toggle sidebar visibility |
| `Ctrl+N` | Create file (explorer focused) |
| `Ctrl+D` | Create directory (explorer focused) |
| `Delete` | Delete selected file/folder (explorer focused) |
| `F2` | Rename file/folder (explorer or editor focused) |
| `F6` | Focus next widget (cycle between sidebar, editor, etc.) |
| `Shift+F6` | Focus previous widget |

### Known Limitations

- No drag-and-drop file/folder move within the explorer (use command palette "Move file or directory" instead).
- Git status is limited to modified and untracked. No staged, conflict, or ignored status indicators.
- No folder-level git diff.
- Auto-refresh polling interval is fixed at 2 seconds and is not configurable.
- Gitignore pattern caching means newly created `.gitignore` files are not picked up until the next tree reload.

**Implementation:** `explorer.py`, `sidebar.py`, `app.py`
