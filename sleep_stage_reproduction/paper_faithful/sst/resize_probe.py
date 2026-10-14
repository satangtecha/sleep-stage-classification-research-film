"""Compare the offline NumPy resize with the locked Keras resize layer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .storage import require_e_drive
from .transform import resize_bilinear_half_pixel


def probe(output_path: str | Path) -> dict[str, object]:
    import tensorflow as tf

    random = np.random.RandomState(42)
    source = random.standard_normal((256, 256, 2)).astype(np.float32)
    offline = np.dstack(tuple(resize_bilinear_half_pixel(source[..., channel], 64) for channel in range(2)))
    resizing_layer = getattr(tf.keras.layers, "Resizing", None)
    if resizing_layer is None:
        resizing_layer = tf.keras.layers.experimental.preprocessing.Resizing
    keras = resizing_layer(64, 64, interpolation="bilinear")(tf.convert_to_tensor(source[None, ...])).numpy()[0]
    difference = np.abs(offline - keras)
    result = {
        "status": "pass" if float(difference.max()) <= 1e-6 else "fail",
        "tensorflow": tf.__version__,
        "source_shape": list(source.shape),
        "output_shape": list(offline.shape),
        "max_abs_difference": float(difference.max()),
        "mean_abs_difference": float(difference.mean()),
        "offline_sha256": hashlib.sha256(offline.tobytes(order="C")).hexdigest(),
        "keras_sha256": hashlib.sha256(keras.astype(np.float32).tobytes(order="C")).hexdigest(),
        "tolerance": 1e-6,
    }
    destination = require_e_drive(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    result = probe(arguments.output)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
