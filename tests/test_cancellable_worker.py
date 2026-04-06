"""Tests for the subprocess-based cancellable worker."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from textual_code.cancellable_worker import run_cancellable

# ── Helper functions (module-level, picklable) ────────────────────────────


def _add(a: int, b: int) -> int:
    return a + b


def _sleep_and_return(seconds: float, value: str) -> str:
    time.sleep(seconds)
    return value


def _raise_value_error(msg: str) -> None:
    raise ValueError(msg)


def _return_path(p: str) -> Path:
    return Path(p)


def _read_file(p: str) -> str:
    return Path(p).read_text(encoding="utf-8")


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_cancellable_basic() -> None:
    """Simple function call returns correct result."""
    result = await run_cancellable(_add, 3, 4)
    assert result == 7


@pytest.mark.asyncio
async def test_run_cancellable_no_timeout() -> None:
    """Function completes within timeout."""
    result = await run_cancellable(_sleep_and_return, 0.1, "done", timeout=5.0)
    assert result == "done"


@pytest.mark.asyncio
async def test_run_cancellable_timeout_kills_process() -> None:
    """TimeoutError is raised and process is killed on timeout."""
    with pytest.raises(TimeoutError, match="timed out"):
        await run_cancellable(_sleep_and_return, 10.0, "never", timeout=0.2)


@pytest.mark.asyncio
async def test_run_cancellable_exception_propagation() -> None:
    """Exceptions from the worker function are re-raised."""
    with pytest.raises(ValueError, match="test error"):
        await run_cancellable(_raise_value_error, "test error")


@pytest.mark.asyncio
async def test_run_cancellable_path_pickling() -> None:
    """Path objects can be passed and returned (pickle round-trip)."""
    result = await run_cancellable(_return_path, "/tmp/test")
    assert result == Path("/tmp/test")


@pytest.mark.asyncio
async def test_run_cancellable_file_read(tmp_path: Path) -> None:
    """Subprocess can read files from the filesystem."""
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello world")
    result = await run_cancellable(_read_file, str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_run_cancellable_timeout_zero_still_works() -> None:
    """Even a very short timeout triggers TimeoutError for slow operations."""
    with pytest.raises(TimeoutError):
        await run_cancellable(_sleep_and_return, 5.0, "never", timeout=0.01)


@pytest.mark.asyncio
async def test_run_cancellable_no_timeout_parameter() -> None:
    """Without timeout parameter, function runs to completion."""
    result = await run_cancellable(_sleep_and_return, 0.1, "ok")
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_cancellable_unknown_ipc_tag() -> None:
    """Unknown IPC tag raises RuntimeError."""
    from unittest.mock import MagicMock, patch

    from textual_code.cancellable_worker import _MP_CTX

    real_pipe = _MP_CTX.Pipe

    def patched_pipe(*args, **kwargs):
        parent, child = real_pipe(*args, **kwargs)
        real_recv = parent.recv
        wrapper = MagicMock()
        wrapper.close = parent.close

        def _fake_recv():
            real_recv()  # consume the real message
            return ("bogus", "unexpected")

        wrapper.recv = _fake_recv
        return wrapper, child

    with (
        patch.object(_MP_CTX, "Pipe", patched_pipe),
        pytest.raises(RuntimeError, match="unknown IPC tag"),
    ):
        await run_cancellable(_add, 1, 2)
