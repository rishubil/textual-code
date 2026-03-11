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

# Run unit/integration tests in parallel (fast, ~1 min)
uv run pytest tests/ -n auto -m "not serial"

# Run snapshot tests separately (serial, slower)
uv run pytest tests/ -m serial
```

## Architecture

**Entry point**: `src/textual_code/__init__.py` — typer-based CLI that parses args and launches the Textual app.

**Component hierarchy**:
```
TextualCode (App) — app.py
├── Sidebar — widgets/sidebar.py
│   ├── TabbedContent
│   │   ├── TabPane("Explorer", id="explorer_pane") → Explorer — widgets/explorer.py (wraps DirectoryTree)
│   │   └── TabPane("Search", id="search_pane") → WorkspaceSearchPane — widgets/workspace_search.py
├── MainView — app.py (manages split view + tab state)
│   └── Horizontal (id="split_container")
│       ├── TabbedContent (id="split_left")   ← always visible
│       │   └── TabPane(s) → CodeEditor — widgets/code_editor.py
│       │       ├── MultiCursorTextArea — widgets/multi_cursor_text_area.py
│       │       └── CodeEditorFooter (file path + language display)
│       ├── TabbedContent (id="split_right")  ← hidden until Ctrl+\
│       │   └── TabPane(s) → CodeEditor (same structure)
│       └── MarkdownPreviewPane (id="markdown_preview")  ← hidden until Ctrl+Shift+M
└── Footer (key bindings)
```

**Key files**:
- `app.py` — `TextualCode` (App) and `MainView` (tab manager); all file operation logic lives here
- `widgets/code_editor.py` — `CodeEditor` widget; owns file read/write/delete, tracks unsaved state via reactive properties
- `widgets/multi_cursor_text_area.py` — `MultiCursorTextArea(TextArea)` subclass; manages extra cursors, intercepts key events, renders additional cursor positions
- `widgets/markdown_preview.py` — `MarkdownPreviewPane` widget; renders live Markdown preview; `update_for(text, path)` method; shows placeholder for non-Markdown files
- `modals.py` — modal dialog screens (SaveAs, UnsavedChange, Delete confirmations)
- `commands.py` — command palette providers, created via factory functions that close over workspace path
- `config.py` — editor defaults: `load_editor_settings()` (merges hardcoded < user < project TOML), `save_user_editor_settings()`; user config at `$XDG_CONFIG_HOME/textual-code/settings.toml`, project config at `{workspace}/.textual-code.toml`
- `search.py` — pure workspace search logic: `WorkspaceSearchResult` dataclass, `search_workspace(path, query, use_regex)` skips binary/hidden files
- `widgets/workspace_search.py` — `WorkspaceSearchPane` widget; sidebar Search tab; posts `OpenFileAtLineRequested` on result selection
- `style.tcss` — all UI styling (Textual CSS)

**Communication patterns**:
- Child → Parent: custom Textual `Message` subclasses (e.g., `CodeEditor.Saved`, `CodeEditor.Closed`, `OpenFileRequested`)
- App reacts to these in `on_*` handlers in `app.py`
- State in `CodeEditor` is managed with Textual `reactive` properties; `watch_*` methods respond to changes

**Adding new commands**: create a factory function in `commands.py` returning a `Provider` subclass, then register it in `TextualCode.COMMANDS` in `app.py`.

**Adding new modals**: subclass `ModalScreen[ResultType]` in `modals.py`, define a result dataclass, call `self.dismiss(result)` on completion.

## Textual Official Documentation

When Textual framework behaviour (API, Widget, Screen, Worker, reactive, etc.) is uncertain, **always check the official docs via WebFetch**.

- **Docs domain**: `textual.textualize.io` (WebFetch permitted)
- Key references:
  - `https://textual.textualize.io/api/app/` — App · screen_stack · query_one behaviour
  - `https://textual.textualize.io/guide/screens/` — ModalScreen · push_screen · dismiss · screen_stack
  - `https://textual.textualize.io/guide/events/` — Message · on_* handlers · post_message · @on decorator
  - `https://textual.textualize.io/guide/reactivity/` — reactive · watch_* trigger conditions · equate
  - `https://textual.textualize.io/guide/workers/` — Worker · @work(exclusive=True) · AwaitComplete
  - `https://textual.textualize.io/guide/testing/` — pilot.pause() · run_test() · testing caveats
  - `https://textual.textualize.io/guide/input/` — BINDINGS · Binding · priority · action_*
  - `https://textual.textualize.io/guide/command_palette/` — CommandPalette · Provider · SystemCommand
  - `https://textual.textualize.io/guide/styles/` — TCSS styles · colours · layout
  - `https://textual.textualize.io/widgets/tabbed_content/` — TabbedContent · TabPane · active
  - `https://textual.textualize.io/widgets/directory_tree/` — DirectoryTree · reload() · Worker caveats
  - `https://textual.textualize.io/widgets/text_area/` — TextArea · replace() · Changed event

**No guessing**: if behaviour is unclear, check the docs before implementing.

## Language Convention

All code comments, docstrings, and documentation (including files in `docs/`) must be written in **English**.

## Key Conventions

- Python 3.12+ required; type hints used throughout
- Keyboard bindings defined as class-level `BINDINGS` lists on App/widget classes
- Language detection from file extension via `LANGUAGE_EXTENSIONS` dict in `code_editor.py`
- `MainView` tracks open panes per-split: `_pane_ids: dict[str, set[str]]` and `_opened_files: dict[str, dict[Path, str]]` keyed by `"left"` / `"right"`; `tabbed_content` property returns the active split's `TabbedContent`, so all existing methods route automatically
