# Recovery validation — 2026-09-09

Scope: code repair and research-gap audit, not a production launch or completed reproduction. Historical r1–r19 artifacts were read only. The main agent used run-lean-team to split cache implementation from runner integration and obtain an independent read-only review.

## Evidence established

- r19 lifecycle has `terminal_validated` at 2026-09-05T17:00:57+07:00; the two recorded child execution digests are `73d17e980d135f2a9bae55cbd6343117480012f9909655aef7934338876af43e` and `1e0296782dfd483db4bbad2e2fc23d92053a8d62888298950d38ec23eb988ba2`. These are cap128 pilot results, not a full numerical replication. This pass did not rerun their standalone verifiers.
- Manifest-only planning on the real cohort: 11.888 seconds, peak traced Python allocations 17.551 MiB. Six selected subjects SC433/SC449/SC408/SC430/SC448/SC437, each train split capped at128. No plan file, runtime namespace, production marker or training process was created by that measurement.
- Full cache payload declared by the manifest: 267,895,111,680 bytes (249.497 GiB). The entire payload was not rescanned in this repair pass.
- The new live host-capacity probe was invoked through the locked WSL interpreter. It reached Windows successfully and refused insufficient physical memory. This is a correctly refused probe, not a passed launch gate.
- Follow-up Windows observation at 2026-09-09T19:40:09+07:00: free RAM 2,290.8 MiB and commit headroom 11,530.2 MiB. Physical memory is still below the current 4,096 MiB admission threshold. This is an observation, not a reserved resource budget.

## Tests run

Host interpreter: project `.venv/Scripts/python.exe`. Locked interpreter: `/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python` on Ubuntu WSL. Test fixtures use temporary directories, not historical run directories.

| Command group | Host | Locked WSL |
|---|---|---|
| `test_recovery_20260909` after receipt/setup fixes | 14 passed | 14 passed |
| `test_subject_generalization`, `test_r18_gpu_admission` | 15 passed | 15 passed |
| `test_trainer_contract`, `test_verify_run`, `test_execution_corrections`, `test_multi_seed`, `test_r19_gpu_admission` | 54 discovered, 50 passed, 4 skipped | 54 discovered, 52 passed, 2 skipped |
| First combined cache/scaffold/recovery check before final immutable-snapshot fix | 51 discovered, 44 passed, 7 skipped | 51 discovered, 50 passed, 1 skipped |
| Explicit E-drive cache path/provenance test with `SLEEP_STAGE_TEST_E_ROOT=/mnt/e/blp/sleep_stage_reproduction/tmp` | Not applicable | 1 passed |
| Final combined cache/recovery/subject/GPU-admission/scaffold check, after all reviewed fixes | 60 discovered, 53 passed, 7 skipped (6.965 seconds) | 60 passed, no skips (77.888 seconds); explicit E-drive fixture enabled |

The counts above are separate invocations and overlap; do not add them as unique tests. Platform-/mount-/historical-fixture-dependent verification tests account for the four host/two WSL skips in the 54-test group. Host scaffold also skips six TensorFlow-dependent tests; those executed in locked WSL. The WSL scaffold run used `CUDA_VISIBLE_DEVICES=-1`, so its CUDA/no-device log is expected and is **not** evidence of GPU failure. It exercises small CPU TensorFlow fixtures, not the research training workload.

The new recovery tests cover seeded temporal sampling/order invariance, cap boundaries, byte-identical plan/execution payloads, unapproved configuration drift, write-once protocol publication, stale/future/invalid receipts, failed GPU probes, no loading on bad admission, split reconstruction in the verifier, own/peer GPU PID handling, environment enforcement/restoration, peer-collision preservation, expiry during runtime import, and durable pre-dispatch setup failure records.

## Independent review

Reviewer task: `01a08618-14e8-7113-aabe-cd7610c78924` (read-only, distinct from writer).

Initial findings:

1. P1: tensor could be replaced between hash and load, then consumed with the old identity.
2. P2: receipt could expire between its initial check and actual cache load.
3. P2: partial marker/setup failure could occupy a runtime namespace without a failure record.

