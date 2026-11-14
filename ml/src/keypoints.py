"""Ground-truth keypoint evaluation, separate from lameness classification.

One row represents one annotated joint in a held-out image. Predictions and
annotations must already share the original-image pixel coordinate system.
The caller supplies the predeclared normalizing distance for each observation
and its name. Visibility uses COCO: 0=unlabeled, 1=occluded, 2=visible.
Missing predictions for eligible joints count as PCK misses. PCK is not COCO AP.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class JointObservation:
    image_id: str
    subject_id: str
    joint: str
    gt_x: float
    gt_y: float
    visibility: int
    normalizer: float
    pred_x: Optional[float] = None
    pred_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


def _finite(value: float, field: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")


def validate_observations(rows: Iterable[JointObservation], expected_joints: Optional[Iterable[str]] = None) -> list[JointObservation]:
    """Validate IDs, visibility, bounds, prediction pairs and duplicates.

    If ``expected_joints`` is supplied, each image must have exactly one row for
    each named joint, including unlabeled joints. The schema is not inferred.
    """
    items = list(rows)
    if not items:
        raise ValueError("no keypoint observations supplied")
    expected = None if expected_joints is None else set(expected_joints)
    if expected is not None and (not expected or "" in expected):
        raise ValueError("expected_joints must contain non-empty names")
    seen = set()
    by_image = defaultdict(set)
    image_info = {}
    for row in items:
        if not row.image_id or not row.subject_id or not row.joint:
            raise ValueError("image_id, subject_id and joint are required")
        key = (row.image_id, row.joint)
        if key in seen:
            raise ValueError(f"duplicate image/joint: {key}")
        seen.add(key)
        by_image[row.image_id].add(row.joint)
        if row.visibility not in (0, 1, 2):
            raise ValueError(f"invalid visibility for {key}: {row.visibility}")
        _finite(row.normalizer, "normalizer")
        if row.normalizer <= 0:
            raise ValueError(f"normalizer must be positive for {key}")
        for value, name in ((row.gt_x, "gt_x"), (row.gt_y, "gt_y")):
            _finite(value, name)
        if (row.pred_x is None) != (row.pred_y is None):
            raise ValueError(f"prediction must contain both coordinates or neither for {key}")
        if row.pred_x is not None:
            _finite(row.pred_x, "pred_x")
            _finite(row.pred_y, "pred_y")
        if (row.width is None) != (row.height is None):
            raise ValueError("width and height must be supplied together")
        if row.width is not None:
            _finite(row.width, "width")
            _finite(row.height, "height")
            if row.width <= 0 or row.height <= 0:
                raise ValueError("image dimensions must be positive")
            if row.visibility and not (0 <= row.gt_x < row.width and 0 <= row.gt_y < row.height):
                raise ValueError(f"ground truth outside image for {key}")
        info = (row.subject_id, row.width, row.height)
        if row.image_id in image_info and image_info[row.image_id] != info:
            raise ValueError(f"inconsistent subject or image dimensions for image {row.image_id}")
        image_info[row.image_id] = info
    if expected is not None:
        for image, joints in by_image.items():
            if joints != expected:
                raise ValueError(f"image {image}: missing {sorted(expected-joints)}; unexpected {sorted(joints-expected)}")
    return items


def evaluate_keypoints(rows: Iterable[JointObservation], thresholds: Iterable[float], *, normalization_name: str,
                       include_occluded: bool = True, expected_joints: Optional[Iterable[str]] = None) -> dict:
    """Calculate pooled keypoint PCK and per-joint normalized error.

    Eligible annotated joints have equal weight, not subjects. Subject/image
    counts are included; error means cover only returned predictions and are
    paired with missing counts to avoid hiding detector failures.
    """
    if not normalization_name.strip():
        raise ValueError("normalization_name is required")
    limits = [float(value) for value in thresholds]
    if not limits or any(not math.isfinite(x) or x < 0 for x in limits):
        raise ValueError("thresholds must be nonempty, finite and non-negative")
    if any(a >= b for a, b in zip(limits, limits[1:])):
        raise ValueError("thresholds must be strictly increasing")
    items = validate_observations(rows, expected_joints)
    eligible = [r for r in items if r.visibility == 2 or (include_occluded and r.visibility == 1)]
    if not eligible:
        raise ValueError("no eligible ground-truth keypoints under selected visibility policy")

    def distance(row):
        if row.pred_x is None:
            return None
        return math.hypot(row.pred_x - row.gt_x, row.pred_y - row.gt_y) / row.normalizer

    grouped = defaultdict(list)
    distances = []
    for item in eligible:
        error = distance(item)
        distances.append(error)
        grouped[item.joint].append(error)

    def summarize(values):
        predicted = [value for value in values if value is not None]
        return {"eligible": len(values), "predicted": len(predicted), "missing": len(values)-len(predicted),
                "mean_normalized_error": sum(predicted)/len(predicted) if predicted else None,
                "pck": [sum(x is not None and x <= t for x in values)/len(values) for t in limits]}

    return {"task": "keypoint_detection", "normalization": normalization_name,
            "visibility_policy": "labeled including occluded" if include_occluded else "visible only",
            "thresholds": limits, "images": len({r.image_id for r in eligible}),
            "subjects": len({r.subject_id for r in eligible}), "overall": summarize(distances),
            "per_joint": {name: summarize(values) for name, values in sorted(grouped.items())}}


def read_observations(path: str | Path) -> list[JointObservation]:
    """Read one row per joint: image_id, subject_id, joint, gt_x, gt_y,
    visibility, normalizer, pred_x, pred_y; optional width,height. Blank
    prediction pairs mean missing. Inputs must be sourced from real labels.
    """
    required = {"image_id", "subject_id", "joint", "gt_x", "gt_y", "visibility", "normalizer", "pred_x", "pred_y"}
    result = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing CSV columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            def optional_float(name):
                value = (row.get(name) or "").strip()
                return float(value) if value else None
            try:
                result.append(JointObservation(image_id=row["image_id"].strip(), subject_id=row["subject_id"].strip(),
                    joint=row["joint"].strip(), gt_x=float(row["gt_x"]), gt_y=float(row["gt_y"]),
                    visibility=int(row["visibility"]), normalizer=float(row["normalizer"]),
                    pred_x=optional_float("pred_x"), pred_y=optional_float("pred_y"),
                    width=optional_float("width"), height=optional_float("height")))
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"invalid keypoint CSV row {line_number}: {exc}") from exc
    return result
