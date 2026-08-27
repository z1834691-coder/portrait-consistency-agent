"""Current configurable policy factories for contract v0.2.

The values here are product configuration, not permanent Pydantic type limits.
Changing a policy requires a new policy version and regression tests, but does
not require changing the six contract schemas.
"""

from portrait_consistency_agent.core.contracts import (
    QualityRoutingPolicySnapshot,
    SafetyPolicySnapshot,
)


def build_v0_quality_routing_policy() -> QualityRoutingPolicySnapshot:
    """Return the currently frozen quality/editability routing thresholds."""

    return QualityRoutingPolicySnapshot(
        policy_id="quality_route_v0",
        policy_version="2026-08-27",
        reject_at_or_below=0.50,
        continue_at_or_above=0.80,
    )


def build_v0_safety_policy() -> SafetyPolicySnapshot:
    """Return the current bounded-plan-family execution policy."""

    return SafetyPolicySnapshot(
        policy_id="safety_v0",
        policy_version="2026-08-27",
        max_provider_rounds=3,
        stop_after_no_improvement_rounds=2,
        max_attempts_per_plan=3,
        max_cost_cny=None,
    )
