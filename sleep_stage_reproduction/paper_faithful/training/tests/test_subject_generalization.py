import json
import tempfile
import unittest
from pathlib import Path

from paper_faithful.training.splits import EpochMember, validate_no_leakage
from paper_faithful.training.subject_generalization import (
    SUBJECT_GENERALIZATION_PROTOCOL_ID,
    cap_subject_balanced_plan,
    build_pilot_folds,
    build_subject_fold,
    safe_fold_id,
    select_pilot_subjects,
)
from paper_faithful.training.subject_generalization_runner import (
    LOCKED_TF24_PYTHON,
    _add_runtime_binding,
    _load_resource_evidence,
    _stream_subject_balanced_cap,
)
from paper_faithful.training.trainer import TrainingContractError


def members(subject_count=12):
    return tuple(
        EpochMember(f"SC{subject:04d}", f"SC{subject:04d}", epoch)
        for subject in range(subject_count)
        for epoch in range(3)
    )


class SubjectGeneralizationTests(unittest.TestCase):
    def test_selection_is_deterministic_and_bounded(self):
        first = select_pilot_subjects(members(), seed=42, count=6)
        second = select_pilot_subjects(members(), seed=42, count=6)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual(len(set(first)), 6)

    def test_folds_cover_each_selected_subject_without_subject_leakage(self):
        selected, folds = build_pilot_folds(members(), selection_seed=42, count=6)
        self.assertEqual(tuple(fold.test_subject for fold in folds), selected)
        self.assertEqual({fold.validation_subject for fold in folds}, set(selected))
        for fold in folds:
            self.assertEqual(fold.plan.protocol_id, SUBJECT_GENERALIZATION_PROTOCOL_ID)
            validate_no_leakage(fold.plan, require_subject_disjoint=True)
            train = {item.subject_id for item in fold.plan.train}
            validation = {item.subject_id for item in fold.plan.validation}
            test = {item.subject_id for item in fold.plan.test}
            self.assertFalse(train & validation)
            self.assertFalse(train & test)
            self.assertFalse(validation & test)

    def test_membership_hash_changes_when_a_partition_changes(self):
        selected = select_pilot_subjects(members(), seed=42, count=6)
        original = build_subject_fold(members(), selected, 0)
        altered = build_subject_fold(members() + (EpochMember("SC9999", "SC9999", 0),), selected, 0)
        self.assertNotEqual(
            original.plan.membership_hashes["train"],
            altered.plan.membership_hashes["train"],
        )

    def test_safe_fold_id_rejects_path_injection(self):
        self.assertEqual(
            safe_fold_id("subject-generalization-v1-pilot-20260906", 0, "SC0400"),
            "subject-generalization-v1-pilot-20260906-fold01-test-SC0400",
        )
        with self.assertRaises(ValueError):
            safe_fold_id("subject-generalization-v1-pilot-20260906", 0, "../escape")

    def test_too_few_subjects_is_refused(self):
        with self.assertRaises(ValueError):
            select_pilot_subjects(members(subject_count=5), seed=42, count=6)

    def test_cap_is_subject_balanced_and_deterministic(self):
        selected = select_pilot_subjects(members(), seed=42, count=6)
        fold = build_subject_fold(members(), selected, 0)
        first = cap_subject_balanced_plan(fold.plan, 5)
        second = cap_subject_balanced_plan(fold.plan, 5)
        self.assertEqual(first.membership_hashes, second.membership_hashes)
        self.assertEqual(
            {item.subject_id for item in first.train},
            set(fold.train_subjects[:5]),
        )
        self.assertEqual(len(first.train), 5)
        self.assertEqual(len(first.validation), 3)
        self.assertEqual(len(first.test), 3)
        validate_no_leakage(first, require_subject_disjoint=True)

    def test_resource_gate_refuses_non_finite_capacity(self):
        evidence = {
            "status": "pass",
            "ready": True,
            "checks": {
                "power_online": True,
                "critical": False,
                "physical_memory_available_mb": float("nan"),
                "commit_headroom_mb": 9000,
                "c_free_gib": 20,
                "e_free_gib": 20,
                "windows_gpu_compute_process_count": 0,
                "wsl_gpu_compute_process_count": 0,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resource.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaises(TrainingContractError):
                _load_resource_evidence(path)

    def test_manifest_only_cap_hash_matches_runtime_cap(self):
        selected = select_pilot_subjects(members(), seed=42, count=6)
        fold = build_subject_fold(members(), selected, 0)
        capped = cap_subject_balanced_plan(fold.plan, 5)
        records = tuple(
            ("SC%04d" % subject, "SC%04d" % subject, 3)
            for subject in range(12)
        )
        train_subjects = set(fold.train_subjects)
        digest, record_count, epoch_count, subject_count = _stream_subject_balanced_cap(
            records, train_subjects, 5
        )
        self.assertEqual(digest, capped.membership_hashes["train"])
        self.assertEqual(record_count, len({item.record_id for item in capped.train}))
        self.assertEqual(epoch_count, len(capped.train))
        self.assertEqual(subject_count, len({item.subject_id for item in capped.train}))

    def test_protocol_binds_locked_runtime_and_verifier(self):
        record = _add_runtime_binding({})
        binding = record["runtime_binding"]
        self.assertEqual(binding["locked_python_executable"], LOCKED_TF24_PYTHON)
        self.assertEqual(binding["tensorflow_version"], "2.4.0")
        self.assertEqual(binding["standalone_verifier_command"][0], LOCKED_TF24_PYTHON)
        self.assertIn("paper_faithful.training.verify_run", binding["standalone_verifier_command"])


if __name__ == "__main__":
    unittest.main()