Findings2/3 were repaired and independently rechecked: reviewer ran all14 recovery tests successfully and reported no additional material finding in that targeted scope. Finding1 was repaired using bounded verified snapshots. Follow-up review also required validating NPY headers before allocation and enforcing writer-consistent chunk boundaries. Those refinements are implemented. The reviewer independently ran the final cache suite (17 passed, one expected E-drive integration skip) and reported no material finding in that targeted scope. This is code-review signoff, not production-GPU or research-result acceptance.

## Remaining limits and launch decision

- No full-cache, full GPU workload, full-cohort metrics, new seed/fold training, cloud purchase or upload occurred.
- Immutable snapshots bind the exact consumed bytes; they do not make the filesystem itself immutable. The cache-owned memory limit does not include temporary decoding buffers, metadata, TensorFlow, or views retained by a caller. Real peak memory and throughput still need measurement.
- CPU/unit tests do not establish GPU admission behavior on every WSL/WDDM configuration. GPU process visibility is explicitly partial; unknown peers are not silently accepted.
- The subject runner remains a capped engineering smoke test. Full held-out evaluation and the actual study budget are still required by the four-week plan.
- Numerical equivalence to the manuscript is not guaranteed: environment, unspecified/inferred parameters, microbatch/BatchNorm semantics and clipping must remain visible deviations.
- Launch decision for this pass: **not launched**. Resource availability and bounded live workload validation are still required. Research objective is not marked complete.

## Final cache review and regression results

The final integration command was `python -m unittest paper_faithful.training.tests.test_cache_loader paper_faithful.training.tests.test_recovery_20260909 paper_faithful.training.tests.test_subject_generalization paper_faithful.training.tests.test_r18_gpu_admission paper_faithful.training.tests.test_training_scaffold`. On Windows, `python` in this notation is the project's `.venv/Scripts/python.exe`. On WSL it is the locked interpreter above, with `CUDA_VISIBLE_DEVICES=-1` and `SLEEP_STAGE_TEST_E_ROOT=/mnt/e/blp/sleep_stage_reproduction/tmp`. Both returned exit 0. Printed injected-failure JSON is expected from failure-path tests. The final WSL run executed all 60 cases without skips.

Cache regression coverage includes numeric/read-only values, shared membership, bounded finite checks, cache eviction without invalidating retained views, replacement between snapshot read and decode, changed files on future misses, oversized inputs, malicious/malformed NPY headers rejected before allocation, C-order/exact payload checks, writer chunk boundaries, source changes during validation, and Windows-to-WSL serialized path/provenance handling. The real cache manifest declares `chunk_epochs=32` and 18,471 chunks; its final partial chunk spans 22 epochs. Full production-cache compatibility still requires its ordinary full validation; synthetic fixtures and manifest inspection do not replace that scan.

Final independent review closed the original P1 and both follow-up cache refinements, with no material finding in the inspected changes. The two agents were closed after their bounded assignments completed. This repair-pass contract can be marked verified; the overall research objective remains incomplete.

### Tested source SHA-256

Paths are relative to `paper_faithful/training/`. These identify the code tested in this pass, not a new production launch approval.

| File | SHA-256 |
|---|---|
| `cache_loader.py` | `67d578410c1e8b7a3d5b447e67a5a53619c3713fcb91939dc45e02cce0cced93` |
| `subject_generalization.py` | `f39333322ea23507457122110ee3549bec029f350e95d8dcdc5ed1869379af37` |
| `subject_generalization_runner.py` | `18ec9b4b6921cebe6b8b0c6dc1c872b3f3cd385e0ea1666bc0044b622f970fc7` |
| `trainer.py` | `4912f6140c7b09e232e9c74122dc1c8c2185b6449f3c29a212f021cce3d02a0b` |
| `verify_run.py` | `092126d0d5bd893b89399636e77d05b081677466888836917795c103c170a831` |
| `tests/test_cache_loader.py` | `b901b0df105f43b001ecf7cca267caf4aba7b6aa0cbd464d33e6f1485be0c594` |
| `tests/test_recovery_20260909.py` | `182f0113b9facc39ddda165a0f630c58015790e2fe80053d343dd05e212d2791` |
