"""Canonical all-route SST cohort cache orchestration."""
from __future__ import print_function
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import numpy as np

from .cache_manifest import RECORD_ID_RE, ROUTES, CacheContractError, cache_stem, load_record_shard, sha256_file
from .cache_writer import CacheCollisionError, ensure_aggregate_capacity, write_record_chunk
from .storage import require_e_drive

EXPECTED = {"recordings": 153, "subjects": 78, "epochs": 194655, "class_counts": {"W": 65795, "N1": 21469, "N2": 68633, "N3": 12991, "REM": 25767}}
FULL_ROUTES = ("PAPER_PRETRAIN_V1", "PAPER_STAGE3_V1", "AUTHOR_CODE_V1")
FULL_PAYLOAD_BYTES, FULL_PAYLOAD_GIB, RUN_LOCK_NAME = 267895111680, 249.496765, ".sst_full_cohort.lock"
LABEL_NAMES = ("W", "N1", "N2", "N3", "REM")
PHASE2_PROTOCOL_ID = "SLEEP_EDF_CASSETTE_PAPER_FAITHFUL_PREPROCESSING_V1"
PHASE2_RESULT_KEYS = {
    "schema_version", "protocol_id", "run_scope", "parameters", "aggregate",
    "parity", "status", "completion_marker", "records", "provenance", "failures",
}
SC4362_ZERO_EPOCH_EXCLUSION = {
    "reason": "author_tail_slice_zero",
    "raw_samples": 6798000,
    "overflow_label": "W",
    "overflow_epochs": 504,
    "annotation_start_sample": 5238000,
    "annotation_end_sample": 8310000,
    "author_code_tail_slice": "labels[:-0] produces an empty label array",
}

class CohortCacheError(ValueError): pass

def _contained(root, candidate):
    root, candidate = root.resolve(strict=False), candidate.resolve(strict=False)
    try: candidate.relative_to(root)
    except ValueError as error: raise CohortCacheError("path escapes its declared root: {0}".format(candidate)) from error
    return candidate

def _load_json(path, description):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error: raise CohortCacheError("{0} is not readable JSON".format(description)) from error

def _completion_binding(manifest, result):
    run_root, contract = manifest.parent.parent, result.get("completion_marker")
    if not isinstance(contract, dict) or contract != {"path": "COMPLETED.json", "required_for_eligibility": True, "published_only_when_status": "complete"}:
        raise CohortCacheError("Phase-2 result completion_marker contract is invalid")
    marker = _contained(run_root, run_root / "COMPLETED.json")
    if not marker.is_file(): raise CohortCacheError("Phase-2 COMPLETED.json is absent")
    content = _load_json(marker, "Phase-2 COMPLETED.json")
    if set(content) != {"schema_version", "status", "preprocessing_result", "preprocessing_result_sha256"} or content.get("schema_version") != "1.0" or content.get("status") != "complete" or content.get("preprocessing_result") != "manifests/preprocessing_result.json" or content.get("preprocessing_result_sha256") != sha256_file(manifest):
        raise CohortCacheError("Phase-2 COMPLETED.json schema, status, path, or result hash is invalid")
    return {"path": marker, "sha256": sha256_file(marker)}

def _validate_phase2_result_schema(result):
    if not isinstance(result, dict) or set(result) != PHASE2_RESULT_KEYS:
        raise CohortCacheError("Phase-2 result top-level fields do not match the declared schema")
    if result.get("schema_version") != "1.0" or result.get("protocol_id") != PHASE2_PROTOCOL_ID:
        raise CohortCacheError("Phase-2 result schema version or protocol ID is invalid")
    if not isinstance(result.get("parameters"), dict):
        raise CohortCacheError("Phase-2 result parameters must be an object")
    provenance = result.get("provenance")
    if (not isinstance(provenance, dict) or
            any(not isinstance(provenance.get(name), list) for name in ("source", "assumption", "unknown"))):
        raise CohortCacheError("Phase-2 result provenance is missing required arrays")


def _is_sc4362_zero_epoch_compatibility_row(row):
    """Permit exactly the audited SC4362 paper-count compatibility exception."""
    return (
        row.get("record_id") == "SC4362"
        and row.get("subject_id") == "SC436"
        and row.get("epochs") == 0
        and row.get("processing_status") == "excluded_author_tail_slice_zero"
        and row.get("compatibility_exclusion") == SC4362_ZERO_EPOCH_EXCLUSION
        and row.get("class_counts") == dict.fromkeys(LABEL_NAMES, 0)
    )

