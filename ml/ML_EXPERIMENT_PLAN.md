# Holy Cow ML Experiment Plan

**Status:** Planning only. This document describes the research/demo workflow; it does not claim that datasets have been downloaded, code has been run, or metrics have been generated.

**Scope confirmed:** Use Google Colab first, with no additional paid compute for now. Use the University of Sydney locomotion-scored dataset and `fahimsohan/CattleLameness` for research/demo only. Produce five separate, task-appropriate evaluation figures (not five incomparable lines on one graph). Datasets are not yet downloaded. Store the plan in this repository at `docs/ML_EXPERIMENT_PLAN.md`.

## 1. Objective and deliverables

Build a reproducible, small-scale side-view cattle lameness experiment that:

1. evaluates a direct video classifier on available lameness-labeled videos;
2. evaluates cattle keypoint detection separately, only where keypoint ground truth exists;
3. compares predictions against held-out, video-level labels without frame leakage;
4. exports a short annotated video showing the computer-vision pipeline;
5. produces five separate plots, a metrics table, and a brief limitations/rights note.

This is a research and hackathon demonstration, not a validated veterinary diagnostic system. Show an experimental risk/score with uncertainty or “needs human review,” never a medical diagnosis.

## 2. Data and rights gate

### University of Sydney locomotion-scored dataset — primary lameness evaluation

Record: <https://ses.library.usyd.edu.au/handle/2123/23647?show=full>

The repository record lists two MP4 files (`absolute.mp4`, about 197 MB; `pairwise.mp4`, about 416 MB) and score spreadsheets, and states CC BY 4.0. It describes 50 conventional locomotion videos and pairwise comparisons. Begin with the absolute-scoring video/spreadsheet pair. Read the spreadsheet and record the exact score scale, video-to-label mapping, and unit represented by each score before modeling.

**Gate:** Verify the repository record, actual file downloads, file integrity, and any file-level terms before sharing footage. Keep attribution and a record of any edits. This plan uses it for research/demo.

### `fahimsohan/CattleLameness` — secondary direct-video baseline only

Repository: <https://github.com/fahimsohan/CattleLameness>

The repo contains short clips grouped as lame/normal and provides 3D CNN / ConvLSTM prototype code. Its data README says clips are derived from YouTube and states research/education use; it also says full original videos are not included. Individual YouTube footage rights are not established by the repository. The GitHub repo has no declared software license in its metadata. Therefore:

- use only for a private research/demo comparison after checking the repo's current contents and relevant source-video terms;
- do not redistribute its clips, place them in a public demo, or claim commercial training rights;
- do not assume a paper's open-access license covers the underlying footage;
- keep this dataset out of commercial products unless rights are separately confirmed in writing.

### Keypoint dataset

Repository: <https://github.com/yww0411/Livestock-keypoint-detection>

The repo reports a multi-species image dataset with 18 anatomical keypoints, including cattle. It contains model/config/evaluation code for SimCC, SAR, and YOLOX-Pose variants. Dataset images have a CC BY 4.0 notice and code a separate MIT license. Inspect the checked-out `LICENSE-DATA.txt`, `LICENSE.txt`, README, split files, and model-specific license before use. This is an image keypoint benchmark, not a lameness-labeled video dataset. Do not infer gait performance from its still-image metrics.

### Rights decision summary

| Asset | Planned use | Rights caution |
|---|---|---|
| Sydney videos + score sheets | Primary lameness evaluation and possible demo after file/record verification | CC BY 4.0 stated by dataset record; attribute and check any file notices |
| CattleLameness repo clips | Secondary research-only baseline; do not redistribute | YouTube-sourced; clip rights unclear/research-only statement in repo |
| Livestock keypoint dataset | Keypoint evaluation | Dataset/code are separately licensed; inspect files and exact model/framework terms |

## 3. Platform and repository organization

### Compute

Use the existing VS Code + Google Colab kernel setup. The notebook runtime is the compute environment; files in the local repo are not automatically available inside the Colab VM. Confirm how the VS Code Colab kernel exposes files before assuming a local path exists remotely. Prefer a small, explicit transfer or download into the active runtime and save outputs/checkpoints to persistent storage. Colab GPU access and runtime duration are not guaranteed, so checkpoint and save outputs often.

No paid GPU, storage upgrade, package install, dataset download, or training is authorized by this plan alone. If free Colab compute is insufficient, pause and ask before using a paid platform.

### Suggested repository layout

