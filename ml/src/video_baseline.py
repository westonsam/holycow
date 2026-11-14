"""ResNet-18 frame encoder + temporal mean baseline.

Run explicitly after the label/outcome mapping and group splits have been audited:
  python -m ml.src.video_baseline MANIFEST OUTPUT_DIR --weights /path/to/resnet18-f37072fd.pth
No weights or other resources are downloaded by this module. Test split is never
read during fitting; this script selects checkpoints by validation loss only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

from .video_io import decode_evenly_spaced, read_manifest


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--weights", type=Path, required=True,
                        help="Local torchvision ResNet-18 ImageNet state_dict; never downloaded")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    if min(args.frames, args.epochs, args.patience, args.batch_size) < 1 or args.learning_rate <= 0:
        raise ValueError("frames, epochs, patience, batch size, and learning rate must be positive")
    if not args.weights.is_file():
        raise FileNotFoundError(f"local pretrained weight file not found: {args.weights}")
    records = read_manifest(args.manifest)
    subsets = {name: [r for r in records if r["split"] == name] for name in ("train", "validation")}
    if any(not subset for subset in subsets.values()):
        raise ValueError("manifest must have nonempty train and validation splits")
    if {r["label"] for r in subsets["train"]} != {0, 1}:
        raise ValueError("training split must contain both audited binary classes")
    try:
        import torch
        from torch import nn
        from torch.utils.data import Dataset, DataLoader
        from torchvision.models import resnet18
        from torchvision.transforms import Compose, Resize, CenterCrop, ToTensor, Normalize
        import torchvision
    except ImportError as exc:
        raise RuntimeError("baseline requires torch, torchvision, Pillow and opencv-python in the runtime") from exc

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # torchvision ResNet18_Weights.IMAGENET1K_V1 inference preprocessing.
    preprocess = Compose([Resize(256), CenterCrop(224), ToTensor(),
                          Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])

    class ClipDataset(Dataset):
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def __getitem__(self, index):
            row = self.rows[index]
            frames = decode_evenly_spaced(row["path"], args.frames)
            return torch.stack([preprocess(frame) for frame in frames]), row["label"]

    class TemporalMean(nn.Module):
        def __init__(self):
            super().__init__()
            encoder = resnet18(weights=None)
            # Safe loading is supported by modern PyTorch; weights are user-supplied.
            encoder.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True))
            in_features = encoder.fc.in_features
            encoder.fc = nn.Identity()
            self.encoder = encoder
            self.classifier = nn.Linear(in_features, 2)
        def forward(self, clips):
            batch, time, channels, height, width = clips.shape
            features = self.encoder(clips.reshape(batch * time, channels, height, width))
            return self.classifier(features.reshape(batch, time, -1).mean(dim=1))

    model = TemporalMean().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    criterion = nn.CrossEntropyLoss()
    generator = torch.Generator().manual_seed(args.seed)
    loaders = {name: DataLoader(ClipDataset(rows), batch_size=args.batch_size,
                                shuffle=name == "train", generator=generator, num_workers=0)
               for name, rows in subsets.items()}
    args.output.mkdir(parents=True, exist_ok=True)
    best_loss, stale = float("inf"), 0
    for epoch in range(args.epochs):
        stats = {}
        for name, loader in loaders.items():
            training = name == "train"
            model.train(training)
            total_loss = total = 0
            with torch.set_grad_enabled(training):
                for clips, labels in loader:
                    clips, labels = clips.to(device), labels.to(device)
                    if training: optimizer.zero_grad(set_to_none=True)
                    logits = model(clips)
                    loss = criterion(logits, labels)
                    if training:
                        loss.backward()
                        optimizer.step()
                    total_loss += float(loss.detach()) * labels.size(0)
                    total += labels.size(0)
            stats[name] = total_loss / total
        print(f"epoch {epoch + 1}: train loss={stats['train']:.4f}, validation loss={stats['validation']:.4f}", flush=True)
        if stats["validation"] < best_loss:
            best_loss, stale = stats["validation"], 0
            torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "epoch": epoch + 1,
                        "best_validation_loss": best_loss}, args.output / "best.pt")
        else:
            stale += 1
            if stale >= args.patience: break
    # No model outputs are presented as veterinary diagnoses.
    config = {"model": "resnet18_temporal_mean", "seed": args.seed, "frames": args.frames,
              "epochs_requested": args.epochs, "patience": args.patience, "batch_size": args.batch_size,
              "learning_rate": args.learning_rate, "device": str(device), "torch": torch.__version__,
              "torchvision": torchvision.__version__, "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
              "preprocessing": "Resize(256), CenterCrop(224), ImageNet V1 mean/std", "best_validation_loss": best_loss,
              "positive_label": 1, "caveat": "Experimental research only; not a diagnosis."}
    (args.output / "config.json").write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    main()
