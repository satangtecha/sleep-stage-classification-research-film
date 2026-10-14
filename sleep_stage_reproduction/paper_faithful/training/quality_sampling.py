"""Auditable label-aware sampling for the quality-improvement track.

This module is intentionally separate from the paper-faithful samplers.  It
uses only sidecar labels whose bytes are bound by a prior full-cache receipt;
tensor payloads are never opened while planning a fold.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import random

from .splits import EpochMember


QUALITY_CAP_POLICY = "subject_class_balanced_seeded_sample_v1"
QUALITY_CLASS_WEIGHTING_ID = "TRAIN_ONLY_BALANCED_CLASS_WEIGHT_V1"
QUALITY_EARLY_STOPPING_ID = "VAL_LOSS_MIN_PATIENCE3_V1"
LABEL_ORDER = (0, 1, 2, 3, 4)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _host_path(value: str) -> Path:
    """Translate E: provenance paths to their WSL mount without rewriting it."""

    windows = PureWindowsPath(value)
    if windows.drive:
        if not windows.is_absolute() or windows.drive.upper() != "E:":
            raise ValueError("quality label evidence must stay on E:")
        if os.name != "nt":
            value = str(PurePosixPath("/mnt/e").joinpath(*windows.parts[1:]))
    elif os.name != "nt" and ("\\" in value or not PurePosixPath(value).is_absolute()):
        raise ValueError("quality label evidence path is not an absolute host path")
    return Path(value).resolve(strict=True)


def _path_key(value: str) -> str:
    windows = PureWindowsPath(value)
    if windows.drive:
        return windows.as_posix().lower()
    return PurePosixPath(value).as_posix()


def load_verified_stage3_labels(manifest_path, receipt_path, subjects):
    """Return canonical Stage-3 labels after checking prior receipt hashes.

    The returned evidence is suitable for inclusion in an immutable protocol.
    A full prior-evidence receipt is required; a compact receipt is not enough
    because the quality sampler may select members outside an earlier cap.
    """

    manifest_path = _host_path(str(manifest_path))
    receipt_path = _host_path(str(receipt_path))
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes.decode("utf-8"))
    if receipt.get("receipt_type") != "FULL_CACHE_VALIDATION_RECEIPT_V1_PRIOR_EVIDENCE":
        raise ValueError("quality planning requires the full prior-evidence receipt")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if receipt.get("cache_manifest_sha256") != manifest_sha256:
        raise ValueError("quality label receipt does not bind the cache manifest")

    subjects = tuple(sorted(set(subjects)))
    if not subjects:
        raise ValueError("quality label selection has no subjects")
    bindings = manifest.get("record_bindings")
    if not isinstance(bindings, list):
        raise ValueError("cache manifest record bindings are missing")
    selected_records = {
        item["record_id"]: (item["subject_id"], item["epochs"])
        for item in bindings
        if isinstance(item, dict) and item.get("subject_id") in subjects
    }
    if not selected_records or {value[0] for value in selected_records.values()} != set(subjects):
        raise ValueError("quality label evidence does not cover every selected subject")

    receipt_chunks = receipt.get("chunks")
    if not isinstance(receipt_chunks, list):
        raise ValueError("quality label receipt chunks are missing")
    receipt_sidecars = {
        _path_key(item["sidecar"]): item.get("sidecar_sha256")
        for item in receipt_chunks
        if isinstance(item, dict) and isinstance(item.get("sidecar"), str)
    }
    labels = {}
    verified_sidecars = []
    for chunk in manifest.get("chunks", []):
        if not isinstance(chunk, dict) or not isinstance(chunk.get("sidecar"), str):
            continue
        serialized = chunk["sidecar"]
        name = PureWindowsPath(serialized).name
        if ".PAPER_STAGE3_V1." not in name:
            continue
        record_id = name.split(".PAPER_STAGE3_V1.", 1)[0]
        if record_id not in selected_records:
            continue
        expected = receipt_sidecars.get(_path_key(serialized))
        sidecar_path = _host_path(serialized)
        if not isinstance(expected, str) or len(expected) != 64 or _sha256_file(sidecar_path) != expected:
            raise ValueError("quality Stage-3 sidecar receipt hash failed")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        subject_id, epochs = selected_records[record_id]
        start = sidecar.get("local_epoch_start")
        values = sidecar.get("labels")
        route = sidecar.get("config", {}).get("route", {}).get("name")
        if (
            sidecar.get("record_id") != record_id
            or sidecar.get("subject_id") != subject_id
            or route != "PAPER_STAGE3_V1"
            or isinstance(start, bool)
            or not isinstance(start, int)
            or not isinstance(values, list)
            or any(type(label) is not int or label not in LABEL_ORDER for label in values)
            or start < 0
            or start + len(values) > epochs
        ):
            raise ValueError("quality Stage-3 sidecar labels are invalid")
        for offset, label in enumerate(values):
            member = EpochMember(subject_id, record_id, start + offset)
            if member.key in labels:
                raise ValueError("quality Stage-3 label membership is duplicated")
            labels[member.key] = label
        verified_sidecars.append({"path": serialized, "sha256": expected})

    expected_count = sum(epochs for _, epochs in selected_records.values())
    if len(labels) != expected_count:
        raise ValueError("quality Stage-3 labels do not cover selected record epochs")
    index_lines = ["%s:%d" % item for item in sorted(labels.items())]
    evidence = {
        "policy": QUALITY_CAP_POLICY,
        "label_route": "PAPER_STAGE3_V1",
        "subjects": list(subjects),
        "member_count": len(labels),
        "label_index_sha256": hashlib.sha256(("\n".join(index_lines) + "\n").encode("utf-8")).hexdigest(),
        "cache_manifest_path": str(manifest_path),
        "cache_manifest_sha256": manifest_sha256,
        "prior_receipt_path": str(receipt_path),
        "prior_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "verified_sidecar_count": len(verified_sidecars),
        "verified_sidecars_sha256": hashlib.sha256(
            json.dumps(verified_sidecars, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    return labels, evidence


def sample_class_balanced_members_per_subject(records, subjects, cap, seed, labels):
    """Select up to ``cap`` members per subject with deterministic class balance.

    Every locally available class receives a slot before remaining capacity is
    filled.  Allocation is round-robin across classes, so class counts differ
    by at most one unless a class is exhausted.
    """

    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("quality cap must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("quality seed must be an unsigned 32-bit integer")
    subjects = tuple(sorted(set(subjects)))
    if not subjects:
        raise ValueError("quality sample has no subjects")
    members_by_subject = {subject: [] for subject in subjects}
    seen = set()
    for record_id, subject_id, epochs in sorted(records, key=lambda row: (row[1], row[0])):
        if record_id in seen:
            raise ValueError("quality records contain a duplicate")
        seen.add(record_id)
        if subject_id not in members_by_subject:
            continue
        for epoch in range(epochs):
            member = EpochMember(subject_id, record_id, epoch)
            try:
                label = labels[member.key]
            except KeyError as error:
                raise ValueError("quality sample has no verified label for a member") from error
            members_by_subject[subject_id].append((member, label))

    selected = []
    for subject_id in subjects:
        grouped = defaultdict(list)
        for member, label in members_by_subject[subject_id]:
            grouped[label].append(member)
        available = tuple(label for label in LABEL_ORDER if grouped[label])
        if not available:
            raise ValueError("quality sample has an empty subject group")
        shuffled = {}
        for label in available:
            values = list(grouped[label])
            class_seed = int(
                hashlib.sha256(f"{seed}:{subject_id}:{label}".encode("utf-8")).hexdigest(), 16
            )
            random.Random(class_seed).shuffle(values)
            shuffled[label] = values
        limit = min(cap, sum(len(values) for values in shuffled.values()))
        positions = Counter()
        while sum(positions.values()) < limit:
            advanced = False
            for label in available:
                if positions[label] < len(shuffled[label]) and sum(positions.values()) < limit:
                    positions[label] += 1
                    advanced = True
            if not advanced:
                break
        for position in range(max(positions.values())):
            for label in available:
                if position < positions[label]:
                    selected.append(shuffled[label][position])
    return tuple(selected)


def class_counts(members, labels):
    counts = Counter(labels[member.key] for member in members)
    return {str(label): int(counts[label]) for label in LABEL_ORDER}


def balanced_class_weights(members, label_lookup):
    """Compute sklearn-style balanced weights from the training split only."""

    counts = Counter(int(label_lookup(member)) for member in members)
    if any(counts[label] <= 0 for label in LABEL_ORDER):
        raise ValueError("quality class weighting requires all five training classes")
    total = sum(counts.values())
    weights = {label: total / (len(LABEL_ORDER) * counts[label]) for label in LABEL_ORDER}
    return {
        "id": QUALITY_CLASS_WEIGHTING_ID,
        "formula": "n_train/(5*n_class)",
        "source_split": "train_only",
        "counts": {str(label): int(counts[label]) for label in LABEL_ORDER},
        "weights": {str(label): float(weights[label]) for label in LABEL_ORDER},
    }
