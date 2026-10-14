"""Execute all walkthrough notebooks in place and fail on the first bad cell."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


HERE = Path(__file__).resolve().parent
NOTEBOOKS = HERE / "notebooks"


def main() -> None:
    paths = sorted(NOTEBOOKS.glob("*.ipynb"))
    if not paths:
        raise SystemExit("No notebooks found. Run build_notebooks.py first.")

    for path in paths:
        started = time.perf_counter()
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=180,
            kernel_name="python3",
            resources={"metadata": {"path": str(path.parent)}},
            allow_errors=False,
        )
        client.execute()
        nbformat.write(notebook, path)
        elapsed = time.perf_counter() - started
        print(f"PASS {path.name} ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
