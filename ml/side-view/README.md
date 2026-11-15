# Cattle keypoint notebook

Open [cattle_keypoint_detection.ipynb](cattle_keypoint_detection.ipynb) with the
existing Python 3.11 kernel and run its cells in order. All data preparation,
validation, model implementation, training, evaluation, plotting, and inference
code lives in the notebook. No MMPose or MMCV installation is required.

The notebook uses the installed Python 3.11.4, PyTorch 2.2.0+cu121 and
torchvision 0.17.0+cu121 environment, including NumPy 1.26.4, pandas 2.1.4,
Pillow 10.1.0, OpenCV 4.9.0, matplotlib 3.10.0, and tqdm 4.66.1. It does not
change the environment. CUDA is selected when available; CPU also works.
The notebook preloads matplotlib's renderer before torch/OpenCV to avoid a
native DLL import-order crash observed in this Windows environment.

Training has **not** been run. Final metrics and example predictions are
generated when you choose to execute the notebook; no accuracy is claimed yet.

To execute without opening the Jupyter UI, from the repository root:

```powershell
python ml/execute_keypoint_notebook.py
```

The helper executes the notebook itself and saves its outputs after each cell.
It requires the already installed nbclient, nbformat and ipykernel packages.
The first execution needs internet access to fetch the dataset and ImageNet
weights. Subsequent executions use locally verified data and checkpoints.

Training uses a pretrained ResNet-18 and a learned heatmap decoder for the
reference dataset's 18 cattle joints. Default budget: 100 epochs, with 20 epochs
of validation patience, mixed precision, batch size 16, and 256×192 crops.
Settings are in the first code cell. Use a new run directory if changing them.

## Monitoring and pausing

Artifacts are written to `ml/runs/cattle_resnet18_p1A/`:

- `history.csv`: training loss, validation loss, PCK, learning rate and epoch time.
- `status.json`: current state and most recently completed epoch.
- `learning_curves.png`: plots updated after each epoch.
- `last.pt`: complete resumable training state.
- `best.pt`: checkpoint selected exclusively by validation PCK@0.05.
- `data_audit.csv` and `split_manifest.json`: verified data partitions.
- `test_metrics.csv`, `per_joint_metrics.csv` and `evaluation.json`: final scores.
- `test_predictions.npz`: original-image predictions, bound to checkpoint hash.
- `test_performance.png`, `test_examples.png`, `test_failures.png`: visual results.
- `benchmark.json`: crop-network inference speed and memory use.

Read live progress from another terminal:

```powershell
Get-Content ml/runs/cattle_resnet18_p1A/status.json
Get-Content ml/runs/cattle_resnet18_p1A/history.csv -Tail 10
```

Pause at the next batch boundary:

```powershell
New-Item ml/runs/cattle_resnet18_p1A/PAUSE -ItemType File -Force
```

The interrupted epoch is discarded. Resume by removing the pause marker and
rerunning the notebook (or execution helper):

```powershell
Remove-Item -LiteralPath ml/runs/cattle_resnet18_p1A/PAUSE
python ml/execute_keypoint_notebook.py
```

Interrupting the training cell also pauses safely. Hard termination loses at
most the current epoch. Do not run two trainers in the same run directory.
Only load trusted checkpoints produced by this notebook.

## Data and evaluation protocol

Source: [yww0411/Livestock-keypoint-detection](https://github.com/yww0411/Livestock-keypoint-detection),
commit `d2fbc81e6181751f2e65eb6e393b10a9c7e16dfe`.
Data is CC BY 4.0; the downloaded dataset license and provenance are retained
under `ml/data/reference/`. See the notebook for the paper citation.

Use cattle fold p1A, holding source A out for testing and training on B/C.
The supplied train/validation files share nine original filename groups.
Conservatively move their ten training members into validation. Final split:
604 training, 78 validation, 206 test images. There are no exact image hashes
or original filenames shared across these final partitions. The notebook
rechecks this on every execution. Animal/video identifiers are unavailable,
so animal-independent separation cannot be verified.

Evaluation uses supplied ground-truth cattle boxes. PCK@0.05 and PCK@0.10
normalize Euclidean error by the original box diagonal. NME is mean normalized
error; AUC020 integrates the PCK curve from 0 to 0.20 and divides by 0.20.
Report visible/occluded and per-joint scores, a train-only mean-shape baseline,
and an image-bootstrap 95% confidence interval for test PCK@0.05.

These are localization metrics with oracle boxes, not full-frame detection AP
or the paper's OKS AP. Test results do not establish drone-view performance.
Further model selection must use validation data, not the reported test set.

Downloaded data, weights and local runs are ignored by Git; the notebook and
its rendered results are retained as the reviewable artifact.
