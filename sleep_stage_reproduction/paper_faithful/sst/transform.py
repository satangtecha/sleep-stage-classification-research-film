"""One-window SST conversion, with an optional ssqueezepy dependency."""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np

try:
    from importlib import metadata
except ImportError:  # Python 3.7 locked author environment
    import importlib_metadata as metadata


class SSTDependencyError(RuntimeError):
    """Raised when the intentionally external SST implementation is unavailable."""


def ssqueezepy_version() -> Optional[str]:
    try:
        return metadata.version("ssqueezepy")
    except metadata.PackageNotFoundError:
        return None


def minmax_component(component: np.ndarray) -> np.ndarray:
    """Author-style per-component normalization, made finite for constant inputs."""
    values = np.asarray(component, dtype=np.float32)
    low, high = float(values.min()), float(values.max())
    if high == low:
        return np.zeros(values.shape, dtype=np.float32)
    return (values - low) / (high - low)


def _ssq_stft() -> Callable[..., object]:
    try:
        from ssqueezepy import ssq_stft
    except ImportError as error:
        raise SSTDependencyError(
            "ssqueezepy is unavailable; install the declared compatibility candidate in an isolated environment"
        ) from error
    return ssq_stft


def resize_bilinear_half_pixel(image: np.ndarray, resolution: int) -> np.ndarray:
    """NumPy bilinear resize matching TensorFlow's half-pixel coordinate rule.

    This supports an offline 256-to-64 cache while retaining the geometry of
    the author's Keras ``Resizing(64, 64, interpolation='bilinear')`` layer.
    Numerical equivalence is gated against the locked TensorFlow environment.
    """
    if image.shape == (resolution, resolution):
        return image.astype(np.float32, copy=False)
    if image.ndim != 2:
        raise ValueError("resize expects a two-dimensional component")
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    values = np.asarray(image, dtype=np.float32)
    source_y = (np.arange(resolution, dtype=np.float32) + np.float32(0.5)) * np.float32(values.shape[0] / resolution) - np.float32(0.5)
    source_x = (np.arange(resolution, dtype=np.float32) + np.float32(0.5)) * np.float32(values.shape[1] / resolution) - np.float32(0.5)
    y0_raw, x0_raw = np.floor(source_y).astype(np.int64), np.floor(source_x).astype(np.int64)
    y1_raw, x1_raw = y0_raw + 1, x0_raw + 1
    wy, wx = (source_y - y0_raw).astype(np.float32), (source_x - x0_raw).astype(np.float32)
    y0, y1 = np.clip(y0_raw, 0, values.shape[0] - 1), np.clip(y1_raw, 0, values.shape[0] - 1)
    x0, x1 = np.clip(x0_raw, 0, values.shape[1] - 1), np.clip(x1_raw, 0, values.shape[1] - 1)
    top = values[np.ix_(y0, x0)] * (np.float32(1.0) - wx)[None, :] + values[np.ix_(y0, x1)] * wx[None, :]
    bottom = values[np.ix_(y1, x0)] * (np.float32(1.0) - wx)[None, :] + values[np.ix_(y1, x1)] * wx[None, :]
    return (top * (np.float32(1.0) - wy)[:, None] + bottom * wy[:, None]).astype(np.float32, copy=False)


def convert_single_window(
    samples: np.ndarray,
    *,
    protocol_id: str,
    n_fft: int = 512,
    frequency_bins: int = 256,
    output_resolution: int = 256,
    ssq_transform: Optional[Callable[..., object]] = None,
) -> np.ndarray:
    """Convert one window using the explicitly selected paper/code transform route.

    ``ssq_stft`` returns the synchrosqueezed transform (Tx) at slot 0 and the
    ordinary STFT coefficients (Sx) at slot 1. The paper describes Tx, while
    the released author notebooks explicitly consume slot 1.
    """
    transform_slot = {"PAPER_TEXT_V1": 0, "AUTHOR_CODE_V1": 1}.get(protocol_id)
    if transform_slot is None:
        raise ValueError("protocol_id must be PAPER_TEXT_V1 or AUTHOR_CODE_V1")
    signal = np.asarray(samples, dtype=np.float32)
    if signal.ndim != 1:
        raise ValueError("single-window SST conversion requires one-dimensional samples")
    transform = ssq_transform or _ssq_stft()
    result = transform(signal, n_fft=n_fft)
    try:
        time_frequency = result[transform_slot]
    except (TypeError, IndexError) as error:
        raise ValueError(f"ssq_stft result does not contain transform slot {transform_slot}") from error
    tf = np.asarray(time_frequency)
    if tf.ndim != 2 or tf.shape[0] < frequency_bins:
        raise ValueError(f"expected at least {frequency_bins} SST frequency bins; got {tf.shape}")
    real = minmax_component(tf.real[:frequency_bins, :])
    imag = minmax_component(tf.imag[:frequency_bins, :])
    real = resize_bilinear_half_pixel(real, output_resolution)
    imag = resize_bilinear_half_pixel(imag, output_resolution)
    return np.dstack((real, imag)).astype(np.float32, copy=False)
