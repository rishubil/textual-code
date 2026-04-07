import logging
import os
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from ripgrep_rs import files as rg_files
from textual.command import Hit, Hits, Provider

from textual_code.search import _SORT_BY_PATH

logger = logging.getLogger(__name__)


def _rg_scan(
    workspace_path: Path,
    *,
    show_hidden_files: bool = True,
    respect_gitignore: bool = False,
    absolute: bool = False,
    include_dirs: bool = False,
    relative_to: str | None = None,
) -> list[Path]:
    """Shared ripgrep-rs file enumeration with timing and logging."""
    ws = str(workspace_path)
    # When showing hidden files, explicitly exclude .git (dir and worktree file).
    globs = ["!.git/", "!.git"] if show_hidden_files else None
    t0 = time.monotonic()
    raw = rg_files(
        paths=[ws],
        hidden=show_hidden_files,
        no_ignore=not respect_gitignore,
        globs=globs,
        sort=_SORT_BY_PATH,
        absolute=absolute or None,
        include_dirs=include_dirs or None,
        relative_to=relative_to,
    )
    elapsed = time.monotonic() - t0
    logger.debug(
        "rg_scan: %d entries in %.3fs (gitignore=%s, hidden=%s)",
        len(raw),
        elapsed,
        respect_gitignore,
        show_hidden_files,
    )
    return [Path(p) for p in raw]


def _read_workspace_files(
    workspace_path: Path,
    *,
    show_hidden_files: bool = True,
    respect_gitignore: bool = False,
) -> list[Path]:
    """Return relative paths for files under workspace_path.

    Uses ``ripgrep-rs`` for fast file enumeration with native ``.gitignore``
    support.  When *respect_gitignore* is True, files matching ``.gitignore``
    patterns are excluded.  When *show_hidden_files* is True, dot-prefixed
    entries are included.  ``.git`` subtrees are always excluded.
    """
    return _rg_scan(
        workspace_path,
        show_hidden_files=show_hidden_files,
        respect_gitignore=respect_gitignore,
        relative_to=str(workspace_path),
    )


def _read_workspace_paths(
    workspace_path: Path,
    *,
    show_hidden_files: bool = True,
    respect_gitignore: bool = False,
) -> list[Path]:
    """Return all files and directories under workspace_path as absolute paths.

    Uses ``ripgrep-rs`` for fast file enumeration with native ``.gitignore``
    support.  When *respect_gitignore* is True, entries matching ``.gitignore``
    patterns are excluded.  When *show_hidden_files* is True, dot-prefixed
    entries are included.  ``.git`` subtrees are always excluded.
    """
    return _rg_scan(
        workspace_path,
        show_hidden_files=show_hidden_files,
        respect_gitignore=respect_gitignore,
        absolute=True,
        include_dirs=True,
    )


def _read_workspace_directories(workspace_path: Path) -> list[Path]:
    """Return all directories under workspace_path, including root.

    Includes dot-prefixed directories (e.g. .github/, .vscode/) but
    excludes .git directories and their subtrees at any depth.
    """
    dirs = [workspace_path]
    try:
        for dirpath, dirnames, _ in os.walk(
            workspace_path, onerror=lambda e: logger.debug("os.walk error: %s", e)
        ):
            # Prune .git directories in-place to prevent descent
            dirnames[:] = sorted(d for d in dirnames if d != ".git")
            dirs.extend(Path(dirpath) / d for d in dirnames)
    except OSError:
        logger.debug("OSError during os.walk of %s", workspace_path)
    dirs.sort()
    return dirs


class BaseCreatePathCommandProvider(Provider):
    """
    Base class for CreatePathCommandProvider
    """

    @property
    def is_dir(self) -> bool:
        raise NotImplementedError

    @property
    def workspace_path(self) -> Path:
        raise NotImplementedError

    @property
    def post_message_callback(self) -> Callable[[Path], Any]:
        raise NotImplementedError

    async def search(self, query: str) -> Hits:
        target_path = (self.workspace_path / query).resolve()

        yield Hit(
            1,
            str(target_path),
            partial(
                self.post_message_callback,
                target_path,
            ),
            help=f"Create this {'directory' if self.is_dir else 'file'}",
        )


def create_create_file_or_dir_command_provider(
    workspace_path: Path,
    is_dir: bool,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    # rename for clarity
    passed_workspace_path = workspace_path
    passed_is_dir = is_dir
    passed_post_message_callback = post_message_callback

    class CreatePathCommandProvider(BaseCreatePathCommandProvider):
        """A command provider to create a new file or directory."""

        @property
        def is_dir(self) -> bool:
            return passed_is_dir

        @property
        def workspace_path(self) -> Path:
            return passed_workspace_path

        @property
        def post_message_callback(self) -> Callable[[Path], Any]:
            return passed_post_message_callback

    return CreatePathCommandProvider
