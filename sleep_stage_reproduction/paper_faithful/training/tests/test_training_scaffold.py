import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from paper_faithful.training.run_manifest import RunManifest, write_run_manifest
from paper_faithful.training.protocols import sequence_windows
from paper_faithful.training.splits import EpochMember, plan_epoch_split, plan_subject_split, validate_no_leakage
from paper_faithful.training.storage import require_bulk_path, run_directory


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.members = [EpochMember(f"S{subject:02}", f"R{subject:02}", epoch) for subject in range(10) for epoch in range(4)]

    def test_epoch_plan_is_repeatable_and_hashes_membership(self):
        first = plan_epoch_split(self.members)
        second = plan_epoch_split(reversed(self.members))
        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(len(first.train), 32)
        self.assertEqual(len(first.validation), 4)
        self.assertEqual(len(first.test), 4)
        validate_no_leakage(first, require_subject_disjoint=False)

    def test_subject_plan_has_no_subject_leakage(self):
        plan = plan_subject_split(self.members, seed=7)
        validate_no_leakage(plan, require_subject_disjoint=True)
        self.assertEqual(sum(map(len, (plan.train, plan.validation, plan.test))), len(self.members))

    def test_stage3_sequence_counts_follow_sources(self):
        self.assertEqual(sequence_windows("PAPER_TEXT_V1"), 15)
        self.assertEqual(sequence_windows("AUTHOR_CODE_V1"), 15)


class ManifestAndStorageTests(unittest.TestCase):
    def test_manifest_writer_and_failed_state(self):
        hashes = {name: digest(name) for name in ("train", "validation", "test")}
        manifest = RunManifest("PAPER_TEXT_V1", digest("source"), digest("environment"), digest("data"), hashes, 42, "stage1", status="failed", failure={"type": "SyntheticFailure", "message": "expected"})
        with tempfile.TemporaryDirectory() as directory:
            output = write_run_manifest(manifest, Path(directory) / "run.json")
            self.assertIn('"status": "failed"', output.read_text(encoding="utf-8"))

    def test_c_drive_and_unsafe_run_id_are_rejected(self):
        with self.assertRaises(ValueError):
            require_bulk_path(r"C:\tmp\run")
        with self.assertRaises(ValueError):
            run_directory("../bad")
        with self.assertRaises(ValueError):
            run_directory("..")
        if os.name == "nt":
            with self.assertRaises(ValueError):
                require_bulk_path("/mnt/e/blp/sleep_stage_reproduction")
        else:
            self.assertEqual(str(require_bulk_path("/mnt/e/blp/sleep_stage_reproduction")), str(Path("/mnt/e/blp/sleep_stage_reproduction")))
        with self.assertRaises(ValueError):
            require_bulk_path("/mnt/e/../../mnt/c/training")
        expected = (r"E:\blp\sleep_stage_reproduction\runs\scaffold" if os.name == "nt"
                    else "/mnt/e/blp/sleep_stage_reproduction/runs/scaffold")
        self.assertEqual(str(run_directory("scaffold", r"E:\blp\sleep_stage_reproduction")), expected)

    def test_non_hex_digest_is_rejected(self):
        hashes = {name: digest(name) for name in ("train", "validation", "test")}
        manifest = RunManifest("PAPER_TEXT_V1", "z" * 64, digest("environment"), digest("data"), hashes, 42, "stage1")
        with self.assertRaises(ValueError):
            manifest.validate()

    def test_diagnostic_publication_is_exclusive_and_never_overwrites(self):
        from paper_faithful.training.stage3_stability_smoke import _atomic_new
        from paper_faithful.training.trainer import TrainingContractError

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "diagnostic.json"
            output.write_text("original", encoding="utf-8")
            with self.assertRaises(TrainingContractError):
                _atomic_new(output, {"status": "pass"})
            self.assertEqual(output.read_text(encoding="utf-8"), "original")
            fresh = Path(directory) / "fresh.json"
            _atomic_new(fresh, {"status": "pass"})
            self.assertIn('"status": "pass"', fresh.read_text(encoding="utf-8"))


