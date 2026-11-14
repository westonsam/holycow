# Holy Cow research experiment

This is an experimental scaffold, not a validated diagnostic system. No model metrics have been produced. The detailed scope and gates are in `ML_EXPERIMENT_PLAN.md` (the plan is currently an existing untracked file; do not move it without coordinating).

## Immediate next step

Open `notebooks/00_environment_and_data_audit.ipynb` in the connected Colab kernel and run its cells. It prints package/GPU/disk information and tests temporary storage. Colab's working directory is remote: the local repository and local dataset files may not be available in that runtime. Arrange an explicit transfer or Drive mount; never assume a `/Users/...` path is visible there. Keep datasets and outputs private as applicable.

The Sydney source host returned a security challenge during the initial audit. Once accessible, obtain the absolute-scoring video and score spreadsheet from the official record: https://ses.library.usyd.edu.au/handle/2123/23647. The downloaded files are in `ml/data/sydney/`. Document licensing and source, then audit:

```bash
python -m ml.src.data_audit ml/data/raw/sydney --output ml/data/manifests/sydney_file_audit.json
```

The published protocol (https://www.journalofdairyscience.org/article/S0022-0302%2821%2900207-1/fulltext) says the absolute video compiles 100 passings, 50 unique passings repeated in shuffled order. The paper describes 0–3 visual locomotion scores; VLS >= 2 is one paper-used binary threshold, but aggregation, actual spreadsheet schema, segment boundaries, and repeated-animal identities must be established before applying it. Record unknowns; do not guess matches or split repeated animals across train/test.

## Code overview

- `src/data_audit.py`: SHA-256, sizes, and ffprobe metadata of local files; this is not a full frame-by-frame decode or score mapping.
- `src/splits.py`, `src/metrics.py`: leakage checks, grouped split, binary metrics, and group bootstrap.
- `src/video_io.py`, `src/video_baseline.py`: explicit-manifest video sampling and a ResNet-18 temporal-mean training scaffold. Requires local pretrained torchvision weights and a runtime with PyTorch, torchvision, Pillow, and OpenCV. No resources are fetched automatically. Model evaluation, test prediction export, and end-to-end smoke tests remain to be implemented and run; no trained model is supplied.
- `src/keypoints.py`, `src/plot_keypoints.py`: PCK/per-joint metrics and plots from real labeled keypoints. They do not run pose inference or compute COCO AP.
- `src/plot_results.py`: three binary outcome plots from a saved held-out prediction CSV, with task metadata supplied by the caller. Do not use until labels and held-out splits are verified.

Run dependency-free checks from the repository root:

```bash
python3 -m unittest discover -s ml/tests -v
```

Models require a labeled manifest with `clip_id,group_id,path,label,split`; group IDs must conservatively connect all repeated animals or source clips. Do not train on a composite as if it were one cow. The group checker cannot discover unknown duplicate animals for you. Private raw data, model weights, outputs, and checkpoints are excluded from git. CattleLameness footage is research-only and must not be publicly redistributed without rights clearance.

## Current limitations

The datasets have been obtained; the approximate video boundaries, outcome definition, grouped test split, model weights, pose model, and predictions are not yet ready for evaluation. Training, model metrics, validation plots, demo-video export, and the five final figures are therefore not complete. Do not present scaffolding or toy-test results as experimental results.

## Stage 2 audit

A score-independent, cow-grouped passing split and its limitations are recorded in `docs/STAGE_2_AUDIT.md` and `splits/`. Exact video boundaries and unknown source-recording overlap remain unresolved. The proposed outcome is a continuous mean score, so the existing binary-only training scaffold is not yet appropriate.

## Stage 3 status

See `docs/STAGE_3_REPORT.md`: the local score-only validation baseline and synthetic model wiring checks ran; real video model training is blocked until the scored cow is localized and walking footage is reviewed. The candidate manifest must not be treated as a set of quality-approved cow clips.

### Visual walkthrough

Open `ml/notebooks/01_stage3_visual_walkthrough.ipynb` in VS Code, select the project-local interpreter `ml/.venv/bin/python` as its kernel, and run its cells. It visualizes the score-only validation baseline, a training-presentation footage-quality sample, and a synthetic pretrained-encoder/head smoke test. It does not train on real footage or evaluate the held-out test set. The notebook is distributed without embedded outputs; an executed local copy (including video-frame images) is under the git-ignored `ml/outputs/stage3/` and should remain private unless the source footage and relevant terms allow sharing.
