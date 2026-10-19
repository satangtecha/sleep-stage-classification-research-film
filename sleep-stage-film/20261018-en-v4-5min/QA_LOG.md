# QA log

## Open / known deviations from the plan
- Transitions: `match` and `pullback` are plain dissolves; carry (`⇢เข้า/ออก`) is not implemented. Carried objects sit at the same position in both scenes where possible.
- B5 CNN plates are 2-D skewed plates, not the 3-D World mesh, so FACE_LIGHT was not tuned.
- B4/B9b show one evidence tag per shot (the plan's split REF-left / CODE-right is drawn as one tag).
- Colour contrast of `dim` text (~3.1:1) is an estimate, not measured.
- The optional "ONE SEED" stamp is off by default.
- Full 21-scene contact-sheet review was done on stills at three times per shot, not frame by frame.

## v4.1 (2026-10-19)
- Script: new scene B3b "The data" (Sleep-EDF facts, 20/39/42,307, ~1,085 epochs ≈ 9 h per night); B4 gains the contrastive-cut rationale; B5 split into STFT / CNN / BiGRU captions; B6 counters moved to B3b.
- Cuts: B12 removed; B9b reduced to one caption; B7b.c2 shortened; III–IV leads 3.5→2.0 s, holds shortened.
- Captions/timeline now derive from docs/script-data.mjs via tools/timeline.mjs (v4 script kept as docs/script-data-v4.mjs).
- Result: 21 scenes, 70 shots, 9,099 frames, 303.3 s.
- Open: "never ran that comparison" (B4.c3) and the reason for dropping contrastive rest on the team's account; no ablation exists. Dataset descriptors (20 h PSG, R&K 1968, cassette home recording) are from PhysioNet's page, not from our results. Paper GRU direction unverified.
- Known cosmetic: B11.S3 REJECTED stamp briefly overlaps a card title (unchanged).
