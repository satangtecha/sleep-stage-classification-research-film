"""Run one synthetic Stage-1 forward/backward/update batch against author code."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict


def load_author_model(model_path: Path):
    specification = importlib.util.spec_from_file_location("author_stage1_model", str(model_path))
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not load author model at {}".format(model_path))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.get_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-model", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-gpu", action="store_true")
    arguments = parser.parse_args()

    import numpy as np
    import tensorflow as tf

    tf.random.set_seed(42)
    np.random.seed(42)
    gpus = tf.config.list_physical_devices("GPU")
    if arguments.require_gpu and not gpus:
        raise RuntimeError("TensorFlow loaded but no GPU device is visible")

    get_model = load_author_model(arguments.author_model)
    model = get_model((256, 256, 2), 5)
    inputs = tf.random.normal((2, 256, 256, 2), seed=42)
    labels = tf.one_hot([0, 4], depth=5)
    optimizer = tf.keras.optimizers.Adam(learning_rate=1e-4)

    with tf.GradientTape() as tape:
        predictions = model(inputs, training=True)
        loss = tf.reduce_mean(tf.keras.losses.categorical_crossentropy(labels, predictions))
    gradients = tape.gradient(loss, model.trainable_variables)
    gradient_pairs = [(gradient, variable) for gradient, variable in zip(gradients, model.trainable_variables) if gradient is not None]
    finite = all(bool(tf.reduce_all(tf.math.is_finite(gradient)).numpy()) for gradient, _ in gradient_pairs)
    optimizer.apply_gradients(gradient_pairs)

    result: Dict[str, Any] = {
        "status": "pass" if finite and len(gradient_pairs) == len(model.trainable_variables) else "fail",
        "tensorflow": tf.__version__,
        "gpu_devices": [device.name for device in gpus],
        "author_model_path": str(arguments.author_model.resolve()),
        "batch_shape": list(inputs.shape),
        "output_shape": list(predictions.shape),
        "loss": float(loss.numpy()),
        "trainable_variables": len(model.trainable_variables),
        "non_none_gradients": len(gradient_pairs),
        "all_gradients_finite": finite,
        "optimizer_step_applied": True,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

