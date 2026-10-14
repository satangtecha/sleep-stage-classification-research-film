"""Bounded SST throughput benchmark using SC4001 only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

from .pilot import SC4001_SHARD
from .storage import DEFAULT_BULK_ROOT, require_e_drive
from .transform import convert_single_window, ssqueezepy_version


def benchmark(protocol_id: str, windows: int = 32, output_path: str | Path | None = None) -> dict[str, object]:
    if windows < 1:
        raise ValueError("windows must be positive")
    destination = Path(output_path) if output_path else DEFAULT_BULK_ROOT / "sst" / "benchmarks" / "SC4001_throughput.json"
    require_e_drive(destination)
    with np.load(SC4001_SHARD, allow_pickle=False) as shard:
        epochs = np.asarray(shard["x"][: windows + 1, :256], dtype=np.float32)
    if epochs.shape[0] < windows + 1:
        raise ValueError(f"SC4001 needs at least {windows + 1} epochs for warmup plus measurement")

    # Keep import/JIT warmup out of measured throughput.
    warmup_start = time.perf_counter()
    convert_single_window(epochs[0], protocol_id=protocol_id)
    warmup_seconds = time.perf_counter() - warmup_start

    digest = hashlib.sha256()
    measured_start = time.perf_counter()
    for signal in epochs[1:]:
        tensor = convert_single_window(signal, protocol_id=protocol_id)
        digest.update(tensor.tobytes(order="C"))
    elapsed = time.perf_counter() - measured_start
    rate = windows / elapsed
    result = {
        "status": "pass",
        "scope": "SC4001 bounded throughput only; no cache and no training",
        "protocol_id": protocol_id,
        "python": platform.python_version(),
        "ssqueezepy": ssqueezepy_version(),
        "warmup_seconds": warmup_seconds,
        "measured_windows": windows,
        "measured_seconds": elapsed,
        "windows_per_second": rate,
        "aggregate_tensor_sha256": digest.hexdigest(),
        "estimated_hours_paper_12_windows": 194655 * 12 / rate / 3600,
        "estimated_hours_author_15_windows": 194655 * 15 / rate / 3600,
        "estimate_warning": "single-process linear projection only; full-cohort I/O, parallelism, throttling, and failures are excluded",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=("PAPER_TEXT_V1", "AUTHOR_CODE_V1"), required=True)
    parser.add_argument("--windows", type=int, default=32)
    parser.add_argument("--output")
    arguments = parser.parse_args()
    print(json.dumps(benchmark(arguments.protocol, arguments.windows, arguments.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
