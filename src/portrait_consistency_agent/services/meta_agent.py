"""Candidate-safe Meta-Agent tool selection for the Tencent Web integration.

This module is intentionally a proposal layer, not an executor.  It joins a
validated request, the local Provider Registry and an optional RAG advisory,
then emits a deterministic ``ToolProposal``.  The proposal is useful to the
main Agent because it explains which tool is relevant and what still blocks
it, while the existing state machine remains the only component that can
authorise a chargeable or image-bearing call.

The implementation is deliberately deterministic for the first integration
slice.  A future LLM may fill a structured proposal, but its output must pass
the same allow-list and admission checks before it can affect routing.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from portrait_consistency_agent.core.contracts import EditableFeature, SafeId
from portrait_consistency_agent.core.rag_contracts import RagAdvisoryDecision, RagAdvisoryRoute
from portrait_consistency_agent.services.tool_registry import ToolDescriptor, ToolRegistry


class MetaAgentStage(str, Enum):
    """Places where the bounded Meta-Agent may propose a tool."""

    PLAN_EDIT = "plan_edit"
    EXECUTE = "execute"
    VERIFICATION_STRATEGY = "verification_strategy"
    FAILURE_ROUTING = "failure_routing"


class MetaAgentRoute(str, Enum):
    """Non-authorising outcomes of a tool selection attempt."""

    BASELINE_SELECTED = "baseline_selected"
    CANDIDATE_PROPOSAL_ONLY = "candidate_proposal_only"
    MANUAL_SUGGESTION = "manual_suggestion"
    BLOCKED = "blocked"


class ToolProposal(BaseModel):
    """A redacted, replayable proposal; it can never be a ProviderRun."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    proposal_id: SafeId
    stage: MetaAgentStage
    requested_features: list[str] = Field(default_factory=list, max_length=16)
    selected_tool_id: SafeId | None = None
    selected_operation: str | None = Field(default=None, min_length=1, max_length=128)
    selected_card_id: SafeId | None = None
    selected_card_version: str | None = Field(default=None, min_length=1, max_length=96)
    route: MetaAgentRoute
    # This literal is the key security boundary.  The next layer must still
    # apply confirmation, consent, budget and idempotency policy.
    execution_authorized: Literal[False] = False
    fallback_tool_id: SafeId | None = None
    required_checks: list[str] = Field(default_factory=list, max_length=32)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    reason_codes: list[str] = Field(min_length=1, max_length=24)
    trace: list[dict[str, object]] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_proposal_boundary(self) -> ToolProposal:
        if self.route == MetaAgentRoute.BASELINE_SELECTED and self.selected_tool_id is None:
            raise ValueError("baseline_selected proposals require a selected tool")
        if self.route == MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY:
            if self.selected_tool_id is None:
                raise ValueError("candidate proposals require a selected candidate tool")
            if "candidate_not_admitted" not in self.reason_codes:
                raise ValueError("candidate proposals must state candidate_not_admitted")
        if self.selected_tool_id is None and self.selected_operation is not None:
            raise ValueError("an operation cannot be selected without a tool")
        return self


