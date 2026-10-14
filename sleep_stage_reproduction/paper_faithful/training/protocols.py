"""Read-only access to the source-locked protocol manifests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_PROTOCOLS = _ROOT / "manifests" / "protocols"
SUPPORTED_PROTOCOLS = frozenset(("PAPER_TEXT_V1", "AUTHOR_CODE_V1", "SUBJECT_GENERALIZATION_V1"))


def load_protocol(protocol_id: str) -> dict[str, Any]:
    if protocol_id not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"unsupported protocol_id: {protocol_id}")
    return json.loads((_PROTOCOLS / f"{protocol_id}.json").read_text(encoding="utf-8"))


def sequence_windows(protocol_id: str) -> int:
    protocol = load_protocol(protocol_id)
    if protocol_id == "PAPER_TEXT_V1":
        return int(protocol["model"]["stage3_windows"])
    if protocol_id == "AUTHOR_CODE_V1":
        return int(protocol["downstream"]["windows"])
    raise ValueError("SUBJECT_GENERALIZATION_V1 has no locked window count; select PAPER_TEXT_V1 or AUTHOR_CODE_V1 representation")
