"""Deterministic, record-bounded planners for the two declared window protocols."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WindowProtocol:
    name: str
    windows: int
    width: int
    overlap: int

    @property
    def stride(self) -> int:
        return self.width - self.overlap

    @property
    def required_samples(self) -> int:
        return self.width + (self.windows - 1) * self.stride

    def starts(self) -> tuple[int, ...]:
        return tuple(index * self.stride for index in range(self.windows))

    def ends(self) -> tuple[int, ...]:
        return tuple(start + self.width for start in self.starts())


PAPER_TEXT_V1 = WindowProtocol("PAPER_TEXT_V1", windows=12, width=256, overlap=7)
AUTHOR_CODE_V1 = WindowProtocol("AUTHOR_CODE_V1", windows=15, width=256, overlap=64)


def plan_window_bounds(protocol: WindowProtocol, epoch_samples: int) -> tuple[tuple[int, int], ...]:
    """Return exact [start, end) bounds, rejecting a source too short for the protocol."""
    if epoch_samples < protocol.required_samples:
        raise ValueError(
            f"{protocol.name} needs {protocol.required_samples} samples; got {epoch_samples}"
        )
    return tuple(zip(protocol.starts(), protocol.ends()))


def window_one_epoch(epoch: np.ndarray, protocol: WindowProtocol) -> np.ndarray:
    """Window one preprocessed epoch only; this API cannot cross a record boundary."""
    samples = np.asarray(epoch)
    if samples.ndim != 1:
        raise ValueError("window_one_epoch accepts exactly one one-dimensional epoch")
    bounds = plan_window_bounds(protocol, samples.size)
    return np.stack([samples[start:end] for start, end in bounds])


def window_record_epochs(record_id: str, epochs: np.ndarray, protocol: WindowProtocol) -> np.ndarray:
    """Window each epoch independently, retaining the record boundary in the caller's data model."""
    if not record_id:
        raise ValueError("record_id is required; concatenated anonymous records are forbidden")
    values = np.asarray(epochs)
    if values.ndim != 2:
        raise ValueError("epochs must be [epoch, sample]; concatenated records are forbidden")
    return np.stack([window_one_epoch(epoch, protocol) for epoch in values])
