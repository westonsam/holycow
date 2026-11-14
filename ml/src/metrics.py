"""Binary video-level metrics and group-resampled bootstrap confidence intervals.

Labels must already be mapped by a documented, fixed protocol. AUC is ROC area;
AUPRC here means average precision (step-wise area), not trapezoidal PR area.
"""
from __future__ import annotations

import math
import random


def _divide(numerator, denominator):
    return numerator / denominator if denominator else None


def binary_metrics(labels, probabilities, threshold=0.5):
    """Calculate metrics for one prediction per held-out video.

    Undefined metrics return None (e.g. AUROC when one class is absent).
    Sensitivity, specificity, and precision are None when their denominators are
    zero; F1 is zero when positives exist but no positive prediction is correct.
    """
    labels, probabilities = list(labels), list(probabilities)
    if not labels or len(labels) != len(probabilities):
        raise ValueError('labels and probabilities must have equal nonzero length')
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold must be between zero and one')
    if any(type(y) not in (int, bool) or y not in (0, 1) for y in labels):
        raise ValueError('binary labels must be 0 or 1')
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0 or p > 1 for p in probabilities):
        raise ValueError('probabilities must be finite values between zero and one')
    tp = sum(y == 1 and p >= threshold for y, p in zip(labels, probabilities))
    fp = sum(y == 0 and p >= threshold for y, p in zip(labels, probabilities))
    tn = sum(y == 0 and p < threshold for y, p in zip(labels, probabilities))
    fn = sum(y == 1 and p < threshold for y, p in zip(labels, probabilities))
    recall = _divide(tp, tp + fn)
    specificity = _divide(tn, tn + fp)
    precision = _divide(tp, tp + fp)
    f1 = _divide(2 * tp, 2 * tp + fp + fn)
    # Pairwise concordance automatically handles ties in AUROC.
    positives = [p for y, p in zip(labels, probabilities) if y == 1]
    negatives = [p for y, p in zip(labels, probabilities) if y == 0]
    auroc = (_divide(sum((a > b) + 0.5 * (a == b) for a in positives for b in negatives),
                     len(positives) * len(negatives)))
    # Group tied scores before stepping precision/recall to avoid ordering bias.
    points = sorted(zip(probabilities, labels), reverse=True)
    seen = correct = 0
    ap = 0.0
    i = 0
    while i < len(points):
        j = i
        while j < len(points) and points[j][0] == points[i][0]:
            correct += points[j][1]
            seen += 1
            j += 1
        new_positives = sum(y for _, y in points[i:j])
        if positives:
            ap += (new_positives / len(positives)) * (correct / seen)
        i = j
    return {
        'n': len(labels), 'threshold': threshold, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'accuracy': (tp + tn) / len(labels),
        'balanced_accuracy': ((recall + specificity) / 2 if recall is not None and specificity is not None else None),
        'sensitivity': recall, 'specificity': specificity, 'precision': precision, 'f1': f1,
        'auroc': auroc, 'auprc': ap if positives else None,
        'positive_prevalence': len(positives) / len(labels),
    }


def grouped_bootstrap(labels, probabilities, groups, *, n_bootstrap=1000, seed=42, threshold=0.5, confidence=0.95):
    """Percentile CIs by resampling groups with replacement, not individual frames.

    A group's complete set of video predictions is resampled together. When a
    statistic is undefined for a replicate (e.g., single-class AUROC), that
    replicate is excluded for that metric and its count is reported.
    """
    labels, probabilities, groups = list(labels), list(probabilities), list(groups)
    point = binary_metrics(labels, probabilities, threshold)
    if len(groups) != len(labels) or any(g is None or str(g).strip() == '' for g in groups):
        raise ValueError('one nonempty group ID is required for each prediction')
    if n_bootstrap < 1 or not 0 < confidence < 1:
        raise ValueError('invalid bootstrap count or confidence level')
    unique = list(dict.fromkeys(groups))
    if len(unique) < 2:
        raise ValueError('at least two independent groups required for bootstrap')
    indices = {g: [] for g in unique}
    for i, g in enumerate(groups):
        indices[g].append(i)
    keys = ('accuracy', 'balanced_accuracy', 'sensitivity', 'specificity', 'precision', 'f1', 'auroc', 'auprc')
    collected = {k: [] for k in keys}
    rng = random.Random(seed)
    for _ in range(n_bootstrap):
        selected = [i for g in rng.choices(unique, k=len(unique)) for i in indices[g]]
        m = binary_metrics([labels[i] for i in selected], [probabilities[i] for i in selected], threshold)
        for key in keys:
            if m[key] is not None:
                collected[key].append(m[key])

    def percentile(values, q):
        if not values:
            return None
        values = sorted(values)
        at = q * (len(values) - 1)
        lo = int(at)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (at - lo)

    alpha = (1 - confidence) / 2
    intervals = {key: {'low': percentile(values, alpha), 'high': percentile(values, 1 - alpha),
                       'valid_replicates': len(values), 'total_replicates': n_bootstrap}
                 for key, values in collected.items()}
    return {'point_estimate': point, 'confidence': confidence, 'n_groups': len(unique), 'intervals': intervals}
