# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Tab reorder commands: reorder the active tab within its tab group via the command palette ("Reorder tab left/right"); includes a defensive underline indicator update to prevent animation race conditions with command palette dismissal

- Directional tab move commands: move the active tab to an adjacent split pane in a specific direction (left, right, up, down) via the command palette ("Move tab left/right/up/down"); uses a spatial tree-walk algorithm to correctly navigate nested split layouts

- Widget focus cycling with `F6` / `Shift+F6`: cycle focus between all focusable widgets (sidebar, editor, etc.) using Textual's built-in focus navigation

- Live text sync between split editors: when the same file is open in two split views, edits in one editor are immediately reflected in the other without needing to save first; saving in one editor also updates the sibling's `initial_text` and mtime so no false "file changed externally" warnings appear

- Dragged tab visual highlight: when dragging a tab to reorder or move between splits, the dragged tab now shows an accent-colored background with inverted text and bold styling for clear visual feedback

- Drop target split pane highlight: when dragging a tab across split panes, the target pane shows an accent-colored border to preview the drop destination

### Changed

- Footer path truncation indicator ("...") is now visually distinct from actual path dot characters: the ellipsis uses theme-aware dimmed foreground (`$foreground-darken-3`) and a lighter background (`$surface-lighten-2`) so it stands out from the rest of the path

### Fixed

- Fix explorer cursor not updating when switching to a tab whose file is inside a collapsed folder: the sidebar now expands the collapsed folder and retries cursor placement until the file node is visible; also fixes the case where a folder was previously expanded then manually collapsed (stale `_line` values on hidden nodes caused `move_cursor` to land on the wrong entry)

- Fix missing space between bold and normal text in markdown preview: a markdown-it core rule now moves leading spaces from text tokens that follow inline close tokens (`strong_close`, `em_close`, etc.) into the trailing of the preceding text token, so rsvg-convert renders the space correctly instead of collapsing it

- Fix overwrite confirm modal body text truncated: `max-width: 60` was too narrow for the 62-character message "The file was modified externally. Overwrite with your changes?", cutting off "changes?"; widened to `max-width: 68` and increased the message row height from `1fr` to `2fr` so text can wrap safely in narrow terminals

- Fix footer wasted space: replaced fixed-width grid columns with `layout: horizontal` so each status button (`line_ending`, `encoding`, `indent`, `language`) sizes exactly to its current label (`width: auto`), the path column (`1fr`) absorbs all freed space, and the path label truncates from the front (`"..." + filename`) when the terminal is narrow. `#cursor_btn` is capped at `max-width: 28` to prevent very long multi-cursor labels from crowding the path

- Fix workspace search pane layout clipping: sidebar widened from 20 to 28 characters, checkboxes (regex/case/gitignore) moved to a dedicated row with compact styling so all labels are visible, and the include/exclude filter inputs changed from a side-by-side horizontal layout to a vertical stack so each input spans the full sidebar width instead of half

- Improve markdown preview: debounce preview updates (300ms) so editing with a preview open no longer blocks input; change base class to VerticalScroll for keyboard scrolling (arrow keys, Page Up/Down, Home/End); add focus border highlight; auto-focus the preview pane when opened; improve `focus_pane()` to focus the first focusable descendant instead of the unfocusable TabPane
- Fix Ctrl+D with reverse selection (right-to-left) adding extra cursor at wrong position: `action_select_next_occurrence()` used `sel.end`/`sel.start` directly without normalizing for selection direction; now uses `max()`/`min()` to get logical bounds and matches extra cursor direction to primary selection
- Fix Ctrl+D (add next occurrence) not selecting the matched text on extra cursors: `add_cursor()` was called without an `anchor`, collapsing new cursors to a single point; now passes `anchor` at the match start so extra cursors have the same selection highlight as the primary cursor
- Fix "Change Indentation" title invisible in footer indent modal: `ChangeIndentModalScreen.no-save-level #dialog` had `max-height: 14`, exactly equal to the fixed row heights (9 rows + 3 gutters + 2 border), leaving 0 cells for the `1fr` title row; increased to `max-height: 16`
- Fix active tab indicator intermittently misplaced after tab reorder: a 300 ms slide animation started when the tab was activated continued to override the underline position set by `_highlight_active`; now stops the animation synchronously via `force_stop_animation` and sets `highlight_start`/`highlight_end` directly, with retry logic for degenerate pre-layout regions
- Fix crash when dragging a markdown preview tab to another split: `_move_pane_to_leaf` assumed all panes contain a `CodeEditor`; now handles `MarkdownPreviewPane` separately, recreating the preview in the destination split and updating `_preview_pane_ids` tracking
- Fix markdown preview tab rendering blank: `MarkdownPreviewPane` had no CSS, so the entire `height: auto` chain caused the Markdown widget content to be invisible; added `height: 1fr; overflow-y: auto` to fill the tab pane and enable scrolling
- Fix split focus and active leaf not synced after creating a new split: `_active_leaf_id` and DOM focus now both move to the newly created leaf immediately after splitting, so a second split (e.g. split right then split down) correctly splits the new leaf rather than the original one
- Fix first (left) leaf not removed when emptied: `_auto_close_split_if_empty` previously skipped the first leaf, leaving an empty panel; all empty leaves are now collapsed regardless of position; when the active leaf is removed, focus moves to the nearest remaining leaf by index

