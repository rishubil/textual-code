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
- Add file external change detection: polls mtime every 2 seconds, auto-reloads when no unsaved changes, shows warning notification when unsaved changes exist
- Add "Reload file" command palette entry for manual reload; shows discard confirmation modal when unsaved changes are present
- Add overwrite confirmation modal when saving over a file that was modified externally

## [0.0.2] - 2025-01-07

### Added

- Add basic text editing features

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/olivierlacan/keep-a-changelog/releases/tag/v0.0.2
