"""Leakage-resistant subject-held-out pilot planning and evidence helpers.

The model protocol remains PAPER_TEXT_V1.  SUBJECT_GENERALIZATION_V1 is an
evaluation protocol and must never be confused with the manuscript's
epoch-random split.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
import re
from typing import Iterable, Sequence

from .splits import EpochMember, SplitPlan, validate_no_leakage


SUBJECT_GENERALIZATION_PROTOCOL_ID = "SUBJECT_GENERALIZATION_V1"
MODEL_PROTOCOL_ID = "PAPER_TEXT_V1"
DEFAULT_SELECTION_SEED = 42
DEFAULT_PILOT_SUBJECT_COUNT = 6
DEFAULT_RUN_PREFIX = "subject-generalization-v1-pilot-20260906"
SAMPLED_CAP_POLICY = "subject_balanced_seeded_temporal_sample_v2"


def sample_record_members(records, subjects, cap, seed):
    """Small, label-blind smoke sample spanning each subject's recordings.

    Offsets are sampled from ranges, so memory is O(subjects * cap), not
    O(cohort epochs). This is NOT a substitute for full held-out evaluation.
    Both manifest planning and execution use this exact function.
    """
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("split cap must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("sampling seed must be an unsigned 32-bit integer")
    groups = {subject: [] for subject in sorted(subjects)}
    seen = set()
    for record, subject, epochs in sorted(records):
        if (not isinstance(record, str) or not record or not isinstance(subject, str)
                or not subject or isinstance(epochs, bool) or not isinstance(epochs, int)
                or epochs < 0 or record in seen):
            raise ValueError("invalid or duplicate record declaration")
        seen.add(record)
        if subject in groups and epochs:
            groups[subject].append((record, epochs))
    if not groups or any(not group for group in groups.values()):
        raise ValueError("sample has an empty subject group")
    ordered_subjects = sorted(groups)
    random.Random(seed).shuffle(ordered_subjects)
    sampled = {}
    for subject in ordered_subjects:
        group = groups[subject]
        total = sum(count for _, count in group)
        subject_seed = int(hashlib.sha256((str(seed) + ":" + subject).encode("utf-8")).hexdigest(), 16)
        offsets = random.Random(subject_seed).sample(range(total), min(cap, total))
        values = []
        for offset in offsets:
            for record, count in group:
                if offset < count:
                    values.append(EpochMember(subject, record, offset))
                    break
                offset -= count
        sampled[subject] = values
    result = []
    for position in range(max(map(len, sampled.values()))):
        for subject in ordered_subjects:
            if position < len(sampled[subject]):
                result.append(sampled[subject][position])
                if len(result) == cap:
                    return tuple(result)
    return tuple(result)


def sample_record_members_per_subject(records, subjects, cap, seed):
    """Return up to ``cap`` deterministic members for every subject.

    The original smoke sampler intentionally caps a whole split.  The
    resource-limited subject-generalization protocol instead declares its cap
    per subject so every training fold still has complete nominal batches.
    """
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("split cap must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("sampling seed must be an unsigned 32-bit integer")
    ordered_subjects = tuple(sorted(subjects))
    if not ordered_subjects:
        raise ValueError("sample has no subjects")
    result = []
    for subject in ordered_subjects:
        result.extend(sample_record_members(records, {subject}, cap, seed))
    return tuple(result)


def _membership_hash(items: Iterable[EpochMember]) -> str:
    payload = "\n".join(sorted(item.key for item in items)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _subject_ids(members: Iterable[EpochMember]) -> tuple[str, ...]:
    values = tuple(sorted({item.subject_id for item in members}))
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("subject IDs must be non-empty strings")
    return values


def select_pilot_subjects(
    members: Iterable[EpochMember],
    *,
    seed: int = DEFAULT_SELECTION_SEED,
    count: int = DEFAULT_PILOT_SUBJECT_COUNT,
) -> tuple[str, ...]:
    """Select a deterministic, recorded subset for the six-subject pilot."""

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("selection seed must be a non-negative integer")
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ValueError("pilot subject count must be at least two")
    subjects = list(_subject_ids(members))
    if len(subjects) < count:
        raise ValueError("pilot subject count exceeds available subjects")
    random.Random(seed).shuffle(subjects)
    return tuple(subjects[:count])


@dataclass(frozen=True)
class SubjectFold:
    fold_index: int
    test_subject: str
    validation_subject: str
    train_subjects: tuple[str, ...]
    plan: SplitPlan

    def as_dict(self) -> dict:
        """Return a compact, immutable fold manifest.

        The complete epoch-member lists are runtime inputs to training, not
        protocol metadata.  Serializing them here duplicated hundreds of
        thousands of references across six folds and made the protocol file
        needlessly expensive to build.  Hashes and counts retain the
        verifiable identity of every partition without embedding the cache.
        """
        return {
            "fold_index": self.fold_index,
            "test_subject": self.test_subject,
            "validation_subject": self.validation_subject,
            "train_subjects": list(self.train_subjects),
            "protocol_id": self.plan.protocol_id,
            "seed": self.plan.seed,
            "split_membership_hashes": dict(self.plan.membership_hashes),
            "split_epoch_counts": {
                name: len(getattr(self.plan, name))
                for name in ("train", "validation", "test")
            },
        }


def _subject_balanced_cap(items: Iterable[EpochMember], cap: int) -> tuple[EpochMember, ...]:
    """Take a deterministic cap while retaining every available subject first.

    A plain ``items[:cap]`` can silently turn a nominally subject-held-out
    pilot into a one-subject training sample because cache members are sorted
    by subject.  Round-robin over sorted subject groups makes the cap explicit
    and guarantees representation of every partition subject whenever the cap
    is at least the number of subjects.
    """

    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("split cap must be a positive integer")
    ordered = tuple(sorted(items))
    groups = {}
    for member in ordered:
        groups.setdefault(member.subject_id, []).append(member)
    subjects = tuple(sorted(groups))
    selected = []
    position = 0
    while len(selected) < cap and position < max((len(group) for group in groups.values()), default=0):
        for subject in subjects:
            group = groups[subject]
            if position < len(group):
                selected.append(group[position])
                if len(selected) == cap:
                    break
        position += 1
    if not selected:
        raise ValueError("split cap leaves an empty split")
    return tuple(selected)


def cap_subject_balanced_plan(plan: SplitPlan, cap: int) -> SplitPlan:
    """Legacy V1 cap retained to interpret old plans; new runs use v2 sampling."""

    parts = {
        name: _subject_balanced_cap(getattr(plan, name), cap)
        for name in ("train", "validation", "test")
    }
    capped = SplitPlan(
        plan.protocol_id,
        plan.seed,
        parts["train"],
        parts["validation"],
        parts["test"],
        {name: _membership_hash(parts[name]) for name in parts},
    )
    validate_no_leakage(capped, require_subject_disjoint=True)
    return capped


def capped_fold_record(fold: SubjectFold, capped_plan: SplitPlan, cap: int) -> dict:
    """Describe both the uncapped source and the exact executed cap."""

    return {
        "fold_index": fold.fold_index,
        "test_subject": fold.test_subject,
        "validation_subject": fold.validation_subject,
        "train_subjects": list(fold.train_subjects),
        "protocol_id": capped_plan.protocol_id,
        "seed": capped_plan.seed,
        "cap": cap,
        "cap_policy": "subject_balanced_round_robin_sorted_members",
        "uncapped_split_epoch_counts": {
            name: len(getattr(fold.plan, name))
            for name in ("train", "validation", "test")
        },
        "split_epoch_counts": {
            name: len(getattr(capped_plan, name))
            for name in ("train", "validation", "test")
        },
        "split_membership_hashes": dict(capped_plan.membership_hashes),
    }


def build_subject_fold(
    members: Iterable[EpochMember],
    pilot_subjects: Sequence[str],
    fold_index: int,
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
) -> SubjectFold:
    """Build one circular validation/test fold with strict subject separation.

    The six selected subjects rotate through the test and validation roles.
    Every other subject in the finalized cache remains in that fold's training
    partition.  No r19 checkpoint or split is consulted.
    """

    all_members = tuple(sorted(members))
    selected = tuple(pilot_subjects)
    if len(selected) < 2 or len(set(selected)) != len(selected):
        raise ValueError("pilot subjects must be unique and contain at least two subjects")
    available = set(_subject_ids(all_members))
    if any(subject not in available for subject in selected):
        raise ValueError("pilot subject is absent from cache membership")
    if isinstance(fold_index, bool) or not isinstance(fold_index, int):
        raise ValueError("fold index must be an integer")
    if not 0 <= fold_index < len(selected):
        raise ValueError("fold index is outside the pilot subject set")
    test_subject = selected[fold_index]
    validation_subject = selected[(fold_index + 1) % len(selected)]
    excluded = {test_subject, validation_subject}
    train_members = tuple(item for item in all_members if item.subject_id not in excluded)
    validation_members = tuple(item for item in all_members if item.subject_id == validation_subject)
    test_members = tuple(item for item in all_members if item.subject_id == test_subject)
    if not train_members or not validation_members or not test_members:
        raise ValueError("subject fold contains an empty partition")
    plan = SplitPlan(
        SUBJECT_GENERALIZATION_PROTOCOL_ID,
        selection_seed,
        train_members,
        validation_members,
        test_members,
        {
            "train": _membership_hash(train_members),
            "validation": _membership_hash(validation_members),
            "test": _membership_hash(test_members),
        },
    )
    validate_no_leakage(plan, require_subject_disjoint=True)
    train_subjects = tuple(sorted({item.subject_id for item in train_members}))
    return SubjectFold(
        fold_index=fold_index,
        test_subject=test_subject,
        validation_subject=validation_subject,
        train_subjects=train_subjects,
        plan=plan,
    )


def build_pilot_folds(
    members: Iterable[EpochMember],
    *,
    selection_seed: int = DEFAULT_SELECTION_SEED,
    count: int = DEFAULT_PILOT_SUBJECT_COUNT,
) -> tuple[tuple[str, ...], tuple[SubjectFold, ...]]:
    """Return the immutable selected subject list and all pilot folds."""

    all_members = tuple(sorted(members))
    selected = select_pilot_subjects(all_members, seed=selection_seed, count=count)
    folds = tuple(
        build_subject_fold(
            all_members,
            selected,
            index,
            selection_seed=selection_seed,
        )
        for index in range(len(selected))
    )
    if tuple(fold.test_subject for fold in folds) != selected:
        raise ValueError("pilot fold test-subject ordering is not stable")
    if {fold.validation_subject for fold in folds} != set(selected):
        raise ValueError("pilot fold validation-subject coverage is incomplete")
    return selected, folds


def safe_fold_id(prefix: str, fold_index: int, test_subject: str) -> str:
    """Construct a path-safe, immutable fold run ID."""

    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", prefix):
        raise ValueError("run prefix is not path-safe")
    if isinstance(fold_index, bool) or not isinstance(fold_index, int) or fold_index < 0:
        raise ValueError("fold index must be a non-negative integer")
    if not isinstance(test_subject, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", test_subject):
        raise ValueError("test subject is not path-safe")
    return f"{prefix}-fold{fold_index + 1:02d}-test-{test_subject}"


def protocol_record(
    *,
    cache_manifest: str,
    cache_hash: str,
    source_manifest: str,
    source_hash: str,
    environment_manifest: str,
    environment_hash: str,
    run_prefix: str = DEFAULT_RUN_PREFIX,
    selection_seed: int = DEFAULT_SELECTION_SEED,
    pilot_subjects: Sequence[str],
    fold_ids: Sequence[str],
) -> dict:
    """Create the small immutable protocol record bound by the pilot runner."""

    if len(pilot_subjects) != len(fold_ids) or len(pilot_subjects) < 2:
        raise ValueError("pilot subject and fold lists must have the same non-trivial length")
    return {
        "schema_version": 1,
        "protocol_id": SUBJECT_GENERALIZATION_PROTOCOL_ID,
        "model_protocol_id": MODEL_PROTOCOL_ID,
        "comparison_guard": {
            "may_compare_to_reported_83_percent": False,
            "reason": "subject-held-out evaluation differs from the manuscript epoch-random split",
        },
        "run_prefix": run_prefix,
        "selection_seed": selection_seed,
        "pilot_subjects": list(pilot_subjects),
        "fold_ids": list(fold_ids),
        "cache_manifest": cache_manifest,
        "cache_hash": cache_hash,
        "source_manifest": source_manifest,
        "source_hash": source_hash,
        "environment_manifest": environment_manifest,
        "environment_hash": environment_hash,
        "fold_policy": "one rotating test subject and one rotating validation subject; all remaining subjects train",
    }


def canonical_json(value: dict) -> str:
    """Serialize evidence with one deterministic UTF-8 representation."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
