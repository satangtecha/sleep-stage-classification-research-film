"""Synthetic regression tests: no GPU, canonical tensor scan or training."""
import copy
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paper_faithful.training.run_manifest import sha256_file
from paper_faithful.training.splits import EpochMember, validate_no_leakage
from paper_faithful.training.subject_generalization import sample_record_members, canonical_json
from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training import trainer
from paper_faithful.training.verify_run import _verify_subject_protocol


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        # Record ordering intentionally differs from subject ordering.
        self.records = (("Z1", "S1", 500), ("A1", "S2", 600), ("Z2", "S1", 500),
                        ("B1", "S3", 700), ("C1", "S4", 800))
        self.manifest = self.root / "cache.json"
        self.manifest.write_text(json.dumps({"record_bindings": [
            {"record_id": record, "subject_id": subject, "epochs": epochs}
            for record, subject, epochs in self.records]}), encoding="utf-8")
        for name in ("source", "environment"):
            (self.root / (name + ".json")).write_text("{}", encoding="utf-8")
        self.args = SimpleNamespace(cache_manifest=str(self.manifest),
            source_manifest=str(self.root / "source.json"), environment_manifest=str(self.root / "environment.json"),
            run_prefix="subject-recovery-test", selection_seed=42, model_seed=42, subject_count=3,
            cap=128, protocol_output=str(self.root / "protocol.json"), plan_only=True,
            bulk_root=str(self.root / "bulk"), runtime_root=str(self.root / "runtime"), resource_evidence=None)

    def resource(self):
        return {"status": "pass", "ready": True, "protocol_id": "SUBJECT_GENERALIZATION_V1",
                "timestamp": datetime.now(timezone.utc).isoformat(), "checks": {
                    "power_online": True, "critical": False, "physical_memory_available_mb": 5000,
                    "commit_headroom_mb": 9000, "c_free_gib": 20, "e_free_gib": 30,
                    "windows_gpu_compute_process_count": 0, "wsl_gpu_compute_process_count": 0,
                    "windows_gpu_probe_exit_code": 0, "wsl_gpu_probe_exit_code": 0}}

    def write_resource(self, value):
        path = self.root / "resource.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def approve_plan(self):
        planned = runner._build_light_plan(self.args)
        runner._publish_protocol(Path(self.args.protocol_output), planned)
        self.args.approved_protocol_sha256 = sha256_file(self.args.protocol_output)
        self.args.resource_evidence = str(self.write_resource(self.resource()))
        return planned

    def test_sampling_reproducible_across_record_order_and_spans_time(self):
        result = sample_record_members(self.records, {"S1", "S2"}, 128, 42)
        self.assertEqual(result, sample_record_members(tuple(reversed(self.records)), {"S2", "S1"}, 128, 42))
        self.assertNotEqual(result, sample_record_members(self.records, {"S1", "S2"}, 128, 43))
        self.assertEqual(len(set(result)), 128)
        self.assertEqual(sum(item.subject_id == "S1" for item in result), 64)
        self.assertEqual({item.record_id for item in result if item.subject_id == "S1"}, {"Z1", "Z2"})
        self.assertTrue(any(item.epoch_index > 128 for item in result))

    def test_sampling_invalid_and_oversized_inputs(self):
        self.assertEqual(len(sample_record_members(self.records, {"S1"}, 1100, 42)), 1000)
        for cap, seed in ((0, 42), (True, 42), (128, True), (128, -1)):
            with self.subTest(cap=cap, seed=seed), self.assertRaises(ValueError):
                sample_record_members(self.records, {"S1"}, cap, seed)
        with self.assertRaises(ValueError):
            sample_record_members(self.records + (self.records[0],), {"S1"}, 128, 42)
        with self.assertRaises(ValueError):
            sample_record_members(self.records, {"missing"}, 128, 42)

    def test_plan_and_execution_exactly_match_without_full_fold_retention(self):
        planned = self.approve_plan()
        self.args.plan_only = False
        all_members = tuple(EpochMember(subject, record, epoch) for record, subject, count in self.records for epoch in range(count))
        cache = SimpleNamespace(members=all_members)
        with patch.object(runner, "load_canonical_cache", return_value=cache):
            executed, folds, actual_cache = runner.build_plan(self.args)
        self.assertEqual(canonical_json(planned), canonical_json(executed))
        self.assertIs(actual_cache, cache)
        for fold, entry in zip(folds, planned["folds"]):
            self.assertEqual(fold.plan.membership_hashes, entry["split_membership_hashes"])
            self.assertEqual(len(fold.plan.train), 128)
            validate_no_leakage(fold.plan, require_subject_disjoint=True)

    def test_unapproved_plan_fails_before_tensor_loading(self):
        self.approve_plan()
        self.args.plan_only = False
        self.args.model_seed = 43
        with patch.object(runner, "load_canonical_cache") as loader:
            with self.assertRaisesRegex(trainer.TrainingContractError, "reviewed protocol differs"):
                runner.build_plan(self.args)
            loader.assert_not_called()

    def test_protocol_file_is_not_overwritten(self):
        original = self.approve_plan()
        with self.assertRaises(trainer.TrainingContractError):
            runner._publish_protocol(Path(self.args.protocol_output), {"changed": True})
        self.assertEqual(Path(self.args.protocol_output).read_text(encoding="utf-8"), canonical_json(original))

    def test_valid_resource_and_stale_future_or_naive_timestamps(self):
        value = self.resource()
        self.assertEqual(runner._load_resource_evidence(self.write_resource(value)), value)
        now = datetime.now(timezone.utc)
        seven_digit = dict(value, timestamp=now.strftime("%Y-%m-%dT%H:%M:%S.%f7+00:00"))
        self.assertEqual(runner._load_resource_evidence(self.write_resource(seven_digit)), seven_digit)
        for stamp in ((now-timedelta(seconds=121)).isoformat(), (now+timedelta(seconds=1)).isoformat(),
                      now.replace(tzinfo=None).isoformat(), "garbage"):
            bad = dict(value, timestamp=stamp)
            with self.subTest(stamp=stamp), self.assertRaises(trainer.TrainingContractError):
                runner._load_resource_evidence(self.write_resource(bad), now=now)

    def test_resource_numeric_and_probe_failures_are_not_idle(self):
        for key, invalid in (("physical_memory_available_mb", float("nan")), ("commit_headroom_mb", float("inf")),
                             ("windows_gpu_probe_exit_code", 1), ("wsl_gpu_probe_exit_code", None),
                             ("wsl_gpu_compute_process_count", False), ("power_online", False)):
            value = self.resource()
            value["checks"][key] = invalid
            with self.subTest(key=key), self.assertRaises(trainer.TrainingContractError):
                runner._load_resource_evidence(self.write_resource(value))

    def test_bad_resources_refused_before_build_plan_and_markers(self):
        self.args.plan_only = False
        value = self.resource()
        value["checks"]["physical_memory_available_mb"] = 100
        self.args.resource_evidence = str(self.write_resource(value))
        with patch.object(runner, "require_bulk_path", side_effect=Path), patch.object(runner, "build_plan") as build:
            with self.assertRaises(trainer.TrainingContractError):
                runner.run(self.args)
            build.assert_not_called()
        self.assertFalse(Path(self.args.runtime_root).exists())

    def test_receipt_expiry_during_runtime_import_refuses_cache_loading(self):
        self.approve_plan()
        self.args.plan_only = False
        self.args.runtime_root = str(Path(self.args.bulk_root)/"runtime"/self.args.run_prefix)
        def slow_import():
            expired = self.resource()
            expired["timestamp"] = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
            self.write_resource(expired)
            return "2.4.0"
        with patch.object(runner, "require_bulk_path", side_effect=Path), \
             patch.object(runner, "run_directory", side_effect=lambda run_id, bulk_root: Path(bulk_root)/"runs"/run_id), \
             patch.object(runner, "_probe_live_capacity", return_value={}), \
             patch.object(runner, "_require_locked_tf24_runtime", side_effect=slow_import), \
             patch.object(runner, "load_canonical_cache") as loader:
            with self.assertRaisesRegex(trainer.TrainingContractError, "stale"):
                runner.run(self.args)
            loader.assert_not_called()
        self.assertFalse(Path(self.args.runtime_root).exists())

    def test_setup_failure_is_recorded_without_touching_existing_namespace(self):
        root = self.root / "new-runtime"
        resource = self.write_resource(self.resource())
        original = runner._create_marker
        def fail_second_marker(path):
            if path.name.endswith(".attempt.lock"):
                raise OSError("injected marker write failure")
            original(path)
        with patch.object(runner, "_create_marker", side_effect=fail_second_marker):
            with self.assertRaisesRegex(trainer.TrainingContractError, "namespace consumed"):
                runner._initialize_runtime(root, "fresh", {}, resource)
        failure = json.loads((root/"failure.json").read_text())
        self.assertEqual(failure["phase"], "pre_dispatch_setup")
        self.assertTrue(failure["namespace_consumed"])
        self.assertFalse((root/"fresh.attempt.lock").exists())
        before = (root/"failure.json").read_bytes()
        with self.assertRaises(FileExistsError):
            runner._initialize_runtime(root, "fresh", {}, resource)
        self.assertEqual((root/"failure.json").read_bytes(), before)

    def test_verifier_reconstructs_fold_and_rejects_misbound_split(self):
        protocol = self.approve_plan()
        entry = protocol["folds"][0]
        config = {"subject_protocol_path": self.args.protocol_output,
                  "subject_protocol_sha256": self.args.approved_protocol_sha256,
                  "cache_manifest": self.args.cache_manifest, "source_manifest": self.args.source_manifest,
                  "environment_manifest": self.args.environment_manifest, "seed": 42, "model_seed": 42,
                  "per_split_epoch_cap": 128, "fold_index": 0, "run_id": entry["run_id"],
                  "test_subject": entry["test_subject"], "validation_subject": entry["validation_subject"],
                  "split_hashes": entry["split_membership_hashes"], "cap_policy": protocol["cap_policy"],
                  "pilot_subjects": protocol["pilot_subjects"],
                  "split_epoch_counts": {name: entry[name + "_epoch_count"] for name in ("train", "validation", "test")}}
        _verify_subject_protocol(config)
        wrong = copy.deepcopy(config)
        wrong["split_hashes"]["train"] = "0"*64
        with self.assertRaises(trainer.TrainingContractError):
            _verify_subject_protocol(wrong)

    def test_collision_never_marks_another_callers_execution_failed(self):
        self.approve_plan()
        self.args.plan_only = False
        self.args.runtime_root = str(Path(self.args.bulk_root) / "runtime" / self.args.run_prefix)
        self.args.resource_evidence = str(self.write_resource(self.resource()))
        cache = SimpleNamespace(members=tuple(EpochMember(subject, record, epoch)
            for record, subject, count in self.records for epoch in range(count)))
        peer_paths = []
        def collide(run_id, config, bulk_root):
            directory = Path(bulk_root) / "runs" / run_id
            directory.mkdir(parents=True)
            path = directory / "execution.json"
            path.write_text('{"status":"running","owner":"other"}', encoding="utf-8")
            peer_paths.append(path)
            raise trainer.TrainingContractError("run exists; explicit resume required")
        with patch.object(runner, "require_bulk_path", side_effect=Path), \
             patch.object(runner, "run_directory", side_effect=lambda run_id, bulk_root: Path(bulk_root)/"runs"/run_id), \
             patch.object(runner, "_probe_live_capacity", return_value={}), \
             patch.object(runner, "_require_locked_tf24_runtime", return_value="2.4.0"), \
             patch.object(runner, "load_canonical_cache", return_value=cache), \
             patch.object(runner, "seed_model", return_value=object()), \
             patch.object(runner, "cleanup_model_state"), \
             patch.object(runner, "_fold_config", return_value={}), \
             patch.object(runner, "prepare_run", side_effect=collide), \
             patch.dict(os.environ, {"PAPER_FAITHFUL_SUBJECT_RUN_PREFIX": "previous-value"}):
            self.assertEqual(runner.run(self.args), 2)
            self.assertEqual(os.environ["PAPER_FAITHFUL_SUBJECT_RUN_PREFIX"], "previous-value")
        self.assertEqual(len(peer_paths), 1)
        self.assertEqual(json.loads(peer_paths[0].read_text()), {"status": "running", "owner": "other"})
        failure = json.loads((Path(self.args.runtime_root)/"failure.json").read_text())
        self.assertEqual(failure["completed_folds"], [])


