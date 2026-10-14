"""Fail-closed verification for persisted training executions."""
from __future__ import print_function

import argparse
from datetime import datetime, timedelta
import json
import os
import sys
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath

import numpy as np

from .metrics import LABELS
from .run_manifest import sha256_file
from .trainer import (
    SILHOUETTE_RESERVOIR_CAP,
    SILHOUETTE_RESERVOIR_SEED,
    STAGES,
    TrainingContractError,
    _hash,
    _latest,
    _validate_progress_lineage,
    _validate_stage_artifacts,
)


def _provenance_path(value):
    """Resolve one immutable provenance path without relaxing path trust."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise TrainingContractError("provenance path must be a non-empty string")
    if value.startswith(("\\\\", "//")):
        raise TrainingContractError("UNC/device provenance paths are forbidden")
    windows_path = PureWindowsPath(value)
    if windows_path.drive:
        if not windows_path.is_absolute():
            raise TrainingContractError("drive-relative provenance paths are forbidden")
        if ".." in windows_path.parts:
            raise TrainingContractError("provenance path traversal is forbidden")
        if os.name != "nt":
            if windows_path.drive.upper() != "E:":
                raise TrainingContractError("unsupported Windows provenance drive")
            candidate = Path("/mnt/e").joinpath(*windows_path.parts[1:])
            try:
                root = Path("/mnt/e").resolve(strict=True)
                resolved = candidate.resolve(strict=True)
            except OSError as error:
                raise TrainingContractError("provenance file is missing") from error
            try:
                resolved.relative_to(root)
            except ValueError as error:
                raise TrainingContractError(
                    "translated provenance path escaped /mnt/e"
                ) from error
            return resolved
        try:
            return Path(value).resolve(strict=True)
        except OSError as error:
            raise TrainingContractError("provenance file is missing") from error
    if os.name == "nt":
        if not windows_path.is_absolute():
            raise TrainingContractError("provenance path must be absolute")
    elif "\\" in value or not PurePosixPath(value).is_absolute():
        raise TrainingContractError("provenance path must be an absolute host path")
    if ".." in Path(value).parts:
        raise TrainingContractError("provenance path traversal is forbidden")
    try:
        return Path(value).resolve(strict=True)
    except OSError as error:
        raise TrainingContractError("provenance file is missing") from error


def _is_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _verify_quality_source_bindings(source_binding, execution_binding):
    """Match stable reviewed identities to the immutable files run in practice."""

    if not isinstance(source_binding, dict) or not source_binding:
        raise TrainingContractError("quality source-code binding maps are invalid")
    legacy = all(
        isinstance(item, dict) and set(item) == {"path", "sha256"}
        for item in source_binding.values()
    )
    if legacy:
        if execution_binding is not None:
            raise TrainingContractError("legacy source binding cannot have execution binding")
        for name, item in source_binding.items():
            if (
                not isinstance(name, str)
                or not name
                or not _is_sha256(item.get("sha256"))
                or sha256_file(_provenance_path(item.get("path"))) != item["sha256"]
            ):
                raise TrainingContractError("legacy source-code binding failed")
        return "legacy"
    if not isinstance(execution_binding, dict) or set(execution_binding) != set(source_binding):
        raise TrainingContractError("quality source-code binding maps are invalid")
    for name, reviewed in source_binding.items():
        executed = execution_binding.get(name)
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(reviewed, dict)
            or set(reviewed) != {"logical_path", "sha256"}
            or not isinstance(executed, dict)
            or set(executed) != {"path", "sha256"}
            or not _is_sha256(reviewed.get("sha256"))
            or executed.get("sha256") != reviewed.get("sha256")
        ):
            raise TrainingContractError("quality source-code binding schema failed")
        logical_value = reviewed.get("logical_path")
        if not isinstance(logical_value, str) or "\\" in logical_value:
            raise TrainingContractError("quality logical source path is invalid")
        logical = PurePosixPath(logical_value)
        if (
            logical.is_absolute()
            or ".." in logical.parts
            or len(logical.parts) < 3
            or logical.parts[:2] != ("paper_faithful", "training")
            or logical.suffix != ".py"
        ):
            raise TrainingContractError("quality logical source path is invalid")
        actual = _provenance_path(executed.get("path"))
        if (
            tuple(actual.parts[-len(logical.parts):]) != logical.parts
            or sha256_file(actual) != reviewed["sha256"]
        ):
            raise TrainingContractError("quality execution source binding failed")
    return "logical"


def _verify_subject_protocol(config):
    """Independently reconstruct the reviewed, compact subject split plan."""
    from .subject_generalization_runner import _build_light_plan
    from .subject_generalization import canonical_json
    try:
        path = _provenance_path(config["subject_protocol_path"])
        if sha256_file(path) != config["subject_protocol_sha256"]:
            raise ValueError("protocol digest mismatch")
        raw = path.read_bytes()
        protocol = json.loads(raw.decode("utf-8"))
        args = argparse.Namespace(cache_manifest=config["cache_manifest"], source_manifest=config["source_manifest"],
                                  environment_manifest=config["environment_manifest"], run_prefix=protocol["run_prefix"],
                                  selection_seed=config["seed"], model_seed=config["model_seed"],
                                  subject_count=len(protocol["pilot_subjects"]), cap=config["per_split_epoch_cap"],
                                  resource_profile=protocol.get("resource_profile"), epochs=protocol.get("stage_epochs"),
                                  cache_validation_receipt=config.get("cache_validation_receipt"),
                                  label_evidence_receipt=config.get("label_evidence_receipt"))
        if raw != canonical_json(_build_light_plan(args)).encode("utf-8"):
            raise ValueError("protocol is not reproducible from the bound manifests")
        index = config["fold_index"]
        if type(index) is not int or not 0 <= index < len(protocol["folds"]):
            raise ValueError("invalid fold index")
        fold = protocol["folds"][index]
        if (fold["run_id"] != config["run_id"] or fold["test_subject"] != config["test_subject"]
                or fold["validation_subject"] != config["validation_subject"]
                or fold["split_membership_hashes"] != config["split_hashes"]
                or config["cap_policy"] != protocol["cap_policy"]
                or config["pilot_subjects"] != protocol["pilot_subjects"]
                or config["split_epoch_counts"] != {name: fold[name + "_epoch_count"] for name in ("train", "validation", "test")}
                or config.get("resource_profile") != protocol.get("resource_profile")
                or config.get("stage_epochs") != protocol.get("stage_epochs")):
            raise ValueError("executed fold differs from protocol")
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        raise TrainingContractError("subject-generalization reviewed protocol verification failed: " + str(error)) from error


def _metric_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and np.isfinite(value)
    )


def _quality_utc_timestamp(value, label):
    if not isinstance(value, str) or not value:
        raise TrainingContractError(label + " timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise TrainingContractError(label + " timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise TrainingContractError(label + " timestamp must be UTC")
    return parsed


def _verify_quality_runtime_evidence(config, record):
    """Bind exact pre-cache admission and post-close evidence into execution.json."""

    binding = config.get("source_code_binding")
    execution_binding = config.get("execution_source_binding")
    _verify_quality_source_bindings(binding, execution_binding)
    admission_paths = config.get("resource_admission_paths")
    attempt_paths = config.get("worker_attempt_marker_paths")
    cleanup_paths = config.get("worker_cleanup_paths")
    evidence = record.get("quality_runtime_evidence")
    thresholds_expected = config.get("resource_gate_thresholds")
    mappings = (admission_paths, attempt_paths, cleanup_paths, evidence)
    if any(not isinstance(item, dict) or set(item) != set(STAGES) for item in mappings):
        raise TrainingContractError("quality runtime-evidence maps are invalid")
    if not isinstance(thresholds_expected, dict) or set(thresholds_expected) != {
        "physical_memory_available_mb", "commit_headroom_mb", "c_free_gib",
        "e_free_gib", "gpu_compute_process_count",
    }:
        raise TrainingContractError("quality resource thresholds are invalid")
    verified = {}
    admission_keys = {
        "schema_version", "artifact_type", "status", "observed_at_utc",
        "run_prefix", "fold_index", "stage", "checks", "thresholds",
        "protocol_path", "protocol_sha256", "attempt_marker_path",
        "attempt_marker_sha256", "source_code_binding", "timing",
    }
    if execution_binding is not None:
        admission_keys.add("execution_source_binding")
    cleanup_keys = {
        "schema_version", "artifact_type", "status", "observed_at_utc",
        "run_prefix", "fold_index", "stage", "attempt_marker_path",
        "attempt_marker_sha256", "resource_admission_path",
        "resource_admission_sha256", "cleanup",
    }
    evidence_keys = {
        "resource_admission_path", "resource_admission_sha256",
        "attempt_marker_path", "attempt_marker_sha256",
        "cleanup_path", "cleanup_sha256",
    }
    run_prefix = config.get("run_id", "").rsplit("-fold", 1)[0]
    for stage in STAGES:
        admission_path = _provenance_path(admission_paths[stage])
        marker_path = _provenance_path(attempt_paths[stage])
        cleanup_path = _provenance_path(cleanup_paths[stage])
        if marker_path.stat().st_size != 0:
            raise TrainingContractError("quality worker attempt marker is invalid")
        try:
            admission = json.loads(admission_path.read_text(encoding="utf-8"))
            cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise TrainingContractError("quality runtime evidence is unreadable") from error
        if not isinstance(admission, dict) or set(admission) != admission_keys:
            raise TrainingContractError("quality resource admission schema failed")
        if not isinstance(cleanup, dict) or set(cleanup) != cleanup_keys:
            raise TrainingContractError("quality cleanup schema failed")
        item = evidence[stage]
        if not isinstance(item, dict) or set(item) != evidence_keys:
            raise TrainingContractError("quality execution evidence schema failed")
        admission_hash = sha256_file(admission_path)
        marker_hash = sha256_file(marker_path)
        cleanup_hash = sha256_file(cleanup_path)
        admission_time = _quality_utc_timestamp(admission["observed_at_utc"], "quality admission")
        cleanup_time = _quality_utc_timestamp(cleanup["observed_at_utc"], "quality cleanup")
        if cleanup_time < admission_time:
            raise TrainingContractError("quality cleanup predates resource admission")
        checks = admission["checks"]
        thresholds = admission["thresholds"]
        if (
            admission["schema_version"] != 1
            or admission["artifact_type"] != "PLAN16_PRE_CACHE_RESOURCE_ADMISSION_V1"
            or admission["status"] != "pass"
            or admission["run_prefix"] != run_prefix
            or admission["fold_index"] != config.get("fold_index")
            or admission["stage"] != stage
            or admission["protocol_path"] != config.get("subject_protocol_path")
            or admission["protocol_sha256"] != config.get("subject_protocol_sha256")
            or _provenance_path(admission["attempt_marker_path"]) != marker_path
            or admission["attempt_marker_sha256"] != marker_hash
            or admission["source_code_binding"] != binding
            or admission.get("execution_source_binding") != execution_binding
            or admission["timing"] != "persisted_before_cache_load"
            or thresholds != thresholds_expected
            or not isinstance(checks, dict)
            or not _metric_number(checks.get("physical_memory_available_mb"))
            or not _metric_number(checks.get("commit_headroom_mb"))
            or not _metric_number(checks.get("c_free_gib"))
            or not _metric_number(checks.get("e_free_gib"))
            or checks["physical_memory_available_mb"] < thresholds["physical_memory_available_mb"]
            or checks["commit_headroom_mb"] < thresholds["commit_headroom_mb"]
            or checks["c_free_gib"] < thresholds["c_free_gib"]
            or checks["e_free_gib"] < thresholds["e_free_gib"]
            or checks.get("power_online") is not True
            or checks.get("critical") is not False
            or checks.get("gpu_compute_process_pids") != []
            or checks.get("gpu_probe_exit_code") != 0
            or cleanup["schema_version"] != 1
            or cleanup["artifact_type"] != "PLAN16_STAGE_CLEANUP_V1"
            or cleanup["status"] != "pass"
            or cleanup["run_prefix"] != run_prefix
            or cleanup["fold_index"] != config.get("fold_index")
            or cleanup["stage"] != stage
            or _provenance_path(cleanup["attempt_marker_path"]) != marker_path
            or cleanup["attempt_marker_sha256"] != marker_hash
            or _provenance_path(cleanup["resource_admission_path"]) != admission_path
            or cleanup["resource_admission_sha256"] != admission_hash
            or cleanup["cleanup"] != "tensorflow_state_released_and_cache_closed_before_worker_exit"
            or _provenance_path(item["resource_admission_path"]) != admission_path
            or item["resource_admission_sha256"] != admission_hash
            or _provenance_path(item["attempt_marker_path"]) != marker_path
            or item["attempt_marker_sha256"] != marker_hash
            or _provenance_path(item["cleanup_path"]) != cleanup_path
            or item["cleanup_sha256"] != cleanup_hash
        ):
            raise TrainingContractError("quality runtime evidence content failed")
        verified["resource_admission_" + stage] = {"path": str(admission_path), "sha256": admission_hash}
        verified["worker_attempt_" + stage] = {"path": str(marker_path), "sha256": marker_hash}
        verified["worker_cleanup_" + stage] = {"path": str(cleanup_path), "sha256": cleanup_hash}
    return verified


def _validate_classification_result(result, sample_count):
    required = {
        "accuracy",
        "macro",
        "weighted",
        "per_class",
        "confusion_matrix",
        "n1_rem",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise TrainingContractError("classification metric schema is invalid")
    matrix = np.asarray(result["confusion_matrix"])
    if (
        matrix.shape != (5, 5)
        or not np.issubdtype(matrix.dtype, np.integer)
        or np.any(matrix < 0)
        or int(matrix.sum()) != sample_count
    ):
        raise TrainingContractError("classification confusion matrix is invalid")
    support = matrix.sum(1)
    predicted = matrix.sum(0)
    true_positive = np.diag(matrix)
    precision = np.divide(
        true_positive,
        predicted,
        out=np.zeros(5, dtype=float),
        where=predicted != 0,
    )
    recall = np.divide(
        true_positive,
        support,
        out=np.zeros(5, dtype=float),
        where=support != 0,
    )
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(5, dtype=float),
        where=(precision + recall) != 0,
    )
    expected_accuracy = float(true_positive.sum() / sample_count)
    if not _metric_number(result["accuracy"]) or not np.isclose(
        result["accuracy"], expected_accuracy
    ):
        raise TrainingContractError("classification accuracy is inconsistent")
    aggregates = (
        ("macro", (precision.mean(), recall.mean(), f1.mean())),
        (
            "weighted",
            (
                np.average(precision, weights=support),
                np.average(recall, weights=support),
                np.average(f1, weights=support),
            ),
        ),
    )
    for aggregate, expected in aggregates:
        value = result.get(aggregate)
        names = ("precision", "recall", "f1")
        if (
            not isinstance(value, dict)
            or set(value) != set(names)
            or any(
                not _metric_number(value[name])
                or not np.isclose(value[name], expected[index])
                for index, name in enumerate(names)
            )
        ):
            raise TrainingContractError(
                "classification aggregate metrics are inconsistent"
            )
    per_class = result.get("per_class")
    if not isinstance(per_class, dict) or set(per_class) != set(LABELS):
        raise TrainingContractError("classification per-class schema is invalid")
    for index, label in enumerate(LABELS):
        value = per_class[label]
        expected_values = (
            ("precision", precision[index]),
            ("recall", recall[index]),
            ("f1", f1[index]),
        )
        if (
            not isinstance(value, dict)
            or set(value) != {"precision", "recall", "f1", "support"}
            or not isinstance(value["support"], int)
            or isinstance(value["support"], bool)
            or value["support"] != int(support[index])
            or any(
                not _metric_number(value[name])
                or not np.isclose(value[name], expected)
                for name, expected in expected_values
            )
        ):
            raise TrainingContractError(
                "classification per-class metrics are inconsistent"
            )
    n1_rem = result.get("n1_rem")
    if (
        not isinstance(n1_rem, dict)
        or set(n1_rem) != {"N1", "REM"}
        or any(n1_rem[label] != per_class[label] for label in ("N1", "REM"))
    ):
        raise TrainingContractError("N1/REM metric projection is inconsistent")


def _validate_metric_result(stage, split, result, membership_hash):
    if not isinstance(result, dict) or "scope" not in result:
        raise TrainingContractError("stage metric result is missing")
    scope = result["scope"]
    if (
        not isinstance(scope, dict)
        or scope.get("split") != split
        or scope.get("base_epoch_membership_hash") != membership_hash
    ):
        raise TrainingContractError("metric scope does not bind its split")
    counts = scope.get("split_sample_count"), scope.get("evaluated_sample_count")
    if (
        any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for value in counts
        )
        or counts[1] > counts[0]
    ):
        raise TrainingContractError("metric scope sample counts are invalid")
    if stage == "stage2":
        required_scope = {
            "split",
            "base_epoch_membership_hash",
            "split_sample_count",
            "evaluated_sample_count",
            "evaluation_mode",
            "reservoir_seed",
            "reservoir_cap",
        }
        if (
            set(result) != {"silhouette", "scope"}
            or set(scope) != required_scope
            or scope["evaluation_mode"] != "deterministic_uniform_reservoir"
            or scope["reservoir_seed"] != SILHOUETTE_RESERVOIR_SEED
            or scope["reservoir_cap"] != SILHOUETTE_RESERVOIR_CAP
            or counts[1] != min(counts[0], SILHOUETTE_RESERVOIR_CAP)
        ):
            raise TrainingContractError("Stage2 metric scope is invalid")
        value = result["silhouette"]
        if (
            not isinstance(value, dict)
            or set(value) != {"sample_count", "silhouette", "undefined_reason"}
            or value["sample_count"] != counts[1]
        ):
            raise TrainingContractError("Stage2 silhouette schema is invalid")
        score = value["silhouette"]
        reason = value["undefined_reason"]
        if score is None:
            allowed = {
                "requires_at_least_two_classes",
                "samples_must_exceed_classes",
                "singleton_class",
            }
            if reason not in allowed:
                raise TrainingContractError(
                    "Stage2 undefined silhouette reason is invalid"
                )
        elif (
            not _metric_number(score)
            or not -1 <= score <= 1
            or reason is not None
        ):
            raise TrainingContractError("Stage2 silhouette value is invalid")
        return
    required_scope = {
        "split",
        "base_epoch_membership_hash",
        "split_sample_count",
        "evaluated_sample_count",
        "evaluation_mode",
    }
    if (
        set(result) != {"classification", "scope"}
        or set(scope) != required_scope
        or scope["evaluation_mode"] != "complete_split"
        or counts[0] != counts[1]
    ):
        raise TrainingContractError("classification metric scope is invalid")
    _validate_classification_result(result["classification"], counts[0])


def _validate_persisted_metrics(stage, artifact, config):
    try:
        metric = json.loads(Path(artifact["metrics_path"]).read_text())
    except (OSError, ValueError) as error:
        raise TrainingContractError("stage metric artifact is unreadable") from error
    provenance = metric.get("provenance")
    required_provenance = {
        "schema_version",
        "protocol_id",
        "stage",
        "route",
        "cache_hash",
        "checkpoint_path",
        "checkpoint_sha256",
        "split_membership_hashes",
        "initial_epoch",
        "stage_spec",
    }
    allowed_provenance = (required_provenance, required_provenance | {"training_outcome"})
    if (
        not isinstance(provenance, dict)
        or set(provenance) not in allowed_provenance
        or provenance.get("schema_version") != 1
        or provenance.get("checkpoint_path") != artifact["checkpoint_path"]
        or not isinstance(provenance.get("initial_epoch"), int)
        or isinstance(provenance.get("initial_epoch"), bool)
        or provenance["initial_epoch"] < 0
        or not isinstance(provenance.get("stage_spec"), dict)
    ):
        raise TrainingContractError("metric provenance schema is invalid")
    outcome = provenance.get("training_outcome")
    if outcome is not None:
        spec = provenance["stage_spec"]
        if (
            not isinstance(outcome, dict)
            or set(outcome) != {"epochs_completed", "max_epochs", "early_stopped", "best_checkpoint_restored"}
            or type(outcome.get("epochs_completed")) is not int
            or type(outcome.get("max_epochs")) is not int
            or type(outcome.get("early_stopped")) is not bool
            or type(outcome.get("best_checkpoint_restored")) is not bool
            or not 1 <= outcome["epochs_completed"] <= outcome["max_epochs"]
            or outcome["max_epochs"] != spec.get("epochs")
            or outcome["early_stopped"] != (outcome["epochs_completed"] < outcome["max_epochs"])
        ):
            raise TrainingContractError("training outcome provenance is invalid")
    if config.get("quality_track") is True and stage == "stage3":
        if (
            outcome is None
            or provenance["stage_spec"].get("class_weighting") != config.get("class_weighting")
            or provenance["stage_spec"].get("early_stopping") != config.get("early_stopping")
        ):
            raise TrainingContractError("quality Stage3 provenance does not bind weighting and stopping")
    if config.get("stage_epochs") is not None and provenance["stage_spec"].get("epochs") != config["stage_epochs"]:
        raise TrainingContractError("stage metric epochs do not bind the execution contract")
    metrics = metric.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != {"validation", "test"}:
        raise TrainingContractError(
            "stage metrics must contain validation and test results"
        )
    for split in ("validation", "test"):
        _validate_metric_result(
            stage,
            split,
            metrics[split],
            config["split_hashes"][split],
        )


def verify_run_directory(directory, require_completed=True):
    directory = Path(directory)
    if not directory.is_dir():
        raise TrainingContractError("run directory is missing")
    record = _latest(directory)
    status = record.get("status")
    if status not in ("planned", "running", "completed", "failed"):
        raise TrainingContractError("execution status is invalid")
    if require_completed and status != "completed":
        raise TrainingContractError("run is not completed")
    if status == "completed" and (directory / "execution.json.lock").exists():
        raise TrainingContractError("completed run retains an execution lock")
    config = record.get("config")
    if (
        not isinstance(config, dict)
        or _hash(config) != record.get("immutable_config_hash")
    ):
        raise TrainingContractError("immutable execution config hash failed")
    required = {
        "protocol_id",
        "source_manifest",
        "source_manifest_hash",
        "environment_manifest",
        "environment_manifest_hash",
        "data_manifest",
        "data_manifest_hash",
        "cache_manifest",
        "cache_manifest_hash",
        "cache_hash",
        "phase2_manifest",
        "split_hashes",
        "seed",
        "mode",
        "stage",
    }
    if not required.issubset(config):
        raise TrainingContractError("execution config is missing provenance fields")
    if (
        config.get("mode") not in ("pilot", "full")
        or config.get("stage") not in STAGES + ("all",)
        or not isinstance(config.get("seed"), int)
    ):
        raise TrainingContractError("execution mode, stage, or seed is invalid")
    quality_verified_files = {}
    if config.get("evaluation_protocol_id") == "SUBJECT_GENERALIZATION_V1":
        expected_python = "/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python"
        if config.get("locked_python_executable") != expected_python:
            raise TrainingContractError("subject-generalization verifier Python binding failed")
        if config.get("tensorflow_version") != "2.4.0":
            raise TrainingContractError("subject-generalization TensorFlow version binding failed")
        if str(Path(sys.executable).resolve()) != str(Path(expected_python).resolve()):
            raise TrainingContractError("subject-generalization verifier must run with locked TF2.4 Python")
        _verify_subject_protocol(config)
        if config.get("quality_track") is True:
            _verify_quality_source_bindings(
                config.get("source_code_binding"),
                config.get("execution_source_binding"),
            )
            label_receipt = _provenance_path(config.get("label_evidence_receipt"))
            if sha256_file(label_receipt) != config.get("label_evidence_receipt_sha256"):
                raise TrainingContractError("quality label-evidence receipt binding failed")
            quality_verified_files.update(_verify_quality_runtime_evidence(config, record))
    split_hashes = config.get("split_hashes")
    if (
        not isinstance(split_hashes, dict)
        or set(split_hashes) != {"train", "validation", "test"}
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in split_hashes.values()
        )
    ):
        raise TrainingContractError("split membership hashes are invalid")
    bindings = (
        ("source_manifest", "source_manifest_hash"),
        ("environment_manifest", "environment_manifest_hash"),
        ("data_manifest", "data_manifest_hash"),
        ("cache_manifest", "cache_manifest_hash"),
        ("phase2_manifest", "data_manifest_hash"),
    )
    verified_files = {}
    verified_files.update(quality_verified_files)
    for path_key, hash_key in bindings:
        try:
            path = _provenance_path(config[path_key])
        except (OSError, ValueError, TrainingContractError) as error:
            raise TrainingContractError(path_key + " provenance path failed") from error
        expected = config[hash_key]
        if (
            not path.is_file()
            or not isinstance(expected, str)
            or len(expected) != 64
            or sha256_file(path) != expected
        ):
            raise TrainingContractError(path_key + " provenance hash failed")
        verified_files[path_key] = {
            "path": str(path.resolve()),
            "sha256": expected,
        }
    if config.get("cache_hash") != config.get("cache_manifest_hash"):
        raise TrainingContractError(
            "canonical cache hash does not bind the cache manifest"
        )
    if verified_files["phase2_manifest"]["path"] != verified_files["data_manifest"]["path"]:
        raise TrainingContractError("Phase-2 and data manifest paths differ")
    external = config.get("external_parent")
    if config["stage"] in ("stage2", "stage3"):
        required_parent = {
            "checkpoint_path",
            "checkpoint_hash",
            "cache_hash",
            "protocol_id",
            "stage",
            "route",
            "metadata_path",
            "metadata_hash",
        }
        if not isinstance(external, dict) or not required_parent.issubset(external):
            raise TrainingContractError(
                "standalone run is missing external-parent metadata"
            )
        metadata_path = Path(external["metadata_path"])
        if (
            not metadata_path.is_absolute()
            or not metadata_path.is_file()
            or sha256_file(metadata_path) != external["metadata_hash"]
        ):
            raise TrainingContractError("external-parent metadata hash failed")
        try:
            metadata = json.loads(metadata_path.read_text())
        except (OSError, ValueError) as error:
            raise TrainingContractError(
                "external-parent metadata is unreadable"
            ) from error
        persisted = dict(external)
        persisted.pop("metadata_path", None)
        persisted.pop("metadata_hash", None)
        if metadata != persisted:
            raise TrainingContractError(
                "external-parent metadata content differs from the persisted parent"
            )
        verified_files["external_parent_metadata"] = {
            "path": str(metadata_path.resolve()),
            "sha256": external["metadata_hash"],
        }
    elif external is not None:
        raise TrainingContractError("Stage1/all run cannot declare an external parent")
    artifacts = record.get("stage_artifacts")
    progress = record.get("stage_progress")
    _validate_stage_artifacts(artifacts, config)
    _validate_progress_lineage(progress, artifacts, config)
    for stage, artifact in artifacts.items():
        _validate_persisted_metrics(stage, artifact, config)
    if (
        not isinstance(progress.get("last_epoch"), int)
        or progress["last_epoch"] < 0
        or not isinstance(progress.get("inflight"), bool)
    ):
        raise TrainingContractError("stage progress counters are invalid")
    if status == "completed":
        if (
            progress.get("next_stage") is not None
            or progress.get("inflight") is not False
        ):
            raise TrainingContractError("completed run has non-terminal progress")
        terminal = "stage3" if config["stage"] == "all" else config["stage"]
        artifact = artifacts[terminal]
        if (
            record.get("checkpoint_path") != artifact["checkpoint_path"]
            or record.get("checkpoint_hash") != artifact["checkpoint_hash"]
        ):
            raise TrainingContractError(
                "terminal checkpoint does not bind the completed execution"
            )
    return {
        "status": status,
        "execution_path": str((directory / "execution.json").resolve()),
        "execution_sha256": sha256_file(directory / "execution.json"),
        "immutable_config_hash": record["immutable_config_hash"],
        "protocol_id": config["protocol_id"],
        "mode": config["mode"],
        "stage_scope": config["stage"],
        "seed": config["seed"],
        "split_hashes": split_hashes,
        "verified_files": verified_files,
        "verified_stages": sorted(artifacts, key=STAGES.index),
        "terminal_checkpoint_sha256": record.get("checkpoint_hash"),
    }


def verify_subject_generalization_runtime(runtime_root, require_terminal_artifact=True):
    """Verify the six-fold parent lifecycle after every worker has exited."""

    root = Path(runtime_root).resolve(strict=True)
    if not root.is_dir():
        raise TrainingContractError("subject runtime root is missing")
    protocol_path = root / "protocol.json"
    summary_path = root / "summary.json"
    lifecycle_path = root / "lifecycle.jsonl"
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        events = [json.loads(line) for line in lifecycle_path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeError, ValueError) as error:
        raise TrainingContractError("subject parent runtime evidence is unreadable") from error
    summary_keys = {
        "schema_version", "status", "protocol_id", "model_protocol_id",
        "run_prefix", "pilot_subjects", "folds", "fold_count",
        "execution_strategy", "protocol_path", "protocol_sha256",
        "source_code_binding", "resource_evidence_path",
        "resource_evidence_sha256",
    }
    protocol_binding = protocol.get("source_code_binding")
    logical_binding = (
        isinstance(protocol_binding, dict)
        and bool(protocol_binding)
        and all(
            isinstance(item, dict) and set(item) == {"logical_path", "sha256"}
            for item in protocol_binding.values()
        )
    )
    if logical_binding:
        summary_keys.add("execution_source_binding")
    if not isinstance(summary, dict) or set(summary) != summary_keys:
        raise TrainingContractError("subject parent summary schema failed")
    folds = protocol.get("folds")
    summary_folds = summary.get("folds")
    if (
        summary["schema_version"] != 1
        or summary["status"] != "completed"
        or summary["protocol_id"] != "SUBJECT_GENERALIZATION_V1"
        or summary["model_protocol_id"] != "PAPER_TEXT_V1"
        or summary["run_prefix"] != protocol.get("run_prefix")
        or summary["pilot_subjects"] != protocol.get("pilot_subjects")
        or summary["execution_strategy"] != "fresh_locked_tf24_process_per_stage_per_fold"
        or not isinstance(folds, list)
        or not isinstance(summary_folds, list)
        or summary["fold_count"] != len(folds)
        or len(summary_folds) != len(folds)
        or summary["source_code_binding"] != protocol.get("source_code_binding")
        or sha256_file(_provenance_path(summary["protocol_path"])) != summary["protocol_sha256"]
        or protocol_path.read_bytes() != _provenance_path(summary["protocol_path"]).read_bytes()
        or sha256_file(_provenance_path(summary["resource_evidence_path"])) != summary["resource_evidence_sha256"]
    ):
        raise TrainingContractError("subject parent summary content failed")
    _verify_quality_source_bindings(
        protocol_binding,
        summary.get("execution_source_binding") if logical_binding else None,
    )
    dispatch = root / (protocol["run_prefix"] + ".dispatch.lock")
    attempt = root / (protocol["run_prefix"] + ".attempt.lock")
    if not dispatch.is_file() or dispatch.stat().st_size != 0 or not attempt.is_file() or attempt.stat().st_size != 0:
        raise TrainingContractError("subject parent exactly-once markers failed")
    expected = ["dispatch_created", "execution_started"]
    for _ in folds:
        expected.append("fold_started")
        for _stage in STAGES:
            expected.extend(("stage_started", "stage_worker_exited", "stage_completed"))
        expected.append("fold_completed")
    expected.append("pilot_completed")
    if not events or [event.get("event") for event in events] != expected:
        raise TrainingContractError("subject parent lifecycle sequence failed")
    previous_time = None
    for event in events:
        observed = _quality_utc_timestamp(event.get("timestamp"), "subject lifecycle")
        if previous_time is not None and observed < previous_time:
            raise TrainingContractError("subject lifecycle timestamps are not monotonic")
        previous_time = observed
    if (
        events[0].get("run_prefix") != protocol["run_prefix"]
        or events[0].get("resource_evidence_sha256") != summary["resource_evidence_sha256"]
        or events[1].get("fold_count") != len(folds)
        or events[-1].get("fold_count") != len(folds)
    ):
        raise TrainingContractError("subject parent lifecycle boundary failed")
    cursor = 2
    verified_folds = []
    for index, (planned, completed_fold) in enumerate(zip(folds, summary_folds)):
        fold_started = events[cursor]
        cursor += 1
        if (
            fold_started.get("fold_index") != index
            or fold_started.get("test_subject") != planned.get("test_subject")
            or fold_started.get("validation_subject") != planned.get("validation_subject")
        ):
            raise TrainingContractError("subject parent fold-start evidence failed")
        for stage in STAGES:
            stage_started, worker_exited, stage_completed = events[cursor:cursor + 3]
            cursor += 3
            if (
                stage_started.get("fold_index") != index
                or stage_started.get("stage") != stage
                or worker_exited.get("fold_index") != index
                or worker_exited.get("stage") != stage
                or worker_exited.get("returncode") != 0
                or stage_completed.get("fold_index") != index
                or stage_completed.get("stage", stage) != stage
                or stage_completed.get("status") != ("verified" if stage == "stage3" else "stage_completed")
            ):
                raise TrainingContractError("subject parent stage lifecycle failed")
            for field in ("stdout", "stderr"):
                log_path = _provenance_path(worker_exited[field + "_path"])
                if sha256_file(log_path) != worker_exited[field + "_sha256"]:
                    raise TrainingContractError("subject parent worker log binding failed")
            cleanup_path = _provenance_path(stage_completed.get("cleanup_path"))
            if sha256_file(cleanup_path) != stage_completed.get("cleanup_sha256"):
                raise TrainingContractError("subject parent worker cleanup binding failed")
        fold_completed = events[cursor]
        cursor += 1
        comparable = {key: value for key, value in fold_completed.items() if key not in ("event", "timestamp")}
        if comparable != completed_fold:
            raise TrainingContractError("subject parent completed-fold binding failed")
        fold_directory = _provenance_path(completed_fold.get("directory"))
        verification = verify_run_directory(fold_directory, require_completed=True)
        if (
            completed_fold.get("fold_index") != index
            or completed_fold.get("run_id") != planned.get("run_id")
            or completed_fold.get("test_subject") != planned.get("test_subject")
            or completed_fold.get("validation_subject") != planned.get("validation_subject")
            or completed_fold.get("execution_sha256") != verification["execution_sha256"]
            or (fold_directory / "execution.json.lock").exists()
        ):
            raise TrainingContractError("subject parent fold verification binding failed")
        verified_folds.append({
            "fold_index": index,
            "run_id": completed_fold["run_id"],
            "execution_sha256": verification["execution_sha256"],
            "terminal_checkpoint_sha256": verification["terminal_checkpoint_sha256"],
        })
    result = {
        "terminal_validated": True,
        "run_prefix": protocol["run_prefix"],
        "fold_count": len(verified_folds),
        "protocol_sha256": sha256_file(protocol_path),
        "summary_sha256": sha256_file(summary_path),
        "lifecycle_sha256": sha256_file(lifecycle_path),
        "dispatch_marker_sha256": sha256_file(dispatch),
        "attempt_marker_sha256": sha256_file(attempt),
        "folds": verified_folds,
    }
    if require_terminal_artifact:
        terminal_path = root / "terminal-validation.json"
        try:
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise TrainingContractError("subject terminal-validation artifact is unreadable") from error
        expected_terminal = {"status": "verified", "verification": result}
        if terminal != expected_terminal:
            raise TrainingContractError("subject terminal-validation artifact binding failed")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-dir")
    target.add_argument("--subject-runtime-root")
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--issue-subject-terminal-validation", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.subject_runtime_root:
            if args.allow_incomplete:
                raise TrainingContractError("parent runtime verification cannot allow incomplete state")
            result = verify_subject_generalization_runtime(
                args.subject_runtime_root,
                require_terminal_artifact=not args.issue_subject_terminal_validation,
            )
        else:
            if args.issue_subject_terminal_validation:
                raise TrainingContractError("terminal-validation issuance requires a subject runtime root")
            result = verify_run_directory(
                args.run_dir,
                require_completed=not args.allow_incomplete,
            )
        print(
            json.dumps(
                {"status": "verified", "verification": result},
                sort_keys=True,
            )
        )
        return 0
    except (TrainingContractError, OSError, ValueError) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
