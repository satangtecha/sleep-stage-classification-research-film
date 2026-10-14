"""Read-only helpers for the VS Code/Jupyter project walkthrough.

The functions in this module intentionally never launch training and never write to
the canonical run directories.  They only inspect the repository, the bulk artifact
root, and already-published JSON/NumPy/EDF artifacts.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np


LABELS = ("W", "N1", "N2", "N3", "REM")
STATUS_COLORS = {
    "complete": "#2a9d8f",
    "completed": "#2a9d8f",
    "pass": "#2a9d8f",
    "prepared": "#e9c46a",
    "blocked": "#e76f51",
    "failed": "#d62828",
    "not_started": "#adb5bd",
    "missing": "#adb5bd",
}


def locate_project_root(start: Path | None = None) -> Path:
    """Locate the repository root from a notebook or script working directory."""

    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "paper_faithful").is_dir() and (candidate / "README_TH.md").is_file():
            return candidate
    raise FileNotFoundError("ไม่พบโฟลเดอร์รากของ sleep_stage_reproduction")


PROJECT_ROOT = locate_project_root(Path(__file__).resolve().parent)
BULK_ROOT = Path(os.environ.get("SLEEP_STAGE_BULK_ROOT", r"E:\blp\sleep_stage_reproduction"))
PREPROCESSING_RESULT = (
    BULK_ROOT
    / "preprocessed"
    / "sleep-edfx"
    / "1.0.0"
    / "sleep-cassette"
    / "paper_faithful_v3_full_20260820"
    / "manifests"
    / "preprocessing_result.json"
)
CACHE_ROOT = BULK_ROOT / "sst_cache" / "paper_faithful_v3_full_20260820"
RUNS_ROOT = BULK_ROOT / "runs"
SUBJECT_GATE = BULK_ROOT / "runtime" / "subject-generalization-v1-pilot-20260906-v4-canonical-gate.json"


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pretty_bytes(value: int | float) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:,.2f} {unit}"
        size /= 1024
    return f"{size:,.2f} TiB"


def evidence_paths() -> dict[str, Path]:
    return {
        "project": PROJECT_ROOT,
        "local_edf": PROJECT_ROOT / "data" / "sleep-edf",
        "full_preprocessing_manifest": PREPROCESSING_RESULT,
        "full_sst_cache": CACHE_ROOT,
        "run_results": RUNS_ROOT,
        "subject_generalization_gate": SUBJECT_GATE,
    }


def path_health() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, path in evidence_paths().items():
        rows.append({"artifact": label, "exists": path.exists(), "path": str(path)})
    return rows


def full_cohort_summary() -> dict[str, Any]:
    result = load_json(PREPROCESSING_RESULT)
    aggregate = result["aggregate"]
    return {
        "status": result["status"],
        "recordings": int(aggregate["recordings"]),
        "subjects": int(aggregate["subjects"]),
        "epochs": int(aggregate["epochs"]),
        "class_counts": {label: int(aggregate["class_counts"][label]) for label in LABELS},
        "parity_matches_expected": bool(result["parity"]["matches_expected"]),
    }


def local_edf_inventory() -> dict[str, Any]:
    data_dir = PROJECT_ROOT / "data" / "sleep-edf"
    psg = sorted(data_dir.glob("*-PSG.edf"))
    hypnograms = sorted(data_dir.glob("*-Hypnogram.edf"))
    subjects = sorted({path.name[:5] for path in psg})
    return {
        "psg_files": len(psg),
        "hypnogram_files": len(hypnograms),
        "subjects": subjects,
        "subject_count": len(subjects),
    }


def _test_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = load_json(path)
    test = payload.get("metrics", {}).get("test", {})
    classification = test.get("classification")
    if not classification:
        silhouette = test.get("silhouette", {}).get("silhouette")
        return {"silhouette": silhouette} if silhouette is not None else None
    return {
        "accuracy": float(classification["accuracy"]),
        "macro_f1": float(classification["macro"]["f1"]),
        "weighted_f1": float(classification["weighted"]["f1"]),
        "confusion_matrix": np.asarray(classification["confusion_matrix"], dtype=int),
        "per_class_f1": {
            label: float(classification["per_class"][label]["f1"]) for label in LABELS
        },
        "sample_count": int(test["scope"]["evaluated_sample_count"]),
    }


def discover_runs(pattern: str = "paper-text-v1-*") -> list[dict[str, Any]]:
    """Summarize existing runs without importing a trainer or loading checkpoints."""

    rows: list[dict[str, Any]] = []
    if not RUNS_ROOT.exists():
        return rows
    for run_dir in sorted(RUNS_ROOT.glob(pattern), key=lambda p: p.name):
        execution_path = run_dir / "execution.json"
        if not execution_path.exists():
            continue
        execution = load_json(execution_path)
        config = execution.get("config", {})
        stage3 = _test_metrics(run_dir / "stage3.metrics.json")
        stage2 = _test_metrics(run_dir / "stage2.metrics.json")
        match = re.search(r"-(r\d+)-", run_dir.name)
        rows.append(
            {
                "run_id": run_dir.name,
                "revision": match.group(1) if match else "unknown",
                "status": execution.get("status", "unknown"),
                "split_seed": config.get("split_seed"),
                "model_seed": config.get("model_seed", config.get("seed")),
                "cap": config.get("per_split_epoch_cap"),
                "protocol_id": config.get("protocol_id"),
                "stage3_accuracy": None if stage3 is None else stage3.get("accuracy"),
                "stage3_macro_f1": None if stage3 is None else stage3.get("macro_f1"),
                "stage2_silhouette": None if stage2 is None else stage2.get("silhouette"),
                "path": run_dir,
            }
        )
    return rows


def r19_runs() -> list[dict[str, Any]]:
    return [row for row in discover_runs() if row["revision"] == "r19"]


def stage_metrics(run_dir: Path | str, stage: str = "stage3") -> dict[str, Any]:
    metrics = _test_metrics(Path(run_dir) / f"{stage}.metrics.json")
    if metrics is None:
        raise FileNotFoundError(f"ไม่พบ metrics ของ {stage}: {run_dir}")
    return metrics


def subject_gate_summary() -> dict[str, Any]:
    gate = load_json(SUBJECT_GATE)
    return {
        "status": gate["status"],
        "fresh_launch_authorized": bool(gate["fresh_launch_authorized"]),
        "reason": gate["reason"],
        "available_memory_mb": float(gate["physical_memory_available_mb"]),
        "required_memory_mb": float(gate["minimum_physical_memory_available_mb"]),
        "training_started": bool(gate["training_started"]),
        "markers_created": bool(gate["production_markers_created"]),
    }


def load_sst_example(route: str = "PAPER_STAGE3_V1") -> tuple[np.ndarray, dict[str, Any], Path]:
    """Memory-map one published SST chunk; only one epoch is copied into RAM."""

    sidecars = sorted(CACHE_ROOT.glob(f"*.{route}.*.json"))
    if not sidecars:
        raise FileNotFoundError(f"ไม่พบ SST route {route} ที่ {CACHE_ROOT}")
    sidecar = sidecars[0]
    meta = load_json(sidecar)
    tensor_path = sidecar.with_suffix(".npy")
    mapped = np.load(tensor_path, mmap_mode="r")
    example = np.asarray(mapped[0], dtype=np.float32)
    return example, meta, tensor_path


def paper_protocol() -> dict[str, Any]:
    return load_json(PROJECT_ROOT / "paper_faithful" / "manifests" / "protocols" / "PAPER_TEXT_V1.json")


def r19_stage_specs() -> list[dict[str, Any]]:
    rows = r19_runs()
    if not rows:
        return []
    run_dir = rows[0]["path"]
    specs: list[dict[str, Any]] = []
    for stage in ("stage1", "stage2", "stage3"):
        payload = load_json(run_dir / f"{stage}.metrics.json")
        spec = dict(payload["provenance"]["stage_spec"])
        specs.append(spec)
    return specs


def print_records(rows: Iterable[dict[str, Any]], columns: Iterable[str] | None = None) -> None:
    rows = list(rows)
    if not rows:
        print("(ไม่มีข้อมูล)")
        return
    names = list(columns or rows[0].keys())
    widths = {name: max(len(name), *(len(str(row.get(name, ""))) for row in rows)) for name in names}
    header = " | ".join(name.ljust(widths[name]) for name in names)
    print(header)
    print("-+-".join("-" * widths[name] for name in names))
    for row in rows:
        print(" | ".join(str(row.get(name, "")).ljust(widths[name]) for name in names))


def plot_confusion_matrix(matrix: np.ndarray, title: str, ax: plt.Axes | None = None) -> plt.Axes:
    ax = ax or plt.subplots(figsize=(5, 4))[1]
    image = ax.imshow(matrix, cmap="Blues")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            ax.text(j, i, str(value), ha="center", va="center", color="white" if value > matrix.max() / 2 else "#222")
    ax.set(xticks=range(5), yticks=range(5), xticklabels=LABELS, yticklabels=LABELS)
    ax.set_xlabel("ค่าที่โมเดลทำนาย")
    ax.set_ylabel("ค่าจริง")
    ax.set_title(title)
    ax.figure.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    return ax


def status_badge(status: str) -> str:
    symbols = {"completed": "✅", "complete": "✅", "pass": "✅", "blocked": "⛔", "failed": "❌"}
    return f"{symbols.get(status, '•')} {status}"