```text
ml/
  docs/ML_EXPERIMENT_PLAN.md
  notebooks/
    00_environment_and_data_audit.ipynb
    01_sydney_baseline.ipynb
    02_keypoint_benchmark.ipynb
    03_video_model_comparison.ipynb
    04_demo_export.ipynb
  data/                  # ignored by git; do not commit datasets
    raw/sydney/
    raw/cattlelameness/   # research-only; keep private
    keypoints/            # keypoint dataset, if licensed/needed
    manifests/
  src/
    data_audit.py
    video_io.py
    metrics.py
    plot_results.py
  outputs/
    metrics/
    figures/
    demo/
    checkpoints/
  requirements-colab.txt  # create only after dependency versions are tested
```

Add large data, checkpoints, and any derived video to `.gitignore`. Do not commit raw video or personal/runtime credentials. Save a manifest with source URL, filename, license/rights notes, size, checksum, dataset subject/video ID, label, split, and preprocessing history.

## 4. Modeling flow

### Stage A — direct video baseline (lameness)

Input: one short sequence per original video / animal. Output: an experimental binary or ordinal lameness score.

1. Start with a transparent baseline: frame sampling + a pretrained image encoder (for example, ResNet-18 from torchvision) with temporal average pooling and a small classification head. This is simpler to debug and lighter than end-to-end 3D training.
2. If runtime and data count permit, compare a compact pretrained video model (for example, torchvision R3D-18) as a second approach. Alternatively reproduce the repo's 3D CNN/ConvLSTM only after auditing its code, class mapping, split, metric calculation, and source data.
3. For each clip, sample a fixed number of evenly spaced frames, resize consistently, and normalize using the selected pretrained model's documented preprocessing. Do not treat each frame as an independent example.
4. Split by animal identity or source video before making frames/windows. Ensure near-duplicates and clips from one source video cannot appear across train/validation/test.
5. Start with a small fixed split and save the exact IDs. If sample counts permit, prefer grouped cross-validation; if they do not, use leave-one-animal/video-group-out or a fixed group holdout and state the limitation.
6. Predict at video level. Report balanced accuracy, sensitivity/recall, specificity, precision, F1, AUROC, AUPRC, and a confusion matrix. Add confidence intervals by bootstrapping animal/video groups, not frames.

**Important:** A model trained on CattleLameness’s lame/normal internet clips and evaluated on Sydney is an external-domain test, not a same-distribution benchmark. Do not merge score labels or assert equivalence of class definitions without a documented mapping.

### Stage B — keypoint evaluation

Use the keypoint repo's documented test split and one documented cattle configuration. The practical first experiment is to reproduce a single lightweight SimCC or SAR configuration rather than the full multi-seed benchmark. Avoid YOLOX-Pose until its exact software and checkpoint licensing is resolved.

Report COCO keypoint AP/AP50/AP75 or the repository's documented metric, plus per-joint errors / PCK if supported. Record the keypoint order and visibility handling. If evaluating on Sydney video frames, annotate a small, subject-disjoint frame subset with the same 18-point schema first; only then calculate keypoint accuracy. Use a consistent annotation protocol and a second reviewer for a sample of frames if feasible.

Keypoint AP is not lameness-detection performance. The keypoint image set and lameness video set have different labels and units.

### Stage C — interpretable pose-to-lameness pipeline (stretch goal)

Only after keypoints have been quality-checked on suitable walking footage:

1. detect/crop the cow;
2. estimate keypoints per sampled frame;
3. smooth keypoint coordinates across time and flag low-confidence/occluded points;
4. derive candidate temporal features (stride periodicity, left/right limb excursion or symmetry, head/pelvis motion), documenting assumptions;
5. fit a simple logistic regression or random forest to video-level labels;
6. compare with the direct-video baseline on identical grouped splits.

With two-dimensional monocular side-view footage, occlusion and hidden-side legs limit what can be inferred. Features are exploratory, not clinical biomarkers. Do not tune and report performance on the final test set.

## 5. Stage-by-stage checklist, design, tests, and validation

### Stage 0 — confirm environment and scope

**Checklist**
- [ ] Open the repo in VS Code and confirm the active Colab kernel name/runtime.
- [ ] In a notebook, print Python version, working directory, `torch.__version__`, `torch.cuda.is_available()`, GPU name if present, free disk space, and available RAM.
- [ ] Confirm whether `/content/...`, mounted Drive, or a VS Code remote filesystem is being used; do not assume `/Users/...` exists in Colab.
- [ ] Confirm the repository root and that outputs will not go into raw-data folders.
- [ ] Record package versions and a random seed.

**Design:** One environment-audit notebook, with no model training.

**Tests / acceptance**
- [ ] Notebook can create/read a small temporary file in the selected project/output path.
- [ ] GPU visibility is explicitly reported (CPU fallback is acceptable for data audit).
- [ ] No large dataset download or paid service is triggered.