class TensorflowSmokeTests(unittest.TestCase):
    def test_gradient_accumulation_matches_one_nominal_batch_if_tensorflow_is_available(self):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run in locked WSL TF 2.4 environment")
        from paper_faithful.training.trainer import _enable_gradient_accumulation

        def model():
            inputs = tf.keras.layers.Input(shape=(1,))
            outputs = tf.keras.layers.Dense(1, use_bias=False, kernel_initializer=tf.keras.initializers.Ones())(inputs)
            result = tf.keras.Model(inputs, outputs)
            result.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="mse")
            return result

        nominal = model()
        accumulated = _enable_gradient_accumulation(tf, model(), 2)
        nominal.train_on_batch(np.asarray([[1.], [2.]], dtype=np.float32), np.zeros((2, 1), dtype=np.float32))
        before = accumulated.get_weights()[0].copy()
        accumulated.train_on_batch(np.asarray([[1.]], dtype=np.float32), np.zeros((1, 1), dtype=np.float32))
        self.assertTrue(np.array_equal(accumulated.get_weights()[0], before))
        self.assertEqual(int(accumulated.optimizer.iterations.numpy()), 0)
        accumulated.train_on_batch(np.asarray([[2.]], dtype=np.float32), np.zeros((1, 1), dtype=np.float32))
        self.assertTrue(np.allclose(accumulated.get_weights()[0], nominal.get_weights()[0], rtol=0, atol=1e-7))
        self.assertEqual(int(accumulated.optimizer.iterations.numpy()), 1)

    def test_gradient_accumulation_model_fit_preserves_frozen_batchnorm_if_tensorflow_is_available(self):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run in locked WSL TF 2.4 environment")
        from paper_faithful.training.trainer import _enable_gradient_accumulation

        inputs = tf.keras.layers.Input(shape=(2,))
        batchnorm = tf.keras.layers.BatchNormalization(trainable=False)
        normalized = batchnorm(inputs)
        outputs = tf.keras.layers.Dense(1, use_bias=False, kernel_initializer=tf.keras.initializers.Ones())(normalized)
        model = tf.keras.Model(inputs, outputs)
        model.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="mse")
        _enable_gradient_accumulation(tf, model, 2)

        class Sequence(tf.keras.utils.Sequence):
            def __len__(self):
                return 2

            def __getitem__(self, index):
                if index not in (0, 1):
                    raise IndexError(index)
                return np.asarray([[index + 1., index + 2.]], dtype=np.float32), np.zeros((1, 1), dtype=np.float32)

        frozen_before = [value.numpy().copy() for value in batchnorm.non_trainable_weights]
        history = model.fit(Sequence(), epochs=1, shuffle=False, verbose=0)
        self.assertEqual(int(model.optimizer.iterations.numpy()), 1)
        self.assertTrue(np.isfinite(history.history["loss"][0]))
        self.assertTrue(all(np.array_equal(before, after.numpy()) for before, after in zip(frozen_before, batchnorm.non_trainable_weights)))

    def test_gradient_clipping_is_applied_after_effective_batch_average_if_tensorflow_is_available(self):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run in locked WSL TF 2.4 environment")
        from paper_faithful.training.trainer import _enable_gradient_accumulation

        def model():
            inputs = tf.keras.layers.Input(shape=(1,))
            outputs = tf.keras.layers.Dense(1, use_bias=False, kernel_initializer=tf.keras.initializers.Ones())(inputs)
            result = tf.keras.Model(inputs, outputs)
            result.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="mse")
            return result

        reference = model()
        accumulated = _enable_gradient_accumulation(tf, model(), 2, gradient_clip_norm=1.0)
        samples = (
            (np.asarray([[10.]], dtype=np.float32), np.asarray([[0.]], dtype=np.float32)),
            (np.asarray([[1.]], dtype=np.float32), np.asarray([[11.]], dtype=np.float32)),
        )
        gradient_sum = tf.Variable(tf.zeros_like(reference.trainable_variables[0]), trainable=False)
        for x, y in samples:
            with tf.GradientTape() as tape:
                loss = tf.reduce_mean(tf.square(reference(x, training=True) - y))
            gradient_sum.assign_add(tape.gradient(loss, reference.trainable_variables)[0])
        averaged = gradient_sum / 2.0
        clipped, _ = tf.clip_by_global_norm([averaged], 1.0)
        reference.optimizer.apply_gradients(zip(clipped, reference.trainable_variables))
        for x, y in samples:
            accumulated.train_on_batch(x, y)
        self.assertTrue(np.allclose(accumulated.get_weights()[0], reference.get_weights()[0], rtol=0, atol=1e-7))
        state = accumulated._gradient_accumulation_state
        self.assertAlmostEqual(float(state["last_effective_gradient_global_norm"].numpy()), 90.0, places=5)
        self.assertAlmostEqual(float(state["last_applied_gradient_global_norm"].numpy()), 1.0, places=6)
        self.assertEqual((int(state["clipped_update_count"].numpy()), int(state["applied_update_count"].numpy())), (1, 1))

    def test_real_stage3_graph_matches_explicit_128_microbatch_post_average_update_if_tensorflow_is_available(self):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run in locked WSL TF 2.4 environment")
        from paper_faithful.training.models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru
        from paper_faithful.training.trainer import _enable_gradient_accumulation

        tf.keras.backend.clear_session()
        tf.random.set_seed(43)

        def stage3():
            stage1 = build_stage1_cnn("PAPER_TEXT_V1", input_shape=(64, 64, 2))
            stage2 = build_stage2_supervised_contrastive("PAPER_TEXT_V1", stage1, input_shape=(64, 64, 2))
            result = build_stage3_cnn_gru("PAPER_TEXT_V1", stage2, input_shape=(64, 64, 2))
            for layer in result.layers:
                if isinstance(layer, tf.keras.layers.Dropout):
                    layer.rate = 0.0
            result.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="sparse_categorical_crossentropy")
            return result

        reference = stage3()
        accumulated = stage3()
        accumulated.set_weights(reference.get_weights())
        _enable_gradient_accumulation(tf, accumulated, 128, gradient_clip_norm=1.0)
        gradient_sums = [tf.Variable(tf.zeros_like(variable), trainable=False) for variable in reference.trainable_variables]

        def sample(index):
            value = np.full((1, 15, 64, 64, 2), ((index % 11) - 5) / 100.0, dtype=np.float32)
            return value, np.asarray([index % 5], dtype=np.int32)

        for index in range(128):
            x, y = sample(index)
            with tf.GradientTape() as tape:
                prediction = reference(x, training=True)
                loss = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(y, prediction))
            gradients = tape.gradient(loss, reference.trainable_variables)
            self.assertTrue(all(gradient is not None and bool(tf.reduce_all(tf.math.is_finite(gradient)).numpy()) for gradient in gradients))
            for total, gradient in zip(gradient_sums, gradients):
                total.assign_add(gradient)
        averaged = [total / 128.0 for total in gradient_sums]
        clipped, _ = tf.clip_by_global_norm(averaged, 1.0)
        reference.optimizer.apply_gradients(zip(clipped, reference.trainable_variables))
        for index in range(128):
            accumulated.train_on_batch(*sample(index))
        self.assertEqual((int(reference.optimizer.iterations.numpy()), int(accumulated.optimizer.iterations.numpy())), (1, 1))
        for expected, actual in zip(reference.trainable_variables, accumulated.trainable_variables):
            self.assertTrue(np.allclose(expected.numpy(), actual.numpy(), rtol=0, atol=1e-5))
        state = accumulated._gradient_accumulation_state
        self.assertEqual(int(state["applied_update_count"].numpy()), 1)
        self.assertLessEqual(float(state["last_applied_gradient_global_norm"].numpy()), 1.000001)
        self.assertTrue(all(np.isfinite(weight).all() for weight in accumulated.get_weights()))

    def test_real_stage3_graph_seed43_stochastic_update_is_finite_if_tensorflow_is_available(self):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run in locked WSL TF 2.4 environment")
        from paper_faithful.training.models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru
        from paper_faithful.training.trainer import _enable_gradient_accumulation

        tf.keras.backend.clear_session()
        tf.random.set_seed(43)
        stage1 = build_stage1_cnn("PAPER_TEXT_V1", input_shape=(64, 64, 2))
        stage2 = build_stage2_supervised_contrastive("PAPER_TEXT_V1", stage1, input_shape=(64, 64, 2))
        model = build_stage3_cnn_gru("PAPER_TEXT_V1", stage2, input_shape=(64, 64, 2))
        model.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="sparse_categorical_crossentropy")
        _enable_gradient_accumulation(tf, model, 128, gradient_clip_norm=1.0)
        for index in range(128):
            x = np.full((1, 15, 64, 64, 2), ((index % 13) - 6) / 100.0, dtype=np.float32)
            y = np.asarray([index % 5], dtype=np.int32)
            model.train_on_batch(x, y)
        state = model._gradient_accumulation_state
        self.assertEqual((int(model.optimizer.iterations.numpy()), int(state["applied_update_count"].numpy()), int(state["counter"].numpy())), (1, 1, 0))
        for name in ("last_microbatch_gradient_global_norm", "max_microbatch_gradient_global_norm", "last_effective_gradient_global_norm", "max_effective_gradient_global_norm", "last_applied_gradient_global_norm", "max_applied_gradient_global_norm"):
            self.assertTrue(np.isfinite(float(state[name].numpy())))
        self.assertLessEqual(float(state["last_applied_gradient_global_norm"].numpy()), 1.000001)
        self.assertTrue(all(np.isfinite(weight).all() for weight in model.get_weights()))

    def test_synthetic_one_batch_if_tensorflow_is_available(self):
        try:
            import tensorflow  # noqa: F401
        except ImportError:
            self.skipTest("TensorFlow unavailable in this host interpreter; run smoke.py in locked WSL TF 2.4 environment")
        from paper_faithful.training.smoke import run
        result = run("PAPER_TEXT_V1")
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["synthetic_only"])
        self.assertEqual(result["stage3_parameter_counts"], {"total": 3340885, "trainable": 1764229, "non_trainable": 1576656})

