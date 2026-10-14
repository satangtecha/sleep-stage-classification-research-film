"""Create the immutable Plan-15 diagnosis and Plan-16 sampling preview."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training.quality_sampling import (
    LABEL_ORDER,
    QUALITY_CAP_POLICY,
    class_counts,
    load_verified_stage3_labels,
    sample_class_balanced_members_per_subject,
)
from paper_faithful.training.subject_generalization import sample_record_members_per_subject
from paper_faithful.training.splits import EpochMember


NAMES = ("W", "N1", "N2", "N3", "REM")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _named_counts(value):
    return {NAMES[label]: int(value[str(label)]) for label in LABEL_ORDER}


def _membership_hash(members):
    return hashlib.sha256(
        ("\n".join(sorted(member.key for member in members)) + "\n").encode("utf-8")
    ).hexdigest()


def _write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--prior-receipt", required=True)
    parser.add_argument("--plan15-protocol", required=True)
    parser.add_argument("--plan15-acceptance", required=True)
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    protocol = json.loads(Path(args.plan15_protocol).read_text(encoding="utf-8"))
    acceptance = json.loads(Path(args.plan15_acceptance).read_text(encoding="utf-8"))
    subjects = tuple(protocol["pilot_subjects"])
    records = runner._read_record_bindings_for_plan(args.manifest)
    labels, label_evidence = load_verified_stage3_labels(
        args.manifest, args.prior_receipt, subjects
    )

    subject_rows = []
    plan15_by_subject = {}
    plan16_by_subject = {}
    for subject in subjects:
        full = tuple(
            member
            for record_id, subject_id, epochs in records
            if subject_id == subject
            for member in (EpochMember(subject, record_id, epoch) for epoch in range(epochs))
        )
        old = sample_record_members_per_subject(records, {subject}, 32, 42)
        proposed = sample_class_balanced_members_per_subject(records, {subject}, 64, 42, labels)
        plan15_by_subject[subject] = old
        plan16_by_subject[subject] = proposed
        subject_rows.append({
            "subject": subject,
            "full_count": len(full),
            "full_class_counts": _named_counts(class_counts(full, labels)),
            "plan15_cap32_count": len(old),
            "plan15_cap32_class_counts": _named_counts(class_counts(old, labels)),
            "plan15_membership_sha256": _membership_hash(old),
            "plan16_cap64_count": len(proposed),
            "plan16_cap64_class_counts": _named_counts(class_counts(proposed, labels)),
            "plan16_membership_sha256": _membership_hash(proposed),
        })

    folds = []
    pooled = [[0 for _ in LABEL_ORDER] for _ in LABEL_ORDER]
    for item in protocol["folds"]:
        fold_number = int(item["fold_index"]) + 1
        test_subject = item["test_subject"]
        validation_subject = item["validation_subject"]
        train_subjects = sorted(set(subjects) - {test_subject, validation_subject})
        old_train = tuple(member for subject in train_subjects for member in plan15_by_subject[subject])
        proposed_train = tuple(member for subject in train_subjects for member in plan16_by_subject[subject])
        run_id = item["run_id"]
        metric_path = Path(args.runs_root) / run_id / "stage3.metrics.json"
        metric = json.loads(metric_path.read_text(encoding="utf-8"))
        classification = metric["metrics"]["test"]["classification"]
        confusion = classification["confusion_matrix"]
        for row_index, row in enumerate(confusion):
            for column_index, value in enumerate(row):
                pooled[row_index][column_index] += int(value)
        supports = {
            name: int(classification["per_class"][name]["support"])
            for name in NAMES
        }
        folds.append({
            "fold": fold_number,
            "test_subject": test_subject,
            "validation_subject": validation_subject,
            "train_subjects": train_subjects,
            "plan15_train_class_counts": _named_counts(class_counts(old_train, labels)),
            "plan15_validation_class_counts": _named_counts(class_counts(plan15_by_subject[validation_subject], labels)),
            "plan15_test_class_counts": _named_counts(class_counts(plan15_by_subject[test_subject], labels)),
            "plan16_train_class_counts": _named_counts(class_counts(proposed_train, labels)),
            "plan16_validation_class_counts": _named_counts(class_counts(plan16_by_subject[validation_subject], labels)),
            "plan16_test_class_counts": _named_counts(class_counts(plan16_by_subject[test_subject], labels)),
            "observed_test_support": supports,
            "observed_confusion_matrix": confusion,
            "observed_accuracy": classification["accuracy"],
            "observed_macro_f1": classification["macro"]["f1"],
            "stage3_metrics_path": str(metric_path.resolve()),
            "stage3_metrics_sha256": _sha(metric_path),
        })

    predicted = [sum(pooled[row][column] for row in range(5)) for column in range(5)]
    actual = [sum(row) for row in pooled]
    output = {
        "schema_version": 1,
        "artifact_type": "PLAN15_ERROR_ANALYSIS_PLAN16_CAP64_PREVIEW_V1",
        "status": "verified",
        "baseline": {
            "run_prefix": protocol["run_prefix"],
            "mean_accuracy": acceptance["aggregate_metrics"]["mean_accuracy"],
            "mean_macro_f1": acceptance["aggregate_metrics"]["mean_macro_f1"],
            "plan15_protocol_path": str(Path(args.plan15_protocol).resolve()),
            "plan15_protocol_sha256": _sha(args.plan15_protocol),
            "plan15_acceptance_path": str(Path(args.plan15_acceptance).resolve()),
            "plan15_acceptance_sha256": _sha(args.plan15_acceptance),
        },
        "label_evidence": label_evidence,
        "plan16_sampling": {
            "policy": QUALITY_CAP_POLICY,
            "cap_scope": "per_subject_per_split",
            "cap": 64,
            "seed": 42,
            "guarantee": "every locally available class is selected before round-robin filling",
        },
        "subjects": subject_rows,
        "folds": folds,
        "pooled_failure": {
            "label_order": list(NAMES),
            "confusion_matrix": pooled,
            "actual_support": dict(zip(NAMES, actual)),
            "predicted_count": dict(zip(NAMES, predicted)),
            "n1_correct": pooled[1][1],
            "n3_correct": pooled[3][3],
            "rem_correct": pooled[4][4],
            "stage2_mean_silhouette": acceptance["aggregate_metrics"]["mean_stage2_silhouette"],
        },
        "interpretation": [
            "Plan 15 sampled labels blindly, so minority-stage support varied and N3 was absent in some held-out subsets.",
            "The pooled classifier predicted N3 rarely or never and did not correctly classify N1 or N3.",
            "Negative mean Stage-2 silhouette is consistent with weak class separation, but does not prove a single causal mechanism.",
            "Plan 16 changes sampling and Stage-3 loss only in the quality track; it is not paper-exact.",
        ],
    }
    _write_once(args.destination, output)
    print(json.dumps({"status": "created", "path": str(Path(args.destination).resolve()), "sha256": _sha(args.destination)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
