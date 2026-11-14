"""Render separate binary held-out ROC, PR and calibration plots from predictions.

CSV requires clip_id,group_id,split,label,probability. The caller must supply
an audited, fixed binary outcome definition and choose a single held-out split.
"""
import argparse
import csv
from pathlib import Path

from .metrics import binary_metrics


def load_predictions(path, split):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'clip_id', 'group_id', 'split', 'label', 'probability'}
        if required - set(reader.fieldnames or []):
            raise ValueError('prediction CSV missing required columns')
        rows = [r for r in reader if r['split'] == split]
    if not rows or any(not r['clip_id'].strip() or not r['group_id'].strip() for r in rows):
        raise ValueError('held-out predictions and IDs are required')
    if len({r['clip_id'] for r in rows}) != len(rows):
        raise ValueError('expected exactly one prediction per clip')
    labels = [int(r['label']) for r in rows]
    scores = [float(r['probability']) for r in rows]
    metrics = binary_metrics(labels, scores)
    if metrics['auroc'] is None:
        raise ValueError('both labels must be represented for ROC/PR figures')
    return labels, scores, len({r['group_id'] for r in rows}), metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('predictions', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--split', choices=('validation', 'test'), required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--outcome-definition', required=True)
    args = parser.parse_args()
    labels, scores, groups, metrics = load_predictions(args.predictions, args.split)
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import roc_curve, precision_recall_curve
        from sklearn.calibration import calibration_curve
    except ImportError as error:
        raise SystemExit('Install/use matplotlib and scikit-learn in the experiment runtime') from error
    args.output.mkdir(parents=True, exist_ok=True)
    caption = f'{args.dataset} · {args.model} · {args.split}: {len(labels)} clips, {groups} groups\n{args.outcome_definition}; exploratory, small sample'
    fpr, tpr, _ = roc_curve(labels, scores)
    precision, recall, _ = precision_recall_curve(labels, scores)
    fraction, mean_pred = calibration_curve(labels, scores, n_bins=min(5, len(labels)), strategy='quantile')
    for name, x, y, xlabel, ylabel, line in [
        ('roc', fpr, tpr, 'False-positive rate', 'Sensitivity', f'AUROC {metrics["auroc"]:.2f}'),
        ('precision_recall', recall, precision, 'Recall', 'Precision', f'AP {metrics["auprc"]:.2f}; prevalence {metrics["positive_prevalence"]:.2f}'),
        ('calibration', mean_pred, fraction, 'Mean predicted probability', 'Observed positive fraction', 'Quantile bins; interpret cautiously'),
    ]:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(x, y, marker='o', label=line)
        if name in ('roc', 'calibration'): ax.plot([0, 1], [0, 1], '--', color='gray', label='Reference')
        if name == 'precision_recall': ax.axhline(metrics['positive_prevalence'], linestyle='--', color='gray', label='Prevalence')
        ax.set(xlabel=xlabel, ylabel=ylabel, xlim=(0, 1), ylim=(0, 1), title=name.replace('_', ' ').title())
        ax.legend(); fig.text(.5, .01, caption, ha='center', fontsize=8, wrap=True)
        fig.tight_layout(rect=(0, .08, 1, 1)); fig.savefig(args.output / f'{name}.png', dpi=180); plt.close(fig)
    print('Saved three binary outcome figures. Compute group bootstrap CIs separately with metrics.grouped_bootstrap.')


if __name__ == '__main__':
    main()
