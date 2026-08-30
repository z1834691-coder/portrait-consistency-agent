"""Current configurable policy factories for contract v0.4.

The values here are product configuration, not permanent Pydantic type limits.
Changing a policy requires a new policy version and regression tests, but does
not require changing the six contract schemas.
"""

from dataclasses import dataclass

from portrait_consistency_agent.core.contracts import (
    DataRetentionPolicySnapshot,
    QualityRoutingPolicySnapshot,
    SafetyPolicySnapshot,
    VerificationStrategy,
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
    """Return the current bounded-plan-family execution policy.

    ``max_provider_rounds`` limits result-changing rounds in one confirmed plan
    family.  ``max_attempts_per_plan`` is deliberately one: the 8B product
    decision forbids silent automatic retries of a paid image-edit request.
    A later retry must be a new, visible user confirmation and therefore a
    separate plan / ProviderRun evidence chain.
    """

    return SafetyPolicySnapshot(
        policy_id="safety_v0",
        policy_version="2026-08-28-8b",
        max_provider_rounds=3,
        stop_after_no_improvement_rounds=2,
        max_attempts_per_plan=1,
        max_cost_cny=None,
    )


@dataclass(frozen=True)
class VerificationPolicy:
    """Versioned thresholds and strategy allow-list for Checkpoint 8C.

    ``measurement_tolerance`` is the smallest relative gap change that the
    current extractor can call an improvement.  It is an engineering default,
    not a calibrated acceptance probability; a benchmark-backed revision may
    replace it later without changing the contract vocabulary.
    """

    policy_id: str
    policy_version: str
    measurement_tolerance: float
    target_gap_tolerance: float
    minimum_measurement_confidence: float
    allowed_strategies: tuple[VerificationStrategy, ...]

    def __post_init__(self) -> None:
        if not 0.0 < self.measurement_tolerance < self.target_gap_tolerance:
            raise ValueError("verification tolerances must be positive and ordered")
        if not 0.0 < self.minimum_measurement_confidence <= 1.0:
            raise ValueError("verification confidence must be in (0, 1]")
        if not self.allowed_strategies:
            raise ValueError("verification strategy allow-list cannot be empty")
        if len(self.allowed_strategies) != len(set(self.allowed_strategies)):
            raise ValueError("verification strategy allow-list must not contain duplicates")


def build_v0_verification_policy() -> VerificationPolicy:
    """Return the first 8C policy; values remain configurable and traceable."""

    return VerificationPolicy(
        policy_id="verification_policy_v0",
        policy_version="2026-08-28-8c",
        measurement_tolerance=0.01,
        target_gap_tolerance=0.04,
        minimum_measurement_confidence=0.80,
        # The first implementation has a local observer and a developer
        # review route. External/hybrid entries are reserved for a later
        # consented strategy adapter and are intentionally not auto-enabled.
        allowed_strategies=(
            VerificationStrategy.LOCAL_GEOMETRY,
            VerificationStrategy.MANUAL_VISUAL_REVIEW,
        ),
    )


@dataclass(frozen=True)
class ExecutionPolicy:
    """V0 mechanics for a single explicitly confirmed execution.

    This is an operational policy rather than a sixth/ seventh business
    contract.  It captures the product decisions frozen for Checkpoint 8B:
    a short-lived confirmation, session-only result bytes, and no automatic
    retries.  Values remain versioned so a later product decision can change
    them without changing Pydantic field types.
    """

    policy_id: str
    policy_version: str
    consent_policy_version: str
    confirmation_ttl_minutes: int
    result_memory_ttl_minutes: int
    automatic_retry_enabled: bool
    max_attempts_per_confirmed_plan: int


def build_v0_execution_policy() -> ExecutionPolicy:
    """Return the Checkpoint 8B policy frozen on 2026-08-28."""

    return ExecutionPolicy(
        policy_id="execution_v0",
        policy_version="2026-08-28-8b",
        consent_policy_version="execution-consent-v0.1",
        confirmation_ttl_minutes=10,
        # The browser session is the primary deletion boundary.  This value is
        # a maximum in-memory lifetime for the opaque result reference, not a
        # promise to persist an image for ten minutes.
        result_memory_ttl_minutes=10,
        automatic_retry_enabled=False,
        max_attempts_per_confirmed_plan=1,
    )


@dataclass(frozen=True)
class FollowupMappingPolicy:
    """Conservative, versioned increments for a confirmed plan family.

    Tencent receives a *new result image* on every round, so its 0--100
    request parameters are per-call strengths rather than a durable slider
    state.  The values below therefore describe the next small action on the
    current result image.  They are not an acceptance score or a claim that a
    fixed value will produce a fixed visual change.
    """

    policy_id: str
    policy_version: str
    minimum_increment: int
    maximum_increment: int
    target_gap_tolerance: float

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_increment <= self.maximum_increment <= 100:
            raise ValueError("follow-up increments must stay inside Tencent's 0..100 range")
        if not 0.0 < self.target_gap_tolerance < 1.0:
            raise ValueError("follow-up target gap tolerance must be in (0, 1)")

    def increment_for_remaining_gap(self, gap: float) -> int:
        """Map a remaining verified gap to a bounded next-call strength.

        This deliberately stays smaller than the first-round mapper: a second
        result-changing call is allowed only after the first moved in the
        correct direction, so the safe default is a small, inspectable step.
        """

        if gap <= self.target_gap_tolerance:
            return 0
        # Gaps at or above 12% get the upper bounded increment.  Between the
        # current target-evidence line and 12%, interpolate deterministically.
        ceiling_gap = 0.12
        if gap >= ceiling_gap:
            return self.maximum_increment
        progress = (gap - self.target_gap_tolerance) / (ceiling_gap - self.target_gap_tolerance)
        value = self.minimum_increment + progress * (
            self.maximum_increment - self.minimum_increment
        )
        return max(self.minimum_increment, min(self.maximum_increment, round(value)))


def build_v0_followup_mapping_policy() -> FollowupMappingPolicy:
    """Return the first bounded plan-family replan policy for 8C-2."""

    return FollowupMappingPolicy(
        policy_id="followup_mapping_v0",
        policy_version="2026-08-28-8c2",
        minimum_increment=2,
        maximum_increment=6,
        target_gap_tolerance=0.04,
    )


def build_v0_data_retention_policy() -> DataRetentionPolicySnapshot:
    """Return the frozen six-month anchor retention and deletion promise."""

    return DataRetentionPolicySnapshot(
        policy_id="anchor-retention-v0",
        policy_version="2026-08-27",
        anchor_retention_days=183,
        reminder_days_before_expiry=[30, 7],
        primary_delete_sla_hours=24,
        backup_delete_sla_days=7,
    )
