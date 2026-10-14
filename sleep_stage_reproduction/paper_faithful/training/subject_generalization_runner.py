"""Exactly-once six-subject held-out pilot runner.

This runner trains fresh fold models with PAPER_TEXT_V1 semantics while
recording SUBJECT_GENERALIZATION_V1 as the evaluation protocol.  It never
opens an r19 run directory or consumes an r19 checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .cache_loader import (
    VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE,
    VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE,
    VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE,
    VALIDATION_RECEIPT_TYPE,
    load_canonical_cache,
)
from .run_manifest import sha256_file
from .quality_sampling import (
    QUALITY_CAP_POLICY,
    QUALITY_CLASS_WEIGHTING_ID,
    QUALITY_EARLY_STOPPING_ID,
    balanced_class_weights,
    class_counts,
    load_verified_stage3_labels,
    sample_class_balanced_members_per_subject,
)
from .splits import EpochMember, SplitPlan, validate_no_leakage
from .storage import require_bulk_path, run_directory
from .subject_generalization import (
    DEFAULT_PILOT_SUBJECT_COUNT,
    DEFAULT_RUN_PREFIX,
    MODEL_PROTOCOL_ID,
    SUBJECT_GENERALIZATION_PROTOCOL_ID,
    build_pilot_folds,
    capped_fold_record,
    cap_subject_balanced_plan,
    canonical_json,
    protocol_record,
    safe_fold_id,
    SubjectFold,
    SAMPLED_CAP_POLICY,
    sample_record_members,
    sample_record_members_per_subject,
)
from .trainer import (
    QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID,
    QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID,
    SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID,
    TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID,
    STAGE3_STABILITY_ADAPTATION_ID,
    TrainingContractError,
    cleanup_model_state,
    failure_record,
    prepare_run,
    run_stage,
    seed_model,
    stage_spec,
    transition_run,
    STAGES,
)


DEFAULT_CAP = 128
DEFAULT_MODEL_SEED = 42
MIN_PHYSICAL_MEMORY_MB = 4096
MIN_COMMIT_HEADROOM_MB = 8192
MIN_C_FREE_GIB = 15.0
MIN_E_FREE_GIB = 15.0
QUALITY_CONSERVATIVE_STAGE3_MIN_C_FREE_GIB = 12.0
QUALITY_CAP32_E6_MIN_C_FREE_GIB = 10.0
LOCKED_TF24_PYTHON = "/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python"
RESOURCE_MAX_AGE_SECONDS = 120
RESOURCE_LIMITED_PROFILE_ID = "RESOURCE_LIMITED_CAP32_E6_V1"
RESOURCE_LIMITED_OFFLINE_PROFILE_ID = "RESOURCE_LIMITED_OFFLINE_CAP32_E6_V1"
RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID = "RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_CAP32_E6_V1"
RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V1"
RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V2_LOW_HEADROOM"
RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V3_LOW_COMPUTE"
RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V4_LOW_COMPUTE"
RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V5_GPU_PROBE_FIXED"
RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V6_DETACHED_GPU_RUN"
RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V7_FRESH_PROCESS_PER_FOLD"
RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V8_FRESH_PROCESS_PER_STAGE"
RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP16_E6_V9_MICROBATCH8_PER_STAGE"
RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V10_MICROBATCH8_PER_STAGE"
RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID = "RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V11_MICROBATCH8_PER_STAGE_WAIT_DRAIN"
QUALITY_BALANCED_CAP64_E12_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V1_FRESH_STAGE_WAIT_DRAIN"
QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V2_CONSERVATIVE_STAGE3_SGD"
QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V3_SUBJECT_ZSCORE"
QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V4_TRAIN_TIME_MASK"
QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V5_STAGE3_FOCAL_LOSS"
QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID = "QUALITY_BALANCED_CAP32_E6_V6_BALANCED_CE"
QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V7_STAGE3_FOCAL_C10"
QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID = "QUALITY_BALANCED_CAP64_E12_V8_STAGE3_FOCAL_C85"
QUALITY_PROFILE_IDS = (
    QUALITY_BALANCED_CAP64_E12_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID,
    QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID,
    QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID,
)
QUALITY_CAP64_E12_FOCAL_C85_MIN_C_FREE_GIB = 8.5
RESOURCE_LIMITED_CAP = 32
RESOURCE_LIMITED_STAGE_EPOCHS = 6
RESOURCE_LIMITED_MIN_PHYSICAL_MEMORY_MB = 3072
RESOURCE_LIMITED_MIN_COMMIT_HEADROOM_MB = 6144
RESOURCE_LIMITED_ULTRA_COMPACT_MIN_PHYSICAL_MEMORY_MB = 2048
RESOURCE_LIMITED_ULTRA_COMPACT_MIN_COMMIT_HEADROOM_MB = 4096
RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_MIN_PHYSICAL_MEMORY_MB = 1536
RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_MIN_COMMIT_HEADROOM_MB = 3072
RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_MIN_PHYSICAL_MEMORY_MB = 1024
RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_MIN_COMMIT_HEADROOM_MB = 2048
RESOURCE_LIMITED_MICRO_STAGE_MIN_PHYSICAL_MEMORY_MB = 1024
RESOURCE_LIMITED_MICRO_STAGE_MIN_COMMIT_HEADROOM_MB = 2048
QUALITY_SOURCE_FILES = {
    "runner": "subject_generalization_runner.py",
    "stage_worker": "subject_generalization_stage_worker.py",
    "fold_worker": "subject_generalization_fold_worker.py",
    "trainer": "trainer.py",
    "verifier": "verify_run.py",
    "sampler": "quality_sampling.py",
    "subject_generalization": "subject_generalization.py",
}


def _quality_source_bindings(source_directory=None) -> tuple[dict, dict]:
    """Return stable reviewed identities and the concrete files executing them.

    The reviewed protocol must survive the launcher's byte-identical relocation
    into an immutable source snapshot, so it records package-relative logical
    paths.  Runtime evidence separately records and hashes the absolute files
    that are actually imported from that snapshot.
    """

    root = Path(source_directory).resolve() if source_directory is not None else Path(__file__).resolve().parent
    identity = {}
    execution = {}
    for name, filename in QUALITY_SOURCE_FILES.items():
        path = (root / filename).resolve(strict=True)
        digest = sha256_file(path)
        identity[name] = {
            "logical_path": "paper_faithful/training/" + filename,
            "sha256": digest,
        }
        execution[name] = {"path": str(path), "sha256": digest}
    return identity, execution


def _resource_profile(args) -> dict:
    """Resolve an explicit resource-limited profile without changing defaults."""
    profile = getattr(args, "resource_profile", None)
    epochs = getattr(args, "epochs", None)
    if profile is None and epochs is None:
        return {
            "id": None,
            "cap": getattr(args, "cap", DEFAULT_CAP),
            "stage_epochs": None,
            "min_physical_memory_mb": MIN_PHYSICAL_MEMORY_MB,
            "min_commit_headroom_mb": MIN_COMMIT_HEADROOM_MB,
            "min_c_free_gib": MIN_C_FREE_GIB,
            "min_e_free_gib": MIN_E_FREE_GIB,
            "allow_offline_power": False,
            "ultra_compact": False,
            "compact_cache": False,
            "stage1_microbatch": 128,
            "stage2_microbatch": 128,
            "stage3_microbatch": 1,
            "stage2_loss_adaptation": None,
            "low_compute": False,
            "fresh_process_per_fold": False,
            "fresh_process_per_stage": False,
        }
    if profile not in (
        RESOURCE_LIMITED_PROFILE_ID,
        RESOURCE_LIMITED_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    ):
        raise TrainingContractError("unknown resource-limited profile")
    quality_profile = profile in QUALITY_PROFILE_IDS
    expected_cap = (32 if profile == QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID else 64) if quality_profile else (16 if profile == RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID else RESOURCE_LIMITED_CAP)
    expected_epochs = (6 if profile == QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID else 12) if quality_profile else RESOURCE_LIMITED_STAGE_EPOCHS
    if getattr(args, "cap", None) != expected_cap or epochs != expected_epochs:
        raise TrainingContractError(f"resource-limited profile requires cap{expected_cap} and {expected_epochs} epochs")
    if getattr(args, "subject_count", DEFAULT_PILOT_SUBJECT_COUNT) != DEFAULT_PILOT_SUBJECT_COUNT:
        raise TrainingContractError("resource-limited profile requires six pilot subjects")
    ultra_compact = profile in (
        RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    )
    compact_cache = profile in (
        RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    )
    low_headroom = profile in (
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    )
    low_compute = profile in (
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    )
    low_compute_v2 = profile in (
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        *QUALITY_PROFILE_IDS,
    )
    min_physical_memory_mb = (
        RESOURCE_LIMITED_MICRO_STAGE_MIN_PHYSICAL_MEMORY_MB
        if profile in (RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID) else
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_MIN_PHYSICAL_MEMORY_MB
        if low_compute_v2 else
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_MIN_PHYSICAL_MEMORY_MB
        if low_headroom else
        RESOURCE_LIMITED_ULTRA_COMPACT_MIN_PHYSICAL_MEMORY_MB
        if ultra_compact else RESOURCE_LIMITED_MIN_PHYSICAL_MEMORY_MB
    )
    min_commit_headroom_mb = (
        RESOURCE_LIMITED_MICRO_STAGE_MIN_COMMIT_HEADROOM_MB
        if profile in (RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID) else
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_MIN_COMMIT_HEADROOM_MB
        if low_compute_v2 else
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_MIN_COMMIT_HEADROOM_MB
        if low_headroom else
        RESOURCE_LIMITED_ULTRA_COMPACT_MIN_COMMIT_HEADROOM_MB
        if ultra_compact else RESOURCE_LIMITED_MIN_COMMIT_HEADROOM_MB
    )
    return {
        "id": profile,
        "cap": expected_cap,
        "stage_epochs": expected_epochs,
        "min_physical_memory_mb": min_physical_memory_mb,
        "min_commit_headroom_mb": min_commit_headroom_mb,
        # Quality runs store bulk data and output on E:.  Their C: floors are
        # explicit per version so a storage-only admission change is visible
        # in the immutable protocol rather than silently weakening the default.
        "min_c_free_gib": (
            QUALITY_CAP32_E6_MIN_C_FREE_GIB
            if profile in (QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID)
            else QUALITY_CAP64_E12_FOCAL_C85_MIN_C_FREE_GIB
            if profile == QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID
            else QUALITY_CONSERVATIVE_STAGE3_MIN_C_FREE_GIB
            if profile in (QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID)
            else MIN_C_FREE_GIB
        ),
        "min_e_free_gib": MIN_E_FREE_GIB,
        "allow_offline_power": profile in (
            RESOURCE_LIMITED_OFFLINE_PROFILE_ID,
            RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID,
            RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID,
            RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
            RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
            RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
            RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
            RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
            RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        ),
        "ultra_compact": ultra_compact,
        "compact_cache": compact_cache,
        "stage1_microbatch": 8 if profile in (RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID, RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID, *QUALITY_PROFILE_IDS) else (16 if low_compute_v2 else (32 if low_compute else 128)),
        "stage2_microbatch": 128,
        "stage3_microbatch": 1,
        "stage2_loss_adaptation": None,
        "low_compute": low_compute,
        "fresh_process_per_fold": profile in (
            RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
            *QUALITY_PROFILE_IDS,
        ),
        "fresh_process_per_stage": profile in (
            RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
            RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
            *QUALITY_PROFILE_IDS,
        ),
        "capacity_wait_seconds": 120 if profile in (RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID, *QUALITY_PROFILE_IDS) else 0,
        "capacity_poll_seconds": 5,
        "quality_track": quality_profile,
        "class_balanced_sampling": quality_profile,
        "class_weighting_id": QUALITY_CLASS_WEIGHTING_ID if quality_profile else None,
        "early_stopping_id": QUALITY_EARLY_STOPPING_ID if quality_profile else None,
        "stage3_optimizer_adaptation_id": (
            QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID
            if profile in (QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID) else None
        ),
        "subject_normalization_id": (
            SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID
            if profile == QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID else None
        ),
        "train_augmentation_id": (
            TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID
            if profile == QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID else None
        ),
        "stage3_loss_adaptation_id": (
            QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID
            if profile in (QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID, QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID) else None
        ),
    }


def _sample_members_for_profile(records, subjects, cap, seed, profile, labels=None):
    if profile.get("class_balanced_sampling"):
        if not isinstance(labels, dict):
            raise TrainingContractError("quality sampling requires verified Stage-3 labels")
        return sample_class_balanced_members_per_subject(records, subjects, cap, seed, labels)
    if profile["id"] is not None:
        return sample_record_members_per_subject(records, subjects, cap, seed)
    return sample_record_members(records, subjects, cap, seed)


def _lineage_checkpoint(stage_result: dict) -> dict:
    keys = ("checkpoint_path", "checkpoint_hash", "cache_hash", "protocol_id", "stage", "route")
    if not isinstance(stage_result, dict) or any(not isinstance(stage_result.get(key), str) for key in keys):
        raise TrainingContractError("subject-generalization stage result has no checkpoint lineage")
    return {key: stage_result[key] for key in keys}


def _hash_object(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    try:
        with Path(temporary).open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def _append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        value = dict(event)
        value.setdefault("timestamp", __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _create_marker(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise TrainingContractError(f"subject-generalization marker collision: {path}") from error
    else:
        os.close(descriptor)


def _load_resource_evidence(path: Path, *, now=None, min_physical_memory_mb=MIN_PHYSICAL_MEMORY_MB,
                            min_commit_headroom_mb=MIN_COMMIT_HEADROOM_MB,
                            min_c_free_gib=MIN_C_FREE_GIB, min_e_free_gib=MIN_E_FREE_GIB,
                            allow_offline_power=False) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise TrainingContractError("subject-generalization resource evidence is unreadable") from error
    if not isinstance(value, dict) or value.get("status") != "pass" or value.get("ready") is not True:
        raise TrainingContractError("subject-generalization resource gate did not pass")
    if value.get("protocol_id") != SUBJECT_GENERALIZATION_PROTOCOL_ID:
        raise TrainingContractError("subject-generalization resource protocol mismatch")
    try:
        timestamp_text = str(value["timestamp"]).replace("Z", "+00:00")
        # Windows PowerShell "o" timestamps can carry seven fractional
        # digits; Python 3.7's locked runtime accepts at most six.
        timestamp_text = re.sub(r"(\.\d{6})\d+(?=[+-]\d\d:\d\d$)", r"\1", timestamp_text)
        captured = datetime.fromisoformat(timestamp_text)
        if captured.tzinfo is None:
            raise ValueError("timestamp needs timezone")
        age = ((now or datetime.now(timezone.utc)) - captured).total_seconds()
        if not 0 <= age <= RESOURCE_MAX_AGE_SECONDS:
            raise ValueError("stale or future evidence")
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise TrainingContractError("subject-generalization resource evidence is stale or has invalid time") from error
    checks = value.get("checks")
    if not isinstance(checks, dict):
        raise TrainingContractError("subject-generalization resource checks are missing")
    offline_authorized = allow_offline_power and checks.get("offline_power_authorized") is True
    if (checks.get("power_online") is not True or checks.get("critical") is not False) and not offline_authorized:
        raise TrainingContractError("subject-generalization power gate failed")
    _require_finite_at_least(checks.get("physical_memory_available_mb"), min_physical_memory_mb, "physical-memory")
    _require_finite_at_least(checks.get("commit_headroom_mb"), min_commit_headroom_mb, "commit-headroom")
    _require_finite_at_least(checks.get("c_free_gib"), min_c_free_gib, "C storage")
    _require_finite_at_least(checks.get("e_free_gib"), min_e_free_gib, "E storage")
    for key in ("windows_gpu_compute_process_count", "wsl_gpu_compute_process_count",
                "windows_gpu_probe_exit_code", "wsl_gpu_probe_exit_code"):
        if type(checks.get(key)) is not int or checks[key] != 0:
            raise TrainingContractError("subject-generalization GPU probe failed: " + key)
    return value


def _probe_live_capacity(*, min_physical_memory_mb=MIN_PHYSICAL_MEMORY_MB,
                         min_commit_headroom_mb=MIN_COMMIT_HEADROOM_MB,
                         min_c_free_gib=MIN_C_FREE_GIB, min_e_free_gib=MIN_E_FREE_GIB,
                         allow_offline_power=False, require_idle_gpu=False) -> dict:
    """Recheck host capacity after long scans and before each training stage.

    The timestamped idle-GPU receipt is a preflight observation, not a lease.
    GPU ownership after TensorFlow initializes is checked by the trainer.
    """
    import base64
    script = r'''
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
Add-Type -AssemblyName System.Windows.Forms
$power = [System.Windows.Forms.SystemInformation]::PowerStatus
[ordered]@{
 power_online = ($power.PowerLineStatus.ToString() -eq 'Online')
 critical = (($power.BatteryChargeStatus -band [System.Windows.Forms.BatteryChargeStatus]::Critical) -ne 0)
 physical_memory_available_mb = [double]$os.FreePhysicalMemory / 1024
 commit_headroom_mb = [double]$os.FreeVirtualMemory / 1024
 c_free_gib = [double](Get-PSDrive C).Free / 1GB
 e_free_gib = [double](Get-PSDrive E).Free / 1GB
} | ConvertTo-Json -Compress
'''
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        probe = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                               timeout=30, check=False)
        if probe.returncode != 0:
            raise ValueError("host probe failed")
        checks = json.loads(probe.stdout.lstrip("\ufeff"))
        if (checks.get("power_online") is not True or checks.get("critical") is not False) and not allow_offline_power:
            raise ValueError("AC power unavailable or critical")
        for key, threshold in (("physical_memory_available_mb", min_physical_memory_mb),
                               ("commit_headroom_mb", min_commit_headroom_mb),
                               ("c_free_gib", min_c_free_gib), ("e_free_gib", min_e_free_gib)):
            _require_finite_at_least(checks.get(key), threshold, key)
        if require_idle_gpu:
            gpu = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                timeout=30, check=False,
            )
            if gpu.returncode != 0:
                raise ValueError("GPU process probe failed")
            pids = sorted({line.strip() for line in gpu.stdout.splitlines() if line.strip()})
            if pids:
                raise ValueError("GPU is not idle before cache load")
            checks["gpu_compute_process_pids"] = pids
            checks["gpu_probe_exit_code"] = gpu.returncode
        return checks
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError) as error:
        observed = ""
        if isinstance(locals().get("checks"), dict):
            observed = "; observed=" + json.dumps(checks, sort_keys=True, separators=(",", ":"))
        raise TrainingContractError("live host capacity gate failed: " + str(error) + observed) from error


def _probe_live_capacity_with_wait(*, min_physical_memory_mb=MIN_PHYSICAL_MEMORY_MB,
                                   min_commit_headroom_mb=MIN_COMMIT_HEADROOM_MB,
                                   min_c_free_gib=MIN_C_FREE_GIB, min_e_free_gib=MIN_E_FREE_GIB,
                                   allow_offline_power=False, wait_seconds=0,
                                   poll_seconds=5, require_idle_gpu=False) -> dict:
    """Wait only for transient memory pressure between fresh stage workers."""
    deadline = time.monotonic() + max(0, float(wait_seconds))
    while True:
        try:
            return _probe_live_capacity(
                min_physical_memory_mb=min_physical_memory_mb,
                min_commit_headroom_mb=min_commit_headroom_mb,
                min_c_free_gib=min_c_free_gib,
                min_e_free_gib=min_e_free_gib,
                allow_offline_power=allow_offline_power,
                require_idle_gpu=require_idle_gpu,
            )
        except TrainingContractError as error:
            message = str(error)
            if wait_seconds <= 0 or (
                "physical_memory_available_mb" not in message
                and "commit_headroom_mb" not in message
            ):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(max(0.1, float(poll_seconds)), remaining))


def _publish_protocol(path: Path, value: dict) -> None:
    """Publish once without replacing a previous approved plan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise TrainingContractError("protocol already exists; choose a fresh plan path") from error


