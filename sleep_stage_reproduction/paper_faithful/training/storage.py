"""Drive-E guard for training artifacts; source code remains on the workspace drive."""
from __future__ import annotations

import os
from pathlib import Path
from pathlib import PureWindowsPath
import re

DEFAULT_BULK_ROOT = Path("/mnt/e/blp/sleep_stage_reproduction") if os.name != "nt" and Path("/mnt/e").is_dir() else Path(r"E:\blp\sleep_stage_reproduction")


def _is_e_drive_path(path: str | Path) -> bool:
    try:
        require_bulk_path(path)
        return True
    except ValueError:
        return False


def require_bulk_path(path: str | Path, *, allow_non_e: bool = False) -> Path:
    target = Path(path)
    if allow_non_e:
        return target
    windows_path = PureWindowsPath(str(path))
    if os.name == "nt":
        if windows_path.drive.upper() != "E:":
            raise ValueError(f"training bulk path must be on E:, got {target}")
        resolved = target.resolve(strict=False)
        if resolved.drive.upper() != "E:":
            raise ValueError(f"resolved training path escaped E: {resolved}")
        return resolved
    if windows_path.drive.upper() == "E:":
        target = Path("/mnt/e").joinpath(*windows_path.parts[1:])
    resolved, root = target.resolve(strict=False), Path("/mnt/e").resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"training bulk path must resolve beneath /mnt/e, got {resolved}") from error
    return resolved


def run_directory(run_id: str, bulk_root: str | Path = DEFAULT_BULK_ROOT) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id or "") or run_id in {".", ".."}:
        raise ValueError("run_id must be a path-safe identifier of at most 128 characters")
    root = require_bulk_path(bulk_root)
    return root / "runs" / run_id
