"""Bounded Phase 4--6 training scaffold; it never loads cohort data by itself."""

from .splits import EpochMember, SplitPlan, plan_epoch_split, plan_subject_split

__all__ = ["EpochMember", "SplitPlan", "plan_epoch_split", "plan_subject_split"]
