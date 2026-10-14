"""Run at most one SC4001 SST window and write its result/evidence beneath E:."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .storage import DEFAULT_BULK_ROOT, estimate_cache, require_e_drive
from .transform import convert_single_window, ssqueezepy_version

SC4001_SHARD = DEFAULT_BULK_ROOT / "preprocessed" / "sleep-edfx" / "1.0.0" / "sleep-cassette" / "paper_faithful_v1" / "shards" / "SC4001.npz"


def storage_matrix(epochs: int = 194655) -> dict[str, float]:
    """Payload-only GiB estimates for both declared context protocols and model resolutions."""
    result: dict[str, float] = {}
    for protocol, windows in (("paper_12", 12), ("author_15", 15)):
        for resolution in (256, 64):
            for dtype in ("float32", "float16"):
                result[f"{protocol}_{resolution}_{dtype}_gib"] = round(
                    estimate_cache(epochs, windows, resolution, dtype).gib_total, 3
                )
    return result


def run_sc4001_pilot(protocol_id: str = "AUTHOR_CODE_V1", output_path: str | Path | None = None) -> dict[str, object]:
    destination = Path(output_path) if output_path else DEFAULT_BULK_ROOT / "sst" / "pilots" / "SC4001_single_window.json"
    require_e_drive(destination)
    result: dict[str, object] = {
        "record_id": "SC4001",
        "protocol_id": protocol_id,
        "shard": str(SC4001_SHARD),
        "scope": "one epoch, one 256-sample window, no cache and no training",
        "storage_payload_estimates_gib": storage_matrix(),
        "reserve_requirement_gib": 100,
        "ssqueezepy_version": ssqueezepy_version(),
    }
    if not SC4001_SHARD.is_file():
        result.update(status="blocked", blocker="SC4001 preprocessed shard is absent")
    elif result["ssqueezepy_version"] is None:
        result.update(
            status="dependency_blocked",
            blocker="ssqueezepy is not installed in the current environment; no package was installed by this gate",
            selected_pin="ssqueezepy==0.6.6",
            sensitivity_versions=["ssqueezepy==0.6.5", "ssqueezepy==0.6.6"],
        )
    else:
        with np.load(SC4001_SHARD, allow_pickle=False) as shard:
            input_window = np.asarray(shard["x"][0, :256], dtype=np.float32)
            tensor = convert_single_window(input_window, protocol_id=protocol_id)
        result.update(
            status="converted",
            input_sha256=hashlib.sha256(input_window.tobytes(order="C")).hexdigest(),
            tensor_shape=list(tensor.shape),
            tensor_dtype=str(tensor.dtype),
            tensor_sha256=hashlib.sha256(tensor.tobytes(order="C")).hexdigest(),
            tensor_min=float(tensor.min()),
            tensor_max=float(tensor.max()),
            tensor_mean=float(tensor.mean()),
            tensor_std=float(tensor.std()),
            tensor_all_finite=bool(np.isfinite(tensor).all()),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_sc4001_pilot(), indent=2))
