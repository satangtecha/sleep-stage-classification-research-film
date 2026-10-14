import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

MANIFEST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MANIFEST_ROOT))
import validate_manifests  # noqa: E402


class ManifestValidationTests(unittest.TestCase):
    def test_owned_manifests_validate(self) -> None:
        self.assertEqual(validate_manifests.validate_directory(), [])

    def test_invalid_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "manifests"
            shutil.copytree(MANIFEST_ROOT, fixture_root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            path = fixture_root / "protocols" / "SUBJECT_GENERALIZATION_V1.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["may_compare_to_reported_83_percent"] = True
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifests.validate_directory(fixture_root)
        self.assertTrue(any("direct comparison to reported 83%" in error for error in errors))

    def test_invalid_source_lock_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "manifests"
            shutil.copytree(MANIFEST_ROOT, fixture_root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            path = fixture_root / "source_lock.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["author_repository"]["commit"] = "not-a-git-sha"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifests.validate_directory(fixture_root)
        self.assertTrue(any("full lowercase Git SHA" in error for error in errors))

    def test_invented_provenance_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "manifests"
            shutil.copytree(MANIFEST_ROOT, fixture_root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            path = fixture_root / "protocols" / "AUTHOR_CODE_V1.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["provenance"]["ref"] = "INVENTED_SOURCE"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifests.validate_directory(fixture_root)
        self.assertTrue(any("provenance ref must resolve" in error for error in errors))

    def test_unknown_author_gaps_are_schema_field(self) -> None:
        manifest = json.loads((MANIFEST_ROOT / "protocols" / "AUTHOR_CODE_V1.json").read_text(encoding="utf-8"))
        self.assertNotIn("reproducibility_gaps", manifest)
        self.assertEqual({entry["field"] for entry in manifest["unknowns"]}, {"split_indices", "checkpoints"})

    def test_undeclared_manifest_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "manifests"
            shutil.copytree(MANIFEST_ROOT, fixture_root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            path = fixture_root / "protocols" / "AUTHOR_CODE_V1.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["reproducibility_gaps"] = []
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifests.validate_directory(fixture_root)
        self.assertTrue(any("unsupported top-level field reproducibility_gaps" in error for error in errors))

    def test_invented_conflict_protocol_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "manifests"
            shutil.copytree(MANIFEST_ROOT, fixture_root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            path = fixture_root / "protocols" / "AUTHOR_CODE_V1.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["conflicts"][0]["other_protocol"] = "INVENTED_PROTOCOL"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_manifests.validate_directory(fixture_root)
        self.assertTrue(any("conflict other_protocol must resolve" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
