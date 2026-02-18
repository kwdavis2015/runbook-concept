"""Unit tests for core/approval.py — ApprovalPolicy and ApprovalEvaluator."""

from __future__ import annotations

import pytest

from core.approval import (
    ApprovalEvaluator,
    ApprovalPolicy,
    ApprovalPolicyType,
    DEFAULT_POLICY,
)
from core.models import Action, ActionType, RiskLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(
    risk_level: RiskLevel = RiskLevel.LOW,
    requires_approval: bool = False,
    action_id: str = "act-1",
) -> Action:
    return Action(
        id=action_id,
        action_type=ActionType.EXECUTE,
        description="Test action",
        risk_level=risk_level,
        requires_approval=requires_approval,
    )


# ---------------------------------------------------------------------------
# ApprovalPolicy
# ---------------------------------------------------------------------------


class TestApprovalPolicy:
    def test_default_policy_low(self):
        assert DEFAULT_POLICY.get(RiskLevel.LOW) == ApprovalPolicyType.AUTO

    def test_default_policy_medium(self):
        assert DEFAULT_POLICY.get(RiskLevel.MEDIUM) == ApprovalPolicyType.REQUIRE_ONE

    def test_default_policy_high(self):
        assert DEFAULT_POLICY.get(RiskLevel.HIGH) == ApprovalPolicyType.REQUIRE_ONE

    def test_default_policy_critical(self):
        assert DEFAULT_POLICY.get(RiskLevel.CRITICAL) == ApprovalPolicyType.REQUIRE_TWO

    def test_custom_policy_overrides_medium(self):
        policy = ApprovalPolicy(medium=ApprovalPolicyType.REQUIRE_TWO)
        assert policy.get(RiskLevel.MEDIUM) == ApprovalPolicyType.REQUIRE_TWO
        # Other levels unchanged
        assert policy.get(RiskLevel.LOW) == ApprovalPolicyType.AUTO

    def test_custom_policy_all_auto(self):
        policy = ApprovalPolicy(
            low=ApprovalPolicyType.AUTO,
            medium=ApprovalPolicyType.AUTO,
            high=ApprovalPolicyType.AUTO,
            critical=ApprovalPolicyType.AUTO,
        )
        for level in RiskLevel:
            assert policy.get(level) == ApprovalPolicyType.AUTO

    def test_custom_policy_all_require_two(self):
        policy = ApprovalPolicy(
            low=ApprovalPolicyType.REQUIRE_TWO,
            medium=ApprovalPolicyType.REQUIRE_TWO,
            high=ApprovalPolicyType.REQUIRE_TWO,
            critical=ApprovalPolicyType.REQUIRE_TWO,
        )
        for level in RiskLevel:
            assert policy.get(level) == ApprovalPolicyType.REQUIRE_TWO


# ---------------------------------------------------------------------------
# ApprovalEvaluator.policy_for
# ---------------------------------------------------------------------------


class TestPolicyFor:
    def test_no_requires_approval_always_auto(self):
        ev = ApprovalEvaluator()
        # Even a critical action that doesn't require approval → AUTO
        action = _make_action(risk_level=RiskLevel.CRITICAL, requires_approval=False)
        assert ev.policy_for(action) == ApprovalPolicyType.AUTO

    def test_requires_approval_uses_risk_level(self):
        ev = ApprovalEvaluator()
        assert ev.policy_for(_make_action(RiskLevel.LOW, True)) == ApprovalPolicyType.AUTO
        assert ev.policy_for(_make_action(RiskLevel.MEDIUM, True)) == ApprovalPolicyType.REQUIRE_ONE
        assert ev.policy_for(_make_action(RiskLevel.HIGH, True)) == ApprovalPolicyType.REQUIRE_ONE
        assert ev.policy_for(_make_action(RiskLevel.CRITICAL, True)) == ApprovalPolicyType.REQUIRE_TWO

    def test_custom_policy_respected(self):
        policy = ApprovalPolicy(high=ApprovalPolicyType.REQUIRE_TWO)
        ev = ApprovalEvaluator(policy)
        action = _make_action(RiskLevel.HIGH, requires_approval=True)
        assert ev.policy_for(action) == ApprovalPolicyType.REQUIRE_TWO


# ---------------------------------------------------------------------------
# ApprovalEvaluator.minimum_approvals_needed
# ---------------------------------------------------------------------------


class TestMinimumApprovalsNeeded:
    def test_auto_needs_zero(self):
        ev = ApprovalEvaluator()
        assert ev.minimum_approvals_needed(_make_action(RiskLevel.LOW, False)) == 0

    def test_require_one_needs_one(self):
        ev = ApprovalEvaluator()
        assert ev.minimum_approvals_needed(_make_action(RiskLevel.MEDIUM, True)) == 1

    def test_require_two_needs_two(self):
        ev = ApprovalEvaluator()
        assert ev.minimum_approvals_needed(_make_action(RiskLevel.CRITICAL, True)) == 2


# ---------------------------------------------------------------------------
# ApprovalEvaluator.requires_human_approval
# ---------------------------------------------------------------------------


class TestRequiresHumanApproval:
    def test_auto_does_not_require_human(self):
        ev = ApprovalEvaluator()
        assert not ev.requires_human_approval(_make_action(RiskLevel.LOW, False))

    def test_low_risk_with_requires_approval_flag_still_auto(self):
        # policy for low is AUTO, so flag doesn't matter
        ev = ApprovalEvaluator()
        assert not ev.requires_human_approval(_make_action(RiskLevel.LOW, True))

    def test_medium_requires_human(self):
        ev = ApprovalEvaluator()
        assert ev.requires_human_approval(_make_action(RiskLevel.MEDIUM, True))

    def test_critical_requires_human(self):
        ev = ApprovalEvaluator()
        assert ev.requires_human_approval(_make_action(RiskLevel.CRITICAL, True))


