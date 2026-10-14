"""A compact, auditable SleepPACNet-style reproduction.

This is intentionally a small implementation rather than a claim of byte-for-byte
reproduction. The public paper specifies the signal construction, filters, Hilbert
phase branch, subject-wise split, weighted loss, and metrics; its supplementary
architecture table is not machine-readable from the article page, so the channel
widths below are kept modest and explicit.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from scipy.signal import butter, hilbert, resample_poly, sosfiltfilt
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from torch import nn
from torch.utils.data import DataLoader, Dataset


STAGES = ["W", "N1", "N2", "N3", "REM"]


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return ((x - np.nanmean(x)) / (np.nanstd(x) + 1e-6)).astype(np.float32)


def bandpass(x: np.ndarray, lo: float, hi: float, fs: float) -> np.ndarray:
    sos = butter(6, [lo, hi], btype="bandpass", fs=fs, output="sos")
    # Short synthetic records can be shorter than the default padding length.
    padlen = min(x.shape[-1] - 1, 3 * (2 * sos.shape[0] + 1))
    return sosfiltfilt(sos, x, axis=-1, padlen=max(1, padlen)).astype(np.float32)


def make_pac_inputs(epoch: np.ndarray, fs: float = 100.0) -> tuple[np.ndarray, np.ndarray]:
    """Return F_r and F_i, each shaped [2, T]."""
    low = bandpass(epoch, 0.5, 8.0, fs)
    high = bandpass(epoch, 8.0, 30.0, fs)
    analytic = hilbert(low).astype(np.complex64)
    fr = np.stack([analytic.real, high], axis=0).astype(np.float32)
    fi = np.stack([analytic.imag, high], axis=0).astype(np.float32)
    return fr, fi


def prepare_epoch(epoch: np.ndarray, source_fs: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply the paper's 250->100 Hz resampling and per-epoch z-normalization."""
    if source_fs != 100:
        epoch = resample_poly(epoch, 100, int(round(source_fs))).astype(np.float32)
    n = 3000
    if len(epoch) < n:
        epoch = np.pad(epoch, (0, n - len(epoch)))
    epoch = epoch[:n]
    epoch = zscore(epoch)
    fr, fi = make_pac_inputs(epoch)
    return epoch[None, :], fr, fi


class EpochDataset(Dataset):
    def __init__(self, x: list[np.ndarray], y: list[int]):
        self.x = list(x)
        self.y = np.asarray(y, dtype=np.int64)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, i: int):
        raw, fr, fi = self.x[i]
        return (
            torch.from_numpy(raw),
            torch.from_numpy(fr),
            torch.from_numpy(fi),
            torch.tensor(self.y[i]),
        )


class PACBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.r1 = nn.Conv2d(1, 12, kernel_size=(2, 1))
        self.r2 = nn.Conv2d(12, 24, kernel_size=(1, 100))
        self.i1 = nn.Conv2d(1, 12, kernel_size=(2, 1))
        self.i2 = nn.Conv2d(12, 24, kernel_size=(1, 100))
        self.drop = nn.Dropout(0.5)
        self.pool = nn.MaxPool2d(kernel_size=(1, 4), stride=(1, 2))

    def _one(self, x: torch.Tensor, first: nn.Module, second: nn.Module) -> torch.Tensor:
        x = x.unsqueeze(1)  # B, 1, 2, T
        x = torch.nn.functional.gelu(first(x))
        x = torch.nn.functional.gelu(second(x))
        return x

    def forward(self, fr: torch.Tensor, fi: torch.Tensor) -> torch.Tensor:
        r = self._one(fr, self.r1, self.r2)
        im = self._one(fi, self.i1, self.i2)
        x = torch.sqrt(torch.clamp(r.square() + im.square(), min=1e-8))
        x = self.pool(self.drop(x)).squeeze(2)
        return x


