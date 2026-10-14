import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_faithful.training.metrics import classification_metrics, silhouette_metric, write_metrics_artifact
from paper_faithful.training.trainer import (
    STAGES,
    TrainingContractError,
    prepare_run,
    transition_run,
)
from paper_faithful.training.verify_run import _provenance_path, verify_run_directory


class VerifyRunTests(unittest.TestCase):
    _R8_EXECUTION = Path(
        "/mnt/e/blp/sleep_stage_reproduction/runs/"
        "paper-text-v1-pilot-cap128-seed42-r8-20260827/execution.json"
    )

    def _source(self, root, name, payload):
        path = root / name
        path.write_bytes(payload)
        return str(path.resolve()), hashlib.sha256(payload).hexdigest()

    def _completed_run(self, root):
        source, source_hash = self._source(root, "source.json", b"source")
        environment, environment_hash = self._source(root, "environment.json", b"environment")
        phase2, phase2_hash = self._source(root, "phase2.json", b"phase2")
        cache, cache_hash = self._source(root, "cache.json", b"cache")
        split_hashes = {"train": "a" * 64, "validation": "b" * 64, "test": "c" * 64}
        config = {
            "protocol_id": "PAPER_TEXT_V1",
            "source_manifest": source,
            "source_manifest_hash": source_hash,
            "environment_manifest": environment,
            "environment_manifest_hash": environment_hash,
            "data_manifest": phase2,
            "data_manifest_hash": phase2_hash,
            "cache_manifest": cache,
            "cache_manifest_hash": cache_hash,
            "cache_hash": cache_hash,
            "phase2_manifest": phase2,
            "split_hashes": split_hashes,
            "seed": 42,
            "mode": "pilot",
            "stage": "all",
        }
        run_dir = root / "run"
        with patch("paper_faithful.training.trainer.run_directory", return_value=run_dir):
            directory, record = prepare_run("run", config, bulk_root=root)
        record = transition_run(directory, record, "running")
        artifacts = {}
        parent = None
        for stage in STAGES:
            route = "PAPER_STAGE3_V1" if stage == "stage3" else "PAPER_PRETRAIN_V1"
            checkpoint = run_dir / (stage + ".weights.h5")
            checkpoint.write_bytes(stage.encode())
            checkpoint_hash = hashlib.sha256(stage.encode()).hexdigest()
            metrics_path = run_dir / (stage + ".metrics.json")
            split_metrics = {}
            for split in ("validation", "test"):
                if stage == "stage2":
                    result = {
                        "silhouette": silhouette_metric([[0], [1], [2], [3]], [0, 0, 1, 1]),
                        "scope": {
                            "split": split,
                            "base_epoch_membership_hash": split_hashes[split],
                            "split_sample_count": 4,
                            "evaluated_sample_count": 4,
                            "evaluation_mode": "deterministic_uniform_reservoir",
                            "reservoir_seed": 42,
                            "reservoir_cap": 4096,
                        },
                    }
                else:
                    result = {
                        "classification": classification_metrics([0, 1, 2, 3, 4], [0, 1, 2, 3, 4]),
                        "scope": {
                            "split": split,
                            "base_epoch_membership_hash": split_hashes[split],
                            "split_sample_count": 5,
                            "evaluated_sample_count": 5,
                            "evaluation_mode": "complete_split",
                        },
                    }
                split_metrics[split] = result
            metrics = write_metrics_artifact(
                metrics_path,
                split_metrics,
                {
                    "schema_version": 1,
                    "protocol_id": "PAPER_TEXT_V1",
                    "stage": stage,
                    "route": route,
                    "cache_hash": cache_hash,
                    "checkpoint_path": str(checkpoint),
                    "checkpoint_sha256": checkpoint_hash,
                    "split_membership_hashes": split_hashes,
                    "initial_epoch": 0,
                    "stage_spec": ({"stage": stage, "learning_rate": 0.1, "nominal_batch": 128, "microbatch": 1, "effective_batch": 128, "gradient_accumulation_steps": 128, "gradient_clip_norm": 1.0, "gradient_clip_application": "after_effective_batch_average_before_optimizer_step", "stage3_stability_adaptation_id": "PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1"} if stage == "stage3" else {"stage": stage}),
                },
            )
            artifacts[stage] = {
                "checkpoint_path": str(checkpoint),
                "checkpoint_hash": checkpoint_hash,
                "parent_checkpoint_path": None if parent is None else parent["checkpoint_path"],
                "parent_checkpoint_hash": None if parent is None else parent["checkpoint_hash"],
                "route": route,
                "metrics_path": str(metrics_path),
                "metrics_file_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
                "metrics_artifact_sha256": metrics["artifact_sha256"],
            }
            parent = {
                "checkpoint_path": str(checkpoint),
                "checkpoint_hash": checkpoint_hash,
                "cache_hash": cache_hash,
                "protocol_id": "PAPER_TEXT_V1",
                "stage": stage,
                "route": route,
            }
            next_stage = STAGES[STAGES.index(stage) + 1] if stage != "stage3" else None
            record = transition_run(
                directory,
                record,
                "running",
                checkpoint_path=str(checkpoint),
                checkpoint_hash=checkpoint_hash,
                stage_artifacts=dict(artifacts),
                stage_progress={"next_stage": next_stage, "last_epoch": 0, "checkpoint": parent, "inflight": False},
            )
        transition_run(directory, record, "completed")
        return run_dir, Path(source), Path(artifacts["stage3"]["metrics_path"])

    def test_completed_run_verifies_all_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, _, _ = self._completed_run(Path(temporary))
            result = verify_run_directory(run_dir)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["verified_stages"], list(STAGES))
            self.assertEqual(result["terminal_checkpoint_sha256"], hashlib.sha256(b"stage3").hexdigest())

    def test_unsafe_provenance_paths_are_refused(self):
        unsafe = ("relative.json", r"E:relative.json", r"\\server\share\manifest.json", r"C:\manifest.json", r"E:\..\manifest.json")
        for value in unsafe:
            with self.subTest(value=value):
                with self.assertRaises(TrainingContractError):
                    _provenance_path(value)

    @unittest.skipUnless(
        os.name != "nt" and os.access("/mnt/e", os.W_OK),
        "requires a writable WSL /mnt/e mount",
    )
    def test_wsl_e_drive_manifest_path_verifies(self):
        with tempfile.TemporaryDirectory(dir="/mnt/e") as temporary:
            root = Path(temporary)
            run_dir, _, _ = self._completed_run(root)
            execution_path = run_dir / "execution.json"
            execution = json.loads(execution_path.read_text())
            phase2_path = Path(execution["config"]["data_manifest"])
            windows_phase2 = "E:\\" + str(phase2_path.relative_to("/mnt/e")).replace("/", "\\")
            execution["config"]["data_manifest"] = windows_phase2
            execution["config"]["phase2_manifest"] = windows_phase2
            from paper_faithful.training.trainer import _hash

            execution["immutable_config_hash"] = _hash(execution["config"])
            execution_path.write_text(json.dumps(execution, sort_keys=True, indent=2) + "\n")
            self.assertEqual(verify_run_directory(run_dir)["status"], "completed")

    @unittest.skipUnless(os.name != "nt", "requires WSL")
    def test_wsl_unsafe_windows_provenance_syntax_is_refused(self):
        unsafe = (r"\\?\E:\device\manifest.json", r"\\server\share\manifest.json", r"C:\manifest.json")
        for value in unsafe:
            with self.subTest(value=value):
                with self.assertRaises(TrainingContractError):
                    _provenance_path(value)
        with self.assertRaises(TrainingContractError):
            _provenance_path(r"E:\blp\sleep_stage_reproduction\__missing_verify_run_manifest__.json")

    @unittest.skipUnless(
        os.name != "nt" and _R8_EXECUTION.is_file(),
        "requires the mounted r8 execution record",
    )
    def test_wsl_translated_manifest_hash_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, _, _ = self._completed_run(Path(temporary))
            execution_path = run_dir / "execution.json"
            execution = json.loads(execution_path.read_text())
            manifest = json.loads(self._R8_EXECUTION.read_text())["config"]["data_manifest"]
            execution["config"]["data_manifest"] = manifest
            execution["config"]["phase2_manifest"] = manifest
            execution["config"]["data_manifest_hash"] = "0" * 64
            from paper_faithful.training.trainer import _hash

            execution["immutable_config_hash"] = _hash(execution["config"])
            execution_path.write_text(json.dumps(execution, sort_keys=True, indent=2) + "\n")
            with self.assertRaisesRegex(TrainingContractError, "data_manifest provenance hash failed"):
                verify_run_directory(run_dir)

    @unittest.skipUnless(
        os.name != "nt" and os.access("/mnt/e", os.W_OK),
        "requires a writable WSL /mnt/e mount",
    )
    def test_wsl_translated_symlink_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(dir="/mnt/e") as mounted:
            target = Path(outside) / "manifest.json"
            target.write_text("outside")
            link = Path(mounted) / "escape"
            link.symlink_to(outside, target_is_directory=True)
            windows_path = "E:\\" + str((link / target.name).relative_to("/mnt/e")).replace("/", "\\")
            with self.assertRaises(TrainingContractError):
                _provenance_path(windows_path)

    def test_source_or_metric_tampering_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, source, metric = self._completed_run(root)
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(TrainingContractError, "source_manifest provenance hash failed"):
                verify_run_directory(run_dir)
            source.write_bytes(b"source")
            payload = json.loads(metric.read_text())
            payload["metrics"]["validation"]["forged_accuracy"] = 1.0
            metric.write_text(json.dumps(payload))
            with self.assertRaisesRegex(TrainingContractError, "metric-file hash failed"):
                verify_run_directory(run_dir)

    def test_self_consistent_empty_metric_artifact_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, _, metric = self._completed_run(Path(temporary))
            payload = json.loads(metric.read_text())
            payload["metrics"] = {"validation": {}, "test": {}}
            canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            payload["metrics_sha256"] = canonical(payload["metrics"])
            payload["artifact_sha256"] = canonical({"metrics": payload["metrics"], "provenance": payload["provenance"]})
            metric.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            execution_path = run_dir / "execution.json"
            execution = json.loads(execution_path.read_text())
            execution["stage_artifacts"]["stage3"]["metrics_file_sha256"] = hashlib.sha256(metric.read_bytes()).hexdigest()
            execution["stage_artifacts"]["stage3"]["metrics_artifact_sha256"] = payload["artifact_sha256"]
            execution_path.write_text(json.dumps(execution, sort_keys=True, indent=2) + "\n")
            with self.assertRaisesRegex(TrainingContractError, "stage metric result is missing"):
                verify_run_directory(run_dir)

    def test_standalone_external_parent_metadata_is_rehashed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, source_hash = self._source(root, "source.json", b"source")
            environment, environment_hash = self._source(root, "environment.json", b"environment")
            phase2, phase2_hash = self._source(root, "phase2.json", b"phase2")
            cache, cache_hash = self._source(root, "cache.json", b"cache")
            checkpoint = root / "parent.weights.h5"
            checkpoint.write_bytes(b"parent")
            checkpoint_hash = hashlib.sha256(b"parent").hexdigest()
            parent_record = {"checkpoint_path": str(checkpoint), "checkpoint_hash": checkpoint_hash, "cache_hash": cache_hash, "protocol_id": "PAPER_TEXT_V1", "stage": "stage1", "route": "PAPER_PRETRAIN_V1"}
            metadata = root / "parent.json"
            metadata.write_text(json.dumps(parent_record, sort_keys=True))
            external = dict(parent_record, metadata_path=str(metadata), metadata_hash=hashlib.sha256(metadata.read_bytes()).hexdigest())
            split_hashes = {"train": "a" * 64, "validation": "b" * 64, "test": "c" * 64}
            config = {"protocol_id": "PAPER_TEXT_V1", "source_manifest": source, "source_manifest_hash": source_hash, "environment_manifest": environment, "environment_manifest_hash": environment_hash, "data_manifest": phase2, "data_manifest_hash": phase2_hash, "cache_manifest": cache, "cache_manifest_hash": cache_hash, "cache_hash": cache_hash, "phase2_manifest": phase2, "split_hashes": split_hashes, "seed": 42, "mode": "pilot", "stage": "stage2", "external_parent": external}
            run_dir = root / "run"
            with patch("paper_faithful.training.trainer.run_directory", return_value=run_dir):
                directory, record = prepare_run("run", config, bulk_root=root)
            record = transition_run(directory, record, "running", stage_progress={"next_stage": "stage2", "last_epoch": 0, "checkpoint": external, "inflight": False})
            output_checkpoint = run_dir / "stage2.weights.h5"
            output_checkpoint.write_bytes(b"stage2")
            output_hash = hashlib.sha256(b"stage2").hexdigest()
            split_metrics = {split: {"silhouette": silhouette_metric([[0], [1], [2], [3]], [0, 0, 1, 1]), "scope": {"split": split, "base_epoch_membership_hash": split_hashes[split], "split_sample_count": 4, "evaluated_sample_count": 4, "evaluation_mode": "deterministic_uniform_reservoir", "reservoir_seed": 42, "reservoir_cap": 4096}} for split in ("validation", "test")}
            metric_path = run_dir / "stage2.metrics.json"
            metric = write_metrics_artifact(metric_path, split_metrics, {"schema_version": 1, "protocol_id": "PAPER_TEXT_V1", "stage": "stage2", "route": "PAPER_PRETRAIN_V1", "cache_hash": cache_hash, "checkpoint_path": str(output_checkpoint), "checkpoint_sha256": output_hash, "split_membership_hashes": split_hashes, "initial_epoch": 0, "stage_spec": {"stage": "stage2"}})
            artifact = {"checkpoint_path": str(output_checkpoint), "checkpoint_hash": output_hash, "parent_checkpoint_path": str(checkpoint), "parent_checkpoint_hash": checkpoint_hash, "route": "PAPER_PRETRAIN_V1", "metrics_path": str(metric_path), "metrics_file_sha256": hashlib.sha256(metric_path.read_bytes()).hexdigest(), "metrics_artifact_sha256": metric["artifact_sha256"]}
            parent = {"checkpoint_path": str(output_checkpoint), "checkpoint_hash": output_hash, "cache_hash": cache_hash, "protocol_id": "PAPER_TEXT_V1", "stage": "stage2", "route": "PAPER_PRETRAIN_V1"}
            record = transition_run(directory, record, "running", checkpoint_path=str(output_checkpoint), checkpoint_hash=output_hash, stage_artifacts={"stage2": artifact}, stage_progress={"next_stage": None, "last_epoch": 0, "checkpoint": parent, "inflight": False})
            transition_run(directory, record, "completed")
            self.assertEqual(verify_run_directory(run_dir)["status"], "completed")
            metadata.write_text("{}")
            with self.assertRaisesRegex(TrainingContractError, "external-parent metadata hash failed"):
                verify_run_directory(run_dir)

    def test_incomplete_run_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, source_hash = self._source(root, "source.json", b"source")
            environment, environment_hash = self._source(root, "environment.json", b"environment")
            phase2, phase2_hash = self._source(root, "phase2.json", b"phase2")
            cache, cache_hash = self._source(root, "cache.json", b"cache")
            config = {
                "protocol_id": "PAPER_TEXT_V1",
                "source_manifest": source,
                "source_manifest_hash": source_hash,
                "environment_manifest": environment,
                "environment_manifest_hash": environment_hash,
                "data_manifest": phase2,
                "data_manifest_hash": phase2_hash,
                "cache_manifest": cache,
                "cache_manifest_hash": cache_hash,
                "cache_hash": cache_hash,
                "phase2_manifest": phase2,
                "split_hashes": {"train": "a" * 64, "validation": "b" * 64, "test": "c" * 64},
                "seed": 42,
                "mode": "pilot",
                "stage": "all",
            }
            with patch("paper_faithful.training.trainer.run_directory", return_value=root / "run"):
                run_dir, _ = prepare_run("run", config, bulk_root=root)
            with self.assertRaisesRegex(TrainingContractError, "run is not completed"):
                verify_run_directory(run_dir)
            self.assertEqual(verify_run_directory(run_dir, require_completed=False)["status"], "planned")


if __name__ == "__main__":
    unittest.main()
