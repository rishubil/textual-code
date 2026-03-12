# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add cross-split tab drag: drag a tab from one split panel and drop it onto a tab in the other split panel to move it; insertion position is determined by which half of the target tab the cursor lands on (before/after); unsaved content is preserved; if the same file is already open in the destination split, focus is moved there instead of duplicating; moving the last tab out of the right split automatically closes it
- Add tab reordering by drag within the same split: drag a tab header left or right to reorder it; dragged tab is highlighted with accent color during drag; reordering preserves editor state (cursor position, content, etc.)
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