class RawBlock(nn.Module):
    def __init__(self, first_kernel: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, first_kernel),
            nn.GELU(),
            nn.MaxPool1d(4, 2),
            nn.Dropout(0.5),
            nn.Conv1d(12, 24, 8),
            nn.GELU(),
            nn.Conv1d(24, 24, 8),
            nn.GELU(),
            nn.MaxPool1d(4, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class SleepPACNet(nn.Module):
    def __init__(self, n_classes: int = 5):
        super().__init__()
        self.pac = PACBranch()
        self.raw_narrow = RawBlock(50)
        self.raw_wide = RawBlock(200)
        self.raw_refine = nn.Sequential(
            nn.Conv1d(48, 48, 8, stride=2),
            nn.ReLU(),
            nn.Conv1d(48, 32, 3),
            nn.ReLU(),
            nn.AvgPool1d(4, 2),
        )
        self.fuse = nn.Sequential(
            nn.Conv1d(56, 48, 8, stride=2),
            nn.ReLU(),
            nn.MaxPool1d(4, 2),
            nn.Dropout(0.5),
        )
        with torch.no_grad():
            dummy = torch.zeros(1, 1, 3000)
            p = self.pac(torch.zeros(1, 2, 3000), torch.zeros(1, 2, 3000))
            rn, rw = self.raw_narrow(dummy), self.raw_wide(dummy)
            rw = nn.functional.interpolate(rw, size=rn.shape[-1], mode="linear", align_corners=False)
            r = self.raw_refine(torch.cat([rn, rw], dim=1))
            if p.shape[-1] != r.shape[-1]:
                r = nn.functional.interpolate(r, size=p.shape[-1], mode="linear", align_corners=False)
            fused = self.fuse(torch.cat([p, r], dim=1))
            flat = int(np.prod(fused.shape[1:]))
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(flat, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, n_classes),
        )

    def forward(self, raw: torch.Tensor, fr: torch.Tensor, fi: torch.Tensor) -> torch.Tensor:
        p = self.pac(fr, fi)
        rn, rw = self.raw_narrow(raw), self.raw_wide(raw)
        rw = nn.functional.interpolate(rw, size=rn.shape[-1], mode="linear", align_corners=False)
        r = self.raw_refine(torch.cat([rn, rw], dim=1))
        # The paper concatenates the PAC and raw maps before a final 1-D CNN.
        # Interpolation is only a shape alignment step and does not add labels.
        if p.shape[-1] != r.shape[-1]:
            r = nn.functional.interpolate(r, size=p.shape[-1], mode="linear", align_corners=False)
        return self.head(self.fuse(torch.cat([p, r], dim=1)))


def discover_h5_paths(root: Path) -> list[Path]:
    return sorted(root.rglob("*.h5"))


def _leaf_map(h5) -> dict[str, np.ndarray]:
    out = {}
    def visit(name, obj):
        if hasattr(obj, "shape") and len(obj.shape) >= 1:
            out[name.lower()] = np.asarray(obj)
    h5.visititems(visit)
    return out


def _find_signal(leaves: dict[str, np.ndarray], *parts: str) -> tuple[str, np.ndarray] | None:
    wanted = [p.lower().replace("-", "_") for p in parts]
    for name, arr in leaves.items():
        norm = name.replace("-", "_")
        if all(p in norm for p in wanted):
            return name, arr
    return None


def load_dreem_h5(path: Path, max_epochs: int | None = None):
    import h5py
    with h5py.File(path, "r") as h5:
        leaves = _leaf_map(h5)
        hyp = None
        for name, arr in leaves.items():
            if "hypnogram" in name or name.endswith("/hypnogram"):
                hyp = np.asarray(arr).reshape(-1)
                break
        if hyp is None:
            raise ValueError(f"No hypnogram found in {path}")
        a = _find_signal(leaves, "fp1", "f3")
        b = _find_signal(leaves, "fp2", "f4")
        c = _find_signal(leaves, "f3", "f4")
        if not (a and b and c):
            raise ValueError(f"Could not find Fp1-F3/Fp2-F4/F3-F4 in {path}; available={list(leaves)[:20]}")
        fs = 250.0
        signals = [np.asarray(q[1]).reshape(-1) for q in (a, b, c)]
        n = min(map(len, signals))
        n = min(n, len(hyp) * int(fs * 30))
        signals = [q[:n] for q in signals]
        x = signals[0] - signals[1] + signals[2]
        n_epochs = min(len(hyp), n // int(fs * 30))
        if max_epochs:
            n_epochs = min(n_epochs, max_epochs)
        xs, ys = [], []
        for i in range(n_epochs):
            label = int(hyp[i])
            if label not in range(5):
                continue
            seg = x[i * int(fs * 30):(i + 1) * int(fs * 30)]
            xs.append(prepare_epoch(seg, fs))
            ys.append(label)
        return xs, ys, {"file": str(path), "n_epochs": len(ys), "signals": [a[0], b[0], c[0]]}


def synthetic_subjects(n_subjects: int = 5, epochs_per_subject: int = 100, seed: int = 7):
    rng = np.random.default_rng(seed)
    records = []
    for s in range(n_subjects):
        xs, ys = [], []
        t = np.arange(3000, dtype=np.float32) / 100
        for i in range(epochs_per_subject):
            y = i % 5
            base = rng.normal(0, 0.25, 3000)
            if y == 0:
                sig = base + 0.4 * np.sin(2 * np.pi * 18 * t)
            elif y == 1:
                sig = base + 0.4 * np.sin(2 * np.pi * 6 * t)
            elif y == 2:
                sig = base + 0.8 * np.sin(2 * np.pi * 13 * t) + 0.8 * np.sin(2 * np.pi * 1.2 * t)
            elif y == 3:
                sig = base + 1.2 * np.sin(2 * np.pi * 1.2 * t)
            else:
                sig = base + 0.5 * np.sin(2 * np.pi * 6 * t) + 0.3 * np.sin(2 * np.pi * 20 * t)
            xs.append(prepare_epoch(sig.astype(np.float32), 100))
            ys.append(y)
        records.append((xs, ys, {"file": f"synthetic-{s:02d}", "n_epochs": len(ys)}))
    return records


def make_weights(labels: Iterable[int]) -> torch.Tensor:
    labels = np.asarray(list(labels), dtype=np.int64)
    counts = np.bincount(labels, minlength=5).astype(np.float64)
    total = counts.sum()
    mu = np.array([1.5, 1.8, 1.0, 1.5, 1.2], dtype=np.float64) / 5
    weights = mu * np.maximum(1.0, np.log(np.maximum(1.0, mu * total / np.maximum(1.0, counts))))
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32)


