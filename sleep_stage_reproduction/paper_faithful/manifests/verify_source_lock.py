"""Verify that the locally retrieved author repository matches source_lock.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parent
DEFAULT_REPOSITORY = ROOT.parent / "vendor" / "Sleep-Stage-Classification-v1.0"


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(repository: Path) -> List[str]:
    lock = json.loads((ROOT / "source_lock.json").read_text(encoding="utf-8"))
    expected = lock["author_repository"]
    errors: List[str] = []
    actual = {
        "remote": git(repository, "remote", "get-url", "origin"),
        "tag": git(repository, "describe", "--tags", "--exact-match", "HEAD"),
        "commit": git(repository, "rev-parse", "HEAD"),
        "requirements_sha256": sha256(repository / "requirements.txt"),
    }
    for field, value in actual.items():
        if value != expected[field]:
            errors.append("{} mismatch: expected {}, found {}".format(field, expected[field], value))
    if git(repository, "status", "--porcelain"):
        errors.append("author repository working tree is not clean")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPOSITORY)
    arguments = parser.parse_args()
    errors = verify(arguments.repository)
    if errors:
        print("INVALID")
        print("\n".join(errors))
        return 1
    print("VALID: author source matches tag, commit, remote, clean tree, and requirements SHA-256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

