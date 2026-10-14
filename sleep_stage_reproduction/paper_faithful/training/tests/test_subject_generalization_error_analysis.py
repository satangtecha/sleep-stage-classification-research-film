import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from paper_faithful.training.subject_generalization_error_analysis import build_report


class ErrorAnalysisTests(unittest.TestCase):
    def test_requires_exactly_six_completed_folds(self):
        # This deliberately exercises the first fail-closed condition without
        # fabricating a synthetic experiment that could resemble real evidence.
        with self.assertRaises(ValueError):
            build_report(__import__("pathlib").Path("/definitely/not/a/run/root"), ("missing",))

    def test_aggregates_six_verified_fold_metric_artifacts(self):
        matrix = np.eye(5, dtype=int).tolist()
        subjects = ("SC1", "SC2", "SC3", "SC4", "SC5", "SC6")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, subject in enumerate(subjects, start=1):
                folder = root / ("run-fold{:02d}-test-{}".format(index, subject))
                folder.mkdir()
                (folder / "execution.json").write_text(
                    json.dumps({"status": "completed", "config": {"test_subject": subject}}),
                    encoding="utf-8",
                )
                (folder / "stage3.metrics.json").write_text(
                    json.dumps({"metrics": {"test": {"classification": {
                        "accuracy": 1.0, "macro": {"f1": 1.0}, "confusion_matrix": matrix,
                    }}}}),
                    encoding="utf-8",
                )
            report = build_report(root, ("run",))
        self.assertEqual(report["runs"][0]["pooled_test"]["accuracy"], 1.0)
        self.assertEqual(report["runs"][0]["pooled_test"]["macro"]["f1"], 1.0)
        self.assertEqual(report["runs"][0]["support_alerts"], [])


if __name__ == "__main__":
    unittest.main()
