"""The small vertical slice for Checkpoint 6.

This service composes three already-separated responsibilities: local quality
analysis, Tencent content/subject evidence, and Profile v0 persistence.  It is
intentionally not an Agent or state machine yet; the later orchestration layer
will call these deterministic operations and decide which operation is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portrait_consistency_agent.core.contracts import (
    ContentSafetyStatus,
    PhotoQualityResult,
    PhotoRole,
    ReferenceProfile,
    SubjectAnchorMetadata,
)
from portrait_consistency_agent.services.photo_quality import (
    PhotoObservation,
    analyze_photo_bytes,
    to_photo_quality_result,
)
from portrait_consistency_agent.services.reference_profile import build_reference_profile
from portrait_consistency_agent.services.tencent_safety import ContentSafetyDecision
from portrait_consistency_agent.services.tencent_subject import (
    SubjectMatchDecision,
    SubjectMatchPolicy,
    TencentCompareFaceResponse,
    build_subject_match_decision,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore


class SubjectComparator(Protocol):
    def compare_base64(
        self,
        image_a: bytes,
        image_b: bytes,
        *,
        policy: SubjectMatchPolicy,
    ) -> TencentCompareFaceResponse: ...


@dataclass(frozen=True)
class ReferencePreparation:
    observation: PhotoObservation
    quality_result: PhotoQualityResult


@dataclass(frozen=True)
class ProfileLockResult:
    preparation: ReferencePreparation
    profile: ReferenceProfile


@dataclass(frozen=True)
class TargetValidationResult:
    reference_observation: PhotoObservation
    target_observation: PhotoObservation
    subject_decision: SubjectMatchDecision | None
    quality_result: PhotoQualityResult | None


class Checkpoint6Service:
    """Coordinate quality, evidence, and Profile v0 without hidden side effects."""

    def __init__(
        self,
        *,
        store: LocalTraceStore | None = None,
        subject_client: SubjectComparator | None = None,
    ) -> None:
        self.store = store
        self.subject_client = subject_client

    def prepare_reference(
        self,
        image_bytes: bytes,
        *,
        session_id: str,
        photo_id: str,
        quality_result_id: str,
        safety_decision: ContentSafetyDecision | None,
    ) -> ReferencePreparation:
        observation = analyze_photo_bytes(
            image_bytes,
            photo_id=photo_id,
            photo_role=PhotoRole.REFERENCE,
        )
        quality_result = to_photo_quality_result(
            observation,
            session_id=session_id,
            quality_result_id=quality_result_id,
            content_safety_status=(
                safety_decision.status
                if safety_decision is not None
                else ContentSafetyStatus.NOT_EVALUATED
            ),
            content_safety_evidence=(
                safety_decision.evidence if safety_decision is not None else None
            ),
        )
        if self.store is not None:
            self.store.save_photo_quality_result(quality_result)
        return ReferencePreparation(observation=observation, quality_result=quality_result)

    def lock_profile(
        self,
        preparation: ReferencePreparation,
        *,
        user_id: str,
        profile_id: str,
        version: int,
        feature_snapshot_ref: str,
        subject_anchor: SubjectAnchorMetadata | None = None,
        allow_quality_warning: bool = False,
    ) -> ProfileLockResult:
        profile = build_reference_profile(
            preparation.observation,
            preparation.quality_result,
            user_id=user_id,
            profile_id=profile_id,
            version=version,
            feature_snapshot_ref=feature_snapshot_ref,
            subject_anchor=subject_anchor,
            allow_quality_warning=allow_quality_warning,
        )
        if self.store is not None:
            self.store.save_reference_profile(profile)
            self.store.record_event(
                preparation.quality_result.session_id,
                "reference_profile_locked",
                {
                    "profile_id": profile.profile_id,
                    "profile_version": profile.version,
                    "profile_status": profile.status,
                    "feature_count": len(profile.normalized_features),
                    "source_photo_sha256": preparation.observation.photo_sha256,
                },
            )
        return ProfileLockResult(preparation=preparation, profile=profile)

    def validate_target_current_session(
        self,
        reference_bytes: bytes,
        target_bytes: bytes,
        *,
        session_id: str,
        target_photo_id: str,
        quality_result_id: str,
        safety_decision: ContentSafetyDecision | None,
        receipt_ref: str,
        subject_policy: SubjectMatchPolicy | None = None,
    ) -> TargetValidationResult:
        """Run local gates, then CompareFace only after safety/face preflight passes."""

        reference_observation = analyze_photo_bytes(
            reference_bytes,
            photo_id="reference_current_session",
            photo_role=PhotoRole.REFERENCE,
        )
        target_observation = analyze_photo_bytes(
            target_bytes,
            photo_id=target_photo_id,
            photo_role=PhotoRole.TARGET,
        )
        if safety_decision is None or safety_decision.status != ContentSafetyStatus.PASSED:
            return TargetValidationResult(
                reference_observation=reference_observation,
                target_observation=target_observation,
                subject_decision=None,
                quality_result=None,
            )
        if reference_observation.face_count != 1 or target_observation.face_count != 1:
            return TargetValidationResult(
                reference_observation=reference_observation,
                target_observation=target_observation,
                subject_decision=None,
                quality_result=None,
            )
        if self.subject_client is None:
            raise RuntimeError("A SubjectComparator is required for current-session matching")
        policy = subject_policy or SubjectMatchPolicy.v0()
        response = self.subject_client.compare_base64(
            reference_bytes,
            target_bytes,
            policy=policy,
        )
        subject_decision = build_subject_match_decision(
            response,
            receipt_ref=receipt_ref,
            policy=policy,
        )
        quality_result = to_photo_quality_result(
            target_observation,
            session_id=session_id,
            quality_result_id=quality_result_id,
            subject_match_status=subject_decision.status,
            subject_match_evidence=subject_decision.evidence,
            content_safety_status=safety_decision.status,
            content_safety_evidence=safety_decision.evidence,
        )
        if self.store is not None:
            self.store.save_photo_quality_result(quality_result)
            self.store.record_event(
                session_id,
                "subject_match_decision_created",
                {
                    "photo_id": target_photo_id,
                    "status": subject_decision.status,
                    "reason_code": subject_decision.reason_code,
                    "provider": subject_decision.evidence.provider,
                    "provider_request_id": subject_decision.evidence.provider_request_id,
                    "raw_score": subject_decision.evidence.raw_score,
                },
            )
        return TargetValidationResult(
            reference_observation=reference_observation,
            target_observation=target_observation,
            subject_decision=subject_decision,
            quality_result=quality_result,
        )
