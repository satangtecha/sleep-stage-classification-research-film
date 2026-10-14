"""Atomic, resumable, record-bounded SST cache chunk writer. No cohort runner lives here."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
import os
from pathlib import Path
import platform
import tempfile
from typing import Callable, Dict, Optional, Tuple, Union

import numpy as np

from .cache_manifest import CacheContractError, ROUTES, CacheRoute, cache_stem, canonical_hash, load_record_shard, route_config, sha256_file
from .storage import CacheEstimate, ensure_cache_capacity, estimate_cache, require_e_drive
from .transform import convert_single_window, ssqueezepy_version


class CacheCollisionError(RuntimeError):
    """Raised instead of overwriting a cache name with mismatched provenance."""


@dataclass(frozen=True)
class ChunkResult:
    tensor_path: Path
    sidecar_path: Path
    resumed: bool
    metadata: Dict[str, object]


def aggregate_storage_estimate(epochs: int, route_names: Tuple[str, ...] = tuple(ROUTES)) -> Dict[str, object]:
    selected = [ROUTES[name] for name in route_names]
    rows = {route.name: estimate_cache(epochs, route.windows, 64, "float32").bytes_total for route in selected}
    return {"epochs": epochs, "routes": rows, "total_bytes": sum(rows.values()),
            "total_gib": round(sum(rows.values()) / (1024 ** 3), 3)}


def ensure_aggregate_capacity(destination: Union[str, Path], epochs: int,
                              route_names: Tuple[str, ...] = tuple(ROUTES), *,
                              free_bytes: Optional[int] = None) -> Dict[str, object]:
    """Gate the combined payload before a future multi-route cohort run starts."""
    output_root = require_e_drive(destination)
    output_root.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_storage_estimate(epochs, route_names)
    total = CacheEstimate(epochs, sum(ROUTES[name].windows for name in route_names), 64, "float32",
                          int(aggregate["total_bytes"]))
    ensure_cache_capacity(output_root, total, free_bytes=free_bytes)
    return aggregate


def worker_plan(requested_workers: Optional[int], *, records: int) -> int:
    if records <= 0:
        raise ValueError("records must be positive")
    if requested_workers is None:
        return 1
    if requested_workers < 1:
        raise ValueError("requested_workers must be positive")
    return min(requested_workers, records)


def _sidecar_path(tensor_path: Path) -> Path:
    return tensor_path.with_suffix(".json")


def _transform_identity(transform: Callable[..., np.ndarray], explicit: Optional[Dict[str, object]]) -> Dict[str, object]:
    if explicit is not None:
        return dict(explicit)
    if transform is not convert_single_window:
        raise CacheContractError("custom transforms require an explicit transform_identity")
    version = ssqueezepy_version()
    if version != "0.6.6":
        raise CacheContractError(f"full cache requires pinned ssqueezepy 0.6.6, got {version}")
    source = inspect.getsourcefile(convert_single_window)
    if source is None:
        raise CacheContractError("cannot resolve transform implementation source")
    return {
        "callable": "paper_faithful.sst.transform.convert_single_window",
        "transform_source_sha256": sha256_file(Path(source)),
        "ssqueezepy": version,
        "numpy": np.__version__,
        "python": platform.python_version(),
        "n_fft": 512,
        "frequency_bins": 256,
        "normalization": "independent_real_imag_minmax_finite_zero_v1",
        "resize": "numpy_bilinear_half_pixel_v1_tf24_tolerance_1e-6",
    }


def _expected_metadata(shard: Dict[str, object], route: CacheRoute, start: int, end: int,
                       tensor_path: Path, transform_identity: Dict[str, object],
                       provenance: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    config = route_config(route, transform_identity)
    result = {"schema_version": 1, "record_id": shard["record_id"], "subject_id": shard["subject_id"],
            "local_epoch_start": start, "local_epoch_end_exclusive": end,
            "local_epoch_indices": list(range(start, end)), "labels": np.asarray(shard["y"])[start:end].astype(int).tolist(),
            "source_path": str(shard["path"]), "source_sha256": shard["source_sha256"], "config": config,
            "config_sha256": canonical_hash(config), "tensor_file": tensor_path.name,
            "tensor_shape": [end - start, *config["output_shape"]], "tensor_dtype": config["dtype"]}
    if provenance is not None:
        result["cohort_provenance"] = dict(provenance)
    return result


def _validate_existing(tensor_path: Path, sidecar_path: Path, expected: Dict[str, object]) -> Optional[Dict[str, object]]:
    if not tensor_path.exists() and not sidecar_path.exists():
        return None
    if not tensor_path.is_file() or not sidecar_path.is_file():
        raise CacheCollisionError(f"incomplete cache collision at {tensor_path}")
    try:
        existing = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CacheCollisionError(f"unreadable cache sidecar at {sidecar_path}") from error
    for key, value in expected.items():
        if existing.get(key) != value:
            raise CacheCollisionError(f"cache provenance mismatch for {key} at {tensor_path}")
    tensor_hash = existing.get("tensor_sha256")
    if not isinstance(tensor_hash, str) or sha256_file(tensor_path) != tensor_hash:
        raise CacheCollisionError(f"cache tensor hash mismatch at {tensor_path}")
    try:
        tensor = np.load(tensor_path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise CacheCollisionError(f"cache tensor is not a readable NPY at {tensor_path}") from error
    if list(tensor.shape) != expected["tensor_shape"] or str(tensor.dtype) != expected["tensor_dtype"]:
        raise CacheCollisionError(f"cache tensor shape/dtype mismatch at {tensor_path}")
    return existing


def _contained(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise CacheContractError("cache path escapes its canonical root") from error
    return resolved


def _unlink_if_present(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def write_record_chunk(source_shard: Union[str, Path], destination: Union[str, Path], route_name: str, *, start_epoch: int = 0,
                       max_epochs: int = 32, transform: Callable[..., np.ndarray] = convert_single_window,
                       transform_identity: Optional[Dict[str, object]] = None,
                       cohort_provenance: Optional[Dict[str, object]] = None,
                       expected_source_sha256: Optional[str] = None,
                       expected_epoch_count: Optional[int] = None,
                       free_bytes: Optional[int] = None) -> ChunkResult:
    """Write one bounded chunk from one shard, or resume only an exact prior output."""
    if route_name not in ROUTES:
        raise ValueError(f"unknown route {route_name!r}")
    if max_epochs < 1 or start_epoch < 0:
        raise ValueError("start_epoch must be non-negative and max_epochs must be positive")
    output_root = require_e_drive(destination)
    output_root = output_root.resolve(strict=False)
    if cohort_provenance is not None and (not isinstance(expected_source_sha256, str) or len(expected_source_sha256) != 64 or
                                         not isinstance(expected_epoch_count, int) or expected_epoch_count < 1):
        raise CacheContractError("cohort writes require the bound source SHA-256 and epoch count")
    route = ROUTES[route_name]
    source = Path(source_shard).resolve(strict=True)
    if expected_source_sha256 is not None and sha256_file(source) != expected_source_sha256:
        raise CacheContractError("source shard changed before cache write")
    shard = load_record_shard(source_shard)
    total_epochs = int(np.asarray(shard["x"]).shape[0])
    if expected_source_sha256 is not None and (shard["source_sha256"] != expected_source_sha256 or
                                               sha256_file(source) != expected_source_sha256):
        raise CacheContractError("source shard changed while loading for cache write")
    if expected_epoch_count is not None and total_epochs != expected_epoch_count:
        raise CacheContractError("source shard epoch count differs from its Phase-2 binding")
    if start_epoch >= total_epochs:
        raise CacheContractError("start_epoch is outside this record shard")
    end_epoch = min(total_epochs, start_epoch + max_epochs)
    tensor_path = _contained(output_root, output_root / f"{cache_stem(str(shard['record_id']), route, start_epoch, end_epoch)}.npy")
    sidecar_path = _sidecar_path(tensor_path)
    _contained(output_root, sidecar_path)
    identity = _transform_identity(transform, transform_identity)
    expected = _expected_metadata(shard, route, start_epoch, end_epoch, tensor_path, identity, cohort_provenance)
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = tensor_path.with_suffix(".lock")
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise CacheCollisionError(f"cache chunk is locked by another or interrupted writer: {lock_path}") from error
    tmp_tensor = None  # type: Optional[Path]
    tmp_sidecar = None  # type: Optional[Path]
    try:
        lock_metadata = {"schema_version": 1, "pid": os.getpid(), "tensor": tensor_path.name,
                         "sidecar": sidecar_path.name, "record_id": shard["record_id"],
                         "route": route.name, "start_epoch": start_epoch, "end_epoch": end_epoch}
        os.write(lock_fd, json.dumps(lock_metadata, sort_keys=True).encode("utf-8"))
        os.fsync(lock_fd)
        os.close(lock_fd)
        lock_fd = -1
        resumed = _validate_existing(tensor_path, sidecar_path, expected)
        if resumed is not None:
            return ChunkResult(tensor_path, sidecar_path, True, resumed)
        estimate = estimate_cache(end_epoch - start_epoch, route.windows, 64, "float32")
        ensure_cache_capacity(output_root, estimate, free_bytes=free_bytes)
        fd, temporary = tempfile.mkstemp(prefix=tensor_path.name + ".", suffix=".tmp", dir=str(output_root))
        os.close(fd)
        tmp_tensor = _contained(output_root, Path(temporary))
        tensor = np.empty((end_epoch - start_epoch, route.windows, 64, 64, 2), dtype=np.float32)
        for output_index, epoch in enumerate(np.asarray(shard["x"])[start_epoch:end_epoch]):
            for window_index in range(route.windows):
                begin = window_index * route.stride
                tensor[output_index, window_index] = transform(epoch[begin:begin + route.width], protocol_id=route.transform_protocol,
                                                               output_resolution=64)
        if tensor.dtype != np.float32 or tensor.shape != (end_epoch - start_epoch, route.windows, 64, 64, 2) or not np.isfinite(tensor).all():
            raise CacheContractError("transform returned an invalid cache tensor")
        with tmp_tensor.open("wb") as stream:
            np.save(stream, tensor, allow_pickle=False)
        metadata = dict(expected)
        metadata["tensor_sha256"] = sha256_file(tmp_tensor)
        fd, temporary = tempfile.mkstemp(prefix=sidecar_path.name + ".", suffix=".tmp", dir=str(output_root))
        os.close(fd)
        tmp_sidecar = _contained(output_root, Path(temporary))
        tmp_sidecar.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if expected_source_sha256 is not None and sha256_file(source) != expected_source_sha256:
            raise CacheContractError("source shard changed during cache write")
        if tensor_path.exists() or sidecar_path.exists():
            raise CacheCollisionError(f"cache destination appeared during write: {tensor_path}")
        os.replace(tmp_tensor, tensor_path)
        tmp_tensor = None
        os.replace(tmp_sidecar, sidecar_path)
        tmp_sidecar = None
        return ChunkResult(tensor_path, sidecar_path, False, metadata)
    finally:
        if 'lock_fd' in locals() and lock_fd != -1:
            os.close(lock_fd)
        _unlink_if_present(tmp_tensor)
        _unlink_if_present(tmp_sidecar)
        _unlink_if_present(lock_path)