def load_phase2_binding(manifest_path):
    manifest = Path(manifest_path).resolve(strict=True); result = _load_json(manifest, "Phase-2 result manifest")
    _validate_phase2_result_schema(result)
    if result.get("status") != "complete": raise CohortCacheError("Phase-2 result status must be complete")
    completion = _completion_binding(manifest, result); parity = result.get("parity")
    if not isinstance(parity, dict) or parity.get("eligible") is not True or parity.get("matches_expected") is not True or result.get("failures") != [] or result.get("run_scope", {}).get("mode") != "full_cohort" or parity.get("expected") != EXPECTED:
        raise CohortCacheError("Phase-2 result is not an eligible, exact full-cohort completion")
    records, listed = result.get("records"), result.get("run_scope", {}).get("record_ids")
    if not isinstance(records, list) or not isinstance(listed, list) or len(records) != 153 or len(listed) != 153 or len(set(listed)) != 153: raise CohortCacheError("Phase-2 manifest must list exactly 153 distinct records")
    shard_root = _contained(manifest.parent.parent, manifest.parent.parent / "shards"); bindings, seen, names, subjects = [], set(), set(), set()
    actual_epochs, actual_class_counts = 0, dict.fromkeys(LABEL_NAMES, 0)
    for row in records:
        if not isinstance(row, dict): raise CohortCacheError("Phase-2 records contains a non-object row")
        record_id, subject_id, name, digest, epochs = row.get("record_id"), row.get("subject_id"), row.get("shard"), row.get("shard_sha256"), row.get("epochs")
        compatibility_zero = _is_sc4362_zero_epoch_compatibility_row(row)
        if (not isinstance(record_id, str) or not RECORD_ID_RE.fullmatch(record_id) or record_id in seen or record_id not in listed or not isinstance(subject_id, str) or subject_id != record_id[:5] or not isinstance(name, str) or Path(name).name != name or not name.endswith(".npz") or name in names or not isinstance(digest, str) or len(digest) != 64 or not isinstance(epochs, int) or epochs < 0 or (epochs == 0 and not compatibility_zero) or (epochs > 0 and (row.get("processing_status") != "emitted" or row.get("compatibility_exclusion") is not None))): raise CohortCacheError("Phase-2 record binding is missing, duplicate, or malformed")
        shard = _contained(shard_root, shard_root / name)
        if not shard.is_file() or sha256_file(shard) != digest: raise CohortCacheError("listed shard is missing or hash-mismatched: {0}".format(name))
        identity = load_record_shard(shard)
        x_epochs, y = int(identity["x"].shape[0]), np.asarray(identity["y"])
        y_epochs = int(y.shape[0]) if y.ndim == 1 else -1
        if identity["record_id"] != record_id or identity["subject_id"] != subject_id or x_epochs != y_epochs or y_epochs != epochs:
            raise CohortCacheError("listed shard identity or epoch count mismatch: {0}".format(name))
        counts = np.bincount(y, minlength=len(LABEL_NAMES))
        if counts.shape[0] != len(LABEL_NAMES):
            raise CohortCacheError("listed shard labels are outside the canonical mapping: {0}".format(name))
        actual_epochs += y_epochs
        for label, count in zip(LABEL_NAMES, counts): actual_class_counts[label] += int(count)
        subjects.add(identity["subject_id"])
        seen.add(record_id); names.add(name); bindings.append({"record_id": record_id, "subject_id": subject_id, "path": shard, "shard_sha256": digest, "epochs": y_epochs})
    if seen != set(listed) or {path.name for path in shard_root.glob("*.npz")} != names: raise CohortCacheError("records and shard directory do not bind the same IDs")
    actual_aggregate = {"recordings": len(seen), "subjects": len(subjects), "epochs": actual_epochs, "class_counts": actual_class_counts}
    if actual_aggregate != result.get("aggregate") or actual_aggregate != EXPECTED:
        raise CohortCacheError("validated shard aggregate does not match the manifest and canonical full-cohort expectation")
    return {"manifest_path": manifest, "manifest_sha256": sha256_file(manifest), "completion_marker_path": completion["path"], "completion_marker_sha256": completion["sha256"], "bindings": sorted(bindings, key=lambda item: item["record_id"])}

