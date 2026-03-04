# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Textual Code** is a TUI-based code editor written in Python, designed as a lightweight vi/nano/Emacs alternative for quick edits on remote servers. It uses the [Textual](https://textual.textualize.io/) framework.

## Commands

**Package manager**: `uv`

```bash
# Run the app in dev mode (with hot reload + devtools)
uv run textual run --dev textual_code:main

# Open the Textual devtools console (run in a separate terminal first)
uv run textual console

# Run with a specific file or directory
uv run textual run --dev textual_code:main -- [path]

# Lint and format (also runs automatically via pre-commit)
uv run ruff check --fix src/
uv run ruff format src/
```

## Architecture

**Entry point**: `src/textual_code/__init__.py` — typer-based CLI that parses args and launches the Textual app.

**Component hierarchy**:
```
TextualCode (App) — app.py
├── Sidebar — widgets/sidebar.py
│   └── Explorer — widgets/explorer.py (wraps DirectoryTree)
├── MainView — app.py (manages tab state)
│   └── TabbedContent
│       └── TabPane(s)
│           └── CodeEditor — widgets/code_editor.py
│               ├── TextArea (syntax-highlighted editor)
│               └── CodeEditorFooter (file path + language display)
└── Footer (key bindings)
```

**Key files**:
- `app.py` — `TextualCode` (App) and `MainView` (tab manager); all file operation logic lives here
- `widgets/code_editor.py` — `CodeEditor` widget; owns file read/write/delete, tracks unsaved state via reactive properties
- `modals.py` — modal dialog screens (SaveAs, UnsavedChange, Delete confirmations)
- `commands.py` — command palette providers, created via factory functions that close over workspace path
- `style.tcss` — all UI styling (Textual CSS)

**Communication patterns**:
- Child → Parent: custom Textual `Message` subclasses (e.g., `CodeEditor.Saved`, `CodeEditor.Closed`, `OpenFileRequested`)
- App reacts to these in `on_*` handlers in `app.py`
- State in `CodeEditor` is managed with Textual `reactive` properties; `watch_*` methods respond to changes

**Adding new commands**: create a factory function in `commands.py` returning a `Provider` subclass, then register it in `TextualCode.COMMANDS` in `app.py`.

**Adding new modals**: subclass `ModalScreen[ResultType]` in `modals.py`, define a result dataclass, call `self.dismiss(result)` on completion.

## Key Conventions

- Python 3.12+ required; type hints used throughout
- Keyboard bindings defined as class-level `BINDINGS` lists on App/widget classes
- Language detection from file extension via `LANGUAGE_EXTENSIONS` dict in `code_editor.py`
- `MainView` tracks open panes in `_panes: dict[str, str]` (pane_id → file path)