def _persist_quality_admission(runtime_root: Path, args, profile: dict, fold_index: int,
                               stage: str, checks: dict, source_code_binding: dict,
                               execution_source_binding: dict, attempt_marker: Path) -> Path:
    """Persist the successful pre-cache admission once for auditability."""

    path = runtime_root / "resource-admission" / ("fold-%02d-%s.json" % (fold_index + 1, stage))
    record = {
        "schema_version": 1,
        "artifact_type": "PLAN16_PRE_CACHE_RESOURCE_ADMISSION_V1",
        "status": "pass",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_prefix": args.run_prefix,
        "fold_index": fold_index,
        "stage": stage,
        "checks": checks,
        "thresholds": {
            "physical_memory_available_mb": profile["min_physical_memory_mb"],
            "commit_headroom_mb": profile["min_commit_headroom_mb"],
            "c_free_gib": profile.get("min_c_free_gib", MIN_C_FREE_GIB),
            "e_free_gib": profile.get("min_e_free_gib", MIN_E_FREE_GIB),
            "gpu_compute_process_count": 0,
        },
        "protocol_path": str(Path(args.protocol_output).resolve()),
        "protocol_sha256": args.approved_protocol_sha256,
        "attempt_marker_path": str(attempt_marker.resolve()),
        "attempt_marker_sha256": sha256_file(attempt_marker),
        "source_code_binding": source_code_binding,
        "execution_source_binding": execution_source_binding,
        "timing": "persisted_before_cache_load",
    }
    _publish_protocol(path, record)
    return path


