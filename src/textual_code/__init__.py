from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from textual_code.app import TextualCode

err_console = Console(stderr=True)


def typer_main(
    target_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the directory or file to open.",
            show_default="working directory",
        ),
    ] = None,
):
    if target_path is None:
        target_path = Path.cwd()
    target_path = target_path.resolve()
    if target_path.is_dir():
        workspace_path = target_path
        with_open_file = None
    elif target_path.is_file():
        workspace_path = target_path.parent
        with_open_file = target_path
    elif not target_path.exists():
        err_console.print(f"Error: {target_path} does not exist.")
        raise typer.Exit(code=1)
    else:
        err_console.print(f"Error: {target_path} is not a directory or a file.")
        raise typer.Exit(code=1)
    app = TextualCode(workspace_path=workspace_path, with_open_file=with_open_file)
    app.run()


def main():
    typer.run(typer_main)


if __name__ == "__main__":
    main()
