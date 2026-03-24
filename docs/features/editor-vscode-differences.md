# VS Code Behavioral Differences

Comprehensive record of how textual-code's editor behavior differs from VS Code,
discovered during the VSCode test suite porting effort (PR #76, issue #63).
257 tests were ported from VS Code's editor test suite across 11 areas.

This document covers both **remaining differences** (accepted or not yet implemented)
and **differences that were fixed** during the porting effort, for historical reference.

## Undo/Redo: no space-based undo stops, no delete-direction boundary

Textual's `EditHistory` batches undo differently from VS Code in three ways:

### No space-based undo stops

VS Code creates an undo boundary when a space character is typed mid-word.
Typing `"first and interesting"` produces 3 undo groups in VS Code (`"first"`, `" and"`, `" interesting"`).
Textual treats all consecutive character insertions as one group regardless of whitespace.
A single Ctrl+Z undoes the entire typing sequence.

**Why:** Textual's `EditHistory` creates new undo batches only on these triggers:

- `_force_end_batch` (cursor movement via arrow keys / home / end / click, redo)
- Edit contains newline (in inserted or replaced text)
- Multi-character paste (edit inserts >1 character at once)
- `is_replacement` flag changes (typing → backspace/delete transition)
- Timer expired (2-second gap between edits)
- Maximum character count reached (100 characters in a batch)

There is no character-content-based checkpoint (spaces, punctuation, etc.).

### No delete-left vs delete-right boundary

VS Code creates an undo boundary when switching between Backspace and Delete (different edit directions).
Textual treats all consecutive deletes as one group regardless of direction.

**Why:** Textual's `EditHistory` distinguishes only between "insertion" and "deletion" (`is_replacement`), not between delete-left and delete-right.

### Selection replace creates extra undo boundary

When typing over a selection, VS Code treats the entire replacement as one undo group.
Textual splits it: the first keystroke (which replaces the selection, `is_replacement=True`) and subsequent keystrokes (pure insertion, `is_replacement=False`) become separate undo groups.

**Severity:** Low. These are edge cases that rarely affect normal editing workflows.

**Source:** `tests/test_vscode_text_editing.py`, `tests/test_vscode_undo_redo.py`

## Case Transform: collapsed cursor no-op, only upper/lower available

### Collapsed cursor does not auto-select word

VS Code auto-selects the word under the cursor when a case transform command is invoked
with no active selection (e.g., cursor at col 3 in `"hello world"` + uppercase = `"HELLO world"`).
textual-code treats collapsed-cursor transforms as a no-op; the user must explicitly select text first.

### Only 2 of 7 case transforms available

VS Code provides 7 case transforms: uppercase, lowercase, title case, snake_case, camelCase, kebab-case, PascalCase.
textual-code supports only uppercase and lowercase via the command palette.

**Severity:** Medium. Missing transforms are a feature gap, not a behavioral conflict.

**Source:** `tests/test_vscode_case_transform.py`

## Find/Replace: `\1` capture syntax, no find-previous, no preserve-case

### Capture group syntax differs — `\1` (Python) vs `$1` (VS Code)

Regex replace uses Python's `re.sub` convention (`\1`, `\2`) for backreferences.
VS Code uses JavaScript convention (`$1`, `$2`).
This is a platform difference that would require a syntax translation layer to resolve.

### Find Previous not available

VS Code supports `moveToPrevMatch` (Shift+Enter in find bar or a dedicated button) to search backward.
textual-code only supports forward search (Enter / Next button) with wrap-around.

### Preserve Case in replace not available

VS Code supports a "Preserve Case" toggle in the replace bar (e.g., replacing `"hello"` → `"goodbye"` while preserving the case pattern: `"Hello"` → `"Goodbye"`, `"HELLO"` → `"GOODBYE"`).
textual-code does not have this feature.

**Severity:** Low to medium. Capture syntax is a platform convention; find-previous and preserve-case are feature gaps.

**Source:** `tests/test_vscode_find_replace.py`

## Word Movement: operator grouping, emoji boundaries

### Operator characters create extra stops

VS Code classifies characters into three groups (word, separator, whitespace) and groups consecutive same-type characters as one "word" for Ctrl+Left/Right.
For example, `+=` is one stop in VS Code (both are separators).

textual-code uses `_WORD_PATTERN = re.compile(r"(?<=\W)(?=\w)|(?<=\w)(?=\W)")`, which stops at every `\w`/`\W` boundary.
So `+=` produces two stops (before `+`, before `=`).
Same applies to `*/`, `-3`, etc.

### Emoji treated as separate word boundary token

VS Code treats `Line🐶` as one word unit.
textual-code treats the emoji as a separate `\W` token because Python's `\w` pattern does not match emoji characters, creating extra cursor stops around emoji.

**Severity:** Low. Affects only navigation over operator sequences and emoji, not common editing patterns.

**Source:** `tests/test_vscode_word_movement.py`

## Cursor Movement: sticky column reset at first line

### Up at first line resets sticky column immediately

VS Code: pressing Up on the first line moves the cursor to column 0 but *remembers* the original column.
A subsequent Down press restores the original column.
Only pressing Up *twice* at the first line resets the sticky column memory.

textual-code: pressing Up on the first line moves the cursor to (0, 0) and *immediately* resets the sticky column.
The next Down press goes to column 0 instead of restoring the original column.

**Why:** Textual's `DocumentNavigator.get_location_above()` resets `last_x_offset` when the cursor physically changes position to (0, 0).

**Severity:** Low. Minor edge case at document boundary.

**Source:** `tests/test_vscode_cursor_movement.py` (VS Code issue #44465)

## Word Selection: single-cursor vs multi-cursor cross-line behavior

Ctrl+Shift+Left/Right has subtly different cross-line behavior depending on cursor mode:

- **Single cursor** (delegates to Textual native `action_cursor_word_left(select=True)`): crosses to the END of the previous line first, then on the next press moves to a word boundary.
- **Multi-cursor** (uses `_move_all_cursors` + `_move_location`): crosses directly to the nearest word boundary on the adjacent line, skipping the line-end intermediate stop.

Both approaches produce correct final results, but the intermediate cursor position differs by one step when crossing a line boundary.

**Severity:** Low. Only observable in single-step comparison; end results are functionally equivalent.

**Source:** `tests/test_vscode_word_selection.py`

## Features Not Supported: auto-indent, auto-close, comments, word delete

The following VS Code editor features are not implemented in textual-code.
These were identified by mapping VS Code test files to our editor capabilities:

| VS Code Feature | Test Source | Notes |
|-----------------|-----------|-------|
| Auto-indent on Enter | `cursor.test.ts` (35+ tests) | No language-aware indent rules |
| Auto-closing pairs | `cursor.test.ts` (35+ tests) | No bracket/quote auto-close |
| Comment toggle (line/block) | `comment*.test.ts` (55 tests) | No `Ctrl+/` or `Ctrl+Shift+/` |
| Word delete (Ctrl+Backspace / Ctrl+Delete) | `wordOperations.test.ts` (30+ tests) | Ctrl+W = close tab, Ctrl+F = find |
| Duplicate line (Ctrl+Shift+D) | `copyLinesCommand.test.ts` (10 tests) | Not implemented |
| Delete line (Ctrl+Shift+K) | `linesOperations.test.ts` | Not implemented |
| Join lines | `linesOperations.test.ts` | Not implemented |
| Transpose characters | `linesOperations.test.ts` | Not implemented |
| Column/box select (Ctrl+Shift+Alt+Arrow) | `cursor.test.ts` | Not implemented |
| Code folding | — | Not implemented |
| Minimap / scroll overview | — | Not implemented |
| Overtype mode (Insert key) | `cursor.test.ts` | Not implemented |

**Source:** PR #76 Phase 1-2 investigation comments

## Fixed Differences: resolved during test porting (PR #76)

The following behavioral differences were discovered and **fixed** in PR #76.
Recorded here for historical reference.

### Smart Home key: now toggles between first non-whitespace and column 0

**Before:** Home key within the indent area went to column 0.
**After:** Matches VS Code — toggles between first non-whitespace character and column 0.
**Fix:** Overrode `get_cursor_line_start_location()` in `MultiCursorTextArea` with `_smart_home_col()` helper.

### Ctrl+Home / Ctrl+End: now bound for document start/end navigation

**Before:** Not bound in single-cursor mode (only worked in multi-cursor `on_key` handler).
**After:** Added BINDINGS for `ctrl+home`, `ctrl+end`, `ctrl+shift+home`, `ctrl+shift+end`.

### Ctrl+D / Ctrl+Shift+L: now uses word-boundary mode from collapsed cursor

**Before:** Always used case-sensitive plain-text substring matching.
**After:** From collapsed cursor: `\b` word-boundary, case-sensitive. From existing selection: case-insensitive substring. Matches VS Code's two-mode behavior.

### Regex find `^`/`$`: now match line boundaries

**Before:** Missing `re.MULTILINE` flag — `^`/`$` only matched document start/end.
**After:** Added `re.MULTILINE` flag in all 4 find/replace handlers.

### Regex replace with lookaheads: now preserves full document context

**Before:** Used `re.fullmatch()` on isolated selected text, breaking lookaheads that need surrounding context.
**After:** Uses `pattern.match(text, start_offset)` on full document text and `m.expand(replacement)` for substitution.

### Undo/redo in read-only mode: now blocked

**Before:** Undo/redo still triggered in read-only mode.
**After:** `action_undo()` / `action_redo()` return early when `read_only=True`.

### Sort lines selection tracking: now adjusts end column after sort

**Before:** Preserved original selection coordinates unchanged after sorting.
**After:** Implements character-offset tracking to adjust selection positions through sorted text, matching VS Code's `trackSelection` behavior.

### Ctrl+Left/Right cross-line: now skips whitespace on adjacent line

**Before:** Ctrl+Left from column 0 stopped at the end of the previous line. Ctrl+Right from end of line stopped at the start of the next line.
**After:** Ctrl+Left from column 0 jumps to the last word boundary on the previous line (skipping trailing whitespace). Ctrl+Right from end of line jumps to the first word boundary on the next line (skipping leading whitespace). Empty/whitespace-only lines remain natural stops.

### Behaviors confirmed working (initially reported as differences)

Two behaviors were initially reported as differences during early investigation but later confirmed as already working correctly in Textual's `DocumentNavigator`:

- **Sticky column**: Textual preserves the original column via `last_x_offset` when moving through shorter lines. Moving down through shorter lines clamps the column, then moving back up restores the original column.
- **Down at last line / Up at first line**: Textual's navigator correctly moves the cursor to end-of-line on the last-line Down press and to column 0 on the first-line Up press, matching VS Code.
