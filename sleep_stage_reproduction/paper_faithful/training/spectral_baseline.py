"""Deterministic CPU baseline for subject-held-out sleep staging.

This is deliberately a small, transparent comparator rather than a replacement
for the paper-faithful three-stage model.  It reconstructs the exact quality
sampling membership recorded by a completed subject-generalization run and
refuses to fit if any split hash differs.  Features are summary statistics of
the already-validated Stage-3 SST magnitude; no GPU or TensorFlow is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

from .cache_loader import load_canonical_cache
from .metrics import classification_metrics
from .quality_sampling import (
    LABEL_ORDER,
    load_verified_stage3_labels,
    sample_class_balanced_members_per_subject,
)
from .subject_generalization_runner import _read_record_bindings_for_plan


BASELINE_ID = "CPU_SST_MAGNITUDE_LOGISTIC_V1"
ROUTE = "PAPER_STAGE3_V1"
L2_GRID = (1e-4, 1e-3, 1e-2, 1e-1)
ITERATIONS = 800
LEARNING_RATE = 0.20
EPSILON = 1e-8


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def membership_hash(members) -> str:
    return hashlib.sha256(
        ("\n".join(sorted(member.key for member in members)) + "\n").encode("utf-8")
    ).hexdigest()


def _write_once(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def extract_features(cache, members: tuple) -> tuple[np.ndarray, np.ndarray]:
    """Extract 64 spectral means + 64 spectral standard deviations per epoch."""
    features, labels = [], []
    for member, tensor, label in cache.stage3_sequences(members, ROUTE):
        if member not in members or int(label) not in LABEL_ORDER:
            raise ValueError("baseline cache membership/label is invalid")
        array = np.asarray(tensor, dtype=np.float64)
        if array.ndim != 4 or array.shape[-1] != 2 or not np.isfinite(array).all():
            raise ValueError("baseline requires finite complex SST tensors")
        magnitude = np.hypot(array[..., 0], array[..., 1])
        log_magnitude = np.log1p(magnitude)
        # Stage-3 tensor is [windows, time-frequency row, frequency, complex].
        # Aggregate every frequency bin across windows and within-window time.
        spectral_mean = log_magnitude.mean(axis=(0, 1))
        spectral_std = log_magnitude.std(axis=(0, 1))
        vector = np.concatenate((spectral_mean, spectral_std)).astype(np.float64)
        if vector.shape != (128,) or not np.isfinite(vector).all():
            raise ValueError("baseline feature extraction is invalid")
        features.append(vector)
        labels.append(int(label))
    if not features:
        raise ValueError("baseline split is empty")
    return np.stack(features), np.asarray(labels, dtype=np.int64)


def standardize_from_train(train: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    if train.ndim != 2 or train.shape[0] < 1 or not np.isfinite(train).all():
        raise ValueError("baseline training features are invalid")
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale = np.where(scale > EPSILON, scale, 1.0)
    result = ((train - mean) / scale,)
    for values in others:
        if values.ndim != 2 or values.shape[1] != train.shape[1] or not np.isfinite(values).all():
            raise ValueError("baseline non-training features are invalid")
        result += ((values - mean) / scale,)
    return result


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def train_weighted_multinomial_logistic(
    features: np.ndarray, labels: np.ndarray, *, l2: float,
    iterations: int = ITERATIONS, learning_rate: float = LEARNING_RATE,
) -> tuple[np.ndarray, np.ndarray]:
    """Full-batch deterministic weighted multinomial logistic regression."""
    if (
        features.ndim != 2 or labels.ndim != 1 or features.shape[0] != labels.size
        or not np.isfinite(features).all() or not set(labels.tolist()).issubset(LABEL_ORDER)
        or l2 <= 0 or iterations < 1 or learning_rate <= 0
    ):
        raise ValueError("baseline logistic inputs are invalid")
    count, width = features.shape
    counts = np.bincount(labels, minlength=5).astype(np.float64)
    if np.any(counts == 0):
        raise ValueError("baseline requires every class in the training split")
    sample_weight = count / (5.0 * counts[labels])
    weights = np.zeros((width, 5), dtype=np.float64)
    bias = np.zeros((5,), dtype=np.float64)
    one_hot = np.eye(5, dtype=np.float64)[labels]
    normalizer = float(sample_weight.sum())
    for _ in range(iterations):
        probability = _softmax(features @ weights + bias)
        residual = (probability - one_hot) * sample_weight[:, None]
        gradient_w = (features.T @ residual) / normalizer + l2 * weights
        gradient_b = residual.sum(axis=0) / normalizer
        weights -= learning_rate * gradient_w
        bias -= learning_rate * gradient_b
        if not np.isfinite(weights).all() or not np.isfinite(bias).all():
            raise ValueError("baseline logistic optimisation became non-finite")
    return weights, bias


def predict(features: np.ndarray, weights: np.ndarray, bias: np.ndarray) -> np.ndarray:
    if features.ndim != 2 or weights.shape != (features.shape[1], 5) or bias.shape != (5,):
        raise ValueError("baseline prediction shapes are invalid")
    return np.argmax(features @ weights + bias, axis=1).astype(np.int64)


def choose_l2(train_x, train_y, validation_x, validation_y) -> tuple[float, dict]:
    """Choose only by validation macro-F1, with deterministic tie breaking."""
    trials = {}
    best = None
    for l2 in L2_GRID:
        weights, bias = train_weighted_multinomial_logistic(train_x, train_y, l2=l2)
        score = classification_metrics(validation_y, predict(validation_x, weights, bias))
        macro_f1 = float(score["macro"]["f1"])
        trials[str(l2)] = {"validation_macro_f1": macro_f1, "validation_accuracy": float(score["accuracy"])}
        candidate = (macro_f1, -l2, l2)
        if best is None or candidate > best:
            best = candidate
    return best[2], trials


def _required_execution(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "completed" or not isinstance(value.get("config"), dict):
        raise ValueError("baseline requires completed execution.json")
    return value["config"]


def _fold_members(records, labels, config: dict) -> dict[str, tuple]:
    required = {"pilot_subjects", "test_subject", "validation_subject", "per_split_epoch_cap", "seed", "split_hashes"}
    if not required.issubset(config):
        raise ValueError("baseline execution config lacks required split fields")
    subjects = tuple(config["pilot_subjects"])
    if len(subjects) != 6 or len(set(subjects)) != 6:
        raise ValueError("baseline requires the six-subject pilot")
    test, validation = config["test_subject"], config["validation_subject"]
    if test not in subjects or validation not in subjects or test == validation:
        raise ValueError("baseline execution subjects are invalid")
    cap, seed = config["per_split_epoch_cap"], config["seed"]
    train_subjects = tuple(sorted(set(subjects) - {test, validation}))
    splits = {
        "train": sample_class_balanced_members_per_subject(records, train_subjects, cap, seed, labels),
        "validation": sample_class_balanced_members_per_subject(records, {validation}, cap, seed, labels),
        "test": sample_class_balanced_members_per_subject(records, {test}, cap, seed, labels),
    }
    expected = config["split_hashes"]
    if set(expected) != set(splits) or any(membership_hash(splits[name]) != expected[name] for name in splits):
        raise ValueError("baseline reconstructed membership does not equal locked execution")
    return splits


def run(args) -> dict:
    runs_root = Path(args.runs_root).resolve(strict=True)
    destination = Path(args.destination)
    if destination.exists():
        raise FileExistsError("baseline destination already exists")
    records = _read_record_bindings_for_plan(args.cache_manifest)
    # The run's protocol establishes selected subjects; start from fold 1.
    first = runs_root / (args.run_prefix + "-fold01-test-" + args.first_test_subject) / "execution.json"
    first_config = _required_execution(first)
    subjects = tuple(first_config["pilot_subjects"])
    labels, label_evidence = load_verified_stage3_labels(args.cache_manifest, args.label_evidence_receipt, subjects)
    # Reconstruct every locked split before opening the cache.  The validated
    # receipt is deliberately compact: it proves the selected pilot members,
    # not every epoch in the full cohort.  Passing this exact union to the
    # loader therefore keeps the same fail-closed membership check while
    # avoiding an invalid demand for full-cohort coverage.
    prepared_folds = []
    required_members = {}
    for index, test_subject in enumerate(subjects, start=1):
        execution_path = runs_root / (args.run_prefix + f"-fold{index:02d}-test-{test_subject}") / "execution.json"
        config = _required_execution(execution_path)
        if tuple(config["pilot_subjects"]) != subjects:
            raise ValueError("baseline fold pilot subjects differ")
        splits = _fold_members(records, labels, config)
        for values in splits.values():
            for member in values:
                required_members[member.key] = member
        prepared_folds.append((index - 1, config, splits))

    cache = load_canonical_cache(
        args.cache_manifest,
        validated_receipt=args.cache_validation_receipt,
        required_members=tuple(required_members.values()),
    )
    folds = []
    try:
        for fold_index, config, splits in prepared_folds:
            train_x, train_y = extract_features(cache, splits["train"])
            validation_x, validation_y = extract_features(cache, splits["validation"])
            test_x, test_y = extract_features(cache, splits["test"])
            train_x, validation_x, test_x = standardize_from_train(train_x, validation_x, test_x)
            chosen_l2, trials = choose_l2(train_x, train_y, validation_x, validation_y)
            weights, bias = train_weighted_multinomial_logistic(train_x, train_y, l2=chosen_l2)
            folds.append({
                "fold_index": fold_index,
                "test_subject": config["test_subject"],
                "validation_subject": config["validation_subject"],
                "split_hashes": dict(config["split_hashes"]),
                "split_counts": {name: len(values) for name, values in splits.items()},
                "selected_l2": chosen_l2,
                "validation_selection": trials,
                "test": classification_metrics(test_y, predict(test_x, weights, bias)),
            })
    finally:
        cache.close()
    aggregate = {
        "mean_accuracy": float(np.mean([fold["test"]["accuracy"] for fold in folds])),
        "mean_macro_f1": float(np.mean([fold["test"]["macro"]["f1"] for fold in folds])),
    }
    output = {
        "schema_version": 1,
        "artifact_type": "SUBJECT_GENERALIZATION_CPU_SPECTRAL_BASELINE_V1",
        "status": "verified",
        "baseline_id": BASELINE_ID,
        "baseline_source_sha256": sha256_file(Path(__file__)),
        "feature_definition": "log1p SST magnitude: per-frequency mean and standard deviation across Stage-3 windows and within-window time",
        "selection_policy": "train-only standardization; validation-only L2 selection; one held-out test evaluation",
        "cache_manifest_path": str(Path(args.cache_manifest).resolve()),
        "cache_manifest_sha256": sha256_file(Path(args.cache_manifest)),
        "label_evidence": label_evidence,
        "source_run_prefix": args.run_prefix,
        "source_first_execution_sha256": sha256_file(first),
        "folds": folds,
        "aggregate": aggregate,
    }
    _write_once(destination, output)
    return {"status": "created", "path": str(destination.resolve()), "sha256": sha256_file(destination)}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cache-manifest", required=True)
    value.add_argument("--cache-validation-receipt", required=True)
    value.add_argument("--label-evidence-receipt", required=True)
    value.add_argument("--runs-root", required=True)
    value.add_argument("--run-prefix", required=True)
    value.add_argument("--first-test-subject", required=True)
    value.add_argument("--destination", required=True)
    return value


def main() -> int:
    result = run(parser().parse_args())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