# ---------------------------------------------------------------------------
# ApprovalEvaluator.is_approved
# ---------------------------------------------------------------------------


class TestIsApproved:
    def test_auto_action_always_approved(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.LOW, False)
        assert ev.is_approved(action)

    def test_require_one_not_approved_without_approvals(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        assert not ev.is_approved(action)

    def test_require_one_approved_with_one_approval(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        action.approvals = ["alice"]
        assert ev.is_approved(action)

    def test_require_two_not_approved_with_one(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        action.approvals = ["alice"]
        assert not ev.is_approved(action)

    def test_require_two_approved_with_two(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        action.approvals = ["alice", "bob"]
        assert ev.is_approved(action)


# ---------------------------------------------------------------------------
# ApprovalEvaluator.is_rejected
# ---------------------------------------------------------------------------


class TestIsRejected:
    def test_not_rejected_by_default(self):
        ev = ApprovalEvaluator()
        assert not ev.is_rejected(_make_action())

    def test_rejected_when_rejected_by_set(self):
        ev = ApprovalEvaluator()
        action = _make_action()
        action.rejected_by = "manager"
        assert ev.is_rejected(action)


# ---------------------------------------------------------------------------
# ApprovalEvaluator.add_approval
# ---------------------------------------------------------------------------


class TestAddApproval:
    def test_first_approval_does_not_complete_require_two(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        result = ev.add_approval(action, "alice")
        assert result is False
        assert action.approved is None
        assert action.approvals == ["alice"]

    def test_second_approval_completes_require_two(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        ev.add_approval(action, "alice")
        result = ev.add_approval(action, "bob")
        assert result is True
        assert action.approved is True
        assert action.approved_by == "bob"
        assert action.approvals == ["alice", "bob"]

    def test_first_approval_completes_require_one(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        result = ev.add_approval(action, "alice")
        assert result is True
        assert action.approved is True

    def test_duplicate_approver_ignored(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        ev.add_approval(action, "alice")
        ev.add_approval(action, "alice")  # duplicate
        assert action.approvals == ["alice"]
        assert action.approved is None  # still needs another approver

    def test_approved_by_tracks_last_approver(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        ev.add_approval(action, "alice")
        assert action.approved_by == "alice"
        ev.add_approval(action, "bob")
        assert action.approved_by == "bob"


# ---------------------------------------------------------------------------
# ApprovalEvaluator.reject
# ---------------------------------------------------------------------------


class TestReject:
    def test_reject_sets_approved_false(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.HIGH, True)
        ev.reject(action, "manager")
        assert action.approved is False
        assert action.rejected_by == "manager"

    def test_reject_after_partial_approval(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.CRITICAL, True)
        ev.add_approval(action, "alice")
        ev.reject(action, "bob")
        assert action.approved is False
        assert action.rejected_by == "bob"
        # Previous approvals still recorded
        assert "alice" in action.approvals


# ---------------------------------------------------------------------------
# ApprovalEvaluator.apply_auto_approvals
# ---------------------------------------------------------------------------


class TestApplyAutoApprovals:
    def test_auto_approves_low_risk_no_flag(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.LOW, False)
        approved = ev.apply_auto_approvals([action])
        assert len(approved) == 1
        assert action.approved is True
        assert action.approved_by == "auto"

    def test_does_not_auto_approve_medium_with_flag(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        approved = ev.apply_auto_approvals([action])
        assert len(approved) == 0
        assert action.approved is None

    def test_skips_already_approved(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.LOW, False)
        action.approved = True
        approved = ev.apply_auto_approvals([action])
        assert len(approved) == 0  # not re-approved

    def test_skips_already_rejected(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.LOW, False)
        action.approved = False
        approved = ev.apply_auto_approvals([action])
        assert len(approved) == 0

    def test_mixed_actions(self):
        ev = ApprovalEvaluator()
        low = _make_action(RiskLevel.LOW, False, "act-1")
        high = _make_action(RiskLevel.HIGH, True, "act-2")
        approved = ev.apply_auto_approvals([low, high])
        assert len(approved) == 1
        assert approved[0].id == "act-1"
        assert high.approved is None


# ---------------------------------------------------------------------------
# ApprovalEvaluator.get_pending_approvals
# ---------------------------------------------------------------------------


class TestGetPendingApprovals:
    def test_no_pending_when_all_auto(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.LOW, False)
        assert ev.get_pending_approvals([action]) == []

    def test_pending_when_requires_human(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        pending = ev.get_pending_approvals([action])
        assert len(pending) == 1
        assert pending[0] is action

    def test_not_pending_when_already_approved(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.MEDIUM, True)
        action.approvals = ["alice"]
        action.approved = True
        assert ev.get_pending_approvals([action]) == []

    def test_not_pending_when_rejected(self):
        ev = ApprovalEvaluator()
        action = _make_action(RiskLevel.HIGH, True)
        action.approved = False
        action.rejected_by = "manager"
        assert ev.get_pending_approvals([action]) == []

    def test_mixed_returns_only_undecided(self):
        ev = ApprovalEvaluator()
        approved_action = _make_action(RiskLevel.MEDIUM, True, "act-1")
        approved_action.approvals = ["alice"]
        approved_action.approved = True

        pending_action = _make_action(RiskLevel.HIGH, True, "act-2")

        auto_action = _make_action(RiskLevel.LOW, False, "act-3")

        result = ev.get_pending_approvals([approved_action, pending_action, auto_action])
        assert len(result) == 1
        assert result[0] is pending_action