def _provenance(binding, phase2):
    return {"phase2_manifest_sha256": phase2["manifest_sha256"], "phase2_manifest_path": str(phase2["manifest_path"]), "completion_marker_path": str(phase2["completion_marker_path"]), "completion_marker_sha256": phase2["completion_marker_sha256"], "record_binding": {"record_id": binding["record_id"], "subject_id": binding["subject_id"], "shard_path": str(binding["path"]), "shard_sha256": binding["shard_sha256"], "epochs": binding["epochs"]}}

def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0: raise CohortCacheError("lock PID is not verifiable")
    if os.name != "nt":
        try: os.kill(pid, 0)
        except ProcessLookupError: return False
        except PermissionError as error: raise CohortCacheError("lock PID cannot be verified") from error
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong)
    open_process.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = open_process(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87: return False
        raise CohortCacheError("lock PID cannot be verified on Windows")
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)): raise CohortCacheError("lock PID cannot be verified on Windows")
        return code.value == 259
    finally: kernel32.CloseHandle(handle)

def _lock_contract(phase2, chunk_epochs):
    return {"schema_version": 1, "pid": os.getpid(), "phase2_manifest_sha256": phase2["manifest_sha256"], "completion_marker_sha256": phase2["completion_marker_sha256"], "routes": list(FULL_ROUTES), "chunk_epochs": chunk_epochs, "payload_bytes": FULL_PAYLOAD_BYTES}

def _acquire_run_lock(output, metadata):
    lock = _contained(output, output / RUN_LOCK_NAME)
    try: fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        existing = _load_json(lock, "full-run lock")
        if existing != metadata or _pid_alive(existing.get("pid")): raise CohortCacheError("a concurrent or incompatible full-run lock exists") from error
        raise CohortCacheError("a stale full-run lock exists; run recover-run-lock explicitly") from error
    try: os.write(fd, json.dumps(metadata, sort_keys=True).encode("utf-8")); os.fsync(fd)
    finally: os.close(fd)
    return lock

def recover_run_lock(destination):
    root = require_e_drive(destination).resolve(strict=False); lock = _contained(root, root / RUN_LOCK_NAME)
    if not lock.exists(): return {"status": "nothing_to_recover", "lock": str(lock)}
    metadata = _load_json(lock, "full-run lock")
    required = {"schema_version", "pid", "phase2_manifest_sha256", "completion_marker_sha256", "routes", "chunk_epochs", "payload_bytes"}
    if set(metadata) != required or metadata.get("routes") != list(FULL_ROUTES) or metadata.get("payload_bytes") != FULL_PAYLOAD_BYTES: raise CohortCacheError("full-run lock contract is invalid; refusing recovery")
    if _pid_alive(metadata.get("pid")): raise CohortCacheError("full-run lock owner is live")
    lock.unlink(); return {"status": "recovered_stale_run_lock", "lock": str(lock), "contract": metadata}

