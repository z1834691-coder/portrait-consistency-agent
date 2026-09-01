"""Local Streamlit shell for the first traceable demo interaction."""

from __future__ import annotations

# The ``src/`` path is bootstrapped before package imports so this file can
# run both from a local install and directly as a Streamlit Cloud entrypoint.
# ruff: noqa: E402
import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import streamlit as st

# The local project uses a ``src/`` layout. ``uv`` installs the package during
# development, while Community Cloud executes the checked-out entrypoint
# directly. Add the source directory explicitly so the same entrypoint works
# in both environments without relying on an editable install.
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if SOURCE_ROOT.is_dir() and str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from portrait_consistency_agent.agent.intent_adapter import (
    DeepSeekIntentAdapter,
    IntentClarification,
    IntentParseReceipt,
    IntentParsingContext,
)
from portrait_consistency_agent.core.contracts import (
    ContentSafetyStatus,
    EditPlan,
    FeedbackEvidenceStrength,
    FeedbackSignal,
    IntentFrame,
    InteractionOutcome,
    InteractionStage,
    PhotoQualityResult,
    PhotoRole,
    ProductEvent,
    ProductEventType,
    ProviderRun,
    ReferenceProfile,
    ReferenceSource,
    VerificationDecision,
    VerificationResult,
)
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.checkpoint6 import Checkpoint6Service
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan
from portrait_consistency_agent.services.execution import (
    cancel_execution_plan,
    confirm_execution,
    execute_confirmed_plan,
    execute_followup_plan,
)
from portrait_consistency_agent.services.local_rag_models import (
    BgeEmbeddingBackend,
    BgeRerankerBackend,
)
from portrait_consistency_agent.services.photo_quality import analyze_photo_bytes
from portrait_consistency_agent.services.plan_family import (
    capture_explicit_feedback,
    propose_followup_plan,
)
from portrait_consistency_agent.services.rag_advisory import (
    RagAdvisoryService,
    build_plan_advisory_query,
    build_verification_strategy_advisory_query,
)
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.services.tencent_beautify import TencentBeautifyClient
from portrait_consistency_agent.services.tencent_safety import (
    ContentSafetyCredentialsMissingError,
    ContentSafetyDecision,
    TencentContentSafetyApiError,
    TencentImageModerationClient,
    build_content_safety_decision,
    safe_error_message,
    safe_error_trace,
)
from portrait_consistency_agent.services.tencent_subject import (
    SubjectMatchCredentialsMissingError,
    TencentCompareFaceClient,
    TencentSubjectApiError,
)
from portrait_consistency_agent.services.verification import verify_result
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore
from portrait_consistency_agent.storage.local_store import LocalTraceStore


@st.cache_resource
def get_store(database_path: Path, trace_path: Path) -> LocalTraceStore:
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    return store


@st.cache_resource
def get_rag_advisory(
    knowledge_path: Path,
    vector_path: Path,
    model_cache_path: Path,
    embedding_model: str,
    embedding_revision: str,
    reranker_model: str,
    reranker_revision: str,
) -> RagAdvisoryService:
    """Create a local-cache-only RAG adviser; it cannot call a photo Provider."""

    knowledge_store = LocalKnowledgeStore(knowledge_path)
    knowledge_store.initialize()
    seed_reviewed_provider_knowledge(knowledge_store)
    retriever = RagP0BHybridRetriever(
        store=knowledge_store,
        dense_index=LocalDenseIndex(vector_path),
        embedding_backend=BgeEmbeddingBackend(
            model_id=embedding_model,
            requested_revision=embedding_revision,
            cache_path=model_cache_path,
            allow_model_download=False,
        ),
        reranker_backend=BgeRerankerBackend(
            model_id=reranker_model,
            requested_revision=reranker_revision,
            cache_path=model_cache_path,
            allow_model_download=False,
        ),
    )
    return RagAdvisoryService(store=knowledge_store, retriever=retriever)


def _rag_advisory_for(settings: AppSettings) -> RagAdvisoryService:
    """Resolve only the configured local knowledge store and model cache."""

    return get_rag_advisory(
        PROJECT_ROOT / settings.knowledge_database_path,
        PROJECT_ROOT / settings.rag_vector_database_path,
        PROJECT_ROOT / settings.rag_model_cache_path,
        settings.rag_embedding_model,
        settings.rag_embedding_revision,
        settings.rag_reranker_model,
        settings.rag_reranker_revision,
    )


def upload_metadata(upload: Any) -> dict[str, object]:
    """Create an in-memory, non-identifying upload audit projection."""

    content = upload.getvalue()
    return {
        "image_sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "mime_type": upload.type or "unknown",
    }


def _photo_id(upload: Any, prefix: str) -> str:
    digest = hashlib.sha256(upload.getvalue()).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _subject_user_projection(result: dict[str, object]) -> dict[str, object]:
    """Keep provider raw score and threshold internals out of the page."""

    evidence = result.get("evidence")
    safe_evidence: dict[str, object] = {}
    if isinstance(evidence, dict):
        for key in (
            "provider",
            "operation",
            "model_version",
            "threshold_policy_version",
            "provider_request_id",
            "evaluated_at",
        ):
            if key in evidence:
                safe_evidence[key] = evidence[key]
    return {
        "subject_match_status": result.get("subject_match_status"),
        "reason_code": result.get("reason_code"),
        "evidence_summary": safe_evidence,
        "user_visible_score": False,
    }


def _intent_user_projection(intent: IntentFrame) -> dict[str, object]:
    """Show structured intent without hashes or opaque authorization references."""

    projection = intent.model_dump(mode="json")
    projection.pop("user_text_sha256", None)
    projection.pop("confirmation_ref", None)
    scope = projection.get("confirmation_scope")
    if isinstance(scope, dict):
        projection["confirmation_scope"] = {
            "status": intent.confirmation_status.value,
            "target_count": len(scope.get("target_refs", [])),
            "allowed_features": scope.get("allowed_features", []),
            "max_provider_rounds": scope.get("max_provider_rounds"),
            "subject_match_uncertain_acknowledged": scope.get(
                "subject_match_uncertain_acknowledged", False
            ),
            "whitening_allowed": scope.get("whitening_allowed"),
            "smoothing_allowed": scope.get("smoothing_allowed"),
            "expires_at": scope.get("expires_at"),
        }
    return projection


def _provider_run_user_projection(run: ProviderRun) -> dict[str, object]:
    """Show a factual provider receipt without artifact paths or consent refs."""

    projection: dict[str, object] = {
        "status": run.status.value,
        "provider": run.provider,
        "operation": run.operation,
        "provider_request_id": run.provider_request_id,
        "request_params": run.request_params.model_dump(mode="json"),
        "total_latency_ms": run.total_latency_ms,
        "result_retention": "仅当前会话内存" if run.result_artifact_ref else "无结果图",
        "result_expires_at": (
            run.artifact_lifecycle.expires_at.isoformat() if run.artifact_lifecycle else None
        ),
        "automatic_retry": False,
    }
    if run.error is not None:
        projection["error"] = {
            "phase": run.error.phase.value,
            "category": run.error.category.value,
            "provider_code": run.error.provider_code,
            "safe_message": run.error.safe_message,
            "system_will_retry": run.error.retryable,
        }
    return projection


def _clear_checkpoint8b_session_state() -> None:
    """Forget memory-only result bytes when an upstream input changes."""

    for key in (
        "cp8b_execution_result",
        "cp8b_result_image_bytes",
        "cp8b_result_expires_at",
        "cp8b_provider_run",
        "cp8b_execution_intent",
        "cp8b_current_plan",
        "cp8b_plan_family_id",
        "cp8b_previous_verification",
        "cp8b_last_known_good_artifact_ref",
        "cp8b_result_artifacts",
        "cp8b_last_plan_id",
        "cp8b_cancelled_plan_id",
        "cp8c_verification_result",
        "cp8c_verification_model",
        "cp8c_followup_plan_result",
        "cp8c_followup_auto_attempted_plan_id",
        "cp8c_followup_auto_execution_result",
        "cp8c_auto_verify_pending_plan_id",
        "cp8c_feedback",
        "cp8c_family_user_closed",
    ):
        st.session_state.pop(key, None)


def _parse_receipt_user_projection(receipt: IntentParseReceipt) -> dict[str, object]:
    """A user-visible, factual explanation of which parser path was used."""

    projection = receipt.trace_projection()
    projection.pop("text_redaction_categories", None)
    return projection


def _previous_intent_from_session() -> IntentFrame | None:
    payload = st.session_state.get("latest_intent")
    if not isinstance(payload, dict):
        return None
    try:
        return IntentFrame.model_validate(payload)
    except ValueError:
        return None


