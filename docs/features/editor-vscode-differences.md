# VS Code Behavioral Differences

How textual-code's editor behavior differs from VS Code.
This document covers accepted differences and features not yet implemented.

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

## Find/Replace: `\1` capture syntax, no preserve-case

### Capture group syntax differs — `\1` (Python) vs `$1` (VS Code)

Regex replace uses Python's `re.sub` convention (`\1`, `\2`) for backreferences.
VS Code uses JavaScript convention (`$1`, `$2`).
This is a platform difference that would require a syntax translation layer to resolve.

### Preserve Case in replace not available

VS Code supports a "Preserve Case" toggle in the replace bar (e.g., replacing `"hello"` → `"goodbye"` while preserving the case pattern: `"Hello"` → `"Goodbye"`, `"HELLO"` → `"GOODBYE"`).
textual-code does not have this feature.

**Severity:** Low to medium. Capture syntax is a platform convention; preserve-case is a feature gap.

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

## Cursor Movement: sticky column reset at first line

### Up at first line resets sticky column immediately

VS Code: pressing Up on the first line moves the cursor to column 0 but *remembers* the original column.
A subsequent Down press restores the original column.
Only pressing Up *twice* at the first line resets the sticky column memory.

textual-code: pressing Up on the first line moves the cursor to (0, 0) and *immediately* resets the sticky column.
The next Down press goes to column 0 instead of restoring the original column.

**Why:** Textual's `DocumentNavigator.get_location_above()` resets `last_x_offset` when the cursor physically changes position to (0, 0).

**Severity:** Low. Minor edge case at document boundary.

## Word Selection: single-cursor vs multi-cursor cross-line behavior

Ctrl+Shift+Left/Right has subtly different cross-line behavior depending on cursor mode:

- **Single cursor** (delegates to Textual native `action_cursor_word_left(select=True)`): crosses to the END of the previous line first, then on the next press moves to a word boundary.
- **Multi-cursor** (uses `_move_all_cursors` + `_move_location`): crosses directly to the nearest word boundary on the adjacent line, skipping the line-end intermediate stop.

Both approaches produce correct final results, but the intermediate cursor position differs by one step when crossing a line boundary.

**Severity:** Low. Only observable in single-step comparison; end results are functionally equivalent.

## Features Not Yet Supported

The following VS Code editor features are not implemented in textual-code:

| VS Code Feature | Notes |
|-----------------|-------|
| Auto-indent on Enter | No language-aware indent rules |
| Auto-closing pairs | No bracket/quote auto-close |
| Comment toggle (line/block) | No `Ctrl+/` or `Ctrl+Shift+/` |
| Word delete (Ctrl+Backspace / Ctrl+Delete) | Implemented. Ctrl+Backspace requires enhanced keyboard protocol support |
| Duplicate line (Ctrl+Shift+D) | Not implemented |
| Delete line (Ctrl+Shift+K) | Not implemented |
| Join lines | Not implemented |
| Transpose characters | Not implemented |
| Column/box select (Ctrl+Shift+Alt+Arrow) | Not implemented |
| Code folding | Not implemented |
| Minimap / scroll overview | Not implemented |
| Overtype mode (Insert key) | Not implemented |
