# Sleep Stage Classification: research to 3D film

This repository preserves the public, reviewable parts of a sleep stage classification project, from research input and protocol through code, results, and two five-minute animated presentations.

## Input → process → output

| Stage | Where to start | What is included |
| --- | --- | --- |
| Input | [`sleep_stage_reproduction/README_TH.md`](sleep_stage_reproduction/README_TH.md), [`research_links.md`](sleep_stage_reproduction/research_links.md), [`paper_faithful/data/`](sleep_stage_reproduction/paper_faithful/data/) | Dataset references, download scripts, schemas, preprocessing protocol, and recorded run manifests. Raw EEG is obtained from its original provider. |
| Process | [`run_sst_gru.py`](sleep_stage_reproduction/run_sst_gru.py), [`paper_faithful/`](sleep_stage_reproduction/paper_faithful/), [`walkthrough/`](sleep_stage_reproduction/walkthrough/) | Model and preprocessing code, experiment protocols, tests, notebooks, and reports. |
| Output | [`research_report_TH.md`](sleep_stage_reproduction/research_report_TH.md), [`slides_build/`](sleep_stage_reproduction/slides_build/), [`pitch_deck_build/`](sleep_stage_reproduction/pitch_deck_build/), [`sleep-stage-film/`](sleep-stage-film/) | Recorded results, explanatory materials, presentation source, and final videos. |

## Watch the films

- [Latest English film, silent with English captions (5 min)](sleep-stage-film/20261014-en-v2/outputs/SleepStage-English-Silent-5min.mp4) · [interactive presentation](sleep-stage-film/20261014-en-v2/outputs/presentation.html) · [source and caveats](sleep-stage-film/20261014-en-v2/README.md)
- [Earlier Thai film with narration (5 min)](sleep-stage-film/20261013-v1/outputs/final/SleepStageResearch-5min-final.mp4) · [interactive presentation](sleep-stage-film/20261013-v1/outputs/final/presentation-final.html) · [source and caveats](sleep-stage-film/20261013-v1/README.md)

The film source, story, facts, package lockfiles, and verification records are in each version directory. The 3D animation is an explanatory visualization of archived research, not an EEG model or a clinical tool.

## Research status

The reproduction track implements the SST/CNN/contrastive/GRU pipeline and includes resource-limited pilots. It has **not** established a full numerical reproduction of the paper's reported accuracy. The films describe a separate simplified CNN + BiGRU study. Its R1 result was selected post hoc and uses offline, full-night information for normalization; it is not independent clinical validation. Read each version's README and the research reports before quoting any metric.

## Publication scope

This public copy includes source code, protocol manifests, aggregate results, notebooks, slides, and final rendered films. Raw Sleep-EDF/Dreem recordings, local caches, checkpoints, runtime logs, virtual environments, npm dependencies, upstream vendor checkouts, and the user-supplied reference video are excluded. Download raw datasets from their original providers under their own terms. The project contains historical local path references in reproducibility records; those paths are examples of the original environment and are not expected to exist elsewhere.

The two film HTML files embed their media so they can be opened offline. They are large by design. To rebuild a film, follow its README in a fresh directory and install the listed dependencies; the archived outputs are kept immutable here.