def _previous_verification_from_session() -> VerificationResult | None:
    """Return the immediate family receipt used for round-to-round checks."""

    payload = st.session_state.get("cp8b_previous_verification")
    if not isinstance(payload, dict):
        return None
    try:
        return VerificationResult.model_validate(payload)
    except ValueError:
        return None


def _previous_verification_id() -> str | None:
    previous = _previous_verification_from_session()
    return previous.verification_id if previous is not None else None


def _previous_no_improvement_streak() -> int:
    previous = _previous_verification_from_session()
    return previous.no_improvement_streak if previous is not None else 0


def _previous_cumulative_improvement() -> bool | None:
    previous = _previous_verification_from_session()
    return previous.cumulative_improvement if previous is not None else None


def render_checkpoint6(
    *,
    reference_upload: Any,
    target_upload: Any,
    session_id: str,
    anonymous_user_id: str,
    settings: AppSettings,
    store: LocalTraceStore,
) -> None:
    """Render the quality/safety/Profile/subject vertical slice with explicit actions."""

    st.subheader("检查点 6：质量门、同人门与母版 Profile v0")
    st.caption(
        "本地质量门只在内存分析；腾讯内容安全和 CompareFace 只有在你勾选同意并点击按钮后，"
        "才会发送照片。"
    )
    if reference_upload is None:
        st.info("先上传候选母版，才能运行检查点 6。")
        return

    reference_bytes = reference_upload.getvalue()
    reference_id = _photo_id(reference_upload, "reference")
    if st.session_state.get("cp6_reference_hash") not in {
        None,
        hashlib.sha256(reference_bytes).hexdigest(),
    }:
        _clear_checkpoint8b_session_state()
        st.session_state.pop("cp6_profile", None)
        st.session_state.pop("cp6_subject_result", None)
        st.session_state.pop("cp6_target_quality_result", None)
        st.session_state.pop("cp6_subject_uncertain_ack", None)
        st.session_state.pop("cp8a_plan_result", None)
        st.session_state.pop("cp6_reference_safety_ack", None)
        st.session_state.pop("cp6_reference_warning_ack", None)
    st.session_state.cp6_reference_hash = hashlib.sha256(reference_bytes).hexdigest()
    reference_observation = analyze_photo_bytes(
        reference_bytes,
        photo_id=reference_id,
        photo_role=PhotoRole.REFERENCE,
    )
    st.markdown("**母版：本地质量门结果**")
    st.json(reference_observation.user_projection())

    safety_cache: dict[str, ContentSafetyDecision] = st.session_state.setdefault(
        "cp6_safety_cache", {}
    )
    reference_hash = reference_observation.photo_sha256
    reference_safety = safety_cache.get(reference_hash)
    reference_ack = st.checkbox(
        "我确认将候选母版发送给腾讯 ImageModeration 做内容安全检查",
        key="cp6_reference_safety_ack",
    )
    if st.button("执行母版内容安全检查", key="cp6_reference_safety_button"):
        if not reference_ack:
            st.warning("请先确认照片发送范围；未确认不会调用腾讯。")
        else:
            try:
                response = TencentImageModerationClient(settings).moderate_base64(reference_bytes)
                reference_safety = build_content_safety_decision(
                    response,
                    receipt_ref=f"safety_{reference_hash[:16]}",
                )
                safety_cache[reference_hash] = reference_safety
                store.record_event(
                    session_id,
                    "reference_content_safety_decision",
                    {
                        "photo_sha256": reference_hash,
                        "status": reference_safety.status,
                        "reason_code": reference_safety.reason_code,
                        "provider_request_id": reference_safety.evidence.provider_request_id,
                    },
                )
                st.success(f"内容安全结果：{reference_safety.status.value}")
            except (
                ContentSafetyCredentialsMissingError,
                TencentContentSafetyApiError,
                ValueError,
            ) as exc:
                store.record_event(
                    session_id,
                    "reference_content_safety_failed",
                    {"photo_sha256": reference_hash, **safe_error_trace(exc)},
                )
                st.error(safe_error_message(exc))
    if reference_safety is not None:
        st.write(f"已保存的安全结果：`{reference_safety.status.value}`")

    warning_ack = False
    if (
        reference_observation.quality_confidence < 0.8
        or reference_observation.editability_confidence < 0.8
    ):
        warning_ack = st.checkbox(
            "我知道这张母版存在质量/可编辑性警告，仍要把它作为长期母版",
            key="cp6_reference_warning_ack",
        )
    if st.button("锁定 ReferenceProfile v0", key="cp6_lock_profile_button", type="primary"):
        if "cp6_profile" in st.session_state:
            st.info("本会话已经锁定一个 Profile；更换母版请创建新的本地会话。")
        elif reference_safety is None or reference_safety.status != ContentSafetyStatus.PASSED:
            st.warning("母版必须先通过内容安全检查；Review/Block 不允许锁定。")
        elif (
            min(
                reference_observation.quality_confidence,
                reference_observation.editability_confidence,
            )
            < 0.8
            and not warning_ack
        ):
            st.warning("质量门给出中等置信度，请明确确认警告后再锁定。")
        else:
            service = Checkpoint6Service(store=store)
            try:
                preparation = service.prepare_reference(
                    reference_bytes,
                    session_id=session_id,
                    photo_id=reference_id,
                    quality_result_id=f"quality_{reference_hash[:16]}",
                    safety_decision=reference_safety,
                )
                profile_result = service.lock_profile(
                    preparation,
                    user_id=anonymous_user_id,
                    profile_id=f"profile_{reference_hash[:16]}",
                    version=1,
                    feature_snapshot_ref=f"snapshot_{reference_hash[:16]}",
                    allow_quality_warning=warning_ack,
                )
                st.session_state.cp6_profile = profile_result.profile.model_dump(mode="json")
                store.record_product_event(
                    ProductEvent(
                        event_id=f"product_event_{uuid.uuid4().hex}",
                        session_id=session_id,
                        anonymous_user_id=anonymous_user_id,
                        event_type=ProductEventType.PROFILE_CREATED,
                        stage=InteractionStage.PROFILE,
                        evidence_strength=FeedbackEvidenceStrength.UNKNOWN,
                        related_contract_ref=profile_result.profile.profile_id,
                    )
                )
                st.success("已锁定母版 Profile v0（只保存归一化几何，不保存原图）。")
            except ValueError as exc:
                st.error(str(exc))
    if "cp6_profile" in st.session_state:
        st.markdown("**当前会话的母版 Profile v0（脱敏结构化字段）**")
        st.json(st.session_state.cp6_profile)

    if target_upload is None:
        st.info("再上传目标照片，才能运行当前会话同人比对。")
        return

    target_bytes = target_upload.getvalue()
    target_id = _photo_id(target_upload, "target")
    if st.session_state.get("cp6_target_hash") not in {
        None,
        hashlib.sha256(target_bytes).hexdigest(),
    }:
        _clear_checkpoint8b_session_state()
        st.session_state.pop("cp6_subject_result", None)
        st.session_state.pop("cp6_target_quality_result", None)
        st.session_state.pop("cp6_target_external_ack", None)
        st.session_state.pop("cp6_subject_uncertain_ack", None)
    st.session_state.cp6_target_hash = hashlib.sha256(target_bytes).hexdigest()
    target_observation = analyze_photo_bytes(
        target_bytes,
        photo_id=target_id,
        photo_role=PhotoRole.TARGET,
    )
    st.markdown("**目标照：本地质量门结果**")
    st.json(target_observation.user_projection())
    target_hash = target_observation.photo_sha256
    target_safety = safety_cache.get(target_hash)
    target_ack = st.checkbox(
        "我确认将目标照发送给腾讯 ImageModeration 和当前会话 CompareFace",
        key="cp6_target_external_ack",
    )
    if st.button("执行目标照内容安全检查", key="cp6_target_safety_button"):
        if not target_ack:
            st.warning("请先确认照片发送范围；未确认不会调用腾讯。")
        else:
            try:
                response = TencentImageModerationClient(settings).moderate_base64(target_bytes)
                target_safety = build_content_safety_decision(
                    response,
                    receipt_ref=f"safety_{target_hash[:16]}",
                )
                safety_cache[target_hash] = target_safety
                store.record_event(
                    session_id,
                    "target_content_safety_decision",
                    {
                        "photo_sha256": target_hash,
                        "status": target_safety.status,
                        "reason_code": target_safety.reason_code,
                        "provider_request_id": target_safety.evidence.provider_request_id,
                    },
                )
                st.success(f"目标照内容安全结果：{target_safety.status.value}")
            except (
                ContentSafetyCredentialsMissingError,
                TencentContentSafetyApiError,
                ValueError,
            ) as exc:
                store.record_event(
                    session_id,
                    "target_content_safety_failed",
                    {"photo_sha256": target_hash, **safe_error_trace(exc)},
                )
                st.error(safe_error_message(exc))
    if target_safety is not None:
        st.write(f"已保存的目标照安全结果：`{target_safety.status.value}`")

    if st.button("执行当前会话同人比对（CompareFace）", key="cp6_subject_button"):
        if "cp6_subject_result" in st.session_state:
            st.info("本会话已经完成一次同人比对；如需重新比较请创建新的本地会话。")
        elif not target_ack:
            st.warning("请先确认目标照会发送给腾讯；未确认不会调用 CompareFace。")
        elif reference_safety is None or reference_safety.status != ContentSafetyStatus.PASSED:
            st.warning("母版必须先通过内容安全检查。")
        elif target_safety is None or target_safety.status != ContentSafetyStatus.PASSED:
            st.warning("目标照必须先通过内容安全检查。")
        elif target_observation.face_count != 1 or reference_observation.face_count != 1:
            st.warning("当前 V0 只把单脸照片发送到 CompareFace；多脸请先裁剪。")
        else:
            service = Checkpoint6Service(
                store=store,
                subject_client=TencentCompareFaceClient(settings),
            )
            try:
                result = service.validate_target_current_session(
                    reference_bytes,
                    target_bytes,
                    session_id=session_id,
                    target_photo_id=target_id,
                    quality_result_id=f"quality_{target_hash[:16]}",
                    safety_decision=target_safety,
                    receipt_ref=f"subject_{target_hash[:16]}",
                )
                if result.subject_decision is not None:
                    subject_result = {
                        "subject_match_status": result.subject_decision.status.value,
                        "reason_code": result.subject_decision.reason_code,
                        "evidence": result.subject_decision.evidence.model_dump(mode="json"),
                    }
                    st.session_state.cp6_subject_result = _subject_user_projection(subject_result)
                    if result.quality_result is not None:
                        st.session_state.cp6_target_quality_result = (
                            result.quality_result.model_dump(mode="json")
                        )
                    st.json(st.session_state.cp6_subject_result)
            except (SubjectMatchCredentialsMissingError, TencentSubjectApiError, ValueError) as exc:
                store.record_event(
                    session_id,
                    "subject_match_failed",
                    {"photo_sha256": target_hash, "error_type": type(exc).__name__},
                )
                st.error(str(exc))
    if "cp6_subject_result" in st.session_state:
        st.markdown("**当前会话同人门结果（供应商原始分不展示）**")
        st.json(st.session_state.cp6_subject_result)


