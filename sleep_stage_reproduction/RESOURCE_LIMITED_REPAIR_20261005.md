# Resource-limited subject pilot repair — 2026-10-05

## What failed

The fresh v9 pilot was correctly refused before runtime initialization. Its preflight snapshot had 4216.3 MB available physical memory, but the full finalized-cache validation then performed a very large tensor/metadata scan in the same process. The live capacity gate after that scan observed less than the 2048 MB safety threshold. No runtime namespace, child fold, checkpoint, or training result was created.

The earlier diagnostic also found that per-file `Path.resolve()` calls crossed the WSL/Windows E-drive boundary for thousands of cache artifacts. That created an avoidable metadata bottleneck.

## Repair implemented

1. Finalized-cache child paths are now normalized lexically after the approved cache root is trusted. Root escape and symlinked-leaf checks remain fail-closed; the expensive per-child `Path.resolve()` loop is gone.
2. `validate_cache_cli.py` can now run the complete integrity scan in a standalone process and publish `FULL_CACHE_VALIDATION_RECEIPT_V1` with atomic create-only semantics.
3. The receipt binds the cache manifest, Phase-2 manifest, completion marker, every tensor and sidecar, tensor byte lengths/shapes/dtypes, and hashes. The training process uses the receipt-bound index instead of retaining the validator's scan memory.
4. Tensor bytes are still hash-checked on first use by `CanonicalCache.array`; the receipt is not a blanket trust bypass.
5. The reviewed protocol and standalone verifier bind the receipt path and SHA-256. A missing receipt is refused for a new execution.
6. Live capacity refusal messages now include the observed host values, so a future refusal is diagnosable rather than just saying “gate failed”.
7. A compact profile now retains only receipt-bound chunks containing the reviewed cap32 fold members. It still validates every selected sidecar and preserves fail-closed chunk-boundary semantics.

## Verification performed

Command:

```text
python -m unittest paper_faithful.training.tests.test_cache_loader paper_faithful.training.tests.test_resource_limited_subject_generalization paper_faithful.training.tests.test_recovery_20260909 paper_faithful.training.tests.test_subject_generalization paper_faithful.training.tests.test_verify_run
```

Result: **62 tests passed; 5 skipped** (the skipped cases require explicit WSL/GPU fixtures).

Compilation also passed for the modified loader, validator CLI, subject runner, and verifier.

## Evidence-driven plan transition

