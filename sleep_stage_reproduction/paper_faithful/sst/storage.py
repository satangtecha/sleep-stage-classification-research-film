"""Conservative SST cache sizing and E-drive safety gate."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Optional, Union
import shutil

GIB = 1024 ** 3
DEFAULT_BULK_ROOT = Path(r"E:\blp\sleep_stage_reproduction")
MIN_FREE_RESERVE_BYTES = 100 * GIB


@dataclass(frozen=True)
class CacheEstimate:
    epochs: int
    windows: int
    resolution: int
    dtype: str
    bytes_total: int

    @property
    def gib_total(self) -> float:
        return self.bytes_total / GIB


def estimate_cache(epochs: int, windows: int, resolution: int, dtype: str) -> CacheEstimate:
    itemsize = {"float32": 4, "float16": 2}.get(dtype)
    if itemsize is None:
        raise ValueError("dtype must be float32 or float16")
    if min(epochs, windows, resolution) <= 0:
        raise ValueError("epochs, windows, and resolution must be positive")
    return CacheEstimate(epochs, windows, resolution, dtype, epochs * windows * resolution**2 * 2 * itemsize)


def require_e_drive(path: Union[str, Path], *, allow_non_e: bool = False) -> Path:
    target = Path(path)
    if allow_non_e:
        return target
    windows_path = PureWindowsPath(str(path))
    if os.name == "nt":
        if windows_path.drive.upper() != "E:":
            raise ValueError(f"SST cache/fixture path must be on E:, got {target}")
        resolved = target.resolve(strict=False)
        if resolved.drive.upper() != "E:":
            raise ValueError(f"resolved SST path escaped E: {resolved}")
        return resolved
    if windows_path.drive.upper() == "E:":
        target = Path("/mnt/e").joinpath(*windows_path.parts[1:])
    resolved, root = target.resolve(strict=False), Path("/mnt/e").resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"SST cache/fixture path must resolve beneath /mnt/e, got {resolved}") from error
    return resolved


def ensure_cache_capacity(destination: Union[str, Path], estimate: CacheEstimate, *, free_bytes: Optional[int] = None) -> None:
    target = require_e_drive(destination)
    available = shutil.disk_usage(target).free if free_bytes is None else free_bytes
    if available - estimate.bytes_total < MIN_FREE_RESERVE_BYTES:
        raise RuntimeError(
            f"cache would violate the 100 GiB free-space reserve: need {estimate.gib_total:.2f} GiB plus reserve"
        )