class FakeTF:
    __version__ = "2.4.0"
    config = SimpleNamespace(list_physical_devices=lambda kind: [object()])
    @contextmanager
    def device(self, name):
        yield
    def constant(self, value):
        return SimpleNamespace(device="/device:GPU:0", numpy=lambda: 0.0)
    def ones(self, shape, dtype=None):
        return SimpleNamespace(device="/device:GPU:0", numpy=lambda: [1.0])


class SubjectAdmissionTests(unittest.TestCase):
    def test_own_gpu_process_allowed_but_peer_and_probe_failures_rejected(self):
        for output, code, succeeds in ((str(os.getpid())+", python, 500\n", 0, True), ("", 0, True),
                                      (str(os.getpid()+1)+", python, 500", 0, False), ("", 1, False), ("N/A, python, 500", 0, False)):
            with self.subTest(output=output, code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run_dir = root / "new-subject-prefix-fold01-test-S1"
                run_dir.mkdir()
                (run_dir / "execution.json").write_text(json.dumps({"config": {"evaluation_protocol_id": "SUBJECT_GENERALIZATION_V1"}}))
                environment = {"PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION": "1", "PAPER_FAITHFUL_SUBJECT_RUN_PREFIX": "new-subject-prefix",
                               "PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT": str(root / "admission")}
                with patch.dict(os.environ, environment), patch.object(trainer.subprocess, "run", return_value=SimpleNamespace(stdout=output, returncode=code)):
                    if succeeds:
                        trainer._subject_generalization_gpu_admission(FakeTF(), run_dir, "stage1")
                        self.assertTrue((root / "admission" / (run_dir.name+".stage1.json")).is_file())
                    else:
                        with self.assertRaises(trainer.TrainingContractError):
                            trainer._subject_generalization_gpu_admission(FakeTF(), run_dir, "stage1")

    def test_subject_identity_cannot_disable_admission_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "execution.json").write_text(json.dumps({"config": {"evaluation_protocol_id": "SUBJECT_GENERALIZATION_V1"}}))
            with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(trainer.TrainingContractError, "environment is required"):
                trainer._subject_generalization_gpu_admission(None, root, "stage1")


if __name__ == "__main__":
    unittest.main()
