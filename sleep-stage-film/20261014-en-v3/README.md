# Reading Sleep from One EEG Channel — English silent film, v3

A roughly 12-minute English film with no audio. It explains the mathematics of the archived CNN + BiGRU sleep-stage study step by step, then shows what the evidence does and does not support. Captions are burned in, and `outputs/captions-en.srt` holds the same text.

v3 replaces the slide-like layout of v2 (a text column beside a small visual) with a full-width, reference-style layout:

- **Card frame.** A dark navy card sits on a purple arc background. The chapter label is top-left and a provenance tag is top-right. The visual area is full-width, and one caption strip sits below a divider.
- **Provenance tags on every scene.** `Archived result. Measured.` (green), `From the project code.` (blue), `Illustrative signal. Not recorded data.` / `Concept picture.` (amber), `Worked example. Hypothetical numbers.` (violet).
- **Progressive builds.** Equations wipe in left to right (typeset with MathJax). Curves draw on with a glowing head, numbers count up, and 3D objects grow into place under a slowly orbiting camera (ecmanim `ThreeDCamera`).
- **Scene transitions.** Within a chapter, scenes alternate between zoom-dissolves and horizontal pushes. Chapter boundaries use an iris wipe into an animated chapter card.
- **Silent pacing.** Every caption gets at least 1 second per 17 characters. Scenes whose captions need more time are stretched uniformly, so the visuals stay in sync with the text. A test enforces this.

## Story (8 chapters, 50 scenes)

| Chapter | Content |
|---|---|
| Opening | EEG trace → 30-second epochs → hypnogram |
| 1. The signal | Voltage difference Fpz − Cz, sampling at 100 Hz, Nyquist and aliasing (70 Hz → 30 Hz), the 3,000-sample epoch vector, five label codes, cohort (20 / 39 / 42,307), subject-wise folds |
| 2. From waves to frequencies | A, f, φ; sums of waves; mean(x²)=A²/2; DFT as winding; magnitude vs phase; STFT with Hamming window; leakage; 129 × 29 grid and Δf; log-magnitude; "the model sees numbers" |
| 3. Putting nights on one scale | z-scores; per-frequency μ_f, σ_f with the 10⁻³ floor; baseline vs R1 (transductive); gain-invariance proof; class-mixture trade-off |
| 4. The network | Tensor [32, 20, 1, 129, 29] and reshape; weighted sum and convolution; ReLU and max pooling; 3D CNN stack to a 128-d embedding; BatchNorm vs dropout (train/eval); GRU gates; BiGRU; logits → softmax |
| 5. How it learns | Cross-entropy; class weights [1, 1.5, 1, 1, 1]; gradient p − 1(c=y); AdamW on a loss surface with clipping; empirical vs true risk, early stopping |
| 6. Predicting and scoring | Sliding windows and logit averaging; R1 confusion matrix; N1 recall, precision and F1 from the archived counts; macro-F1 vs subject-mean macro-F1 |
| 7. What we found | Failing baseline nights; 56.42% / 74.86% / 71.84% subject-mean MF1; full-night statistics range; paired bootstrap CI [−7.12, +1.22]; folds; per-class recall |
| 8. The evidence boundary | Rejected validation pilots; provenance audit (30 / 48 / 0); limitations; the whole pipeline as one system |

All measured numbers are read from `facts.json`, copied unchanged from v2. That file records the frozen research source hashes and commits. Charts tagged *Measured* plot archived values only. EEG traces, spectrograms, loss surfaces, network activity, per-participant bars and the bootstrap histogram shape are illustrative and tagged as such. The bootstrap interval and point estimate shown with that histogram come from the archive.

## Research interpretation (unchanged)

R1 is post-hoc. R1 and the full-night sensitivity run normalize with unlabeled signal from each evaluated night, which makes them offline and transductive. Baseline → R1 changes normalization and retrains the weights together, so it does not isolate a causal effect. The full-night − R1 interval includes zero. That is insufficient evidence of a difference, not proof of equivalence. The three validation pilots were all rejected, and no independent cohort is certified. This film is neither a replication of the original SST / contrastive paper nor clinical validation.

## Tools

- [ecmanim](https://github.com/johnhenry/ecmanim) 0.1.0 provides the `Scene` frame clock and the `ThreeDCamera` projection for all 3D scenes.
- [MathJax](https://github.com/mathjax/MathJax-src) 3.2.2 (`mathjax-full`) typesets every equation to SVG, which is drawn natively with `@napi-rs/canvas`. Frames are piped to FFmpeg (libx264, no audio stream).
- [Manim Slides](https://github.com/jeertmans/manim-slides) 5.5.2 converts the nine chapter clips into a single-file, offline HTML presentation (`outputs/presentation.html`).

## Rebuild

```bash
npm ci --no-audit --no-fund
node --test tests/film.test.mjs     # facts, caption pacing, every scene renders
node film.mjs stills                # one still per scene in outputs/stills/
node film.mjs render 0 2 & node film.mjs render 1 2 & wait   # parallel parts
node film.mjs srt                   # captions-en.srt + story.json
node deliver.mjs                    # concat, chapter markers, verification.json
node deliver.mjs slides             # 720p chapter clips + Manim Slides config
manim-slides convert --folder slides SleepStageEnglishV3 outputs/presentation.html --one-file -ccontrols=true -cprogress=true -cslide_number=true
```

Fonts: Inter is used on Linux, with a Segoe UI fallback on Windows (see `lib.mjs`).

Dataset attribution: Sleep-EDF Expanded 1.0.0; Kemp et al. (2000); Goldberger et al. (2000); PhysioNet; ODC-By 1.0.
