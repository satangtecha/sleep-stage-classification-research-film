"""Derive a smaller receipt from already validated compact metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path
from types import SimpleNamespace

from paper_faithful.training import subject_generalization_runner as runner


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-receipt", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = Path(args.manifest)
    base_path = Path(args.base_receipt)
    destination = Path(args.destination)

    base = json.loads(base_path.read_text(encoding="utf-8"))
    if base.get("receipt_type") != "FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION_METADATA":
        raise ValueError("base receipt must contain validated compact metadata")
    records = runner._read_record_bindings_for_plan(str(manifest))
    subjects = sorted({subject for _, subject, _ in records})
    random.Random(args.seed).shuffle(subjects)
    selected = tuple(subjects[:6])
    profile = runner._resource_profile(
        SimpleNamespace(
            resource_profile=runner.RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
            cap=32,
            epochs=6,
            subject_count=6,
        )
    )
    required = set()
    for index, test_subject in enumerate(selected):
        validation_subject = selected[(index + 1) % len(selected)]
        for subset in (
            set(selected) - {test_subject, validation_subject},
            {validation_subject},
            {test_subject},
        ):
            required.update(
                item.key
                for item in runner._sample_members_for_profile(records, subset, 32, args.seed, profile)
            )

    chunk_by_key = {(item["tensor"], item["sidecar"]): item for item in base["chunks"]}
    selected_chunks = []
    selected_metadata = []
    covered = set()
    for metadata in base["selected_chunk_metadata"]:
        sidecar = metadata["sidecar_payload"]
        subject = sidecar["subject_id"]
        record_id = sidecar["record_id"]
        start = sidecar["local_epoch_start"]
        end = sidecar["local_epoch_end_exclusive"]
        members = {f"{subject}/{record_id}/{epoch:08d}" for epoch in range(start, end)}
        if not members.intersection(required):
            continue
        key = (metadata["tensor"], metadata["sidecar"])
        selected_chunks.append(chunk_by_key[key])
        selected_metadata.append(metadata)
        covered.update(members)
    if not required.issubset(covered):
        missing = sorted(required - covered)
        raise ValueError(f"filtered receipt does not cover required members: {len(missing)}")
    if destination.exists():
        raise FileExistsError(f"receipt already exists: {destination}")

    payload = {
        "schema_version": 1,
        "receipt_type": "FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION_METADATA",
        "cache_manifest_path": base["cache_manifest_path"],
        "cache_manifest_sha256": base["cache_manifest_sha256"],
        "phase2_manifest_path": base["phase2_manifest_path"],
        "phase2_manifest_sha256": base["phase2_manifest_sha256"],
        "completion_marker_path": base["completion_marker_path"],
        "completion_marker_sha256": base["completion_marker_sha256"],
        "chunks": selected_chunks,
        "route_epoch_entries": base["route_epoch_entries"],
        "member_count": len(covered),
        "record_bindings_sha256": base["record_bindings_sha256"],
        "validation_mode": base["validation_mode"],
        "validation_evidence_path": base["validation_evidence_path"],
        "validation_evidence_sha256": base["validation_evidence_sha256"],
        "base_receipt_path": str(base_path.resolve()),
        "base_receipt_sha256": _sha256(base_path),
        "selection_mode": "required_members_chunk_union_v1",
        "selection_members_sha256": hashlib.sha256(
            ("\n".join(sorted(required)) + "\n").encode("utf-8")
        ).hexdigest(),
        "selected_chunks": [
            {"tensor": item["tensor"], "sidecar": item["sidecar"]} for item in selected_chunks
        ],
        "selected_chunk_metadata": selected_metadata,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(payload_text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    print(
        json.dumps(
            {
                "status": "created",
                "selected_subjects": selected,
                "required_members": len(required),
                "covered_members": len(covered),
                "selected_chunks": len(selected_chunks),
                "receipt_sha256": _sha256(destination),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
