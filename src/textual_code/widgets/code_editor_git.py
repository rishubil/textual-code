"""Git diff gutter support for CodeEditor."""

from __future__ import annotations

import logging
import shutil
import subprocess
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

# Cached git binary path (None if git is not installed)
_git_bin: str | None = shutil.which("git")

# Maximum line count for diff computation (performance protection)
_MAX_DIFF_LINES = 10000


class LineChangeType(Enum):
    """Type of change for a line in the git diff gutter."""

    ADDED = "added"  # green ▎
    MODIFIED = "modified"  # yellow ▎
    DELETED_ABOVE = "deleted_above"  # red ▔ (content deleted above this line)
    DELETED_BELOW = "deleted_below"  # red ▁ (content deleted below this line, EOF)


def _compute_line_changes(
    old_lines: list[str], new_lines: list[str]
) -> dict[int, LineChangeType]:
    """Compute line-level changes between old and new text.

    Returns a dict mapping line indices (in new_lines) to their change type.
    All keys are guaranteed to satisfy ``0 <= k < len(new_lines)`` — no
    phantom lines are ever created.

    Returns empty dict when either side exceeds _MAX_DIFF_LINES.
    """
    if not new_lines:
        return {}
    if len(old_lines) > _MAX_DIFF_LINES or len(new_lines) > _MAX_DIFF_LINES:
        return {}

    sm = SequenceMatcher(None, old_lines, new_lines)
    changes: dict[int, LineChangeType] = {}

    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            for line in range(j1, j2):
                changes[line] = LineChangeType.MODIFIED
        elif tag == "insert":
            for line in range(j1, j2):
                changes[line] = LineChangeType.ADDED
        elif tag == "delete":
            # j1 == j2 for delete opcodes (no lines in new text).
            # Place indicator on the nearest existing line.
            if j1 < len(new_lines):
                if j1 not in changes:
                    changes[j1] = LineChangeType.DELETED_ABOVE
            elif j1 > 0 and j1 - 1 not in changes:
                changes[j1 - 1] = LineChangeType.DELETED_BELOW

    return changes


def _get_git_head_content(path: Path, encoding: str = "utf-8") -> str | None:
    """Get the HEAD version of a file from git.

    Uses ``git rev-parse --show-toplevel`` to detect the git root
    independently of the workspace path.

    Args:
        path: Path to the file whose HEAD content to retrieve.
        encoding: Encoding to use when decoding ``git show`` output.
            Should match the file's detected encoding (e.g. ``"latin-1"``,
            ``"euc_kr"``).  Defaults to ``"utf-8"``.

    Returns None when:
    - git binary not found
    - path is not inside a git repo
    - file is not tracked (untracked / new)
    - subprocess times out or fails
    """
    if _git_bin is None:
        log.debug("git diff gutter: git binary not found")
        return None

    resolved = path.resolve()
    parent = str(resolved.parent)

    try:
        # Find git root
        result = subprocess.run(
            [_git_bin, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=parent,
            timeout=5,
        )
        if result.returncode != 0:
            log.debug("git diff gutter: not a git repo at %s", parent)
            return None

        git_root = Path(result.stdout.strip())
        rel_path = resolved.relative_to(git_root).as_posix()

        # Get HEAD content
        result = subprocess.run(
            [_git_bin, "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            cwd=str(git_root),
            timeout=5,
        )
        if result.returncode != 0:
            log.debug("git diff gutter: file not tracked: %s", rel_path)
            return None

        return result.stdout
    except subprocess.TimeoutExpired:
        log.warning("git diff gutter: timed out for %s", path)
        return None
    except (OSError, ValueError, LookupError) as e:
        log.debug("git diff gutter: error (encoding=%s): %s", encoding, e)
        return None
