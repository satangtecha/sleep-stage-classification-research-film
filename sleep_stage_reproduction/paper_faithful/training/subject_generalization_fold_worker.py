"""Run exactly one held-out subject fold in a fresh locked TF2.4 process.

The parent pilot owns the versioned run namespace and launches this module
once per fold.  Exiting the worker is intentional: TensorFlow allocator state
must be returned to the operating system before the next fold starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from . import subject_generalization_runner as runner
from .subject_generalization import SubjectFold
from .splits import SplitPlan, validate_no_leakage
from .trainer import TrainingContractError, cleanup_model_state, seed_model


def _build_fold(args, record, fold_index: int):
    records = runner._read_record_bindings_for_plan(args.cache_manifest)
    profile = runner._resource_profile(args)
    subjects = set(record["pilot_subjects"])
    try:
        item = record["folds"][fold_index]
    except (IndexError, TypeError) as error:
        raise TrainingContractError("worker fold index is outside the reviewed protocol") from error
    train_subjects = subjects - {item["test_subject"], item["validation_subject"]}
    labels = None
    if profile.get("class_balanced_sampling"):
        try:
            labels, _ = runner.load_verified_stage3_labels(
                args.cache_manifest, args.label_evidence_receipt, subjects
            )
        except (OSError, UnicodeError, ValueError) as error:
            raise TrainingContractError("worker quality label evidence failed: " + str(error)) from error
    parts = {
        name: runner._sample_members_for_profile(records, subset, args.cap, args.selection_seed, profile, labels)
        for name, subset in (
            ("train", train_subjects),
            ("validation", {item["validation_subject"]}),
            ("test", {item["test_subject"]}),
        )
    }
    hashes = {
        name: hashlib.sha256(
            ("\n".join(sorted(member.key for member in values)) + "\n").encode("utf-8")
        ).hexdigest()
        for name, values in parts.items()
    }
    if hashes != item["split_membership_hashes"]:
        raise TrainingContractError("worker sampling differs from reviewed fold")
    plan = SplitPlan(
        runner.SUBJECT_GENERALIZATION_PROTOCOL_ID,
        args.selection_seed,
        parts["train"],
        parts["validation"],
        parts["test"],
        hashes,
    )
    validate_no_leakage(plan, require_subject_disjoint=True)
    return item, SubjectFold(
        item["fold_index"],
        item["test_subject"],
        item["validation_subject"],
        tuple(sorted(train_subjects)),
        plan,
    ), {member.key for values in parts.values() for member in values}


def run(args) -> int:
    profile = runner._resource_profile(args)
    if not profile["fresh_process_per_fold"]:
        raise TrainingContractError("fold worker requires the fresh-process resource profile")
    record = runner._build_light_plan(args)
    runner._require_approved_protocol(args, record)
    item, fold, required_members = _build_fold(args, record, args.fold_index)

    runner._probe_live_capacity(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        allow_offline_power=profile["allow_offline_power"],
    )
    cache = None
    tf = None
    try:
        cache = runner.load_canonical_cache(
            args.cache_manifest,
            validated_receipt=args.cache_validation_receipt,
            required_members=required_members if profile["compact_cache"] else None,
        )
        if not required_members.issubset({member.key for member in cache.members}):
            raise TrainingContractError("worker compact cache is missing reviewed fold members")
        args.pilot_subjects = tuple(record["pilot_subjects"])
        args.tensorflow_version = runner._require_locked_tf24_runtime()
        tf = seed_model(args.model_seed)
        try:
            result = runner._run_fold(
                cache=cache,
                args=args,
                fold=fold,
                fold_index=args.fold_index,
                bulk_root=Path(args.bulk_root),
            )
        except Exception as error:
            directory = runner.run_directory(
                runner.safe_fold_id(args.run_prefix, args.fold_index, fold.test_subject),
                bulk_root=Path(args.bulk_root),
            )
            execution_path = directory / "execution.json"
            if getattr(args, "active_fold_directory", None) == str(directory) and execution_path.is_file():
                current = json.loads(execution_path.read_text(encoding="utf-8"))
                if current.get("status") == "running":
                    runner.transition_run(directory, current, "failed", failure=runner.failure_record(error))
            raise
        if result.get("status") != "verified":
            raise TrainingContractError("worker fold did not produce verified lineage")
        result["fold_protocol_subject"] = item["test_subject"]
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if tf is not None:
            cleanup_model_state(tf)
        if cache is not None:
            cache.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-manifest", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--environment-manifest", required=True)
    parser.add_argument("--bulk-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--selection-seed", type=int, required=True)
    parser.add_argument("--subject-count", type=int, required=True)
    parser.add_argument("--model-seed", type=int, required=True)
    parser.add_argument("--cap", type=int, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--resource-profile", required=True)
    parser.add_argument("--protocol-output", required=True)
    parser.add_argument("--resource-evidence", required=True)
    parser.add_argument("--approved-protocol-sha256", required=True)
    parser.add_argument("--cache-validation-receipt", required=True)
    parser.add_argument("--label-evidence-receipt")
    parser.add_argument("--fold-index", type=int, required=True)
    return parser


if __name__ == "__main__":
    parsed = _parser().parse_args()
    try:
        raise SystemExit(run(parsed))
    except TrainingContractError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