class MetaAgentToolSelector:
    """Choose from the registry without granting an external side effect."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry.default()

    def propose(
        self,
        *,
        stage: MetaAgentStage | str,
        requested_features: Iterable[str | EditableFeature],
        rag_advice: RagAdvisoryDecision | None = None,
        preferred_tool_id: str | None = None,
        outbound_allowed: bool = True,
        proposal_id: str | None = None,
    ) -> ToolProposal:
        """Return one bounded proposal and a complete decision trace.

        ``preferred_tool_id`` represents a user/product route preference, not
        an instruction to bypass admission.  Candidate Web tools can be
        surfaced with a baseline fallback, but are never marked executable.
        An unknown feature, RAG conflict/miss without a baseline, or an
        outbound restriction produces a fail-closed result.
        """

        stage_value = MetaAgentStage(stage)
        features = _normalise_features(requested_features)
        proposal_key = proposal_id or f"tool_proposal_{uuid.uuid4().hex[:16]}"
        descriptors = self.registry.tools
        trace: list[dict[str, object]] = [
            {
                "step": "provider_discovered",
                "stage": stage_value.value,
                "tool_ids": [tool.tool_id for tool in descriptors],
                "candidate_tools": [
                    tool.tool_id for tool in descriptors if not tool.execution_allowed
                ],
                "image_bytes_read": False,
                "network_called": False,
            }
        ]

        if rag_advice is not None:
            trace.append(
                {
                    "step": "rag_advisory_consumed",
                    "advice_id": rag_advice.advice_id,
                    "retrieval_route": rag_advice.retrieval_route.value,
                    "advisory_route": rag_advice.advisory_route.value,
                    "direct_evidence_refs": rag_advice.direct_evidence_refs,
                    "reference_information_refs": rag_advice.reference_information_refs,
                    "conflict_information_refs": rag_advice.conflict_information_refs,
                    "execution_authorized_by_rag": False,
                }
            )
            if rag_advice.advisory_route in {
                RagAdvisoryRoute.CONFLICT_BLOCKED,
                RagAdvisoryRoute.UNKNOWN_STOPPED,
            }:
                # A separately approved baseline can still be used only when
                # the RAG contract explicitly says it may continue.
                if not rag_advice.existing_baseline_may_continue:
                    return self._proposal(
                        proposal_id=proposal_key,
                        stage=stage_value,
                        features=features,
                        route=MetaAgentRoute.BLOCKED,
                        reason_codes=(
                            "rag_advisory_blocked",
                            "execution_not_authorized",
                        ),
                        evidence_refs=_evidence_refs(rag_advice),
                        required_checks=("manual_review",),
                        trace=trace,
                    )

        baseline = self.registry.get("tencent_beautify_pic")
        preferred = self.registry.get(preferred_tool_id) if preferred_tool_id else None
        trace.append(
            {
                "step": "provider_admission_checked",
                "preferred_tool_id": preferred_tool_id,
                "baseline_execution_allowed": baseline.execution_allowed if baseline else False,
                "candidate_review_status": {
                    tool.tool_id: tool.review_status
                    for tool in descriptors
                    if not tool.execution_allowed
                },
                "outbound_allowed": outbound_allowed,
            }
        )

        if preferred_tool_id and preferred is None:
            return self._proposal(
                proposal_id=proposal_key,
                stage=stage_value,
                features=features,
                route=MetaAgentRoute.BLOCKED,
                reason_codes=("preferred_tool_not_registered", "execution_not_authorized"),
                required_checks=("manual_review",),
                trace=trace,
            )

        # A caller explicitly asking for Web gets an honest candidate proposal
        # when the Card covers the requested features.  It may include the
        # reviewed REST baseline as a fallback, but does not execute either
        # tool here.
        if preferred is not None and preferred.tool_id == "tencent_effect_web":
            if not _covers(preferred, features):
                return self._proposal(
                    proposal_id=proposal_key,
                    stage=stage_value,
                    features=features,
                    route=MetaAgentRoute.MANUAL_SUGGESTION,
                    reason_codes=("candidate_does_not_cover_requested_features",),
                    evidence_refs=(preferred.source_ref,),
                    required_checks=("manual_feature_mapping_review",),
                    trace=trace,
                )
            fallback_id = (
                baseline.tool_id
                if baseline is not None
                and baseline.execution_allowed
                and _covers(baseline, features)
                else None
            )
            reasons = ["candidate_not_admitted", "execution_not_authorized"]
            if not outbound_allowed:
                reasons.append("outbound_policy_not_approved")
            if fallback_id:
                reasons.append("reviewed_baseline_available")
            trace.append(
                {
                    "step": "tool_proposal",
                    "route": MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY.value,
                    "selected_tool_id": preferred.tool_id,
                    "fallback_tool_id": fallback_id,
                    "execution_authorized": False,
                    "reason_codes": reasons,
                }
            )
            return self._proposal(
                proposal_id=proposal_key,
                stage=stage_value,
                features=features,
                selected=preferred,
                fallback_tool_id=fallback_id,
                route=MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY,
                reason_codes=tuple(reasons),
                evidence_refs=(preferred.source_ref,),
                required_checks=preferred.required_checks,
                trace=trace,
            )

        # If no preferred route was supplied, or the caller preferred the
        # baseline, choose only a reviewed tool that covers the whole request.
        if baseline is not None and baseline.execution_allowed and _covers(baseline, features):
            trace.append(
                {
                    "step": "tool_proposal",
                    "route": MetaAgentRoute.BASELINE_SELECTED.value,
                    "selected_tool_id": baseline.tool_id,
                    "execution_authorized": False,
                    "reason_codes": ["reviewed_baseline", "execution_not_authorized"],
                }
            )
            return self._proposal(
                proposal_id=proposal_key,
                stage=stage_value,
                features=features,
                selected=baseline,
                route=MetaAgentRoute.BASELINE_SELECTED,
                reason_codes=("reviewed_baseline", "execution_not_authorized"),
                evidence_refs=(baseline.source_ref,),
                required_checks=baseline.required_checks,
                trace=trace,
            )

        candidate = next(
            (
                tool
                for tool in descriptors
                if not tool.execution_allowed and _covers(tool, features)
            ),
            None,
        )
        if candidate is not None:
            trace.append(
                {
                    "step": "tool_proposal",
                    "route": MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY.value,
                    "selected_tool_id": candidate.tool_id,
                    "execution_authorized": False,
                    "reason_codes": ["candidate_not_admitted", "execution_not_authorized"],
                }
            )
            return self._proposal(
                proposal_id=proposal_key,
                stage=stage_value,
                features=features,
                selected=candidate,
                route=MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY,
                reason_codes=("candidate_not_admitted", "execution_not_authorized"),
                evidence_refs=(candidate.source_ref,),
                required_checks=candidate.required_checks,
                trace=trace,
            )

        return self._proposal(
            proposal_id=proposal_key,
            stage=stage_value,
            features=features,
            route=MetaAgentRoute.MANUAL_SUGGESTION,
            reason_codes=("requested_capability_not_registered", "manual_suggestion_only"),
            required_checks=("manual_feature_mapping_review",),
            trace=trace,
        )

    @staticmethod
    def _proposal(
        *,
        proposal_id: str,
        stage: MetaAgentStage,
        features: list[str],
        route: MetaAgentRoute,
        reason_codes: tuple[str, ...],
        trace: list[dict[str, object]],
        selected: ToolDescriptor | None = None,
        fallback_tool_id: str | None = None,
        required_checks: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
    ) -> ToolProposal:
        if fallback_tool_id:
            trace.append(
                {
                    "step": "fallback_selected",
                    "fallback_tool_id": fallback_tool_id,
                    "reason": "candidate_or_route_not_admitted",
                }
            )
        trace.append(
            {
                "step": "proposal_finalized",
                "proposal_id": proposal_id,
                "route": route.value,
                "execution_authorized": False,
                "provider_run_created": False,
                "external_call_made": False,
            }
        )
        return ToolProposal(
            proposal_id=proposal_id,
            stage=stage,
            requested_features=features,
            selected_tool_id=selected.tool_id if selected else None,
            selected_operation=selected.operation if selected else None,
            selected_card_id=selected.card_id if selected else None,
            selected_card_version=selected.card_version if selected else None,
            route=route,
            fallback_tool_id=fallback_tool_id,
            required_checks=list(dict.fromkeys(required_checks)),
            evidence_refs=list(dict.fromkeys(evidence_refs)),
            reason_codes=list(dict.fromkeys(reason_codes)),
            trace=trace,
        )


def _normalise_features(values: Iterable[str | EditableFeature]) -> list[str]:
    result: list[str] = []
    for value in values:
        feature = value.value if isinstance(value, EditableFeature) else str(value).strip()
        if not feature:
            raise ValueError("requested feature names must not be empty")
        if feature not in result:
            result.append(feature)
    if len(result) > 16:
        raise ValueError("at most 16 requested features may be proposed")
    return result


def _covers(tool: ToolDescriptor, features: list[str]) -> bool:
    return set(features) <= set(tool.available_features)


def _evidence_refs(advice: RagAdvisoryDecision) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            [
                *advice.direct_evidence_refs,
                *advice.reference_information_refs,
                *advice.conflict_information_refs,
            ]
        )
    )
