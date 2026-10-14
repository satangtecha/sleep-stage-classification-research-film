# Bounded executable training

## Recovery changes (2026-09-09)

See `../../RECOVERY_PLAN_20260909_TH.md` for the dated research scope. Historical r1-r19 artifacts are not changed or resumed. The subject runner is still an **engineering smoke pilot**, not full held-out evaluation.

For new subject plans, first run the standalone full-cache validator with `--write-receipt <fresh-receipt-path>`. It validates the complete cache in its own process and publishes `FULL_CACHE_VALIDATION_RECEIPT_V1` with create-only semantics. Then use `--cache-validation-receipt <fresh-receipt-path>` with `--plan-only --protocol-output <fresh-path>`; the reviewed protocol binds the receipt SHA-256. Training requires the same receipt, protocol, and `--approved-protocol-sha256 <digest>`. The runner loads the receipt-bound index without retaining the validator's tensor-scan memory; each tensor is still hash-checked on first use. Old v1-v4 plans use a different sampling policy and must not be treated as approvals of the new code.

When the full receipt-bound index itself exceeds the live workstation memory gate, use the explicitly versioned `RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V1` profile. It derives the exact union of the reviewed fold members, retains only receipt-bound chunks containing those members, and still validates selected sidecars and first-use tensor hashes. Chunk boundaries may retain neighboring epochs; this is recorded as a compact selected-cache execution, not as a full-cache claim. The profile runs one fold at a time and remains an engineering smoke pilot rather than a paper-exact result.

If the machine fluctuates just below the V1 2,048-MiB admission floor before loading, the separately versioned `RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V2_LOW_HEADROOM` profile may be used only as a low-headroom engineering pilot (1,536-MiB physical / 3,072-MiB commit floor). It does not relax tensor integrity checks or permit concurrent folds.

Generate and execute the plan from the same locked WSL interpreter and absolute input paths; a Windows-path plan is not interchangeable with a WSL-path plan. `--runtime-root` must equal `<bulk-root>/runtime/<run-prefix>`. Resource evidence is checked again immediately before tensor loading, so a slow interpreter import cannot reuse an expired receipt. An interrupted setup consumes its namespace and records `failure.json` when storage is writable; it never overwrites another caller's run.

Sampling v2 is label-blind, seeded and spread over recordings, subject-balanced where the cap permits. Validation and test are capped only because this runner is a smoke test; do not report their scores as full-cohort generalization. Production study evaluation must include complete held-out sets in a separately reviewed protocol.

Resource receipts must be no more than 120 seconds old, timezone-aware, and bind successful GPU probes. Host RAM/commit/AC/storage are checked again live after cache validation and before every stage. GPU admission accepts the current Linux PID, refuses other/unknown owners, and explicitly does not claim complete WSL/WDDM process visibility. Live hardware training with these repairs remains to be measured; unit tests are not that evidence.

Cache access now uses verified read-only snapshots, not persistent file-backed memmaps. Each miss hashes the exact bytes subsequently decoded. The default cache retains at most eight arrays and 128 MiB of array payload; temporary decoding buffers, metadata, and caller-retained views are additional memory. Tensor headers and exact payload length are validated before allocation, with a 128 MiB per-tensor payload ceiling. Canonical 32-epoch chunks fit this bound. Measure end-to-end memory and I/O before claiming a throughput improvement.

## Legacy CLI reference

The commands below describe existing CLI capabilities. Their resume support is not evidence of interruption-equivalent research recovery. The current recovery plan does not enable resume or authorize changing historical r1-r19 runs.

`smoke` runs the existing synthetic Stage 1/2/3 gradient/model smoke and returns a pass/fail result:

`python -m paper_faithful.training.cli smoke --protocol AUTHOR_CODE_V1`

`pilot` runs the actual pipeline after finalized-cache validation, with a deterministic per-split membership cap. `full` runs the actual pipeline only against the exact, complete cache and rejects any cap other than 128. Both require an E-drive bulk root, safe run ID, and use `--stage stage1|stage2|stage3|all`.

`python -m paper_faithful.training.cli pilot --cache-manifest E:\cache\sst_full_cohort_run_manifest.json --bulk-root E:\blp\sleep_stage_reproduction --run-id pilot-01 --stage all --weight-decay 0.0`

Stage 1 uses AdamW-recipe learning rate .05 and requires a supplied weight-decay assumption. Stage 2 uses SGD .1 and supervised contrastive temperature .05 with integer labels. Stage 3 uses SGD .1 and sparse categorical cross-entropy. Nominal batch is 128 and faithful batches drop remainder. A smaller Stage 1 or Stage 3 hardware microbatch must divide 128 and uses recorded gradient accumulation so the optimizer still receives one averaged nominal-batch update; it is labelled a hardware adaptation rather than paper-exact. The current resource-limited Plan 4 uses Stage 1 microbatch 32 with four-step accumulation, retains Stage 2 at 128 because the contrastive objective has not been adapted, and retains Stage 3's global-norm protocol. Stage 2 below 128 is refused unless the implemented `adapted_pairwise_objective` is explicitly selected and recorded; it is not an exact-embedding run. Every fit includes immediate NaN termination and refuses incomplete or non-finite history even if an earlier checkpoint exists.

PAPER uses 20 epochs/stage and ReduceLROnPlateau .2/1/1e-4. AUTHOR uses 20/20/50 and .5/5/1e-6 plus EarlyStopping(30, best validation loss). No class weights are applied. PAPER routes Stage 1/2 to `PAPER_PRETRAIN_V1` and Stage 3 to `PAPER_STAGE3_V1`; AUTHOR uses `AUTHOR_CODE_V1` in all stages.

`pilot` and `full` require hashable `--source-manifest` and `--environment-manifest` files. The execution record binds those hashes, the cache/Phase-2 manifest hash, split hashes, seed, per-stage batches/adaptations, checkpoint lineage, and progress. Resuming requires the latest `execution.json` to contain a valid next-stage/checkpoint record; completed records cannot be changed. A standalone Stage 2/3 run additionally requires `--checkpoint` and hash-bound `--parent-metadata` JSON.

After a run completes, verify the persisted source/environment/data/cache bindings, immutable configuration, split hashes, every checkpoint and metrics hash, metric provenance, and Stage 1 -> 2 -> 3 lineage with:

`python -m paper_faithful.training.verify_run --run-dir /mnt/e/blp/sleep_stage_reproduction/runs/<run-id>`

The verifier refuses incomplete runs by default. `--allow-incomplete` is diagnostic-only and still validates every artifact currently recorded.

Stage 1 and Stage 3 classification metrics evaluate their complete validation/test splits. Stage 2 silhouette uses a fixed-seed, bounded uniform reservoir (cap 4,096) because exact pairwise silhouette is quadratic; its artifact records the full split sample count, retained count, seed, cap, and base epoch-membership hash. Each stage writes a separate hash-bound metric artifact and the execution record retains all per-stage checkpoint/metric bindings. The loader invokes SST's finalized Phase-2 gate, validates every source/shard/marker binding, writer-exact sidecars, finite float32 tensors, all three routes, and complete non-overlapping coverage. Runs persist an immutable contract hash and only transition planned → running → completed/failed; failed records include type, message, and fingerprint. Resume accepts only matching running/failed records.
