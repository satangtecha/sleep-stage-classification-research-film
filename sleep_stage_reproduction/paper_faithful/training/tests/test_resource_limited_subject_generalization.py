import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training.trainer import TrainingContractError, stage_spec


class ResourceLimitedSubjectGeneralizationTests(unittest.TestCase):
    def _args(self, root):
        cache = root / "cache.json"
        cache.write_text(json.dumps({
            "record_bindings": [
                {"record_id": f"R{i}", "subject_id": f"S{i}", "epochs": 40}
                for i in range(6)
            ]
        }), encoding="utf-8")
        source = root / "source.json"
        environment = root / "environment.json"
        source.write_text("{}", encoding="utf-8")
        environment.write_text("{}", encoding="utf-8")
        return SimpleNamespace(
            cache_manifest=str(cache),
            source_manifest=str(source),
            environment_manifest=str(environment),
            run_prefix="subject-generalization-resource-limited-v1-cap32-e6-20261004",
            selection_seed=42,
            model_seed=42,
            subject_count=6,
            cap=32,
            resource_profile=runner.RESOURCE_LIMITED_PROFILE_ID,
            epochs=6,
        )

    def test_profile_binds_cap32_and_six_epochs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            plan = runner._build_light_plan(args)
            self.assertEqual(plan["resource_profile"], runner.RESOURCE_LIMITED_PROFILE_ID)
            self.assertEqual(plan["stage_epochs"], 6)
            self.assertEqual(plan["cap"], 32)
            self.assertTrue(all(spec["epochs"] == 6 for spec in plan["stage_specs"].values()))
            self.assertEqual(len(plan["folds"]), 6)
            self.assertTrue(all(fold["train_epoch_count"] >= 128 for fold in plan["folds"]))
            self.assertTrue(all(fold["validation_epoch_count"] == 32 for fold in plan["folds"]))
            self.assertTrue(all(fold["test_epoch_count"] == 32 for fold in plan["folds"]))

    def test_training_stays_inside_selected_six_subject_pilot(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            cache_path = Path(args.cache_manifest)
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            payload["record_bindings"].extend(
                {"record_id": f"EXTRA_R{i}", "subject_id": f"EXTRA_S{i}", "epochs": 40}
                for i in range(40)
            )
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            plan = runner._build_light_plan(args)

            self.assertEqual(len(plan["pilot_subjects"]), 6)
            self.assertTrue(all(fold["train_subject_count"] == 4 for fold in plan["folds"]))
            self.assertTrue(all(fold["capped_train_subject_count"] == 4 for fold in plan["folds"]))
            self.assertTrue(all(fold["train_epoch_count"] == 128 for fold in plan["folds"]))

    def test_profile_rejects_wrong_cap_or_epoch_count(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.cap = 128
            with self.assertRaisesRegex(TrainingContractError, "cap32"):
                runner._build_light_plan(args)
            args.cap = 32
            args.epochs = 20
            with self.assertRaisesRegex(TrainingContractError, "cap32"):
                runner._build_light_plan(args)

    def test_ultra_compact_profile_is_explicitly_lower_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_ULTRA_COMPACT_OFFLINE_PROFILE_ID
            plan = runner._build_light_plan(args)
            self.assertEqual(plan["resource_gate_thresholds"]["physical_memory_available_mb"], 2048)
            self.assertEqual(plan["resource_gate_thresholds"]["commit_headroom_mb"], 4096)
            self.assertTrue(plan["offline_power_authorized"])

    def test_compact_profile_explicitly_selects_cache_subset(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertTrue(profile["compact_cache"])
            self.assertEqual(profile["min_physical_memory_mb"], 2048)
            self.assertEqual(profile["min_commit_headroom_mb"], 4096)
            self.assertEqual(plan["resource_profile"], runner.RESOURCE_LIMITED_COMPACT_OFFLINE_PROFILE_ID)

    def test_low_headroom_compact_profile_is_separately_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_COMPACT_LOW_HEADROOM_PROFILE_ID
            profile = runner._resource_profile(args)
            self.assertTrue(profile["compact_cache"])
            self.assertEqual(profile["min_physical_memory_mb"], 1536)
            self.assertEqual(profile["min_commit_headroom_mb"], 3072)
            self.assertTrue(profile["allow_offline_power"])

    def test_low_compute_profile_records_stage1_accumulation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_COMPACT_LOW_COMPUTE_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertEqual(profile["stage1_microbatch"], 32)
            self.assertEqual(profile["stage2_microbatch"], 128)
            self.assertEqual(plan["stage_specs"]["stage1"]["effective_batch"], 128)
            self.assertEqual(plan["stage_specs"]["stage1"]["gradient_accumulation_steps"], 4)
            self.assertEqual(plan["stage_specs"]["stage2"]["microbatch"], 128)

    def test_detached_gpu_profile_preserves_low_compute_and_thresholds(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertEqual(profile["min_physical_memory_mb"], 1024)
            self.assertEqual(profile["min_commit_headroom_mb"], 2048)
            self.assertEqual(profile["stage1_microbatch"], 16)
            self.assertEqual(profile["stage2_microbatch"], 128)
            self.assertEqual(plan["stage_specs"]["stage1"]["effective_batch"], 128)
            self.assertEqual(plan["stage_specs"]["stage1"]["gradient_accumulation_steps"], 8)
            self.assertEqual(plan["resource_profile"], runner.RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID)

    def test_fresh_stage_profile_resets_tensorflow_between_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_FRESH_STAGE_PROCESS_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertTrue(profile["fresh_process_per_stage"])
            self.assertTrue(profile["fresh_process_per_fold"])
            self.assertEqual(plan["execution_strategy"], "fresh_locked_tf24_process_per_stage_per_fold")
            self.assertTrue(plan["fresh_process_per_stage"])
            self.assertEqual(profile["stage1_microbatch"], 16)
            self.assertEqual(profile["stage2_microbatch"], 128)
            self.assertEqual(profile["stage3_microbatch"], 1)
            self.assertEqual(plan["stage_specs"]["stage1"]["gradient_accumulation_steps"], 8)

    def test_micro_stage_profile_lowers_cap_and_stage1_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.cap = 16
            args.resource_profile = runner.RESOURCE_LIMITED_MICRO_STAGE_PROCESS_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertEqual(profile["cap"], 16)
            self.assertEqual(profile["stage1_microbatch"], 8)
            self.assertEqual(profile["stage2_microbatch"], 128)
            self.assertEqual(profile["stage3_microbatch"], 1)
            self.assertEqual(plan["cap"], 16)
            self.assertEqual(plan["stage_specs"]["stage1"]["gradient_accumulation_steps"], 16)
            self.assertTrue(profile["fresh_process_per_stage"])
            self.assertEqual(plan["execution_strategy"], "fresh_locked_tf24_process_per_stage_per_fold")

    def test_ultra_micro_stage_profile_keeps_cap32_and_lowers_stage1_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_ULTRA_MICRO_STAGE_PROCESS_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertEqual(profile["cap"], 32)
            self.assertEqual(profile["stage1_microbatch"], 8)
            self.assertEqual(profile["stage2_microbatch"], 128)
            self.assertEqual(profile["stage3_microbatch"], 1)
            self.assertEqual(plan["cap"], 32)
            self.assertEqual(plan["stage_specs"]["stage1"]["gradient_accumulation_steps"], 16)
            self.assertEqual(plan["stage_specs"]["stage1"]["effective_batch"], 128)
            self.assertEqual(plan["stage_specs"]["stage2"]["microbatch"], 128)

    def test_wait_drain_profile_records_bounded_memory_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self._args(Path(directory))
            args.resource_profile = runner.RESOURCE_LIMITED_WAIT_DRAIN_STAGE_PROCESS_PROFILE_ID
            profile = runner._resource_profile(args)
            plan = runner._build_light_plan(args)
            self.assertTrue(profile["fresh_process_per_stage"])
            self.assertEqual(profile["capacity_wait_seconds"], 120)
            self.assertEqual(profile["capacity_poll_seconds"], 5)
            self.assertEqual(plan["capacity_wait_strategy"], "drain_after_previous_stage_exit")

    def test_wait_drain_rechecks_only_transient_memory_failure(self):
        transient = TrainingContractError(
            "live host capacity gate failed: physical_memory_available_mb gate failed"
        )
        with patch.object(runner, "_probe_live_capacity", side_effect=[transient, {"ok": True}]) as probe, \
             patch.object(runner.time, "sleep") as sleep:
            result = runner._probe_live_capacity_with_wait(wait_seconds=120, poll_seconds=5)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(probe.call_count, 2)
        sleep.assert_called_once()

    def test_wait_drain_does_not_delay_non_memory_failure(self):
        failure = TrainingContractError("live host capacity gate failed: AC power unavailable")
        with patch.object(runner, "_probe_live_capacity", side_effect=failure) as probe, \
             patch.object(runner.time, "sleep") as sleep:
            with self.assertRaisesRegex(TrainingContractError, "AC power"):
                runner._probe_live_capacity_with_wait(wait_seconds=120, poll_seconds=5)
        probe.assert_called_once()
        sleep.assert_not_called()

    def test_stage_spec_override_is_not_paper_exact(self):
        spec = stage_spec("PAPER_TEXT_V1", "stage1", microbatch=128, weight_decay=0.0, epochs_override=6)
        self.assertEqual(spec["epochs"], 6)
        self.assertFalse(spec["paper_exact"])

    def test_lower_resource_profile_threshold_is_explicit(self):
        evidence = {
            "status": "pass",
            "ready": True,
            "protocol_id": "SUBJECT_GENERALIZATION_V1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "power_online": True,
                "critical": False,
                "physical_memory_available_mb": 3500,
                "commit_headroom_mb": 6500,
                "c_free_gib": 20,
                "e_free_gib": 20,
                "windows_gpu_compute_process_count": 0,
                "wsl_gpu_compute_process_count": 0,
                "windows_gpu_probe_exit_code": 0,
                "wsl_gpu_probe_exit_code": 0,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resource.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            self.assertEqual(
                runner._load_resource_evidence(
                    path,
                    min_physical_memory_mb=runner.RESOURCE_LIMITED_MIN_PHYSICAL_MEMORY_MB,
                    min_commit_headroom_mb=runner.RESOURCE_LIMITED_MIN_COMMIT_HEADROOM_MB,
                )["status"],
                "pass",
            )
            with self.assertRaises(TrainingContractError):
                runner._load_resource_evidence(
                    path,
                    min_physical_memory_mb=4096,
                    min_commit_headroom_mb=8192,
                )

    def test_offline_profile_requires_explicit_authorization(self):
        evidence = {
            "status": "pass",
            "ready": True,
            "protocol_id": "SUBJECT_GENERALIZATION_V1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "power_online": False,
                "critical": True,
                "offline_power_authorized": True,
                "physical_memory_available_mb": 3500,
                "commit_headroom_mb": 6500,
                "c_free_gib": 20,
                "e_free_gib": 20,
                "windows_gpu_compute_process_count": 0,
                "wsl_gpu_compute_process_count": 0,
                "windows_gpu_probe_exit_code": 0,
                "wsl_gpu_probe_exit_code": 0,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "offline-resource.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaises(TrainingContractError):
                runner._load_resource_evidence(
                    path,
                    min_physical_memory_mb=3072,
                    min_commit_headroom_mb=6144,
                )
            self.assertEqual(
                runner._load_resource_evidence(
                    path,
                    min_physical_memory_mb=3072,
                    min_commit_headroom_mb=6144,
                    allow_offline_power=True,
                )["status"],
                "pass",
            )


if __name__ == "__main__":
    unittest.main()