def render_checkpoint8a(
    *,
    target_upload: Any,
    session_id: str,
    settings: AppSettings,
    store: LocalTraceStore,
) -> None:
    """Expose the read-only diagnosis/plan module with its evidence chain."""

    st.subheader("检查点 8A：差异诊断与 EditPlan 草案（不执行修图）")
    st.caption(
        "本步骤只比较归一化几何并生成待确认方案；不会调用腾讯 BeautifyPic，"
        "参数由确定性规则计算，不由 LLM 猜测。"
    )
    profile_payload = st.session_state.get("cp6_profile")
    quality_payload = st.session_state.get("cp6_target_quality_result")
    intent_payload = st.session_state.get("latest_intent")
    if profile_payload is None or quality_payload is None or intent_payload is None:
        st.info("请先完成母版 Profile、目标照安全/同人门和本轮 IntentFrame。")
        return
    if target_upload is None:
        st.info("当前没有目标照文件，无法生成诊断。")
        return
    try:
        profile = ReferenceProfile.model_validate(profile_payload)
        quality_result = PhotoQualityResult.model_validate(quality_payload)
        intent = IntentFrame.model_validate(intent_payload)
        target_observation = analyze_photo_bytes(
            target_upload.getvalue(),
            photo_id=_photo_id(target_upload, "target"),
            photo_role=PhotoRole.TARGET,
        )
    except ValueError as exc:
        st.error(f"8A 输入合同无法验证：{exc}")
        store.record_event(
            session_id,
            "edit_plan_input_validation_failed",
            {"error_type": type(exc).__name__},
        )
        return

    subject_match_uncertain_acknowledged = False
    if quality_result.subject_match_status.value == "uncertain":
        st.warning(
            "腾讯当前无法稳定确认目标照与母版是同一人。若这是你的本人照片，且你有权编辑，"
            "可以确认后继续；系统会记录这次确认，但不会把不确定结果升级成‘同人已证实’。"
        )
        subject_match_uncertain_acknowledged = st.checkbox(
            "我确认目标照是本人，且我有权编辑；接受同人判断不确定可能带来的偏差",
            key="cp6_subject_uncertain_ack",
        )

    if st.button("生成差异诊断与计划草案", key="cp8a_plan_button", type="primary"):
        try:
            if subject_match_uncertain_acknowledged:
                store.record_event(
                    session_id,
                    "subject_match_uncertain_acknowledged",
                    {
                        "photo_id": quality_result.photo_id,
                        "quality_result_id": quality_result.quality_result_id,
                        "policy_version": (
                            quality_result.subject_match_evidence.threshold_policy_version
                            if quality_result.subject_match_evidence is not None
                            else None
                        ),
                    },
                )
            rag_run = _rag_advisory_for(settings).advise(
                query=build_plan_advisory_query(
                    query_id=f"rag_plan_{uuid.uuid4().hex}",
                    intent=intent,
                    profile=profile,
                    face_count=target_observation.face_count,
                ),
                # The only baseline allowed after a RAG miss is the already
                # configured, separately gated BeautifyPic Provider Card.
                existing_baseline_available=True,
            )
            store.record_event(
                session_id,
                "rag_plan_advisory_completed",
                {
                    "advice_id": rag_run.decision.advice_id,
                    "advisory_route": rag_run.decision.advisory_route.value,
                    "retrieval_route": rag_run.decision.retrieval_route.value,
                    "direct_evidence_refs": rag_run.decision.direct_evidence_refs,
                    "conflict_information_refs": rag_run.decision.conflict_information_refs,
                    "execution_authorized_by_rag": False,
                    "bad_case_ref": rag_run.decision.bad_case_ref,
                },
            )
            result = diagnose_and_plan(
                profile=profile,
                target_observation=target_observation,
                quality_result=quality_result,
                intent=intent,
                store=store,
                rag_advice=rag_run.decision,
                subject_match_uncertain_acknowledged=subject_match_uncertain_acknowledged,
            )
            _clear_checkpoint8b_session_state()
            st.session_state.cp8a_plan_result = {
                "route": result.route,
                "reason_codes": list(result.reason_codes),
                "user_message": result.user_message,
                "differences": [
                    item.model_dump(mode="json") for item in result.feature_differences
                ],
                "trace": list(result.trace),
                "plan": result.plan.model_dump(mode="json") if result.plan is not None else None,
                "rag_advisory": {
                    "decision": rag_run.decision.model_dump(mode="json"),
                    "trace": list(rag_run.trace),
                },
            }
        except (ValueError, RuntimeError) as exc:
            store.record_event(
                session_id,
                "edit_plan_generation_failed",
                {"photo_id": target_observation.photo_id, "error_type": type(exc).__name__},
            )
            st.error(f"无法生成计划：{exc}")

    payload = st.session_state.get("cp8a_plan_result")
    if not isinstance(payload, dict):
        return
    st.markdown("**用户可读结论**")
    st.write(payload.get("user_message"))
    rag_advisory = payload.get("rag_advisory")
    if isinstance(rag_advisory, dict):
        decision = rag_advisory.get("decision")
        if isinstance(decision, dict):
            with st.expander("查看 RAG 工具知识依据（只提议，不授权执行）"):
                st.json(
                    {
                        "advisory_route": decision.get("advisory_route"),
                        "direct_evidence_refs": decision.get("direct_evidence_refs"),
                        "reference_information_refs": decision.get("reference_information_refs"),
                        "conflict_information_refs": decision.get("conflict_information_refs"),
                        "execution_authorized": decision.get("execution_authorized"),
                        "bad_case_ref": decision.get("bad_case_ref"),
                    }
                )
    differences = payload.get("differences")
    if isinstance(differences, list) and differences:
        display_rows = []
        for item in differences:
            if not isinstance(item, dict):
                continue
            gap = item.get("normalized_gap")
            display_rows.append(
                {
                    "测量项": item.get("feature_code"),
                    "母版值（归一化）": item.get("reference_value"),
                    "目标照值（归一化）": item.get("observed_value"),
                    "局部差异": (
                        f"{float(gap) * 100:.1f}%" if isinstance(gap, (int, float)) else "不可测量"
                    ),
                    "是否可进入计划": "是" if item.get("editable") else "否",
                    "原因": "、".join(item.get("reason_codes", [])),
                }
            )
        st.dataframe(display_rows, use_container_width=True, hide_index=True)
    plan = payload.get("plan")
    if isinstance(plan, dict):
        st.markdown("**计划草案（尚未执行）**")
        st.json(
            {
                "status": plan.get("status"),
                "requires_confirmation": plan.get("requires_confirmation"),
                "provider_absolute_params": plan.get("provider_absolute_params"),
                "executable_changes": plan.get("executable_changes"),
                "suggestion_only_changes": plan.get("suggestion_only_changes"),
                "mapping_policy_version": plan.get("mapping_policy_version"),
            }
        )
    trace = payload.get("trace")
    if isinstance(trace, list):
        with st.expander("查看完整 8A Trace（脱敏）"):
            st.json(trace)


