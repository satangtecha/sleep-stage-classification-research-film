// v5 script (source of truth for captions). Order and focus follow the v6 presentation script (six criteria).
// SECTIONS -> beats -> caps. Numbers on screen come from facts.json; numbers inside captions are checked by tests/film.test.mjs.
export const SECTIONS=[
 {id:'1',title:'Problem and pipeline',beats:[
  {id:'B1',name:'The task',caps:[
   "Every 30 seconds of a night's sleep gets a label: Wake, N1, N2, N3 or REM. Experts score them by hand.",
   "Can a computer read sleep from one EEG channel, a single pair of scalp electrodes?"]},
  {id:'P1',name:'Input, process, output',caps:[
   "One pipeline. Input: a single Fpz-Cz EEG channel, 100 samples a second, all night.",
   "Process: cut into 30-second epochs, make a frequency picture of each, then a CNN and a BiGRU.",
   "Output: one of five stages for every 30 seconds, a hypnogram."]}]},
 {id:'2',title:'Research question',beats:[
  {id:'B2',name:'The reference',caps:[
   "A 2026 Scientific Reports paper claims about 83% accuracy from one channel, chaining four ideas.",
   "We set out to reproduce it. Within our time and compute, we could not.",
   "The paper splits epochs at random, so one person can be on both sides. We split by person.",
   "Why? A new patient is a new person; a random split can reward recognising the person."]},
  {id:'B3',name:'The new question',caps:[
   "So we changed the question: does it still work on a person the model has never seen, and can we explain every step?"]},
  {id:'Q2',name:'Scope and hypothesis',caps:[
   "Scope: not a replication or clinical validation. Twenty people, one public dataset, unseen people only.",
   "Hypothesis, formed after the baseline failed: nights differ in signal strength, so per-night scaling should help."]}]},
 {id:'3',title:'Data',beats:[
  {id:'B3b',name:'The data',caps:[
   "Sleep-EDF, public on PhysioNet: healthy adults recorded at home on cassette recorders, usually two nights each.",
   "Trained technicians scored every 30-second page of each night by hand, using the 1968 Rechtschaffen and Kales rules.",
   "Two experts can disagree, so labels are a trusted reference, not perfect truth.",
   "We use 20 people, 39 nights, 42,307 epochs. Trimmed, a night is about 1,085 epochs, or 9 hours."]},
  {id:'D2',name:'Variables and limits',caps:[
   "Three variables: the EEG signal, the stage label, and a person ID that only splits the data and never feeds the model.",
   "Limits: healthy adults only, just 20 people, human-scored labels and one channel. This data cannot speak for patients."]}]},
 {id:'4',title:'Technique',beats:[
  {id:'M1',name:'STFT',caps:[
   "STFT: a 2-second window slides in 1-second steps, making a 129 × 29 picture of frequency over time.",
   "Why? Stages are defined by rhythms: slow waves mark N3, spindles N2, alpha waves relaxed wake.",
   "The paper uses a synchrosqueezed transform. We chose STFT because we can draw, compute and check it by hand. We never compared them."]},
  {id:'M2',name:'CNN',caps:[
   "CNN: three blocks of 32, 64 and 128 channels squeeze each picture into 128 numbers. Its limit: it sees one epoch at a time."]},
  {id:'M3',name:'BiGRU',caps:[
   "BiGRU: two layers read 20 neighbouring epochs forwards and backwards, because sleep is a sequence.",
   "Why? Sleep comes in long runs: an epoch is easier to judge with its neighbours than alone.",
   "The cost: it uses future epochs, so it works offline only, never in real time."]},
  {id:'M4',name:'Why no contrastive stage',caps:[
   "Contrastive learning trains the CNN: similar epochs are pulled together, different ones pushed apart.",
   "It is a second training phase with many settings to tune: more time, more compute.",
   "We dropped the contrastive stage: reproducing it failed, and we wanted a chain we can check step by step. We never tested it."]},
  {id:'M5',name:'The test',caps:[
   "Testing is by person: ten folds, 16 people train, 2 pick the checkpoint, 2 are tested. Nobody appears twice.",
   "Only two test people per fold, so scores swing between folds."]}]},
 {id:'5',title:'Evidence',beats:[
  {id:'E1',name:'The baseline',caps:[
   "Baseline first: macro-F1 56.42%, 95% interval 48.26 to 63.44. Accuracy 65.00%. Folds swing from 39.95% to 74.39%.",
   "Opening single nights, three were right on only 7.22%, 18.60% and 19.01% of epochs. The average hid them."]},
  {id:'E2',name:'R1: a ruler per night',caps:[
   "To fix this, R1 changes one step: how each frequency picture is scaled before it reaches the CNN.",
   "STFT hands the CNN one picture per epoch. We first rescale each frequency row, so every frequency counts evenly.",
   "That rescaling is a z-score: subtract the mean, divide by the spread. Values become standard deviations.",
   "The baseline already did this, but with one ruler for all nights: the 16 training people's mean and spread.",
   "R1 gives every night its own ruler: that night's own mean and spread, with no labels used.",
   "Same architecture, retrained: macro-F1 74.86%, interval 71.33 to 78.03; accuracy 80.99%. Gain +18.44 (10.07 to 27.55).",
   "The three failing nights recover to 82.54%, 88.68% and 84.87%."]},
  {id:'E3',name:'The catch',caps:[
   "But R1 reads each test night's unlabeled signal and was chosen after the baseline failed: offline, post-hoc.",
   "Whole-recording statistics give 71.84%: −3.02 versus R1, interval −7.12 to +1.22. No clear difference, not proof of equality."]}]},
 {id:'6',title:'Limits and summary',beats:[
  {id:'L2',name:'What we cannot say',caps:[
   "What we cannot say: that it works on new people, since R1 is offline and was chosen after the fact.",
   "Nor that 80.99% beats or matches the paper's 83%, that it is clinically ready, or that N1 is solved.",
   "None of the 78 audited participants is certified independent."]},
  {id:'L3',name:'Summary',caps:[
   "Nights differ, and an average can hide the one that fails. Next: lock the protocol, then test on truly independent data."]}]}
];
