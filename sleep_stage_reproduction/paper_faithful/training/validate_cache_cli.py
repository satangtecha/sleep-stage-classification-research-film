"""Read-only integrity gate for a finalized full-cohort SST cache."""
from __future__ import print_function

import argparse
import json
import time
from pathlib import Path

from .cache_loader import (
    CacheValidationError,
    load_canonical_cache,
    write_validation_receipt,
    write_validation_receipt_from_prior_evidence,
)
from paper_faithful.sst.cache_manifest import sha256_file


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-manifest", required=True)
    parser.add_argument("--write-receipt")
    parser.add_argument("--prior-validation-log")
    args = parser.parse_args(argv)
    started = time.time()
    print(
        json.dumps(
            {
                "event": "cache_validation_started",
                "cache_manifest": args.cache_manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        cache = None
        if args.prior_validation_log:
            if not args.write_receipt:
                raise CacheValidationError("--prior-validation-log requires --write-receipt")
            receipt_path = write_validation_receipt_from_prior_evidence(
                args.cache_manifest, args.write_receipt, args.prior_validation_log
            )
            receipt_path = Path(receipt_path)
            receipt_mode = "prior_full_cache_validator_evidence"
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf8"))
            output_manifest = str(args.cache_manifest)
            output_manifest_hash = sha256_file(args.cache_manifest)
            output_phase2 = receipt_payload["phase2_manifest_path"]
            output_phase2_hash = receipt_payload["phase2_manifest_sha256"]
            receipt_epochs = receipt_payload["member_count"]
            receipt_entries = receipt_payload["route_epoch_entries"]
        else:
            cache = load_canonical_cache(args.cache_manifest)
            receipt_path = None
            if args.write_receipt:
                receipt_path = write_validation_receipt(cache, args.write_receipt)
            receipt_mode = "standalone_full_validation"
            output_manifest = str(cache.manifest_path)
            output_manifest_hash = cache.cache_hash
            output_phase2 = str(cache.phase2_manifest_path)
            output_phase2_hash = cache.phase2_manifest_hash
            receipt_epochs = len(cache.members)
            receipt_entries = len(cache.epoch_map)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "invalid",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                    "elapsed_seconds": round(time.time() - started, 3),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2
    print(
        json.dumps(
            {
                "status": "valid",
                "cache_manifest": output_manifest,
                "cache_manifest_sha256": output_manifest_hash,
                "phase2_manifest": output_phase2,
                "phase2_manifest_sha256": output_phase2_hash,
                "epochs": receipt_epochs,
                "route_epoch_entries": receipt_entries,
                "validation_mode": receipt_mode,
                "validation_receipt": str(receipt_path) if receipt_path is not None else None,
                "validation_receipt_sha256": sha256_file(receipt_path) if receipt_path is not None else None,
                "elapsed_seconds": round(time.time() - started, 3),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
