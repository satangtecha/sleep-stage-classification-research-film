"""Fail-closed error analysis for completed subject-held-out experiments.

The report never reads predictions or labels directly.  It aggregates only the
signed stage-3 metric artifacts emitted after each fold's locked verification.
That makes it appropriate for comparing independently completed runs without
opening a route for re-scoring or test-set tuning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .metrics import LABELS, classification_metrics


ANALYSIS_ID = "SUBJECT_GENERALIZATION_ERROR_ANALYSIS_V1"


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object: {}".format(path))
    return value


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


def _classification(metric_artifact: dict) -> dict:
    try:
        result = metric_artifact["metrics"]["test"]["classification"]
        matrix = np.asarray(result["confusion_matrix"], dtype=np.int64)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("stage-3 metric lacks test classification") from exc
    if matrix.shape != (5, 5) or np.any(matrix < 0):
        raise ValueError("stage-3 confusion matrix is invalid")
    if classification_metrics(
        np.repeat(np.arange(5), matrix.sum(axis=1)),
        np.concatenate([np.repeat(np.arange(5), matrix[row]) for row in range(5)]),
    )["confusion_matrix"] != matrix.tolist():
        raise ValueError("stage-3 confusion matrix failed deterministic integrity check")
    return result


def _metric_path(runs_root: Path, prefix: str, fold_index: int, subject: str) -> Path:
    return runs_root / ("{}-fold{:02d}-test-{}".format(prefix, fold_index, subject)) / "stage3.metrics.json"


def analyse_run(runs_root: Path, prefix: str) -> dict:
    folders = sorted(runs_root.glob(prefix + "-fold??-test-*"))
    if len(folders) != 6:
        raise ValueError("{} must have exactly six fold directories".format(prefix))
    folds, pooled = [], np.zeros((5, 5), dtype=np.int64)
    seen_subjects = set()
    for folder in folders:
        execution = _read_json(folder / "execution.json")
        config = execution.get("config", {})
        if execution.get("status") != "completed" or not isinstance(config, dict):
            raise ValueError("{} is not a completed fold".format(folder))
        subject = config.get("test_subject")
        if not isinstance(subject, str) or subject in seen_subjects:
            raise ValueError("{} has invalid/duplicate test subject".format(folder))
        seen_subjects.add(subject)
        metrics_path = folder / "stage3.metrics.json"
        metrics = _read_json(metrics_path)
        classification = _classification(metrics)
        matrix = np.asarray(classification["confusion_matrix"], dtype=np.int64)
        pooled += matrix
        folds.append({
            "test_subject": subject,
            "fold_directory": str(folder),
            "stage3_metrics_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
            "accuracy": float(classification["accuracy"]),
            "macro_f1": float(classification["macro"]["f1"]),
            "support": int(matrix.sum()),
            "class_support": {LABELS[index]: int(matrix[index].sum()) for index in range(5)},
            "confusion_matrix": matrix.tolist(),
        })
    folds.sort(key=lambda item: item["test_subject"])
    truth = np.repeat(np.arange(5), pooled.sum(axis=1))
    predicted = np.concatenate([np.repeat(np.arange(5), pooled[row]) for row in range(5)])
    pooled_metrics = classification_metrics(truth, predicted)
    support_alerts = [
        {"test_subject": item["test_subject"], "absent_classes": [name for name, count in item["class_support"].items() if count == 0]}
        for item in folds
        if any(count == 0 for count in item["class_support"].values())
    ]
    return {
        "run_prefix": prefix,
        "folds": folds,
        "pooled_test": pooled_metrics,
        "fold_mean": {
            "accuracy": float(np.mean([item["accuracy"] for item in folds])),
            "macro_f1": float(np.mean([item["macro_f1"] for item in folds])),
        },
        "support_alerts": support_alerts,
    }


def build_report(runs_root: Path, prefixes: tuple[str, ...]) -> dict:
    if len(prefixes) < 1 or len(set(prefixes)) != len(prefixes):
        raise ValueError("provide unique run prefixes")
    runs = [analyse_run(runs_root, prefix) for prefix in prefixes]
    comparison = []
    if len(runs) == 2:
        left = {item["test_subject"]: item for item in runs[0]["folds"]}
        right = {item["test_subject"]: item for item in runs[1]["folds"]}
        if set(left) != set(right):
            raise ValueError("two-run comparison requires identical held-out subjects")
        comparison = [
            {"test_subject": subject, "accuracy_delta": right[subject]["accuracy"] - left[subject]["accuracy"], "macro_f1_delta": right[subject]["macro_f1"] - left[subject]["macro_f1"]}
            for subject in sorted(left)
        ]
    return {"analysis_id": ANALYSIS_ID, "runs": runs, "paired_comparison": comparison}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--run-prefix", required=True, action="append")
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("destination already exists")
    report = build_report(args.runs_root, tuple(args.run_prefix))
    _write_once(args.destination, report)
    print(json.dumps({"destination": str(args.destination), "analysis_id": ANALYSIS_ID}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
