"""Risk-level-based approval policies for incident actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.models import Action, RiskLevel


class ApprovalPolicyType(str, Enum):
    AUTO = "auto"           # No human input needed; system auto-approves
    REQUIRE_ONE = "require_one"  # One human approver required
    REQUIRE_TWO = "require_two"  # Two distinct human approvers required


@dataclass
class ApprovalPolicy:
    """Maps each risk level to an approval policy type."""

    low: ApprovalPolicyType = ApprovalPolicyType.AUTO
    medium: ApprovalPolicyType = ApprovalPolicyType.REQUIRE_ONE
    high: ApprovalPolicyType = ApprovalPolicyType.REQUIRE_ONE
    critical: ApprovalPolicyType = ApprovalPolicyType.REQUIRE_TWO

    def get(self, risk_level: RiskLevel) -> ApprovalPolicyType:
        return getattr(self, risk_level.value)


# Singleton default policy — import and use directly in most cases.
DEFAULT_POLICY = ApprovalPolicy()


class ApprovalEvaluator:
    """Evaluates approval state for actions based on a configurable policy.

    Usage:
        evaluator = ApprovalEvaluator()
        evaluator.add_approval(action, "alice")      # returns True when threshold met
        evaluator.apply_auto_approvals(incident.actions)
    """

    def __init__(self, policy: ApprovalPolicy = DEFAULT_POLICY) -> None:
        self._policy = policy

    # ------------------------------------------------------------------
    # Policy queries
    # ------------------------------------------------------------------

    def policy_for(self, action: Action) -> ApprovalPolicyType:
        """Return the effective policy type for an action."""
        if not action.requires_approval:
            return ApprovalPolicyType.AUTO
        return self._policy.get(action.risk_level)

    def minimum_approvals_needed(self, action: Action) -> int:
        """Return the minimum number of distinct human approvals required."""
        policy = self.policy_for(action)
        if policy == ApprovalPolicyType.AUTO:
            return 0
        if policy == ApprovalPolicyType.REQUIRE_ONE:
            return 1
        return 2  # REQUIRE_TWO

    def requires_human_approval(self, action: Action) -> bool:
        return self.minimum_approvals_needed(action) > 0

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_approved(self, action: Action) -> bool:
        """Return True if the action has met its approval threshold or was auto-approved."""
        needed = self.minimum_approvals_needed(action)
        if needed == 0:
            return True
        return len(action.approvals) >= needed

    def is_rejected(self, action: Action) -> bool:
        return action.rejected_by is not None

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def add_approval(self, action: Action, approver: str) -> bool:
        """Record a human approval from *approver*.

        Duplicate approvals from the same person are ignored.
        Sets ``action.approved = True`` and ``action.approved_by`` to the
        last approver once the threshold is met.

        Returns:
            True if the action is now fully approved, False otherwise.
        """
        if approver not in action.approvals:
            action.approvals.append(approver)
        action.approved_by = action.approvals[-1] if action.approvals else approver
        if self.is_approved(action):
            action.approved = True
            return True
        return False

    def reject(self, action: Action, rejected_by: str) -> None:
        """Record a rejection, setting approved=False and rejected_by."""
        action.approved = False
        action.rejected_by = rejected_by

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    def apply_auto_approvals(self, actions: list[Action]) -> list[Action]:
        """Auto-approve all actions that don't need human input.

        Skips actions that are already approved or rejected.
        Returns the list of actions that were auto-approved this call.
        """
        auto_approved: list[Action] = []
        for action in actions:
            if action.approved is not None:
                continue  # already decided
            if not self.requires_human_approval(action):
                action.approved = True
                action.approved_by = "auto"
                auto_approved.append(action)
        return auto_approved

    def get_pending_approvals(self, actions: list[Action]) -> list[Action]:
        """Return actions that require human approval and haven't been decided yet."""
        return [
            a for a in actions
            if self.requires_human_approval(a)
            and not self.is_approved(a)
            and not self.is_rejected(a)
        ]