class SubjectAwareNormalizationTests(unittest.TestCase):
    def _cache(self, labels):
        arrays = {
            "S1": np.asarray([[[[1.0, 3.0]]], [[[3.0, 5.0]]]], dtype=np.float32),
            "S2": np.asarray([[[[10.0, 20.0]]], [[[14.0, 24.0]]]], dtype=np.float32),
        }

        class Cache:
            def entry(self, member, route):
                return SimpleNamespace(offset=member.epoch_index, label=labels[member.key], subject_id=member.subject_id)

            def array(self, entry):
                return arrays[entry.subject_id]

        return Cache()

    def test_subject_zscore_is_per_subject_and_label_blind(self):
        from paper_faithful.training.trainer import CacheSequence, SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID

        members = (
            EpochMember("S1", "R1", 0), EpochMember("S1", "R1", 1),
            EpochMember("S2", "R2", 0), EpochMember("S2", "R2", 1),
        )
        first = CacheSequence(self._cache({member.key: index for index, member in enumerate(members)}), members, "route", 4, True, False, subject_normalization_id=SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID)
        second = CacheSequence(self._cache({member.key: 4 - index for index, member in enumerate(members)}), members, "route", 4, True, False, subject_normalization_id=SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID)
        normalized, _ = first[0]
        normalized_with_changed_labels, _ = second[0]
        self.assertTrue(np.allclose(normalized, normalized_with_changed_labels))
        self.assertTrue(np.allclose(normalized[:, 0, 0, :], [[-1.0, -1.0], [1.0, 1.0], [-1.0, -1.0], [1.0, 1.0]]))
        self.assertEqual(set(first._subject_stats), {"S1", "S2"})

    def test_subject_zscore_is_opt_in_and_rejects_unknown_id(self):
        from paper_faithful.training.trainer import CacheSequence, TrainingContractError

        members = (EpochMember("S1", "R1", 0), EpochMember("S1", "R1", 1))
        plain = CacheSequence(self._cache({member.key: 0 for member in members}), members, "route", 2, True, False)
        values, _ = plain[0]
        self.assertTrue(np.allclose(values[:, 0, 0, :], [[1.0, 3.0], [3.0, 5.0]]))
        with self.assertRaises(TrainingContractError):
            CacheSequence(self._cache({member.key: 0 for member in members}), members, "route", 2, True, False, subject_normalization_id="wrong")


class TrainOnlyTimeMaskTests(unittest.TestCase):
    def test_time_mask_is_deterministic_and_opt_in(self):
        from paper_faithful.training.trainer import CacheSequence, TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID

        values = np.arange(2 * 1 * 8 * 8 * 2, dtype=np.float32).reshape((2, 1, 8, 8, 2))
        members = (EpochMember("S1", "R1", 0), EpochMember("S1", "R1", 1))

        class Cache:
            def entry(self, member, route):
                return SimpleNamespace(offset=member.epoch_index, label=0, subject_id=member.subject_id)

            def array(self, entry):
                return values

        plain, _ = CacheSequence(Cache(), members, "route", 2, False, False)[0]
        first, _ = CacheSequence(Cache(), members, "route", 2, False, False, train_augmentation_id=TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID)[0]
        second, _ = CacheSequence(Cache(), members, "route", 2, False, False, train_augmentation_id=TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID)[0]
        self.assertTrue(np.array_equal(first, second))
        self.assertFalse(np.array_equal(plain, first))
        self.assertTrue(np.all(first == 0, axis=(0, 1, 3)).any())


if __name__ == "__main__":
    unittest.main()