def metrics(y_true: list[int], y_pred: list[int]) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=list(range(5)), average="macro", zero_division=0)),
        "kappa": float(cohen_kappa_score(y_true, y_pred, labels=list(range(5)))),
        "per_stage_f1": {s: float(v) for s, v in zip(STAGES, f1_score(y_true, y_pred, labels=list(range(5)), average=None, zero_division=0))},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(range(5))).tolist(),
    }


def run_epoch(model, loader, opt=None, loss_fn=None, device="cpu"):
    train = opt is not None
    model.train(train)
    total_loss, true, pred = 0.0, [], []
    for raw, fr, fi, y in loader:
        raw, fr, fi, y = raw.to(device), fr.to(device), fi.to(device), y.to(device)
        with torch.set_grad_enabled(train):
            logits = model(raw, fr, fi)
            loss = loss_fn(logits, y)
            if train:
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
        total_loss += float(loss.item()) * len(y)
        true.extend(y.detach().cpu().numpy().tolist())
        pred.extend(logits.argmax(1).detach().cpu().numpy().tolist())
    return total_loss / max(1, len(true)), metrics(true, pred)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data/dodh"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-subjects", type=int, default=5)
    ap.add_argument("--max-epochs-per-subject", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("results.json"))
    args = ap.parse_args()
    seed_all(args.seed)

    if args.synthetic:
        records = synthetic_subjects(args.max_subjects, min(args.max_epochs_per_subject, 100), args.seed)
    else:
        paths = discover_h5_paths(args.data_dir)[:args.max_subjects]
        if not paths:
            raise SystemExit(f"No .h5 records found under {args.data_dir}. Use --synthetic for a pipeline smoke test.")
        records = []
        manifest = []
        for path in paths:
            try:
                rec = load_dreem_h5(path, args.max_epochs_per_subject)
                records.append(rec)
                manifest.append(rec[2])
                print(f"loaded {path.name}: {rec[2]['n_epochs']} scored epochs")
            except Exception as exc:
                print(f"skip {path}: {exc}")
        if not records:
            raise SystemExit("No compatible Dreem H5 records were loaded.")

    n = len(records)
    test_i = n - 1
    val_i = n - 2 if n >= 3 else 0
    train_i = [i for i in range(n) if i not in {test_i, val_i}]
    if not train_i:
        train_i = [i for i in range(n) if i != test_i]
        val_i = test_i
    train_x = sum((records[i][0] for i in train_i), [])
    train_y = sum((records[i][1] for i in train_i), [])
    val_x, val_y = records[val_i][0], records[val_i][1]
    test_x, test_y = records[test_i][0], records[test_i][1]
    print(f"subject split: train={train_i}, val={val_i}, test={test_i}; epochs={len(train_y)}/{len(val_y)}/{len(test_y)}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SleepPACNet().to(device)
    loss_fn = nn.CrossEntropyLoss(weight=make_weights(train_y).to(device))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, betas=(0.9, 0.999), weight_decay=1e-6)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs))
    train_loader = DataLoader(EpochDataset(train_x, train_y), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(EpochDataset(val_x, val_y), batch_size=args.batch_size)
    test_loader = DataLoader(EpochDataset(test_x, test_y), batch_size=args.batch_size)

    history = []
    for epoch in range(1, args.epochs + 1):
        train_loss, train_m = run_epoch(model, train_loader, opt, loss_fn, device)
        with torch.no_grad():
            val_loss, val_m = run_epoch(model, val_loader, None, loss_fn, device)
        scheduler.step()
        row = {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "train": train_m, "val": val_m}
        history.append(row)
        print(json.dumps(row, ensure_ascii=False))

    with torch.no_grad():
        test_loss, test_m = run_epoch(model, test_loader, None, loss_fn, device)
    result = {
        "protocol": "SleepPACNet-style reproduction",
        "device": device,
        "n_subjects": n,
        "test_loss": test_loss,
        "test": test_m,
        "history": history,
        "paper_reference": {"reported_accuracy": 0.757, "dataset": "DOD-H, 25 healthy participants"},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"test": test_m, "saved": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
