import unittest
import os
from pathlib import Path

import numpy as np

from paper_faithful.sst.storage import MIN_FREE_RESERVE_BYTES, ensure_cache_capacity, estimate_cache, require_e_drive
from paper_faithful.sst.pilot import storage_matrix
from paper_faithful.sst.transform import convert_single_window, minmax_component, resize_bilinear_half_pixel
from paper_faithful.sst.windowing import AUTHOR_CODE_V1, PAPER_TEXT_V1, plan_window_bounds, window_one_epoch, window_record_epochs


class WindowingTests(unittest.TestCase):
    def test_exact_starts_and_end_coverage(self):
        self.assertEqual(PAPER_TEXT_V1.starts(), (0, 249, 498, 747, 996, 1245, 1494, 1743, 1992, 2241, 2490, 2739))
        self.assertEqual(AUTHOR_CODE_V1.starts(), (0, 192, 384, 576, 768, 960, 1152, 1344, 1536, 1728, 1920, 2112, 2304, 2496, 2688))
        self.assertEqual(plan_window_bounds(PAPER_TEXT_V1, 3000)[0], (0, 256))
        self.assertEqual(plan_window_bounds(PAPER_TEXT_V1, 3000)[-1], (2739, 2995))
        self.assertEqual(plan_window_bounds(AUTHOR_CODE_V1, 3000)[-1], (2688, 2944))

    def test_shape_and_determinism(self):
        epoch = np.arange(3000, dtype=np.float32)
        first = window_one_epoch(epoch, PAPER_TEXT_V1)
        second = window_one_epoch(epoch, PAPER_TEXT_V1)
        self.assertEqual(first.shape, (12, 256))
        np.testing.assert_array_equal(first, second)

    def test_record_boundary_prohibition(self):
        with self.assertRaises(ValueError):
            window_record_epochs("", np.zeros((2, 3000)), PAPER_TEXT_V1)
        with self.assertRaises(ValueError):
            window_record_epochs("SC4001", np.zeros(6000), PAPER_TEXT_V1)


class TransformTests(unittest.TestCase):
    def test_independent_normalization_shape_and_determinism(self):
        matrix = np.arange(256 * 256, dtype=np.float32).reshape(256, 256) + 1j * 7
        fake = lambda signal, n_fft: (None, matrix)
        first = convert_single_window(np.zeros(256), protocol_id="AUTHOR_CODE_V1", ssq_transform=fake)
        second = convert_single_window(np.zeros(256), protocol_id="AUTHOR_CODE_V1", ssq_transform=fake)
        self.assertEqual(first.shape, (256, 256, 2))
        self.assertEqual(float(first[..., 0].min()), 0.0)
        self.assertEqual(float(first[..., 0].max()), 1.0)
        np.testing.assert_array_equal(first[..., 1], np.zeros((256, 256), dtype=np.float32))
        np.testing.assert_array_equal(first, second)

    def test_paper_sst_and_author_stft_slots_are_distinct(self):
        stft = np.arange(256 * 256, dtype=np.float32).reshape(256, 256).astype(np.complex64)
        sst = np.flipud(stft).copy()
        fake = lambda signal, n_fft: (sst, stft)
        paper = convert_single_window(np.zeros(256), protocol_id="PAPER_TEXT_V1", ssq_transform=fake)
        author = convert_single_window(np.zeros(256), protocol_id="AUTHOR_CODE_V1", ssq_transform=fake)
        self.assertFalse(np.array_equal(paper, author))

    def test_zero_range_is_finite_zero(self):
        normalized = minmax_component(np.full((3, 4), 8.0))
        np.testing.assert_array_equal(normalized, np.zeros((3, 4), dtype=np.float32))

    def test_half_pixel_bilinear_downsample(self):
        image = np.arange(16, dtype=np.float32).reshape(4, 4)
        resized = resize_bilinear_half_pixel(image, 2)
        np.testing.assert_allclose(resized, np.array([[2.5, 4.5], [10.5, 12.5]], dtype=np.float32), rtol=0, atol=0)


class StorageTests(unittest.TestCase):
    def test_estimator_and_reserve(self):
        estimate = estimate_cache(194655, 12, 256, "float32")
        self.assertEqual(estimate.bytes_total, 194655 * 12 * 256 * 256 * 2 * 4)
        ensure_cache_capacity(r"E:\blp\sleep_stage_reproduction\sst", estimate, free_bytes=estimate.bytes_total + MIN_FREE_RESERVE_BYTES)
        with self.assertRaises(RuntimeError):
            ensure_cache_capacity(r"E:\blp\sleep_stage_reproduction\sst", estimate, free_bytes=estimate.bytes_total + MIN_FREE_RESERVE_BYTES - 1)

    def test_storage_matrix_covers_resolutions_and_precisions(self):
        matrix = storage_matrix()
        self.assertEqual(set(matrix), {
            "paper_12_256_float32_gib", "paper_12_256_float16_gib", "paper_12_64_float32_gib", "paper_12_64_float16_gib",
            "author_15_256_float32_gib", "author_15_256_float16_gib", "author_15_64_float32_gib", "author_15_64_float16_gib",
        })

    def test_c_drive_is_rejected(self):
        with self.assertRaises(ValueError):
            require_e_drive(r"C:\tmp\sst")
        if os.name == "nt":
            with self.assertRaises(ValueError):
                require_e_drive("/mnt/e/blp/sleep_stage_reproduction/sst")
        else:
            self.assertEqual(str(require_e_drive("/mnt/e/blp/sleep_stage_reproduction/sst")), str(Path("/mnt/e/blp/sleep_stage_reproduction/sst")))
        with self.assertRaises(ValueError):
            require_e_drive("/mnt/e/../../mnt/c/sst-cache")


if __name__ == "__main__":
    unittest.main()