### Added

- Add case-sensitive toggle to find/replace bar: a new "Aa" checkbox controls case sensitivity for find and replace operations; the checkbox is automatically disabled when regex mode is on (regex controls its own case via `(?i)`)
- Add gitignore support to workspace search: a "Gitignore" checkbox (default on) filters workspace search results according to `.gitignore` files found at any directory level; nested `.gitignore` files are applied relative to their own directory
- Add file include/exclude filters to workspace search: two new inputs ("Files to include" / "Files to exclude") accept comma-separated glob patterns (e.g. `src/**`, `*.py`) to narrow or skip files during workspace search and replace
- Improve open-file command palette performance: `OpenFileCommandProvider` now enumerates only files (not directories) and skips hidden paths, returning relative paths so the matcher scores them correctly; absolute path is still passed to the open callback
- Add background worker for workspace search: workspace search now runs in a background thread so the UI stays responsive during large searches; errors are surfaced as a "Search failed" result item
- Add case-sensitive toggle to workspace search: a new "Aa" checkbox (default on) controls whether the workspace search and replace operations are case-sensitive; unchecking it enables case-insensitive matching for both plain-text and regex queries
- Fix workspace search folder exclusion: the "Files to exclude" field now correctly excludes entire directories by name (e.g. `node_modules`, `dist`), including at any nesting depth and with or without a trailing slash

- Add Ctrl+A select all: selects the entire document text and clears any active extra cursors in one keystroke
- Add markdown preview as tab (Ctrl+Shift+M): opens a live preview of the active `.md` file in a new editor tab instead of a side panel; the preview auto-updates as you type; closing the source editor also closes its linked preview tab; pressing Ctrl+Shift+M again focuses the existing preview tab without creating a duplicate
- Add syntax highlighting for 10 additional languages via `tree-sitter-language-pack`: Dockerfile, TypeScript (`.ts`), TSX (`.tsx`), C (`.c`, `.h`), C++ (`.cpp`, `.cc`, `.cxx`, `.hpp`), Ruby (`.rb`), Kotlin (`.kt`, `.kts`), Lua (`.lua`), PHP (`.php`), Makefile (`Makefile`, `makefile`, `GNUmakefile`, `.mk`, `.dockerfile`); highlight queries are bundled in `src/textual_code/grammars/`
- Remove save-level selector from footer indentation/line-ending/encoding modals: the "Save to User/Project" dropdown now only appears in the "Set default…" dialogs invoked from the app menu, not in the per-file change dialogs opened via the footer buttons

- Add double/triple click selection: double-clicking a word selects the full word (using `\w+` boundaries); triple-clicking a line selects the entire line; double/triple click also clears any active extra cursors
- Add binary file detection: opening a binary file (null byte in first 8 KiB) now shows a "⚠  Binary file — not supported" notice tab instead of attempting to load it in the editor; the same file cannot be opened twice
- Add explorer cursor sync: switching between editor tabs now moves the explorer cursor to the corresponding file, keeping the sidebar in sync with the active editor

