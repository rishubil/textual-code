# Feature Specification

Comprehensive feature documentation for Textual Code — a TUI-based code editor
designed to bring VS Code-like experience to the terminal.

## Maintenance Rules

- **When adding a new feature**: add an entry to the matching section in the appropriate detail file. If no section fits, create a new H2 section.
- **When modifying a feature**: update the corresponding section immediately. Stale docs are worse than no docs.
- **Sync with CHANGELOG**: every CHANGELOG "Added" entry must map to a features section. Use the verification checklist in Task 12 of the original plan.
- **Line limit**: each file must stay under 1800 lines. If a file exceeds this, split at H2 boundaries into a new file with the same prefix (e.g. `editor.md` → `editor-cursors.md`).

## Document Map

### [Editor Features](editor.md): file management, text editing, multiple cursors, find & replace

Core editing capabilities including file lifecycle, text manipulation, multi-cursor support, and in-file search/replace.

### [Workspace Features](workspace.md): workspace search, split view, tab management, sidebar & explorer

Workspace-level features including cross-file search, split editor views, tab drag-and-drop, and the file explorer sidebar.

### [Configuration Features](config.md): syntax highlighting, EditorConfig, encoding, settings, keybindings, themes

Language detection, EditorConfig compliance, encoding/line-ending management, application settings, keyboard customization, and UI themes.

### [UI Features](ui.md): markdown preview, image preview, footer status bar, CLI, drag-and-drop visuals

Markdown live preview, image file preview (PNG, JPG, GIF, BMP, WebP, TIFF via rich-pixels), status bar indicators, command-line interface, and drag-and-drop visual feedback.

### [VS Code Behavioral Differences](editor-vscode-differences.md): remaining gaps, accepted differences, fixed issues

Comprehensive record of how textual-code differs from VS Code, discovered during the VSCode test suite porting effort (PR #76). Covers undo/redo batching, case transforms, find/replace, word movement, cursor behavior, and unsupported features.

### [Implementation Internals](internals.md): design decisions, event flows, internal architecture

Implementation-level documentation covering WHY decisions, event flows, column math for multi-cursor, and other internal details. This is a reference for contributors, not a feature spec.
