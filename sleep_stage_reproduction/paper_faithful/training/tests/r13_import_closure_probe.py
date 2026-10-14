from __future__ import print_function

import importlib
import json
import pathlib
import sys


def main():
    root = pathlib.Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    for name in (
        "paper_faithful.training.cli",
        "paper_faithful.training.models",
        "paper_faithful.training.verify_run",
    ):
        importlib.import_module(name)
    paths = {}
    for name, module in tuple(sys.modules.items()):
        if name == "__main__":
            continue
        value = getattr(module, "__file__", None)
        if not value:
            continue
        path = pathlib.Path(value).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if (
            relative.suffix == ".py"
            and relative.parts
            and relative.parts[0] == "paper_faithful"
        ):
            paths[relative.as_posix()] = name
    print(
        json.dumps(
            [{"path": path, "module": paths[path]} for path in sorted(paths)],
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

