"""Launch Paeonia's editable Jupyter workbench with ``python -m paeonia``."""

from __future__ import annotations

import argparse
import importlib.resources
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


DEFAULT_NOTEBOOK = "paeonia_workbench.ipynb"


def copy_workbench(destination: Path, reset: bool = False) -> Path:
    """Copy the bundled notebook to an editable user location."""

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not reset:
        return destination

    with importlib.resources.open_binary("paeonia.data", "workbench.ipynb") as source:
        destination.write_bytes(source.read())
    return destination


def _jupyter_command(notebook: Path, no_browser: bool, classic: bool) -> List[str]:
    module = "notebook" if classic else "jupyterlab"
    command = [
        sys.executable,
        "-m",
        module,
        notebook.name,
        f"--ServerApp.root_dir={notebook.parent}",
    ]
    if no_browser:
        command.append("--no-browser")
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and launch an editable Paeonia Jupyter workbench."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path.cwd() / DEFAULT_NOTEBOOK,
        help=f"notebook path (default: ./{DEFAULT_NOTEBOOK})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="replace the local notebook with the packaged template",
    )
    parser.add_argument(
        "--copy-only",
        action="store_true",
        help="create the notebook but do not start Jupyter",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="start the server without opening a browser",
    )
    parser.add_argument(
        "--classic",
        action="store_true",
        help="use Jupyter Notebook rather than JupyterLab",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    notebook = copy_workbench(args.path, reset=args.reset)
    print(f"Paeonia workbench: {notebook}")

    if args.copy_only:
        return 0

    module = "notebook" if args.classic else "jupyterlab"
    if importlib.util.find_spec(module) is None:
        package = "notebook" if args.classic else "jupyterlab"
        raise SystemExit(
            f"Could not start {module}. Install it with `pip install {package}`."
        )

    return subprocess.call(
        _jupyter_command(notebook, args.no_browser, args.classic),
        cwd=str(notebook.parent),
    )


if __name__ == "__main__":
    raise SystemExit(main())