### Stage 1 — obtain and audit data

**Checklist**
- [ ] Download Sydney files from its official record; save to `data/raw/sydney/` outside version control.
- [ ] Verify file sizes/checksums where supplied; use a video probe (OpenCV/ffprobe) to list duration, dimensions, frame rate, and successful decode.
- [ ] Inspect score spreadsheets and map each original video/animal to its locomotion score; preserve raw scores.
- [ ] Download/keypoint repo
- [ ] Treat CattleLameness clips as research-only; keep original source URLs and do not redistribute.
- [ ] Generate `data/manifests/data_manifest.csv` with source, license notes, asset name, ID, labels, checksum, modality, and split assignment.

**Design:** Data loader returns one record per video or image, with metadata separated from tensors.

**Tests / acceptance**
- [ ] Every listed file opens and decodes; corrupt files are reported, not silently dropped.
- [ ] Label count matches expected rows/video IDs; no unmapped labels.
- [ ] Confirm whether the videos are individual cow passings or composite videos/pairs; resolve mapping before model development.
- [ ] Confirm left/right orientation and whether flips are valid before using horizontal-flip augmentation.
- [ ] Do not proceed if video-to-score mapping is ambiguous.

### Stage 2 — dataset and leakage audit

**Checklist**
- [ ] Count videos, subjects, classes, score distribution, duration, and frame properties.
- [ ] Identify repeated animals, repeated scenes, and any overlap between clips.
- [ ] Reserve groups (animal/video/source) for validation and test before frame extraction or augmentation.
- [ ] Save split IDs to a versioned CSV/JSON, but do not store restricted/private media in git.
- [ ] Choose an outcome definition from the original scoring protocol; keep ordinal scores unless a binary threshold is justified and fixed in advance.

**Design:** Group-based split utility; all frames/windows from a subject/source remain in one split.

**Tests / acceptance**
- [ ] Automated assertion finds zero subject/video/source overlap across splits.
- [ ] No label or class-derived filenames leak into model inputs.
- [ ] Print class counts in each split; if a class is absent from a fold, adjust only via a predeclared grouped strategy.
- [ ] Keep final test data untouched during model selection.

### Stage 3 — baseline and evaluation pipeline

**Checklist**
- [ ] Implement majority-class and simple handcrafted baseline first.
- [ ] Implement frame-sampled pretrained ResNet-18 + temporal pooling.
- [ ] Add compact R3D-18 only if GPU/runtime allows.
- [ ] Add early stopping based on validation metric; save best checkpoint and config.
- [ ] Use class weighting or sampling only if needed; calculate on training split alone.

**Design:** Video-level Dataset/DataLoader; fixed preprocessing; deterministic split; group-aware predictions; metrics generated from one saved prediction table.

**Tests / acceptance**
- [ ] A tiny overfit smoke test (a handful of clips) can reach near-perfect training fit; this tests code wiring only, not generalization.
- [ ] Check that output probabilities are valid and class-to-index mapping matches labels.
- [ ] Test metrics on a hand-constructed toy example with known confusion matrix.
- [ ] Confirm one prediction per held-out video, not one vote per duplicated frame.
- [ ] Save a CSV containing truth, probability, predicted class, group ID, and split.

### Stage 4 — keypoint model and pose quality

**Checklist**
- [ ] Read the keypoint repo README, license files, cattle configs, and documented evaluation command.
- [ ] Reproduce one configuration on its provided cattle split, preferably a lightweight SimCC/SAR variant.
- [ ] Confirm checkpoint availability; if not included, train from the repo's prescribed initialization and log the cost/time.
- [ ] Preserve exact keypoint names/order, visibility flags, bounding-box convention, and image resize transforms.
- [ ] Create qualitative overlays for a sample of held-out images.

**Design:** Keep keypoint evaluation separate from video lameness. For Sydney, manually annotate a predeclared small frame subset before claiming cross-dataset pose accuracy.

**Tests / acceptance**
- [ ] Parse annotations and confirm image IDs, keypoint count, visibility values, and coordinate bounds.
- [ ] Apply/invert resize and crop transforms; predicted overlay coordinates align with original frames.
- [ ] Compare overlay predictions against a human-reviewed sample; report per-joint error and occlusion behavior.
- [ ] Do not report keypoint accuracy for datasets without keypoint labels.

### Stage 5 — model comparison and robustness

