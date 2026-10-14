# Decision record: post-v11 quality iteration

## Evidence considered

- The terminal-valid v11 parent result is recorded in
  `E:/blp/sleep_stage_reproduction/runtime/subject-generalization-quality-plan16-v11-cap64-e12-cohort43-model45-20261006/terminal-validation.json`.
  All six folds are verified.  Its six-fold mean accuracy is 0.21875 and mean
  macro-F1 is 0.18839.
- `subject-generalization-quality-plan16-v9-v11-error-analysis-v1-20261006.json`
  shows only a small accuracy gain over v9 (0.20573 to 0.21875) and weak N1
  and N3 performance.  The two test folds without N3 are explicitly excluded
  from any claim about N3 generalisation.
- The immutable exact-fold CPU comparator
  `subject-generalization-quality-plan16-v11-cpu-spectral-baseline-v4-20261006.json`
  is verified (SHA-256
  `6d49dfd827e53758d9b772934a12871cb0e9336278b2db183ceb70ecf75eb5fd`).
  It obtains mean accuracy 0.16927 and mean macro-F1 0.12622.  Therefore the
  learned three-stage representation is materially better than this simple
  spectral summary; replacing the model with the baseline is not justified.
- Five of six v11 Stage-3 folds early-stopped at 4--9 of the permitted 12
  epochs.  Stage 3 used SGD learning rate 0.1, scheduler patience 1, and the
  same train-only balanced class weighting in every fold.  This is direct
  validation-side evidence for testing a more conservative Stage-3 optimizer
  schedule.

## Fixed selection for the next fresh run

Select exactly **one** adaptation:

`QUALITY_STAGE3_CONSERVATIVE_SGD_LR002_V1`

- Stage 3 only: SGD learning rate `0.02` rather than `0.1`.
- Stage 3 scheduler only: `ReduceLROnPlateau(factor=0.5, patience=2,
  min_lr=1e-5)` rather than `(0.2, 1, 1e-4)`.
- Preserve v11's six participants, ordered leave-one-subject-out folds,
  selection seed, cap 64, 12-epoch maximum, model seed, Stage 1/2 behavior,
  post-accumulation global norm clipping, train-only class weights, validation
  early stopping, and single held-out test evaluation.

This is an optimization comparison, not a paper-exact replication.  The
change is encoded by
`QUALITY_BALANCED_CAP64_E12_V2_CONSERVATIVE_STAGE3_SGD`; it is fail-closed if
used outside the existing quality Stage-3 contract.

## Explicitly not selected

- **Additional class weighting/focal loss:** v11 already uses a train-only
  balanced class-weighted cross-entropy.  Adding focal loss at the same time
  would confound the optimizer comparison.
- **Subject/recording normalization:** subject-level normalization is a
  plausible separate experiment (Hartmann and Baumert, 2023,
  https://pubmed.ncbi.nlm.nih.gov/38083045/), but aggregate scale evidence has
  not yet been collected.  It is not added speculatively.
- **Domain adaptation:** this changes the evaluation question and remains a
  separately labelled transductive track.

## Research context

Cross-subject discrepancy and class imbalance are established sleep-staging
failure modes (Li et al., 2022, https://pubmed.ncbi.nlm.nih.gov/36084381/).
This run retains strictly subject-held-out evaluation and uses validation, not
held-out test labels, for all model-selection decisions.

## Gates before dispatch

1. Focused unit tests and locked TF2.4 smoke/preflight tests must pass.
2. A fresh protocol must bind the revised source hash and this decision
   record, then receive independent review and canonical gate evidence.
3. Dispatch must use a new namespace with CreateNew markers; no v9/v11 or
   baseline artifact can be resumed, retried, or reused.
## Supersession before any training

The initial v12 plan was published but never dispatched: no runtime directory,
attempt marker, child directory, cache mount, or training process was created.
Its loader-only canary revealed that the otherwise reviewed quality profile still
enforced the global 15 GiB C: storage floor, while C: had 14.24 GiB free and all
bulk input/output resides on E:.  The runner was therefore corrected and tested
to make the C: floor an explicit profile property: the new conservative profile
alone permits 12 GiB, while every existing profile retains 15 GiB.  Because that
source change invalidates the v12 source binding, the immutable v12 plan remains
as pre-dispatch evidence and the next eligible fresh namespace is v13.
