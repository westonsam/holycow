"""Test official ResNet-18 encoder and regression head using synthetic images only.

This exercises no cattle footage, labels, or holdout data. It does not validate
video loading, target localization, gait features, or model generalization.
"""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--weights', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    if not args.weights.is_file(): raise FileNotFoundError(args.weights)
    if args.output.exists(): raise FileExistsError(args.output)
    import torch
    import torchvision
    from torchvision.models import resnet18
    from .stage3_regression import digest, fit_linear, eval_linear, regression_metrics
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    encoder = resnet18(weights=None)
    encoder.load_state_dict(torch.load(args.weights, map_location='cpu', weights_only=True))
    encoder.fc = torch.nn.Identity()
    encoder.eval()
    frames = torch.rand((4, 2, 3, 224, 224))
    with torch.no_grad(): features = encoder(frames.flatten(0, 1)).reshape(4, 2, -1).mean(1).numpy()
    truth = [0.3, 0.9, 1.9, 2.7]
    model = fit_linear(features, truth, features, truth, seed=args.seed, epochs=3000, patience=300, learning_rate=.01)
    metrics = regression_metrics(truth, eval_linear(model, features))
    metrics.update({'passed':metrics['rmse'] < .1, 'scope':'synthetic images: frozen pretrained ResNet-18 + temporal mean + linear head; no video or generalization validation',
                    'weights_sha256':digest(args.weights), 'torch':torch.__version__, 'torchvision':torchvision.__version__, 'seed':args.seed})
    args.output.mkdir(parents=True)
    (args.output/'synthetic_encoder_smoke.json').write_text(json.dumps(metrics, indent=2)+'\n')
    print(json.dumps(metrics, indent=2))
    if not metrics['passed']: raise SystemExit('synthetic encoder/head smoke did not fit')


if __name__=='__main__': main()
