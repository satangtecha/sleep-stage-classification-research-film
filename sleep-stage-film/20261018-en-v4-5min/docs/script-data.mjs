// v4.1 script (source of truth for captions). v4 original: script-data-v4.mjs
export const ACTS=[
 {
  "id": "I",
  "title": "A night in 30-second pieces",
  "beats": [
   {
    "id": "B1",
    "name": "The task",
    "caps": [
     "Every 30 seconds of a night's sleep gets a label: Wake, N1, N2, N3 or REM. Experts score them by hand.",
     "Can a computer do it from one EEG channel, a single pair of scalp electrodes?"
    ]
   },
   {
    "id": "B2",
    "name": "The reference",
    "caps": [
     "A 2026 paper in Scientific Reports says yes: about 83% accuracy, combining a synchrosqueezed transform, a CNN, contrastive learning and a GRU.",
     "We set out to reproduce it. Within our time and compute, we could not."
    ]
   }
  ]
 },
 {
  "id": "II",
  "title": "A different question",
  "beats": [
   {
    "id": "B3",
    "name": "The pivot",
    "caps": [
     "So we changed the question. Not “how high can one number go?” but “does it still work on a person the model has never seen?”",
     "And can we explain every step from first principles?"
    ]
   },
   {
    "id": "B3b",
    "name": "The data",
    "caps": [
     "Our data is Sleep-EDF, a public PhysioNet set: healthy adults recorded at home on cassette recorders, usually two nights of about 20 hours.",
     "Trained technicians then scored every 30-second epoch by hand, following the 1968 Rechtschaffen and Kales rules.",
     "We use 20 people and 39 nights: 42,307 epochs. Trimmed to its scored span, a night is about 1,085 epochs, or 9 hours."
    ]
   },
   {
    "id": "B4",
    "name": "Their way, our way",
    "caps": [
     "The paper chains four ideas. Ours is three plain ones: a short-time Fourier transform, a CNN and a bidirectional GRU.",
     "We dropped the contrastive stage: reproducing it failed within our time and compute, and we wanted a chain we can draw, derive and check.",
     "We make no claim that it helps or hurts: we never ran that comparison."
    ]
   },
   {
    "id": "B5",
    "name": "How the model reads a night",
    "caps": [
     "The paper uses a synchrosqueezed transform. We use a plain STFT: a 2-second Hamming window sliding in 1-second steps.",
     "Each 30-second epoch becomes a 129 × 29 picture of frequency over time. A CNN squeezes it into 128 numbers.",
     "A bidirectional GRU then reads 20 neighbouring epochs forwards and backwards, because sleep is a story, not a snapshot."
    ]
   },
   {
    "id": "B6",
    "name": "The test",
    "caps": [
     "Testing is strict. Twenty people, ten folds: in each fold 16 people train, 2 choose the checkpoint and 2 are tested.",
     "Nobody appears twice. A person's epochs look alike, so splitting by epoch would flatter the score."
    ]
   }
  ]
 },
 {
  "id": "III",
  "title": "The nights that failed",
  "beats": [
   {
    "id": "B7",
    "name": "The failure",
    "caps": [
     "First result: 56.42% macro-F1, a score that treats all five stages equally, averaged over people. Accuracy: 65.00%.",
     "Then we opened individual nights. On three of them the model was right on only 7.22%, 18.60% and 19.01% of epochs."
    ]
   },
   {
    "id": "B7b",
    "name": "A hypothesis",
    "caps": [
     "Our hypothesis: nights differ in overall signal strength, so a model trained on some nights misreads others.",
     "A per-night yardstick cancels that, at a cost: a night's average also depends on its stage mix."
    ]
   },
   {
    "id": "B8",
    "name": "The turn",
    "caps": [
     "Our idea, R1: judge every night against its own yardstick, using that night's own mean and spread for each frequency.",
     "Same architecture, retrained. Macro-F1 rose from 56.42% to 74.86%; accuracy from 65.00% to 80.99%.",
     "The three failing nights recovered to 82.54%, 88.68% and 84.87%."
    ]
   },
   {
    "id": "B9",
    "name": "The catch",
    "caps": [
     "But R1 reads each test night's unlabeled signal within its scored span, and we chose it after the baseline failed.",
     "So it is offline and post-hoc: a promising finding, not a finished product."
    ]
   },
   {
    "id": "B9b",
    "name": "Not comparable to 83%",
    "caps": [
     "Our 80.99% sits near the paper's 83%. We do not rank them: the protocols differ, and R1 sees each test night's signal."
    ]
   }
  ]
 },
 {
  "id": "IV",
  "title": "What we can honestly say",
  "beats": [
   {
    "id": "B10",
    "name": "Is it fragile?",
    "caps": [
     "A sensitivity check takes the statistics from the whole recording instead: 71.84%.",
     "Versus R1: −3.02 points, 95% interval −7.12 to +1.22. It crosses zero: no clear difference, but not proof they are equal."
    ]
   },
   {
    "id": "B11",
    "name": "The weak spot",
    "caps": [
     "N1, the lightest sleep, stays hard: R1 recovers 44.69% of true N1 epochs, and 38.91% of its N1 calls are right.",
     "Three small attempts to fix it were all rejected."
    ]
   },
   {
    "id": "B13",
    "name": "What we cannot say yet",
    "caps": [
     "What we cannot yet say: that it works on new people. None of 78 audited participants is certified independent.",
     "Next: a locked protocol on truly independent data."
    ]
   }
  ]
 }
];
