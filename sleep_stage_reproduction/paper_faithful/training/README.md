# Phase 4--6 training scaffold

This directory is a bounded scaffold only. It creates model graphs, deterministic split plans, and compact run manifests; it never downloads data, builds a full SST cache, or starts full training.

## Commands

From `sleep_stage_reproduction` on the host interpreter, run the dependency-free checks:

```powershell
python -m unittest paper_faithful.training.tests.test_training_scaffold
```

In the locked WSL TensorFlow 2.4 environment, run one synthetic CPU/GPU-compatible batch only:

```powershell
cd /mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction
python -m paper_faithful.training.smoke --protocol PAPER_TEXT_V1
python -m paper_faithful.training.smoke --protocol AUTHOR_CODE_V1
```

Bulk run outputs must be below `E:\blp\sleep_stage_reproduction\runs`; `require_bulk_path` rejects drive C by default. The smoke runner creates no files and uses random tensors only.

The accepted manuscript reports Python 3.9 and TensorFlow 2.9, while the released repository declares Python 3.7 and TensorFlow-GPU 2.4. The current GPU smoke evidence belongs to the locked author-code environment. A separate TF 2.9 environment gate is required before a `PAPER_TEXT_V1` training claim.

## Protocol routing

- `PAPER_TEXT_V1`: 12 windows for Stage-1/2 derivation, but 15 segments for Stage 3 as stated later in the manuscript; overlap 64 at Stage 3 is an explicit author-code inference because the manuscript omits it.
- `AUTHOR_CODE_V1`: 15 windows, overlap 64, and 50 Stage-3 epochs.
- `SUBJECT_GENERALIZATION_V1`: grouped subject splitting only; its metric must not be compared directly to the manuscript's reported epoch-random-split result.

`splits.py` sorts immutable membership keys before seeded shuffling, hashes each split's sorted membership, and rejects overlapping epochs. Subject plans also reject overlap by `subject_id`.

## Unresolved reproduction deviations

- The author release extracts the flattened 512-feature backbone by numeric layer index. This scaffold preserves that topology with a stable named backbone and excludes the Stage-2 projection head from Stage 3, matching the manuscript parameter accounting.
- The manuscript is internally inconsistent: Stage-1/2 preprocessing specifies 12 windows with overlap 7, while Stage 3 states 15 overlapping segments without giving overlap. The manifest keeps both statements and labels overlap 64 as a released-code inference.
- Exact author split indices, checkpoints, and `ssqueezepy` version/kwargs remain unavailable. No numerical replication claim is supported by this scaffold.
