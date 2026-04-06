"""Debug test to diagnose Windows spawn failures.

This test runs run_cancellable directly and prints detailed error info
that would normally be swallowed by @work(exit_on_error=False).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only debug test")
async def test_debug_run_cancellable_load_file(tmp_path: Path) -> None:
    """Directly test run_cancellable with load_file_for_editor on Windows."""
    from textual_code.cancellable_worker import run_cancellable
    from textual_code.widgets.code_editor_helpers import load_file_for_editor

    test_file = tmp_path / "hello.py"
    test_file.write_text("print('hello')\n", encoding="utf-8")

    print(f"\n=== DEBUG: Platform={sys.platform} ===")
    print(f"=== DEBUG: File={test_file} ===")
    print(f"=== DEBUG: load_file_for_editor.__module__={load_file_for_editor.__module__} ===")

    try:
        result = await run_cancellable(load_file_for_editor, test_file, timeout=30)
        print(f"=== DEBUG: SUCCESS text={result.text!r} ===")
        assert result.text == "print('hello')\n"
    except Exception as exc:
        print(f"=== DEBUG: FAILED {type(exc).__name__}: {exc} ===")
        import traceback
        traceback.print_exc()
        raise


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only debug test")
async def test_debug_run_cancellable_simple_func(tmp_path: Path) -> None:
    """Test run_cancellable with a simple stdlib function on Windows."""
    import shutil

    from textual_code.cancellable_worker import run_cancellable

    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("hello")

    print(f"\n=== DEBUG: Testing shutil.copy2 via run_cancellable ===")
    try:
        await run_cancellable(shutil.copy2, str(src), str(dst), timeout=30)
        print(f"=== DEBUG: shutil.copy2 SUCCESS, dst exists={dst.exists()} ===")
        assert dst.exists()
    except Exception as exc:
        print(f"=== DEBUG: shutil.copy2 FAILED {type(exc).__name__}: {exc} ===")
        import traceback
        traceback.print_exc()
        raise


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only debug test")
async def test_debug_run_cancellable_subprocess_tasks(tmp_path: Path) -> None:
    """Test run_cancellable with subprocess_tasks functions on Windows."""
    from textual_code.cancellable_worker import run_cancellable
    from textual_code.subprocess_tasks import calc_dir_size, scan_directory_sync

    (tmp_path / "x.txt").write_text("hello")

    print(f"\n=== DEBUG: Testing calc_dir_size ===")
    try:
        total, count = await run_cancellable(calc_dir_size, tmp_path, 0, timeout=30)
        print(f"=== DEBUG: calc_dir_size SUCCESS total={total} count={count} ===")
    except Exception as exc:
        print(f"=== DEBUG: calc_dir_size FAILED {type(exc).__name__}: {exc} ===")
        import traceback
        traceback.print_exc()
        raise

    print(f"=== DEBUG: Testing scan_directory_sync ===")
    try:
        paths, cache = await run_cancellable(
            scan_directory_sync, tmp_path, True, timeout=30
        )
        print(f"=== DEBUG: scan_directory_sync SUCCESS count={len(paths)} ===")
    except Exception as exc:
        print(f"=== DEBUG: scan_directory_sync FAILED {type(exc).__name__}: {exc} ===")
        import traceback
        traceback.print_exc()
        raise
