import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from paper_faithful.sst.cache_manifest import PAPER_PRETRAIN_V1, cache_stem, sha256_file
from paper_faithful.sst.cohort_cache import CohortCacheError, EXPECTED, FULL_PAYLOAD_BYTES, FULL_ROUTES, PHASE2_RESULT_KEYS, SC4362_ZERO_EPOCH_EXCLUSION, _acquire_run_lock, _contained, _pid_alive, load_phase2_binding, recover_chunk, recover_run_lock, run_full_cache
from paper_faithful.sst.cache_writer import write_record_chunk


class CohortCacheTests(unittest.TestCase):
    def test_sidecar_persists_manifest_hash_and_record_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); shard = root / "SC4001.npz"
            np.savez(shard, x=np.zeros((1, 3000), dtype=np.float32), y=np.array([0], dtype=np.uint8),
                     record_id=np.asarray("SC4001"), subject_id=np.asarray("SC400"), sampling_hz=np.asarray(100))
            identity = {"callable": "test", "transform_source_sha256": "a" * 64, "ssqueezepy": "test", "numpy": np.__version__, "python": "test", "n_fft": 512, "frequency_bins": 256, "normalization": "test", "resize": "test"}
            provenance = {"phase2_manifest_sha256": "b" * 64, "record_binding": {"record_id": "SC4001", "shard_sha256": sha256_file(shard)}}
            def transform(*args, **kwargs): return np.zeros((64, 64, 2), dtype=np.float32)
            with patch("paper_faithful.sst.cache_writer.require_e_drive", side_effect=lambda value: Path(value)), \
                 patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                outcome = write_record_chunk(shard, root / "cache", PAPER_PRETRAIN_V1.name, max_epochs=1,
                                             transform=transform, transform_identity=identity, cohort_provenance=provenance,
                                             expected_source_sha256=sha256_file(shard), expected_epoch_count=1)
            self.assertEqual(json.loads(outcome.sidecar_path.read_text())["cohort_provenance"], provenance)

    def make_phase2(self, base, *, subject_count=78, include_sc4362_zero=False):
        root = Path(base) / "phase2"; manifests = root / "manifests"; shards = root / "shards"
        manifests.mkdir(parents=True); shards.mkdir()
        if not 1 <= subject_count <= 78:
            raise ValueError("fixture subject count must be 1..78")
        ids = ["SC{0:03d}{1}".format(index % subject_count, index // subject_count) for index in range(153)]
        labels = np.concatenate([np.full(EXPECTED["class_counts"][name], value, dtype=np.int64)
                                 for value, name in enumerate(("W", "N1", "N2", "N3", "REM"))])
        labels = np.random.default_rng(20260819).permutation(labels)
        active_rows = 152 if include_sc4362_zero else 153
        lengths = np.full(active_rows, labels.size // active_rows, dtype=np.int64)
        lengths[:labels.size % active_rows] += 1
        zero_index = 75 if include_sc4362_zero else None
        if zero_index is not None:
            ids[zero_index] = "SC4362"
        records, offset, active_index, fake_identities = [], 0, 0, {}
        for index in range(153):
            record_id = ids[index]
            path = shards / (record_id + ".npz")
            np.savez(path, x=np.zeros((1, 3000), dtype=np.float32), y=np.array([0], dtype=np.uint8),
                     record_id=np.asarray(record_id), subject_id=np.asarray(record_id[:5]), sampling_hz=np.asarray(100))
            count = 0 if index == zero_index else int(lengths[active_index])
            if index != zero_index:
                active_index += 1
            y = labels[offset:offset + count]; offset += count
            fake_identities[path.name] = {"record_id": record_id, "subject_id": record_id[:5],
                                          "x": type("ShapeOnly", (), {"shape": (count, 3000)})(), "y": y}
            records.append({"record_id": record_id, "subject_id": record_id[:5], "shard": path.name,
                            "shard_sha256": sha256_file(path), "epochs": count,
                            "class_counts": {name: int(np.count_nonzero(y == value)) for value, name in enumerate(("W", "N1", "N2", "N3", "REM"))},
                            "processing_status": "excluded_author_tail_slice_zero" if count == 0 else "emitted",
                            "compatibility_exclusion": SC4362_ZERO_EPOCH_EXCLUSION if count == 0 else None})
        result = {"schema_version": "1.0", "protocol_id": "SLEEP_EDF_CASSETTE_PAPER_FAITHFUL_PREPROCESSING_V1",
                  "parameters": {}, "provenance": {"source": [], "assumption": [], "unknown": []},
                  "status": "complete", "run_scope": {"mode": "full_cohort", "record_ids": ids}, "aggregate": EXPECTED,
                  "parity": {"eligible": True, "matches_expected": True, "expected": EXPECTED}, "records": records,
                  "failures": []}
        manifest = manifests / "preprocessing_result.json"; manifest.write_text(json.dumps(result), encoding="utf-8")
        marker = {"schema_version": "1.0", "status": "complete", "preprocessing_result": "manifests/preprocessing_result.json", "preprocessing_result_sha256": sha256_file(manifest)}
        completed = root / "COMPLETED.json"; completed.write_text(json.dumps(marker), encoding="utf-8")
        result["completion_marker"] = {"path": "COMPLETED.json", "required_for_eligibility": True, "published_only_when_status": "complete"}
        manifest.write_text(json.dumps(result), encoding="utf-8")
        marker["preprocessing_result_sha256"] = sha256_file(manifest); completed.write_text(json.dumps(marker), encoding="utf-8")
        return manifest, fake_identities

    def publish(self, manifest, result):
        manifest.write_text(json.dumps(result), encoding="utf-8")
        marker = manifest.parent.parent / "COMPLETED.json"
        marker.write_text(json.dumps({"schema_version": "1.0", "status": "complete",
                                      "preprocessing_result": "manifests/preprocessing_result.json",
                                      "preprocessing_result_sha256": sha256_file(manifest)}), encoding="utf-8")

    def load_fixture(self, manifest, identities, mutate=None):
        def loader(path):
            identity = dict(identities[Path(path).name])
            if mutate is not None:
                identity = mutate(identity)
            return identity
        return patch("paper_faithful.sst.cohort_cache.load_record_shard", side_effect=loader)

    def test_phase2_acceptance_and_hash_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp)
            with self.load_fixture(manifest, identities): binding = load_phase2_binding(manifest)
            self.assertEqual(len(binding["bindings"]), 153)
            self.assertEqual(binding["manifest_sha256"], sha256_file(manifest))

    def test_phase2_accepts_only_the_exact_sc4362_zero_epoch_compatibility_row(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp, include_sc4362_zero=True)
            with self.load_fixture(manifest, identities): binding = load_phase2_binding(manifest)
            zero = next(item for item in binding["bindings"] if item["record_id"] == "SC4362")
            self.assertEqual(zero["epochs"], 0)
            malformed = json.loads(manifest.read_text())
            row = next(item for item in malformed["records"] if item["record_id"] == "SC4362")
            row["compatibility_exclusion"]["overflow_epochs"] = 503
            self.publish(manifest, malformed)
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError):
                load_phase2_binding(manifest)

    def test_phase2_rejects_missing_or_invalid_declared_schema_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp)
            baseline = json.loads(manifest.read_text())
            variants = []
            for field in sorted(PHASE2_RESULT_KEYS):
                changed = json.loads(json.dumps(baseline)); del changed[field]
                variants.append(("missing_" + field, changed))
            extra = json.loads(json.dumps(baseline)); extra["unexpected"] = True
            variants.append(("unexpected_top_level", extra))
            wrong_schema = json.loads(json.dumps(baseline)); wrong_schema["schema_version"] = "2.0"
            variants.append(("wrong_schema_version", wrong_schema))
            wrong_protocol = json.loads(json.dumps(baseline)); wrong_protocol["protocol_id"] = "OTHER"
            variants.append(("wrong_protocol", wrong_protocol))
            wrong_parameters = json.loads(json.dumps(baseline)); wrong_parameters["parameters"] = []
            variants.append(("parameters_not_object", wrong_parameters))
            for field in ("source", "assumption", "unknown"):
                wrong_provenance = json.loads(json.dumps(baseline)); wrong_provenance["provenance"][field] = {}
                variants.append(("provenance_" + field + "_not_array", wrong_provenance))
            for name, invalid in variants:
                with self.subTest(name=name):
                    self.publish(manifest, invalid)
                    with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError):
                        load_phase2_binding(manifest)

    def test_phase2_rejects_forged_aggregate_subject_labels_and_row_epochs(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp)
            baseline = json.loads(manifest.read_text())
            forged = json.loads(json.dumps(baseline)); forged["aggregate"]["epochs"] -= 1; self.publish(manifest, forged)
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            self.publish(manifest, baseline)
            def forge_labels(item):
                labels = item["y"].copy(); labels[0] = (labels[0] + 1) % 5
                return dict(item, y=labels)
            with self.load_fixture(manifest, identities, forge_labels), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            row_mismatch = json.loads(json.dumps(baseline)); row_mismatch["records"][0]["epochs"] += 1; self.publish(manifest, row_mismatch)
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            subject_manifest, subject_identities = self.make_phase2(Path(temp) / "wrong-subjects", subject_count=77)
            with self.load_fixture(subject_manifest, subject_identities), self.assertRaises(CohortCacheError): load_phase2_binding(subject_manifest)

    def test_phase2_rejects_parity_hash_duplicate_and_extra_or_missing_shards(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp); baseline = json.loads(manifest.read_text())
            variants = []
            parity = json.loads(json.dumps(baseline)); parity["parity"]["eligible"] = False; variants.append(parity)
            hash_mismatch = json.loads(json.dumps(baseline)); hash_mismatch["records"][0]["shard_sha256"] = "0" * 64; variants.append(hash_mismatch)
            duplicate = json.loads(json.dumps(baseline)); duplicate["records"][-1]["record_id"] = duplicate["records"][0]["record_id"]; variants.append(duplicate)
            for result in variants:
                self.publish(manifest, result)
                with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            self.publish(manifest, baseline)
            extra = manifest.parent.parent / "shards" / "SC9999.npz"; extra.write_bytes(b"tiny")
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            extra.unlink(); (manifest.parent.parent / "shards" / baseline["records"][0]["shard"]).unlink()
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)

    def test_aggregate_gate_precedes_first_write_and_persists_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp); order = []
            class Result:
                tensor_path = Path("tensor.npy"); sidecar_path = Path("tensor.json"); resumed = False
            def gate(*args): order.append("gate"); return {"total_bytes": FULL_PAYLOAD_BYTES, "total_gib": 249.497, "routes": {name: 1 for name in FULL_ROUTES}}
            def writer(*args, **kwargs):
                order.append("write")
                self.assertIn("phase2_manifest_sha256", kwargs["cohort_provenance"])
                return Result()
            output = Path(temp) / "cache"
            with self.load_fixture(manifest, identities), \
                 patch("paper_faithful.sst.cohort_cache.require_e_drive", side_effect=lambda value: Path(value)), \
                 patch("paper_faithful.sst.cohort_cache.ensure_aggregate_capacity", side_effect=gate):
                result = run_full_cache(manifest, output, chunk_epochs=EXPECTED["epochs"], writer=writer)
            self.assertEqual(order[0], "gate")
            self.assertEqual(result["phase2_manifest_sha256"], sha256_file(manifest))
            self.assertEqual(tuple(result["routes"]), FULL_ROUTES)
            self.assertEqual(len([item for item in order if item == "write"]), 153 * 3)
            self.assertTrue((output / "sst_full_cohort_run_manifest.json").is_file())

    def test_completion_contract_rejects_absent_malformed_path_hash_status_and_result_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp); result = json.loads(manifest.read_text()); marker = manifest.parent.parent / "COMPLETED.json"
            variants = []
            absent = json.loads(json.dumps(result)); variants.append((absent, None))
            malformed = json.loads(json.dumps(result)); malformed["completion_marker"] = {}; variants.append((malformed, None))
            wrong_status = json.loads(json.dumps(result)); wrong_status["status"] = "failed"; variants.append((wrong_status, None))
            wrong_path = json.loads(json.dumps(result)); variants.append((wrong_path, {"schema_version": "1.0", "status": "complete", "preprocessing_result": "other.json", "preprocessing_result_sha256": sha256_file(manifest)}))
            wrong_hash = json.loads(json.dumps(result)); variants.append((wrong_hash, {"schema_version": "1.0", "status": "complete", "preprocessing_result": "manifests/preprocessing_result.json", "preprocessing_result_sha256": "0" * 64}))
            for changed, marker_value in variants:
                manifest.write_text(json.dumps(changed), encoding="utf-8")
                if marker_value is None:
                    if marker.exists(): marker.unlink()
                else: marker.write_text(json.dumps(marker_value), encoding="utf-8")
                with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)

    def test_rejects_epoch_mismatch_and_malicious_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, identities = self.make_phase2(temp); result = json.loads(manifest.read_text()); result["records"][0]["epochs"] += 1
            self.publish(manifest, result)
            with self.load_fixture(manifest, identities), self.assertRaises(CohortCacheError): load_phase2_binding(manifest)
            with patch("paper_faithful.sst.cohort_cache.require_e_drive", side_effect=lambda value: Path(value)):
                with self.assertRaises(CohortCacheError): recover_chunk(Path(temp), "SC4001/..", PAPER_PRETRAIN_V1.name, 0, 1)

    def test_stale_run_lock_requires_explicit_dead_owner_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); lock = root / ".sst_full_cohort.lock"
            lock.write_text(json.dumps({"schema_version": 1, "pid": 999999, "phase2_manifest_sha256": "a" * 64, "completion_marker_sha256": "b" * 64, "routes": list(FULL_ROUTES), "chunk_epochs": 32, "payload_bytes": FULL_PAYLOAD_BYTES}))
            with patch("paper_faithful.sst.cohort_cache.require_e_drive", side_effect=lambda value: Path(value)), patch("paper_faithful.sst.cohort_cache._pid_alive", return_value=False):
                self.assertEqual(recover_run_lock(root)["status"], "recovered_stale_run_lock")

    def test_windows_invalid_pid_is_dead_not_unverifiable(self):
        kernel32 = Mock(); kernel32.OpenProcess.return_value = None
        with patch("paper_faithful.sst.cohort_cache.os.name", "nt"), patch("paper_faithful.sst.cohort_cache.ctypes.WinDLL", return_value=kernel32) as windll, patch("paper_faithful.sst.cohort_cache.ctypes.set_last_error") as set_error, patch("paper_faithful.sst.cohort_cache.ctypes.get_last_error", return_value=87):
            self.assertFalse(_pid_alive(999999))
        windll.assert_called_once_with("kernel32", use_last_error=True); set_error.assert_called_once_with(0)

    def test_run_lock_rejects_concurrent_and_incompatible_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); contract = {"schema_version": 1, "pid": os.getpid(), "phase2_manifest_sha256": "a" * 64, "completion_marker_sha256": "b" * 64, "routes": list(FULL_ROUTES), "chunk_epochs": 32, "payload_bytes": FULL_PAYLOAD_BYTES}
            lock = _acquire_run_lock(root, contract)
            try:
                with self.assertRaises(CohortCacheError): _acquire_run_lock(root, contract)
                changed = dict(contract); changed["chunk_epochs"] = 1
                with self.assertRaises(CohortCacheError): _acquire_run_lock(root, changed)
            finally:
                lock.unlink()

    def target(self, root):
        stem = cache_stem("SC4001", PAPER_PRETRAIN_V1, 0, 1)
        return stem, root / (stem + ".npy"), root / (stem + ".json"), root / (stem + ".lock")

    def recovery(self, root, *args):
        with patch("paper_faithful.sst.cohort_cache.require_e_drive", side_effect=lambda value: Path(value)):
            return recover_chunk(root, "SC4001", PAPER_PRETRAIN_V1.name, 0, 1)

    def test_live_lock_refuses_and_stale_partial_recovers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); stem, tensor, sidecar, lock = self.target(root)
            tensor.write_bytes(b"partial"); lock.write_text(json.dumps({"pid": os.getpid(), "tensor": tensor.name, "sidecar": sidecar.name}))
            with self.assertRaises(CohortCacheError): self.recovery(root)
            with patch("paper_faithful.sst.cohort_cache._pid_alive", return_value=False):
                outcome = self.recovery(root)
            self.assertEqual(outcome["status"], "recovered"); self.assertFalse(tensor.exists()); self.assertFalse(lock.exists())

    def test_recovery_preserves_complete_pair_and_refuses_escape_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); stem, tensor, sidecar, lock = self.target(root)
            with tensor.open("wb") as stream: np.save(stream, np.zeros((1,), dtype=np.float32), allow_pickle=False)
            sidecar.write_text(json.dumps({"tensor_sha256": sha256_file(tensor)}))
            outcome = self.recovery(root); self.assertEqual(outcome["status"], "preserved_complete_pair")
            self.assertTrue(tensor.exists() and sidecar.exists())
            outside = root.parent / "outside"; outside.mkdir(exist_ok=True)
            link = root / "link"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(CohortCacheError): _contained(root, link / "SC4001.npz")


if __name__ == "__main__":
    unittest.main()
