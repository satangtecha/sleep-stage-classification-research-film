# Evidence-guided directions after v11

## Decision boundary

The immediate question is whether weak held-out-subject performance arises from
the data/sampling protocol, ordinary model instability, or true subject domain
shift.  v11 must become terminal and independently verified before any result
is used as evidence.  No target-subject labels may be used in model selection.

## Evidence found

1. **Subject/domain shift is a recognised sleep-staging problem.**  Yoo, Lee,
   and Kang describe performance loss when a model trained on a source cohort is
   applied to a small target cohort because the distributions differ between
   subjects.  Their domain-adaptation solution is a possible later track, not a
   first change because it alters the scientific question and training system.
   Source: https://pubmed.ncbi.nlm.nih.gov/34388101/ (PMID 34388101,
   DOI 10.1109/JBHI.2021.3103614).

2. **Robust channel/subject scaling is plausible but must be declared.**
   U-Sleep is evidence that robustness across heterogeneous PSG cohorts needs
   explicit design rather than being assumed from a small single-cohort pilot.
   Applying statistics computed from an entire held-out recording would be
   transductive (unlabelled target data are seen), so it is not eligible for
   the first non-transductive comparison.  A later, separately labelled
   experiment can assess it with this limitation explicit.
   Source: Perslev et al., *U-Sleep: resilient high-frequency sleep staging*,
   npj Digital Medicine 2021,
   https://www.nature.com/articles/s41746-021-00440-5.

3. **Class imbalance deserves diagnosis before a new loss.**  The current
   quality track already uses train-only balanced class weights and every class
   in the training fold is checked.  Focal loss/oversampling remain candidates
   only if v9/v11 show repeatable low minority-class recall with support present
   in held-out test and validation partitions.  They must be selected using
   training/validation only.
   Example source: Wang et al., *Deep adaptation network for subject-specific
   sleep stage classification*, Biomedical Signal Processing and Control 2022,
   https://doi.org/10.1016/j.bspc.2022.103548.

4. **Independent studies confirm that the two observed failure modes are
   genuine research problems.**  Li et al. identify class imbalance and
   cross-subject discrepancy as principal constraints in single-channel sleep
   staging (PMID 36084381, https://pubmed.ncbi.nlm.nih.gov/36084381/).
   Nejedly et al. report that subject/domain adaptation can improve target
   performance, but it is a different, transductive evaluation question and
   therefore must remain separate from the ordinary held-out protocol (PMID
   35508121, https://pubmed.ncbi.nlm.nih.gov/35508121/).

5. **A simple baseline is required before architecture escalation.**  A
   CPU-only spectral logistic classifier on the exact same folds can distinguish
   a data/protocol ceiling from a failure of the three-stage CNN/contrastive/GRU
   training.  It costs little memory and does not contend with GPU work.

## Pre-registered sequence

1. Verify v11 parent and every child with locked TF2.4.
2. Create pooled and per-subject/class error analysis for v9 and v11, including
   support counts, confusion matrices, macro-F1, accuracy, and seed variance.
3. Run deterministic CPU spectral-logistic baseline on exactly reconstructed
   v11 folds; halt if any membership hash differs.
4. Choose at most two changes from the following hierarchy:
   - **A.** Stage-3 learning-rate/schedule change, only if validation histories
     show optimisation instability rather than missing support.
   - **B.** Focal loss or sampling adjustment, only if class-level recall
     remains poor with sufficient validation support.
   - **C.** Per-epoch robust normalization, only if raw amplitude statistics
     show subject scale variation; this stays non-transductive.
   - **D.** Explicit transductive test-time/subject adaptation, a separate
     research track with no claim of ordinary held-out generalization.
5. Freeze the selected changes in a fresh versioned protocol, gate it, run it
   exactly once, and compare with v9, v11, and the baseline.

## Explicit non-claims

- Six held-out subjects are a pilot, not evidence of paper-equivalent
  population performance.
- A higher number from a transductive adaptation method is not directly
  comparable to a non-transductive subject-held-out result.
- No 83-percent or manuscript-replication claim is permitted until data,
  preprocessing, split, metrics, and multi-seed evidence match the stated
  target claim.