def _persist_quality_cleanup(runtime_root: Path, args, fold_index: int, stage: str,
                             attempt_marker: Path, admission_path: Path) -> Path:
    """Prove that model state and the native cache closed before worker exit."""

    path = runtime_root / "worker-cleanup" / ("fold-%02d-%s.json" % (fold_index + 1, stage))
    record = {
        "schema_version": 1,
        "artifact_type": "PLAN16_STAGE_CLEANUP_V1",
        "status": "pass",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_prefix": args.run_prefix,
        "fold_index": fold_index,
        "stage": stage,
        "attempt_marker_path": str(attempt_marker.resolve()),
        "attempt_marker_sha256": sha256_file(attempt_marker),
        "resource_admission_path": str(admission_path.resolve()),
        "resource_admission_sha256": sha256_file(admission_path),
        "cleanup": "tensorflow_state_released_and_cache_closed_before_worker_exit",
    }
    _publish_protocol(path, record)
    return path


def _require_approved_protocol(args, planned):
    expected = getattr(args, "approved_protocol_sha256", None)
    path = Path(args.protocol_output)
    if not isinstance(expected, str) or len(expected) != 64 or not path.is_file():
        raise TrainingContractError("training requires the reviewed protocol file and SHA-256")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected or raw != canonical_json(planned).encode("utf-8"):
        raise TrainingContractError("reviewed protocol differs from current inputs or execution plan")


def _initialize_runtime(runtime_root, run_prefix, protocol, resource_path):
    """Own the new directory before recording anything; preserve failed setup.

    A mkdir collision is never ours to modify. Once created, this namespace
    is consumed, including failures before either marker exists.
    """
    runtime_root.mkdir(parents=True, exist_ok=False)
    lifecycle = runtime_root / "lifecycle.jsonl"
    try:
        _atomic_json(runtime_root / "protocol.json", protocol)
        _create_marker(runtime_root / (run_prefix + ".dispatch.lock"))
        _create_marker(runtime_root / (run_prefix + ".attempt.lock"))
        _append_event(lifecycle, {"event": "dispatch_created", "run_prefix": run_prefix,
                                 "resource_evidence": str(resource_path),
                                 "resource_evidence_sha256": sha256_file(resource_path)})
    except Exception as error:
        failure = {"schema_version": 1, "status": "failed", "phase": "pre_dispatch_setup",
                   "run_prefix": run_prefix, "namespace_consumed": True,
                   "completed_folds": [], "failure": failure_record(error)}
        try:
            _atomic_json(runtime_root / "failure.json", failure)
        except OSError as recording_error:
            # A full/offline disk may prevent durable evidence: make that
            # explicit on stderr instead of pretending persistence succeeded.
            failure["failure_recording_error"] = str(recording_error)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        raise TrainingContractError("pre-dispatch setup failed; namespace consumed: " + str(runtime_root)) from error
    return lifecycle


