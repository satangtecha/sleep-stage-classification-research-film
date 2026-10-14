"""Bounded workstation diagnostic; never a research run or accepted lineage.

Reads four manifest-listed chunks only. GPU modes use fresh random models and
repeat that small sample. No validation/test metrics or reusable checkpoints.
"""
from __future__ import annotations

import argparse
import base64
import gc
import hashlib
import json
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from .cache_loader import (CanonicalCache, CachedEpoch, _TensorSnapshotSpec,
    _all_finite_in_bounded_rows, _array_from_verified_snapshot, _host_path,
    _read_verified_snapshot, _tensor_byte_budget)
from .splits import EpochMember
from .run_manifest import sha256_file
from paper_faithful.sst.cache_manifest import ROUTES, canonical_hash, route_config

MANIFEST_SHA = "a4512970c6023cd1dc727cad40c2352126fea46356b78bb6782055f9d0ce7ed2"
DEFAULT_MANIFEST = "/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json"
DESIGN = "BOUNDED_RESOURCE_DIAGNOSTIC_V2_CGROUP"


def cgroup_observation():
    """Read the actual process scope, not an unverified environment flag."""
    entries = Path("/proc/self/cgroup").read_text().splitlines()
    entry = next(line[3:] for line in entries if line.startswith("0::"))
    root = Path("/sys/fs/cgroup").resolve()
    scope = (root / entry.lstrip("/")).resolve()
    scope.relative_to(root)
    result = {"path": str(scope)}
    for name in ("memory.max", "memory.high", "memory.swap.max", "memory.current", "memory.swap.current"):
        value = (scope / name).read_text().strip()
        result[name] = value if value == "max" else int(value)
    result["memory.events"] = (scope / "memory.events").read_text().strip()
    return result


def check_compact_scope(scope):
    for name in ("memory.max", "memory.swap.max"):
        value = scope.get(name)
        if type(value) is not int or not 0 < value <= 2 * 1024 ** 3:
            raise ValueError("compact diagnostic requires cgroup RAM and swap caps <= 2 GiB")
    return scope


def check_host_budget(checks, mode, initial=True, compact=False):
    """Diagnostic-only budget, not the full-cache production admission rule."""
    required = (1536 if mode == "io" else 3072) if initial else 1024
    if compact:
        required = 2816 if initial else 768
    if checks.get("power_online") is not True or checks.get("critical") is not False:
        raise ValueError("diagnostic requires noncritical AC power")
    for key, floor in (("free_ram_mib", required), ("commit_headroom_mib", 4096), ("e_free_gib", 2)):
        value = checks.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value) or value < floor:
            raise ValueError("diagnostic host budget failed: " + key)
    return checks


def host_observation(mode, initial=True, compact=False):
    script = r'''
$ErrorActionPreference='Stop'
$taskOs=Get-CimInstance Win32_OperatingSystem
Add-Type -AssemblyName System.Windows.Forms
$taskPower=[System.Windows.Forms.SystemInformation]::PowerStatus
[ordered]@{power_online=($taskPower.PowerLineStatus.ToString() -eq 'Online'); critical=(($taskPower.BatteryChargeStatus -band [System.Windows.Forms.BatteryChargeStatus]::Critical) -ne 0); free_ram_mib=[double]$taskOs.FreePhysicalMemory/1024; commit_headroom_mib=[double]$taskOs.FreeVirtualMemory/1024; e_free_gib=[double](Get-PSDrive E).Free/1GB}|ConvertTo-Json -Compress
'''
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    if result.returncode:
        raise ValueError("diagnostic host observation failed")
    return check_host_budget(json.loads(result.stdout.lstrip("\ufeff")), mode, initial, compact)


def set_failure(record, error):
    record["status"] = "failed"
    record["error"] = {"type": type(error).__name__, "message": str(error)}


def handle_stop(record, signum):
    # The terminal decision is made while still inside the workload try/except.
    # Cover the handoff into finalization as well as publication itself.
    if record.get("status") in ("pass", "failed"):
        return
    raise TimeoutError("diagnostic interrupted or exceeded 600 seconds (signal %s)" % signum)


