# TODO

Issues found during visual snapshot inspection.

## [E] Dockerfile highlighting: missing space between keyword and argument

**File**: `test_snapshot_dockerfile_highlighting`

Dockerfile instructions render as `FROMubuntu:22.04`, `RUNapt-get ...` — the space
between the keyword span and the argument text is lost in the highlighting render.

## [F] Markdown preview: missing space after bold text

**File**: `test_snapshot_markdown_preview_open`

`"This is a **Markdown** preview."` renders as `"Markdownpreview."` — space after the
closing bold span is dropped by the Markdown renderer.
