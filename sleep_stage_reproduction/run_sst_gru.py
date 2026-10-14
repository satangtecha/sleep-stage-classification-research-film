"""Compact reproduction of the 20-Jul-2026 SST + contrastive + GRU sleep paper.

Protocol implemented from the public article abstract/appendix:
1) Fpz-Cz, 30-second epochs, SST-like time-frequency representation;
2) 256-sample windows and CNN segment pretraining;
3) contrastive refinement of the encoder;
4) time-distributed CNN features over the full epoch, followed by a 2-layer GRU.

The paper's early-access HTML does not expose all split and architecture tables,
so this file is a faithful protocol-level reproduction, not a claim of exact
weight-level replication. It uses subject-wise splits when enough unique subjects
are available; very small pilots are explicitly marked as pilot-only.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from scipy.signal import stft
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler


STAGES = ["W", "N1", "N2", "N3", "REM"]

# Known complete PSG sizes for the local official Sleep-EDF subset. A partial
# download must never be treated as a valid recording by the loader.
SLEEP_EDF_PSG_BYTES = {
    "SC4001E0-PSG.edf": 48338048,
    "SC4002E0-PSG.edf": 51621248,
    "SC4011E0-PSG.edf": 51110528,
    "SC4012E0-PSG.edf": 51986048,
    "SC4021E0-PSG.edf": 51147008,
    "SC4022E0-PSG.edf": 50271488,
    "SC4031E0-PSG.edf": 51438848,
    "SC4032E0-PSG.edf": 49833728,
    "SC4041E0-PSG.edf": 46878848,
    "SC4042E0-PSG.edf": 50928128,
    "SC4051E0-PSG.edf": 49651328,
    "SC4052E0-PSG.edf": 51183488,
}


def is_complete_sleep_edf_psg(path: Path) -> bool:
    expected = SLEEP_EDF_PSG_BYTES.get(path.name)
    if expected is not None:
        return path.stat().st_size == expected
    # Conservative fallback for records outside the local manifest.
    return path.stat().st_size > 10_000_000


def seed_all(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def sst_like(x: np.ndarray, fs: float = 100.0, nperseg: int = 64) -> np.ndarray:
    """Small STFT synchrosqueezing implementation.

    For each STFT coefficient, estimate instantaneous frequency from phase
    advance and reassign its magnitude to the nearest frequency bin. This is
    the same SST principle shown in the paper's Appendix A, with no external
    synchrosqueezing package required.
    """
    f, t, z = stft(x.astype(np.float32), fs=fs, nperseg=nperseg,
                   noverlap=nperseg // 2, nfft=nperseg, boundary="zeros")
    mag = np.abs(z).astype(np.float32)
    if z.shape[1] > 1:
        phase_step = np.angle(z[:, 1:] * np.conj(z[:, :-1]))
        hop = (t[1] - t[0]) if len(t) > 1 else nperseg / fs
        inst = f[:, None] + phase_step / (2 * np.pi * max(hop, 1e-6))
        inst = np.concatenate([inst[:, :1], inst], axis=1)
    else:
        inst = np.broadcast_to(f[:, None], z.shape)
    out = np.zeros_like(mag)
    for k in range(z.shape[0]):
        idx = np.rint(inst[k] / (fs / nperseg)).astype(int)
        valid = (idx >= 0) & (idx < len(f))
        cols = np.arange(z.shape[1])[valid]
        np.add.at(out, (idx[valid], cols), mag[k, valid])
    keep = (f >= 0.5) & (f <= 30.0)
    out = np.log1p(out[keep])
    out = (out - out.mean()) / (out.std() + 1e-6)
    return out.astype(np.float32)


def windows(epoch: np.ndarray, size: int = 256, n: int = 12) -> np.ndarray:
    out = []
    for i in range(n):
        start = i * size
        w = epoch[start:start + size]
        if len(w) < size:
            w = np.pad(w, (0, size - len(w)))
        out.append(sst_like(w))
    return np.stack(out).astype(np.float32)


def metrics(y_true, y_pred):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=list(range(5)), average="macro", zero_division=0)),
        "kappa": float(cohen_kappa_score(y_true, y_pred, labels=list(range(5)))),
        "per_stage_f1": {s: float(v) for s, v in zip(STAGES, f1_score(y_true, y_pred, labels=list(range(5)), average=None, zero_division=0))},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(range(5))).tolist(),
    }


class SegmentSet(Dataset):
    def __init__(self, x, y):
        self.x = np.asarray(x, dtype=np.float32)
        self.y = np.asarray(y, dtype=np.int64)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return torch.from_numpy(self.x[i, None]), torch.tensor(self.y[i])


class SequenceSet(Dataset):
    def __init__(self, x, y):
        self.x = np.asarray(x, dtype=np.float32)
        self.y = np.asarray(y, dtype=np.int64)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return torch.from_numpy(self.x[i, :, None]), torch.tensor(self.y[i])


class Encoder(nn.Module):
    def __init__(self, emb=32):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, emb, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
        )

    def forward(self, x):
        return self.body(x).flatten(1)


class SegmentPretrainer(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = Encoder()
        self.head = nn.Linear(32, 5)

    def forward(self, x):
        z = self.encoder(x)
        return self.head(z), z


class SequenceClassifier(nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder
        self.gru = nn.GRU(32, 64, num_layers=2, batch_first=True, dropout=0.2)
        self.head = nn.Linear(64, 5)

    def forward(self, x):
        b, n, c, h, w = x.shape
        z = self.encoder(x.reshape(b * n, c, h, w)).reshape(b, n, -1)
        z, _ = self.gru(z)
        return self.head(z[:, -1])


def contrastive_loss(z1, z2, temperature=0.2):
    z1 = nn.functional.normalize(z1, dim=1)
    z2 = nn.functional.normalize(z2, dim=1)
    logits = z1 @ z2.T / temperature
    target = torch.arange(len(z1), device=z1.device)
    return (nn.functional.cross_entropy(logits, target) + nn.functional.cross_entropy(logits.T, target)) / 2


def augment(x):
    y = x.clone()
    y = y * (0.9 + 0.2 * torch.rand(len(y), 1, 1, 1, device=y.device))
    mask = torch.rand_like(y[:, :1]) < 0.05
    y = y.masked_fill(mask, 0)
    return y


def train_segments(model, loader, opt, device, weights=None):
    model.train(); total = 0.0; ys = []; ps = []
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        logits, _ = model(x)
        loss = nn.functional.cross_entropy(logits, y, weight=weights)
        opt.zero_grad(); loss.backward(); opt.step()
        total += loss.item() * len(y); ys.extend(y.cpu().tolist()); ps.extend(logits.argmax(1).cpu().tolist())
    return total / max(1, len(ys)), metrics(ys, ps)


@torch.no_grad()
def eval_segments(model, loader, device):
    model.eval(); ys = []; ps = []
    for x, y in loader:
        logits, _ = model(x.to(device)); ys.extend(y.tolist()); ps.extend(logits.argmax(1).cpu().tolist())
    return metrics(ys, ps)


def train_contrastive(encoder, loader, epochs, device):
    encoder.train(); opt = torch.optim.AdamW(encoder.parameters(), lr=1e-3)
    for epoch in range(1, epochs + 1):
        total = 0.0
        for x, _ in loader:
            x = x.to(device)
            loss = contrastive_loss(encoder(augment(x)), encoder(augment(x)))
            opt.zero_grad(); loss.backward(); opt.step(); total += loss.item() * len(x)
        print(json.dumps({"contrastive_epoch": epoch, "loss": total / max(1, len(loader.dataset))}))


def train_sequence(model, loader, opt, device, weights=None):
    model.train(); total = 0.0; ys = []; ps = []
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        logits = model(x); loss = nn.functional.cross_entropy(logits, y, weight=weights)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5); opt.step()
        total += loss.item() * len(y); ys.extend(y.cpu().tolist()); ps.extend(logits.argmax(1).cpu().tolist())
    return total / max(1, len(ys)), metrics(ys, ps)


@torch.no_grad()
def eval_sequence(model, loader, device):
    model.eval(); ys = []; ps = []
    for x, y in loader:
        logits = model(x.to(device)); ys.extend(y.tolist()); ps.extend(logits.argmax(1).cpu().tolist())
    return metrics(ys, ps)


def make_balanced_sampler(labels, seed: int, power: float = 1.0):
    """Oversample minority stages while keeping one epoch-sized loader.

    ``power=1`` is full inverse-frequency balancing; ``power=0.5`` is a
    softer inverse-square-root schedule that is less likely to overwhelm
    moderately represented classes such as N1.
    """
    labels = np.asarray(labels, dtype=np.int64)
    counts = np.bincount(labels, minlength=5).astype(np.float64)
    per_class = 1.0 / np.maximum(counts, 1.0) ** power
    sample_weights = torch.as_tensor(per_class[labels], dtype=torch.double)
    generator = torch.Generator().manual_seed(seed)
    return WeightedRandomSampler(
        sample_weights,
        num_samples=len(labels),
        replacement=True,
        generator=generator,
    )


def load_sleep_edf(hyp: Path, max_epochs=None):
    import mne
    candidates = [p for p in sorted(hyp.parent.glob(hyp.name[:6] + "*PSG.edf")) if is_complete_sleep_edf_psg(p)]
    if not candidates:
        raise FileNotFoundError(f"PSG companion not found for {hyp.name}")
    psg = candidates[0]
    raw = mne.io.read_raw_edf(psg, preload=True, verbose=False)
    ch = next((c for c in raw.ch_names if "fpz-cz" in c.lower()), None)
    if ch is None:
        raise ValueError(f"Fpz-Cz not found in {raw.ch_names}")
    ann = mne.read_annotations(hyp)
    sig = raw.get_data(picks=[ch])[0].astype(np.float32)
    fs = raw.info["sfreq"]
    epochs = []
    for onset, duration, desc in zip(ann.onset, ann.duration, ann.description):
        text = str(desc).lower().replace("sleep stage ", "").strip()
        label = {"w": 0, "1": 1, "2": 2, "3": 3, "4": 3, "r": 4}.get(text)
        if label is None:
            continue
        start = int(round(onset * fs)); length = int(round(30 * fs))
        seg = sig[start:start + length]
        if len(seg) < length:
            continue
        if fs != 100:
            from scipy.signal import resample_poly
            seg = resample_poly(seg, 100, int(round(fs)))
        seg = seg[:3000]
        if len(seg) < 3000:
            seg = np.pad(seg, (0, 3000 - len(seg)))
        seg = (seg - np.mean(seg)) / (np.std(seg) + 1e-6)
        epochs.append((windows(seg), label))
        if max_epochs and len(epochs) >= max_epochs:
            break
    return epochs


def synthetic(n_subjects=5, n_epochs=50, seed=7):
    rng = np.random.default_rng(seed); out = []
    t = np.arange(3000) / 100
    for s in range(n_subjects):
        rows = []
        for i in range(n_epochs):
            y = i % 5
            freqs = [18, 6, 13, 1.2, 20]
            x = rng.normal(0, 0.25, 3000) + np.sin(2 * np.pi * freqs[y] * t)
            x = (x - x.mean()) / (x.std() + 1e-6)
            rows.append((windows(x), y))
        out.append(rows)
    return out


def flatten_segments(records):
    x, y = [], []
    for rec in records:
        for w, label in rec:
            x.extend(w); y.extend([label] * len(w))
    return x, y


def sleep_edf_subject_id(name: str) -> str:
    """Return the Sleep-EDF subject identifier from a cassette filename.

    Sleep-EDF cassette names use the first five characters for the subject
    identifier and the following night code for the recording. For example,
    SC4001E0 and SC4002E0 belong to subject SC400, while SC4011E0 and SC4012E0
    belong to subject SC401.
    """
    stem = Path(name).name.split("-")[0]
    if stem.startswith("SC4") and len(stem) >= 5:
        return stem[:5]
    return stem


def make_subject_split(items, seed: int):
    """Merge nights by subject and create a deterministic subject-level split."""
    groups = {}
    for rec, subject_id, record_name in items:
        groups.setdefault(subject_id, []).append((rec, record_name))
    subject_ids = sorted(groups)
    if len(subject_ids) < 2:
        raise ValueError("At least two unique subjects are required for a held-out test subject")

    rng = random.Random(seed)
    rng.shuffle(subject_ids)
    test_subjects = [subject_ids[-1]]
    if len(subject_ids) >= 3:
        val_subjects = [subject_ids[-2]]
        train_subjects = subject_ids[:-2]
        strict = True
        split_note = "strict_subject_wise"
    else:
        # With only two subjects, a separate validation subject is impossible.
        # Keep the held-out test subject clean and reuse the training subject for
        # monitoring only; the output is explicitly marked pilot-only.
        val_subjects = subject_ids[:-1]
        train_subjects = subject_ids[:-1]
        strict = False
        split_note = "pilot_subject_holdout_no_independent_validation"

    def merge(subject_list):
        merged = []
        record_names = []
        for sid in subject_list:
            for rec, record_name in groups[sid]:
                merged.append(rec)
                record_names.append(record_name)
        return merged, record_names

    train_records, train_names = merge(train_subjects)
    val_records, val_names = merge(val_subjects)
    test_records, test_names = merge(test_subjects)
    metadata = {
        "split_type": split_note,
        "strict_subject_wise": strict,
        "all_subjects": subject_ids,
        "train_subjects": train_subjects,
        "validation_subjects": val_subjects,
        "test_subjects": test_subjects,
        "train_records": train_names,
        "validation_records": val_names,
        "test_records": test_names,
    }
    return train_records, val_records, test_records, metadata


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data/sleep-edf"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--max-subjects", type=int, default=5)
    ap.add_argument("--max-epochs-per-subject", type=int, default=200)
    ap.add_argument("--epochs-pretrain", type=int, default=2)
    ap.add_argument("--epochs-contrastive", type=int, default=1)
    ap.add_argument("--epochs-sequence", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument(
        "--imbalance-mode",
        choices=["none", "class_weighted", "balanced_sampler", "class_weighted_balanced_sampler"],
        default="none",
        help="strategy for imbalanced sleep stages; balanced_sampler oversamples minority stages",
    )
    ap.add_argument(
        "--class-weighted",
        action="store_true",
        help="backward-compatible alias for --imbalance-mode class_weighted",
    )
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--split-seed", type=int, default=None, help="keep the subject split fixed while changing model seed")
    ap.add_argument("--sampler-power", type=float, default=1.0, help="minority oversampling power: 1.0 inverse-frequency, 0.5 softer")
    ap.add_argument("--out", type=Path, default=Path("sst_gru_results.json"))
    args = ap.parse_args(); seed_all(args.seed)

    if not 0.0 <= args.sampler_power <= 1.0:
        raise SystemExit("--sampler-power must be between 0 and 1")

    if args.class_weighted:
        if args.imbalance_mode != "none":
            raise SystemExit("Use either --class-weighted or --imbalance-mode, not both")
        args.imbalance_mode = "class_weighted"

    if args.synthetic:
        synthetic_records = synthetic(args.max_subjects, min(50, args.max_epochs_per_subject), args.seed)
        items = [(rec, f"S{i:02d}", f"S{i:02d}") for i, rec in enumerate(synthetic_records)]
    else:
        files = sorted(args.data_dir.glob("*-Hypnogram.edf"))
        if not files:
            raise SystemExit(f"No *-Hypnogram.edf found under {args.data_dir}")
        loaded = []
        for hyp in files:
            try:
                rec = load_sleep_edf(hyp, args.max_epochs_per_subject)
                subject_id = sleep_edf_subject_id(hyp.name)
                print(f"loaded {hyp.name}: {len(rec)} epochs | subject={subject_id}")
                loaded.append((rec, subject_id, hyp.name))
            except Exception as exc:
                print(f"skip {hyp.name}: {exc}")
        if not loaded:
            raise SystemExit("No readable Sleep-EDF records found")
        unique_subjects = sorted({sid for _, sid, _ in loaded})
        if args.max_subjects and len(unique_subjects) > args.max_subjects:
            keep = set(unique_subjects[:args.max_subjects])
            loaded = [item for item in loaded if item[1] in keep]
        items = loaded

    split_seed = args.seed if args.split_seed is None else args.split_seed
    train_records, val_records, test_records, split = make_subject_split(items, split_seed)
    seg_x, seg_y = flatten_segments(train_records)
    val_seg_x, val_seg_y = flatten_segments(val_records)
    test_seg_x, test_seg_y = flatten_segments(test_records)
    print(json.dumps({"split": split, "epoch_counts": {"train": sum(len(rec) for rec in train_records), "validation": sum(len(rec) for rec in val_records), "test": sum(len(rec) for rec in test_records)}}, ensure_ascii=False))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    all_train_labels = np.asarray([label for rec in train_records for _, label in rec], dtype=np.int64)
    counts = np.bincount(all_train_labels, minlength=5).astype(np.float32)
    class_weighted = args.imbalance_mode in {"class_weighted", "class_weighted_balanced_sampler"}
    balanced_sampler = args.imbalance_mode in {"balanced_sampler", "class_weighted_balanced_sampler"}
    weights = torch.tensor(np.sqrt(counts.sum() / np.maximum(counts, 1.0)), dtype=torch.float32, device=device)
    weights = weights / weights.mean() if class_weighted else None
    pre = SegmentPretrainer().to(device)
    seg_sampler = make_balanced_sampler(seg_y, args.seed + 101, args.sampler_power) if balanced_sampler else None
    seg_loader = DataLoader(
        SegmentSet(seg_x, seg_y),
        batch_size=args.batch_size,
        shuffle=seg_sampler is None,
        sampler=seg_sampler,
    )
    val_loader = DataLoader(SegmentSet(val_seg_x, val_seg_y), batch_size=args.batch_size)
    pre_opt = torch.optim.AdamW(pre.parameters(), lr=1e-3)
    history = []
    for e in range(1, args.epochs_pretrain + 1):
        loss, train_m = train_segments(pre, seg_loader, pre_opt, device, weights)
        val_m = eval_segments(pre, val_loader, device)
        history.append({"pretrain_epoch": e, "loss": loss, "train": train_m, "val": val_m})
        print(json.dumps(history[-1], ensure_ascii=False))

    train_contrastive(pre.encoder, seg_loader, args.epochs_contrastive, device)

    seq_train_x = [w for rec in train_records for w, _ in rec]; seq_train_y = [y for rec in train_records for _, y in rec]
    seq_val_x = [w for rec in val_records for w, _ in rec]; seq_val_y = [y for rec in val_records for _, y in rec]
    seq_test_x = [w for rec in test_records for w, _ in rec]; seq_test_y = [y for rec in test_records for _, y in rec]
    model = SequenceClassifier(pre.encoder).to(device)
    seq_sampler = make_balanced_sampler(seq_train_y, args.seed + 202, args.sampler_power) if balanced_sampler else None
    seq_loader = DataLoader(
        SequenceSet(seq_train_x, seq_train_y),
        batch_size=args.batch_size,
        shuffle=seq_sampler is None,
        sampler=seq_sampler,
    )
    val_seq_loader = DataLoader(SequenceSet(seq_val_x, seq_val_y), batch_size=args.batch_size)
    test_seq_loader = DataLoader(SequenceSet(seq_test_x, seq_test_y), batch_size=args.batch_size)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    for e in range(1, args.epochs_sequence + 1):
        loss, train_m = train_sequence(model, seq_loader, opt, device, weights)
        val_m = eval_sequence(model, val_seq_loader, device)
        row = {"sequence_epoch": e, "loss": loss, "train": train_m, "val": val_m}
        history.append(row); print(json.dumps(row, ensure_ascii=False))
    test_m = eval_sequence(model, test_seq_loader, device)
    result = {
        "protocol": "SST + CNN pretraining + contrastive learning + 2-layer GRU",
        "class_weighted": class_weighted,
        "imbalance_mode": args.imbalance_mode,
        "seed": args.seed,
        "split_seed": split_seed,
        "sampler_power": args.sampler_power,
        "device": device,
        "n_subjects": len(split["all_subjects"]),
        "class_counts_train": counts.astype(int).tolist(),
        "split": split,
        "test": test_m,
        "history": history,
        "paper_reference": {"reported_accuracy": 0.83, "dataset": "Sleep-EDF, Fpz-Cz"},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"test": test_m, "saved": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
