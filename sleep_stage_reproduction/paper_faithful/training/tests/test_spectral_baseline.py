import unittest

import numpy as np

from paper_faithful.training.metrics import classification_metrics
from paper_faithful.training.spectral_baseline import (
    choose_l2,
    extract_features,
    membership_hash,
    predict,
    standardize_from_train,
    train_weighted_multinomial_logistic,
)
from paper_faithful.training.splits import EpochMember


class SpectralBaselineTests(unittest.TestCase):
    def test_sst_feature_shape_and_label_order(self):
        member = EpochMember("SC1", "R1", 0)
        tensor = np.zeros((15, 64, 64, 2), dtype=np.float32)
        tensor[..., 0] = 1.0

        class Cache:
            def stage3_sequences(self, values, route):
                if values != (member,) or route != "PAPER_STAGE3_V1":
                    raise AssertionError("unexpected baseline cache request")
                return iter(((member, tensor, 3),))

        features, labels = extract_features(Cache(), (member,))
        self.assertEqual(features.shape, (1, 128))
        self.assertEqual(labels.tolist(), [3])
        np.testing.assert_allclose(features[:, :64], np.log(2.0))
        np.testing.assert_allclose(features[:, 64:], 0.0, atol=1e-12)

    def test_membership_hash_ignores_input_order(self):
        members = (
            EpochMember("SC1", "R1", 1),
            EpochMember("SC1", "R1", 0),
        )
        self.assertEqual(membership_hash(members), membership_hash(tuple(reversed(members))))

    def test_training_standardization_does_not_use_test_statistics(self):
        train = np.array([[0.0, 2.0], [2.0, 4.0]])
        test = np.array([[100.0, 100.0]])
        normalized_train, normalized_test = standardize_from_train(train, test)
        np.testing.assert_allclose(normalized_train.mean(axis=0), np.zeros(2))
        self.assertGreater(normalized_test[0, 0], 90.0)

    def test_logistic_fits_separable_five_class_data(self):
        features = np.eye(5, dtype=np.float64) * 5.0
        labels = np.arange(5, dtype=np.int64)
        weights, bias = train_weighted_multinomial_logistic(
            features, labels, l2=1e-4, iterations=1500, learning_rate=0.25
        )
        result = classification_metrics(labels, predict(features, weights, bias))
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["macro"]["f1"], 1.0)

    def test_l2_selection_is_validation_based(self):
        features = np.eye(5, dtype=np.float64) * 3.0
        labels = np.arange(5, dtype=np.int64)
        chosen, trials = choose_l2(features, labels, features, labels)
        self.assertIn(chosen, (1e-4, 1e-3, 1e-2, 1e-1))
        self.assertEqual(set(trials), {"0.0001", "0.001", "0.01", "0.1"})


if __name__ == "__main__":
    unittest.main()
