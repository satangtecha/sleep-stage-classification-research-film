"""Validated metadata and deterministic names for record-bounded SST cache chunks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Union

import numpy as np


class CacheContractError(ValueError):
    """Raised when a shard or cache sidecar does not satisfy the cache contract."""


@dataclass(frozen=True)
class CacheRoute:
    name: str
    transform_protocol: str
    transform_slot: int
    windows: int
    width: int
    stride: int

    @property
    def required_samples(self) -> int:
        return self.width + (self.windows - 1) * self.stride


PAPER_PRETRAIN_V1 = CacheRoute("PAPER_PRETRAIN_V1", "PAPER_TEXT_V1", 0, 12, 256, 249)
PAPER_STAGE3_V1 = CacheRoute("PAPER_STAGE3_V1", "PAPER_TEXT_V1", 0, 15, 256, 192)
AUTHOR_CODE_V1 = CacheRoute("AUTHOR_CODE_V1", "AUTHOR_CODE_V1", 1, 15, 256, 192)
ROUTES = {route.name: route for route in (PAPER_PRETRAIN_V1, PAPER_STAGE3_V1, AUTHOR_CODE_V1)}
RECORD_ID_RE = re.compile(r"^SC[0-9]{4}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scalar_text(value: np.ndarray, key: str) -> str:
    if value.shape != ():
        raise CacheContractError(f"shard {key} must be a scalar")
    result = str(value.item())
    if not result:
        raise CacheContractError(f"shard {key} must not be empty")
    return result


def load_record_shard(path: Union[str, Path]) -> Dict[str, Any]:
    """Load exactly one preprocessed record shard and validate its identity and labels."""
    source = Path(path)
    if source.suffix.lower() != ".npz" or not source.is_file():
        raise CacheContractError(f"preprocessed record shard is absent or not an NPZ: {source}")
    with np.load(source, allow_pickle=False) as shard:
        required = {"x", "y", "record_id", "subject_id", "sampling_hz"}
        missing = required - set(shard.files)
        if missing:
            raise CacheContractError(f"shard missing required fields: {sorted(missing)}")
        x = np.asarray(shard["x"], dtype=np.float32)
        y = np.asarray(shard["y"])
        record_id, subject_id = scalar_text(shard["record_id"], "record_id"), scalar_text(shard["subject_id"], "subject_id")
        sampling_hz = int(np.asarray(shard["sampling_hz"]).item())
    if x.ndim != 2 or x.shape[1] != 3000:
        raise CacheContractError(f"shard x must be [epochs, 3000], got {x.shape}")
    if y.ndim != 1 or y.shape[0] != x.shape[0] or not np.issubdtype(y.dtype, np.integer):
        raise CacheContractError("shard y must be an integer [epochs] array aligned with x")
    if np.any(y < 0) or np.any(y > 4):
        raise CacheContractError("shard labels must use the canonical 0..4 sleep-stage mapping")
    if sampling_hz != 100:
        raise CacheContractError(f"shard sampling_hz must be 100, got {sampling_hz}")
    if not RECORD_ID_RE.fullmatch(record_id) or subject_id != record_id[:5]:
        raise CacheContractError("shard record_id/subject_id identity is invalid")
    return {"path": source, "source_sha256": sha256_file(source), "x": x, "y": y.astype(np.int64),
            "record_id": record_id, "subject_id": subject_id, "sampling_hz": sampling_hz}


def cache_stem(record_id: str, route: CacheRoute, start_epoch: int, end_epoch: int) -> str:
    if not RECORD_ID_RE.fullmatch(record_id) or route.name not in ROUTES or start_epoch < 0 or end_epoch <= start_epoch:
        raise CacheContractError("cache stem requires a canonical record ID, route, and epoch range")
    return f"{record_id}.{route.name}.{start_epoch:08d}-{end_epoch:08d}"


def route_config(route: CacheRoute, transform_identity: Dict[str, Any], *, output_resolution: int = 64) -> Dict[str, Any]:
    required_identity = {"callable", "transform_source_sha256", "ssqueezepy", "numpy", "python",
                         "n_fft", "frequency_bins", "normalization", "resize"}
    if set(transform_identity) != required_identity:
        raise CacheContractError(f"transform identity fields differ from contract: {sorted(transform_identity)}")
    if not isinstance(transform_identity["transform_source_sha256"], str) or len(transform_identity["transform_source_sha256"]) != 64:
        raise CacheContractError("transform identity requires a SHA-256 source digest")
    return {"route": asdict(route), "output_shape": [route.windows, output_resolution, output_resolution, 2],
            "dtype": "float32", "sampling_hz": 100, "implementation": "SST_CACHE_CHUNK_V2",
            "transform_identity": transform_identity}
