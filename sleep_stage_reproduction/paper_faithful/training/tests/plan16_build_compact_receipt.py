"""Build the exact metadata receipt for Plan-16 class-balanced cap64."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from paper_faithful.training import subject_generalization_runner as runner
from paper_faithful.training.cache_loader import write_compact_selection_receipt_from_prior_evidence
from paper_faithful.training.quality_sampling import (
    load_verified_stage3_labels,
    sample_class_balanced_members_per_subject,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-receipt", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--subjects", nargs="+", required=True)
    args = parser.parse_args()

    records = runner._read_record_bindings_for_plan(args.manifest)
    subjects = tuple(args.subjects)
    labels, evidence = load_verified_stage3_labels(args.manifest, args.base_receipt, subjects)
    required = set()
    for subject in subjects:
        required.update(
            member.key
            for member in sample_class_balanced_members_per_subject(
                records, {subject}, 64, args.seed, labels
            )
        )
    path = write_compact_selection_receipt_from_prior_evidence(
        args.manifest,
        args.destination,
        args.base_receipt,
        required,
        include_sidecar_metadata=True,
        select_by_sidecar_filename=True,
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    print(json.dumps({
        "status": "created",
        "path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "subjects": list(subjects),
        "required_member_count": len(required),
        "selected_chunk_count": len(payload["chunks"]),
        "label_index_sha256": evidence["label_index_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
