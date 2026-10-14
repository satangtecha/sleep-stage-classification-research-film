# Sleep Stage Research: English silent film

This version presents the archived CNN + BiGRU study in English, with burned-in English captions and no audio. It preserves the previous Thai film and every research result. The attached Facebook screen recording supplies visual inspiration only. No footage, audio or research claims from that clip appear here.

Subject-wise protocol differs from the paper; test < 10 subjects **per fold**, with 20 distinct test participants across the ten folds. The simplified CNN + BiGRU study does not replicate the original SST / contrastive learning paper.

## Five-minute story

| Time | Content |
|---|---|
| 0:00–1:00 | Sleep staging, cohort, five labels, subject-wise split |
| 1:00–2:00 | STFT, CNN architecture, bidirectional GRU, overlapping inference |
| 2:00–3:00 | Failing baseline nights, R1 normalization, archived results, full-night sensitivity |
| 3:00–4:00 | Paired bootstrap interval, fold variability, class recall, confusion counts |
| 4:00–5:00 | Rejected validation pilots, exposure audit, limitations and evidence boundary |

The 20 scenes last 15 seconds each. Two captions per scene provide 7.5 seconds to read each explanation. Titles, explanation, visual viewport and caption strip occupy separate reserved regions. Charts use archived numbers; EEG traces, spectra, network features and meshes are illustrative and labeled accordingly.

## Research interpretation

The headline macro-F1 is the **mean of participant-level macro-F1**, not the mean of fold-pooled macro-F1. Pooled accuracy weights every retained epoch. R1 scored 74.86% subject-mean macro-F1 and 80.99% pooled accuracy, compared with 56.42% / 65.00% for the baseline. Full-night sensitivity scored 71.84% / 79.10%.

R1 is post-hoc. R1 and full-night sensitivity use unlabeled signals from each validation/test night for normalization and are offline/transductive. Baseline-to-R1 combines retrained weights with changed normalization. It does not isolate a model-only or normalization-only causal effect. The sensitivity difference from R1 is -3.02 percentage points, paired 95% CI [-7.12, +1.22]. Insufficient evidence of a difference is **not proof of equivalence**. The 71.86% cutoff preceded that run but followed the baseline and R1 results, so it was not blind to R1.

The three recent pilots concern validation only and all failed the selection gate. Available participants with unresolved provenance are not certified unused. No independent cohort is currently certified. One model seed, post-hoc selection, incomplete earlier attempt counts, overlapping training folds and historical environment/source-hash limitations constrain interpretation. This is neither clinical validation nor an online prediction system.

## Tools used

- [ecmanim](https://github.com/johnhenry/ecmanim): npm 0.1.0 supplies the real `Scene` timeline and `ThreeDCamera` projection used in all five film chapters. Custom original meshes render through native canvas and FFmpeg. The inspected clone is `e16465ec4de78344f1fbcd993774ac9b20bb8793`.
- [Manim-Motion](https://github.com/BlommeJan/Manim-Motion): its real exporter at clone `5d51316543db9dc9f489dc1e7bb52524645bffee` produces the editable English result project and `motion-export.py`. This is a companion chart source, not the main film renderer. The Docker editor/backend was not launched.
- [Manim Slides](https://github.com/jeertmans/manim-slides): installed 5.7.0 with Manim CE 0.19.0 converts the five silent clips into an offline, single-file HTML presentation. The inspected clone is `df0f1f18f799cd38de0712b0abc4507d4d94b822`. Reverse files intentionally point to the same normal clips; no reverse-playback claim is made.

The requested reference direction takes priority over generic slide-design defaults. The skill guidance influenced reading hierarchy, contrast, progressive disclosure and factual caveats; the film deliberately uses code-native animated diagrams rather than decorative bitmap artwork.

## Rebuild on this machine

From this directory in Windows PowerShell:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
node --test tests/film.test.mjs
node qa.mjs
node film.mjs render 1
node film.mjs render 2
node film.mjs render 3
node film.mjs render 4
node film.mjs render 5
node motion-bridge.mjs
node deliver.mjs
```

After generating the HTML below, run `node --test tests/*.test.mjs` for the complete source and delivery checks. The delivery tests require the completed media files.

Render and delivery commands refuse to overwrite existing videos. Use a fresh output directory/version for a rebuild. `build-facts.mjs` also refuses to overwrite the local facts snapshot and verifies frozen aggregate sources before copying numbers. It reads no EEG arrays or model logits and runs no model.

From WSL, in the corresponding `/mnt/c/.../sleep-stage-film/20261014-en-v2` directory:

```bash
/home/techatat/.venvs/sleep-stage-film/bin/manim -ql motion-export.py MainScene --media_dir motion-render
/home/techatat/.venvs/sleep-stage-film/bin/manim-slides convert SleepStageEnglish outputs/presentation.html --one-file --offline -ctitle="Sleep Stage Research" -ccontrols=true -cprogress=true -cslide_number=true
```

The MP4 is the continuous five-minute deliverable. The HTML is a manual chapter presentation. Space/right arrow advances chapters in RevealJS. Use video controls for pause/seek when available. The English SRT in `outputs/captions-en.srt` contains the same burned-in captions.

## Provenance and QA

Frozen aggregate evidence comes from `sleep_stage_simple/results/closeout-and-exposure-audit-v1-20261013`. `facts.json` and `outputs/verification.json` record exact research source hashes and commits. `outputs/layout-audit.json` records text bounds and collision checks for both caption states. Representative images and an independent scientific/layout review complement those checks; text-box checks alone cannot prove perfect visual layout or comprehension.

The previous Thai film, reference video, research code/configs/receipts, protected plan/state and attempt counters remain untouched. No timers, research experiments, push or merge are part of this film task.

Actual final checks: 16 passed, 0 failed, 0 skipped on Node 24.16.0. The complete MP4 decoded without error and contains exactly 300 seconds, 7,200 frames and no audio stream. All five chapter videos played and navigation worked in the Codex in-app browser, with duration 60 seconds, readiness 4 and no media error for each. The temporary loopback-only QA server and tab were stopped after inspection. Nine frozen research source hashes remained valid. `outputs/tests-final-raw.txt` and `outputs/qa-verification-final.json` preserve the final test output and verification details. Browser/reviewer observations are explicitly historical manual evidence, not checks re-executed by `verify.mjs`. Native Qt/reverse playback and all third-party browsers were not tested.

Dataset attribution: Sleep-EDF Expanded 1.0.0; Kemp et al. (2000), Goldberger et al. (2000), PhysioNet, ODC-By 1.0. The closing scene displays this attribution.
