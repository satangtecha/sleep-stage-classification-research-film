"""Create a fresh Plan16-native cache subset from an immutable compact receipt."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _host_path(value: str) -> Path:
    windows = PureWindowsPath(value)
    if windows.drive:
        if windows.drive.upper() != "E:" or not windows.is_absolute() or ".." in windows.parts:
            raise ValueError("unsupported Windows cache path")
        return Path("/mnt/e").joinpath(*windows.parts[1:]).resolve(strict=True)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("cache path must be absolute")
    return path.resolve(strict=True)


def _publish(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--label-receipt", required=True)
    parser.add_argument("--subjects", required=True)
    parser.add_argument("--previous-stage", required=True)
    parser.add_argument("--output-stage", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    receipt_path = Path(args.receipt).resolve(strict=True)
    label_receipt_path = Path(args.label_receipt).resolve(strict=True)
    previous = Path(args.previous_stage).resolve(strict=True)
    output = Path(args.output_stage)
    evidence_path = Path(args.evidence)
    if evidence_path.exists() or output.exists():
        raise FileExistsError("Plan16 native stage or evidence already exists")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    label_receipt = json.loads(label_receipt_path.read_text(encoding="utf-8"))
    if receipt.get("receipt_type") != "FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION_METADATA" or not isinstance(receipt.get("chunks"), list):
        raise ValueError("Plan16 compact receipt schema failed")
    sources = [
        (_host_path(receipt["cache_manifest_path"]), receipt["cache_manifest_sha256"], "cache_manifest"),
        (_host_path(receipt["completion_marker_path"]), receipt["completion_marker_sha256"], "completion_marker"),
    ]
    for chunk in receipt["chunks"]:
        sources.append((_host_path(chunk["sidecar"]), chunk["sidecar_sha256"], "sidecar"))
        sources.append((_host_path(chunk["tensor"]), chunk["tensor_sha256"], "tensor"))
    selected_subjects = set(args.subjects.split(","))
    if not selected_subjects or any(not subject for subject in selected_subjects):
        raise ValueError("selected subject list is invalid")
    existing = {source.name: expected for source, expected, _ in sources}
    for chunk in label_receipt.get("chunks", []):
        serialized = chunk["sidecar"]
        name = PureWindowsPath(serialized).name if "\\" in serialized else Path(serialized).name
        if ".PAPER_STAGE3_V1." not in name or not any(name.startswith(subject) for subject in selected_subjects):
            continue
        sidecar = _host_path(serialized)
        expected = chunk["sidecar_sha256"]
        if sidecar.name in existing:
            if existing[sidecar.name] != expected:
                raise ValueError("conflicting sidecar digest")
            continue
        sources.append((sidecar, expected, "label_sidecar"))
        existing[sidecar.name] = expected
    names = [source.name for source, _, _ in sources]
    if len(names) != len(set(names)):
        raise ValueError("Plan16 native stage has duplicate basenames")
    output.mkdir(parents=False, exist_ok=False)
    linked = copied = total_bytes = 0
    counts = {"cache_manifest": 0, "completion_marker": 0, "sidecar": 0, "tensor": 0, "label_sidecar": 0}
    try:
        for source, expected, kind in sources:
            destination = output / source.name
            prior = previous / source.name
            if prior.is_file() and _sha256(prior) == expected:
                os.link(str(prior), str(destination))
                linked += 1
            else:
                shutil.copyfile(str(source), str(destination))
                copied += 1
            actual = _sha256(destination)
            if actual != expected:
                raise ValueError("staged cache digest mismatch: " + source.name)
            total_bytes += destination.stat().st_size
            counts[kind] += 1
        record = {
            "schema_version": 1,
            "artifact_type": "PLAN16_NATIVE_CACHE_STAGE_V1",
            "status": "pass",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "receipt_path": str(receipt_path),
            "receipt_sha256": _sha256(receipt_path),
            "label_receipt_path": str(label_receipt_path),
            "label_receipt_sha256": _sha256(label_receipt_path),
            "subjects": sorted(selected_subjects),
            "previous_stage": str(previous),
            "output_stage": str(output.resolve()),
            "counts": counts,
            "linked_file_count": linked,
            "copied_file_count": copied,
            "total_file_count": len(sources),
            "total_bytes": total_bytes,
            "all_digests_verified": True,
            "source_cache_untouched": True,
        }
        _publish(evidence_path, record)
    except Exception:
        failure = {
            "schema_version": 1,
            "artifact_type": "PLAN16_NATIVE_CACHE_STAGE_FAILURE_V1",
            "status": "failed",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "receipt_path": str(receipt_path),
            "previous_stage": str(previous),
            "output_stage": str(output.resolve()),
        }
        try:
            _publish(output / "STAGING_FAILED.json", failure)
        except Exception:
            pass
        raise
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
