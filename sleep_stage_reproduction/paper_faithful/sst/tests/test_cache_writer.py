from concurrent.futures import ThreadPoolExecutor
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from paper_faithful.sst.cache_manifest import AUTHOR_CODE_V1, PAPER_PRETRAIN_V1, PAPER_STAGE3_V1, sha256_file
from paper_faithful.sst.cache_writer import CacheCollisionError, aggregate_storage_estimate, ensure_aggregate_capacity, worker_plan, write_record_chunk
from paper_faithful.sst.storage import MIN_FREE_RESERVE_BYTES


def fake_transform(samples, *, protocol_id, output_resolution):
    value = {"PAPER_TEXT_V1": 1.0, "AUTHOR_CODE_V1": 2.0}[protocol_id] + float(samples[0])
    return np.full((output_resolution, output_resolution, 2), value, dtype=np.float32)


FAKE_IDENTITY = {
    "callable": "tests.fake_transform",
    "transform_source_sha256": "a" * 64,
    "ssqueezepy": "test",
    "numpy": np.__version__,
    "python": "test",
    "n_fft": 512,
    "frequency_bins": 256,
    "normalization": "test",
    "resize": "test",
}


class CacheWriterTests(unittest.TestCase):
    def make_shard(self, directory: Path, *, record_id="SC4001", epochs=2):
        path = directory / f"{record_id}.npz"
        x = np.stack([np.arange(3000, dtype=np.float32) + index * 10_000 for index in range(epochs)])
        np.savez(path, x=x, y=np.arange(epochs, dtype=np.uint8) + 1, record_id=np.asarray(record_id),
                 subject_id=np.asarray(record_id[:5]), sampling_hz=np.asarray(100, dtype=np.int32))
        return path

    def e_root(self, directory: Path) -> Path:
        return directory / "e-output"

    def write_test_chunk(self, *args, **kwargs):
        kwargs.setdefault("transform_identity", FAKE_IDENTITY)
        with patch("paper_faithful.sst.cache_writer.require_e_drive", side_effect=lambda path: Path(path)), \
             patch("paper_faithful.sst.storage.require_e_drive", side_effect=lambda path: Path(path)):
            return write_record_chunk(*args, **kwargs)

    def test_routes_and_shapes_identity_labels_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                for route, windows, slot in ((PAPER_PRETRAIN_V1, 12, 0), (PAPER_STAGE3_V1, 15, 0), (AUTHOR_CODE_V1, 15, 1)):
                    result = self.write_test_chunk(shard, output, route.name, max_epochs=1, transform=fake_transform)
                    self.assertFalse(result.resumed); self.assertEqual(np.load(result.tensor_path).shape, (1, windows, 64, 64, 2))
                    self.assertEqual(np.load(result.tensor_path).dtype, np.float32)
                    metadata = json.loads(result.sidecar_path.read_text())
                    self.assertEqual((metadata["record_id"], metadata["subject_id"], metadata["local_epoch_indices"], metadata["labels"]), ("SC4001", "SC400", [0], [1]))
                    self.assertEqual(metadata["config"]["route"]["transform_slot"], slot)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                resumed = self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)
            self.assertTrue(resumed.resumed)

    def test_corruption_collision_and_atomic_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                result = self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)
            result.tensor_path.write_bytes(b"corrupt")
            with self.assertRaises(CacheCollisionError):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)
            result.tensor_path.unlink(); result.sidecar_path.unlink()
            def broken(*args, **kwargs): raise RuntimeError("boom")
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                with self.assertRaises(RuntimeError): self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=broken)
            self.assertEqual(list(output.glob("*")), [])

    def test_resume_rejects_wrong_npy_shape_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                result = self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)
            with result.tensor_path.open("wb") as stream:
                np.save(stream, np.zeros((1, 1), dtype=np.float32), allow_pickle=False)
            metadata = json.loads(result.sidecar_path.read_text())
            metadata["tensor_sha256"] = sha256_file(result.tensor_path)
            result.sidecar_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(CacheCollisionError):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)

    def test_record_boundaries_capacity_and_c_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            with self.assertRaises(ValueError): write_record_chunk(shard, base / "c-output", PAPER_PRETRAIN_V1.name, transform=fake_transform)
            with self.assertRaises(RuntimeError):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform, free_bytes=MIN_FREE_RESERVE_BYTES)
            invalid = base / "joined.npz"
            np.savez(invalid, x=np.zeros((1, 6000), dtype=np.float32), y=np.array([1]), record_id=np.asarray("SC4001"), subject_id=np.asarray("SC400"), sampling_hz=np.asarray(100))
            with self.assertRaises(ValueError): self.write_test_chunk(invalid, output, PAPER_PRETRAIN_V1.name, transform=fake_transform)

    def test_estimate_and_worker_planning(self):
        estimate = aggregate_storage_estimate(10, (PAPER_PRETRAIN_V1.name, AUTHOR_CODE_V1.name))
        self.assertEqual(set(estimate["routes"]), {PAPER_PRETRAIN_V1.name, AUTHOR_CODE_V1.name})
        self.assertEqual(worker_plan(8, records=2), 2); self.assertEqual(worker_plan(None, records=2), 1)

    def test_changed_transform_identity_is_not_resumed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform)
            changed = dict(FAKE_IDENTITY); changed["transform_source_sha256"] = "b" * 64
            with self.assertRaises(CacheCollisionError):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1,
                                      transform=fake_transform, transform_identity=changed)

    def test_exclusive_lock_rejects_overlapping_writer(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            started, release = threading.Event(), threading.Event()

            def slow_transform(*args, **kwargs):
                started.set(); release.wait(timeout=5)
                return fake_transform(*args, **kwargs)

            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(self.write_test_chunk, shard, output, PAPER_PRETRAIN_V1.name,
                                        max_epochs=1, transform=slow_transform)
                    self.assertTrue(started.wait(timeout=5))
                    second = pool.submit(self.write_test_chunk, shard, output, PAPER_PRETRAIN_V1.name,
                                         max_epochs=1, transform=slow_transform)
                    with self.assertRaises(CacheCollisionError):
                        second.result(timeout=5)
                    release.set()
                    self.assertFalse(first.result(timeout=5).resumed)

    def test_interruption_between_pair_replaces_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base); output = self.e_root(base)
            real_replace, calls = os.replace, []

            def interrupted(source, destination):
                calls.append((source, destination))
                if len(calls) == 2:
                    raise OSError("simulated interruption")
                return real_replace(source, destination)

            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"), \
                 patch("paper_faithful.sst.cache_writer.os.replace", side_effect=interrupted):
                with self.assertRaises(OSError):
                    self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name,
                                          max_epochs=1, transform=fake_transform)
            self.assertEqual(len(list(output.glob("*.npy"))), 1)
            self.assertEqual(len(list(output.glob("*.json"))), 0)
            self.assertEqual(len(list(output.glob("*.lock"))), 0)
            with self.assertRaises(CacheCollisionError):
                self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name,
                                      max_epochs=1, transform=fake_transform)

    def test_aggregate_capacity_and_label_range(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); output = self.e_root(base)
            with patch("paper_faithful.sst.cache_writer.require_e_drive", side_effect=lambda path: Path(path)), \
                 patch("paper_faithful.sst.storage.require_e_drive", side_effect=lambda path: Path(path)):
                with self.assertRaises(RuntimeError):
                    ensure_aggregate_capacity(output, 194655, free_bytes=MIN_FREE_RESERVE_BYTES)
            invalid = base / "invalid-label.npz"
            np.savez(invalid, x=np.zeros((1, 3000), dtype=np.float32), y=np.array([5]),
                     record_id=np.asarray("SC4001"), subject_id=np.asarray("SC400"), sampling_hz=np.asarray(100))
            with self.assertRaises(ValueError):
                self.write_test_chunk(invalid, output, PAPER_PRETRAIN_V1.name,
                                      max_epochs=1, transform=fake_transform)

    def test_cohort_binding_rejects_mutation_and_epoch_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base, epochs=2); output = self.e_root(base); bound_hash = sha256_file(shard)
            def mutating_transform(*args, **kwargs):
                self.make_shard(base, epochs=1)
                return fake_transform(*args, **kwargs)
            with patch("paper_faithful.sst.cache_writer.ensure_cache_capacity"):
                with self.assertRaises(Exception):
                    self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=mutating_transform,
                                          cohort_provenance={"record_binding": {}}, expected_source_sha256=bound_hash, expected_epoch_count=2)
                with self.assertRaises(Exception):
                    self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, max_epochs=1, transform=fake_transform,
                                          cohort_provenance={"record_binding": {}}, expected_source_sha256=sha256_file(shard), expected_epoch_count=2)

    def test_malicious_record_id_cannot_write_outside_cache_root(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); shard = self.make_shard(base, record_id="SC4001"); output = self.e_root(base)
            np.savez(shard, x=np.zeros((1, 3000), dtype=np.float32), y=np.array([0]), record_id=np.asarray("SC4001/.."), subject_id=np.asarray("SC400"), sampling_hz=np.asarray(100))
            with self.assertRaises(Exception): self.write_test_chunk(shard, output, PAPER_PRETRAIN_V1.name, transform=fake_transform)


if __name__ == "__main__":
    unittest.main()
