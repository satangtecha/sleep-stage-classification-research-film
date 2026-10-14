"""Deterministic split plans with membership hashes and leakage gates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import random
from typing import Iterable


@dataclass(frozen=True, order=True)
class EpochMember:
    subject_id: str
    record_id: str
    epoch_index: int

    @property
    def key(self) -> str:
        return f"{self.subject_id}/{self.record_id}/{self.epoch_index:08d}"


@dataclass(frozen=True)
class SplitPlan:
    protocol_id: str
    seed: int
    train: tuple[EpochMember, ...]
    validation: tuple[EpochMember, ...]
    test: tuple[EpochMember, ...]
    membership_hashes: dict[str, str]

    def as_dict(self) -> dict:
        return {"protocol_id": self.protocol_id, "seed": self.seed, "splits": {name: [asdict(item) for item in getattr(self, name)] for name in ("train", "validation", "test")}, "membership_hashes": self.membership_hashes}


def _hash(items: Iterable[EpochMember]) -> str:
    text = "\n".join(sorted(item.key for item in items)) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_unique(items: list[EpochMember]) -> None:
    if len({item.key for item in items}) != len(items):
        raise ValueError("split input contains duplicate epoch membership keys")
    if any(item.epoch_index < 0 or not item.subject_id or not item.record_id for item in items):
        raise ValueError("each member needs non-empty subject/record IDs and a non-negative epoch index")


def validate_no_leakage(plan: SplitPlan, *, require_subject_disjoint: bool) -> None:
    named = {name: set(getattr(plan, name)) for name in ("train", "validation", "test")}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if named[left] & named[right]:
            raise ValueError(f"epoch leakage between {left} and {right}")
    if require_subject_disjoint:
        subjects = {name: {item.subject_id for item in values} for name, values in named.items()}
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
            if subjects[left] & subjects[right]:
                raise ValueError(f"subject leakage between {left} and {right}")


def _finish(protocol_id: str, seed: int, parts: tuple[list[EpochMember], list[EpochMember], list[EpochMember]], subject_disjoint: bool) -> SplitPlan:
    plan = SplitPlan(protocol_id, seed, *(tuple(part) for part in parts), {name: _hash(part) for name, part in zip(("train", "validation", "test"), parts)})
    validate_no_leakage(plan, require_subject_disjoint=subject_disjoint)
    return plan


def plan_epoch_split(members: Iterable[EpochMember], *, seed: int = 42, fractions: tuple[float, float, float] = (0.8, 0.1, 0.1), protocol_id: str = "PAPER_TEXT_V1") -> SplitPlan:
    if protocol_id not in {"PAPER_TEXT_V1", "AUTHOR_CODE_V1"}:
        raise ValueError("epoch split is restricted to PAPER_TEXT_V1 or AUTHOR_CODE_V1")
    if len(fractions) != 3 or any(value <= 0 for value in fractions) or abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("fractions must be three positive values summing to one")
    ordered = sorted(members)
    _validate_unique(ordered)
    random.Random(seed).shuffle(ordered)
    train_end, validation_end = int(len(ordered) * fractions[0]), int(len(ordered) * (fractions[0] + fractions[1]))
    return _finish(protocol_id, seed, (ordered[:train_end], ordered[train_end:validation_end], ordered[validation_end:]), False)


def plan_subject_split(members: Iterable[EpochMember], *, seed: int, fractions: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> SplitPlan:
    if len(fractions) != 3 or any(value <= 0 for value in fractions) or abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("fractions must be three positive values summing to one")
    ordered = sorted(members)
    _validate_unique(ordered)
    subject_ids = sorted({item.subject_id for item in ordered})
    random.Random(seed).shuffle(subject_ids)
    train_end, validation_end = int(len(subject_ids) * fractions[0]), int(len(subject_ids) * (fractions[0] + fractions[1]))
    groups = (set(subject_ids[:train_end]), set(subject_ids[train_end:validation_end]), set(subject_ids[validation_end:]))
    if any(not group for group in groups):
        raise ValueError("subject split needs enough subjects to populate train, validation, and test")
    return _finish("SUBJECT_GENERALIZATION_V1", seed, tuple([[item for item in ordered if item.subject_id in group] for group in groups]), True)