def render_checkpoint8b(
    *,
    target_upload: Any,
    session_id: str,
    anonymous_user_id: str,
    settings: AppSettings,
    store: LocalTraceStore,
) -> None:
    """Render the bounded confirmation and one-attempt execution checkpoint."""

    st.subheader("检查点 8B：确认后调用腾讯修图（尚未复测）")
    st.caption(
        "8A 已经计算好参数；这里不让 LLM 再看图或改参数。"
        "只有你勾选同意并点击确认后，系统才会把目标照发送给腾讯 BeautifyPic。"
    )
    plan_payload = st.session_state.get("cp8a_plan_result")
    profile_payload = st.session_state.get("cp6_profile")
    quality_payload = st.session_state.get("cp6_target_quality_result")
    intent_payload = st.session_state.get("latest_intent")
    if (
        not isinstance(plan_payload, dict)
        or not isinstance(profile_payload, dict)
        or not isinstance(quality_payload, dict)
        or not isinstance(intent_payload, dict)
        or target_upload is None
    ):
        st.info("请先完成 8A 的待确认计划，才能进入执行确认。")
        return
    raw_plan = plan_payload.get("plan")
    if not isinstance(raw_plan, dict):
        st.info("当前没有可执行的 EditPlan；系统不会调用腾讯。")
        return
    try:
        plan = EditPlan.model_validate(raw_plan)
        profile = ReferenceProfile.model_validate(profile_payload)
        quality_result = PhotoQualityResult.model_validate(quality_payload)
        source_intent = IntentFrame.model_validate(intent_payload)
    except ValueError as exc:
        st.error(f"8B 输入合同无法验证：{exc}")
        store.record_event(
            session_id,
            "execution_input_validation_failed",
            {"error_type": type(exc).__name__},
        )
        return
    if not plan.executable_changes:
        st.info("这份计划没有当前腾讯可执行的改动；保留诊断或手动建议即可，无需调用腾讯。")
        return

    existing_result = st.session_state.get("cp8b_execution_result")
    if isinstance(existing_result, dict):
        _render_checkpoint8b_result(existing_result)
        return
    if st.session_state.get("cp8b_cancelled_plan_id") == plan.plan_id:
        st.info("你已取消这份计划；腾讯没有收到修图请求。重新生成方案后可再次决定。")
        return

    st.markdown("**本次确认将包含什么**")
    st.write(
        "仅当前目标照；仅 8A 已列出的可执行部位；最多三轮的受限计划族。"
        "本模块只执行第一轮；结果图不写入数据库或 Trace，只在当前会话内临时展示。"
    )
    st.json(
        {
            "待执行参数": plan.provider_absolute_params.model_dump(mode="json"),
            "可执行部位": [item.feature.value for item in plan.executable_changes],
            "不会执行": [item.feature.value for item in plan.suggestion_only_changes],
            "自动重试": False,
            "复测状态": "尚未开始（属于下一检查点）",
        }
    )
    acknowledgement = st.checkbox(
        "我确认仅将当前目标照发送给腾讯云 BeautifyPic，按上方参数处理；"
        "若复测允许继续，上一轮结果图可能在本次受限计划族内作为下一轮输入，"
        "同一照片、部位、用途、预算和轮次范围内可由 Agent 自动续跑；"
        "结果仅在本次浏览器会话中临时展示，我可以主动下载。",
        key=f"cp8b_execution_ack_{plan.plan_id}",
    )
    action_left, action_right = st.columns(2)
    with action_left:
        execute_clicked = st.button(
            "确认并调用腾讯 BeautifyPic",
            key=f"cp8b_execute_{plan.plan_id}",
            type="primary",
        )
    with action_right:
        cancel_clicked = st.button(
            "取消本次执行",
            key=f"cp8b_cancel_{plan.plan_id}",
        )
    if cancel_clicked:
        try:
            cancelled_plan = cancel_execution_plan(plan)
            store.save_edit_plan(cancelled_plan)
            store.record_event(
                session_id,
                "execution_cancelled_by_user",
                {"plan_id": plan.plan_id, "plan_revision": cancelled_plan.revision},
            )
            st.session_state.cp8b_cancelled_plan_id = plan.plan_id
            st.success("已取消：腾讯没有收到修图请求。")
        except ValueError as exc:
            st.error(f"无法取消当前方案：{exc}")
        return
    if not execute_clicked:
        return
    if not acknowledgement:
        st.warning("请先勾选照片发送与临时结果保留说明；未勾选时不会调用腾讯。")
        return

    try:
        confirmation = confirm_execution(
            source_intent=source_intent,
            proposed_plan=plan,
            next_turn=store.next_intent_turn(session_id),
            subject_match_uncertain_acknowledged=bool(
                st.session_state.get("cp6_subject_uncertain_ack", False)
            ),
        )
        store.save_intent_frame(confirmation.execution_intent)
        store.save_edit_plan(confirmation.confirmed_plan)
        # 8C must verify against this confirmed revision, not the older
        # proposed plan saved by 8A. ProviderRun receipts are bound to the
        # confirmed revision and following that lineage prevents a subtle
        # plan/run mismatch in the next checkpoint.
        st.session_state.cp8b_execution_intent = confirmation.execution_intent.model_dump(
            mode="json"
        )
        st.session_state.cp8b_current_plan = confirmation.confirmed_plan.model_dump(mode="json")
        st.session_state.cp8b_plan_family_id = f"family_{confirmation.confirmed_plan.plan_id}"
        store.record_product_event(
            ProductEvent(
                event_id=f"product_event_{uuid.uuid4().hex}",
                session_id=session_id,
                anonymous_user_id=anonymous_user_id,
                event_type=ProductEventType.EXECUTION_CONFIRMED,
                stage=InteractionStage.CONFIRMATION,
                evidence_strength=FeedbackEvidenceStrength.STRONG_INTENT,
                outcome=InteractionOutcome.CONTINUED,
                related_contract_ref=confirmation.confirmed_plan.plan_id,
                reason_codes=["user_confirmed_execution"],
            )
        )
        store.record_event(
            session_id,
            "execution_confirmation_trace",
            {"plan_id": confirmation.confirmed_plan.plan_id, "trace": confirmation.trace},
        )
        st.info(confirmation.user_confirmation_copy)
        with st.spinner("已获得本次授权，正在调用腾讯 BeautifyPic…"):
            result = execute_confirmed_plan(
                confirmed_plan=confirmation.confirmed_plan,
                execution_intent=confirmation.execution_intent,
                target_image_bytes=target_upload.getvalue(),
                target_photo_id=_photo_id(target_upload, "target"),
                profile=profile,
                quality_result=quality_result,
                client=TencentBeautifyClient(settings),
                store=store,
            )
    except (RuntimeError, ValueError) as exc:
        store.record_event(
            session_id,
            "execution_confirmation_or_runtime_failed",
            {"plan_id": plan.plan_id, "error_type": type(exc).__name__},
        )
        st.error(f"本次没有完成可审计执行：{exc}")
        return

    result_payload: dict[str, object] = {
        "route": result.route,
        "user_message": result.user_message,
        "final_plan_status": result.final_plan.status.value,
        "provider_run": (
            _provider_run_user_projection(result.provider_run) if result.provider_run else None
        ),
        "trace": list(result.trace),
    }
    st.session_state.cp8b_execution_result = result_payload
    st.session_state.cp8b_last_plan_id = plan.plan_id
    if result.provider_run is not None:
        # The full factual receipt is kept in session state for the next
        # checkpoint; the persisted store still receives only its redacted
        # projection.  It contains no image bytes.
        st.session_state.cp8b_provider_run = result.provider_run.model_dump(mode="json")
    if result.result_image_bytes is not None and result.provider_run is not None:
        st.session_state.cp8b_result_image_bytes = result.result_image_bytes
        artifacts = dict(st.session_state.get("cp8b_result_artifacts", {}))
        if result.provider_run.result_artifact_ref is not None:
            artifacts[result.provider_run.result_artifact_ref] = result.result_image_bytes
        st.session_state.cp8b_result_artifacts = artifacts
        if result.provider_run.artifact_lifecycle is not None:
            st.session_state.cp8b_result_expires_at = (
                result.provider_run.artifact_lifecycle.expires_at.isoformat()
            )
    _render_checkpoint8b_result(result_payload)