def finalize_record(output, record, cache):
    # Work has finished: ignore catchable interruption during short publication.
    # SIGKILL or power loss cannot be intercepted; started.json then remains evidence.
    signals = {signal.SIGINT, signal.SIGTERM}
    if hasattr(signal, "SIGALRM"):
        signals.add(signal.SIGALRM)
    previous_handlers = {sig: signal.getsignal(sig) for sig in signals}
    try:
        # Process-wide dispositions also cover native library worker threads;
        # masking only the Python thread does not block process-directed signals.
        for sig in signals:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if cache is not None:
                cache.close()
            gc.collect()
        except BaseException as error:
            set_failure(record, error)
        try:
            record["after"] = memory_snapshot()
        except BaseException as error:
            set_failure(record, error)
            record["after"] = {"unavailable": True}
        record["finalization_policy"] = "workload finished; catchable stop signals during durable publication are consumed, not raised after a committed result"
        with (output / "result.json").open("x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        print(json.dumps(record, sort_keys=True, allow_nan=False), flush=True)
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


def read_json_bytes(path, budget):
    with Path(path).open("rb") as handle:
        raw = handle.read(budget + 1)
    if len(raw) > budget:
        raise ValueError("JSON exceeds diagnostic budget")
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def memory_snapshot():
    import resource
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            memory[key + "_mib"] = int(value.split()[0]) / 1024.0
    status = Path("/proc/self/status").read_text().splitlines()
    for line in status:
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value = line.split(":", 1)
            memory[key + "_mib"] = int(value.split()[0]) / 1024.0
    memory["max_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    return memory


def gpu_snapshot():
    result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15)
    if result.returncode or len(result.stdout.strip().splitlines()) != 1:
        raise ValueError("GPU observation unavailable or ambiguous")
    fields = [item.strip() for item in result.stdout.strip().split(",")]
    if len(fields) != 5:
        raise ValueError("malformed GPU observation")
    return {"name": fields[0], "used_mib": int(fields[1]), "free_mib": int(fields[2]),
            "utilization_percent": int(fields[3]), "temperature_c": int(fields[4])}


def selected_cache(manifest_path, expected_sha, route):
    """Validate selected payload bytes, source hashes and declared metadata only."""
    path = _host_path(str(manifest_path))
    manifest, digest = read_json_bytes(path, 32 * 1024 * 1024)
    if digest != expected_sha:
        raise ValueError("diagnostic manifest anchor mismatch")
    records = {item["record_id"]: item for item in manifest["record_bindings"]}
    candidates = sorted((chunk for chunk in manifest["chunks"] if ("." + route + ".") in Path(chunk["tensor"]).name), key=lambda chunk: chunk["tensor"])[:4]
    if len(candidates) != 4 or type(manifest["chunk_epochs"]) is not int or manifest["chunk_epochs"] < 1:
        raise ValueError("four writer chunks required")
    entries, specs, evidence, sources = {}, {}, [], {}
    selected_payload_bytes = 0
    for chunk in candidates:
        tensor = _host_path(chunk["tensor"], path.parent)
        side_path = _host_path(chunk["sidecar"], path.parent)
        side, side_sha = read_json_bytes(side_path, 1024 * 1024)
        record = records[side["record_id"]]
        start, end = side["local_epoch_start"], side["local_epoch_end_exclusive"]
        shape = (end - start, ROUTES[route].windows, 64, 64, 2)
        selected_payload_bytes += int(np.prod(shape)) * 4
        if selected_payload_bytes > 64 * 1024 * 1024:
            raise ValueError("selected diagnostic payload exceeds 64 MiB")
        provenance = {key: manifest[key] for key in ("phase2_manifest_sha256", "phase2_manifest_path", "completion_marker_path", "completion_marker_sha256")}
        provenance["record_binding"] = record
        expected_config = route_config(ROUTES[route], side["config"]["transform_identity"])
        if (type(start) is not int or type(end) is not int or start < 0 or start % manifest["chunk_epochs"]
            or end != min(start + manifest["chunk_epochs"], record["epochs"]) or end <= start
            or side["local_epoch_indices"] != list(range(start, end)) or side["subject_id"] != record["subject_id"]
            or side["tensor_shape"] != list(shape) or side["tensor_dtype"] != "float32" or side["tensor_file"] != tensor.name
            or side["config"] != expected_config or side["config_sha256"] != canonical_hash(expected_config)
            or side["cohort_provenance"] != provenance or side["source_sha256"] != record["shard_sha256"]
            or side["source_path"] != record["shard_path"] or len(side["labels"]) != end-start
            or any(type(label) is not int or not 0 <= label <= 4 for label in side["labels"])):
            raise ValueError("selected chunk metadata differs")
        source = _host_path(record["shard_path"])
        if source not in sources:
            sources[source] = sha256_file(source)
        if sources[source] != record["shard_sha256"]:
            raise ValueError("selected source hash differs")
        provisional = _TensorSnapshotSpec(side["tensor_sha256"], None, _tensor_byte_budget(shape), shape, np.dtype("float32"))
        raw = _read_verified_snapshot(tensor, provisional)
        spec = _TensorSnapshotSpec(provisional.digest, len(raw), provisional.byte_budget, shape, provisional.dtype)
        array = _array_from_verified_snapshot(raw, spec)
        if not _all_finite_in_bounded_rows(array):
            raise ValueError("non-finite selected tensor")
        specs[tensor] = spec
        for offset, epoch in enumerate(range(start, end)):
            member = EpochMember(record["subject_id"], record["record_id"], epoch)
            if (member, route) in entries:
                raise ValueError("selected chunks overlap")
            entries[(member, route)] = CachedEpoch(member, route, tensor, offset, side["labels"][offset])
        evidence.append({"tensor": str(tensor), "tensor_sha256": spec.digest, "bytes": spec.byte_length,
            "sidecar": str(side_path), "sidecar_sha256": side_sha, "source_sha256": sources[source]})
        del raw, array
    return CanonicalCache(path, entries, digest, manifest["phase2_manifest_path"], manifest["phase2_manifest_sha256"], specs), evidence


def io_measure(cache, evidence):
    """Alternating warm-cache comparison; never flushes user/OS caches."""
    results = {"windows_mount": [], "linux_ext4": []}
    total_bytes = sum(row["bytes"] for row in evidence)
    with tempfile.TemporaryDirectory(prefix="sleep-resource-io-") as directory:
        pairs = []
        for row in evidence:
            source = Path(row["tensor"])
            target = Path(directory) / source.name
            shutil.copyfile(str(source), str(target))
            if sha256_file(target) != row["tensor_sha256"]:
                raise ValueError("diagnostic copy hash differs")
            pairs.append((source, target, cache._tensor_specs[source]))
        for repeat in range(4):
            order = ("windows_mount", "linux_ext4") if repeat % 2 == 0 else ("linux_ext4", "windows_mount")
            for location in order:
                started = time.perf_counter()
                for original, copied, spec in pairs:
                    array = _array_from_verified_snapshot(_read_verified_snapshot(original if location == "windows_mount" else copied, spec), spec)
                    if not _all_finite_in_bounded_rows(array):
                        raise ValueError("non-finite I/O payload")
                    del array
                results[location].append(time.perf_counter() - started)
    return {"warm_cache_only": True, "cold_cache_measured": False, "bytes_per_pass": total_bytes,
        "seconds": results, "median_seconds": {key: statistics.median(value) for key, value in results.items()},
        "limit": "Includes hashing, decode and finite scan; four repeated chunks, not full-cohort random I/O."}


def gpu_measure(cache, route, mode, steps, gpu_limit_mib, compact=False):
    import tensorflow as tf
    from .models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru, supervised_contrastive_loss
    from .trainer import CacheSequence, _enable_gradient_accumulation, _gradient_accumulation_metrics, validate_stage3_parameter_gate
    if tf.__version__ != "2.4.0":
        raise ValueError("diagnostic requires locked TF2.4.0")
    gpus = tf.config.list_physical_devices("GPU")
    if len(gpus) != 1:
        raise ValueError("one real GPU required")
    tf.config.experimental.set_virtual_device_configuration(gpus[0], [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=gpu_limit_mib)])
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    random.seed(42); np.random.seed(42); tf.random.set_seed(42)
    with tf.device("/GPU:0"):
        probe = tf.reduce_sum(tf.ones((16, 16)))
    if "GPU:0" not in probe.device:
        raise ValueError("GPU probe was placed on CPU")
    model1 = build_stage1_cnn("PAPER_TEXT_V1", input_shape=(64, 64, 2))
    if mode == "stage1":
        import tensorflow_addons as tfa
        model = model1
        optimizer = tfa.optimizers.AdamW(weight_decay=0.0, learning_rate=0.05)
    else:
        model2 = build_stage2_supervised_contrastive("PAPER_TEXT_V1", model1, input_shape=(64, 64, 2))
        model = model2 if mode == "stage2" else build_stage3_cnn_gru("PAPER_TEXT_V1", model2, input_shape=(64, 64, 2))
        optimizer = tf.keras.optimizers.SGD(0.1)
    if "GPU:0" not in model.weights[0].device:
        raise ValueError("model variables were not placed on GPU")
    loss = (lambda y, x: supervised_contrastive_loss(y, x, 0.05)) if mode == "stage2" else "sparse_categorical_crossentropy"
    model.compile(optimizer=optimizer, loss=loss)
    microsteps = 128 if mode == "stage3" else 1
    if mode == "stage3":
        validate_stage3_parameter_gate(model)
        _enable_gradient_accumulation(tf, model, 128, gradient_clip_norm=1.0)
    sequence = CacheSequence(cache, cache.members, route, 1 if mode == "stage3" else 128,
                             sequence=mode == "stage3", nominal_batch=128)
    if len(sequence) < microsteps:
        raise ValueError("insufficient selected samples for a nominal batch")
    times, gpu_samples, host_samples = [], [], []
    started = time.monotonic()
    for step in range(steps + 1):
        snapshot = memory_snapshot()
        if time.monotonic() - started > 600 or snapshot["MemAvailable_mib"] < 768 or snapshot["VmRSS_mib"] > 2048:
            raise ValueError("diagnostic time or guest memory budget reached")
        host_samples.append(host_observation(mode, initial=False, compact=compact))
        begin = time.perf_counter()
        for micro in range(microsteps):
            x, y = sequence[(step * microsteps + micro) % len(sequence)]
            value = model.train_on_batch(x, y)
            if not np.isfinite(np.asarray(value)).all():
                raise ValueError("non-finite diagnostic loss")
        elapsed = time.perf_counter() - begin
        times.append(elapsed)
        gpu_samples.append(gpu_snapshot())
        print(json.dumps({"event": "diagnostic_batch", "stage": mode, "step": step,
            "warmup": step == 0, "seconds": elapsed, "memory": memory_snapshot()}), flush=True)
    finite = all(np.isfinite(weight.numpy()).all() for weight in model.weights)
    if not finite:
        raise ValueError("non-finite diagnostic weights")
    result = {"tf_version": tf.__version__, "gpu_scalar_device": probe.device,
        "first_variable_device": model.weights[0].device, "gpu_allocator_limit_mib": gpu_limit_mib,
        "fresh_random_parent": mode != "stage1", "checkpoint_saved": False,
        "repeated_small_sample": True, "nominal_batch": 128, "microbatch": 1 if mode == "stage3" else 128,
        "warmup_seconds": times[0], "measured_seconds": times[1:], "median_nominal_batch_seconds": statistics.median(times[1:]),
        "weights_finite": finite, "optimizer_iterations": int(model.optimizer.iterations.numpy()),
        "gradient_accumulation": _gradient_accumulation_metrics(model), "gpu_samples": gpu_samples, "host_samples": host_samples,
        "timing_excludes_host_probe": True, "process_rss_guard_mib": 2048, "rss_guard_is_sampled_not_allocation_limit": True}
    tf.keras.backend.clear_session()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("io", "stage1", "stage2", "stage3"), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cache-manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--manifest-sha256", default=MANIFEST_SHA)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--gpu-limit-mib", type=int, choices=(3072,), default=3072)
    parser.add_argument("--compact", action="store_true", help="requires externally enforced cgroup RAM/swap caps of at most 2 GiB each")
    args = parser.parse_args(argv)
    if os.name == "nt" or not 1 <= args.steps <= (3 if args.mode == "stage3" else 100):
        parser.error("requires WSL; bounded steps and GPU allocation required")
    output = Path(args.output_dir).resolve()
    output.relative_to(Path("/mnt/e/blp/sleep_stage_reproduction/runtime/resource-profile-20260909").resolve())
    output.mkdir(parents=True, exist_ok=False)
    record = {"design_id": DESIGN, "mode": args.mode, "status": "started", "pid": os.getpid(),
        "research_run": False, "accepted_lineage": False, "full_cache_validated": False,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "code_sha256": sha256_file(__file__),
        "before": {}}
    record["runtime_environment"] = {key: os.environ.get(key) for key in (
        "TF_CUDNN_USE_AUTOTUNE", "TF_CUDNN_RNN_USE_AUTOTUNE", "TF_CUDNN_WORKSPACE_LIMIT_IN_MB",
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "LD_LIBRARY_PATH")}
    with (output / "started.json").open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    def interrupted(signum, frame):
        handle_stop(record, signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    signal.alarm(600)
    cache = None
    try:
        record["before"] = memory_snapshot()
        if args.compact:
            record["cgroup_before"] = check_compact_scope(cgroup_observation())
        record["host_preflight"] = host_observation(args.mode, compact=args.compact)
        if record["before"]["MemAvailable_mib"] < (1024 if args.mode == "io" else 3072):
            raise ValueError("insufficient available guest memory")
        record["diagnostic_only_budget"] = {"initial_host_free_mib": 2816 if args.compact else (1536 if args.mode == "io" else 3072),
            "runtime_host_reserve_mib": 768 if args.compact else 1024, "compact_cgroup": args.compact,
            "selected_payload_limit_mib": 64, "production_gate_changed": False,
            "limit_note": "cgroup charges process and file cache; GPU/driver allocations may be accounted separately; host reserve is observed, not reserved"}
        if args.mode != "io":
            record["gpu_before"] = gpu_snapshot()
            if record["gpu_before"]["free_mib"] < args.gpu_limit_mib + 512 or record["gpu_before"]["utilization_percent"] > (50 if args.compact else 20):
                raise ValueError("GPU has insufficient diagnostic headroom")
            record["gpu_exclusivity_claimed"] = False
        route = "PAPER_STAGE3_V1" if args.mode == "stage3" else "PAPER_PRETRAIN_V1"
        cache, evidence = selected_cache(args.cache_manifest, args.manifest_sha256, route)
        record["manifest_sha256"] = args.manifest_sha256
        record["selected_chunks"] = evidence
        record["label_counts"] = {str(label): sum(cache.entry(member, route).label == label for member in cache.members) for label in range(5)}
        record["result"] = io_measure(cache, evidence) if args.mode == "io" else gpu_measure(cache, route, args.mode, args.steps, args.gpu_limit_mib, args.compact)
        end_memory = memory_snapshot()
        if end_memory["max_rss_mib"] > (512 if args.mode == "io" else 2048):
            raise ValueError("diagnostic exceeded peak process RSS budget")
        record["status"] = "pass"
    except BaseException as error:
        set_failure(record, error)
    finally:
        signal.alarm(0)
        if args.compact:
            try:
                record["cgroup_after"] = cgroup_observation()
            except Exception as error:
                set_failure(record, error)
        finalize_record(output, record, cache)
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
