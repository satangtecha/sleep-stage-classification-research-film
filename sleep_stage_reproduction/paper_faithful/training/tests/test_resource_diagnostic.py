"""Synthetic diagnostics contract tests; no GPU or real cache scan."""
import hashlib
import json
import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from paper_faithful.training import resource_diagnostic as diagnostic
from paper_faithful.sst.cache_manifest import ROUTES, canonical_hash, route_config


class ResourceDiagnosticTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        source = root / "source.npz"
        source.write_bytes(b"diagnostic fixture only")
        binding = {"record_id": "SC4001", "subject_id": "SC400", "epochs": 4,
            "shard_path": str(source), "shard_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        route = "PAPER_PRETRAIN_V1"
        identity = {"callable":"x","transform_source_sha256":"0"*64,"ssqueezepy":"0","numpy":"0","python":"0","n_fft":512,"frequency_bins":256,"normalization":"x","resize":"x"}
        config = route_config(ROUTES[route], identity)
        manifest = {"record_bindings": [binding], "chunk_epochs": 1, "chunks": [],
            "phase2_manifest_sha256": "0"*64, "phase2_manifest_path": "phase.json",
            "completion_marker_path": "marker.json", "completion_marker_sha256": "1"*64}
        provenance = {key: manifest[key] for key in ("phase2_manifest_sha256", "phase2_manifest_path", "completion_marker_path", "completion_marker_sha256")}
        provenance["record_binding"] = binding
        for epoch in range(4):
            tensor = root / ("SC4001." + route + ".%08d.npy" % epoch)
            values = np.full((1, 12, 64, 64, 2), epoch, dtype=np.float32)
            np.save(str(tensor), values)
            side = {"record_id": "SC4001", "subject_id": "SC400", "local_epoch_start": epoch,
                "local_epoch_end_exclusive": epoch+1, "local_epoch_indices": [epoch], "labels": [epoch],
                "tensor_shape": list(values.shape), "tensor_dtype": "float32", "tensor_file": tensor.name,
                "config": config, "config_sha256": canonical_hash(config), "cohort_provenance": provenance,
                "source_path": str(source), "source_sha256": binding["shard_sha256"],
                "tensor_sha256": hashlib.sha256(tensor.read_bytes()).hexdigest()}
            side_path = tensor.with_suffix(".json")
            side_path.write_text(json.dumps(side), encoding="utf-8")
            manifest["chunks"].append({"tensor": str(tensor), "sidecar": str(side_path)})
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), route

    def test_exact_selected_data_and_io_copy_leave_originals_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest, route = self.fixture(directory)
            with patch.object(diagnostic, "_host_path", side_effect=lambda value, *unused: Path(value).resolve()):
                cache, evidence = diagnostic.selected_cache(path, digest, route)
            self.assertEqual(len(cache.members), 4)
            for index, member in enumerate(cache.members):
                self.assertTrue(np.all(cache.window(member, route) == index))
            result = diagnostic.io_measure(cache, evidence)
            self.assertEqual(set(result["seconds"]), {"windows_mount", "linux_ext4"})
            self.assertTrue(all(len(samples) == 4 for samples in result["seconds"].values()))
            self.assertTrue(result["warm_cache_only"])
            self.assertFalse(result["cold_cache_measured"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            for row in evidence:
                self.assertEqual(hashlib.sha256(Path(row["tensor"]).read_bytes()).hexdigest(), row["tensor_sha256"])
            cache.close()

    def test_manifest_anchor_and_changed_tensor_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest, route = self.fixture(directory)
            with patch.object(diagnostic, "_host_path", side_effect=lambda value, *unused: Path(value).resolve()):
                with self.assertRaisesRegex(ValueError, "anchor mismatch"):
                    diagnostic.selected_cache(path, "f"*64, route)
                manifest = json.loads(path.read_text())
                with Path(manifest["chunks"][0]["tensor"]).open("ab") as handle:
                    handle.write(b"changed")
                with self.assertRaises(ValueError):
                    diagnostic.selected_cache(path, digest, route)

    def test_json_budget_rejects_oversized_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_bytes(b" "*16 + b"{}")
            with self.assertRaisesRegex(ValueError, "budget"):
                diagnostic.read_json_bytes(path, 8)

    def test_diagnostic_budget_is_specific_and_rejects_invalid_values(self):
        valid = {"power_online": True, "critical": False, "free_ram_mib": 1600, "commit_headroom_mib": 5000, "e_free_gib": 3}
        diagnostic.check_host_budget(valid, "io")
        with self.assertRaises(ValueError):
            diagnostic.check_host_budget(valid, "stage1")
        diagnostic.check_host_budget(valid, "stage1", initial=False)
        for key, value in (("free_ram_mib", True), ("free_ram_mib", float("nan")), ("power_online", False), ("commit_headroom_mib", 0)):
            with self.assertRaises(ValueError):
                diagnostic.check_host_budget(dict(valid, **{key: value}), "io")

    def test_compact_requires_real_finite_kernel_limits_and_host_reserve(self):
        limits = {"memory.max": 2*1024**3, "memory.swap.max": 2*1024**3}
        diagnostic.check_compact_scope(limits)
        for key in limits:
            for invalid in ("max", None, True, -1, 0, 2*1024**3+1):
                with self.assertRaises(ValueError):
                    diagnostic.check_compact_scope(dict(limits, **{key: invalid}))
        host = {"power_online": True, "critical": False, "free_ram_mib": 2816, "commit_headroom_mib": 4096, "e_free_gib": 2}
        diagnostic.check_host_budget(host, "stage1", compact=True)
        with self.assertRaises(ValueError):
            diagnostic.check_host_budget(dict(host, free_ram_mib=2815), "stage1", compact=True)
        diagnostic.check_host_budget(dict(host, free_ram_mib=768), "stage1", initial=False, compact=True)
        with self.assertRaises(ValueError):
            diagnostic.check_host_budget(dict(host, free_ram_mib=767), "stage1", initial=False, compact=True)

    def test_interrupt_and_cleanup_failures_publish_terminal_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            record = {"status": "started"}
            diagnostic.set_failure(record, KeyboardInterrupt("interrupted"))
            with patch.object(diagnostic, "memory_snapshot", return_value={}), patch("builtins.print"):
                diagnostic.finalize_record(Path(directory), record, None)
            result = json.loads((Path(directory) / "result.json").read_text())
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"]["type"], "KeyboardInterrupt")
        with tempfile.TemporaryDirectory() as directory:
            class Cache:
                def close(self):
                    raise KeyboardInterrupt("cleanup interrupted")
            with patch.object(diagnostic, "memory_snapshot", return_value={}), patch("builtins.print"):
                diagnostic.finalize_record(Path(directory), {"status": "pass"}, Cache())
            self.assertEqual(json.loads((Path(directory) / "result.json").read_text())["status"], "failed")

    def test_final_snapshot_failure_still_publishes_failed_result(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(diagnostic, "memory_snapshot", side_effect=OSError("proc unavailable")), patch("builtins.print"):
                diagnostic.finalize_record(Path(directory), {"status": "pass"}, None)
            result = json.loads((Path(directory) / "result.json").read_text())
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["after"]["unavailable"])

    def test_stop_in_terminal_handoff_preserves_decision(self):
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            with self.assertRaises(TimeoutError):
                diagnostic.handle_stop({"status": "started"}, stop_signal)
            for status in ("pass", "failed"):
                record = {"status": status}
                diagnostic.handle_stop(record, stop_signal)
                self.assertEqual(record["status"], status)

    @unittest.skipUnless(hasattr(signal, "pthread_sigmask"), "requires POSIX signal masking")
    def test_stop_during_final_publication_does_not_contradict_completed_work(self):
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            with tempfile.TemporaryDirectory() as directory:
                previous = signal.getsignal(stop_signal)
                def stop_during_snapshot():
                    os.kill(os.getpid(), stop_signal)
                    return {}
                with patch.object(diagnostic, "memory_snapshot", side_effect=stop_during_snapshot), patch("builtins.print"):
                    diagnostic.finalize_record(Path(directory), {"status": "pass"}, None)
                self.assertEqual(json.loads((Path(directory) / "result.json").read_text())["status"], "pass")
                self.assertEqual(signal.getsignal(stop_signal), previous)


if __name__ == "__main__":
    unittest.main()
