"""Small, explicit utilities for one-clip-per-record video experiments.

OpenCV and Pillow are runtime dependencies; imports are deferred so split and
manifest checks can run without downloading or installing any packages.
"""
from __future__ import annotations
from pathlib import Path
import csv
import math


def evenly_spaced_indices(frame_count: int, samples: int) -> list[int]:
    """Indices spanning the entire clip; short clips repeat frames deliberately."""
    if frame_count <= 0 or samples <= 0:
        raise ValueError("frame_count and samples must be positive")
    if samples == 1:
        return [(frame_count - 1) // 2]
    return [round(i * (frame_count - 1) / (samples - 1)) for i in range(samples)]


def read_manifest(path: str | Path) -> list[dict]:
    """Read explicit clip paths, IDs, groups, labels and locked split assignments.

    Labels are externally audited values, never inferred from file or folder names.
    Paths in the CSV are resolved relative to the CSV, not the current directory.
    The group column must represent a conservative animal/source grouping; this
    function cannot detect undeclared duplicate animals or footage.
    """
    path = Path(path).expanduser().resolve()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"clip_id", "group_id", "path", "label", "split"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"manifest missing columns: {', '.join(sorted(missing))}")
        records = []
        for line, row in enumerate(reader, 2):
            if any(not (row.get(k) or "").strip() for k in required):
                raise ValueError(f"missing required value on manifest line {line}")
            try:
                label = int(row["label"])
            except ValueError as exc:
                raise ValueError(f"non-integer binary label on line {line}") from exc
            if label not in (0, 1) or row["split"].strip() not in {"train", "validation", "test"}:
                raise ValueError(f"invalid label or split on line {line}")
            raw_path = Path(row["path"].strip()).expanduser()
            resolved = (path.parent / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
            records.append({"clip_id": row["clip_id"].strip(), "group_id": row["group_id"].strip(),
                            "path": str(resolved), "label": label, "split": row["split"].strip()})
    if not records:
        raise ValueError("empty manifest")
    if len({r["clip_id"] for r in records}) != len(records):
        raise ValueError("clip_id must be unique")
    group_splits: dict[str, set[str]] = {}
    path_splits: dict[str, set[str]] = {}
    for r in records:
        group_splits.setdefault(r["group_id"], set()).add(r["split"])
        path_splits.setdefault(r["path"], set()).add(r["split"])
    if any(len(v) > 1 for v in group_splits.values()):
        raise ValueError("group appears in more than one split")
    if any(len(v) > 1 for v in path_splits.values()):
        raise ValueError("same clip path appears in more than one split")
    return records


def decode_evenly_spaced(path: str | Path, samples: int):
    """Decode sampled RGB PIL images. Failed reads are errors, never silent drops."""
    try:
        import cv2
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("video decoding requires opencv-python and Pillow") from exc
    path = Path(path)
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"unable to open video: {path}")
        reported = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(reported) or reported < 1:
            raise ValueError(f"invalid frame count for {path}: {reported}")
        indices = evenly_spaced_indices(int(reported), samples)
        frames = []
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, bgr = capture.read()
            if not ok or bgr is None:
                raise ValueError(f"failed to decode frame {index} of {path}")
            frames.append(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
        return frames
    finally:
        capture.release()
