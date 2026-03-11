# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
- Add Multiple Cursors support: add extra cursors with `Ctrl+Alt+Down` / `Ctrl+Alt+Up`; type, backspace, and delete simultaneously at all cursor positions; press `Escape` or any movement key to return to single-cursor mode; active cursor count shown in footer as `Ln X, Col Y [N]`; also available via command palette ("Add cursor below" / "Add cursor above")
- Add Select All Occurrences feature (`Ctrl+Shift+L`): selects every occurrence of the current selection (or word under cursor) in the file using plain-text, case-sensitive search; sets primary selection to the first match and adds extra cursors at the start of each remaining match; also available via command palette ("Select all occurrences")
- Add more language detection: new file extensions (`mjs`, `cjs` → JavaScript; `svg`, `xhtml` → XML; `bash` → Bash) and filename-based detection for dotfiles (`.bashrc`, `.bash_profile`, `.bash_logout` → Bash); filename lookup takes priority over extension
- Add editor defaults with config file persistence: default indentation style/size, line ending, and encoding for new (untitled) files; settings stored in `$XDG_CONFIG_HOME/textual-code/settings.toml` (user-level) with optional project-level override in `{workspace}/.textual-code.toml`; "Set default indentation/line ending/encoding" commands available in the command palette; priority order: project config > user config > hardcoded defaults

## [0.0.2] - 2025-01-07

### Added

- Add basic text editing features

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/olivierlacan/keep-a-changelog/releases/tag/v0.0.2
