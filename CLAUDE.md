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

## Textual 공식 문서 참조

Textual API, Widget, Screen, Worker, reactive 등 프레임워크 동작이 불확실할 때 **반드시 공식 문서를 WebFetch로 확인**하세요.

- **문서 도메인**: `textual.textualize.io` (WebFetch 허가됨)
- 주요 참조:
  - `https://textual.textualize.io/api/app/` — App · screen_stack · query_one 동작
  - `https://textual.textualize.io/guide/screens/` — ModalScreen · push_screen · dismiss · screen_stack
  - `https://textual.textualize.io/guide/events/` — Message · on_* 핸들러 · post_message · @on 데코레이터
  - `https://textual.textualize.io/guide/reactivity/` — reactive · watch_* 트리거 조건 · equate
  - `https://textual.textualize.io/guide/workers/` — Worker · @work(exclusive=True) · AwaitComplete
  - `https://textual.textualize.io/guide/testing/` — pilot.pause() · run_test() · 테스트 주의사항
  - `https://textual.textualize.io/guide/input/` — BINDINGS · Binding · priority · action_*
  - `https://textual.textualize.io/guide/command_palette/` — CommandPalette · Provider · SystemCommand
  - `https://textual.textualize.io/guide/styles/` — TCSS 스타일 · 색상 · 레이아웃
  - `https://textual.textualize.io/widgets/tabbed_content/` — TabbedContent · TabPane · active
  - `https://textual.textualize.io/widgets/directory_tree/` — DirectoryTree · reload() · Worker 주의
  - `https://textual.textualize.io/widgets/text_area/` — TextArea · replace() · Changed 이벤트

**추측 금지**: 동작이 불명확하면 문서를 먼저 확인하고 구현하세요.

## Key Conventions

- Python 3.12+ required; type hints used throughout
- Keyboard bindings defined as class-level `BINDINGS` lists on App/widget classes
- Language detection from file extension via `LANGUAGE_EXTENSIONS` dict in `code_editor.py`
- `MainView` tracks open panes in `_panes: dict[str, str]` (pane_id → file path)
