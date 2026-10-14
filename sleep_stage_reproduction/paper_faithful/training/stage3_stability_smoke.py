"""Bounded real-data Stage-3 stability diagnostic.

This is deliberately not a training run.  It reconstructs the failed pilot's
capped split, loads the immutable Stage-2 checkpoint, performs exactly one
nominal-batch Stage-3 update through hardware microbatches, and writes a
fail-closed evidence artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath

import numpy as np

from paper_faithful.sst.cache_manifest import ROUTES, canonical_hash, route_config
from paper_faithful.sst.cohort_cache import FULL_ROUTES, load_phase2_binding
from .cache_loader import RUN, SIDE, _host_path
from .models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru
from .run_manifest import sha256_file
from .splits import EpochMember, plan_epoch_split
from .trainer import (
    TrainingContractError,
    _enable_gradient_accumulation,
    cap_split_plan,
    stage_spec,
    validate_stage3_parameter_gate,
)


ROUTE = "PAPER_STAGE3_V1"
PROTOCOL = "PAPER_TEXT_V1"
FAILURE_FINGERPRINT = "a45bd30448e1516f6300946b28075e0192c416480e14a6419cfa42fccb1a7807"


def _require_sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise TrainingContractError(name + " must be a lowercase SHA-256 digest")


def _read_anchored_json(path, expected_sha, name):
    path = Path(path)
    _require_sha(expected_sha, name + " SHA-256")
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise TrainingContractError(name + " trust anchor failed")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TrainingContractError(name + " is unreadable") from error


def _atomic_new(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise TrainingContractError("diagnostic output already exists") from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # Preserve a partial exclusive-create artifact as fail-closed evidence.
        raise


def _weight_digest(weights):
    digest = hashlib.sha256()
    for weight in weights:
        value = np.asarray(weight.numpy())
        digest.update(weight.name.encode("utf-8"))
        digest.update(str(value.shape).encode("ascii"))
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _all_weights_finite(weights):
    return all(np.isfinite(np.asarray(weight.numpy())).all() for weight in weights)


class BoundCache:
    def __init__(self, root, manifest, selected_members):
        self.root = Path(root)
        if (
            set(manifest) != RUN
            or manifest.get("schema_version") != 1
            or manifest.get("routes") != list(FULL_ROUTES)
        ):
            raise TrainingContractError("cache manifest schema or routes are invalid")
        self.chunk_epochs = manifest.get("chunk_epochs")
        if not isinstance(self.chunk_epochs, int) or self.chunk_epochs < 1:
            raise TrainingContractError("cache manifest has an invalid chunk size")
        bindings = manifest.get("record_bindings")
        if not isinstance(bindings, list):
            raise TrainingContractError("cache manifest record bindings are invalid")
        phase_path = _host_path(manifest.get("phase2_manifest_path"))
        completion_path = _host_path(manifest.get("completion_marker_path"))
        try:
            phase = load_phase2_binding(phase_path)
        except Exception as error:
            raise TrainingContractError("finalized Phase-2 binding rejected the selected cache") from error
        if (
            Path(phase["manifest_path"]).resolve(strict=True),
            phase["manifest_sha256"],
            Path(phase["completion_marker_path"]).resolve(strict=True),
            phase["completion_marker_sha256"],
        ) != (
            phase_path,
            manifest.get("phase2_manifest_sha256"),
            completion_path,
            manifest.get("completion_marker_sha256"),
        ):
            raise TrainingContractError("cache manifest Phase-2 binding differs")
        phase_bindings = {binding["record_id"]: binding for binding in phase["bindings"]}
        self.records = {}
        self.record_hosts = {}
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {"record_id", "subject_id", "shard_path", "shard_sha256", "epochs"}:
                raise TrainingContractError("cache manifest record binding is malformed")
            record_id = binding["record_id"]
            if record_id in self.records:
                raise TrainingContractError("cache manifest contains a duplicate record")
            actual = phase_bindings.get(record_id)
            source_host = _host_path(binding["shard_path"])
            if (
                actual is None
                or (binding["subject_id"], binding["shard_sha256"], binding["epochs"])
                != (actual["subject_id"], actual["shard_sha256"], actual["epochs"])
                or source_host != Path(actual["path"]).resolve(strict=True)
            ):
                raise TrainingContractError("cache record binding differs from finalized Phase-2")
            self.records[record_id] = binding
            self.record_hosts[record_id] = source_host
        if set(self.records) != set(phase_bindings):
            raise TrainingContractError("cache record bindings are incomplete")
        chunks = manifest.get("chunks")
        if not isinstance(chunks, list):
            raise TrainingContractError("cache manifest chunks are invalid")
        self.declared = set()
        for chunk in chunks:
            if not isinstance(chunk, dict) or set(chunk) != {"tensor", "sidecar", "resumed"}:
                raise TrainingContractError("cache manifest chunk entry is malformed")
            self.declared.add((PureWindowsPath(chunk["sidecar"]).name, PureWindowsPath(chunk["tensor"]).name))
        self.selected = set(selected_members)
        self.sidecars = {}
        self.verified_tensors = {}
        self.verified_sources = {}
        self.manifest = manifest

    def _binding(self, member):
        if member not in self.selected:
            raise TrainingContractError("member is outside the bounded diagnostic selection")
        binding = self.records.get(member.record_id)
        if binding is None or binding["subject_id"] != member.subject_id or not 0 <= member.epoch_index < binding["epochs"]:
            raise TrainingContractError("selected member does not bind to the cache manifest")
        return binding

    def sample(self, member):
        binding = self._binding(member)
        start = (member.epoch_index // self.chunk_epochs) * self.chunk_epochs
        end = min(start + self.chunk_epochs, binding["epochs"])
        stem = "%s.%s.%08d-%08d" % (member.record_id, ROUTE, start, end)
        sidecar_path = self.root / (stem + ".json")
        tensor_path = self.root / (stem + ".npy")
        if (sidecar_path.name, tensor_path.name) not in self.declared:
            raise TrainingContractError("selected chunk is absent from the cache manifest")
        sidecar = self.sidecars.get(sidecar_path)
        if sidecar is None:
            try:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise TrainingContractError("selected sidecar is unreadable") from error
            if set(sidecar) != SIDE:
                raise TrainingContractError("selected sidecar schema is not writer-exact")
            config = sidecar.get("config")
            route = config.get("route", {}) if isinstance(config, dict) else {}
            try:
                expected_config = route_config(ROUTES[ROUTE], config["transform_identity"])
            except Exception as error:
                raise TrainingContractError("selected sidecar transform identity is invalid") from error
            expected_provenance = {
                "phase2_manifest_sha256": self.manifest["phase2_manifest_sha256"],
                "phase2_manifest_path": self.manifest["phase2_manifest_path"],
                "completion_marker_path": self.manifest["completion_marker_path"],
                "completion_marker_sha256": self.manifest["completion_marker_sha256"],
                "record_binding": binding,
            }
            if (
                sidecar.get("record_id") != member.record_id
                or sidecar.get("subject_id") != member.subject_id
                or sidecar.get("local_epoch_start") != start
                or sidecar.get("local_epoch_end_exclusive") != end
                or route.get("name") != ROUTE
                or sidecar.get("tensor_file") != tensor_path.name
                or sidecar.get("tensor_dtype") != "float32"
                or sidecar.get("tensor_shape") != [end - start, 15, 64, 64, 2]
                or config != expected_config
                or sidecar.get("config_sha256") != canonical_hash(config)
                or sidecar.get("cohort_provenance") != expected_provenance
                or sidecar.get("source_path") != binding["shard_path"]
                or sidecar.get("source_sha256") != binding["shard_sha256"]
                or sidecar.get("local_epoch_indices") != list(range(start, end))
            ):
                raise TrainingContractError("selected sidecar does not bind the expected Stage-3 tensor")
            labels = sidecar.get("labels")
            if not isinstance(labels, list) or len(labels) != end - start or any(type(label) is not int or not 0 <= label <= 4 for label in labels):
                raise TrainingContractError("selected sidecar labels are invalid")
            self.sidecars[sidecar_path] = sidecar
        if member.record_id not in self.verified_sources:
            source_sha = sha256_file(self.record_hosts[member.record_id])
            if source_sha != binding["shard_sha256"]:
                raise TrainingContractError("selected source shard hash failed")
            self.verified_sources[member.record_id] = source_sha
        declared_sha = sidecar.get("tensor_sha256")
        _require_sha(declared_sha, "selected tensor SHA-256")
        if tensor_path not in self.verified_tensors:
            if not tensor_path.is_file() or sha256_file(tensor_path) != declared_sha:
                raise TrainingContractError("selected tensor hash failed")
            try:
                verified = np.load(str(tensor_path), allow_pickle=False, mmap_mode="r")
                if list(verified.shape) != sidecar["tensor_shape"] or verified.dtype != np.dtype("float32") or not np.isfinite(verified).all():
                    raise TrainingContractError("selected tensor payload is invalid")
            except (OSError, ValueError) as error:
                raise TrainingContractError("selected tensor payload is unreadable") from error
            finally:
                if "verified" in locals() and getattr(verified, "_mmap", None) is not None:
                    verified._mmap.close()
            self.verified_tensors[tensor_path] = {
                "tensor_sha256": declared_sha,
                "sidecar": str(sidecar_path),
                "sidecar_sha256": sha256_file(sidecar_path),
                "record_id": member.record_id,
                "source_sha256": binding["shard_sha256"],
            }
        try:
            tensor = np.load(str(tensor_path), allow_pickle=False, mmap_mode="r")
            offset = member.epoch_index - start
            value = np.asarray(tensor[offset : offset + 1], dtype=np.float32).copy()
            label = int(sidecar["labels"][offset])
        except (OSError, ValueError, IndexError) as error:
            raise TrainingContractError("selected tensor sample is unreadable") from error
        finally:
            if "tensor" in locals() and getattr(tensor, "_mmap", None) is not None:
                tensor._mmap.close()
        if value.shape != (1, 15, 64, 64, 2) or not np.isfinite(value).all():
            raise TrainingContractError("selected Stage-3 sample is non-finite or has the wrong shape")
        return value, np.asarray([label], dtype=np.int32)

    def evidence(self):
        return [
            dict({"tensor": str(path)}, **binding)
            for path, binding in sorted(self.verified_tensors.items(), key=lambda item: str(item[0]))
        ]


def _members_from_manifest(manifest):
    members = []
    for binding in manifest["record_bindings"]:
        members.extend(
            EpochMember(binding["subject_id"], binding["record_id"], index)
            for index in range(binding["epochs"])
        )
    return tuple(members)


def run(args):
    cache_manifest = _read_anchored_json(args.cache_manifest, args.cache_manifest_sha256, "cache manifest")
    execution = _read_anchored_json(args.failed_execution, args.failed_execution_sha256, "failed execution")
    _require_sha(args.stage2_checkpoint_sha256, "Stage-2 checkpoint SHA-256")
    checkpoint = Path(args.stage2_checkpoint)
    if not checkpoint.is_file() or sha256_file(checkpoint) != args.stage2_checkpoint_sha256:
        raise TrainingContractError("Stage-2 checkpoint trust anchor failed")
    if (
        execution.get("status") != "failed"
        or execution.get("failure", {}).get("fingerprint") != FAILURE_FINGERPRINT
        or execution.get("stage_artifacts", {}).get("stage2", {}).get("checkpoint_hash") != args.stage2_checkpoint_sha256
        or execution.get("config", {}).get("cache_manifest_hash") != args.cache_manifest_sha256
    ):
        raise TrainingContractError("failed execution does not bind the supplied cache and Stage-2 checkpoint")

    members = _members_from_manifest(cache_manifest)
    capped = cap_split_plan(plan_epoch_split(members, seed=42, protocol_id=PROTOCOL), 128)
    if capped.membership_hashes != execution.get("config", {}).get("split_hashes"):
        raise TrainingContractError("reconstructed capped split does not match failed execution")
    train_members = capped.train
    validation_members = capped.validation[: args.validation_samples]
    if len(train_members) != 128 or not validation_members:
        raise TrainingContractError("bounded diagnostic selection is incomplete")
    cache = BoundCache(Path(args.cache_manifest).parent, cache_manifest, train_members + validation_members)

    import tensorflow as tf

    np.random.seed(42)
    tf.random.set_seed(42)
    spec = stage_spec(PROTOCOL, "stage3", microbatch=1)
    stage1 = build_stage1_cnn(PROTOCOL, input_shape=(64, 64, 2))
    stage2 = build_stage2_supervised_contrastive(PROTOCOL, stage1, input_shape=(64, 64, 2))
    stage2.load_weights(str(checkpoint))
    model = build_stage3_cnn_gru(PROTOCOL, stage2, input_shape=(64, 64, 2))
    parameter_counts = validate_stage3_parameter_gate(model)
    model.compile(optimizer=tf.keras.optimizers.SGD(0.1), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    _enable_gradient_accumulation(tf, model, spec["gradient_accumulation_steps"])
    if int(model.optimizer.iterations.numpy()) != 0 or not _all_weights_finite(model.weights):
        raise TrainingContractError("Stage-3 model is non-finite before the diagnostic update")
    before_digest = _weight_digest(model.trainable_weights)
    non_trainable_before = _weight_digest(model.non_trainable_weights)
    train_labels = [int(cache.sample(member)[1][0]) for member in train_members]

    class DiagnosticSequence(tf.keras.utils.Sequence):
        def __len__(self):
            return len(train_members)

        def __getitem__(self, index):
            if not 0 <= index < len(train_members):
                raise IndexError(index)
            return cache.sample(train_members[index])

    class IterationTrace(tf.keras.callbacks.Callback):
        def __init__(self):
            super().__init__()
            self.losses = []
            self.iterations = []
            self.logs_finite = True

        def on_train_batch_end(self, batch, logs=None):
            logs = {} if logs is None else logs
            numeric = [float(value) for value in logs.values()]
            self.logs_finite = self.logs_finite and bool(numeric) and bool(np.isfinite(numeric).all())
            self.losses.append(float(logs.get("loss", float("nan"))))
            self.iterations.append(int(self.model.optimizer.iterations.numpy()))

    trace = IterationTrace()
    history = model.fit(
        DiagnosticSequence(),
        epochs=1,
        shuffle=False,
        verbose=0,
        callbacks=[tf.keras.callbacks.TerminateOnNaN(), trace],
    )
    losses = trace.losses
    expected_iterations = [0] * 127 + [1]
    history_values = getattr(history, "history", {})
    if (
        len(losses) != 128
        or not trace.logs_finite
        or trace.iterations != expected_iterations
        or not isinstance(history_values, dict)
        or not history_values
        or any(len(series) != 1 or not np.isfinite(float(series[0])) for series in history_values.values())
    ):
        raise TrainingContractError("model.fit violated finite nominal-batch accumulation")
    after_digest = _weight_digest(model.trainable_weights)
    non_trainable_after = _weight_digest(model.non_trainable_weights)
    if before_digest == after_digest or non_trainable_before != non_trainable_after or not _all_weights_finite(model.weights):
        raise TrainingContractError("Stage-3 diagnostic update did not preserve finite frozen weights")

    validation_losses = []
    predictions = []
    labels = []
    for member in validation_members:
        value, label = cache.sample(member)
        prediction = np.asarray(model.predict_on_batch(value), dtype=np.float64)
        if prediction.shape != (1, 5) or not np.isfinite(prediction).all():
            raise TrainingContractError("Stage-3 diagnostic validation prediction is invalid")
        loss = tf.keras.losses.sparse_categorical_crossentropy(label, prediction).numpy()
        if not np.isfinite(loss).all():
            raise TrainingContractError("Stage-3 diagnostic validation loss is non-finite")
        validation_losses.append(float(loss[0]))
        predictions.append([float(value) for value in prediction[0]])
        labels.append(int(label[0]))

    checkpoint_after = sha256_file(checkpoint)
    if checkpoint_after != args.stage2_checkpoint_sha256:
        raise TrainingContractError("immutable Stage-2 checkpoint changed during diagnostic")
    artifact = {
        "schema_version": 1,
        "status": "pass",
        "mode": "bounded_real_data_stage3_stability_diagnostic",
        "not_a_training_run": True,
        "failed_run_id": args.failed_run_id,
        "failed_execution": {"path": str(args.failed_execution), "sha256": args.failed_execution_sha256},
        "cache": {"manifest_path": str(args.cache_manifest), "manifest_sha256": args.cache_manifest_sha256},
        "stage2_checkpoint": {"path": str(checkpoint), "sha256_before": args.stage2_checkpoint_sha256, "sha256_after": checkpoint_after},
        "split_membership_hashes": capped.membership_hashes,
        "selection": {
            "train_members": [member.key for member in train_members],
            "validation_members": [member.key for member in validation_members],
            "train_label_histogram": {str(label): int(train_labels.count(label)) for label in range(5)},
        },
        "strategy": {
            "optimizer": "SGD",
            "learning_rate": 0.1,
            "hardware_microbatch": 1,
            "nominal_batch": 128,
            "effective_batch": spec["effective_batch"],
            "gradient_accumulation_steps": spec["gradient_accumulation_steps"],
            "optimizer_iterations_before": 0,
            "optimizer_iterations_after": int(model.optimizer.iterations.numpy()),
            "incomplete_nominal_batch_dropped": True,
        },
        "model": {
            "parameter_counts": parameter_counts,
            "trainable_weight_sha256_before": before_digest,
            "trainable_weight_sha256_after": after_digest,
            "non_trainable_weight_sha256_before": non_trainable_before,
            "non_trainable_weight_sha256_after": non_trainable_after,
            "frozen_non_trainable_weights_unchanged": True,
            "all_weights_finite_after": True,
        },
        "train": {
            "microbatches": len(losses),
            "execution_path": "model.fit(tf.keras.utils.Sequence)",
            "first_losses": losses[:8],
            "last_loss": losses[-1],
            "history": {name: [float(value) for value in series] for name, series in history_values.items()},
            "all_results_finite": True,
        },
        "validation": {
            "samples": len(validation_losses),
            "labels": labels,
            "losses": validation_losses,
            "predictions": predictions,
            "all_results_finite": True,
        },
        "tensorflow": {"version": tf.__version__, "gpu_devices": [device.name for device in tf.config.list_physical_devices("GPU")]},
        "verified_input_chunks": cache.evidence(),
        "source_sha256": {
            "diagnostic": sha256_file(Path(__file__)),
            "trainer": sha256_file(Path(__file__).with_name("trainer.py")),
            "models": sha256_file(Path(__file__).with_name("models.py")),
            "splits": sha256_file(Path(__file__).with_name("splits.py")),
        },
    }
    _atomic_new(args.output, artifact)
    return artifact


def parser():
    result = argparse.ArgumentParser()
    result.add_argument("--cache-manifest", required=True)
    result.add_argument("--cache-manifest-sha256", required=True)
    result.add_argument("--failed-execution", required=True)
    result.add_argument("--failed-execution-sha256", required=True)
    result.add_argument("--failed-run-id", required=True)
    result.add_argument("--stage2-checkpoint", required=True)
    result.add_argument("--stage2-checkpoint-sha256", required=True)
    result.add_argument("--validation-samples", type=int, default=8)
    result.add_argument("--output", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.failed_run_id != "paper-text-v1-pilot-cap128-seed42-r5-20260826":
        raise TrainingContractError("diagnostic is bound to the failed r5 pilot")
    if not 1 <= args.validation_samples <= 16:
        raise TrainingContractError("validation sample count must be between 1 and 16")
    artifact = run(args)
    print(json.dumps({"output": str(args.output), "status": artifact["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