@st.fragment(run_every=timedelta(seconds=30))
def _render_checkpoint8b_result(payload: dict[str, object]) -> None:
    """Render a session-only 8B result without reading any persisted image."""

    route = payload.get("route")
    if route == "succeeded":
        st.success(str(payload.get("user_message")))
    elif route == "blocked":
        st.warning(str(payload.get("user_message")))
    else:
        st.error(str(payload.get("user_message")))
    raw_expiry = st.session_state.get("cp8b_result_expires_at")
    result_bytes = st.session_state.get("cp8b_result_image_bytes")
    expired = False
    if isinstance(raw_expiry, str):
        try:
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(raw_expiry)
        except ValueError:
            expired = True
    if expired:
        st.session_state.pop("cp8b_result_image_bytes", None)
        st.session_state.pop("cp8b_result_artifacts", None)
        result_bytes = None
        st.info("临时结果图已过期并从当前会话内存移除；不会重新调用腾讯。")
    if isinstance(result_bytes, bytes):
        st.image(result_bytes, caption="腾讯返回的临时结果图：尚未经过 8C 复测")
        st.download_button(
            "主动下载临时结果图",
            data=result_bytes,
            file_name="portrait-consistency-result.jpg",
            mime="image/jpeg",
            key="cp8b_result_download",
        )
    elif route == "succeeded":
        st.info(
            "该会话内的结果图已不在内存中；ProviderRun 回执仍可证明曾发生调用，但系统不会自动重发。"
        )
    provider_run = payload.get("provider_run")
    if isinstance(provider_run, dict):
        st.markdown("**真实工具回执摘要**")
        st.json(provider_run)
    trace = payload.get("trace")
    if isinstance(trace, list):
        with st.expander("查看完整 8B Trace（脱敏）"):
            st.json(trace)


def _render_checkpoint8c_result(payload: dict[str, object]) -> None:
    """Render structured post-edit evidence; never reloads result bytes."""

    st.markdown("**8C 用户可读复测结论**")
    st.write(payload.get("user_message"))
    verification_payload = payload.get("verification")
    if isinstance(verification_payload, dict):
        st.json(
            {
                "总体趋势": verification_payload.get("overall_trend"),
                "下一步": verification_payload.get("decision"),
                "停止原因": verification_payload.get("stop_reason"),
                "是否有结构化目标证据": verification_payload.get("target_evidence_sufficient"),
                "是否验证了妆面/肤色/背景保持": verification_payload.get(
                    "preserved_attributes_verified"
                ),
                "验证策略": verification_payload.get("verification_strategy"),
            }
        )
        comparisons = verification_payload.get("feature_comparisons")
        if isinstance(comparisons, list) and comparisons:
            rows = []
            for item in comparisons:
                if isinstance(item, dict):
                    rows.append(
                        {
                            "特征": item.get("feature_code"),
                            "修前差异": item.get("before_gap"),
                            "修后差异": item.get("after_gap"),
                            "趋势": item.get("trend"),
                            "测量可靠性": item.get("measurement_confidence"),
                        }
                    )
            st.dataframe(rows, use_container_width=True, hide_index=True)
        if (
            verification_payload.get("decision") == VerificationDecision.STOP.value
            and verification_payload.get("stop_reason") == "result_worsened"
        ):
            fallback_ref = verification_payload.get("last_known_good_artifact_ref")
            artifacts = st.session_state.get("cp8b_result_artifacts", {})
            fallback_bytes = artifacts.get(fallback_ref) if isinstance(artifacts, dict) else None
            if isinstance(fallback_bytes, bytes):
                st.warning("本轮变差，下面保留的是上一张已知朝目标改善的临时结果图。")
                st.image(fallback_bytes, caption="已知良好结果（未重新调用腾讯）")
            else:
                st.warning("本轮变差；上一张临时结果图已不在当前会话内存中，无法展示回退预览。")
    observation = payload.get("observation")
    if isinstance(observation, dict):
        with st.expander("查看修后观察事实（不含原图和人脸坐标）"):
            st.json(observation)
    proposal = payload.get("strategy_proposal")
    if isinstance(proposal, dict):
        with st.expander("查看策略选择证据"):
            st.json(proposal)
    trace = payload.get("trace")
    if isinstance(trace, list):
        with st.expander("查看完整 8C Trace（脱敏）"):
            st.json(trace)


