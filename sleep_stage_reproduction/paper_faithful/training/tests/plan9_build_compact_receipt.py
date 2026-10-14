"""Build the receipt-bound cache subset for the corrected six-subject pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from types import SimpleNamespace

from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training.cache_loader import write_compact_selection_receipt_from_prior_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-receipt", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = runner._read_record_bindings_for_plan(args.manifest)
    subjects = sorted({subject for _, subject, _ in records})
    random.Random(args.seed).shuffle(subjects)
    selected = tuple(subjects[:6])
    profile = runner._resource_profile(
        SimpleNamespace(
            resource_profile=runner.RESOURCE_LIMITED_DETACHED_GPU_PROFILE_ID,
            cap=32,
            epochs=6,
            subject_count=6,
        )
    )

    required_members = set()
    for index, test_subject in enumerate(selected):
        validation_subject = selected[(index + 1) % len(selected)]
        for subset in (
            set(selected) - {test_subject, validation_subject},
            {validation_subject},
            {test_subject},
        ):
            required_members.update(
                item.key
                for item in runner._sample_members_for_profile(
                    records, subset, 32, args.seed, profile
                )
            )

    receipt_path = write_compact_selection_receipt_from_prior_evidence(
        args.manifest,
        args.destination,
        args.base_receipt,
        required_members,
        include_sidecar_metadata=True,
    )
    payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": "created",
                "selected_subjects": selected,
                "required_members": len(required_members),
                "selected_chunks": len(payload["chunks"]),
                "selected_member_count": payload["member_count"],
                "receipt_sha256": hashlib.sha256(Path(receipt_path).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
