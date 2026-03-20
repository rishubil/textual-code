# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **CLI**: `--version` flag to print the installed version and exit
- **Editor**: Shift+PageUp/PageDown to select while paging up/down (single cursor and multi-cursor)
- **Explorer**: create file/directory dialog pre-fills with the currently selected folder's relative path
- **Explorer/Editor**: rename files and folders with F2 key, command palette, or "Rename file" system command; stem pre-selected in modal; directory rename updates all open tabs
- **Explorer**: move files and folders to different paths via command palette ("Move file", "Move file or directory"); destination folder selected via fuzzy-searchable directory picker that includes dot-prefixed directories (`.github/`, `.vscode/`, etc.) but excludes `.git`; file/folder keeps its original name; workspace boundary validation; directory move updates all open tabs
- **Explorer**: copy/cut/paste files and folders with Ctrl+C/X/V when explorer is focused; also accessible via command palette ("Copy file or directory", "Cut file or directory", "Paste file or directory"); name conflicts auto-resolved with " copy" suffix; cut updates open tabs; copy preserves clipboard for repeated paste
- **Docs**: Troubleshooting section in README for keyboard shortcut issues (`textual keys`)

### Changed

- **Explorer**: startup performance improved — gitignore patterns now load lazily per-directory instead of scanning the entire workspace; git status loads in a background thread; directory listing uses `os.scandir` to eliminate redundant stat calls
- **Footer**: shortcut bar now displays key bindings in a fixed, deterministic order (Save → Find → Replace → Goto line → Close tab → New file → Toggle sidebar) regardless of focus state
- **Performance**: footer status bar now batches all reactive property updates into a single layout refresh on tab switch, reducing redundant repaints (Fix #4)
- **Performance**: file-change and EditorConfig polling centralized to one shared timer; only the active editor is polled regardless of how many tabs are open (Fix #4)
- **Performance**: inactive editor tabs are lazily unmounted from the DOM; DOM widget count stays constant regardless of tab count, eliminating per-tab keystroke latency growth (Fix #4)

### Fixed

- **Command Palette**: app no longer crashes when file browsing encounters inaccessible files due to permission errors or other OS-level issues (Fix #9)
- **Settings**: config save operations (keybindings, user/project editor settings) now handle I/O errors gracefully instead of crashing
- **Editor**: EditorConfig file reading handles I/O errors without crashing
- **Split View**: edge-zone drag (split down/up/left/right) from an existing multi-pane split now correctly creates a new sub-split instead of moving the tab to the adjacent pane
- **Editor**: mouse click now clears multi-cursor mode (single, double, and triple click all dismiss extra cursors)
- **Editor**: Ctrl+D (add next occurrence) now scrolls the viewport to show the newly added cursor when it is off-screen

## [0.1.1] - 2026-03-18

### Fixed

- Wheel build only included `.scm` grammar files, excluding all Python source — caused `ModuleNotFoundError` when installed via `pip install` or `uv tool install`

## [0.1.0] - 2026-03-18

### Added

- **Editor**: multiple cursors with Ctrl+Alt+Up/Down, add next occurrence (Ctrl+D), select all occurrences (Ctrl+Shift+L); multi-cursor movement, selection, typing, and editing all work simultaneously; move line up/down (Alt+Up/Down), scroll viewport (Ctrl+Up/Down), select all (Ctrl+A), double/triple click word/line selection, Ctrl+C/X copies/cuts current line when no selection, Tab/Shift+Tab indent/dedent, Ctrl+Shift+Z redo
- **Find & Replace**: inline find/replace bar (Ctrl+F/Ctrl+H) with regex, case-sensitivity, and Select All matches for multi-cursor editing; workspace-wide search (Ctrl+Shift+F) and Replace All with gitignore, file include/exclude filters, case-sensitivity toggle, and background search with loading indicator
- **Split view**: unlimited nested horizontal/vertical splits via recursive tree structure; split in any direction (Ctrl+\\, command palette); close split (Ctrl+Shift+\\); drag-and-drop tabs between splits with 4-direction edge zones and visual drop hints; drag resize handles; toggle split orientation; directional tab move commands; move tab to other split (Ctrl+Alt+\\); live text sync between split editors viewing the same file; focus cycling with F6/Shift+F6
- **Explorer**: create file/directory (Ctrl+N/Ctrl+D in sidebar), delete file/folder (Delete key); toggle hidden files, dim gitignored files, dim hidden files, git status highlighting (modified in yellow, untracked in green with folder inheritance); auto-refresh on workspace file changes and git status changes; cursor sync with active editor tab; responsive emoji icons that collapse at narrow widths
- **File handling**: new file (Ctrl+N), Save As, reload file from disk; expanded encoding auto-detection (40+ encodings including CJK via charset-normalizer); binary file detection; EditorConfig support with auto-reload on `.editorconfig` changes; `trim_trailing_whitespace` and `insert_final_newline` applied at save time; configurable line endings; free-form indentation size input; external file change detection with auto-reload or overwrite confirmation
- **Tabs & navigation**: command palette (Ctrl+Shift+P) for quick access to all commands; tab reorder by drag, cross-split tab drag, Goto Line (Ctrl+G), copy relative/absolute path, close all (Ctrl+Shift+W), save all (Ctrl+Shift+S), toggle sidebar (Ctrl+B), sidebar drag resize, resize sidebar/split via command palette
- **Markdown**: live preview in tab (Ctrl+Shift+M) with debounced auto-updates, GFM support, keyboard scrolling; preview closes with source editor
- **Themes**: UI theme selection from 20 built-in themes (nord, gruvbox, dracula, etc.); syntax highlighting theme selection (monokai, dracula, github_light, vscode_dark, css)
- **Keyboard shortcuts**: view and customize all key bindings (F1), shortcut hints in command palette, custom bindings saved to keybindings.toml
- **Configuration**: user-level and project-level settings persistence (TOML) with project taking priority; open settings commands; save-level selector (User/Project) in theme and default settings dialogs; `sidebar_width`, `path_display_mode`, `warn_line_ending`, word wrap toggle and default settings; `--workspace` / `-w` CLI option for overriding sidebar root directory
- **Language support**: syntax highlighting for 10 additional languages (TypeScript, TSX, C, C++, Ruby, Kotlin, Lua, PHP, Dockerfile, Makefile) via tree-sitter-language-pack; extended file type detection for dotfiles and additional extensions
- **Footer**: clickable file path copies to clipboard; path display mode toggle (absolute/relative); cursor position with multi-cursor count; clickable language, encoding, line ending, and indentation indicators; dynamic column sizing

### Changed

- Default word wrap changed to enabled
- Footer path truncation indicator visually distinct from actual path characters

## [0.0.2] - 2025-01-07

### Added

- Add basic text editing features

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/rishubil/textual-code/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/rishubil/textual-code/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/rishubil/textual-code/releases/tag/v0.0.2
