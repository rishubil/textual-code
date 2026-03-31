#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    echo 'Usage: ./scripts/check-language.sh [--all]

Scan tracked project files for non-English text (Korean, Japanese, Chinese characters).

By default, scans only lines added in the current git diff (HEAD).
With --all, scans all git-tracked text files in the repository.

Exit codes:
  0  No non-English text found
  1  Non-English text found
'
    exit
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

main() {
    local mode="diff"
    if [[ "${1-}" == "--all" ]]; then
        mode="all"
    fi

    echo "=== Language check started (mode: ${mode}) ==="
    echo ""

    PYTHONUTF8=1 uv run python - "$mode" <<'PYEOF'
import subprocess
import sys
from pathlib import Path

NON_LATIN_RANGES = [
    (0x1100, 0x11FF),   # Hangul Jamo
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0x3130, 0x318F),   # Hangul Compatibility Jamo
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xAC00, 0xD7A3),   # Hangul Syllables
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

def has_non_english(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        for start, end in NON_LATIN_RANGES:
            if start <= cp <= end:
                return True
    return False


def is_binary(path: Path) -> bool:
    """Return True if the file appears to be binary (contains null bytes)."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except OSError:
        return True


def check_diff() -> list[tuple[str, str]]:
    """Return (filepath, line) pairs with non-English text from git diff HEAD."""
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    hits = []
    current_file = ""
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        if has_non_english(content):
            hits.append((current_file, content))
    return hits


def check_all() -> list[tuple[str, str]]:
    """Return (filepath:lineno, line) pairs with non-English text from all tracked files."""
    # Use git ls-files to get all tracked files (respects .gitignore)
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    hits = []
    for filepath in sorted(result.stdout.splitlines()):
        path = Path(filepath)
        if not path.is_file() or is_binary(path):
            continue
        try:
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if has_non_english(line):
                    hits.append((f"{filepath}:{lineno}", line))
        except OSError as e:
            print(f"  Warning: could not read {filepath}: {e}", file=sys.stderr)
    return hits


mode = sys.argv[1] if len(sys.argv) > 1 else "diff"
hits = check_diff() if mode == "diff" else check_all()

if hits:
    for location, content in hits:
        print(f"  {location}: {content}")
    print()
    print(f"❌ Non-English text found ({len(hits)} line(s)).")
    print("   Translate all non-English text to English.")
    sys.exit(1)
else:
    print("✅ No non-English text found.")
    sys.exit(0)
PYEOF
}

main "$@"
