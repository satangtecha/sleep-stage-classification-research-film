"""Small, canonical run-manifest contract for bounded training executions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .protocols import SUPPORTED_PROTOCOLS

RUN_STATUSES = frozenset(("planned", "running", "completed", "failed"))


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class RunManifest:
    protocol_id: str
    source_hash: str
    environment_hash: str
    data_manifest_hash: str
    split_membership_hashes: dict[str, str]
    seed: int
    stage: str
    status: str = "planned"
    metrics: dict[str, float] = field(default_factory=dict)
    checkpoint_hash: str | None = None
    failure: dict[str, str] | None = None
    schema_version: str = "1.0"
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def validate(self) -> None:
        if self.protocol_id not in SUPPORTED_PROTOCOLS:
            raise ValueError("unknown protocol_id")
        if self.stage not in {"stage1", "stage2", "stage3"}:
            raise ValueError("stage must be stage1, stage2, or stage3")
        if self.status not in RUN_STATUSES:
            raise ValueError("invalid run status")
        if not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        for name in ("source_hash", "environment_hash", "data_manifest_hash"):
            if not _is_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a SHA-256 hex digest")
        if set(self.split_membership_hashes) != {"train", "validation", "test"} or any(not _is_sha256(value) for value in self.split_membership_hashes.values()):
            raise ValueError("split_membership_hashes must contain SHA-256 values for train, validation, and test")
        if self.status == "failed" and not self.failure:
            raise ValueError("failed runs require a failure object")
        if self.status != "failed" and self.failure:
            raise ValueError("failure object is only valid for failed runs")
        if self.checkpoint_hash is not None and not _is_sha256(self.checkpoint_hash):
            raise ValueError("checkpoint_hash must be a SHA-256 digest when supplied")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def write_run_manifest(manifest: RunManifest, destination: str | Path) -> Path:
    """Write canonical JSON only after validating the bounded manifest contract."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    destination.write_text(payload, encoding="utf-8")
    return destination
