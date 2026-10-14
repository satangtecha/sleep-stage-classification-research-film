# Record-bounded SST cache engineering gate

## Runtime environment contract

All SST preprocessing, cache, and SST test commands require the selected isolated Python **3.12.x** environment on E:, currently `E:\blp\sleep_stage_reproduction\envs\ssqueezepy-0.6.6\Scripts\python.exe`, installed from `requirements-sst-pinned.txt` (including `ssqueezepy==0.6.6`, `numpy==2.5.2`, `numba==0.67.0`, `llvmlite==0.49.0`, and `scipy==1.18.0`). The project host `.venv` may run control tests, but is not the declared SST reproduction runtime unless it matches those selected pins.

Python 3.7 is solely the separate `AUTHOR_CODE_V1` TensorFlow training compatibility environment. It is not an SST dependency environment: passing stdlib or control-path tests there must not be interpreted as SST stack compatibility or SST-runtime reproduction.

`cache_writer.py` writes only a bounded chunk from one preprocessed record NPZ shard. It never concatenates records. The sole supported executable for a full cohort is `python -m paper_faithful.sst.cohort_cache run-full`.

Routes are explicit: `PAPER_PRETRAIN_V1` uses PAPER_TEXT slot 0 with 12 windows at stride 249; `PAPER_STAGE3_V1` uses PAPER_TEXT slot 0 with 15 windows at stride 192; `AUTHOR_CODE_V1` uses AUTHOR_CODE slot 1 with 15 windows at stride 192. Each cache tensor is `float32 [epochs, windows, 64, 64, 2]` and has a JSON sidecar preserving record/subject/local-epoch identities, labels, source hash, configuration hash, and tensor hash.

The writer requires a canonically resolved E-drive destination, rejects traversal or symlink escapes, reserves 100 GiB before writing, and acquires an exclusive per-chunk lock before publishing temporary tensor and sidecar files. Resume is accepted only when tensor shape/dtype/hash and all sidecar provenance match. An interrupted, partial, concurrently locked, corrupted, or mismatched output fails closed.

`SST_CACHE_CHUNK_V2` binds every chunk to the exact transform identity: callable, source hash, Python, NumPy, ssqueezepy 0.6.6, FFT settings, normalization, and resize contract. Custom transforms must supply an explicit identity, so a changed transform cannot silently reuse an old cache.

`aggregate_storage_estimate()` reports payload estimates for selected routes; `worker_plan()` only caps an optional future worker count and does not execute records concurrently.

## Full cache command

Run only after Phase 2 has produced a successful full-cohort result:

```powershell
python -m paper_faithful.sst.cohort_cache run-full --phase2-manifest E:\blp\sleep_stage_reproduction\preprocessed\sleep-edfx\1.0.0\sleep-cassette\paper_faithful_v1\manifests\preprocessing_result.json --cache-root E:\blp\sleep_stage_reproduction\sst_cache
```

`run-full` always processes exactly `PAPER_PRETRAIN_V1`, `PAPER_STAGE3_V1`, and `AUTHOR_CODE_V1`; it accepts no route subset. It preflights the exact 267895111680-byte (249.496765-GiB) payload plus the 100-GiB reserve before its first write. The command requires a `status=complete` Phase-2 result with the exact completion-marker contract, and its sibling `COMPLETED.json` (`schema_version: "1.0"`, `status: "complete"`, `preprocessing_result: "manifests/preprocessing_result.json"`, and `preprocessing_result_sha256` matching the exact manifest bytes). It verifies every listed shard's filename, resolved containment, SHA-256, x/y/row epoch consistency, canonical `SC####` record/subject identity, and the aggregate derived from validated shard labels (153 recordings, 78 subjects, 194655 epochs, and the exact W/N1/N2/N3/REM counts). Each sidecar and the run manifest bind both Phase-2 and completion-marker hashes.

## Explicit hard-crash recovery

After a hard termination, do not rerun blindly. Inspect one deterministic chunk explicitly:

```powershell
python -m paper_faithful.sst.cohort_cache recover-chunk --cache-root E:\blp\sleep_stage_reproduction\sst_cache --record-id SC4001 --route PAPER_PRETRAIN_V1 --start-epoch 0 --end-epoch 32
```

Recovery reads the lock PID and fails closed when liveness cannot be verified or the owner is live. For a dead owner it removes only that stale lock, target-matching temporary files, and an unpublished one-sided tensor/sidecar (including the crash window after tensor replace and before sidecar replace). A complete tensor/sidecar pair is preserved unconditionally. The JSON command result is the recovery audit record.

For an interrupted full run, use `recover-run-lock --cache-root ...`. It removes only a schema-valid full-run lock whose owner is verified dead; it never clears a live or unverifiable lock.
