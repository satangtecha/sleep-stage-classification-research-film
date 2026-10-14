"""Run one stage of one new subject fold in a fresh locked TF2.4 process."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import subject_generalization_runner as runner
from .subject_generalization_fold_worker import _build_fold
from .trainer import TrainingContractError, cleanup_model_state, prepare_run, run_stage, seed_model, transition_run


def run(args) -> int:
    profile = runner._resource_profile(args)
    if not profile["fresh_process_per_stage"]:
        raise TrainingContractError("stage worker requires the fresh-stage resource profile")
    if args.stage not in runner.STAGES:
        raise TrainingContractError("stage worker stage is invalid")
    record_plan = runner._build_light_plan(args)
    runner._require_approved_protocol(args, record_plan)
    item, fold, required_members = _build_fold(args, record_plan, args.fold_index)
    run_id = runner.safe_fold_id(args.run_prefix, args.fold_index, fold.test_subject)
    directory = runner.run_directory(run_id, bulk_root=Path(args.bulk_root))
    if args.stage != "stage1" and not directory.exists():
        raise TrainingContractError("stage continuation namespace is missing")
    runtime_root = Path(args.runtime_root)
    attempt_marker = runtime_root / "worker-attempts" / ("fold-%02d-%s.lock" % (args.fold_index + 1, args.stage))
    if profile.get("quality_track"):
        runner._create_marker(attempt_marker)
    checks = runner._probe_live_capacity_with_wait(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
        wait_seconds=profile["capacity_wait_seconds"],
        poll_seconds=profile["capacity_poll_seconds"],
        require_idle_gpu=profile.get("quality_track", False),
    )
    admission_path = None
    if profile.get("quality_track"):
        admission_path = runner._persist_quality_admission(
            runtime_root, args, profile, args.fold_index, args.stage, checks,
            record_plan["source_code_binding"], runner._quality_source_bindings()[1],
            attempt_marker,
        )
    cache = None
    tf = None
    record = None
    args.active_fold_directory = None
    try:
        cache = runner.load_canonical_cache(
            args.cache_manifest,
            validated_receipt=args.cache_validation_receipt,
            required_members=required_members if profile["compact_cache"] else None,
        )
        if not required_members.issubset({member.key for member in cache.members}):
            raise TrainingContractError("stage worker compact cache is missing reviewed fold members")
        args.pilot_subjects = tuple(record_plan["pilot_subjects"])
        args.tensorflow_version = runner._require_locked_tf24_runtime()
        config = runner._fold_config(cache, fold.plan, args, fold, run_id)
        directory, record = prepare_run(
            run_id,
            config,
            bulk_root=Path(args.bulk_root),
            resume=args.stage != "stage1",
        )
        args.active_fold_directory = str(directory)
        progress = record.get("stage_progress", {})
        if args.stage != "stage1" and progress.get("next_stage") != args.stage:
            raise TrainingContractError("stage continuation does not match reviewed next-stage lineage")
        parent = None if args.stage == "stage1" else progress.get("checkpoint")
        if args.stage != "stage1" and not isinstance(parent, dict):
            raise TrainingContractError("stage continuation checkpoint lineage is missing")
        record = transition_run(
            directory,
            record,
            "running",
            stage_progress={
                "next_stage": args.stage,
                "last_epoch": 0,
                "checkpoint": parent,
                "inflight": True,
            },
        )
        tf = seed_model(args.model_seed)
        stage_result = run_stage(
            cache,
            fold.plan,
            runner.MODEL_PROTOCOL_ID,
            args.stage,
            directory,
            parent=parent,
            weight_decay=0.0,
            microbatch={
                "stage1": profile["stage1_microbatch"],
                "stage2": profile["stage2_microbatch"],
                "stage3": profile["stage3_microbatch"],
            }[args.stage],
            stage2_loss_adaptation=(profile["stage2_loss_adaptation"] if args.stage == "stage2" else None),
            stage3_gradient_clip_norm=1.0 if args.stage == "stage3" else None,
            stage3_stability_adaptation_id=(runner.STAGE3_STABILITY_ADAPTATION_ID if args.stage == "stage3" else None),
            stage3_optimizer_adaptation_id=(profile.get("stage3_optimizer_adaptation_id") if args.stage == "stage3" else None),
            stage3_loss_adaptation_id=(profile.get("stage3_loss_adaptation_id") if args.stage == "stage3" else None),
            epochs_override=profile["stage_epochs"],
            quality_class_weighting_id=(profile.get("class_weighting_id") if args.stage == "stage3" else None),
            quality_early_stopping_id=(profile.get("early_stopping_id") if args.stage == "stage3" else None),
            subject_normalization_id=profile.get("subject_normalization_id"),
            train_augmentation_id=profile.get("train_augmentation_id"),
        )
        if tf is not None:
            cleanup_model_state(tf)
            tf = None
        if cache is not None:
            cache.close()
            cache = None
        cleanup_path = None
        if profile.get("quality_track"):
            cleanup_path = runner._persist_quality_cleanup(
                runtime_root, args, args.fold_index, args.stage,
                attempt_marker, admission_path,
            )
        artifacts = dict(record.get("stage_artifacts", {}))
        artifacts[args.stage] = {
            "checkpoint_path": stage_result["checkpoint_path"],
            "checkpoint_hash": stage_result["checkpoint_hash"],
            "parent_checkpoint_path": None if args.stage == "stage1" else parent["checkpoint_path"],
            "parent_checkpoint_hash": None if args.stage == "stage1" else parent["checkpoint_hash"],
            "route": stage_result["route"],
            "metrics_path": stage_result["metrics_path"],
            "metrics_file_sha256": runner.sha256_file(stage_result["metrics_path"]),
            "metrics_artifact_sha256": stage_result["metrics"]["artifact_sha256"],
        }
        lineage = runner._lineage_checkpoint(stage_result)
        next_stage = runner.STAGES[runner.STAGES.index(args.stage) + 1] if args.stage != "stage3" else None
        runtime_evidence = dict(record.get("quality_runtime_evidence", {}))
        if profile.get("quality_track"):
            runtime_evidence[args.stage] = {
                "resource_admission_path": str(admission_path.resolve()),
                "resource_admission_sha256": runner.sha256_file(admission_path),
                "attempt_marker_path": str(attempt_marker.resolve()),
                "attempt_marker_sha256": runner.sha256_file(attempt_marker),
                "cleanup_path": str(cleanup_path.resolve()),
                "cleanup_sha256": runner.sha256_file(cleanup_path),
            }
        record = transition_run(
            directory,
            record,
            "completed" if args.stage == "stage3" else "running",
            checkpoint_hash=lineage["checkpoint_hash"],
            checkpoint_path=lineage["checkpoint_path"],
            stage_artifacts=artifacts,
            stage_progress={
                "next_stage": next_stage,
                "last_epoch": 0,
                "checkpoint": lineage,
                "inflight": False,
            },
            quality_runtime_evidence=runtime_evidence,
        )
    except Exception as error:
        if directory is not None and getattr(args, "active_fold_directory", None) == str(directory):
            execution_path = directory / "execution.json"
            if execution_path.is_file():
                current = json.loads(execution_path.read_text(encoding="utf-8"))
                if current.get("status") == "running":
                    transition_run(directory, current, "failed", failure=runner.failure_record(error))
        raise
    finally:
        if tf is not None:
            cleanup_model_state(tf)
        if cache is not None:
            cache.close()
    if args.stage == "stage3":
        verification = runner._verify_fold(directory)
        result = {
            "fold_index": fold.fold_index,
            "run_id": run_id,
            "test_subject": fold.test_subject,
            "validation_subject": fold.validation_subject,
            "directory": str(directory),
            "execution_sha256": verification["verification"]["execution_sha256"],
            "status": "verified",
            "verifier_python": runner.LOCKED_TF24_PYTHON,
        }
    else:
        result = {
            "fold_index": fold.fold_index,
            "run_id": run_id,
            "test_subject": fold.test_subject,
            "validation_subject": fold.validation_subject,
            "directory": str(directory),
            "stage": args.stage,
            "execution_sha256": runner.sha256_file(directory / "execution.json"),
            "status": "stage_completed",
            "verifier_python": runner.LOCKED_TF24_PYTHON,
        }
    if profile.get("quality_track"):
        result["cleanup_path"] = str(cleanup_path)
        result["cleanup_sha256"] = runner.sha256_file(cleanup_path)
    print(json.dumps(result, sort_keys=True))
    return 0


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
    parser.add_argument("--stage", choices=("stage1", "stage2", "stage3"), required=True)
    return parser


if __name__ == "__main__":
    parsed = _parser().parse_args()
    try:
        raise SystemExit(run(parsed))
    except TrainingContractError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