**Checklist**
- [ ] Compare majority/simple baseline, ResNet temporal pooling, optional R3D-18, and pose-feature classifier only on a shared eligible holdout.
- [ ] Separate in-domain validation from cross-dataset transfer.
- [ ] Run a small grouped bootstrap or repeated grouped folds if compute permits.
- [ ] Record failures, low-confidence cases, and class-wise performance.

**Design:** One comparable video-level prediction table and one experiment metadata file (model/config, seed, split hash, data version, runtime, metrics).

**Tests / acceptance**
- [ ] Same eligible samples and split IDs for every model in any head-to-head comparison.
- [ ] Same preprocessing/outcome mapping when comparisons are claimed.
- [ ] Confidence intervals resample groups/animals, not frames.
- [ ] Include uncertainty and baseline; do not rely on accuracy alone.
- [ ] Explicitly label cross-dataset results as domain transfer.

### Stage 6 — demo video export

**Checklist**
- [ ] Select a Sydney video whose use for the demo is within the dataset license and attribution conditions; for a public event, confirm whether redistribution/display is covered and include attribution.
- [ ] Run detector/pose predictions on sampled frames; smooth only for visualization and keep raw model outputs for metrics.
- [ ] Overlay cow box, visible keypoints/skeleton, confidence, and a modest gait trace.
- [ ] Display “experimental estimate / human review” language; no diagnostic claims.
- [ ] Export a short MP4 and add a source/attribution card or README.

**Design:** Side-by-side original and annotated video, plus a small timeline of model confidence and predicted score. Hide the score when input quality/visibility is inadequate.

**Tests / acceptance**
- [ ] Video plays end-to-end, correct orientation/frame rate, no black/missing frames.
- [ ] Overlay coordinates are aligned; timestamps correspond to source frames.
- [ ] Confidence/score is stable enough for a demonstration and clearly labeled as experimental.
- [ ] Any non-Sydney footage is omitted from public demo until rights are clarified.

### Stage 7 — plots and final report

Produce **five separate figures**; each uses only the data/labels appropriate to its task:

1. **Lameness ROC curve** — video-level Sydney labels and scores, only if a documented binary threshold is set; grouped held-out predictions; include AUROC and uncertainty.
2. **Lameness precision–recall curve** — same labels/split; include AUPRC and positive-class prevalence.
3. **Lameness calibration / reliability plot** — predicted probability versus observed group-level frequency; mark small sample size and use grouped bins.
4. **Keypoint PCK curve** — fraction of keypoints within normalized distance thresholds, on the keypoint test split with ground-truth points; show normalization definition.
5. **Keypoint per-joint error plot** — per-joint normalized error/PCK on the same held-out set, with occluded points handled according to protocol.

If binary lameness labels are not defensible, replace figures 1–3 with ordinal analyses (for example, score correlation, weighted agreement, and calibration against continuous score) and state the exact protocol. Do not place pose metrics and lameness metrics on one shared numerical axis. A direct-video versus pose-based comparison can be a secondary table or supplementary figure on a common held-out set, not a claim of equivalent task scores.

**Checklist / acceptance**
- [ ] Each plot generated from saved predictions/ground truth, not manually typed values.
- [ ] Axis labels include units/normalization, sample size, and split.
- [ ] Report confidence intervals or per-subject dots where practical.
- [ ] Add captions stating dataset, task, held-out unit, model, and limitations.
- [ ] Save five figures, prediction CSVs, and `experiment_summary.md` under `outputs/`.

## 6. Go/no-go milestones

- **M0: Data ready** — files decode, labels map, rights note recorded.
- **M1: Split valid** — no group leakage; outcome protocol fixed.
- **M2: Baseline works** — toy tests pass and one baseline produces one video-level prediction per holdout item.
- **M3: Metrics trustworthy** — grouped evaluation, class metrics, confidence intervals, and limitations documented.
- **M4: Pose works** — labeled keypoint split gives measurable AP/PCK and visual overlays pass review.
- **M5: Demo ready** — short attributed video plays end-to-end without claiming diagnosis.

If Sydney label mapping cannot be resolved, stop lameness evaluation and use the dataset only for pipeline/display checks until clarified. If the Colab runtime ends, resume from saved outputs/checkpoints; do not assume its local ephemeral disk persists.

## 7. Final checklist

- [ ] No large raw media or secrets committed to git.
- [ ] Source and rights notes accompany every dataset and public demo.
- [ ] Split is group-based; final test set not used for tuning.
- [ ] Code, seed, package versions, data manifest, split IDs, and checkpoint recorded.
- [ ] Metrics are calculated at the subject/video level and include class-sensitive measures.
- [ ] Five figures are task-appropriate and independently interpretable.
- [ ] Demo is framed as research/prototype, not clinical diagnosis or pasture validation.