def _render_checkpoint8c2(
    *,
    session_id: str,
    anonymous_user_id: str,
    settings: AppSettings,
    store: LocalTraceStore,
) -> None:
    """Render bounded continuation and final feedback for an 8C receipt.

    The first 8B plan is the only point that asks the user to authorize an
    external edit.  When 8C proves a cumulative improvement and the next
    child plan remains inside that exact scope, this renderer performs one
    idempotent automatic follow-up call.  A preflight event is written before
    the call, the child plan/run carries parent lineage, and Streamlit state
    prevents a rerun from charging the same child twice.  New scope, provider,
    purpose, budget or consent always fails closed.
    """

    verification_payload = st.session_state.get("cp8c_verification_model")
    plan_payload = st.session_state.get("cp8b_current_plan")
    intent_payload = st.session_state.get("cp8b_execution_intent")
    profile_payload = st.session_state.get("cp6_profile")
    quality_payload = st.session_state.get("cp6_target_quality_result")
    provider_payload = st.session_state.get("cp8b_provider_run")
    result_bytes = st.session_state.get("cp8b_result_image_bytes")
    if not all(
        isinstance(payload, dict)
        for payload in (
            verification_payload,
            plan_payload,
            intent_payload,
            profile_payload,
            quality_payload,
            provider_payload,
        )
    ) or not isinstance(result_bytes, bytes):
        return
    try:
        verification = VerificationResult.model_validate(verification_payload)
        current_plan = EditPlan.model_validate(plan_payload)
        execution_intent = IntentFrame.model_validate(intent_payload)
        profile = ReferenceProfile.model_validate(profile_payload)
        quality_result = PhotoQualityResult.model_validate(quality_payload)
        provider_run = ProviderRun.model_validate(provider_payload)
    except ValueError as exc:
        st.error(f"8C-2 输入合同无法验证：{exc}")
        store.record_event(
            session_id,
            "plan_family_input_validation_failed",
            {"error_type": type(exc).__name__},
        )
        return

    st.markdown("**8C-2：计划族下一轮与反馈**")
    st.caption(
        "点赞/点踩是明确满意度反馈；文字反馈会被记录为文本哈希，不会直接当作修图命令。"
        "如果证据显示仍有正确方向上的改善，系统会在首次同意的范围内自动续跑；"
        "只有达到停止条件、无法继续或失败时，才向你展示最终结果和反馈入口。"
    )

    feedback_payload = st.session_state.get("cp8c_feedback")
    if isinstance(feedback_payload, dict):
        st.info(str(feedback_payload.get("user_message")))
        with st.expander("查看反馈 Trace（不含原话）"):
            st.json(feedback_payload.get("trace"))
    if st.session_state.get("cp8c_family_user_closed", False):
        st.info("本计划族已按你的明确反馈停止；如需继续，请重新表达目标并生成新计划。")
        return

    # A REPLAN is an intermediate machine decision.  Do not ask for a
    # satisfaction button between rounds; the final/blocked result below is
    # where the user can provide explicit feedback.
    if verification.decision != VerificationDecision.REPLAN:
        if not st.session_state.get("cp8c_family_user_closed", False):
            left, right = st.columns(2)
            with left:
                liked = st.button("👍 可以了", key=f"cp8c_like_{verification.verification_id}")
            with right:
                disliked = st.button(
                    "👎 不满意，停止本计划族",
                    key=f"cp8c_dislike_{verification.verification_id}",
                )
            if liked or disliked:
                signal = FeedbackSignal.LIKE if liked else FeedbackSignal.DISLIKE
                captured = capture_explicit_feedback(
                    session_id=session_id,
                    anonymous_user_id=anonymous_user_id,
                    verification=verification,
                    signal=signal,
                    store=store,
                )
                st.session_state.cp8c_feedback = {
                    "feedback": captured.feedback.model_dump(mode="json"),
                    "trace": list(captured.trace),
                    "user_message": captured.user_message,
                }
                st.session_state.cp8c_family_user_closed = True
                st.rerun()

            with st.form(key=f"cp8c_comment_{verification.verification_id}", clear_on_submit=True):
                comment = st.text_area(
                    "补充反馈（可选）",
                    placeholder="例如：脸型可以，但眼睛看起来不自然。原话不写入本地数据库。",
                )
                comment_submitted = st.form_submit_button("保存文字反馈并停止本计划族")
            if comment_submitted:
                if not comment.strip():
                    st.warning("请输入反馈内容，或使用上方点赞/点踩。")
                else:
                    captured = capture_explicit_feedback(
                        session_id=session_id,
                        anonymous_user_id=anonymous_user_id,
                        verification=verification,
                        signal=FeedbackSignal.TEXT_COMMENT,
                        comment_text=comment,
                        store=store,
                    )
                    st.session_state.cp8c_feedback = {
                        "feedback": captured.feedback.model_dump(mode="json"),
                        "trace": list(captured.trace),
                        "user_message": captured.user_message,
                    }
                    # V0 does not infer a new execution scope from free text. The
                    # user can return to the IntentFrame panel to state a new goal.
                    st.session_state.cp8c_family_user_closed = True
                    st.rerun()
        return

    cached_followup = st.session_state.get("cp8c_followup_plan_result")
    if not (
        isinstance(cached_followup, dict)
        and cached_followup.get("previous_verification_id") == verification.verification_id
    ):
        followup = propose_followup_plan(
            previous_plan=current_plan,
            previous_provider_run=provider_run,
            previous_verification=verification,
            execution_intent=execution_intent,
            profile=profile,
            result_image_bytes=result_bytes,
            store=store,
        )
        cached_followup = {
            "previous_verification_id": verification.verification_id,
            "route": followup.route,
            "reason_codes": list(followup.reason_codes),
            "user_message": followup.user_message,
            "plan": followup.plan.model_dump(mode="json") if followup.plan else None,
            "trace": list(followup.trace),
        }
        st.session_state.cp8c_followup_plan_result = cached_followup

    st.write(str(cached_followup.get("user_message")))
    if cached_followup.get("route") != "followup_plan_ready":
        with st.expander("查看下一轮未生成的原因（Trace）"):
            st.json(cached_followup.get("trace"))
        return
    raw_child_plan = cached_followup.get("plan")
    if not isinstance(raw_child_plan, dict):
        st.error("下一轮计划缺少可验证合同；系统不会调用腾讯。")
        return
    try:
        child_plan = EditPlan.model_validate(raw_child_plan)
    except ValueError as exc:
        st.error(f"下一轮 EditPlan 无效：{exc}")
        return
    st.info(
        f"第 {child_plan.iteration} 轮已通过证据前置检查：系统将在首次确认的范围内自动执行。"
        "你不需要逐轮理解或点击滑杆；如果授权、预算、轮次、工具或结果血缘发生变化，"
        "系统会在调用前停止。"
    )
    with st.expander("查看本轮执行事实（不需要操作）"):
        st.json(
            {
                "round": child_plan.iteration,
                "parent_plan_id": child_plan.parent_plan_id,
                "本次输入": "上一轮经过复测的临时结果图",
                "授权范围": "沿用首次确认的照片、部位、用途、预算和轮次",
                "执行方式": "auto_bounded_followup",
                "本次参数（Trace 可追溯）": child_plan.provider_absolute_params.model_dump(
                    mode="json"
                ),
            }
        )

    attempted_plan_id = st.session_state.get("cp8c_followup_auto_attempted_plan_id")
    previous_auto_result = st.session_state.get("cp8c_followup_auto_execution_result")
    if attempted_plan_id == child_plan.plan_id:
        if isinstance(previous_auto_result, dict):
            route = previous_auto_result.get("route")
            if route == "succeeded":
                st.success("本轮自动调用已经完成，正在准备修后复测。")
            else:
                st.error(str(previous_auto_result.get("user_message")))
            with st.expander("查看本轮自动执行 Trace（脱敏）"):
                st.json(previous_auto_result.get("trace"))
        else:
            st.warning("本轮自动调用已经发起但没有可展示的结果；为避免重复扣费，系统不会重试。")
        return

    # Set the sentinel before the network call.  Streamlit reruns can happen
    # after a widget interaction or a browser reconnect; this prevents the
    # same child plan from being charged twice.
    st.session_state.cp8c_followup_auto_attempted_plan_id = child_plan.plan_id
    scope = execution_intent.confirmation_scope
    store.record_event(
        session_id,
        "auto_followup_preflight",
        {
            "plan_id": child_plan.plan_id,
            "parent_plan_id": child_plan.parent_plan_id,
            "iteration": child_plan.iteration,
            "trigger": "agent_bounded_auto_followup",
            "scope_reused": True,
            "confirmation_scope_hash": child_plan.confirmation_scope_hash,
            "scope_expires_at": scope.expires_at.isoformat() if scope else None,
            "result_input_sha256": hashlib.sha256(result_bytes).hexdigest(),
            "user_round_confirmation_required": False,
        },
    )
    try:
        with st.spinner("正在按已确认范围自动执行本轮增量计划…"):
            execution = execute_followup_plan(
                confirmed_plan=child_plan,
                execution_intent=execution_intent,
                result_image_bytes=result_bytes,
                target_photo_id=child_plan.photo_id,
                profile=profile,
                original_quality_result=quality_result,
                previous_provider_run=provider_run,
                previous_verification=verification,
                client=TencentBeautifyClient(settings),
                store=store,
            )
    except (RuntimeError, ValueError) as exc:
        trace = [
            {
                "step": "auto_followup_execution",
                "status": "runtime_failed",
                "execution_trigger": "auto_bounded_followup",
                "plan_id": child_plan.plan_id,
                "error_type": type(exc).__name__,
                "automatic_retry": False,
            }
        ]
        payload = {
            "route": "failed",
            "user_message": f"下一轮没有完成可审计执行：{exc}",
            "trace": trace,
        }
        st.session_state.cp8c_followup_auto_execution_result = payload
        store.record_event(
            session_id,
            "plan_family_execution_runtime_failed",
            {
                "plan_id": child_plan.plan_id,
                "error_type": type(exc).__name__,
                "auto_followup": True,
                "trace": trace,
            },
        )
        st.error(str(payload["user_message"]))
        with st.expander("查看本轮自动执行 Trace（脱敏）"):
            st.json(trace)
        return

    if execution.route != "succeeded" or execution.provider_run is None:
        payload = {
            "route": execution.route,
            "user_message": execution.user_message,
            "provider_run": (
                _provider_run_user_projection(execution.provider_run)
                if execution.provider_run
                else None
            ),
            "trace": list(execution.trace),
        }
        st.session_state.cp8c_followup_auto_execution_result = payload
        st.error(execution.user_message)
        with st.expander("查看本轮自动执行 Trace（脱敏）"):
            st.json(payload["trace"])
        return
    if execution.result_image_bytes is None:
        payload = {
            "route": "failed",
            "user_message": "腾讯回执成功但当前会话没有可验证结果图；系统不会继续或重试。",
            "trace": list(execution.trace),
        }
        st.session_state.cp8c_followup_auto_execution_result = payload
        st.error(str(payload["user_message"]))
        with st.expander("查看本轮自动执行 Trace（脱敏）"):
            st.json(payload["trace"])
        return

    store.record_event(
        session_id,
        "auto_followup_completed",
        {
            "plan_id": child_plan.plan_id,
            "parent_plan_id": child_plan.parent_plan_id,
            "iteration": child_plan.iteration,
            "route": execution.route,
            "provider_request_id": execution.provider_run.provider_request_id,
            "result_artifact_sha256": execution.provider_run.result_artifact_sha256,
            "trigger": "agent_bounded_auto_followup",
            "automatic_retry": False,
        },
    )
    st.session_state.cp8b_current_plan = child_plan.model_dump(mode="json")
    st.session_state.cp8b_provider_run = execution.provider_run.model_dump(mode="json")
    st.session_state.cp8b_result_image_bytes = execution.result_image_bytes
    st.session_state.cp8b_result_expires_at = (
        execution.provider_run.artifact_lifecycle.expires_at.isoformat()
        if execution.provider_run.artifact_lifecycle
        else None
    )
    artifacts = dict(st.session_state.get("cp8b_result_artifacts", {}))
    if execution.provider_run.result_artifact_ref:
        artifacts[execution.provider_run.result_artifact_ref] = execution.result_image_bytes
    st.session_state.cp8b_result_artifacts = artifacts
    st.session_state.cp8b_previous_verification = verification.model_dump(mode="json")
    st.session_state.cp8b_last_known_good_artifact_ref = verification.result_artifact_ref
    st.session_state.cp8b_execution_result = {
        "route": execution.route,
        "user_message": execution.user_message,
        "final_plan_status": execution.final_plan.status.value,
        "provider_run": _provider_run_user_projection(execution.provider_run),
        "trace": list(execution.trace),
    }
    st.session_state.cp8b_last_plan_id = child_plan.plan_id
    # The result of an automatic child call should be verified automatically
    # as the next step; the initial 8C verification remains user-initiated.
    st.session_state.cp8c_auto_verify_pending_plan_id = child_plan.plan_id
    for key in (
        "cp8c_verification_result",
        "cp8c_verification_model",
        "cp8c_followup_plan_result",
        "cp8c_followup_auto_execution_result",
        "cp8c_feedback",
        "cp8c_family_user_closed",
    ):
        st.session_state.pop(key, None)
    st.rerun()


