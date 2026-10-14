"""Protocol-aware Keras builders adapted from the vendored v1.0 structures.

TensorFlow is imported only inside builders so split/manifest tooling stays usable on
hosts without the legacy TensorFlow environment.
"""
from __future__ import annotations

from typing import Any

from .protocols import SUPPORTED_PROTOCOLS, sequence_windows


def _tf() -> Any:
    try:
        import tensorflow as tf
    except ImportError as error:  # exercised by dependency-aware tests
        raise RuntimeError("TensorFlow is required for model construction; use the locked WSL TF 2.4 environment") from error
    return tf


def _check_model_protocol(protocol_id: str) -> None:
    if protocol_id not in {"PAPER_TEXT_V1", "AUTHOR_CODE_V1"}:
        raise ValueError("model builders require PAPER_TEXT_V1 or AUTHOR_CODE_V1")


def build_stage1_cnn(protocol_id: str, input_shape: tuple[int, int, int] = (256, 256, 2), classes: int = 5):
    """Build Stage 1.

    Both the manuscript and released model specify six Conv/AvgPool/BN blocks,
    followed by 256- and 64-unit dense layers.
    """
    _check_model_protocol(protocol_id)
    if classes <= 1:
        raise ValueError("classes must be greater than one")
    tf = _tf()
    layers = tf.keras.layers
    inputs = layers.Input(shape=input_shape, name="sst_input")
    resizing_layer = getattr(layers, "Resizing", None)
    if resizing_layer is None:  # TensorFlow 2.4 location used by the author model.
        resizing_layer = layers.experimental.preprocessing.Resizing
    x = resizing_layer(64, 64, name="resize_64")(inputs)
    filters = (16, 32, 64, 128, 256, 512)
    for index, channels in enumerate(filters, start=1):
        x = layers.Conv2D(channels, (3, 3), strides=1, padding="same", activation="relu", name=f"cnn_conv_{index}_{channels}")(x)
        x = layers.AveragePooling2D((2, 2), name=f"cnn_pool_{index}")(x)
        x = layers.BatchNormalization(name=f"cnn_bn_{index}")(x)
    x = layers.Flatten(name="cnn_flatten")(x)
    backbone = tf.keras.Model(inputs, x, name=f"cnn_backbone_{protocol_id.lower()}")
    x = layers.Dense(256, activation="relu", name="cnn_dense_256")(x)
    x = layers.Dropout(0.3, name="cnn_dropout")(x)
    embedding = layers.Dense(64, activation="relu", name="embedding")(x)
    outputs = layers.Dense(classes, activation="softmax", name="stage1_classifier")(embedding)
    model = tf.keras.Model(inputs, outputs, name=f"stage1_cnn_{protocol_id.lower()}")
    # Stable named backbone is equivalent to the vendor's fragile layer-20
    # extraction and yields one 512-feature vector per SST/STFT window.
    model.backbone = backbone  # type: ignore[attr-defined]
    return model


def build_stage2_supervised_contrastive(protocol_id: str, stage1_model=None, input_shape: tuple[int, int, int] = (256, 256, 2)):
    """Build the Stage-2 projection model; caller supplies labels/loss in training."""
    _check_model_protocol(protocol_id)
    tf = _tf()
    stage1_model = stage1_model or build_stage1_cnn(protocol_id, input_shape=input_shape)
    try:
        backbone = stage1_model.backbone
    except AttributeError as error:
        raise ValueError("stage1_model must be built by build_stage1_cnn") from error
    inputs = tf.keras.layers.Input(shape=input_shape, name="sst_input")
    x = backbone(inputs)
    x = tf.keras.layers.Dense(256, activation="relu", name="contrastive_dense_256")(x)
    model = tf.keras.Model(inputs, x, name=f"stage2_supervised_contrastive_{protocol_id.lower()}")
    model.backbone = backbone  # type: ignore[attr-defined]
    return model


def supervised_contrastive_loss(labels, features, temperature: float = 0.05):
    """Author-equivalent supervised N-pairs loss without importing TFA.

    This reproduces ``tensorflow_addons.losses.npairs_loss``: labels are
    converted to a row-normalized same-class matrix before softmax cross
    entropy is applied to the pairwise embedding logits.
    """
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    tf = _tf()
    labels = tf.reshape(labels, (-1,))
    features = tf.math.l2_normalize(features, axis=1)
    logits = tf.matmul(features, features, transpose_b=True) / temperature
    labels = tf.expand_dims(labels, -1)
    positive_pairs = tf.cast(tf.equal(labels, tf.transpose(labels)), logits.dtype)
    positive_pairs /= tf.reduce_sum(positive_pairs, axis=1, keepdims=True)
    losses = tf.nn.softmax_cross_entropy_with_logits(labels=positive_pairs, logits=logits)
    return tf.reduce_mean(losses)


def build_stage3_cnn_gru(protocol_id: str, stage2_model=None, input_shape: tuple[int, int, int] = (256, 256, 2), classes: int = 5):
    """Build Stage 3 with the locked protocol's 12 or 15 timestep input."""
    _check_model_protocol(protocol_id)
    tf = _tf()
    stage2_model = stage2_model or build_stage2_supervised_contrastive(protocol_id, input_shape=input_shape)
    try:
        backbone = stage2_model.backbone
    except AttributeError as error:
        raise ValueError("stage2_model must be built by build_stage2_supervised_contrastive") from error
    for layer in backbone.layers:
        layer.trainable = False
    windows = sequence_windows(protocol_id)
    inputs = tf.keras.layers.Input(shape=(windows, *input_shape), name="epoch_window_sequence")
    features = tf.keras.layers.TimeDistributed(backbone, name="time_distributed_encoder")(inputs)
    gru = tf.keras.layers.GRU(256, return_sequences=True, name="gru_256")(features)
    gru = tf.keras.layers.GRU(128, name="gru_128")(gru)
    skip = tf.keras.layers.Flatten(name="skip_flatten")(features)
    skip = tf.keras.layers.Dense(128, name="skip_dense_128")(skip)
    x = tf.keras.layers.Concatenate(name="gru_skip_concat")([skip, gru])
    for index, units in enumerate((128, 64), start=1):
        x = tf.keras.layers.Dropout(0.3, name=f"stage3_dropout_{index}")(x)
        x = tf.keras.layers.Dense(units, activation="relu", name=f"stage3_dense_{units}")(x)
    x = tf.keras.layers.Dropout(0.3, name="stage3_dropout_3")(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax", name="stage3_classifier")(x)
    return tf.keras.Model(inputs, outputs, name=f"stage3_cnn_gru_{protocol_id.lower()}")