- Plan 1 (fresh full validator): stopped once, safely, after the host dropped below the memory safety floor. No research namespace was created.
- Plan 2 (receipt-only full index): prior valid validator evidence produced `full-cache-validation-receipt-plan2c-prior-20261005.json` (SHA-256 `0333aebc3320361e66b1603affd06e602a8bc65d2696028c0b40d268ad98270a`). Loading all 583,965 entries still failed the live 2,048-MB capacity gate at 1,668.023 MB available.
- Plan 3 (compact selected cache): the no-training canary passed with 2,464 required members, 64,337 retained members, 193,011 entries, and 32.008 seconds load time. Its low-headroom WSL attempt was then stopped before runtime after a verified 9p metadata stall; no historical run was retried or reused.
- Plan 4 (low-compute compact metadata): focused tests passed (65 tests, 5 skipped). The fresh profile uses `RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V3_LOW_COMPUTE`: Stage 1 microbatch 32 with four-step gradient accumulation (effective batch 128), Stage 2 microbatch 128, and Stage 3 microbatch 1 with the existing 128-step global-norm protocol. The compact metadata receipt is `E:/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan4-low-compute-metadata-20261005.json` (SHA-256 `c31eea4d496dcfe0c6e7cb21f3c2d0f5d9a7ac7f69741af6d24f6e057bcacc95`). The locked WSL canary passed with 2,464 required members, 64,337 retained members, 193,011 entries, and 87.148 seconds load time under 1,536-MB physical / 3,072-MB commit floors. The reviewed plan is `E:/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan4-low-compute-v1-cap32-e6-20261005.json` (SHA-256 `ff8fc2c7993eaaf8b5a5d27bbf4d6d7b56f5335bd03fb7e0eed4f2cae6947fd6`).
- Plan 4 dispatch was then refused before runtime: after cache loading, the live host gate saw 1,210.605 MB available physical memory against the 1,536-MB floor. No Plan 4 runtime or child fold was created, and Plan 4 was not retried.
- Plan 5 (lower compute): the fresh profile `RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V4_LOW_COMPUTE` lowers Stage 1 to microbatch 16 with eight-step accumulation (effective batch 128); Stage 2 remains 128 because the contrastive objective has not been adapted. Its locked WSL canary passed with 2,464 required members, 64,337 retained members, 193,011 entries, 86.435 seconds cache load, and 91.348 seconds total under 1,024-MB physical / 2,048-MB commit floors. The reviewed Plan 5 protocol is `E:/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan5-lower-compute-v1-cap32-e6-20261005.json` (SHA-256 `f61d4efa6954bcdfa9e67628196f1e565e410f6e99f02e8be0e3fe51fcd3b097`).
- Plan 5 then stopped before its first fold because the TF2.4 scalar GPU admission probe falsely reported CPU placement; no fold was accepted and Plan 5 was not retried.
- Plan 6 (GPU probe fixed): the admission probe now uses a one-element `tf.ones((1,))`, which TF2.4 actually places on the RTX 3050. The real locked-TF2.4 GPU-only canary passed, focused tests passed (65 tests, 5 skipped), and the reviewed Plan 6 protocol is `E:/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan6-gpu-fixed-v1-cap32-e6-20261005.json` (SHA-256 `1a5de8a6099c0e8bca5c2af3c359940df2a73af1b943d7218bab76f0e6b7f5c6`).

- Plan 6 terminal interruption: the fresh namespace was dispatched exactly once and entered fold 0 (`SC433`, validation `SC449`). It did not produce a checkpoint, summary, failure sidecar, or verified fold. Windows rebooted at `2026-10-05T14:41:40+07:00`; immediately afterward WSL reported `up 0 min`, and its kernel log recorded an unclean journal shutdown. The exact WSL/Python workload process was absent after the reboot. This is an external host interruption, not evidence of a successful or failed model result; Plan 6 is consumed and must not be resumed or reused.

- Plan 7 continuation policy: use a new protocol/run prefix with the same reviewed scientific cap32/6-epoch/six-fold design, launch detached from the interactive terminal, and treat any subsequent host reboot as a terminal failure without automatic retry.

- Plan 7 terminal blocker: the detached launch itself worked and WSL PID 386 started with the locked TF2.4 runner, but the runner never reached runtime initialization. It entered `Ds+` state at `p9_client_rpc` while reading the E: cache; `/proc/386/io` reported `read_bytes` unchanged at `224833536` over a 30-second observation. No Plan 7 runtime namespace, child fold, checkpoint, or training/GPU fit was created. The process was terminated after the verified stall and evidence was written to `E:/blp/sleep_stage_reproduction/runtime/reviews/subject-generalization-plan7-terminal-blocker-20261005.json` (SHA-256 `65ee477d6c06781ba87501c17061c29f307f5ec478798ded52ef370d685769d2`). Plan 7 is consumed exactly once and must not be retried, resumed, or reused.

- Current conclusion: the remaining blocker is cache transport through WSL/DrvFS 9p, not the model's RAM profile or GPU admission. The next viable research change is to stage the receipt-bound compact cache on a Linux-native filesystem before training, but that is a new transport design and is outside the consumed Plan 7 run.

The fresh plan is published at `E:/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan3-compact-offline-cap32-e6-20261005.json` with SHA-256 `c848d8f55c89a2dde19d1341db9ca288ded5ce6e92313d80cab2ba2b8cea5bc2`. Historical r1–r19 runs are not modified, resumed, or reused.
