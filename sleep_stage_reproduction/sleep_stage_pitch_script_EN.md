# Sleep Stage Classification from Single-Channel EEG

## 3–5 minute presentation script

### Slide 1 — The problem (about 45 seconds)

“Hello everyone. My project is about automatic sleep stage classification from EEG.

Sleep is usually divided into five stages: Wake, N1, N2, N3, and REM. Today, sleep staging is commonly performed by experts who inspect polysomnography recordings. This process is accurate, but it is time-consuming, requires multiple sensors, and is difficult to scale.

The idea of my project is to investigate whether one EEG channel can provide enough information to classify sleep stages automatically. This could support a simpler and more reproducible sleep-monitoring pipeline.”

### Slide 2 — The idea and objective (about 50 seconds)

“The core idea is simple: take a 30-second segment of single-channel EEG, learn its time-frequency patterns, and predict one of the five sleep stages.

The main objective is to develop and evaluate a deep learning pipeline based on a recent research approach. The model will combine a synchrosqueezed time-frequency representation, a convolutional neural network, contrastive learning, and a two-layer GRU.

This is an algorithmic research prototype. It is not intended to replace a clinician or act as a medical diagnostic device.”

### Slide 3 — The proposed workflow (about 90 seconds)

“The workflow has several stages.

First, I will extract the Fpz-Cz EEG channel and divide the recording into 30-second epochs. Each epoch will be normalized and converted into a time-frequency representation using a synchrosqueezed transform.

Next, a CNN will learn local signal patterns from short windows. Contrastive learning will be used to make the learned representation more robust to small signal changes and noise.

Finally, a two-layer GRU will process the ordered feature windows within each epoch and produce the final prediction: Wake, N1, N2, N3, or REM.

The evaluation will focus on macro-F1 and per-stage F1, not accuracy alone, because sleep-stage data are imbalanced and the N1 and REM classes are usually more difficult.”

### Slide 4 — Data, evaluation, and expected outcome (about 70 seconds)

“The primary dataset will be Sleep-EDF Expanded, a public dataset containing whole-night polysomnography recordings with EEG and expert-scored hypnograms.

I have already built a working pilot pipeline and downloaded a small subset for testing. The next step is to expand the data and split it by subject, so recordings from the same person never appear in both training and test sets.

I will compare a simple CNN baseline with the full model, test class-weighted training, and report accuracy, macro-F1, Cohen’s kappa, confusion matrices, and per-stage performance.

The expected outcome is a reproducible single-channel EEG sleep-staging pipeline, together with an analysis of which model components improve performance and how well the model generalizes to unseen subjects.”

### Closing sentence

“In short, this project asks whether a carefully designed deep learning pipeline can turn one EEG channel into a reliable five-stage sleep classifier, while keeping the data, evaluation, and limitations transparent.”
