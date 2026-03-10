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
- Show line and column numbers in editor footer: cursor position updates in real time (Ln X, Col Y)
- Add Delete file/folder from sidebar: press Delete key on a selected node in the file tree
- Add Delete file/folder from command palette: delete any file or directory via command palette with improved modal UX (dynamic title, undo warning)
- Add file external change detection: polls mtime every 2 seconds, auto-reloads when no unsaved changes, shows warning notification when unsaved changes exist
- Add "Reload file" command palette entry for manual reload; shows discard confirmation modal when unsaved changes are present
- Add overwrite confirmation modal when saving over a file that was modified externally

## [0.0.2] - 2025-01-07

### Added

- Add basic text editing features

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/olivierlacan/keep-a-changelog/releases/tag/v0.0.2
