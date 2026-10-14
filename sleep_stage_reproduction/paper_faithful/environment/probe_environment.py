"""Record the narrow environment facts needed before a paper-faithful run."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def command_output(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=15,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return "unavailable: {}".format(error)


def memory_info() -> Dict[str, Any]:
    path = Path("/proc/meminfo")
    if not path.exists():
        return {}
    values: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal"}:
            values[key + "_kib"] = int(raw.strip().split()[0])
    return values


def os_release() -> Dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, raw = line.split("=", 1)
        values[key] = raw.strip().strip('"')
    return values


def text_file(path: str) -> str:
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8").strip() if file_path.exists() else "unavailable"


def conda_packages() -> list[Dict[str, Any]]:
    metadata = Path(sys.prefix) / "conda-meta"
    packages = []
    for path in sorted(metadata.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        packages.append(
            {
                "name": record.get("name"),
                "version": record.get("version"),
                "build": record.get("build"),
                "channel": record.get("channel"),
            }
        )
    return packages


def collect() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "python": sys.version,
        "python_executable": sys.executable,
        "kernel": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "os_release": os_release(),
        "os_identity_source": "/etc/os-release",
        "legacy_python37_platform_string": platform.platform(),
        "debian_compatibility_version": text_file("/etc/debian_version"),
        "legacy_platform_interpretation": "Python 3.7 platform.platform() derives its distro suffix from /etc/debian_version on this system. It is retained as compatibility metadata, not as the authoritative WSL distribution identity.",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "memory": memory_info(),
        "conda_packages": conda_packages(),
        "pip_freeze": command_output([sys.executable, "-m", "pip", "freeze"]).splitlines(),
        "nvidia_smi": command_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ]
        ),
    }
    try:
        import tensorflow as tf

        report.update(
            {
                "tensorflow": tf.__version__,
                "tensorflow_built_with_cuda": tf.test.is_built_with_cuda(),
                "tensorflow_gpu_devices": [device.name for device in tf.config.list_physical_devices("GPU")],
                "tensorflow_build_info": getattr(tf.sysconfig, "get_build_info", lambda: {})(),
            }
        )
    except Exception as error:  # pragma: no cover - records import/runtime failures
        report["tensorflow_error"] = "{}: {}".format(type(error).__name__, error)
    try:
        import tensorflow_addons as tfa

        report["tensorflow_addons"] = tfa.__version__
    except Exception as error:  # pragma: no cover - records import/runtime failures
        report["tensorflow_addons_error"] = "{}: {}".format(type(error).__name__, error)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = collect()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not any(key.endswith("_error") for key in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
