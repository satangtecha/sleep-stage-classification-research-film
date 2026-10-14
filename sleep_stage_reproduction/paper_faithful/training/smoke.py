"""Synthetic-only CPU one-batch smoke runner. It does not read sleep data."""
from __future__ import annotations

import argparse
import json

from .models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru, supervised_contrastive_loss
from .protocols import sequence_windows


def run(protocol_id: str) -> dict:
    import tensorflow as tf

    # ``tf.keras.utils.set_random_seed`` did not exist in the locked TF 2.4.
    tf.random.set_seed(42)
    x = tf.random.normal((4, 256, 256, 2), seed=42)
    labels = tf.constant([0, 0, 4, 4], dtype=tf.int32)
    stage1 = build_stage1_cnn(protocol_id)
    stage2 = build_stage2_supervised_contrastive(protocol_id, stage1)

    with tf.GradientTape() as tape:
        stage1_output = stage1(x, training=True)
        stage1_loss = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(labels, stage1_output))
    stage1_gradients = tape.gradient(stage1_loss, stage1.trainable_variables)

    with tf.GradientTape() as tape:
        embeddings = stage2(x, training=True)
        contrastive = supervised_contrastive_loss(labels, embeddings)
    stage2_gradients = tape.gradient(contrastive, stage2.trainable_variables)

    # Stage 3 intentionally freezes Stage 2; build it only after validating the
    # trainable Stage-2 path so the smoke test does not mutate earlier gates.
    stage3 = build_stage3_cnn_gru(protocol_id, stage2)
    sequence = tf.random.normal((1, sequence_windows(protocol_id), 256, 256, 2), seed=7)
    sequence_label = tf.constant([2], dtype=tf.int32)
    with tf.GradientTape() as tape:
        stage3_output = stage3(sequence, training=True)
        stage3_loss = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(sequence_label, stage3_output))
    stage3_gradients = tape.gradient(stage3_loss, stage3.trainable_variables)

    def gradient_status(gradients):
        present = [gradient for gradient in gradients if gradient is not None]
        return {
            "non_none": len(present),
            "all_finite": bool(present) and all(bool(tf.reduce_all(tf.math.is_finite(gradient)).numpy()) for gradient in present),
        }

    checks = {
        "stage1": gradient_status(stage1_gradients),
        "stage2": gradient_status(stage2_gradients),
        "stage3": gradient_status(stage3_gradients),
    }
    passed = all(check["all_finite"] for check in checks.values())
    parameter_counts = {
        "total": stage3.count_params(),
        "trainable": sum(int(weight.shape.num_elements()) for weight in stage3.trainable_weights),
        "non_trainable": sum(int(weight.shape.num_elements()) for weight in stage3.non_trainable_weights),
    }
    return {
        "status": "pass" if passed else "fail",
        "protocol_id": protocol_id,
        "synthetic_only": True,
        "stage1_shape": list(stage1_output.shape),
        "stage2_shape": list(embeddings.shape),
        "stage3_shape": list(stage3_output.shape),
        "stage3_parameter_counts": parameter_counts,
        "losses_finite": {
            "stage1": bool(tf.math.is_finite(stage1_loss).numpy()),
            "stage2": bool(tf.math.is_finite(contrastive).numpy()),
            "stage3": bool(tf.math.is_finite(stage3_loss).numpy()),
        },
        "gradients": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=("PAPER_TEXT_V1", "AUTHOR_CODE_V1"), default="AUTHOR_CODE_V1")
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.protocol), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