def _run_checkpoint8c_verification(
    *,
    session_id: str,
    plan: EditPlan,
    profile: ReferenceProfile,
    provider_run: ProviderRun,
    result_bytes: bytes,
    settings: AppSettings,
    store: LocalTraceStore,
    automatic: bool,
) -> bool:
    """Observe one result and persist its redacted VerificationResult.

    The first 8C observation is started by the user.  A child plan generated
    inside the already confirmed family sets ``automatic=True`` so the UI can
    continue without another click while still exposing the trigger in Trace.
    """

    trigger = "auto_bounded_followup_verification" if automatic else "user_started_verification"
    if automatic:
        store.record_event(
            session_id,
            "auto_followup_verification_preflight",
            {
                "plan_id": plan.plan_id,
                "provider_run_id": provider_run.run_id,
                "trigger": trigger,
                "result_input_sha256": hashlib.sha256(result_bytes).hexdigest(),
            },
        )
    with st.spinner(
        "正在自动复测刚刚的结果图并决定是否继续…"
        if automatic
        else "正在本机重新观察修后图片并生成复测结论…"
    ):
        try:
            rag_run = _rag_advisory_for(settings).advise(
                query=build_verification_strategy_advisory_query(
                    query_id=f"rag_verify_{uuid.uuid4().hex}",
                    profile_version=profile.version,
                    round_number=plan.iteration,
                ),
                # Local geometry is an existing, no-outbound verification
                # baseline. A RAG miss cannot create an external alternative.
                existing_baseline_available=True,
            )
            store.record_event(
                session_id,
                "rag_verification_advisory_completed",
                {
                    "advice_id": rag_run.decision.advice_id,
                    "advisory_route": rag_run.decision.advisory_route.value,
                    "retrieval_route": rag_run.decision.retrieval_route.value,
                    "direct_evidence_refs": rag_run.decision.direct_evidence_refs,
                    "conflict_information_refs": rag_run.decision.conflict_information_refs,
                    "execution_authorized_by_rag": False,
                    "bad_case_ref": rag_run.decision.bad_case_ref,
                },
            )
            result = verify_result(
                profile=profile,
                plan=plan,
                provider_run=provider_run,
                result_image_bytes=result_bytes,
                prior_no_improvement_streak=_previous_no_improvement_streak(),
                previous_verification_id=_previous_verification_id(),
                previous_cumulative_improvement=_previous_cumulative_improvement(),
                plan_family_id=st.session_state.get(
                    "cp8b_plan_family_id", f"family_{plan.plan_id}"
                ),
                last_known_good_artifact_ref=st.session_state.get(
                    "cp8b_last_known_good_artifact_ref"
                ),
                rag_advice=rag_run.decision,
                store=store,
            )
        except (RuntimeError, ValueError) as exc:
            trace = [
                {
                    "step": "verification_trigger",
                    "trigger": trigger,
                    "status": "failed",
                    "plan_id": plan.plan_id,
                    "error_type": type(exc).__name__,
                }
            ]
            store.record_event(
                session_id,
                "verification_failed",
                {"plan_id": plan.plan_id, "error_type": type(exc).__name__, "trace": trace},
            )
            st.error(f"本次复测没有生成 VerificationResult：{exc}")
            with st.expander("查看复测失败 Trace（脱敏）"):
                st.json(trace)
            return False

    trace = list(result.trace)
    if automatic:
        trace.append(
            {
                "step": "verification_trigger",
                "trigger": trigger,
                "status": "completed",
                "plan_id": plan.plan_id,
                "provider_run_id": provider_run.run_id,
            }
        )
        store.record_event(
            session_id,
            "auto_followup_verification_completed",
            {
                "plan_id": plan.plan_id,
                "provider_run_id": provider_run.run_id,
                "decision": result.verification.decision.value,
                "overall_trend": result.verification.overall_trend.value,
                "trigger": trigger,
            },
        )
    st.session_state.cp8c_verification_result = {
        "user_message": result.user_message,
        "verification": result.verification.model_dump(mode="json"),
        "observation": result.observation.public_projection(),
        "strategy_proposal": result.strategy_proposal.model_dump(mode="json"),
        "rag_advisory": rag_run.decision.model_dump(mode="json"),
        "trace": trace,
    }
    st.session_state.cp8c_verification_model = result.verification.model_dump(mode="json")
    return True


def render_checkpoint8c(
    *,
    session_id: str,
    anonymous_user_id: str,
    settings: AppSettings,
    store: LocalTraceStore,
) -> None:
    """Run the first 8C slice after an 8B result is explicitly available."""

    st.subheader("检查点 8C：修后复测与策略选择（首版）")
    st.caption(
        "首轮复测由你启动；若后续一轮在首次确认范围内自动执行，系统会自动复测并决定是否继续。"
        "所有选择、调用、结果和停止原因都写入脱敏 Trace，不展示一致性分数或接受概率。"
    )
    existing = st.session_state.get("cp8c_verification_result")
    if isinstance(existing, dict):
        _render_checkpoint8c_result(existing)
        _render_checkpoint8c2(
            session_id=session_id,
            anonymous_user_id=anonymous_user_id,
            settings=settings,
            store=store,
        )
        return
    raw_plan = st.session_state.get("cp8b_current_plan")
    raw_profile = st.session_state.get("cp6_profile")
    raw_provider_run = st.session_state.get("cp8b_provider_run")
    result_bytes = st.session_state.get("cp8b_result_image_bytes")
    if not (
        isinstance(raw_plan, dict)
        and isinstance(raw_profile, dict)
        and isinstance(raw_provider_run, dict)
        and isinstance(result_bytes, bytes)
    ):
        st.info("请先在 8B 明确确认并成功拿到腾讯返回图；没有结果图时不会虚构复测。")
        return
    try:
        plan = EditPlan.model_validate(raw_plan)
        profile = ReferenceProfile.model_validate(raw_profile)
        provider_run = ProviderRun.model_validate(raw_provider_run)
    except ValueError as exc:
        st.error(f"8C 输入合同无法验证：{exc}")
        store.record_event(
            session_id,
            "verification_input_validation_failed",
            {"error_type": type(exc).__name__},
        )
        return
    auto_pending_plan_id = st.session_state.get("cp8c_auto_verify_pending_plan_id")
    if auto_pending_plan_id == plan.plan_id:
        st.session_state.pop("cp8c_auto_verify_pending_plan_id", None)
        if _run_checkpoint8c_verification(
            session_id=session_id,
            plan=plan,
            profile=profile,
            provider_run=provider_run,
            result_bytes=result_bytes,
            settings=settings,
            store=store,
            automatic=True,
        ):
            _render_checkpoint8c_result(st.session_state.cp8c_verification_result)
            _render_checkpoint8c2(
                session_id=session_id,
                anonymous_user_id=anonymous_user_id,
                settings=settings,
                store=store,
            )
        return

    if auto_pending_plan_id is not None and auto_pending_plan_id != plan.plan_id:
        # A stale sentinel can only arise after the user changes the upstream
        # photo/session.  Drop it and record why it was not consumed.
        st.session_state.pop("cp8c_auto_verify_pending_plan_id", None)
        store.record_event(
            session_id,
            "auto_followup_verification_stale_sentinel",
            {"pending_plan_id": auto_pending_plan_id, "current_plan_id": plan.plan_id},
        )

    if st.button("开始修后复测（8C）", key=f"cp8c_verify_{plan.plan_id}", type="primary"):
        if not _run_checkpoint8c_verification(
            session_id=session_id,
            plan=plan,
            profile=profile,
            provider_run=provider_run,
            result_bytes=result_bytes,
            settings=settings,
            store=store,
            automatic=False,
        ):
            return
        _render_checkpoint8c_result(st.session_state.cp8c_verification_result)
        _render_checkpoint8c2(
            session_id=session_id,
            anonymous_user_id=anonymous_user_id,
            settings=settings,
            store=store,
        )