def run_full_cache(manifest_path, destination, *, chunk_epochs=32, writer=write_record_chunk):
    if chunk_epochs < 1: raise CohortCacheError("chunk_epochs must be positive")
    phase2 = load_phase2_binding(manifest_path); output = require_e_drive(destination).resolve(strict=False); output.mkdir(parents=True, exist_ok=True)
    capacity = ensure_aggregate_capacity(output, EXPECTED["epochs"], FULL_ROUTES)
    if capacity.get("total_bytes") != FULL_PAYLOAD_BYTES or capacity.get("total_gib") != round(FULL_PAYLOAD_GIB, 3) or set(capacity.get("routes", ())) != set(FULL_ROUTES): raise CohortCacheError("full-run capacity estimate does not match canonical all-route payload")
    lock = _acquire_run_lock(output, _lock_contract(phase2, chunk_epochs)); completed = []
    try:
        for binding in phase2["bindings"]:
            for route_name in FULL_ROUTES:
                for start in range(0, binding["epochs"], chunk_epochs):
                    result = writer(binding["path"], output, route_name, start_epoch=start, max_epochs=chunk_epochs, cohort_provenance=_provenance(binding, phase2), expected_source_sha256=binding["shard_sha256"], expected_epoch_count=binding["epochs"])
                    completed.append({"tensor": str(result.tensor_path), "sidecar": str(result.sidecar_path), "resumed": bool(result.resumed)})
        run = {"schema_version": 1, "phase2_manifest_path": str(phase2["manifest_path"]), "phase2_manifest_sha256": phase2["manifest_sha256"], "completion_marker_path": str(phase2["completion_marker_path"]), "completion_marker_sha256": phase2["completion_marker_sha256"], "routes": list(FULL_ROUTES), "chunk_epochs": chunk_epochs, "record_bindings": [_provenance(item, phase2)["record_binding"] for item in phase2["bindings"]], "capacity": capacity, "chunks": completed}
        target = _contained(output, output / "sst_full_cohort_run_manifest.json"); fd, name = tempfile.mkstemp(prefix="sst_full_cohort_run_manifest.", suffix=".json.tmp", dir=str(output)); os.close(fd); temporary = _contained(output, Path(name))
        try: temporary.write_text(json.dumps(run, sort_keys=True, indent=2) + "\n", encoding="utf-8"); os.replace(str(temporary), str(target))
        finally:
            if temporary.exists(): temporary.unlink()
        return run
    finally:
        if lock.exists(): lock.unlink()

def recover_chunk(destination, record_id, route_name, start_epoch, end_epoch):
    if not RECORD_ID_RE.fullmatch(record_id) or route_name not in ROUTES or start_epoch < 0 or end_epoch <= start_epoch: raise CohortCacheError("invalid deterministic chunk target")
    root = require_e_drive(destination).resolve(strict=False); stem = cache_stem(record_id, ROUTES[route_name], start_epoch, end_epoch)
    tensor, sidecar, lock = (_contained(root, root / (stem + suffix)) for suffix in (".npy", ".json", ".lock")); removed = []
    if lock.exists():
        metadata = _load_json(lock, "chunk lock")
        if metadata.get("tensor") != tensor.name or metadata.get("sidecar") != sidecar.name: raise CohortCacheError("lock does not belong to requested chunk")
        if _pid_alive(metadata.get("pid")): raise CohortCacheError("requested chunk has a live lock owner")
        lock.unlink(); removed.append(str(lock))
    if tensor.exists() and sidecar.exists(): return {"status": "preserved_complete_pair", "target": stem, "removed": removed}
    for artifact in (tensor, sidecar):
        if artifact.exists():
            if not artifact.is_file(): raise CohortCacheError("artifact is not a regular file; refusing recovery")
            artifact.unlink(); removed.append(str(artifact))
    for temporary in root.glob(stem + ".*.tmp"):
        temporary = _contained(root, temporary)
        if temporary.is_file(): temporary.unlink(); removed.append(str(temporary))
    return {"status": "recovered" if removed else "nothing_to_recover", "target": stem, "removed": removed}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run-full"); run.add_argument("--phase2-manifest", required=True, type=Path); run.add_argument("--cache-root", required=True, type=Path); run.add_argument("--chunk-epochs", type=int, default=32)
    recover = commands.add_parser("recover-chunk"); recover.add_argument("--cache-root", required=True, type=Path); recover.add_argument("--record-id", required=True); recover.add_argument("--route", required=True, choices=sorted(ROUTES)); recover.add_argument("--start-epoch", required=True, type=int); recover.add_argument("--end-epoch", required=True, type=int)
    stale = commands.add_parser("recover-run-lock"); stale.add_argument("--cache-root", required=True, type=Path); args = parser.parse_args(argv)
    try:
        if args.command == "run-full": outcome = run_full_cache(args.phase2_manifest, args.cache_root, chunk_epochs=args.chunk_epochs)
        elif args.command == "recover-chunk": outcome = recover_chunk(args.cache_root, args.record_id, args.route, args.start_epoch, args.end_epoch)
        else: outcome = recover_run_lock(args.cache_root)
        print(json.dumps(outcome, sort_keys=True)); return 0
    except (CohortCacheError, CacheContractError, CacheCollisionError, OSError, RuntimeError, ValueError) as error: print("ERROR: {0}".format(error), file=sys.stderr); return 2
if __name__ == "__main__": raise SystemExit(main())
