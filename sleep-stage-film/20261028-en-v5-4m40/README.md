# Reading Sleep from One EEG Channel — 5-minute silent film (v4)

English, silent, 1920×1080, 30 fps, 298.4 s (8,952 frames), 21 scenes / 67 shots, 21 chapter markers.
Audience: professors and neuroscience experts. The 12-minute v3 film (`../20261014-en-v3/`) stays as the technical appendix.

Every frame is a pure function of story time (`frameAt(canvas,t)` in `film.mjs`), drawn with @napi-rs/canvas.
Every number on screen is read from `facts.json` through `fact()`.

## Commands
- `node film.mjs info` — scene/shot counts
- `node film.mjs stills [ids]` — three stills per shot in `outputs/stills/`
- `node film.mjs render K 8` — render part K of 8 (x264, CRF 18)
- `node film.mjs srt` — `outputs/captions-en.srt` + `story.json`
- `node tools/deliver.mjs` — concat parts, 21 chapters, `outputs/verification.json`
- `npm test` — timeline, caption rate, element budget, determinism, facts, black last frame

Plan, storyboard and script data are in `docs/`.
