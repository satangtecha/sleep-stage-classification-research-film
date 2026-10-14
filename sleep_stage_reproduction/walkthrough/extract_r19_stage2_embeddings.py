"""Read-only post-hoc Stage-2 embedding extraction for the completed r19 pilots.

Run this script with the locked WSL TensorFlow 2.4 interpreter.  It reconstructs
the immutable capped test split, loads the published Stage-2 checkpoint, performs
CPU-only inference, and writes visualization-only NPZ/JSON files outside the
canonical run directories.  It never trains or mutates a run.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from paper_faithful.training.models import build_stage1_cnn, build_stage2_supervised_contrastive
from paper_faithful.training.splits import EpochMember, plan_epoch_split
from paper_faithful.training.trainer import cap_split_plan


ROUTE = "PAPER_PRETRAIN_V1"
CHUNK_EPOCHS = 32


def sha256_file(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reconstruct_plan(preprocessing, seed, cap, expected_hash):
    members = []
    for record in preprocessing["records"]:
        for epoch_index in range(int(record["epochs"])):
            members.append(EpochMember(record["subject_id"], record["record_id"], epoch_index))
    plan = cap_split_plan(plan_epoch_split(members, seed=seed, protocol_id="PAPER_TEXT_V1"), cap)
    if plan.membership_hashes["test"] != expected_hash:
        raise RuntimeError("reconstructed test split does not match execution.json")
    return plan


def epoch_tensor_and_label(cache_root, member, record_epochs):
    start = (member.epoch_index // CHUNK_EPOCHS) * CHUNK_EPOCHS
    end = min(start + CHUNK_EPOCHS, record_epochs[member.record_id])
    stem = "%s.%s.%08d-%08d" % (member.record_id, ROUTE, start, end)
    sidecar_path = cache_root / (stem + ".json")
    tensor_path = cache_root / (stem + ".npy")
    sidecar = load_json(sidecar_path)
    offset = member.epoch_index - start
    if sidecar["record_id"] != member.record_id or sidecar["subject_id"] != member.subject_id:
        raise RuntimeError("cache sidecar identity mismatch")
    if sidecar["local_epoch_indices"][offset] != member.epoch_index:
        raise RuntimeError("cache sidecar epoch mismatch")
    tensor = np.load(str(tensor_path), mmap_mode="r")
    return np.asarray(tensor[offset], dtype=np.float32), int(sidecar["labels"][offset])


def extract(args):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    execution_path = args.run_dir / "execution.json"
    execution = load_json(execution_path)
    if execution.get("status") != "completed":
        raise RuntimeError("embedding extraction requires a completed run")
    config = execution["config"]
    seed = int(config["split_seed"])
    cap = int(config["per_split_epoch_cap"])
    if cap != 128 or config["protocol_id"] != "PAPER_TEXT_V1":
        raise RuntimeError("this extractor is bound to the r19 PAPER_TEXT_V1 cap128 pilots")

    preprocessing = load_json(args.preprocessing_manifest)
    plan = reconstruct_plan(preprocessing, seed, cap, config["split_hashes"]["test"])
    record_epochs = {row["record_id"]: int(row["epochs"]) for row in preprocessing["records"]}

    checkpoint = args.run_dir / "stage2.weights.h5"
    expected_checkpoint_hash = execution["stage_artifacts"]["stage2"]["checkpoint_hash"]
    if sha256_file(checkpoint) != expected_checkpoint_hash:
        raise RuntimeError("Stage-2 checkpoint hash mismatch")

    stage1 = build_stage1_cnn("PAPER_TEXT_V1", input_shape=(64, 64, 2))
    model = build_stage2_supervised_contrastive("PAPER_TEXT_V1", stage1, input_shape=(64, 64, 2))
    model.load_weights(str(checkpoint))

    feature_blocks = []
    label_blocks = []
    member_keys = []
    epoch_batch = int(args.epoch_batch)
    for start in range(0, len(plan.test), epoch_batch):
        tensors = []
        labels = []
        keys = []
        for member in plan.test[start : start + epoch_batch]:
            tensor, label = epoch_tensor_and_label(args.cache_root, member, record_epochs)
            tensors.append(tensor)
            labels.extend([label] * tensor.shape[0])
            keys.extend([member.key] * tensor.shape[0])
        x = np.concatenate(tensors, axis=0)
        feature_blocks.append(np.asarray(model.predict_on_batch(x), dtype=np.float32))
        label_blocks.append(np.asarray(labels, dtype=np.int16))
        member_keys.extend(keys)
        print("processed epochs %d..%d / %d" % (start + 1, min(start + epoch_batch, len(plan.test)), len(plan.test)))

    embeddings = np.concatenate(feature_blocks, axis=0)
    labels = np.concatenate(label_blocks, axis=0)
    if embeddings.shape != (cap * 12, 256) or labels.shape != (cap * 12,):
        raise RuntimeError("unexpected Stage-2 embedding shape")
    if not np.isfinite(embeddings).all():
        raise RuntimeError("non-finite Stage-2 embeddings")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(args.output),
        embeddings=embeddings,
        labels=labels,
        member_keys=np.asarray(member_keys),
        split_seed=np.asarray(seed),
        model_seed=np.asarray(config["model_seed"]),
    )
    artifact = {
        "schema_version": 1,
        "purpose": "visualization_only_posthoc_inference",
        "training_performed": False,
        "run_id": args.run_dir.name,
        "run_status": execution["status"],
        "protocol_id": config["protocol_id"],
        "split": "test",
        "split_seed": seed,
        "model_seed": int(config["model_seed"]),
        "test_membership_sha256": plan.membership_hashes["test"],
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": expected_checkpoint_hash,
        "execution_path": str(execution_path),
        "execution_sha256": sha256_file(execution_path),
        "preprocessing_manifest_path": str(args.preprocessing_manifest),
        "preprocessing_manifest_sha256": sha256_file(args.preprocessing_manifest),
        "cache_root": str(args.cache_root),
        "route": ROUTE,
        "epoch_count": cap,
        "windows_per_epoch": 12,
        "embedding_count": int(embeddings.shape[0]),
        "embedding_dimensions": int(embeddings.shape[1]),
        "output_npz": str(args.output),
        "output_npz_sha256": sha256_file(args.output),
        "tensorflow_device": "CPU_only_CUDA_VISIBLE_DEVICES_minus_1",
    }
    provenance = args.output.with_suffix(".json")
    provenance.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "output": str(args.output), "shape": list(embeddings.shape)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--preprocessing-manifest", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--epoch-batch", type=int, default=4)
    args = parser.parse_args()
    if args.epoch_batch < 1 or args.epoch_batch > 16:
        raise SystemExit("--epoch-batch must be in 1..16")
    extract(args)


if __name__ == "__main__":
    main()
