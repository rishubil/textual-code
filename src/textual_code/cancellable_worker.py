"""Subprocess-based cancellable worker for blocking operations.

Python threads cannot be force-killed.  When ``asyncio.to_thread()`` or
``@work(thread=True)`` times out, the underlying thread keeps running.
This module provides ``run_cancellable()`` which runs a function in a
**subprocess** instead: on timeout or cancellation the process is killed
with SIGKILL and the OS reclaims all resources immediately.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import sys
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any

log = logging.getLogger(__name__)

_MP_CTX = multiprocessing.get_context("fork" if sys.platform == "linux" else "spawn")


def _worker(fn: Callable[..., Any], args: tuple[Any, ...], conn: Connection) -> None:
    """Subprocess entry point: run *fn* and send the result over *conn*."""
    try:
        result = fn(*args)
        conn.send(("ok", result))
    except BaseException as exc:
        # Send the exception so the caller can re-raise it.
        conn.send(("error", exc))
    finally:
        conn.close()


async def run_cancellable[T](
    fn: Callable[..., T],
    *args: Any,
    timeout: float | None = None,
) -> T:
    """Run *fn(*args)* in a subprocess with optional timeout.

    On timeout or ``asyncio.CancelledError`` the subprocess is killed
    immediately with ``proc.kill()`` (SIGKILL on POSIX, TerminateProcess
    on Windows).

    Args:
        fn: A **module-level** callable (must be picklable).
            Closures and lambdas are not supported.
        *args: Positional arguments for *fn* (must be picklable).
        timeout: Maximum seconds to wait.  ``None`` means no timeout.

    Returns:
        The return value of ``fn(*args)``.

    Raises:
        TimeoutError: If the operation exceeds *timeout* seconds.
        RuntimeError: If the subprocess crashes without sending a result.
        Exception: Any exception raised by *fn* is re-raised in the caller.
    """
    parent_conn, child_conn = _MP_CTX.Pipe()
    proc = _MP_CTX.Process(target=_worker, args=(fn, args, child_conn), daemon=True)
    proc.start()
    child_conn.close()  # parent doesn't need the child's end

    try:
        tag, payload = await asyncio.wait_for(
            asyncio.to_thread(parent_conn.recv),
            timeout=timeout,
        )
    except (TimeoutError, asyncio.CancelledError):
        _kill(proc)
        parent_conn.close()
        fn_name = getattr(fn, "__name__", repr(fn))
        raise TimeoutError(f"{fn_name} timed out after {timeout}s") from None
    except EOFError:
        _kill(proc)
        parent_conn.close()
        fn_name = getattr(fn, "__name__", repr(fn))
        raise RuntimeError(f"{fn_name} crashed without sending a result") from None

    parent_conn.close()
    proc.join(timeout=2)
    if proc.is_alive():
        _kill(proc)

    if tag == "error":
        assert isinstance(payload, BaseException)
        raise payload
    result: T = payload
    return result


def _kill(proc: BaseProcess) -> None:
    """Kill a process and wait for it to exit."""
    if proc.is_alive():
        log.debug("Killing subprocess %s (pid=%s)", proc.name, proc.pid)
        proc.kill()
        proc.join(timeout=2)
