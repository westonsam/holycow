"""Generate held-out keypoint PCK figures from an explicitly labeled CSV.

Run: python ml/src/plot_keypoints.py INPUT.csv --output-dir ml/outputs/figures
     --dataset DATASET --split SPLIT --model MODEL --normalization 'bbox diagonal'
Requires matplotlib for plotting; no dependencies are installed by this script.
The input schema is documented in keypoints.read_observations. Source and
prediction coordinates must be transformed back to the original image space.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from keypoints import evaluate_keypoints, read_observations


def plot_keypoint_results(result: dict, output_dir: str | Path, *, dataset: str, split: str, model: str,
                          joint_threshold: float) -> None:
    if not all(value.strip() for value in (dataset, split, model)):
        raise ValueError("dataset, split and model are required")
    try:
        idx = result["thresholds"].index(joint_threshold)
    except ValueError as exc:
        raise ValueError("joint_threshold must be among computed thresholds") from exc
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Plotting requires matplotlib; install it in the selected runtime before plotting") from exc

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    title = f"{dataset} · {split} · {model}"
    foot = (f"{result['images']} images, {result['subjects']} subjects, "
            f"{result['overall']['eligible']} labeled joints; {result['visibility_policy']}. "
            "Missing predictions count as misses.")
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.plot(result["thresholds"], result["overall"]["pck"], color="#277746", linewidth=2)
    ax.set(xlabel=f"Distance threshold (fraction of {result['normalization']})", ylabel="PCK (fraction of eligible joints)",
           ylim=(0, 1.04), title=f"Keypoint PCK\n{title}")
    ax.grid(alpha=0.2)
    fig.text(0.5, 0.015, foot, ha="center", fontsize=8, wrap=True)
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(out / "keypoint_pck.png", dpi=180)
    plt.close(fig)

    joints = list(result["per_joint"])
    values = [result["per_joint"][joint]["pck"][idx] for joint in joints]
    fig, ax = plt.subplots(figsize=(8, max(4, 0.38 * len(joints) + 2)))
    positions = list(range(len(joints)))
    ax.barh(positions, values, color="#277746")
    ax.set_yticks(positions, joints)
    ax.invert_yaxis()
    ax.set(xlim=(0, 1.04), xlabel=f"PCK at {joint_threshold:g} × {result['normalization']}",
           title=f"Keypoint PCK by joint\n{title}")
    for pos, value, joint in zip(positions, values, joints):
        count = result["per_joint"][joint]["eligible"]
        ax.text(min(value + 0.01, 0.94), pos, f"{value:.2f} (n={count})", va="center", fontsize=8)
    fig.text(0.5, 0.015, foot, ha="center", fontsize=8, wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out / "keypoint_per_joint_pck.png", dpi=180)
    plt.close(fig)
    (out / "keypoint_metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Held-out ground truth joined to keypoint predictions")
    for name in ("output-dir", "dataset", "split", "model", "normalization"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--joint-threshold", type=float, required=True, help="Normalized distance used for joint PCK")
    parser.add_argument("--max-threshold", type=float, required=True)
    parser.add_argument("--visible-only", action="store_true", help="Exclude occluded ground-truth joints")
    args = parser.parse_args(argv)
    if args.max_threshold <= 0 or not 0 <= args.joint_threshold <= args.max_threshold:
        parser.error("require 0 <= joint threshold <= positive max threshold")
    thresholds = sorted(set([i * args.max_threshold / 50 for i in range(51)] + [args.joint_threshold]))
    result = evaluate_keypoints(read_observations(args.csv), thresholds, normalization_name=args.normalization,
                                include_occluded=not args.visible_only)
    plot_keypoint_results(result, args.output_dir, dataset=args.dataset, split=args.split, model=args.model,
                          joint_threshold=args.joint_threshold)


if __name__ == "__main__":
    main()
