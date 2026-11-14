# Stage 3 baseline and evaluation: partial

Stage 3 is **not complete**: no individual-cow image model has been trained, no video-based performance is reported, and the locked test set has not been evaluated. The target is the stage 2 predeclared mean of ten 0–3 observer ratings, an exploratory continuous outcome, not a diagnosis.

## What ran locally

- Local isolated Python 3.12 environment: `torch 2.15.0`, `torchvision 0.29.2`, `opencv-python-headless 5.0.0.93`, `numpy 2.5.4`, `Pillow 13.0.0` on macOS ARM64. CUDA is not available; MPS was not available in the tested execution environment. The environment lives at `/Users/sam/Documents/Codex/2026-11-13/here/work/holy-ml-env`; dependencies tested are listed in `ml/requirements-local.txt`. Other local kernels may use a different Python.
- The official torchvision ResNet-18 ImageNet weights were downloaded from `https://download.pytorch.org/models/resnet18-f37072fd.pth` to ignored `ml/data/pretrained/`. SHA-256: `f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec`.
- A **score-only mean baseline** used the training mean (1.1467 on the 0–3 outcome scale) as the prediction for each of the 10 validation passings (8 cows). Validation MAE was 0.87 and RMSE was 1.105. This is not an image model and is not model accuracy, clinical performance, or test-set performance. Artifacts: `ml/outputs/stage3/mean_validation_recorded/` (git-ignored).
- The regression head fitted four synthetic feature vectors with training RMSE 0.0000784. A separate synthetic-image test ran pretrained ResNet-18, temporal mean pooling and a regression head, with training RMSE 0.0001127. These are wiring/overfit smoke checks on invented inputs and targets, not generalization results; they do not run the real video decoder or validate the cattle pipeline. Artifacts: `ml/outputs/stage3/synthetic_head_smoke/` and `synthetic_encoder_smoke/`.
- The 22 local unit tests pass, including hand-computed regression metrics, grouped-split safeguards, candidate-manifest checks and fail-closed video checks. They do not prove the visual model works on real footage.

## Candidate manifest and video-quality gate

`ml/data/manifests/sydney_candidate_passing_manifest.csv` joins one first-round presentation per passing to the locked cow split and continuous target. It uses one-second guards around the sampled presentation boundaries. These are **candidate windows**: matching the on-screen presentation number does not identify or localize the target animal. No candidate window is approved as an individual-cow input. The candidate manifest has SHA-256 `101e55f96e5fda5c6764e45e3b3623b1ff59f433d54375a2cce0129715b50ef1`.

The unlabelled visual audit (`ml/outputs/stage3/sydney-masked-midpoints-audit.png`, and `sydney-timing-samples-audit.png`) shows multiple cattle, fences/occlusion, background animals, and target animals visible for only parts of the presentations. Uniform full-frame sampling can miss walking or learn scene cues. Presentation numbers must be masked or removed to prevent label leakage, and the unused black lower half must be excluded. All image-based feature extraction in `stage3_regression.py` therefore fails closed, **even if review flags are filled in**, until frame-level target localization and masking are implemented and validated. The mean baseline and synthetic tests do not read source video.

## Before stage 3 can be completed

1. Establish a reproducible way to identify and track the scored cow in each selected presentation; check walking visibility and occlusion, and flag unusable examples.
2. Generate target-specific, time-aligned frames or clips with documented margins, remove presentation overlays, and validate sampling/coordinate alignment. Keep all repeated animals in their assigned split.
3. Run actual tiny-cow-clip overfit testing, handcrafted and pretrained video baselines on training/validation only, with checkpoints and preprocessing metadata. Choose the model without consulting the test set.
4. Once the method and data gates are fixed, generate one prediction per eligible held-out passing and appropriate continuous-target metrics. Report group-aware uncertainty and the same-farm limitations. Do not present binary sensitivity, specificity, ROC or alert colors without a separately justified outcome mapping.

Sydney cow identity grouping does not prove unknown original-recording independence, and data from a fixed-camera dairy setting do not validate drone footage of pasture cattle. CattleLameness source/cow identities and public use rights are unresolved; do not use it to claim an independently grouped result.