def main() -> None:
    st.set_page_config(page_title="母版人像一致性 Agent", page_icon="🪞", layout="wide")
    settings = AppSettings()
    store = get_store(
        PROJECT_ROOT / settings.database_path,
        PROJECT_ROOT / settings.trace_path,
    )

    if "local_session_id" not in st.session_state:
        session = store.create_session()
        st.session_state.local_session_id = session.session_id
        st.session_state.anonymous_user_id = session.anonymous_user_id
    session_id: str = st.session_state.local_session_id
    anonymous_user_id: str = st.session_state.anonymous_user_id

    with st.sidebar:
        st.header("当前原型状态")
        st.caption(f"本地会话：`{session_id}`")
        st.caption("运行环境：Private Demo；本机开发端口为 127.0.0.1:8501")
        st.caption("腾讯 API：首轮需明确同意；受限计划族续跑自动执行且全程可追溯")
        st.caption("LLM：DeepSeek 只解析文字；未勾选/失败时回退本地模板")
        if st.button("创建新的本地会话"):
            session = store.create_session(anonymous_user_id=anonymous_user_id)
            st.session_state.local_session_id = session.session_id
            _clear_checkpoint8b_session_state()
            st.session_state.pop("latest_intent", None)
            st.session_state.pop("latest_intent_summary", None)
            st.session_state.pop("latest_intent_clarification", None)
            st.session_state.pop("latest_intent_receipt", None)
            for key in (
                "cp6_reference_hash",
                "cp6_target_hash",
                "cp6_profile",
                "cp6_subject_result",
                "cp6_target_quality_result",
                "cp6_subject_uncertain_ack",
                "cp8a_plan_result",
                "cp6_safety_cache",
                "cp6_reference_safety_ack",
                "cp6_reference_warning_ack",
                "cp6_target_external_ack",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    st.title("母版人像一致性 Agent")
    st.info(
        "页面现已接入“文字 → IntentFrame → 几何差异 → EditPlan 草案 → 有界确认 → 腾讯修图回执”。"
        "参数规划不由 LLM 猜测；腾讯返回图片后仍需下一检查点复测，当前不会宣称已达到母版一致。"
    )

    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("1. 候选母版（仅内存预览）")
        reference_upload = st.file_uploader(
            "上传一张你有权使用的候选母版",
            type=["png", "jpg", "jpeg"],
            key="reference_upload",
        )
        if reference_upload:
            st.image(reference_upload, caption="本地预览：尚未保存、未上传到外部服务")

    with right_column:
        st.subheader("2. 目标照片（仅内存预览）")
        target_upload = st.file_uploader(
            "上传一张你有权使用的目标照片",
            type=["png", "jpg", "jpeg"],
            key="target_upload",
        )
        if target_upload:
            st.image(target_upload, caption="本地预览：尚未保存、未上传到外部服务")

    render_checkpoint6(
        reference_upload=reference_upload,
        target_upload=target_upload,
        session_id=session_id,
        anonymous_user_id=anonymous_user_id,
        settings=settings,
        store=store,
    )

    st.subheader("3. 用一句话表达你的目标")
    user_text = st.text_area(
        "例如：把这张照片向我的母版靠拢，但保持妆面不变，先给我参数建议。",
        placeholder=(
            "原话只在当前页面内存中使用；写入本地 Trace 的是文本哈希，不是原文。"
            "不要输入姓名、联系方式、证件号或任何密钥。"
        ),
    )
    if settings.has_deepseek_credentials:
        allow_deepseek = st.checkbox(
            "我同意仅将本轮经过脱敏的文字发送给 DeepSeek 做意图理解；"
            "不会发送照片、Base64、人脸向量、主体锚点、密钥或原始 Trace。",
            key="cp7_deepseek_text_ack",
        )
    else:
        allow_deepseek = False
        st.caption("尚未在本机 `.env` 配置 DeepSeek 密钥：本轮会自动使用本地模板 fallback。")

    if st.button("解析并保存本轮 IntentFrame", type="primary"):
        if reference_upload is None or target_upload is None:
            st.warning("请先各上传一张母版和目标照片；文件仍只在当前页面内存中预览。")
        elif not user_text.strip():
            st.warning("请先用一句话说明本轮目标；系统不会把空白文本发送给任何外部服务。")
        else:
            target_metadata = upload_metadata(target_upload)
            previous_intent = _previous_intent_from_session()
            context = IntentParsingContext(
                session_id=session_id,
                turn=store.next_intent_turn(session_id),
                target_refs=[f"photo_{str(target_metadata['image_sha256'])[:16]}"],
                has_locked_profile="cp6_profile" in st.session_state,
                default_reference_source=(
                    ReferenceSource.EXISTING_PROFILE
                    if "cp6_profile" in st.session_state
                    else ReferenceSource.NEW_UPLOAD
                ),
                previous_intent=previous_intent,
            )
            result = DeepSeekIntentAdapter(settings).parse(
                context=context,
                user_text=user_text,
                allow_remote=allow_deepseek,
            )
            store.save_intent_frame(result.intent_frame)
            store.record_event(
                session_id,
                "intent_parser_completed",
                {
                    "reference": upload_metadata(reference_upload),
                    "target": target_metadata,
                    "intent_id": result.intent_frame.intent_id,
                    "clarification_needed": result.clarification.needed,
                    **result.receipt.trace_projection(),
                },
            )
            st.session_state.latest_intent = result.intent_frame.model_dump(mode="json")
            st.session_state.latest_intent_summary = result.user_summary
            st.session_state.latest_intent_clarification = result.clarification.model_dump(
                mode="json"
            )
            st.session_state.latest_intent_receipt = result.receipt.trace_projection()
            if result.intent_frame.parser_mode.value == "llm":
                st.success(
                    "DeepSeek 已完成文本解析并保存 IntentFrame；它没有访问照片，也没有执行修图。"
                )
            elif result.receipt.network_called:
                st.warning(
                    "DeepSeek 文本解析未通过可用性/Schema 校验，已安全回退到本地模板；"
                    "未发送照片，也没有执行修图。"
                )
            else:
                st.info(
                    "本轮使用本地模板 fallback 并已保存 IntentFrame；没有发生 DeepSeek 文本调用。"
                )

    if "latest_intent" in st.session_state:
        st.subheader("4. 当前 IntentFrame（结构化理解，不代表已执行）")
        latest_intent = IntentFrame.model_validate(st.session_state.latest_intent)
        summary = st.session_state.get("latest_intent_summary")
        if isinstance(summary, str) and summary:
            st.write(summary)
        st.json(_intent_user_projection(latest_intent))
        receipt_payload = st.session_state.get("latest_intent_receipt")
        if isinstance(receipt_payload, dict):
            st.caption("本次解析的可审计事实（不包含原话、隐藏思维链或密钥）")
            st.json(receipt_payload)
        clarification_payload = st.session_state.get("latest_intent_clarification")
        if isinstance(clarification_payload, dict):
            clarification = IntentClarification.model_validate(clarification_payload)
            if clarification.needed:
                st.warning(clarification.next_question)
                if clarification.quick_replies:
                    st.caption("可选快捷回复：" + " / ".join(clarification.quick_replies))

    render_checkpoint8a(
        target_upload=target_upload,
        session_id=session_id,
        settings=settings,
        store=store,
    )
    render_checkpoint8b(
        target_upload=target_upload,
        session_id=session_id,
        anonymous_user_id=anonymous_user_id,
        settings=settings,
        store=store,
    )
    render_checkpoint8c(
        session_id=session_id,
        anonymous_user_id=anonymous_user_id,
        settings=settings,
        store=store,
    )

    st.subheader("5. 当前会话 Trace（脱敏）")
    st.json(store.recent_events(session_id))

    st.caption(
        "当前 8B 完成首轮受确认保护的腾讯修图与真实回执；8C 会按逐特征证据复测，"
        "在首次授权范围内自动续跑最多三轮，并在每次调用前后写入脱敏 Trace。"
    )


if __name__ == "__main__":
    main()
