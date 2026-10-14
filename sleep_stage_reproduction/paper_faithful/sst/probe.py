"""Emit a small, auditable ssqueezepy availability probe without installing packages."""

from __future__ import annotations

import json
from pathlib import Path

from .storage import DEFAULT_BULK_ROOT, require_e_drive
from .transform import ssqueezepy_version


def probe(output_path: str | Path | None = None) -> dict[str, object]:
    destination = Path(output_path) if output_path else DEFAULT_BULK_ROOT / "sst" / "probes" / "ssqueezepy_probe.json"
    require_e_drive(destination)
    version = ssqueezepy_version()
    result = {
        "dependency": "ssqueezepy",
        "installed": version is not None,
        "installed_version": version,
        "selected_pin": "ssqueezepy==0.6.6",
        "sensitivity_versions": ["ssqueezepy==0.6.5", "ssqueezepy==0.6.6"],
        "candidate_status": "one_window_cross_version_parity_not_author_exact",
        "author_source": "paper_faithful/vendor/Sleep-Stage-Classification-v1.0/requirements.txt (unversioned ssqueezepy)",
        "next_action": "use the pinned E-drive environment" if version == "0.6.6" else "run the one-window numeric compatibility fixture",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
