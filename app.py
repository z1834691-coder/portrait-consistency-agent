"""Local Streamlit shell for the first traceable demo interaction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import streamlit as st

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    BatchFailurePolicy,
    ContentSafetyStatus,
    EditableFeature,
    ExecutionPriority,
    FieldSource,
    IntentAction,
    IntentFrame,
    IntentGoal,
    OutputPreference,
    ParserMode,
    PhotoRole,
    PreserveAttribute,
    ReferenceSource,
    Route,
    TargetScope,
)
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.checkpoint6 import Checkpoint6Service
from portrait_consistency_agent.services.photo_quality import analyze_photo_bytes
from portrait_consistency_agent.services.tencent_safety import (
    ContentSafetyCredentialsMissingError,
    ContentSafetyDecision,
    TencentContentSafetyApiError,
    TencentImageModerationClient,
    build_content_safety_decision,
)
from portrait_consistency_agent.services.tencent_subject import (
    SubjectMatchCredentialsMissingError,
    TencentCompareFaceClient,
    TencentSubjectApiError,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore

PROJECT_ROOT = Path(__file__).resolve().parent


@st.cache_resource
def get_store(database_path: Path, trace_path: Path) -> LocalTraceStore:
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    return store


def upload_metadata(upload: Any) -> dict[str, object]:
    """Create an in-memory, non-identifying upload audit projection."""

    content = upload.getvalue()
    return {
        "image_sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "mime_type": upload.type or "unknown",
    }


def build_template_intent(
    session_id: str,
    *,
    turn: int,
    target_ref: str,
    user_text_sha256: str,
) -> IntentFrame:
    """A clearly marked fallback until the LLM intent adapter is implemented."""

    return IntentFrame(
        intent_id=f"intent_{session_id[-12:]}_{turn}",
        session_id=session_id,
        turn=turn,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.PROVIDE_PLAN,
        target_scope=TargetScope.CURRENT_PHOTO,
        reference_source=ReferenceSource.NEW_UPLOAD,
        target_refs=[target_ref],
        output_preferences=[OutputPreference.REPORT, OutputPreference.MANUAL_PARAMETERS],
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        blocked_features=[EditableFeature.SKIN_TONE, EditableFeature.MAKEUP],
        preserve_attributes=[
            PreserveAttribute.SKIN_TONE,
            PreserveAttribute.MAKEUP,
            PreserveAttribute.BACKGROUND,
            PreserveAttribute.BODY,
        ],
        adjustment_mode=AdjustmentMode.BALANCED,
        priority=ExecutionPriority.BALANCED,
        requested_max_rounds=2,
        batch_failure_policy=BatchFailurePolicy.CONTINUE_VALID,
        field_sources={
            "goal": FieldSource.PRODUCT_DEFAULT,
            "route": FieldSource.PRODUCT_DEFAULT,
            "action": FieldSource.PRODUCT_DEFAULT,
            "allowed_features": FieldSource.PRODUCT_DEFAULT,
        },
        slot_confidence={},
        intent_confidence=0.0,
        parser_mode=ParserMode.TEMPLATE_FALLBACK,
        model_provider="template_fallback",
        prompt_version="intent-template-v0",
        user_text_sha256=user_text_sha256,
    )


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


def render_checkpoint6(
    *,
    reference_upload: Any,
    target_upload: Any,
    session_id: str,
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
        st.session_state.pop("cp6_profile", None)
        st.session_state.pop("cp6_subject_result", None)
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
                    {"photo_sha256": reference_hash, "error_type": type(exc).__name__},
                )
                st.error(str(exc))
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
                    user_id="user_demo",
                    profile_id=f"profile_{reference_hash[:16]}",
                    version=1,
                    feature_snapshot_ref=f"snapshot_{reference_hash[:16]}",
                    allow_quality_warning=warning_ack,
                )
                st.session_state.cp6_profile = profile_result.profile.model_dump(mode="json")
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
        st.session_state.pop("cp6_subject_result", None)
        st.session_state.pop("cp6_target_external_ack", None)
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
                    {"photo_sha256": target_hash, "error_type": type(exc).__name__},
                )
                st.error(str(exc))
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


def main() -> None:
    st.set_page_config(page_title="母版人像一致性 Agent", page_icon="🪞", layout="wide")
    settings = AppSettings()
    store = get_store(
        PROJECT_ROOT / settings.database_path,
        PROJECT_ROOT / settings.trace_path,
    )

    if "local_session_id" not in st.session_state:
        st.session_state.local_session_id = store.create_session().session_id
    session_id: str = st.session_state.local_session_id

    with st.sidebar:
        st.header("当前原型状态")
        st.caption(f"本地会话：`{session_id}`")
        st.caption("服务器：仅本机 127.0.0.1:8501")
        st.caption("腾讯 API：只有明确勾选并点击按钮才调用")
        st.caption("LLM：当前使用模板 fallback")
        if st.button("创建新的本地会话"):
            st.session_state.local_session_id = store.create_session().session_id
            st.session_state.pop("latest_intent", None)
            for key in (
                "cp6_reference_hash",
                "cp6_target_hash",
                "cp6_profile",
                "cp6_subject_result",
                "cp6_safety_cache",
                "cp6_reference_safety_ack",
                "cp6_reference_warning_ack",
                "cp6_target_external_ack",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    st.title("母版人像一致性 Agent")
    st.info(
        "检查点 6：页面已接入本地质量门、内容安全/同人 Adapter 和 Profile v0；"
        "参数规划、修图执行、LLM 澄清与修后复测仍在后续检查点。"
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
        settings=settings,
        store=store,
    )

    st.subheader("3. 用一句话表达你的目标")
    user_text = st.text_area(
        "例如：把这张照片向我的母版靠拢，但保持妆面不变，先给我参数建议。",
        placeholder="此检查点只在浏览器内显示原话；写入 trace 的是文本哈希，不是原文。",
    )
    if st.button("保存本轮本地意图（模板模式）", type="primary"):
        if reference_upload is None or target_upload is None:
            st.warning("请先各上传一张母版和目标照片；文件仍只在当前页面内存中预览。")
        else:
            target_metadata = upload_metadata(target_upload)
            user_text_sha256 = hashlib.sha256(user_text.encode("utf-8")).hexdigest()
            intent = build_template_intent(
                session_id,
                turn=store.next_intent_turn(session_id),
                target_ref=f"photo_{str(target_metadata['image_sha256'])[:16]}",
                user_text_sha256=user_text_sha256,
            )
            store.save_intent_frame(intent)
            store.record_event(
                session_id,
                "uploads_previewed_and_template_intent_created",
                {
                    "reference": upload_metadata(reference_upload),
                    "target": target_metadata,
                    "user_text_sha256": user_text_sha256,
                    "network_called": False,
                },
            )
            st.session_state.latest_intent = intent.model_dump(mode="json")
            st.success("已保存模板 IntentFrame 和脱敏 trace；没有调用任何外部 API。")

    if "latest_intent" in st.session_state:
        st.subheader("4. 当前 IntentFrame（模板，不是 LLM 解析结果）")
        st.json(st.session_state.latest_intent)

    st.subheader("5. 当前会话 Trace（脱敏）")
    st.json(store.recent_events(session_id))

    st.caption("下一检查点将接入差异诊断、EditPlan 和受确认保护的腾讯 BeautifyPic 执行。")


if __name__ == "__main__":
    main()