def _require_finite_at_least(value, threshold: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrainingContractError("subject-generalization %s value is not numeric" % label)
    import math
    if not math.isfinite(float(value)) or float(value) < threshold:
        raise TrainingContractError("subject-generalization %s gate failed" % label)


def _require_locked_tf24_runtime() -> str:
    actual = str(Path(sys.executable).resolve())
    expected = str(Path(LOCKED_TF24_PYTHON).resolve())
    if actual != expected:
        raise TrainingContractError("subject-generalization must run with locked TF2.4 Python")
    try:
        import tensorflow as tf
    except ImportError as error:
        raise TrainingContractError("subject-generalization locked TensorFlow 2.4 is unavailable") from error
    version = getattr(tf, "__version__", None)
    if version != "2.4.0":
        raise TrainingContractError("subject-generalization requires TensorFlow 2.4.0")
    return version


def _read_members_for_plan(manifest_path: str | Path) -> tuple[EpochMember, ...]:
    """Read verified-cache record membership for planning; never read tensors."""

    path = Path(manifest_path).resolve(strict=True)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise TrainingContractError("subject-generalization cache manifest is unreadable") from error
    bindings = manifest.get("record_bindings")
    if not isinstance(bindings, list):
        raise TrainingContractError("subject-generalization cache record bindings are missing")
    records = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            raise TrainingContractError("subject-generalization cache record binding is malformed")
        record_id = binding.get("record_id")
        subject_id = binding.get("subject_id")
        epochs = binding.get("epochs")
        if not isinstance(record_id, str) or not isinstance(subject_id, str) or not isinstance(epochs, int) or epochs < 0:
            raise TrainingContractError("subject-generalization cache record binding is invalid")
        if record_id in records:
            raise TrainingContractError("subject-generalization cache record binding is duplicated")
        records[record_id] = (subject_id, epochs)
    members = set()
    for record_id, (subject_id, epochs) in records.items():
        # The full cache manifest has already been independently validated by
        # the r19 run.  This lightweight planning path expands only its
        # immutable record/epoch declarations and never opens tensor payloads.
        members.update(EpochMember(subject_id, record_id, epoch) for epoch in range(epochs))
    if not members:
        raise TrainingContractError("subject-generalization cache has no planned members")
    return tuple(sorted(members))


def _read_record_bindings_for_plan(manifest_path: str | Path) -> tuple[tuple[str, str, int], ...]:
    """Read compact record declarations without materializing epoch objects."""

    path = Path(manifest_path).resolve(strict=True)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise TrainingContractError("subject-generalization cache manifest is unreadable") from error
    bindings = manifest.get("record_bindings")
    if not isinstance(bindings, list):
        raise TrainingContractError("subject-generalization cache record bindings are missing")
    records = []
    seen = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            raise TrainingContractError("subject-generalization cache record binding is malformed")
        record_id, subject_id, epochs = binding.get("record_id"), binding.get("subject_id"), binding.get("epochs")
        if not isinstance(record_id, str) or not record_id or not isinstance(subject_id, str) or not subject_id or isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 0 or record_id in seen:
            raise TrainingContractError("subject-generalization cache record binding is invalid")
        seen.add(record_id)
        if epochs:
            records.append((record_id, subject_id, epochs))
    if not records:
        raise TrainingContractError("subject-generalization cache has no non-empty records")
    return tuple(sorted(records, key=lambda item: (item[1], item[0])))


def _stream_membership_hash(records: tuple[tuple[str, str, int], ...], subjects: set[str]) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    record_count = 0
    epoch_count = 0
    for record_id, subject_id, epochs in sorted(records, key=lambda item: (item[1], item[0])):
        if subject_id not in subjects:
            continue
        record_count += 1
        epoch_count += epochs
        for epoch in range(epochs):
            digest.update(f"{subject_id}/{record_id}/{epoch:08d}\n".encode("utf-8"))
    return digest.hexdigest(), record_count, epoch_count


def _stream_subject_balanced_cap(
    records: tuple[tuple[str, str, int], ...], subjects: set[str], cap: int
) -> tuple[str, int, int, int]:
    """Hash the exact deterministic subject-balanced cap without tensors."""

    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise TrainingContractError("pilot cap must be positive")
    groups = {subject: [] for subject in sorted(subjects)}
    for record_id, subject_id, epochs in records:
        if subject_id in groups:
            groups[subject_id].append((record_id, epochs))
    if not groups or any(not values for values in groups.values()):
        raise TrainingContractError("subject-generalization cap has an empty subject group")

    def total_epochs(values):
        return sum(epochs for _, epochs in values)

    def member_at(values, offset):
        for record_id, epochs in values:
            if offset < epochs:
                return record_id, offset
            offset -= epochs
        raise TrainingContractError("subject-generalization cap member lookup failed")

    selected = []
    max_epochs = max(total_epochs(values) for values in groups.values())
    position = 0
    ordered_subjects = tuple(sorted(groups))
    while len(selected) < cap and position < max_epochs:
        for subject_id in ordered_subjects:
            values = groups[subject_id]
            if position < total_epochs(values):
                record_id, epoch = member_at(values, position)
                selected.append("%s/%s/%08d" % (subject_id, record_id, epoch))
                if len(selected) == cap:
                    break
        position += 1
    if not selected:
        raise TrainingContractError("subject-generalization cap leaves an empty split")
    digest = hashlib.sha256(("\n".join(sorted(selected)) + "\n").encode("utf-8")).hexdigest()
    record_count = len({(key.split("/", 2)[0], key.split("/", 2)[1]) for key in selected})
    subject_count = len({key.split("/", 1)[0] for key in selected})
    return digest, record_count, len(selected), subject_count


def _add_runtime_binding(record: dict) -> dict:
    """Bind the interpreter and verifier identity in the protocol itself."""

    record["runtime_binding"] = {
        "locked_python_executable": LOCKED_TF24_PYTHON,
        "tensorflow_version": "2.4.0",
        "standalone_verifier_command": [
            LOCKED_TF24_PYTHON,
            "-m",
            "paper_faithful.training.verify_run",
            "--run-dir",
            "<fold-run-directory>",
        ],
        "trainer_runtime_check": "exact_interpreter_path_and_tensorflow_version_before_markers",
    }
    return record


def _build_light_plan(args) -> dict:
    profile = _resource_profile(args)
    for label in ("selection_seed", "model_seed"):
        seed = getattr(args, label)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise TrainingContractError(label + " must be an unsigned 32-bit integer")
    if isinstance(args.subject_count, bool) or not isinstance(args.subject_count, int) or args.subject_count < 2:
        raise TrainingContractError("subject count must be at least two")
    records = _read_record_bindings_for_plan(args.cache_manifest)
    subjects = sorted({subject_id for _, subject_id, _ in records})
    if len(subjects) < max(3, args.subject_count):
        raise TrainingContractError("subject-generalization pilot subject count exceeds cache subjects")
    import random
    random.Random(args.selection_seed).shuffle(subjects)
    selected = tuple(subjects[:args.subject_count])
    labels = None
    label_evidence = None
    if profile.get("class_balanced_sampling"):
        label_receipt = getattr(args, "label_evidence_receipt", None)
        if not label_receipt:
            raise TrainingContractError("quality planning requires --label-evidence-receipt")
        try:
            labels, label_evidence = load_verified_stage3_labels(
                args.cache_manifest, label_receipt, selected
            )
        except (OSError, UnicodeError, ValueError) as error:
            raise TrainingContractError("quality label evidence failed: " + str(error)) from error
    folds = []
    fold_ids = []
    for index, test_subject in enumerate(selected):
        validation_subject = selected[(index + 1) % len(selected)]
        # The resource-limited compact profile is an explicitly bounded
        # six-subject pilot.  Other profiles retain their historical
        # full-cohort semantics, so only the compact profile is restricted to
        # the selected cohort here.
        cohort = set(selected) if profile["id"] is not None else set(subjects)
        train_subject_set = cohort - {test_subject, validation_subject}
        validation_full_hash, validation_full_records, validation_full_epochs = _stream_membership_hash(records, {validation_subject})
        test_full_hash, test_full_records, test_full_epochs = _stream_membership_hash(records, {test_subject})
        train_full_hash, train_full_records, train_full_epochs = _stream_membership_hash(records, train_subject_set)
        def sample_info(subject_set):
            values = _sample_members_for_profile(records, subject_set, args.cap, args.selection_seed, profile, labels)
            digest = hashlib.sha256(("\n".join(sorted(item.key for item in values)) + "\n").encode("utf-8")).hexdigest()
            counts = class_counts(values, labels) if labels is not None else None
            return digest, len({item.record_id for item in values}), len(values), len({item.subject_id for item in values}), counts
        validation_hash, validation_records, validation_epochs, validation_subjects, validation_counts = sample_info({validation_subject})
        test_hash, test_records, test_epochs, test_subjects, test_counts = sample_info({test_subject})
        train_hash, train_records, train_epochs, train_subjects_seen, train_counts = sample_info(train_subject_set)
        fold_id = safe_fold_id(args.run_prefix, index, test_subject)
        fold_ids.append(fold_id)
        folds.append({
            "fold_index": index,
            "test_subject": test_subject,
            "validation_subject": validation_subject,
            "train_subject_count": len(train_subject_set),
            "capped_train_subject_count": train_subjects_seen,
            "capped_validation_subject_count": validation_subjects,
            "capped_test_subject_count": test_subjects,
            "train_record_count": train_records,
            "validation_record_count": validation_records,
            "test_record_count": test_records,
            "train_epoch_count": train_epochs,
            "validation_epoch_count": validation_epochs,
            "test_epoch_count": test_epochs,
            "uncapped_split_epoch_counts": {"train": train_full_epochs, "validation": validation_full_epochs, "test": test_full_epochs},
            "uncapped_split_membership_hashes": {"train": train_full_hash, "validation": validation_full_hash, "test": test_full_hash},
            "split_membership_hashes": {"train": train_hash, "validation": validation_hash, "test": test_hash},
            "cap": args.cap,
            "cap_policy": QUALITY_CAP_POLICY if profile.get("class_balanced_sampling") else SAMPLED_CAP_POLICY,
            "run_id": fold_id,
        })
        if labels is not None:
            folds[-1]["class_counts"] = {
                "train": train_counts,
                "validation": validation_counts,
                "test": test_counts,
            }
    record = protocol_record(
        cache_manifest=str(Path(args.cache_manifest).resolve()),
        cache_hash=sha256_file(args.cache_manifest),
        source_manifest=str(Path(args.source_manifest).resolve()),
        source_hash=sha256_file(args.source_manifest),
        environment_manifest=str(Path(args.environment_manifest).resolve()),
        environment_hash=sha256_file(args.environment_manifest),
        run_prefix=args.run_prefix,
        selection_seed=args.selection_seed,
        pilot_subjects=selected,
        fold_ids=fold_ids,
    )
    record["cache_validation_mode"] = "manifest_record_epoch_declarations_only; full cache validation required before training"
    receipt = getattr(args, "cache_validation_receipt", None)
    if receipt:
        receipt_path = Path(receipt).resolve(strict=True)
        try:
            receipt_type = json.loads(receipt_path.read_text(encoding="utf-8")).get("receipt_type")
        except (OSError, UnicodeError, ValueError, AttributeError) as error:
            raise TrainingContractError("cache validation receipt is unreadable") from error
        if receipt_type == VALIDATION_RECEIPT_TYPE:
            record["cache_validation_mode"] = "standalone_full_validation_receipt_v1"
        elif receipt_type == VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE:
            record["cache_validation_mode"] = "prior_full_cache_validator_evidence_receipt_v1"
        elif receipt_type == VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE:
            record["cache_validation_mode"] = "prior_full_cache_validator_evidence_compact_selection_receipt_v1"
        elif receipt_type == VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE:
            record["cache_validation_mode"] = "prior_full_cache_validator_evidence_compact_selection_metadata_receipt_v1"
        else:
            raise TrainingContractError("cache validation receipt type is unsupported")
        record["cache_validation_receipt"] = str(receipt_path)
        record["cache_validation_receipt_sha256"] = sha256_file(receipt_path)
    record["folds"] = folds
    record["cap"] = args.cap
    record["model_seed"] = args.model_seed
    record["purpose"] = "engineering_smoke_test_not_full_generalization_estimate"
    record["cap_policy"] = QUALITY_CAP_POLICY if profile.get("class_balanced_sampling") else SAMPLED_CAP_POLICY
    record["stage_specs"] = _stage_specs(profile["stage_epochs"], profile)
    if profile["fresh_process_per_stage"]:
        record["execution_strategy"] = "fresh_locked_tf24_process_per_stage_per_fold"
    elif profile["fresh_process_per_fold"]:
        record["execution_strategy"] = "fresh_locked_tf24_process_per_fold"
    else:
        record["execution_strategy"] = "single_locked_tf24_process"
    record["fresh_process_per_fold"] = profile["fresh_process_per_fold"]
    record["fresh_process_per_stage"] = profile["fresh_process_per_stage"]
    if profile["id"] is not None:
        record["resource_profile"] = profile["id"]
        record["stage_epochs"] = profile["stage_epochs"]
        record["resource_gate_thresholds"] = {
            "physical_memory_available_mb": profile["min_physical_memory_mb"],
            "commit_headroom_mb": profile["min_commit_headroom_mb"],
            # Keep the plan receipt byte-for-byte consistent with the runtime
            # admission record.  Some quality profiles deliberately use a
            # narrower C: floor because artifacts live on E:.
            "c_free_gib": profile["min_c_free_gib"],
            "e_free_gib": profile["min_e_free_gib"],
        }
        record["offline_power_authorized"] = profile["allow_offline_power"]
        record["capacity_wait_seconds"] = profile["capacity_wait_seconds"]
        record["capacity_poll_seconds"] = profile["capacity_poll_seconds"]
        record["capacity_wait_strategy"] = "drain_after_previous_stage_exit" if profile["capacity_wait_seconds"] else "none"
    if profile.get("quality_track"):
        source_code_binding, _ = _quality_source_bindings()
        record["quality_track"] = {
            "track_id": "SUBJECT_GENERALIZATION_QUALITY_PLAN16_V1",
            "paper_exact": False,
            "class_weighting": {
                "id": QUALITY_CLASS_WEIGHTING_ID,
                "formula": "n_train/(5*n_class)",
                "source_split": "train_only",
                "zero_class_policy": "fail_closed",
            },
            "early_stopping": _stage_specs(profile["stage_epochs"], profile)["stage3"]["early_stopping"],
            "cap_scope": "per_subject_per_split",
        }
        record["label_evidence"] = label_evidence
        record["source_code_binding"] = source_code_binding
    return _add_runtime_binding(record)


def _adaptation_record(spec: dict, batch: int) -> dict:
    strategies = []
    if spec["gradient_accumulation_steps"] > 1:
        strategies.append("gradient_accumulation")
    if spec["gradient_clip_norm"] is not None:
        strategies.append("post_accumulation_global_norm_clipping")
    return {
        "batch": batch,
        "nominal_batch": spec["nominal_batch"],
        "effective_batch": spec["effective_batch"],
        "gradient_accumulation_steps": spec["gradient_accumulation_steps"],
        "strategy": "+".join(strategies) if strategies else None,
        "gradient_clip_norm": spec["gradient_clip_norm"],
        "gradient_clip_application": spec["gradient_clip_application"],
        "stability_adaptation_id": spec["stage3_stability_adaptation_id"],
        "recorded": bool(strategies),
    }


def _stage_specs(epochs_override=None, profile=None) -> dict:
    batches = {
        "stage1": 128 if profile is None else profile["stage1_microbatch"],
        "stage2": 128 if profile is None else profile["stage2_microbatch"],
        "stage3": 1 if profile is None else profile["stage3_microbatch"],
    }
    return {
        stage: stage_spec(
            MODEL_PROTOCOL_ID,
            stage,
            microbatch=batches[stage],
            stage2_loss_adaptation=(profile["stage2_loss_adaptation"] if profile is not None and stage == "stage2" else None),
            weight_decay=0.0 if stage == "stage1" else None,
            stage3_gradient_clip_norm=1.0 if stage == "stage3" else None,
            stage3_stability_adaptation_id=(STAGE3_STABILITY_ADAPTATION_ID if stage == "stage3" else None),
            stage3_optimizer_adaptation_id=(profile.get("stage3_optimizer_adaptation_id") if profile is not None and stage == "stage3" else None),
            stage3_loss_adaptation_id=(profile.get("stage3_loss_adaptation_id") if profile is not None and stage == "stage3" else None),
            epochs_override=epochs_override,
            quality_class_weighting_id=(profile.get("class_weighting_id") if profile is not None and stage == "stage3" else None),
            quality_early_stopping_id=(profile.get("early_stopping_id") if profile is not None and stage == "stage3" else None),
            subject_normalization_id=(profile.get("subject_normalization_id") if profile is not None else None),
            train_augmentation_id=(profile.get("train_augmentation_id") if profile is not None else None),
        )
        for stage in STAGES
    }


def _fold_config(cache, plan, args, fold, run_id: str) -> dict:
    profile = _resource_profile(args)
    batches = {
        "stage1": profile["stage1_microbatch"],
        "stage2": profile["stage2_microbatch"],
        "stage3": profile["stage3_microbatch"],
    }
    specs = _stage_specs(profile["stage_epochs"], profile)
    adaptations = {stage: _adaptation_record(specs[stage], batches[stage]) for stage in STAGES}
    cache_path = str(Path(cache.manifest_path).resolve())
    source_path = str(Path(args.source_manifest).resolve())
    environment_path = str(Path(args.environment_manifest).resolve())
    phase2_path = str(cache.phase2_manifest_path)
    config = {
        "protocol_id": MODEL_PROTOCOL_ID,
        "evaluation_protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
        "source_manifest": source_path,
        "source_manifest_hash": sha256_file(source_path),
        "environment_manifest": environment_path,
        "environment_manifest_hash": sha256_file(environment_path),
        "data_manifest": phase2_path,
        "data_manifest_hash": cache.phase2_manifest_hash,
        "cache_manifest": cache_path,
        "cache_manifest_hash": sha256_file(cache_path),
        "cache_hash": cache.cache_hash,
        "phase2_manifest": phase2_path,
        "split_hashes": plan.membership_hashes,
        "split_epoch_counts": {name: len(getattr(plan, name)) for name in ("train", "validation", "test")},
        "cap_policy": QUALITY_CAP_POLICY if profile.get("class_balanced_sampling") else SAMPLED_CAP_POLICY,
        "subject_protocol_path": str(Path(args.protocol_output).resolve()),
        "subject_protocol_sha256": args.approved_protocol_sha256,
        "seed": args.selection_seed,
        "model_seed": args.model_seed,
        "mode": "pilot",
        "per_split_epoch_cap": args.cap,
        "stage": "all",
        "external_parent": None,
        "weight_decay": 0.0,
        "batches": batches,
        "stage2_loss_adaptation": profile["stage2_loss_adaptation"],
        "stage3_gradient_clip_norm": 1.0,
        "stage3_stability_adaptation_id": STAGE3_STABILITY_ADAPTATION_ID,
        "subject_normalization_id": profile.get("subject_normalization_id"),
        "protocol_assumptions": {
            "stage1_weight_decay": 0.0,
            "evaluation_protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
        },
        "adaptations": adaptations,
        "fold_index": fold.fold_index,
        "test_subject": fold.test_subject,
        "validation_subject": fold.validation_subject,
        "pilot_subjects": list(args.pilot_subjects),
        "run_id": run_id,
        "locked_python_executable": LOCKED_TF24_PYTHON,
        "tensorflow_version": getattr(args, "tensorflow_version", None),
        "compute_profile": {
            "stage1_microbatch": profile["stage1_microbatch"],
            "stage2_microbatch": profile["stage2_microbatch"],
            "stage3_microbatch": profile["stage3_microbatch"],
            "stage2_loss_adaptation": profile["stage2_loss_adaptation"],
            "subject_normalization_id": profile.get("subject_normalization_id"),
        },
        "execution_strategy": (
            "fresh_locked_tf24_process_per_stage_per_fold"
            if profile["fresh_process_per_stage"]
            else "fresh_locked_tf24_process_per_fold"
            if profile["fresh_process_per_fold"]
            else "single_locked_tf24_process"
        ),
    }
    receipt = getattr(args, "cache_validation_receipt", None)
    if receipt:
        config["cache_validation_receipt"] = str(Path(receipt).resolve())
        config["cache_validation_receipt_sha256"] = sha256_file(receipt)
    if profile["id"] is not None:
        config["resource_profile"] = profile["id"]
        config["stage_epochs"] = profile["stage_epochs"]
        config["resource_gate_thresholds"] = {
            "physical_memory_available_mb": profile["min_physical_memory_mb"],
            "commit_headroom_mb": profile["min_commit_headroom_mb"],
            # The verifier compares this exact contract to each stage's
            # pre-cache admission.  Do not substitute global defaults here:
            # a profile-specific floor is part of the run's immutable lineage.
            "c_free_gib": profile["min_c_free_gib"],
            "e_free_gib": profile["min_e_free_gib"],
            "gpu_compute_process_count": 0,
        }
        config["capacity_wait_seconds"] = profile["capacity_wait_seconds"]
        config["capacity_poll_seconds"] = profile["capacity_poll_seconds"]
        config["capacity_wait_strategy"] = "drain_after_previous_stage_exit" if profile["capacity_wait_seconds"] else "none"
    if profile.get("quality_track"):
        try:
            config["class_weighting"] = balanced_class_weights(
                plan.train, lambda member: cache.entry(member, "PAPER_STAGE3_V1").label
            )
        except ValueError as error:
            raise TrainingContractError(str(error)) from error
        config["quality_track"] = True
        config["early_stopping"] = _stage_specs(profile["stage_epochs"], profile)["stage3"]["early_stopping"]
        config["sampling_policy"] = QUALITY_CAP_POLICY
        label_receipt = Path(args.label_evidence_receipt).resolve(strict=True)
        config["label_evidence_receipt"] = str(label_receipt)
        config["label_evidence_receipt_sha256"] = sha256_file(label_receipt)
        reviewed_protocol = json.loads(Path(args.protocol_output).read_text(encoding="utf-8"))
        config["source_code_binding"] = reviewed_protocol["source_code_binding"]
        current_source_binding, execution_source_binding = _quality_source_bindings()
        if current_source_binding != config["source_code_binding"]:
            raise TrainingContractError("executing source digests differ from the reviewed protocol")
        config["execution_source_binding"] = execution_source_binding
        runtime_root = Path(args.runtime_root)
        config["resource_admission_paths"] = {
            stage: str((runtime_root / "resource-admission" / ("fold-%02d-%s.json" % (fold.fold_index + 1, stage))).resolve())
            for stage in STAGES
        }
        config["worker_attempt_marker_paths"] = {
            stage: str((runtime_root / "worker-attempts" / ("fold-%02d-%s.lock" % (fold.fold_index + 1, stage))).resolve())
            for stage in STAGES
        }
        config["worker_cleanup_paths"] = {
            stage: str((runtime_root / "worker-cleanup" / ("fold-%02d-%s.json" % (fold.fold_index + 1, stage))).resolve())
            for stage in STAGES
        }
    return config


def _verify_fold(directory: Path) -> dict:
    command = [LOCKED_TF24_PYTHON, "-m", "paper_faithful.training.verify_run", "--run-dir", str(directory)]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    try:
        result = json.loads(completed.stdout)
    except (TypeError, ValueError) as error:
        raise TrainingContractError("subject-generalization standalone verifier returned invalid JSON") from error
    if completed.returncode != 0 or result.get("status") != "verified":
        raise TrainingContractError("subject-generalization fold standalone verification failed")
    return result


def _verify_parent_runtime(runtime_root: Path, *, issue_terminal_validation: bool = False) -> dict:
    command = [
        LOCKED_TF24_PYTHON, "-m", "paper_faithful.training.verify_run",
        "--subject-runtime-root", str(runtime_root),
    ]
    if issue_terminal_validation:
        command.append("--issue-subject-terminal-validation")
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    try:
        result = json.loads(completed.stdout)
    except (TypeError, ValueError) as error:
        raise TrainingContractError("subject-generalization parent verifier returned invalid JSON") from error
    if completed.returncode != 0 or result.get("status") != "verified":
        raise TrainingContractError("subject-generalization parent runtime verification failed")
    return result


def _finalize_quality_parent_runtime(runtime_root: Path, lifecycle: Path, summary: dict) -> dict:
    """Publish the single terminal lifecycle event before fail-closed verification."""

    _atomic_json(runtime_root / "summary.json", summary)
    _append_event(lifecycle, {
        "event": "pilot_completed",
        "fold_count": len(summary["folds"]),
    })
    verification = _verify_parent_runtime(runtime_root, issue_terminal_validation=True)
    terminal_path = runtime_root / "terminal-validation.json"
    _publish_protocol(terminal_path, verification)
    _verify_parent_runtime(runtime_root)
    output = dict(summary)
    output["status"] = "terminal_validated"
    output["terminal_validation_path"] = str(terminal_path.resolve())
    output["terminal_validation_sha256"] = sha256_file(terminal_path)
    return output


def _run_fold(cache, args, fold, fold_index: int, bulk_root: Path) -> dict:
    plan = fold.plan
    profile = _resource_profile(args)
    run_id = safe_fold_id(args.run_prefix, fold_index, fold.test_subject)
    args.active_fold_directory = None
    directory, record = prepare_run(run_id, _fold_config(cache, plan, args, fold, run_id), bulk_root=bulk_root)
    args.active_fold_directory = str(directory)
    record = transition_run(
        directory,
        record,
        "running",
        stage_progress={"next_stage": "stage1", "last_epoch": 0, "checkpoint": None, "inflight": False},
    )
    parent = None
    for stage in STAGES:
        _probe_live_capacity(
            min_physical_memory_mb=profile["min_physical_memory_mb"],
            min_commit_headroom_mb=profile["min_commit_headroom_mb"],
            min_c_free_gib=profile["min_c_free_gib"],
            min_e_free_gib=profile["min_e_free_gib"],
            allow_offline_power=profile["allow_offline_power"],
        )
        record = transition_run(
            directory,
            record,
            "running",
            stage_progress={"next_stage": stage, "last_epoch": 0, "checkpoint": parent, "inflight": True},
        )
        stage_result = run_stage(
            cache,
            plan,
            MODEL_PROTOCOL_ID,
            stage,
            directory,
            parent=parent,
            weight_decay=0.0,
            microbatch={
                "stage1": profile["stage1_microbatch"],
                "stage2": profile["stage2_microbatch"],
                "stage3": profile["stage3_microbatch"],
            }[stage],
            stage2_loss_adaptation=(profile["stage2_loss_adaptation"] if stage == "stage2" else None),
            stage3_gradient_clip_norm=1.0 if stage == "stage3" else None,
            stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID if stage == "stage3" else None,
            stage3_optimizer_adaptation_id=(profile.get("stage3_optimizer_adaptation_id") if stage == "stage3" else None),
            stage3_loss_adaptation_id=(profile.get("stage3_loss_adaptation_id") if stage == "stage3" else None),
            epochs_override=profile["stage_epochs"],
            quality_class_weighting_id=(profile.get("class_weighting_id") if stage == "stage3" else None),
            quality_early_stopping_id=(profile.get("early_stopping_id") if stage == "stage3" else None),
        )
        artifacts = dict(record.get("stage_artifacts", {}))
        artifacts[stage] = {
            "checkpoint_path": stage_result["checkpoint_path"],
            "checkpoint_hash": stage_result["checkpoint_hash"],
            "parent_checkpoint_path": None if stage == "stage1" else parent["checkpoint_path"],
            "parent_checkpoint_hash": None if stage == "stage1" else parent["checkpoint_hash"],
            "route": stage_result["route"],
            "metrics_path": stage_result["metrics_path"],
            "metrics_file_sha256": sha256_file(stage_result["metrics_path"]),
            "metrics_artifact_sha256": stage_result["metrics"]["artifact_sha256"],
        }
        parent = _lineage_checkpoint(stage_result)
        next_stage = STAGES[STAGES.index(stage) + 1] if stage != "stage3" else None
        record = transition_run(
            directory,
            record,
            "running",
            checkpoint_hash=parent["checkpoint_hash"],
            checkpoint_path=parent["checkpoint_path"],
            stage_artifacts=artifacts,
            stage_progress={"next_stage": next_stage, "last_epoch": 0, "checkpoint": parent, "inflight": False},
        )
    record = transition_run(directory, record, "completed")
    verification = _verify_fold(directory)
    return {
        "fold_index": fold.fold_index,
        "run_id": run_id,
        "test_subject": fold.test_subject,
        "validation_subject": fold.validation_subject,
        "directory": str(directory),
        "execution_sha256": verification["verification"]["execution_sha256"],
        "status": "verified",
        "verifier_python": LOCKED_TF24_PYTHON,
    }


def _run_fresh_process_per_fold(args, planned, bulk_root: Path, runtime_root: Path,
                                resource_path: Path, profile: dict) -> int:
    """Run each reviewed fold in a new locked TF2.4 process.

    The parent deliberately does not import TensorFlow, load the cache, or
    create a model.  A worker owns one fold and exits after standalone
    verification, which is the only reliable way to return TensorFlow's
    allocator arenas to the host between folds.
    """
    _probe_live_capacity(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    lifecycle = _initialize_runtime(runtime_root, args.run_prefix, planned, resource_path)
    environment_keys = (
        "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION",
        "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT",
        "PAPER_FAITHFUL_SUBJECT_RUN_PREFIX",
    )
    previous_environment = {key: os.environ.get(key) for key in environment_keys}
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION"] = "1"
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT"] = str(runtime_root / "gpu-admission")
    os.environ["PAPER_FAITHFUL_SUBJECT_RUN_PREFIX"] = args.run_prefix
    results = []
    try:
        _append_event(lifecycle, {
            "event": "execution_started",
            "fold_count": len(planned["folds"]),
            "fit_started": False,
            "execution_strategy": "fresh_locked_tf24_process_per_fold",
        })
        for index, item in enumerate(planned["folds"]):
            _append_event(lifecycle, {
                "event": "fold_started",
                "fold_index": item["fold_index"],
                "test_subject": item["test_subject"],
                "validation_subject": item["validation_subject"],
                "execution_strategy": "fresh_locked_tf24_process_per_fold",
            })
            command = [
                LOCKED_TF24_PYTHON,
                "-m",
                "paper_faithful.training.subject_generalization_fold_worker",
                "--cache-manifest", str(args.cache_manifest),
                "--source-manifest", str(args.source_manifest),
                "--environment-manifest", str(args.environment_manifest),
                "--bulk-root", str(bulk_root),
                "--runtime-root", str(runtime_root),
                "--run-prefix", str(args.run_prefix),
                "--selection-seed", str(args.selection_seed),
                "--subject-count", str(args.subject_count),
                "--model-seed", str(args.model_seed),
                "--cap", str(args.cap),
                "--epochs", str(profile["stage_epochs"]),
                "--resource-profile", str(profile["id"]),
                "--protocol-output", str(args.protocol_output),
                "--resource-evidence", str(args.resource_evidence),
                "--approved-protocol-sha256", str(args.approved_protocol_sha256),
                "--cache-validation-receipt", str(args.cache_validation_receipt),
                "--label-evidence-receipt", str(getattr(args, "label_evidence_receipt", "")),
                "--fold-index", str(index),
            ]
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env=os.environ.copy(),
            )
            stdout_path = runtime_root / ("fold-%02d-worker.stdout.log" % (index + 1))
            stderr_path = runtime_root / ("fold-%02d-worker.stderr.log" % (index + 1))
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
            _append_event(lifecycle, {
                "event": "fold_worker_exited",
                "fold_index": item["fold_index"],
                "returncode": completed.returncode,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "stdout_sha256": sha256_file(stdout_path),
                "stderr_sha256": sha256_file(stderr_path),
            })
            parsed = None
            for line in reversed((completed.stdout or "").splitlines()):
                if line.strip():
                    try:
                        parsed = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    break
            if completed.returncode != 0 or not isinstance(parsed, dict) or parsed.get("status") != "verified":
                tail = (completed.stderr or completed.stdout or "").strip()[-2000:]
                raise TrainingContractError(
                    "fresh fold worker failed at fold %d: %s" % (index + 1, tail)
                )
            results.append(parsed)
            _append_event(lifecycle, {"event": "fold_completed", **parsed})
        _append_event(lifecycle, {"event": "pilot_completed", "fold_count": len(results)})
        summary = {
            "schema_version": 1,
            "status": "completed",
            "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
            "model_protocol_id": MODEL_PROTOCOL_ID,
            "run_prefix": args.run_prefix,
            "pilot_subjects": list(planned["pilot_subjects"]),
            "folds": results,
            "execution_strategy": "fresh_locked_tf24_process_per_fold",
            "resource_evidence_sha256": sha256_file(resource_path),
        }
        _atomic_json(runtime_root / "summary.json", summary)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema_version": 1,
            "status": "failed",
            "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
            "run_prefix": args.run_prefix,
            "completed_folds": results,
            "execution_strategy": "fresh_locked_tf24_process_per_fold",
            "failure": failure_record(error),
        }
        _atomic_json(runtime_root / "failure.json", failure)
        _append_event(lifecycle, {
            "event": "pilot_failed",
            "completed_folds": len(results),
            "failure": failure["failure"],
        })
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_fresh_process_per_stage(args, planned, bulk_root: Path, runtime_root: Path,
                                 resource_path: Path, profile: dict) -> int:
    """Run one fresh locked-TF2.4 process for each stage of each fold."""
    _probe_live_capacity(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    lifecycle = _initialize_runtime(runtime_root, args.run_prefix, planned, resource_path)
    environment_keys = (
        "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION",
        "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT",
        "PAPER_FAITHFUL_SUBJECT_RUN_PREFIX",
    )
    previous_environment = {key: os.environ.get(key) for key in environment_keys}
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION"] = "1"
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT"] = str(runtime_root / "gpu-admission")
    os.environ["PAPER_FAITHFUL_SUBJECT_RUN_PREFIX"] = args.run_prefix
    results = []
    try:
        _append_event(lifecycle, {
            "event": "execution_started",
            "fold_count": len(planned["folds"]),
            "fit_started": False,
            "execution_strategy": "fresh_locked_tf24_process_per_stage_per_fold",
        })
        for index, item in enumerate(planned["folds"]):
            _append_event(lifecycle, {
                "event": "fold_started",
                "fold_index": item["fold_index"],
                "test_subject": item["test_subject"],
                "validation_subject": item["validation_subject"],
                "execution_strategy": "fresh_locked_tf24_process_per_stage_per_fold",
            })
            final_result = None
            for stage in STAGES:
                _append_event(lifecycle, {"event": "stage_started", "fold_index": item["fold_index"], "stage": stage})
                command = [
                    LOCKED_TF24_PYTHON,
                    "-m",
                    "paper_faithful.training.subject_generalization_stage_worker",
                    "--cache-manifest", str(args.cache_manifest),
                    "--source-manifest", str(args.source_manifest),
                    "--environment-manifest", str(args.environment_manifest),
                    "--bulk-root", str(bulk_root),
                    "--runtime-root", str(runtime_root),
                    "--run-prefix", str(args.run_prefix),
                    "--selection-seed", str(args.selection_seed),
                    "--subject-count", str(args.subject_count),
                    "--model-seed", str(args.model_seed),
                    "--cap", str(args.cap),
                    "--epochs", str(profile["stage_epochs"]),
                    "--resource-profile", str(profile["id"]),
                    "--protocol-output", str(args.protocol_output),
                    "--resource-evidence", str(args.resource_evidence),
                    "--approved-protocol-sha256", str(args.approved_protocol_sha256),
                    "--cache-validation-receipt", str(args.cache_validation_receipt),
                    "--label-evidence-receipt", str(getattr(args, "label_evidence_receipt", "")),
                    "--fold-index", str(index),
                    "--stage", stage,
                ]
                completed = subprocess.run(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, check=False, env=os.environ.copy(),
                )
                stdout_path = runtime_root / ("fold-%02d-%s-worker.stdout.log" % (index + 1, stage))
                stderr_path = runtime_root / ("fold-%02d-%s-worker.stderr.log" % (index + 1, stage))
                stdout_path.write_text(completed.stdout or "", encoding="utf-8")
                stderr_path.write_text(completed.stderr or "", encoding="utf-8")
                _append_event(lifecycle, {
                    "event": "stage_worker_exited",
                    "fold_index": item["fold_index"],
                    "stage": stage,
                    "returncode": completed.returncode,
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "stdout_sha256": sha256_file(stdout_path),
                    "stderr_sha256": sha256_file(stderr_path),
                })
                parsed = None
                for line in reversed((completed.stdout or "").splitlines()):
                    if line.strip():
                        try:
                            parsed = json.loads(line)
                        except (TypeError, ValueError):
                            continue
                        break
                expected_status = "verified" if stage == "stage3" else "stage_completed"
                if completed.returncode != 0 or not isinstance(parsed, dict) or parsed.get("status") != expected_status:
                    tail = (completed.stderr or completed.stdout or "").strip()[-2000:]
                    raise TrainingContractError(
                        "fresh stage worker failed at fold %d %s: %s" % (index + 1, stage, tail)
                    )
                _append_event(lifecycle, {"event": "stage_completed", **parsed})
                if stage == "stage3":
                    final_result = parsed
            results.append(final_result)
            _append_event(lifecycle, {"event": "fold_completed", **final_result})
        summary = {
            "schema_version": 1,
            "status": "completed",
            "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
            "model_protocol_id": MODEL_PROTOCOL_ID,
            "run_prefix": args.run_prefix,
            "pilot_subjects": list(planned["pilot_subjects"]),
            "folds": results,
            "fold_count": len(results),
            "execution_strategy": "fresh_locked_tf24_process_per_stage_per_fold",
            "protocol_path": str(Path(args.protocol_output).resolve()),
            "protocol_sha256": args.approved_protocol_sha256,
            "source_code_binding": planned["source_code_binding"],
            "execution_source_binding": _quality_source_bindings()[1],
            "resource_evidence_path": str(resource_path.resolve()),
            "resource_evidence_sha256": sha256_file(resource_path),
        }
        output = _finalize_quality_parent_runtime(runtime_root, lifecycle, summary)
        print(json.dumps(output, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema_version": 1,
            "status": "failed",
            "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
            "run_prefix": args.run_prefix,
            "completed_folds": results,
            "execution_strategy": "fresh_locked_tf24_process_per_stage_per_fold",
            "failure": failure_record(error),
        }
        _atomic_json(runtime_root / "failure.json", failure)
        _append_event(lifecycle, {
            "event": "pilot_failed",
            "completed_folds": len(results),
            "failure": failure["failure"],
        })
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def build_plan(args) -> tuple[dict, tuple, object]:
    # Identical payload in plan-only and execution modes. Only training
    # performs the expensive tensor validation; never build six full cohorts.
    record = _build_light_plan(args)
    if args.plan_only:
        return record, tuple(), None
    if any(fold["train_epoch_count"] < 128 for fold in record["folds"]):
        raise TrainingContractError("subject-generalization training needs at least one effective batch of 128 epochs")
    _require_approved_protocol(args, record)
    records = _read_record_bindings_for_plan(args.cache_manifest)
    if not args.resource_evidence:
        raise TrainingContractError("fresh resource evidence is required immediately before cache loading")
    profile = _resource_profile(args)
    _load_resource_evidence(
        Path(args.resource_evidence),
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    receipt = getattr(args, "cache_validation_receipt", None)
    # Execution must use the same bounded pilot cohort that was committed by
    # _build_light_plan.  Expanding back to every subject in the cache here
    # defeats the resource-limited protocol and makes a compact receipt look
    # incomplete even though it exactly covers all reviewed fold members.
    subjects = (set(record["pilot_subjects"])
                if profile["id"] is not None
                else {subject for _, subject, _ in records})
    labels = None
    if profile.get("class_balanced_sampling"):
        try:
            labels, _ = load_verified_stage3_labels(
                args.cache_manifest, args.label_evidence_receipt, subjects
            )
        except (OSError, UnicodeError, ValueError) as error:
            raise TrainingContractError("quality label evidence failed: " + str(error)) from error
    fold_parts = []
    required_members = set()
    for item in record["folds"]:
        train_subjects = subjects - {item["test_subject"], item["validation_subject"]}
        parts = {
            name: _sample_members_for_profile(records, subset, args.cap, args.selection_seed, profile, labels)
            for name, subset in (
                ("train", train_subjects),
                ("validation", {item["validation_subject"]}),
                ("test", {item["test_subject"]}),
            )
        }
        required_members.update(member.key for values in parts.values() for member in values)
        fold_parts.append((item, train_subjects, parts))
    cache = load_canonical_cache(
        args.cache_manifest,
        validated_receipt=receipt if receipt and Path(receipt).is_file() else None,
        required_members=required_members if profile["compact_cache"] else None,
    )
    _require_approved_protocol(args, _build_light_plan(args))
    members = cache.members
    actual_keys = {item.key for item in members}
    if profile["compact_cache"]:
        if not required_members.issubset(actual_keys):
            raise TrainingContractError("compact cache membership is missing reviewed fold members")
    else:
        expected_hash, _, expected_count = _stream_membership_hash(records, subjects)
        actual_hash = hashlib.sha256(("\n".join(sorted(actual_keys)) + "\n").encode("utf-8")).hexdigest()
        if actual_hash != expected_hash or len(members) != expected_count:
            raise TrainingContractError("validated cache membership differs from reviewed declarations")
    args.pilot_subjects = tuple(record["pilot_subjects"])
    folds = []
    for item, train_subjects, parts in fold_parts:
        hashes = {name: hashlib.sha256(("\n".join(sorted(member.key for member in values)) + "\n").encode("utf-8")).hexdigest()
                  for name, values in parts.items()}
        if hashes != item["split_membership_hashes"]:
            raise TrainingContractError("execution sampling differs from reviewed fold")
        plan = SplitPlan(SUBJECT_GENERALIZATION_PROTOCOL_ID, args.selection_seed,
                         parts["train"], parts["validation"], parts["test"], hashes)
        validate_no_leakage(plan, require_subject_disjoint=True)
        folds.append(SubjectFold(item["fold_index"], item["test_subject"], item["validation_subject"],
                                 tuple(sorted(train_subjects)), plan))
    return record, tuple(folds), cache


def run(args) -> int:
    profile = _resource_profile(args)
    bulk_root = require_bulk_path(args.bulk_root)
    if args.plan_only:
        if hasattr(args, "cache_validation_receipt") and (
            not args.cache_validation_receipt or not Path(args.cache_validation_receipt).is_file()
        ):
            raise TrainingContractError("standalone full-cache validation receipt is required before planning")
        protocol_record_value, _, _ = build_plan(args)
        output = Path(args.protocol_output)
        _publish_protocol(output, protocol_record_value)
        print(json.dumps({"status": "planned", "protocol_path": str(output), "protocol_sha256": sha256_file(output), "pilot_subjects": protocol_record_value["pilot_subjects"]}, sort_keys=True))
        return 0
    if not args.resource_evidence:
        raise TrainingContractError("subject-generalization resource evidence path is required for training")
    if hasattr(args, "cache_validation_receipt") and (
        not args.cache_validation_receipt or not Path(args.cache_validation_receipt).is_file()
    ):
        raise TrainingContractError("standalone full-cache validation receipt is required before training")
    resource_path = Path(args.resource_evidence)
    resource = _load_resource_evidence(
        resource_path,
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    runtime_root = require_bulk_path(args.runtime_root)
    try:
        runtime_root.relative_to(bulk_root / "runtime")
    except ValueError as error:
        raise TrainingContractError("subject runtime must be inside the selected bulk-root/runtime") from error
    if runtime_root != bulk_root / "runtime" / args.run_prefix:
        raise TrainingContractError("subject runtime must equal bulk-root/runtime/run-prefix")
    if runtime_root.exists():
        raise TrainingContractError("subject-generalization runtime namespace already exists")
    planned = _build_light_plan(args)
    _require_approved_protocol(args, planned)
    for fold_id in planned["fold_ids"]:
        if run_directory(fold_id, bulk_root=bulk_root).exists():
            raise TrainingContractError("subject-generalization child namespace already exists")
    _probe_live_capacity(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    if profile["fresh_process_per_stage"]:
        return _run_fresh_process_per_stage(
            args=args,
            planned=planned,
            bulk_root=bulk_root,
            runtime_root=runtime_root,
            resource_path=resource_path,
            profile=profile,
        )
    if profile["fresh_process_per_fold"]:
        return _run_fresh_process_per_fold(
            args=args,
            planned=planned,
            bulk_root=bulk_root,
            runtime_root=runtime_root,
            resource_path=resource_path,
            profile=profile,
        )
    args.tensorflow_version = _require_locked_tf24_runtime()
    protocol_record_value, folds, cache = build_plan(args)
    _probe_live_capacity(
        min_physical_memory_mb=profile["min_physical_memory_mb"],
        min_commit_headroom_mb=profile["min_commit_headroom_mb"],
        min_c_free_gib=profile["min_c_free_gib"],
        min_e_free_gib=profile["min_e_free_gib"],
        allow_offline_power=profile["allow_offline_power"],
    )
    lifecycle = _initialize_runtime(runtime_root, args.run_prefix, protocol_record_value, resource_path)
    environment_keys = ("PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION", "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT", "PAPER_FAITHFUL_SUBJECT_RUN_PREFIX")
    previous_environment = {key: os.environ.get(key) for key in environment_keys}
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION"] = "1"
    os.environ["PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT"] = str(runtime_root / "gpu-admission")
    os.environ["PAPER_FAITHFUL_SUBJECT_RUN_PREFIX"] = args.run_prefix
    results = []
    try:
        _append_event(lifecycle, {"event": "execution_started", "fold_count": len(folds), "fit_started": False})
        for index, fold in enumerate(folds):
            _append_event(lifecycle, {"event": "fold_started", "fold_index": fold.fold_index, "test_subject": fold.test_subject, "validation_subject": fold.validation_subject})
            tf = None
            try:
                tf = seed_model(args.model_seed)
                result = _run_fold(cache=cache, args=args, fold=fold, fold_index=index, bulk_root=bulk_root)
            except Exception as error:
                directory = run_directory(safe_fold_id(args.run_prefix, index, fold.test_subject), bulk_root=bulk_root)
                execution_path = directory / "execution.json"
                if getattr(args, "active_fold_directory", None) == str(directory) and execution_path.is_file():
                    current = json.loads(execution_path.read_text(encoding="utf-8"))
                    # A completed training whose standalone verification fails
                    # remains completed-but-unverified; never rewrite success
                    # into accepted lineage or hide the parent failure.
                    if current.get("status") == "running":
                        transition_run(directory, current, "failed", failure=failure_record(error))
                raise
            finally:
                args.active_fold_directory = None
                if tf is not None:
                    cleanup_model_state(tf)
            results.append(result)
            _append_event(lifecycle, {"event": "fold_completed", **result})
        summary = {"schema_version": 1, "status": "completed", "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID, "model_protocol_id": MODEL_PROTOCOL_ID, "run_prefix": args.run_prefix, "pilot_subjects": list(protocol_record_value["pilot_subjects"]), "folds": results, "resource_evidence_sha256": sha256_file(resource_path)}
        _atomic_json(runtime_root / "summary.json", summary)
        _append_event(lifecycle, {"event": "pilot_completed", "fold_count": len(results)})
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as error:
        failure = {"schema_version": 1, "status": "failed", "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID, "run_prefix": args.run_prefix, "completed_folds": results, "failure": failure_record(error)}
        _atomic_json(runtime_root / "failure.json", failure)
        _append_event(lifecycle, {"event": "pilot_failed", "completed_folds": len(results), "failure": failure["failure"]})
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        if hasattr(cache, "close"):
            cache.close()
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-manifest", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--environment-manifest", required=True)
    parser.add_argument("--bulk-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--run-prefix", default=DEFAULT_RUN_PREFIX)
    parser.add_argument("--selection-seed", type=int, default=42)
    parser.add_argument("--subject-count", type=int, default=DEFAULT_PILOT_SUBJECT_COUNT)
    parser.add_argument("--model-seed", type=int, default=DEFAULT_MODEL_SEED)
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--resource-profile", choices=(
        RESOURCE_LIMITED_PROFILE_ID,
        RESOURCE_LIMITED_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID,
        RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_V2_PROFILE_ID,
        RESOURCE_LIMITED_GPU_PROBE_FIXED_PROFILE_ID,
        RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_FOLD_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID,
        RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID,
        QUALITY_BALANCED_CAP32_E6_BALANCED_CE_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID,
        QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID,
    ))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--protocol-output", required=True)
    parser.add_argument("--resource-evidence")
    parser.add_argument("--approved-protocol-sha256", help="SHA-256 of the reviewed --protocol-output file; required for training")
    parser.add_argument("--cache-validation-receipt", help="Receipt produced by the standalone full-cache validator")
    parser.add_argument("--label-evidence-receipt", help="Full prior-evidence receipt used to verify Stage-3 labels for quality sampling")
    parser.add_argument("--plan-only", action="store_true")
    return parser


if __name__ == "__main__":
    parsed = _parser().parse_args()
    try:
        raise SystemExit(run(parsed))
    except TrainingContractError as error:
        print(json.dumps({"status": "refused", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
