"""Validate the recorded Phase-1 environment and repeated Stage-1 smoke results."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> List[str]:
    errors: List[str] = []
    probe = read_json(RESULTS / "wsl_tf24_probe.json")
    expected_pip = {
        line.strip()
        for line in (ROOT / "requirements-resolved.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    actual_pip = set(probe.get("pip_freeze", []))
    if actual_pip != expected_pip:
        errors.append("pip freeze differs from requirements-resolved.txt")
    if not str(probe.get("python", "")).startswith("3.7.12"):
        errors.append("Python must be 3.7.12")
    os_release = probe.get("os_release", {})
    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "24.04":
        errors.append("WSL distribution must be Ubuntu 24.04 according to /etc/os-release")
    if probe.get("os_identity_source") != "/etc/os-release":
        errors.append("OS identity must explicitly use /etc/os-release as the authoritative source")
    if "platform" in probe:
        errors.append("ambiguous legacy platform field must not be used for OS identity")
    if not probe.get("debian_compatibility_version") or "/etc/debian_version" not in probe.get("legacy_platform_interpretation", ""):
        errors.append("legacy Python 3.7 platform suffix must be explicitly documented as compatibility metadata")
    if probe.get("tensorflow") != "2.4.0" or probe.get("tensorflow_addons") != "0.12.0":
        errors.append("TensorFlow/TensorFlow Addons versions differ from the reference stack")
    if probe.get("tensorflow_built_with_cuda") is not True or probe.get("tensorflow_gpu_devices") != ["/physical_device:GPU:0"]:
        errors.append("TensorFlow CUDA build must expose exactly GPU:0")
    conda_versions = {item["name"]: item["version"] for item in probe.get("conda_packages", [])}
    if conda_versions.get("cudatoolkit") != "11.0.3" or conda_versions.get("cudnn") != "8.0.5.39":
        errors.append("CUDA/cuDNN realized versions differ from the environment lock")

    smokes = [
        read_json(RESULTS / "stage1_one_batch.json"),
        read_json(RESULTS / "stage1_one_batch_repeat.json"),
    ]
    for index, smoke in enumerate(smokes, start=1):
        prefix = "smoke {}".format(index)
        if smoke.get("status") != "pass":
            errors.append(prefix + " did not pass")
        if smoke.get("tensorflow") != "2.4.0" or smoke.get("gpu_devices") != ["/physical_device:GPU:0"]:
            errors.append(prefix + " did not use the locked TensorFlow GPU route")
        if smoke.get("batch_shape") != [2, 256, 256, 2] or smoke.get("output_shape") != [2, 5]:
            errors.append(prefix + " has an unexpected input/output shape")
        if smoke.get("all_gradients_finite") is not True or smoke.get("non_none_gradients") != smoke.get("trainable_variables"):
            errors.append(prefix + " has missing or non-finite gradients")
        if smoke.get("optimizer_step_applied") is not True:
            errors.append(prefix + " did not apply an optimizer step")
    if abs(float(smokes[0]["loss"]) - float(smokes[1]["loss"])) > 1e-12:
        errors.append("seed-repeat losses differ")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("INVALID")
        print("\n".join(errors))
        return 1
    print("VALID: locked TF2.4 GPU environment and two reproducible Stage-1 smoke batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
