"""CLI argument tests — typer_main() in textual_code/__init__.py."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from textual_code import typer_main
from textual_code.app import TextualCode


def test_workspace_option_overrides_file_parent(workspace: Path):
    """--workspace replaces the auto-derived workspace_path."""
    target_file = workspace / "subdir" / "file.py"
    target_file.parent.mkdir()
    target_file.write_text("x = 1\n")
    custom_ws = workspace / "custom_ws"
    custom_ws.mkdir()

    captured: list[TextualCode] = []
    with patch.object(TextualCode, "run", lambda self: captured.append(self)):
        typer_main(target_path=target_file, workspace=custom_ws)

    assert captured[0].workspace_path == custom_ws
    assert captured[0].with_open_file == target_file


def test_workspace_not_provided_uses_default(workspace: Path):
    """Without --workspace, behaviour unchanged (file parent as workspace)."""
    target_file = workspace / "file.py"
    target_file.write_text("x = 1\n")

    captured: list[TextualCode] = []
    with patch.object(TextualCode, "run", lambda self: captured.append(self)):
        typer_main(target_path=target_file, workspace=None)

    assert captured[0].workspace_path == workspace


def test_workspace_nonexistent_exits(workspace: Path):
    """--workspace with non-existent path raises typer.Exit(code=1)."""
    target_file = workspace / "file.py"
    target_file.write_text("x = 1\n")

    with pytest.raises((SystemExit, typer.Exit)):
        typer_main(target_path=target_file, workspace=workspace / "no_such_dir")
