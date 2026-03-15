# TODO

Issues found during visual snapshot inspection.

## [A] Footer: language name truncated

**Files**: `test_snapshot_app_with_file`, `test_snapshot_unsaved_marker`, `test_snapshot_multi_cursor`

Footer last column (`auto` width) truncates `python` to `pytho`. The 6-column grid
(`1fr auto auto auto auto auto`) may not allocate enough space for the language button.

## [B] Overwrite confirm modal: body text truncated

**File**: `test_snapshot_overwrite_confirm_modal`

Modal body reads "The file was modified externally. Overwrite with your" — the remainder
("changes?") is missing. The dialog width or text wrapping is too narrow.

## [E] Dockerfile highlighting: missing space between keyword and argument

**File**: `test_snapshot_dockerfile_highlighting`

Dockerfile instructions render as `FROMubuntu:22.04`, `RUNapt-get ...` — the space
between the keyword span and the argument text is lost in the highlighting render.

## [F] Markdown preview: missing space after bold text

**File**: `test_snapshot_markdown_preview_open`

`"This is a **Markdown** preview."` renders as `"Markdownpreview."` — space after the
closing bold span is dropped by the Markdown renderer.
