"""Raw EEG CNN baseline for the Sleep-EDF sleep-stage project.

This baseline intentionally avoids SST, contrastive learning and GRU. It uses
the same label mapping and subject-level split helper as run_sst_gru.py so the
comparison is meaningful.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from scipy.signal import resample_poly
from torch import nn
from torch.utils.data import DataLoader, Dataset

from run_sst_gru import is_complete_sleep_edf_psg, make_subject_split, metrics, seed_all, sleep_edf_subject_id


class EpochSet(Dataset):
    def __init__(self, records):
        self.x = np.asarray([x for rec in records for x, _ in rec], dtype=np.float32)
        self.y = np.asarray([y for rec in records for _, y in rec], dtype=np.int64)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return torch.from_numpy(self.x[i][None]), torch.tensor(self.y[i])


class RawCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(4),
            nn.Conv1d(16, 32, kernel_size=9, stride=2, padding=4),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(4),
            nn.Conv1d(32, 64, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(64), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(64, 5)

    def forward(self, x):
        return self.head(self.body(x).flatten(1))


def load_raw_sleep_edf(hyp: Path, max_epochs=None):
    import mne

    candidates = [p for p in sorted(hyp.parent.glob(hyp.name[:6] + "*PSG.edf")) if is_complete_sleep_edf_psg(p)]
    if not candidates:
        raise FileNotFoundError(f"PSG companion not found for {hyp.name}")
    raw = mne.io.read_raw_edf(candidates[0], preload=True, verbose=False)
    channel = next((c for c in raw.ch_names if "fpz-cz" in c.lower()), None)
    if channel is None:
        raise ValueError(f"Fpz-Cz not found in {raw.ch_names}")
    ann = mne.read_annotations(hyp)
    sig = raw.get_data(picks=[channel])[0].astype(np.float32)
    fs = raw.info["sfreq"]
    out = []
    for onset, desc in zip(ann.onset, ann.description):
        text = str(desc).lower().replace("sleep stage ", "").strip()
        label = {"w": 0, "1": 1, "2": 2, "3": 3, "4": 3, "r": 4}.get(text)
        if label is None:
            continue
        start = int(round(onset * fs))
        length = int(round(30 * fs))
        seg = sig[start:start + length]
        if len(seg) < length:
            continue
        if fs != 100:
            seg = resample_poly(seg, 100, int(round(fs)))
        seg = seg[:3000]
        if len(seg) < 3000:
            seg = np.pad(seg, (0, 3000 - len(seg)))
        seg = (seg - seg.mean()) / (seg.std() + 1e-6)
        out.append((seg.astype(np.float32), label))
        if max_epochs and len(out) >= max_epochs:
            break
    return out


def run_epoch(model, loader, device, optimizer=None, weights=None):
    training = optimizer is not None
    model.train(training)
    ys, ps = [], []
    total = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.set_grad_enabled(training):
            logits = model(x)
            loss = nn.functional.cross_entropy(logits, y, weight=weights)
            if training:
                optimizer.zero_grad(); loss.backward(); optimizer.step()
        total += loss.item() * len(y)
        ys.extend(y.cpu().tolist()); ps.extend(logits.argmax(1).cpu().tolist())
    return total / max(1, len(ys)), metrics(ys, ps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data/sleep-edf"))
    ap.add_argument("--max-subjects", type=int, default=5)
    ap.add_argument("--max-epochs-per-subject", type=int, default=160)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--class-weighted", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("raw_cnn_baseline_results.json"))
    args = ap.parse_args()
    seed_all(args.seed)

    files = sorted(args.data_dir.glob("*-Hypnogram.edf"))
    loaded = []
    for hyp in files:
        try:
            rec = load_raw_sleep_edf(hyp, args.max_epochs_per_subject)
            sid = sleep_edf_subject_id(hyp.name)
            print(f"loaded {hyp.name}: {len(rec)} epochs | subject={sid}")
            loaded.append((rec, sid, hyp.name))
        except Exception as exc:
            print(f"skip {hyp.name}: {exc}")
    if not loaded:
        raise SystemExit("No readable Sleep-EDF records found")
    unique = sorted({sid for _, sid, _ in loaded})
    if args.max_subjects and len(unique) > args.max_subjects:
        keep = set(unique[:args.max_subjects])
        loaded = [item for item in loaded if item[1] in keep]

    train_records, val_records, test_records, split = make_subject_split(loaded, args.seed)
    train_set, val_set, test_set = EpochSet(train_records), EpochSet(val_records), EpochSet(test_records)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    counts = np.bincount(train_set.y, minlength=5).astype(np.float32)
    weights = torch.tensor(np.sqrt(counts.sum() / np.maximum(counts, 1.0)), dtype=torch.float32, device=device)
    weights = weights / weights.mean() if args.class_weighted else None
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=args.batch_size)
    test_loader = DataLoader(test_set, batch_size=args.batch_size)
    model = RawCNN().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    history = []
    for epoch in range(1, args.epochs + 1):
        loss, train_m = run_epoch(model, train_loader, device, opt, weights)
        _, val_m = run_epoch(model, val_loader, device, None, weights)
        row = {"epoch": epoch, "loss": loss, "train": train_m, "validation": val_m}
        history.append(row); print(json.dumps(row, ensure_ascii=False))
    _, test_m = run_epoch(model, test_loader, device, None, weights)
    result = {
        "protocol": "raw EEG + 1D CNN baseline",
        "class_weighted": args.class_weighted,
        "device": device,
        "n_subjects": len(split["all_subjects"]),
        "split": split,
        "test": test_m,
        "history": history,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"test": test_m, "saved": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
