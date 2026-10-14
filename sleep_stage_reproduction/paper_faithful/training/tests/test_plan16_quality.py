from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training.quality_sampling import (
    QUALITY_CAP_POLICY,
    QUALITY_CLASS_WEIGHTING_ID,
    QUALITY_EARLY_STOPPING_ID,
    balanced_class_weights,
    class_counts,
    load_verified_stage3_labels,
    sample_class_balanced_members_per_subject,
)
from paper_faithful.training.splits import EpochMember
from paper_faithful.training.trainer import QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID, QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID, SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID, TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID, TrainingContractError, _validate_fit_history, stage_spec
from paper_faithful.training import verify_run as verifier


class Plan16QualityTests(unittest.TestCase):
    def _records_and_labels(self):
        records = (("R1", "S1", 100), ("R2", "S2", 100))
        labels = {}
        for record, subject, epochs in records:
            for epoch in range(epochs):
                labels[EpochMember(subject, record, epoch).key] = epoch % 5
        return records, labels

    def test_class_balanced_cap64_is_deterministic_and_per_subject(self):
        records, labels = self._records_and_labels()
        first = sample_class_balanced_members_per_subject(records, {"S1", "S2"}, 64, 42, labels)
        second = sample_class_balanced_members_per_subject(records, {"S1", "S2"}, 64, 42, labels)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 128)
        for subject in ("S1", "S2"):
            selected = tuple(member for member in first if member.subject_id == subject)
            counts = class_counts(selected, labels)
            self.assertEqual(sum(counts.values()), 64)
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
            self.assertTrue(all(value > 0 for value in counts.values()))

    def test_locally_missing_class_is_not_fabricated(self):
        records = (("R1", "S1", 40),)
        labels = {EpochMember("S1", "R1", epoch).key: epoch % 4 for epoch in range(40)}
        selected = sample_class_balanced_members_per_subject(records, {"S1"}, 20, 42, labels)
        counts = class_counts(selected, labels)
        self.assertEqual(counts["4"], 0)
        self.assertTrue(all(counts[str(label)] > 0 for label in range(4)))

    def test_train_only_balanced_weights(self):
        members = tuple(EpochMember("S1", "R1", index) for index in range(15))
        values = [0] * 5 + [1] * 4 + [2] * 3 + [3] * 2 + [4]
        labels = dict(zip(members, values))
        result = balanced_class_weights(members, labels.__getitem__)
        self.assertEqual(result["id"], QUALITY_CLASS_WEIGHTING_ID)
        self.assertEqual(result["counts"], {"0": 5, "1": 4, "2": 3, "3": 2, "4": 1})
        self.assertAlmostEqual(result["weights"]["4"], 3.0)

    def test_quality_profile_and_stage3_spec_are_locked(self):
        profile = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertTrue(profile["quality_track"])
        self.assertTrue(profile["fresh_process_per_stage"])
        self.assertEqual(profile["cap"], 64)
        spec = stage_spec(
            "PAPER_TEXT_V1", "stage3", microbatch=1,
            stage3_gradient_clip_norm=1.0,
            stage3_stability_adaptation_id=runner.STAGE3_STABILITY_ADAPTATION_ID,
            epochs_override=12,
            quality_class_weighting_id=QUALITY_CLASS_WEIGHTING_ID,
            quality_early_stopping_id=QUALITY_EARLY_STOPPING_ID,
        )
        self.assertEqual(spec["early_stopping"]["patience"], 3)
        self.assertEqual(spec["early_stopping"]["min_delta"], 1e-4)
        self.assertEqual(spec["class_weighting"]["source_split"], "train_only")
        self.assertFalse(spec["paper_exact"])

    def test_conservative_quality_profile_binds_the_reviewed_optimizer_change(self):
        profile = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertEqual(profile["stage3_optimizer_adaptation_id"], QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID)
        self.assertEqual(profile["min_c_free_gib"], 12.0)
        self.assertEqual(profile["min_e_free_gib"], 15.0)
        spec = stage_spec(
            "PAPER_TEXT_V1", "stage3", microbatch=1,
            stage3_gradient_clip_norm=1.0,
            stage3_stability_adaptation_id=runner.STAGE3_STABILITY_ADAPTATION_ID,
            stage3_optimizer_adaptation_id=profile["stage3_optimizer_adaptation_id"],
            epochs_override=12,
            quality_class_weighting_id=QUALITY_CLASS_WEIGHTING_ID,
            quality_early_stopping_id=QUALITY_EARLY_STOPPING_ID,
        )
        self.assertEqual(spec["learning_rate"], 0.02)
        self.assertEqual(spec["scheduler"], {"name": "ReduceLROnPlateau", "factor": 0.5, "patience": 2, "min_lr": 1e-5})

    def test_subject_zscore_profile_binds_every_stage_without_relaxing_stage3(self):
        profile = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_SUBJECT_ZSCORE_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertEqual(profile["subject_normalization_id"], SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID)
        self.assertEqual(profile["stage3_optimizer_adaptation_id"], QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID)
        specs = runner._stage_specs(profile["stage_epochs"], profile)
        self.assertTrue(all(spec["subject_normalization"]["fit_uses_labels"] is False for spec in specs.values()))
        self.assertTrue(all(spec["subject_normalization"]["id"] == SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID for spec in specs.values()))

    def test_time_mask_profile_is_train_only_and_does_not_enable_zscore(self):
        profile = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_TIME_MASK_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertEqual(profile["train_augmentation_id"], TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID)
        self.assertIsNone(profile["subject_normalization_id"])
        specs = runner._stage_specs(profile["stage_epochs"], profile)
        self.assertTrue(all(spec["train_augmentation"]["scope"] == "train_split_only" for spec in specs.values()))
        self.assertTrue(all(spec["subject_normalization"] is None for spec in specs.values()))

    def test_focal_loss_profile_is_stage3_only_and_preserves_quality_guards(self):
        profile = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertEqual(profile["stage3_loss_adaptation_id"], QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID)
        specs = runner._stage_specs(profile["stage_epochs"], profile)
        self.assertIsNone(specs["stage1"]["stage3_loss_adaptation"])
        self.assertIsNone(specs["stage2"]["stage3_loss_adaptation"])
        self.assertEqual(specs["stage3"]["loss"], "sparse_categorical_focal_gamma_2")
        self.assertEqual(specs["stage3"]["stage3_loss_adaptation"]["gamma"], 2.0)
        self.assertEqual(specs["stage3"]["class_weighting"]["source_split"], "train_only")
        with self.assertRaises(TrainingContractError):
            stage_spec("PAPER_TEXT_V1", "stage3", microbatch=1, stage3_loss_adaptation_id=QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID)

    def test_storage_recovery_profile_changes_only_c_floor(self):
        base = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_FOCAL_C10_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        recovery = runner._resource_profile(SimpleNamespace(
            resource_profile=runner.QUALITY_BALANCED_CAP64_E12_FOCAL_C85_PROFILE_ID,
            cap=64, epochs=12, subject_count=6,
        ))
        self.assertEqual(recovery["cap"], base["cap"])
        self.assertEqual(recovery["stage_epochs"], base["stage_epochs"])
        self.assertEqual(recovery["stage3_loss_adaptation_id"], base["stage3_loss_adaptation_id"])
        self.assertEqual(recovery["stage3_optimizer_adaptation_id"], base["stage3_optimizer_adaptation_id"])
        self.assertEqual(recovery["min_c_free_gib"], 8.5)
        self.assertEqual(recovery["min_e_free_gib"], base["min_e_free_gib"])

    def test_focal_loss_profile_is_available_to_the_production_cli(self):
        parser = runner._parser()
        parsed = parser.parse_args([
            "--cache-manifest", "cache.json",
            "--source-manifest", "source.json",
            "--environment-manifest", "environment.json",
            "--bulk-root", "bulk",
            "--runtime-root", "runtime",
            "--protocol-output", "protocol.json",
            "--resource-profile", runner.QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID,
        ])
        self.assertEqual(parsed.resource_profile, runner.QUALITY_BALANCED_CAP64_E12_FOCAL_LOSS_PROFILE_ID)

    def test_quality_plan_and_fold_config_bind_profile_storage_thresholds(self):
        """The immutable config must match the thresholds persisted by workers."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            environment = root / "environment.json"
            phase2 = root / "phase2.json"
            cache_manifest = root / "cache.json"
            protocol = root / "protocol.json"
            for path in (source, environment, phase2, cache_manifest, protocol):
                path.write_text("{}", encoding="utf-8")
            label_receipt = root / "label-receipt.json"
            label_receipt.write_text("{}", encoding="utf-8")
            protocol.write_text(json.dumps({"source_code_binding": runner._quality_source_bindings()[0]}), encoding="utf-8")
            profile = runner._resource_profile(SimpleNamespace(
                resource_profile=runner.QUALITY_BALANCED_CAP64_E12_CONSERVATIVE_STAGE3_PROFILE_ID,
                cap=64, epochs=12, subject_count=6,
            ))
            args = SimpleNamespace(
                source_manifest=str(source), environment_manifest=str(environment),
                protocol_output=str(protocol), approved_protocol_sha256=runner.sha256_file(protocol),
                selection_seed=42, model_seed=42, cap=64,
                pilot_subjects=("S1", "S2"), tensorflow_version="2.4.0",
                cache_validation_receipt=None,
                label_evidence_receipt=str(label_receipt), runtime_root=str(root / "runtime"),
                resource_profile=profile["id"], epochs=12, subject_count=6,
            )
            members = tuple(runner.EpochMember("S1", "R1", index) for index in range(5))
            fold = SimpleNamespace(
                fold_index=0, test_subject="S1", validation_subject="S2",
                plan=SimpleNamespace(
                    membership_hashes={"train": "a" * 64},
                    train=members, validation=members, test=members,
                ),
            )
            cache = SimpleNamespace(
                manifest_path=str(cache_manifest), phase2_manifest_path=str(phase2),
                phase2_manifest_hash=runner.sha256_file(phase2), cache_hash="b" * 64,
                entry=lambda member, *_: SimpleNamespace(label=member.epoch_index),
            )
            config = runner._fold_config(cache, fold.plan, args, fold, "quality-plan16-fold01-test-S1")
            self.assertEqual(config["resource_gate_thresholds"]["c_free_gib"], profile["min_c_free_gib"])
            self.assertEqual(config["resource_gate_thresholds"]["e_free_gib"], profile["min_e_free_gib"])

    def test_early_stopped_history_is_bounded_but_plain_history_must_finish(self):
        history = SimpleNamespace(history={"loss": [1.0] * 8, "val_loss": [1.0] * 8})
        spec = {"epochs": 12, "early_stopping": {"monitor": "val_loss"}}
        values = _validate_fit_history(history, spec, 0)
        self.assertEqual(len(values["loss"]), 8)
        with self.assertRaises(TrainingContractError):
            _validate_fit_history(history, {"epochs": 12, "early_stopping": None}, 0)

    def test_verified_label_index_checks_receipt_hash(self):
        root = Path("E:/blp/sleep_stage_reproduction/runtime") if os.name == "nt" else Path("/mnt/e/blp/sleep_stage_reproduction/runtime")
        if not root.is_dir():
            self.skipTest("E bulk runtime is unavailable")
        with tempfile.TemporaryDirectory(prefix="plan16-label-test-", dir=str(root)) as directory:
            directory = Path(directory)
            sidecar = directory / "R1.PAPER_STAGE3_V1.00000000-00000005.json"
            sidecar_value = {
                "record_id": "R1", "subject_id": "S1", "local_epoch_start": 0,
                "labels": [0, 1, 2, 3, 4],
                "config": {"route": {"name": "PAPER_STAGE3_V1"}},
            }
            sidecar.write_text(json.dumps(sidecar_value), encoding="utf-8")
            serialized = str(sidecar)
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({
                "record_bindings": [{"record_id": "R1", "subject_id": "S1", "epochs": 5}],
                "chunks": [{"sidecar": serialized}],
            }), encoding="utf-8")
            receipt = directory / "receipt.json"
            receipt.write_text(json.dumps({
                "receipt_type": "FULL_CACHE_VALIDATION_RECEIPT_V1_PRIOR_EVIDENCE",
                "cache_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "chunks": [{"sidecar": serialized, "sidecar_sha256": hashlib.sha256(sidecar.read_bytes()).hexdigest()}],
            }), encoding="utf-8")
            labels, evidence = load_verified_stage3_labels(manifest, receipt, {"S1"})
            self.assertEqual(len(labels), 5)
            self.assertEqual(evidence["policy"], QUALITY_CAP_POLICY)
            sidecar.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_verified_stage3_labels(manifest, receipt, {"S1"})

    def test_quality_admission_is_create_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol.write_text("{}", encoding="utf-8")
            marker = root / "attempt.lock"
            runner._create_marker(marker)
            args = SimpleNamespace(run_prefix="quality-plan16", protocol_output=str(protocol), approved_protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest())
            profile = {"min_physical_memory_mb": 1024, "min_commit_headroom_mb": 2048}
            checks = {"power_online": True, "critical": False, "physical_memory_available_mb": 4096.0, "commit_headroom_mb": 8192.0, "c_free_gib": 20.0, "e_free_gib": 20.0, "gpu_compute_process_pids": [], "gpu_probe_exit_code": 0}
            binding = {"runner": {"logical_path": "paper_faithful/training/source.py", "sha256": "a" * 64}}
            execution = {"runner": {"path": str(protocol.resolve()), "sha256": "a" * 64}}
            path = runner._persist_quality_admission(
                root, args, profile, 0, "stage1", checks,
                binding, execution, marker,
            )
            self.assertTrue(path.is_file())
            with self.assertRaises(TrainingContractError):
                runner._persist_quality_admission(
                    root, args, profile, 0, "stage1", checks,
                    {}, {}, marker,
                )

    def test_reviewed_source_identity_is_location_independent_and_execution_is_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = []
            for location in (root / "live", root / "snapshot"):
                source_root = location / "paper_faithful" / "training"
                source_root.mkdir(parents=True)
                for filename in runner.QUALITY_SOURCE_FILES.values():
                    (source_root / filename).write_text("# identical\n", encoding="utf-8")
                bindings.append(runner._quality_source_bindings(source_root))
            self.assertEqual(bindings[0][0], bindings[1][0])
            self.assertNotEqual(bindings[0][1], bindings[1][1])
            verifier._verify_quality_source_bindings(*bindings[0])
            verifier._verify_quality_source_bindings(*bindings[1])
            tampered = json.loads(json.dumps(bindings[1][1]))
            tampered["runner"]["sha256"] = "0" * 64
            with self.assertRaises(TrainingContractError):
                verifier._verify_quality_source_bindings(bindings[1][0], tampered)

    def test_quality_runtime_evidence_requires_exact_timestamped_bound_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol.write_text("{}", encoding="utf-8")
            digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
            args = SimpleNamespace(run_prefix="quality-plan16", protocol_output=str(protocol), approved_protocol_sha256=digest)
            profile = {"min_physical_memory_mb": 1024, "min_commit_headroom_mb": 2048}
            thresholds = {"physical_memory_available_mb": 1024, "commit_headroom_mb": 2048, "c_free_gib": runner.MIN_C_FREE_GIB, "e_free_gib": runner.MIN_E_FREE_GIB, "gpu_compute_process_count": 0}
            checks = {"power_online": True, "critical": False, "physical_memory_available_mb": 4096.0, "commit_headroom_mb": 8192.0, "c_free_gib": 20.0, "e_free_gib": 20.0, "gpu_compute_process_pids": [], "gpu_probe_exit_code": 0}
            source = root / "paper_faithful" / "training" / "source.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")
            source_digest = runner.sha256_file(source)
            binding = {"runner": {"logical_path": "paper_faithful/training/source.py", "sha256": source_digest}}
            execution_binding = {"runner": {"path": str(source.resolve()), "sha256": source_digest}}
            config = {
                "run_id": "quality-plan16-fold01-test-S1", "fold_index": 0,
                "subject_protocol_path": str(protocol.resolve()), "subject_protocol_sha256": digest,
                "source_code_binding": binding, "execution_source_binding": execution_binding,
                "resource_gate_thresholds": thresholds,
                "resource_admission_paths": {}, "worker_attempt_marker_paths": {}, "worker_cleanup_paths": {},
            }
            evidence = {}
            for stage in runner.STAGES:
                marker = root / "attempts" / (stage + ".lock")
                runner._create_marker(marker)
                admission = runner._persist_quality_admission(
                    root, args, profile, 0, stage, checks,
                    binding, execution_binding, marker,
                )
                cleanup = runner._persist_quality_cleanup(root, args, 0, stage, marker, admission)
                config["resource_admission_paths"][stage] = str(admission.resolve())
                config["worker_attempt_marker_paths"][stage] = str(marker.resolve())
                config["worker_cleanup_paths"][stage] = str(cleanup.resolve())
                evidence[stage] = {
                    "resource_admission_path": str(admission.resolve()), "resource_admission_sha256": runner.sha256_file(admission),
                    "attempt_marker_path": str(marker.resolve()), "attempt_marker_sha256": runner.sha256_file(marker),
                    "cleanup_path": str(cleanup.resolve()), "cleanup_sha256": runner.sha256_file(cleanup),
                }
            verified = verifier._verify_quality_runtime_evidence(config, {"quality_runtime_evidence": evidence})
            self.assertEqual(len(verified), 9)
            first = Path(config["resource_admission_paths"]["stage1"])
            tampered = json.loads(first.read_text(encoding="utf-8"))
            tampered.pop("observed_at_utc")
            first.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(TrainingContractError, "schema"):
                verifier._verify_quality_runtime_evidence(config, {"quality_runtime_evidence": evidence})

    def test_parent_runtime_verifier_requires_ordered_terminal_workers_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "paper_faithful" / "training" / "source.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n", encoding="utf-8")
            binding = {"runner": {"logical_path": "paper_faithful/training/source.py", "sha256": runner.sha256_file(source)}}
            execution_binding = {"runner": {"path": str(source.resolve()), "sha256": runner.sha256_file(source)}}
            protocol = {
                "run_prefix": "quality-plan16", "pilot_subjects": ["S1"], "source_code_binding": binding,
                "folds": [{"fold_index": 0, "run_id": "quality-plan16-fold01-test-S1", "test_subject": "S1", "validation_subject": "S2"}],
            }
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            resource = root / "resource.json"
            resource.write_text("{}", encoding="utf-8")
            runner._create_marker(root / "quality-plan16.dispatch.lock")
            runner._create_marker(root / "quality-plan16.attempt.lock")
            fold_dir = root / "fold"
            fold_dir.mkdir()
            timestamp = "2026-10-06T00:00:00+00:00"
            events = [
                {"event": "dispatch_created", "run_prefix": "quality-plan16", "resource_evidence_sha256": runner.sha256_file(resource), "timestamp": timestamp},
                {"event": "execution_started", "fold_count": 1, "timestamp": timestamp},
                {"event": "fold_started", "fold_index": 0, "test_subject": "S1", "validation_subject": "S2", "timestamp": timestamp},
            ]
            final = None
            for stage in runner.STAGES:
                stdout = root / (stage + ".stdout")
                stderr = root / (stage + ".stderr")
                cleanup = root / (stage + ".cleanup.json")
                stdout.write_text("ok", encoding="utf-8")
                stderr.write_text("", encoding="utf-8")
                cleanup.write_text("{}", encoding="utf-8")
                result = {
                    "fold_index": 0, "run_id": "quality-plan16-fold01-test-S1", "test_subject": "S1", "validation_subject": "S2",
                    "directory": str(fold_dir.resolve()), "execution_sha256": "e" * 64,
                    "status": "verified" if stage == "stage3" else "stage_completed",
                    "verifier_python": runner.LOCKED_TF24_PYTHON,
                    "cleanup_path": str(cleanup.resolve()), "cleanup_sha256": runner.sha256_file(cleanup),
                }
                if stage != "stage3":
                    result["stage"] = stage
                events.extend([
                    {"event": "stage_started", "fold_index": 0, "stage": stage, "timestamp": timestamp},
                    {"event": "stage_worker_exited", "fold_index": 0, "stage": stage, "returncode": 0,
                     "stdout_path": str(stdout.resolve()), "stdout_sha256": runner.sha256_file(stdout),
                     "stderr_path": str(stderr.resolve()), "stderr_sha256": runner.sha256_file(stderr), "timestamp": timestamp},
                    dict({"event": "stage_completed", "timestamp": timestamp}, **result),
                ])
                if stage == "stage3":
                    final = result
            events.append(dict({"event": "fold_completed", "timestamp": timestamp}, **final))
            (root / "lifecycle.jsonl").write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
            summary = {
                "schema_version": 1, "status": "completed", "protocol_id": "SUBJECT_GENERALIZATION_V1", "model_protocol_id": "PAPER_TEXT_V1",
                "run_prefix": "quality-plan16", "pilot_subjects": ["S1"], "folds": [final], "fold_count": 1,
                "execution_strategy": "fresh_locked_tf24_process_per_stage_per_fold",
                "protocol_path": str(protocol_path.resolve()), "protocol_sha256": runner.sha256_file(protocol_path),
                "source_code_binding": binding, "execution_source_binding": execution_binding,
                "resource_evidence_path": str(resource.resolve()), "resource_evidence_sha256": runner.sha256_file(resource),
            }
            mocked = {"execution_sha256": "e" * 64, "terminal_checkpoint_sha256": "c" * 64}
            with patch.object(verifier, "verify_run_directory", return_value=mocked):
                def verify_parent(path, issue_terminal_validation=False):
                    result = verifier.verify_subject_generalization_runtime(
                        path,
                        require_terminal_artifact=not issue_terminal_validation,
                    )
                    return {"status": "verified", "verification": result}

                with patch.object(runner, "_verify_parent_runtime", side_effect=verify_parent):
                    output = runner._finalize_quality_parent_runtime(
                        root,
                        root / "lifecycle.jsonl",
                        summary,
                    )
                self.assertEqual(output["status"], "terminal_validated")
                result = verifier.verify_subject_generalization_runtime(root)
                self.assertTrue(result["terminal_validated"])
                Path(final["cleanup_path"]).unlink()
                with self.assertRaises(TrainingContractError):
                    verifier.verify_subject_generalization_runtime(root)

    def test_quality_parent_finalization_publishes_completion_before_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lifecycle = root / "lifecycle.jsonl"
            summary = {"folds": [{"fold_index": 0}, {"fold_index": 1}]}
            calls = []

            def record_summary(path, payload):
                calls.append(("summary", Path(path).name, payload))

            def record_event(path, event):
                calls.append((event["event"], event["fold_count"], Path(path).name))

            def record_verification(path, issue_terminal_validation=False):
                calls.append(("verify", issue_terminal_validation, Path(path).name))
                return {"status": "verified", "verification": {"terminal_validated": True}}

            def record_terminal(path, payload):
                calls.append(("terminal", Path(path).name, payload["status"]))

            with patch.object(runner, "_atomic_json", side_effect=record_summary), \
                    patch.object(runner, "_append_event", side_effect=record_event), \
                    patch.object(runner, "_verify_parent_runtime", side_effect=record_verification), \
                    patch.object(runner, "_publish_protocol", side_effect=record_terminal), \
                    patch.object(runner, "sha256_file", return_value="a" * 64):
                output = runner._finalize_quality_parent_runtime(root, lifecycle, summary)

            self.assertEqual(
                [item[0] for item in calls],
                ["summary", "pilot_completed", "verify", "terminal", "verify"],
            )
            self.assertEqual(calls[1][1], 2)
            self.assertTrue(calls[2][1])
            self.assertFalse(calls[4][1])
            self.assertEqual(output["status"], "terminal_validated")
            self.assertEqual(output["terminal_validation_sha256"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