- Add recursive split system: replace the binary left/right split with unlimited nested horizontal/vertical splits using a tree data structure; split right (Ctrl+\\), split down, close split (Ctrl+Shift+\\), focus next/previous split; N-way splits flatten into siblings when direction matches; closing a split auto-collapses the parent; split resize handles work with any number of children
- Refactor status bar to a single global footer owned by `MainView`: previously each `CodeEditor` tab rendered its own `CodeEditorFooter`; now there is exactly one footer in the whole app that always reflects the active editor's state (path, language, line ending, encoding, indentation, cursor position, and cursor count); footer buttons (cursor, line ending, encoding, indent, language) are wired through `MainView` to the active editor
- Add multi-cursor selection and movement: arrow keys, Home/End, Ctrl+Left/Right/Home/End, Page Up/Down now move all active cursors simultaneously; Shift+movement extends the selection per cursor; each extra cursor has an independent anchor so selections are maintained; typing or backspace/delete replaces/removes the selected range at every cursor; overlapping selections are automatically merged before editing; cursors that collide after movement are deduplicated; `Ctrl+Shift+L` (select all occurrences) now places each extra cursor at the end of the matched word with the selection spanning the whole match, consistent with VS Code behaviour
- Fix active split not updated when clicking editor content directly: focusing the editor body (not the tab header) now correctly updates `_active_split`, so Ctrl+W, Ctrl+S, Ctrl+F, and other commands always operate on the focused split rather than the previously active one; closing the last tab in the right split via Ctrl+W now auto-hides the right panel as expected
- Fix tab reorder active indicator not refreshing: after dragging a tab to a new position, the underline indicator now redraws on the correct tab
- Add edge-drag to create new split: drag a tab to the right edge of the left panel (or left edge of the right panel) to move it into a new split view; the edge zone is visually indicated with an accent border during drag; requires at least 2 tabs in the source split (last tab is protected)
- Add cross-split tab drag: drag a tab from one split panel and drop it onto a tab in the other split panel to move it; insertion position is determined by which half of the target tab the cursor lands on (before/after); unsaved content is preserved; if the same file is already open in the destination split, focus is moved there instead of duplicating; moving the last tab out of the right split automatically closes it
- Add tab reordering by drag within the same split: drag a tab header left or right to reorder it; dragged tab is highlighted with accent color during drag; reordering preserves editor state (cursor position, content, etc.)
- Add save level selection to theme dialogs: the "Change UI theme" and "Change syntax highlighting theme" modals now include a "Save to" selector — User (`~/.config`) or Project (`.textual-code.toml`); the built-in Textual "Theme" command is removed from the command palette to avoid duplication
- Add save level selection to editor default settings dialogs: each "Set default..." dialog (indentation, line ending, encoding, word wrap) now includes a "Save to" selector — User (`~/.config`) or Project (`.textual-code.toml`); project-level settings are applied on startup and take priority over user-level settings
- Fix word wrap not applied on file open: word wrap setting is now correctly applied both to newly created files and to existing files opened at startup
- Fix Tab key indentation: Tab now indents selected lines (or inserts spaces at cursor) and Shift+Tab dedents selected lines; multi-line selections are supported; consistent with VS Code behaviour
- Fix Ctrl+D (select next occurrence) placing extra cursor at start of match: cursor is now placed at the end of the matched word, consistent with VS Code behaviour
- Fix F1 keyboard shortcuts dialog not centered on screen
- Add "Copy relative path" and "Copy absolute path" commands: copy the active file's path to clipboard via command palette; relative path falls back to absolute when the file is outside the workspace
- Add "Open user settings" and "Open project settings" commands: open the corresponding TOML config file directly in the editor via command palette; creates the file if it does not exist
- Change word wrap default to `true`: new files now open with word wrap enabled by default
- Add settings guide documentation (`docs/settings-guide.md`): covers config file locations, settings priority, all editor keys, and keybindings customization
- Add keyboard shortcuts customization: view all key bindings via F1 or command palette ("Show keyboard shortcuts"); click any row to rebind it; custom bindings are saved to `~/.config/textual-code/keybindings.toml` and applied on next launch; Escape is not rebindable
- Add UI theme selection: change the application UI theme at runtime via command palette ("Change UI theme"); choose from 20 Textual built-in themes (e.g. nord, gruvbox, dracula, tokyo-night, catppuccin-mocha); selected theme is persisted to user config and restored on next launch
- Add workspace-wide Replace All: the sidebar Search panel now includes a "Replace with..." input and a "Replace All" button; replaces all occurrences of the search query across all text files in the workspace; supports plain text and regex; shows a status line with replacement count and files modified; skips binary, hidden, and non-UTF-8 files
- Add split view drag resize: drag the handle between the two split panels to resize them; width/height is clamped between `SPLIT_MIN_SIZE` (10) and `container_size - 10`; supports both horizontal and vertical split orientations; handle is hidden when no split is open
- Add sidebar drag resize: drag the right border of the sidebar to resize it; width is clamped between `SIDEBAR_MIN_WIDTH` (5) and `screen_width - 5`; existing modal resize flow is unchanged
- Ctrl+C with no selection copies the current line including its newline (VS Code behaviour); Ctrl+X with no selection cuts the current line; Ctrl+C with a selection copies the selected text as before
- Replace Find/Replace modals with an inline find/replace bar (VS Code style): bar docks to the top of the editor, stays open while editing, supports sequential Next clicks without reopening, and shows a replace row in replace mode; regex support retained
- Expand supported file encodings: auto-detection now uses `charset-normalizer` for reliable detection of CJK (GBK, Shift-JIS, EUC-JP, EUC-KR, Big5, GB18030), Cyrillic, Greek, and other non-Latin encodings; UTF-32 BOM detection added; Change Encoding modal now lists 40+ encodings grouped by script/region
- Allow free-form indentation size input: Change Indentation modal replaces the fixed 2/4/8 selector with a text input accepting any positive integer; modal pre-populates current values; invalid input (zero, negative, or non-integer) shows an error notification and keeps the modal open
- Show keyboard shortcut hints in command palette: commands with keybindings now display their shortcut in the description (e.g. "Save the current file (Ctrl+S)"), consistent with existing conventions for multi-cursor commands
- Add "Toggle split orientation" feature: switch between horizontal (side-by-side) and vertical (top-and-bottom) split layout via command palette; toggling adds/removes the `split-vertical` CSS class on the split container
- Add "Find in Workspace" feature (Ctrl+Shift+F): search all text files in the workspace from a Search panel in the sidebar; supports plain text and regex; results show file, line number, and line content; clicking a result opens the file and moves the cursor to the matched line; also accessible via command palette
- Add "Move tab to other split" feature (Ctrl+Alt+\): move the active tab to the opposite split panel (left→right or right→left); auto-creates the right split if not open; unsaved content is preserved; also accessible via command palette
- Add feature to open file or folder from command arguments
- Add feature to open a specific file from the command palette
- Add feature to create a new file or directory
- Add feature to open new file from command arguments
- Add Change Encoding feature: auto-detect encoding on load (UTF-8, UTF-8 BOM, UTF-16, Latin-1), display in footer, change via modal or command palette, save with correct encoding
- Add Indentation button to footer: shows current indent settings (e.g. "4 Spaces", "Tabs"), clickable to open Change Indentation modal
- Add Change Indentation feature: change indent style (spaces/tabs) and size (2/4/8) via modal or command palette, converts existing indentation in the file
- Add Change Line Ending feature: detect line ending on file load (LF/CRLF/CR), display in footer, change via modal or command palette, warn on non-LF files
- Add Change Language feature: change syntax highlighting language via modal or command palette
- Add Find feature (Ctrl+F): search text in current file with plain text or regex support
- Add Replace feature (Ctrl+H): replace text with Replace All and single Replace, supports regex with capture groups
- Add Regex support in Find and Replace: toggle "Use regex" checkbox in Find/Replace modals
- Add Goto Line and Column feature (Ctrl+G): navigate to a specific line and column (e.g. "5" or "3:7") via modal or command palette
- Add Close All Files feature (Ctrl+Shift+W): close all open editor tabs with unsaved-change prompts
- Add Save All Files feature (Ctrl+Shift+S): save all open editor tabs
- Add Toggle Sidebar feature (Ctrl+B): show/hide the sidebar, also accessible via command palette
- Show line and column numbers in editor footer: cursor position updates in real time (Ln X, Col Y); position button is clickable to open Goto Line modal
- Add Delete file/folder from sidebar: press Delete key on a selected node in the file tree
- Add Delete file/folder from command palette: delete any file or directory via command palette with improved modal UX (dynamic title, undo warning)
- Add file external change detection: polls mtime every 2 seconds, auto-reloads when no unsaved changes, shows warning notification when unsaved changes exist
- Add "Reload file" command palette entry for manual reload; shows discard confirmation modal when unsaved changes are present
- Add overwrite confirmation modal when saving over a file that was modified externally
- Add EditorConfig support: reads `.editorconfig` files from file directory up to `root = true`, applies indent style/size, charset, and end-of-line settings; supports full EditorConfig glob syntax (`*`, `**`, `?`, `[seq]`, `[!seq]`, `{s1,s2}`, `{n..m}`, `\x`)
- Add Resize Sidebar command in command palette: set sidebar width using absolute cells (`30`), relative offset (`+5`, `-3`), or percentage (`30%`); enforces min 5 / max app-width-5 cells, 1%–90% for percentages
- Add Multiple Cursors support: add extra cursors with `Ctrl+Alt+Down` / `Ctrl+Alt+Up`; type, backspace, delete, and Enter simultaneously at all cursor positions; backspace at column 0 merges each cursor's line with the line above; delete at end-of-line merges each cursor's line with the line below; press `Escape` or any movement key to return to single-cursor mode; active cursor count shown in footer as `Ln X, Col Y [N]`; also available via command palette ("Add cursor below" / "Add cursor above")
- Add Select All Occurrences feature (`Ctrl+Shift+L`): selects every occurrence of the current selection (or word under cursor) in the file using plain-text, case-sensitive search; sets primary selection to the first match and adds extra cursors at the start of each remaining match; also available via command palette ("Select all occurrences")
- Add more language detection: new file extensions (`mjs`, `cjs` → JavaScript; `svg`, `xhtml` → XML; `bash` → Bash) and filename-based detection for dotfiles (`.bashrc`, `.bash_profile`, `.bash_logout` → Bash); filename lookup takes priority over extension
- Add editor defaults with config file persistence: default indentation style/size, line ending, and encoding for new (untitled) files; settings stored in `$XDG_CONFIG_HOME/textual-code/settings.toml` (user-level) with optional project-level override in `{workspace}/.textual-code.toml`; "Set default indentation/line ending/encoding" commands available in the command palette; priority order: project config > user config > hardcoded defaults
- Add Add Next Occurrence feature (`Ctrl+D`, VS Code style): selects the word under cursor on first press (no selection); each subsequent press adds a cursor at the next occurrence of the current selection using plain-text, case-sensitive, wrap-around search; shows "All occurrences already selected" notification when all matches are already covered; also available via command palette ("Add next occurrence")
- Add horizontal Split View feature: open current file side-by-side in a right panel (`Ctrl+\`); close the right panel (`Ctrl+Shift+\`); right panel auto-closes when its last tab is closed; split actions also available via command palette ("Split editor right", "Close split", "Focus left/right split")
- Add Markdown Preview feature (`Ctrl+Shift+M`): toggle a live preview panel that renders the active left-split Markdown file (`.md`, `.markdown`, `.mkd`) in real time; updates on every keystroke; shows a placeholder when no Markdown file is open; compatible with Split View; also available via command palette ("Toggle markdown preview")
- Add Resize Split command in command palette: set the left split panel width using absolute cells (`50`), relative offset (`+10`, `-5`), or percentage (`40%`); enforces min 10 / max total-10 cells, 10%–90% for percentages; right panel fills remaining space automatically; shows error when no split is open
- Add syntax highlighting theme selection: choose from built-in themes (`monokai`, `dracula`, `github_light`, `vscode_dark`, `css`) via command palette ("Change syntax highlighting theme"); applies immediately to all open editors; persisted in `$XDG_CONFIG_HOME/textual-code/settings.toml` as `syntax_theme`; new editors inherit the saved default; default theme is `monokai`
- Add `Ctrl+Shift+Z` as a Redo keybinding (in addition to the existing `Ctrl+Y`)
- Add Word Wrap toggle: toggle soft word wrap for the active file via command palette ("Toggle word wrap"); set default word wrap for new files via command palette ("Set default word wrap"); persisted in `$XDG_CONFIG_HOME/textual-code/settings.toml` as `word_wrap`; default is `false`
- Add `--workspace` / `-w` CLI option to `tc`: override the sidebar root directory independently of the target file path, useful for monorepos where the file lives in a subdirectory but the sidebar should be rooted at the project root; exits with code 1 if the given path is not an existing directory

### Fixed

- Fix `SidebarResizeHandle` and `SplitResizeHandle` showing class name as vertical text: added `render()` to both handles so they display `│` (dim, vertically centered) instead of the default Widget class-name output; also added `pointer: ew-resize` / `pointer: ns-resize` CSS for the appropriate resize cursor on hover
- Fix extra cursors not rendering immediately after `Ctrl+D` / `Ctrl+Alt+Down` / `Ctrl+Alt+Up` until the next text edit: `add_cursor()` and `clear_extra_cursors()` now clear `_line_cache` so the cursor highlight is painted in the very next frame
- Fix cursor position button (`Ln X, Col Y`) being clipped when the column number reaches 10 or more: `#cursor_btn` now has `min-width: 20` in TCSS, reserving enough space for `Ln 9999, Col 9999`
- Fix external file change notification repeating every 2 seconds: notification is now shown once and persists until the user dismisses it; flag resets after saving or reloading
- Fix `OverwriteConfirmModalScreen` and `DiscardAndReloadModalScreen` rendering full-screen due to missing CSS; both modals now display as compact centred dialogs matching the style of other modals
- Hide "Save all" and "Close all" from the footer key bindings bar to reduce clutter (`Ctrl+Shift+S` / `Ctrl+Shift+W` still work)

## [0.0.2] - 2025-01-07

### Added

- Add basic text editing features

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/olivierlacan/keep-a-changelog/releases/tag/v0.0.2
