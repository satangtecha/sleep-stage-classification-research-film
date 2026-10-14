"""Focused, dependency-free validation for Phase-0 paper-alignment manifests."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PROTOCOL_DIR = ROOT / "protocols"
REQUIRED_PROTOCOLS = {"PAPER_TEXT_V1", "AUTHOR_CODE_V1", "SUBJECT_GENERALIZATION_V1"}
PROVENANCE = {"source", "assumption", "unknown"}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_protocol(manifest: dict[str, Any], source_ids: set[str]) -> list[str]:
    errors: list[str] = []
    name = manifest.get("protocol_id", "<missing protocol_id>")
    required = {"schema_version", "protocol_id", "title", "comparison_scope", "may_compare_to_reported_83_percent", "sources", "provenance", "conflicts", "unknowns"}
    allowed = required | {"dataset", "split", "model", "preprocessing", "downstream", "comparison_guard"}
    for key in sorted(required - manifest.keys()):
        errors.append(f"{name}: missing required field {key}")
    for key in sorted(manifest.keys() - allowed):
        errors.append(f"{name}: unsupported top-level field {key}")
    if manifest.get("schema_version") != "1.0":
        errors.append(f"{name}: schema_version must be 1.0")
    if name not in REQUIRED_PROTOCOLS:
        errors.append(f"{name}: unsupported protocol_id")
    if not isinstance(manifest.get("may_compare_to_reported_83_percent"), bool):
        errors.append(f"{name}: comparison flag must be boolean")
    for source in manifest.get("sources", []):
        if source not in source_ids:
            errors.append(f"{name}: unknown source {source}")
    manifest_sources = set(manifest.get("sources", []))
    provenance = manifest.get("provenance", {})
    if provenance.get("status") not in PROVENANCE or not provenance.get("ref") or not provenance.get("note"):
        errors.append(f"{name}: provenance requires status, ref, and note")
    elif provenance.get("ref") not in manifest_sources:
        errors.append(f"{name}: provenance ref must resolve to a source declared by this protocol")
    for unknown in manifest.get("unknowns", []):
        if unknown.get("provenance") != "unknown" or not unknown.get("field") or not unknown.get("reason"):
            errors.append(f"{name}: unknown entries require field, reason, and unknown provenance")
    for conflict in manifest.get("conflicts", []):
        if conflict.get("provenance") not in PROVENANCE or not all(conflict.get(key) for key in ("field", "other_protocol", "other_value", "resolution")):
            errors.append(f"{name}: conflict entry is incomplete")
        elif conflict.get("other_protocol") not in REQUIRED_PROTOCOLS or conflict.get("other_protocol") == name:
            errors.append(f"{name}: conflict other_protocol must resolve to a different declared protocol")
    if name == "PAPER_TEXT_V1":
        expected = {"recordings": 153, "subjects": 78, "epochs": 194655, "signal": "Fpz-Cz", "sampling_hz": 100, "labels": ["W", "N1", "N2", "N3", "REM"]}
        if manifest.get("dataset") != expected:
            errors.append(f"{name}: dataset facts differ from the contract")
        if manifest.get("split") != {"unit": "epoch", "method": "random", "train_fraction": 0.8, "validation_fraction": 0.1, "test_fraction": 0.1, "seed": 42}:
            errors.append(f"{name}: split must be epoch random 80/10/10 seed 42")
        expected_model = {
            "pretraining_windows": 12,
            "width": 256,
            "overlap": 7,
            "stage3_windows": 15,
            "stage3_overlap": 64,
            "stage3_overlap_provenance": "inferred from AUTHOR_CODE_V1 because the manuscript states 15 overlapping Stage-3 segments but does not state their overlap",
            "stages": [20, 20, 20],
        }
        if manifest.get("model") != expected_model:
            errors.append(f"{name}: manuscript model settings differ from the contract")
    elif name == "AUTHOR_CODE_V1":
        preprocessing = manifest.get("preprocessing", {})
        if preprocessing.get("transform") != "ssqueezepy.ssq_stft" or preprocessing.get("n_fft") != 512 or preprocessing.get("components") != ["real", "imag"] or preprocessing.get("frequency_bins") != 256 or preprocessing.get("normalization") != "min-max each component" or preprocessing.get("resize") != 64:
            errors.append(f"{name}: preprocessing settings differ from the contract")
        if manifest.get("downstream") != {"windows": 15, "overlap": 64, "stage3_epochs": 50}:
            errors.append(f"{name}: downstream settings differ from the contract")
    elif name == "SUBJECT_GENERALIZATION_V1":
        split = manifest.get("split", {})
        guard = manifest.get("comparison_guard", {})
        if split.get("unit") != "subject" or split.get("method") != "grouped" or split.get("group_key") != "subject_id" or split.get("require_disjoint_subjects") is not True:
            errors.append(f"{name}: split must group disjoint subject_id values")
        if manifest.get("may_compare_to_reported_83_percent") is not False or guard.get("rule") != "never_compare_directly" or guard.get("reported_metric") != "83%":
            errors.append(f"{name}: direct comparison to reported 83% must be prohibited")
    return errors


def validate_sources(source_manifest: dict[str, Any], source_lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = source_manifest.get("sources", [])
    ids = [entry.get("id") for entry in sources]
    if len(ids) != len(set(ids)):
        errors.append("source_manifest: source ids must be unique")
    for entry in sources:
        if not all(entry.get(key) for key in ("id", "kind", "ref", "label", "provenance", "notes")):
            errors.append("source_manifest: every source requires id, kind, ref, label, provenance, and notes")
        if entry.get("provenance") not in PROVENANCE:
            errors.append("source_manifest: unsupported provenance for {}".format(entry.get("id", "<missing>")))

    repository = source_lock.get("author_repository", {})
    if repository.get("tag") != "v1.0":
        errors.append("source_lock: author tag must be v1.0")
    if not re.fullmatch(r"[0-9a-f]{40}", str(repository.get("commit", ""))):
        errors.append("source_lock: author commit must be a full lowercase Git SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", str(repository.get("requirements_sha256", ""))):
        errors.append("source_lock: requirements hash must be SHA-256")
    if source_lock.get("paper", {}).get("doi") != "10.1038/s41598-026-62832-5":
        errors.append("source_lock: primary paper DOI differs from the approved target")
    if source_lock.get("dataset", {}).get("release_version") != "1.0.0":
        errors.append("source_lock: Sleep-EDF release must be 1.0.0")
    return errors


def validate_directory(root: Path = ROOT) -> list[str]:
    sources = read_json(root / "source_manifest.json")
    source_lock = read_json(root / "source_lock.json")
    source_ids = {entry["id"] for entry in sources.get("sources", [])}
    paths = sorted((root / "protocols").glob("*.json"))
    manifests = [read_json(path) for path in paths]
    errors: list[str] = validate_sources(sources, source_lock)
    ids = [manifest.get("protocol_id") for manifest in manifests]
    if set(ids) != REQUIRED_PROTOCOLS or len(ids) != len(REQUIRED_PROTOCOLS):
        errors.append("protocol set must contain each required protocol exactly once")
    for manifest in manifests:
        errors.extend(validate_protocol(manifest, source_ids))
    return errors


def main() -> int:
    errors = validate_directory()
    if errors:
        print("INVALID")
        print("\n".join(errors))
        return 1
    print("VALID: 3 protocol manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
