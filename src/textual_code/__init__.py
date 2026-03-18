from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from textual_code.app import TextualCode

err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    """Print version and exit when --version is passed."""
    if value:
        import importlib.metadata

        try:
            version = importlib.metadata.version("textual-code")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        print(f"textual-code {version}")
        raise typer.Exit()


def typer_main(
    target_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the directory or file to open.",
            show_default="working directory",
        ),
    ] = None,
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            "-w",
            help="Override workspace directory (sidebar root). "
            "Defaults to the target file's parent or target directory.",
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
):
    """
    Run Textual Code with the given target path.

    This is the main entry point for the Textual Code CLI, with typer as the CLI
    framework.
    """

    # if target_path is None, use the current working directory
    if target_path is None:
        target_path = Path.cwd()
    target_path = target_path.resolve()

    # determine the workspace path and the file to open
    if target_path.is_dir():
        workspace_path = target_path
        with_open_file = None
    elif target_path.is_file():
        workspace_path = target_path.parent
        with_open_file = target_path
    elif not target_path.exists():
        try:
            target_path.touch()
        except Exception as e:
            err_console.print(f"Error: {e}")
            raise typer.Exit(code=1) from e
        workspace_path = target_path.parent
        with_open_file = target_path
    else:
        err_console.print(f"Error: {target_path} is not a directory or a file.")
        raise typer.Exit(code=1)

    if workspace is not None:
        workspace = workspace.resolve()
        if not workspace.is_dir():
            err_console.print(f"Error: --workspace {workspace} is not a directory.")
            raise typer.Exit(code=1)
        workspace_path = workspace

    app = TextualCode(workspace_path=workspace_path, with_open_file=with_open_file)
    app.run()


def main():
    """
    Main entry point for the Textual Code CLI.

    This function is called when the package is run as a script.
    """
    typer.run(typer_main)


if __name__ == "__main__":
    main()
