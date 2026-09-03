"""Versioned, candidate-safe registry for portrait editing tools.

The registry is the small control-plane seam between Provider Cards and the
Meta-Agent.  A Provider Card describes what a vendor claims or what the
project has verified; the registry turns that description into a typed,
read-only catalogue.  It does *not* hold credentials, image bytes, a signed
payload, or a ProviderRun, and loading it has no network side effect.

There are two deliberately different states in the default catalogue:

* ``tencent_beautify_pic`` is the reviewed REST baseline and may be selected
  for the existing execution flow (the existing state machine still performs
  confirmation and policy checks).
* ``tencent_effect_web`` is executable only after the E3 Card is promoted with
  the explicit ``private_demo_beta`` scope.  A candidate Card remains visible
  for explanation but is never authorised by this registry.  Promotion does
  not mean public production readiness.

Keeping this distinction in one place prevents an LLM or RAG result from
turning a documented/candidate capability into a hidden side effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from portrait_consistency_agent.core.contracts import EditableFeature, SafeId
from portrait_consistency_agent.services.provider_cards import (
    load_tencent_beautify_card,
    load_tencent_effect_web_card,
)


class ToolDescriptor(BaseModel):
    """A safe projection of one Provider Card for routing decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    tool_id: SafeId
    provider: str = Field(min_length=1, max_length=96)
    operation: str = Field(min_length=1, max_length=128)
    card_id: SafeId
    card_version: str = Field(min_length=1, max_length=96)
    review_status: str = Field(min_length=1, max_length=32)
    integration_kind: str = Field(min_length=1, max_length=64)
    promotion_scope: str | None = Field(default=None, max_length=64)
    available_features: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    execution_allowed: bool = False
    required_checks: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    reason_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    source_ref: str = Field(min_length=1, max_length=256)


@dataclass(frozen=True)
class ToolRegistry:
    """Read-only catalogue used by the bounded Meta-Agent proposal layer."""

    tools: tuple[ToolDescriptor, ...]

    @classmethod
    def default(cls) -> ToolRegistry:
        """Load the reviewed baseline and the separately gated Web candidate."""

        baseline = load_tencent_beautify_card()
        web = load_tencent_effect_web_card()
        return cls(
            tools=(
                _descriptor_from_beautify(baseline),
                _descriptor_from_web(web),
            )
        )

    def get(self, tool_id: str) -> ToolDescriptor | None:
        """Return one descriptor by opaque tool id without guessing aliases."""

        return next((tool for tool in self.tools if tool.tool_id == tool_id), None)

    def candidates_for(
        self, requested_features: list[str] | tuple[str, ...]
    ) -> tuple[ToolDescriptor, ...]:
        """Return tools whose Cards mention every requested feature.

        Candidate tools are included intentionally: the Meta-Agent may need
        to explain that a candidate is relevant but not executable.  Callers
        must inspect ``execution_allowed`` rather than treating this result as
        permission.
        """

        requested = set(_feature_code(value) for value in requested_features)
        if not requested:
            return self.tools
        return tuple(tool for tool in self.tools if requested <= set(tool.available_features))

    def executable_for(
        self, requested_features: list[str] | tuple[str, ...]
    ) -> tuple[ToolDescriptor, ...]:
        """Return only independently reviewed tools allowed by the registry."""

        return tuple(
            tool for tool in self.candidates_for(requested_features) if tool.execution_allowed
        )


def _feature_code(value: str | EditableFeature) -> str:
    return value.value if isinstance(value, EditableFeature) else str(value)


def _descriptor_from_beautify(card: dict[str, Any]) -> ToolDescriptor:
    parameters = card.get("parameters", {})
    features = tuple(
        sorted(
            str(item.get("feature"))
            for item in parameters.values()
            if isinstance(item, dict) and item.get("feature")
        )
    )
    return ToolDescriptor(
        tool_id="tencent_beautify_pic",
        provider=str(card["provider"]),
        operation=str(card["operation"]),
        card_id=str(card["card_id"]),
        card_version=str(card["card_version"]),
        review_status=str(card["review_status"]),
        integration_kind="rest_api",
        available_features=features,
        execution_allowed=True,
        required_checks=("provider_card_verified", "confirmation_scope", "budget", "consent"),
        reason_codes=("reviewed_baseline",),
        source_ref="data/provider_cards/tencent_beautify_pic.json",
    )


def _descriptor_from_web(card: dict[str, Any]) -> ToolDescriptor:
    parameters = card.get("parameters", [])
    features = tuple(
        sorted(
            str(item.get("feature_code"))
            for item in parameters
            if isinstance(item, dict) and item.get("feature_code")
        )
    )
    gate = card.get("permission_budget_gate")
    required_checks = (
        tuple(str(item) for item in gate.get("required_checks", []))
        if isinstance(gate, dict)
        else ()
    )
    review_status = str(card["review_status"])
    promotion_scope = card.get("promotion_scope")
    promotion_scope_value = str(promotion_scope) if promotion_scope is not None else None
    is_private_demo_verified = (
        review_status == "verified" and promotion_scope_value == "private_demo_beta"
    )
    if is_private_demo_verified:
        reason_codes = ("verified_private_demo_scope",)
    else:
        reason_codes = ("candidate_not_admitted", "browser_receipt_only_smoke")
    return ToolDescriptor(
        tool_id="tencent_effect_web",
        provider=str(card["provider"]),
        operation=str(card["operation"]),
        card_id=str(card["card_id"]),
        card_version=str(card["card_version"]),
        review_status=review_status,
        integration_kind=str(card["integration_kind"]),
        promotion_scope=promotion_scope_value,
        available_features=features,
        execution_allowed=is_private_demo_verified,
        required_checks=required_checks,
        reason_codes=reason_codes,
        source_ref="data/provider_cards/tencent_effect_web.json",
    )
