# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Tabs**: directional/selective close tab commands via command palette — Close Other Editors, Close Editors to the Right, Close Editors to the Left, and Close Saved Editors; dirty unmounted editors are preserved to prevent silent data loss (#122)

### Fixed

- **Explorer**: git-modified and untracked filenames are now readable across all built-in themes — replaced background-calibrated `$warning`/`$success` with foreground-appropriate `$text-warning`/`$text-success` semantic color tokens (Fix #170)
- **Explorer**: git status colours (modified/untracked) no longer flicker off and back on when a file is saved — stale decorations are now kept visible until the background worker atomically replaces them, matching VS Code's behaviour (Fix #171)
- **Editor / Explorer**: all git subprocess calls now specify `encoding="utf-8"` and `errors="replace"` — fixes silent git diff gutter and git status failures on Windows for files with non-ASCII UTF-8 content (Fix #174)
- **Tests**: add explicit `encoding="utf-8"` to all `write_text()`/`read_text()` calls in tests — fixes 8 test failures on Windows with cp949 (Korean) locale; enable ruff `PLW1514` rule to prevent future regressions (Fix #177)
- **Tests**: fix flaky cross-split drag tests on Windows — add extra `await pilot.pause()` after tab activation to allow lazy editor remount to complete before subsequent actions (Fix #178)

## [0.4.0] - 2026-03-29

### Added

- **Highlighting**: fix incomplete syntax highlighting for TypeScript, TSX, and C++ — these languages now compose their highlight queries with base language rules (JavaScript for TS/TSX, C for C++) via a recursive composition system defined in `grammars/composition.json`, matching upstream tree-sitter grammar conventions
- **Performance**: Open File search (`Ctrl+O`) now respects `.gitignore` patterns by default using `ripgrep-rs`, reducing file scan from 78K files / 7s to ~234 files / 0.009s; a **Gitignore toggle checkbox** in the search bar lets users include gitignored files when needed; when gitignored files are included, fuzzy matching uses `rapidfuzz` for 14-140x faster search with a spinner indicator during matching (Fix #144)
- **Performance**: Workspace Search (sidebar find-in-files) now uses `ripgrep-rs` for both file enumeration and text matching, reducing search time from 2.5s to 0.01s with gitignore enabled; hidden files are now included/excluded based on the `show_hidden_files` setting (Fix #144)
- **Search**: display workspace search results as a collapsible tree grouped by file — each file node shows relative path and match count, with individual match lines as expandable children; replaces the previous flat list layout, matching VSCode's "Find in Files" tree view (Fix #127)
- **Explorer**: compact folder rendering — single-child directory chains display as a single node with a combined path label (e.g., `src/main/java`), matching VSCode's "Compact Folders" behavior; toggleable via command palette or `compact_folders` setting (Fix #128)
- **Tabs**: new tabs open immediately after the active tab instead of at the end, matching VSCode's default `openPositioning: 'right'` behavior (Fix #124)
- **Themes**: live preview when changing UI or syntax themes — selecting a theme in the dropdown immediately previews it; cancelling reverts to the original theme (Fix #104)
- **Shortcuts**: assign Ctrl+O as default keyboard shortcut for "Open File..." command — opens the file search modal from any context; displayed in the footer, command palette, and F1 shortcuts viewer (Fix #101)
- **Modals**: press Escape to dismiss non-destructive modals (Save As, Rename, Go to Line, Find, Replace, Change Language, Change Indentation, Change Line Ending, Change Encoding, Change Syntax Theme, Change Word Wrap, Change UI Theme, Sidebar Resize, Split Resize, Shortcut Settings, Footer Config, Show Shortcuts); destructive confirmation modals (Unsaved Changes, Delete, Overwrite, Discard & Reload, Replace All) are not affected (Fix #107)
- **Command Palette**: "Save Screenshot..." command — prompts for a file path and saves an SVG screenshot of the terminal; supports relative paths (resolved against workspace root) and auto-creates parent directories (Fix #102)

### Fixed

- **Explorer**: renaming a file to an empty or whitespace-only name now shows an error notification ("Invalid name: name cannot be empty.") instead of silently closing the modal (Fix #160)
- **Scripts**: `check-licenses.sh` now correctly classifies `rich-pixels` as MIT (allowed) via a manual override map for packages whose metadata lacks standard license fields (Fix #147)
- **Explorer**: `select_file` now reveals files at any directory depth — replaced frame-synchronous retry polling (`call_after_refresh`) with timer-based retries and depth-progress tracking so that deeply nested paths (12+ levels) are fully expanded instead of stopping mid-way after 10 retries (Fix #141)
- **Open File**: "Open File" (Ctrl+O) and Delete/Rename path actions now respect the `show_hidden_files` setting — hidden files (e.g., `.env`, `.gitignore`, `.github/`) appear in search results when the setting is enabled; `.git/` contents are always excluded (Fix #140)
- **Split**: split left/right/up/down in complex grid layouts (3+ panes with mixed directions) now correctly places the new pane adjacent to the focused editor group, instead of mounting it inside a nested sibling container (Fix #135)
- **Explorer**: clicking on an editor in a different split group now updates the Explorer sidebar selection and footer status bar; also works with keyboard navigation (F6/Shift+F6) (Fix #131)
- **Settings**: changing a single setting via UI now persists only the changed key (plus any previously explicit overrides) instead of writing all 17 default settings; preserves the cascading override mechanism (defaults → user → project) (Fix #132)
- **Editor**: extra-cursor selection highlights on the cursor line are now re-applied at the Strip level after cursor-line styling, restoring their visibility; cursor cells take priority over selection cells when they overlap (Fix #114)
- **Editor**: indentation guides and whitespace markers now use a higher-contrast foreground color on the cursor line, fixing invisibility caused by the overlay color being too close to the cursor-line highlight background in many themes (Fix #106)
- **Editor**: extra (multi) cursors on the same line as the primary cursor are now re-applied at the Strip level after cursor-line styling, restoring their visibility (Fix #105)
- **Editor**: "Close All Editors" now processes dirty editors before clean ones, so cancelling the unsaved-changes modal preserves all open tabs instead of losing clean tabs that were closed before the modal appeared (#100)

### Changed

- **CI**: add Python 3.13 and 3.14 to supported versions and CI test matrix; remove `.python-version` file (#97)
- **Dependencies**: add `exclude-newer = "P15D"` to `[tool.uv]` for reproducible dependency resolution; relax `ty` lower bound from 0.0.23 to 0.0.21 for compatibility (Fix #108)

## [0.3.0] - 2026-03-25

### Added

- **Settings**: show warning toast when configuration file parsing fails — if `settings.toml` or `keybindings.toml` contains invalid TOML syntax or cannot be read due to permission errors, a warning toast is displayed at startup identifying the file and error type; missing config files produce no warning (Fix #67)
- **Shortcuts**: per-command shortcut settings via F1 viewer — toggle command palette visibility and rebind keys; dedicated footer configuration modal with reorderable, toggleable list (Fix #28)
- **Footer**: per-area footer shortcut configuration — each focus area (editor, explorer, search, image preview, markdown preview) can have its own shortcut display order; area selector dropdown in the footer config modal; default action orders per area (Fix #36)
- **Settings**: "Open keybindings" command palette entry to open the keybindings.toml config file directly in the editor
- **Image Preview**: open image files (.png, .jpg, .jpeg, .gif, .bmp, .webp, .tiff, .tif) in a terminal preview pane using rich-pixels half-cell rendering; loading spinner during render; 10 MB file size cap; never upscales beyond 1:1 pixel ratio; re-renders on resize with debounce (Fix #12)
- **Editor**: VS Code-style line paste — when pasting text that was copied or cut without a selection, the line is inserted above the current cursor line instead of at the cursor position; cursor follows the original line down; metadata is shared across tabs and auto-invalidated when clipboard changes externally (Fix #39)
- **Editor**: git diff gutter indicators — display colored markers in the line number gutter to show git changes: green `▎` for added lines, yellow `▎` for modified lines, red `▔`/`▁` for deleted line positions; diff computed against HEAD via background worker; updates live on each keystroke; respects `show_git_status` setting (Fix #41)
- **Editor**: indentation guides — display vertical `│` guide lines at each indent level within leading whitespace; adapts to dark/light themes; toggleable per-file via command palette ("Toggle indentation guides"); configurable via `show_indentation_guides` setting (default: `true`) (Fix #40)
- **Editor**: sort selected lines — sort selected lines alphabetically (ascending) or in reverse order (descending) via command palette ("Sort lines ascending" / "Sort lines descending"); case-sensitive sorting matching VS Code default; supports multi-cursor with merged ranges (Fix #37)
- **Editor**: transform selected text case — convert selected text to uppercase or lowercase via command palette ("Transform to uppercase" / "Transform to lowercase"); no default keybinding (Fix #38)
- **Editor**: render whitespace — display invisible characters as visible markers: spaces as `·` (middle dot), tabs as `→` (arrow); four modes: `none` (default), `all`, `boundary` (leading + trailing), `trailing`; select mode via command palette ("Set render whitespace"); configurable via `render_whitespace` setting; coexists with indentation guides (guides take priority at guide positions) (Fix #59)
- **Search**: Enter key support in all search input fields — pressing Enter in the find bar replace input triggers single Replace; pressing Enter in workspace search include/exclude filter inputs triggers search execution (Fix #60)
- **Input**: standard editing shortcuts in text input widgets — Ctrl+A selects all text (instead of moving cursor to home); Ctrl+D is suppressed when an Input widget has focus to prevent unintended "add next occurrence" action (Fix #54)
- **Search**: confirmation modal before workspace Replace All — clicking Replace All now shows a confirmation dialog displaying the number of affected files and occurrences, plus a patch-style diff preview of the first match with syntax-highlighted red/green coloring; match counting runs in a background thread to keep the UI responsive; zero-match queries show a "No matches found" status without opening the modal (Fix #61)

- **Shortcuts**: unified command registry — all command palette functions can now be assigned keyboard shortcuts via the F1 viewer; all shortcut-only actions now appear in the command palette; "Unbind" button to remove existing shortcuts; dynamic key hints in palette descriptions reflect custom bindings; single source of truth (`command_registry.py`) prevents commands from drifting out of sync (Fix #53)

- **Editor**: Ctrl+Backspace and Ctrl+Delete word deletion — delete from cursor to previous/next word boundary; works with multi-cursor; requires terminal with enhanced keyboard protocol support for Ctrl+Backspace (Fix #77)
- **Editor**: all 7 VS Code case transforms — added title case, snake_case, camelCase, kebab-case, PascalCase via command palette; collapsed cursor now auto-selects word under cursor before transforming (Fix #78, Fix #79)
- **Editor**: Find Previous — search backward via Shift+Enter in find bar or ↑ Prev button; wraps around to last match when no match before cursor
- **Command Palette**: remove Textual built-in commands — Textual's default system commands (Theme, Keys, Maximize/Minimize, Screenshot) are excluded from the command palette; only project-defined commands appear (Fix #87)
- **App**: double Ctrl+Q force quit — pressing Ctrl+Q twice within 1 second exits immediately, bypassing the unsaved-changes modal; safety mechanism to ensure the user can always quit
- **Command Palette**: show Ctrl+Q shortcut hint on Quit command — add `default_key="ctrl+q"` to the quit entry in `COMMAND_REGISTRY` so the keyboard shortcut appears in the command palette description; add guard test to catch future Textual base binding ↔ registry mismatches
- **UI**: compact find/replace bar buttons — replace text labels with responsive icons (↑, ↓, All, ↪, 🔄) that switch between icon-only and icon+text based on bar width; add tooltips for discoverability; color-code buttons by importance (primary blue for actions, warning yellow for Replace All, subtle tint for navigation); mirrors the sidebar's `_BTN_LABELS` responsive pattern (Fix #84)

- **Editor**: Ctrl+Home / Ctrl+End — jump to start/end of document; Ctrl+Shift+Home/End extends selection to document boundaries (Fix #63)
- **Editor**: VS Code-style smart Home key — toggles between first non-whitespace character and column 0 (Fix #63)
- **Tests**: 257 test cases ported from VSCode's editor test suite covering cursor movement, text editing, selection, multi-cursor, undo/redo, word movement, word selection, case transforms, sort lines, move lines, and find/replace (Fix #63)

### Fixed

- **Editor**: fix multi-cursor vertical movement diverging from single-cursor — up/down with extra cursors now delegates to Textual's `DocumentNavigator`, matching single-cursor behavior for sticky column, up-at-first-line → (0,0), and down-at-last-line → end of line (Fix #80)
- **Editor**: fix Ctrl+D / Ctrl+Shift+L matching — Ctrl+D from collapsed cursor now uses word-boundary case-sensitive matching (matching VSCode); from existing selection uses case-insensitive substring matching (Fix #63)
- **Editor**: fix regex find/replace `^` and `$` not matching line boundaries — added `re.MULTILINE` flag when regex mode is enabled (Fix #63)
- **Editor**: fix regex replace with lookaheads — replace now matches against full document text instead of isolated selection, preserving lookahead/lookbehind context (Fix #63)

- **Sidebar**: fix horizontal scrollbar hidden by footer — add `padding-bottom: 1` to the Sidebar so its content area does not extend into the dock-bottom Footer row, preventing the Footer from occluding horizontal scrollbars in both the Explorer tree and search results (Fix #70)
- **Search**: enable horizontal scrolling in workspace search results — override `VerticalScroll`'s default `overflow-x: hidden` with `auto` on the results `ListView`, and allow `ListItem` children to expand beyond the container width so long result lines remain accessible (Fix #70)

- **Editor**: fix copy/paste working incorrectly on Windows — override `_on_paste` (bracketed paste event handler) in `MultiCursorTextArea` to normalize CRLF line endings, sync with the local clipboard, and delegate to `action_paste` so VS Code line-paste behavior and whitespace preservation work correctly on terminals that intercept Ctrl+V; use trailing-whitespace-tolerant comparison to handle Windows Terminal stripping trailing spaces and newlines from clipboard text (Fix #58)
- **Command Palette**: prevent command palette from opening when a modal dialog is already displayed (Fix #34)
- **Testing**: disable cursor blinking in snapshot tests for deterministic SVG capture; wrap `snap_compare` fixture to set `cursor_blink = False` on all `TextArea` and `Input` widgets (Fix #35)
- **Performance**: fix PathSearchModal UI slowness with many files — replace `clear_options()` + per-item `add_option()` loop (N+1 render cycles) with single `set_options()` call (1 render cycle); remove redundant display refresh on every scan chunk to eliminate repeated OptionList rebuilds during file scanning (Fix #52)
- **Editor**: show indentation guides on the first indentation level — guide lines now start at column 0 instead of skipping the first indent level (Fix #55)
- **Editor**: fix render whitespace setting not preserved across tab switches — propagate `render_whitespace` to the underlying text area on mount; replace cycling command with selectable mode picker via command palette ("Set render whitespace") that updates the session default (Fix #65)
- **Editor**: fix whitespace markers and indentation guides rendered at wrong positions when horizontally scrolling with word wrap disabled — add scroll offset to viewport-to-document column mapping in `_inject_whitespace_rendering` and `_inject_indentation_guides` (Fix #69)

- **Command Palette**: align command titles with VS Code conventions — apply Title Case to all command titles, adopt VS Code terminology ("Editor" instead of "file/tab", "Group" instead of "split"), add ellipsis (`...`) to commands that open dialogs/pickers, use plain words for transform case names ("Snake Case" instead of "snake_case"); update descriptions and binding descriptions for consistency (Fix #85)
- **Breaking**: rename all command action IDs to match new titles — remove `_cmd` suffixes, adopt VS Code terminology in IDs (e.g. `close` → `close_editor`, `new_editor` → `new_untitled_file`, `close_split` → `close_editor_group`); existing `keybindings.toml` custom bindings using old action IDs will need manual update (Fix #85)
- **Tab Drag**: fix `NoWidget` crash when dragging a tab to the screen edge — `get_widget_at` raises when cursor coordinates fall outside all widget regions; wrap all three call sites (`_update_drop_target`, `on_mouse_down`, `on_mouse_up`) with a safe helper that returns `(None, None)` instead of crashing

### Changed

- **Performance**: replace CommandPalette with dedicated `PathSearchModal` for file search, delete, rename, and move palettes; UI matches CommandPalette look & feel (top-aligned, semi-transparent overlay, search icon, keyboard navigation); fuzzy matching runs in a background thread with class-level cache and automatic dirty-flag invalidation; generation counter prevents stale search results from overwriting current display
- **Dependencies**: update lower-bound versions in `pyproject.toml` to match resolved versions from `uv.lock`; prevents installation of incompatible old versions (Fix #33)

## [0.2.0] - 2026-03-21

### Added

- **CLI**: `--version` flag to print the installed version and exit
- **Editor**: Shift+PageUp/PageDown to select while paging up/down (single cursor and multi-cursor)
- **Explorer**: create file/directory dialog pre-fills with the currently selected folder's relative path
- **Explorer/Editor**: rename files and folders with F2 key, command palette, or "Rename file" system command; stem pre-selected in modal; directory rename updates all open tabs
- **Explorer**: move files and folders to different paths via command palette ("Move file", "Move file or directory"); destination folder selected via fuzzy-searchable directory picker that includes dot-prefixed directories (`.github/`, `.vscode/`, etc.) but excludes `.git`; file/folder keeps its original name; workspace boundary validation; directory move updates all open tabs
- **Explorer**: copy/cut/paste files and folders with Ctrl+C/X/V when explorer is focused; also accessible via command palette ("Copy file or directory", "Cut file or directory", "Paste file or directory"); name conflicts auto-resolved with " copy" suffix; cut updates open tabs; copy preserves clipboard for repeated paste
- **Docs**: Troubleshooting section in README for keyboard shortcut issues (`textual keys`)
- **Docs**: EditorConfig priority and property source reference in settings guide (Fix #17)

### Changed

- **Editor**: CRLF/CR line ending warning now appears when copying, cutting, or pasting multiline text instead of when opening the file; warning appears once per tab session and resets when the line ending changes (Fix #10)
- **Explorer**: startup performance improved — gitignore patterns now load lazily per-directory instead of scanning the entire workspace; git status loads in a background thread; directory listing uses `os.scandir` to eliminate redundant stat calls
- **Footer**: shortcut bar now displays key bindings in a fixed, deterministic order (Save → Find → Replace → Goto line → Close tab → New file → Toggle sidebar) regardless of focus state
- **Performance**: footer status bar now batches all reactive property updates into a single layout refresh on tab switch, reducing redundant repaints (Fix #4)
- **Performance**: file-change and EditorConfig polling centralized to one shared timer; only the active editor is polled regardless of how many tabs are open (Fix #4)
- **Performance**: inactive editor tabs are lazily unmounted from the DOM; DOM widget count stays constant regardless of tab count, eliminating per-tab keystroke latency growth (Fix #4)

### Fixed

- **Command Palette**: app no longer crashes when file browsing encounters inaccessible files due to permission errors or other OS-level issues (Fix #9)
- **Settings**: config save operations (keybindings, user/project editor settings) now handle I/O errors gracefully instead of crashing
- **Editor**: EditorConfig file reading handles I/O errors without crashing
- **Tabs**: title-change events arriving after a tab is removed no longer crash the app (race condition in split/close operations)
- **Split View**: edge-zone drag (split down/up/left/right) from an existing multi-pane split now correctly creates a new sub-split instead of moving the tab to the adjacent pane
- **Editor**: mouse click now clears multi-cursor mode (single, double, and triple click all dismiss extra cursors)
- **Editor**: Ctrl+D (add next occurrence) now scrolls the viewport to show the newly added cursor when it is off-screen
- **Tabs**: switching back to a tab with a custom tree-sitter language (Kotlin, TypeScript, C, etc.) no longer crashes with `LanguageDoesNotExist` (Fix #15)
- **Footer**: status bar buttons (language, encoding, line ending, indentation) now properly resize when switching between editor tabs with different values (Fix #20)
- **Workspace Replace**: find-and-replace no longer doubles line endings on Windows by converting `\n` to `\r\n` twice (Fix #14)
- **Split View**: moving a tab to another split no longer crashes with `ValueError: No Tab with id` on Windows due to a race condition between pane addition and tab activation (Fix #14)
- **App**: accessing the sidebar property during app shutdown no longer crashes with `IndexError` when the screen stack is empty (Fix #14)
- **Tests**: user's local editor settings (theme, indent size, etc.) no longer leak into test execution, preventing false test failures on developer machines (Fix #16)
- **Tabs**: active tab underline highlight bar now spans the full tab width when opening files with long names (previously stuck at placeholder width for 2nd+ tabs)

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

[unreleased]: https://github.com/rishubil/textual-code/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/rishubil/textual-code/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/rishubil/textual-code/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rishubil/textual-code/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/rishubil/textual-code/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/rishubil/textual-code/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/rishubil/textual-code/releases/tag/v0.0.2
