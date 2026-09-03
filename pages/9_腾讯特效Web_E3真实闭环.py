"""E3 owner-only Web path: prepare a real profile, edit, and verify in one flow.

This page is deliberately separate from page 6's SDK spike.  It composes the
same product gates used by the main app (local quality, Tencent IMS, current
session CompareFace, ReferenceProfile, EditPlan and confirmation), then sends
the browser result through ``accept_and_verify_effect_web_result``.  Pixels are
kept in Streamlit session memory only; the ledger receives hashes and receipt
facts.

The page is for an owner-authorized private E3 evidence run, not a public
consumer surface.  It supports one reference and up to three targets so a
single session can produce a redacted multi-sample manifest.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if SOURCE_ROOT.is_dir() and str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# ruff: noqa: E402 - Streamlit pages bootstrap the src layout when Cloud runs them directly.
from portrait_consistency_agent.core.contracts import (  # noqa: E402
    AdjustmentMode,
    ContentSafetyStatus,
    EditableFeature,
    ExecutionPriority,
    IntentAction,
    IntentFrame,
    IntentGoal,
    OutputPreference,
    ParserMode,
    PhotoRole,
    PreserveAttribute,
    ReferenceProfile,
    ReferenceSource,
    Route,
    TargetScope,
)
from portrait_consistency_agent.core.settings import AppSettings  # noqa: E402
from portrait_consistency_agent.services.checkpoint6 import Checkpoint6Service  # noqa: E402
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan  # noqa: E402
from portrait_consistency_agent.services.effect_web_e3_flow import (  # noqa: E402
    EffectWebE3FlowResult,
    accept_and_verify_effect_web_result,
)
from portrait_consistency_agent.services.execution import confirm_execution  # noqa: E402
from portrait_consistency_agent.services.photo_quality import analyze_photo_bytes  # noqa: E402
from portrait_consistency_agent.services.provider_cards import (  # noqa: E402
    load_tencent_effect_web_card,
)
from portrait_consistency_agent.services.tencent_effect_web import (  # noqa: E402
    MAX_DATA_URL_BYTES,
    TencentEffectWebAdapter,
    TencentEffectWebConfigurationError,
    TencentEffectWebCredentialsMissingError,
    get_or_create_effect_web_request,
    render_tencent_effect_web,
)
from portrait_consistency_agent.services.tencent_safety import (  # noqa: E402
    ContentSafetyCredentialsMissingError,
    TencentContentSafetyApiError,
    TencentImageModerationClient,
    build_content_safety_decision,
    safe_error_message,
    safe_error_trace,
)
from portrait_consistency_agent.services.tencent_subject import (  # noqa: E402
    SubjectMatchCredentialsMissingError,
    SubjectMatchPolicy,
    TencentCompareFaceClient,
    TencentSubjectApiError,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore  # noqa: E402


def _store(settings: AppSettings) -> LocalTraceStore:
    store = LocalTraceStore(
        PROJECT_ROOT / settings.database_path, PROJECT_ROOT / settings.trace_path
    )
    store.initialize()
    return store


def _component_value(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _photo_id(upload: Any, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(upload.getvalue()).hexdigest()[:16]}"


def _data_url(upload: Any) -> tuple[str, str]:
    raw = upload.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    mime = (
        upload.type
        if isinstance(upload.type, str) and upload.type.startswith("image/")
        else "image/jpeg"
    )
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", digest


def _intent(session_id: str, target_id: str) -> IntentFrame:
    """Create the owner-test's explicit product goal; no LLM is needed here."""

    return IntentFrame(
        intent_id=f"intent_e3_{uuid.uuid4().hex[:16]}",
        session_id=session_id,
        turn=1,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.PROVIDE_PLAN,
        target_scope=TargetScope.CURRENT_PHOTO,
        reference_source=ReferenceSource.EXISTING_PROFILE,
        target_refs=[target_id],
        output_preferences=[OutputPreference.EDITED_IMAGES],
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        blocked_features=[],
        preserve_attributes=[
            PreserveAttribute.SKIN_TONE,
            PreserveAttribute.MAKEUP,
            PreserveAttribute.BACKGROUND,
        ],
        adjustment_mode=AdjustmentMode.BALANCED,
        priority=ExecutionPriority.CONSISTENCY,
        requested_max_rounds=3,
        intent_confidence=1.0,
        reason_codes=["e3_owner_authorized_web_test"],
        parser_mode=ParserMode.USER_STRUCTURED_INPUT,
    )


def _error_event(store: LocalTraceStore, session_id: str, event: str, exc: BaseException) -> None:
    store.record_event(session_id, event, safe_error_trace(exc))


def _receipt_projection(
    receipt: dict[str, object],
    *,
    sample_id: str,
    input_sha256: str,
    flow: EffectWebE3FlowResult | None = None,
) -> dict[str, object]:
    output_sha = receipt.get("output_sha256")
    verification = flow.verification if flow is not None else None
    return {
        "sample_id": sample_id,
        "receipt_id": receipt.get("receipt_id"),
        "request_ref": receipt.get("request_ref"),
        "input_sha256": input_sha256,
        "status": receipt.get("status"),
        "elapsed_ms": receipt.get("elapsed_ms"),
        "output_sha256": output_sha,
        "output_width": receipt.get("output_width"),
        "output_height": receipt.get("output_height"),
        "handoff_accepted": bool(output_sha),
        "result_retention": "browser_session_only",
        "verification_status": "completed" if verification is not None else "not_run",
        "verification_id": verification.verification_id if verification else None,
        "verification_decision": verification.decision.value if verification else None,
        "overall_trend": verification.overall_trend.value if verification else None,
        "target_evidence_sufficient": (
            verification.target_evidence_sufficient if verification else None
        ),
        "measured_feature_count": (
            len([item for item in verification.feature_comparisons if item.after_gap is not None])
            if verification
            else None
        ),
        "image_bytes_saved": False,
        "data_url_saved": False,
    }


def _render_verification(flow: EffectWebE3FlowResult) -> None:
    verification = flow.verification
    if verification is None:
        st.info("本次 Web 回执未进入复测（失败或结果图未交接）。")
        return
    assert flow.verification_run is not None
    st.success(flow.verification_run.user_message)
    st.dataframe(
        [
            {
                "特征": item.feature_code,
                "修前差异": item.before_gap,
                "修后差异": item.after_gap,
                "趋势": item.trend.value,
                "测量置信度（内部路由）": item.measurement_confidence,
            }
            for item in verification.feature_comparisons
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.json(
        {
            "overall_trend": verification.overall_trend.value,
            "decision": verification.decision.value,
            "target_evidence_sufficient": verification.target_evidence_sufficient,
            "verification_strategy": verification.verification_strategy.value,
            "reason_codes": verification.reason_codes,
            "result_artifact_persisted": False,
        }
    )
    with st.expander("查看完整 Web→VerificationResult Trace（脱敏）"):
        st.json(list(flow.trace))


def _prepare_reference(
    *,
    upload: Any,
    settings: AppSettings,
    store: LocalTraceStore,
    session_id: str,
    user_id: str,
) -> ReferenceProfile | None:
    raw = upload.getvalue()
    photo_id = _photo_id(upload, "e3_reference")
    observation = analyze_photo_bytes(raw, photo_id=photo_id, photo_role=PhotoRole.REFERENCE)
    st.image(raw, caption="候选母版（只在当前会话显示）", width=260)
    st.json(observation.user_projection())
    if observation.face_count != 1:
        st.error("母版必须是可检测到的单人照片；当前不会建立 Profile。")
        return None
    if not st.checkbox(
        "我确认这是本人/已获授权照片，并允许发送给腾讯 ImageModeration；只用于本次 E3 私有测试。",
        key="e3_reference_consent",
    ):
        st.info("完成发送范围确认后，才会进行安全检查。")
        return None
    if st.button("检查并锁定母版（一次完成）", key="e3_reference_prepare", type="primary"):
        try:
            response = TencentImageModerationClient(settings).moderate_base64(raw)
            safety = build_content_safety_decision(
                response, receipt_ref=f"e3_safety_{observation.photo_sha256[:16]}"
            )
            store.record_event(
                session_id,
                "e3_reference_content_safety_decision",
                {
                    "photo_sha256": observation.photo_sha256,
                    "status": safety.status.value,
                    "provider_request_id": safety.evidence.provider_request_id,
                },
            )
            if safety.status != ContentSafetyStatus.PASSED:
                st.error("腾讯内容安全未通过，母版不会锁定。")
                return None
            prep = Checkpoint6Service(store=store).prepare_reference(
                raw,
                session_id=session_id,
                photo_id=photo_id,
                quality_result_id=f"e3_quality_{observation.photo_sha256[:16]}",
                safety_decision=safety,
            )
            profile_result = Checkpoint6Service(store=store).lock_profile(
                prep,
                user_id=user_id,
                profile_id=f"e3_profile_{observation.photo_sha256[:16]}",
                version=1,
                feature_snapshot_ref=f"e3_snapshot_{observation.photo_sha256[:16]}",
            )
            st.session_state.e3_profile = profile_result.profile.model_dump(mode="json")
            st.session_state.e3_reference_bytes = raw
            st.success("母版安全检查通过，ReferenceProfile v0 已锁定。原图不写入账本。")
        except (
            ContentSafetyCredentialsMissingError,
            TencentContentSafetyApiError,
            ValueError,
        ) as exc:
            _error_event(store, session_id, "e3_reference_preparation_failed", exc)
            st.error(safe_error_message(exc))
    profile_payload = st.session_state.get("e3_profile")
    if isinstance(profile_payload, dict):
        st.success("当前会话已有母版档案。")
        return ReferenceProfile.model_validate(profile_payload)
    return None


def _prepare_target(
    *,
    upload: Any,
    sample_id: str,
    reference_bytes: bytes,
    profile: ReferenceProfile,
    settings: AppSettings,
    store: LocalTraceStore,
    session_id: str,
) -> tuple[dict[str, object], bytes] | None:
    raw = upload.getvalue()
    target_id = _photo_id(upload, "e3_target")
    target_hash = hashlib.sha256(raw).hexdigest()
    st.image(raw, caption=f"目标照：{upload.name}", width=220)
    observation = analyze_photo_bytes(raw, photo_id=target_id, photo_role=PhotoRole.TARGET)
    st.json(observation.user_projection())
    if observation.face_count != 1:
        st.error("当前目标照不是单人可编辑照片，跳过本张。")
        return None
    if not st.checkbox(
        "我确认允许这张目标照发送给腾讯 ImageModeration 与 CompareFace；结果仅用于本次 E3 测试。",
        key=f"e3_target_consent_{target_hash[:12]}",
    ):
        st.info("完成发送范围确认后，才会进行目标照预检。")
        return None
    if st.button("运行这张目标照的安全＋同人预检", key=f"e3_target_preflight_{target_hash[:12]}"):
        try:
            safety_response = TencentImageModerationClient(settings).moderate_base64(raw)
            safety = build_content_safety_decision(
                safety_response,
                receipt_ref=f"e3_safety_{target_hash[:16]}",
            )
            if safety.status != ContentSafetyStatus.PASSED:
                st.error("腾讯内容安全未通过，本张不进入 Web 处理。")
                return None
            service = Checkpoint6Service(
                store=store,
                subject_client=TencentCompareFaceClient(settings),
            )
            validated = service.validate_target_current_session(
                reference_bytes,
                raw,
                session_id=session_id,
                target_photo_id=target_id,
                quality_result_id=f"e3_quality_{target_hash[:16]}",
                safety_decision=safety,
                receipt_ref=f"e3_subject_{target_hash[:16]}",
                subject_policy=SubjectMatchPolicy.v0(),
            )
            if validated.quality_result is None or validated.subject_decision is None:
                st.error("同人预检未产生可继续的质量合同。")
                return None
            if validated.quality_result.route.value not in {
                "continue",
                "warn_continue",
                "subject_confirmation_required",
            }:
                st.error(f"当前照片不能继续：{validated.quality_result.route.value}")
                return None
            st.session_state[f"e3_target_quality_{target_hash}"] = (
                validated.quality_result.model_dump(mode="json")
            )
            st.session_state[f"e3_target_observation_{target_hash}"] = observation
            st.session_state[f"e3_target_ready_{target_hash}"] = True
            st.success(
                f"预检通过：{validated.subject_decision.status.value}；下一步可生成 Web EditPlan。"
            )
        except (
            SubjectMatchCredentialsMissingError,
            TencentSubjectApiError,
            ContentSafetyCredentialsMissingError,
            TencentContentSafetyApiError,
            ValueError,
        ) as exc:
            _error_event(store, session_id, "e3_target_preflight_failed", exc)
            st.error(safe_error_message(exc))
    quality_payload = st.session_state.get(f"e3_target_quality_{target_hash}")
    if isinstance(quality_payload, dict):
        return quality_payload, raw
    return None


def _render_target_web_flow(
    *,
    upload: Any,
    sample_id: str,
    reference_bytes: bytes,
    profile: ReferenceProfile,
    target_payload: dict[str, object],
    settings: AppSettings,
    store: LocalTraceStore,
    session_id: str,
) -> None:
    target_bytes = upload.getvalue()
    target_id = _photo_id(upload, "e3_target")
    target_hash = hashlib.sha256(target_bytes).hexdigest()
    quality_payload = target_payload
    try:
        from portrait_consistency_agent.core.contracts import PhotoQualityResult

        quality = PhotoQualityResult.model_validate(quality_payload)
        observation = analyze_photo_bytes(
            target_bytes, photo_id=target_id, photo_role=PhotoRole.TARGET
        )
        intent = _intent(session_id, target_id)
    except ValueError as exc:
        st.error(f"目标合同无法验证：{exc}")
        return
    planned_key = f"e3_plan_{target_hash}"
    if planned_key not in st.session_state:
        try:
            planned = diagnose_and_plan(
                profile=profile,
                target_observation=observation,
                quality_result=quality,
                intent=intent,
                provider_id="tencent_effect_web",
                plan_id=f"e3_web_plan_{target_hash[:16]}",
                store=store,
            )
            if planned.plan is None:
                st.warning(f"无法生成可执行 Web 计划：{planned.user_message}")
                st.json(list(planned.trace))
                return
            st.session_state[planned_key] = {
                "plan": planned.plan.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
                "trace": list(planned.trace),
            }
        except (ValueError, RuntimeError) as exc:
            st.error(f"Web EditPlan 生成失败：{exc}")
            return
    planned_payload = st.session_state.get(planned_key)
    if not isinstance(planned_payload, dict):
        return
    from portrait_consistency_agent.core.contracts import EditPlan

    plan = EditPlan.model_validate(planned_payload["plan"])
    st.markdown("**Agent 生成的 Web 计划（参数只做审计，不要求用户理解滑杆）**")
    st.json(
        {
            "可执行部位": [item.feature.value for item in plan.executable_changes],
            "产品参数（0—100）": [
                {"feature": item.feature.value, "proposed_absolute": item.proposed_absolute}
                for item in plan.executable_changes
            ],
            "provider": plan.provider,
            "card_version": plan.provider_card_version,
        }
    )
    confirmation_key = f"e3_confirmation_{target_hash}"
    if confirmation_key not in st.session_state:
        st.session_state[confirmation_key] = False
    if not st.session_state[confirmation_key]:
        st.caption("E3 测试需要一次范围确认；确认后，同一张照片只在本次受限计划族内交给 Web SDK。")
        if st.button(
            "确认本张测试并生成 Web 调用", key=f"e3_confirm_{target_hash}", type="primary"
        ):
            try:
                confirmation = confirm_execution(
                    source_intent=intent,
                    proposed_plan=plan,
                    next_turn=1,
                    now=datetime.now(timezone.utc),
                )
                st.session_state[confirmation_key] = {
                    "plan": confirmation.confirmed_plan.model_dump(mode="json"),
                    "intent": confirmation.execution_intent.model_dump(mode="json"),
                }
                store.save_intent_frame(confirmation.execution_intent)
                store.save_edit_plan(confirmation.confirmed_plan)
                st.success("本张图片的 Web 执行范围已确认。")
            except ValueError as exc:
                st.error(f"无法确认本张测试：{exc}")
                return
    confirmation_payload = st.session_state.get(confirmation_key)
    if not isinstance(confirmation_payload, dict):
        return
    confirmed_plan = EditPlan.model_validate(confirmation_payload["plan"])
    execution_intent = IntentFrame.model_validate(confirmation_payload["intent"])
    try:
        adapter = TencentEffectWebAdapter(settings)
        input_value, input_hash = _data_url(upload)
        if len(input_value.encode("utf-8")) > MAX_DATA_URL_BYTES:
            st.error("目标照超过当前 Web bridge 8MB 限制，请压缩后重试。")
            return
        # Each target owns an independent request-generation state. Reusing
        # page-6's global key would let a later sample replace an earlier
        # request_ref during a Streamlit rerun.
        request_state = st.session_state.setdefault(f"e3_request_state_{target_hash}", {})
        if not isinstance(request_state, dict):
            request_state = {}
            st.session_state[f"e3_request_state_{target_hash}"] = request_state
        request, _ = get_or_create_effect_web_request(
            request_state,
            adapter,
            input_artifact_ref=f"e3_upload_{target_hash[:16]}",
            input_artifact_sha256=input_hash,
            parameters={
                "face_lifting": confirmed_plan.provider_absolute_params.lift * 100,
                "eye_enlarging": confirmed_plan.provider_absolute_params.eye * 100,
            },
            input_source="data_url",
        )
        payload = adapter.build_component_payload(
            request, input_value=input_value, reset_token=f"e3_{target_hash}"
        )
    except (
        TencentEffectWebCredentialsMissingError,
        TencentEffectWebConfigurationError,
        ValueError,
    ) as exc:
        st.error(str(exc))
        return

    st.markdown("**Web SDK 处理**")
    st.caption(
        "浏览器执行后只回传一次性图片结果；服务端会立即进入共同 "
        "VerificationResult，结果图不写入账本。"
    )
    component_result = render_tencent_effect_web(payload, key=f"e3_web_component_{target_hash}")
    receipt_value = _component_value(component_result, "completed")
    if not isinstance(receipt_value, dict):
        st.info("等待浏览器回执；请点击组件内的‘开始腾讯特效处理’。")
        return
    result_value = _component_value(component_result, "result")
    receipt_payload = dict(receipt_value)
    if not isinstance(result_value, dict):
        result_value = receipt_payload.pop("result_handoff", None)
    else:
        receipt_payload.pop("result_handoff", None)
    try:
        receipt = TencentEffectWebAdapter.validate_browser_receipt(receipt_payload, request=request)
        result_payload = result_value if isinstance(result_value, dict) else None
        flow_key = f"e3_flow_{target_hash}_{receipt.receipt_id}"
        if flow_key not in st.session_state:
            web_card = load_tencent_effect_web_card()
            flow = accept_and_verify_effect_web_result(
                confirmed_plan=confirmed_plan,
                execution_intent=execution_intent,
                target_image_bytes=target_bytes,
                target_photo_id=target_id,
                profile=profile,
                quality_result=quality,
                prepared_request=request.model_dump(mode="json"),
                browser_receipt=receipt.model_dump(mode="json"),
                browser_result=result_payload,
                store=store,
                now=datetime.now(timezone.utc),
                allow_candidate_trial=web_card.get("review_status") != "verified",
            )
            st.session_state[flow_key] = flow
        flow = st.session_state[flow_key]
        if f"e3_live_receipt_{target_hash}" not in st.session_state:
            st.session_state[f"e3_live_receipt_{target_hash}"] = _receipt_projection(
                receipt.model_dump(mode="json"),
                sample_id=sample_id,
                input_sha256=target_hash,
                flow=flow,
            )
        execution = flow.execution
        if execution.result_image_bytes is not None:
            st.image(
                execution.result_image_bytes, caption="Web 结果图（当前会话临时内存）", width=360
            )
        _render_verification(flow)
        st.download_button(
            "下载本张脱敏 E3 回执（可用于本地准入清单）",
            data=json.dumps(
                st.session_state[f"e3_live_receipt_{target_hash}"], ensure_ascii=False, indent=2
            ),
            file_name=f"e3_receipt_{target_hash[:12]}.json",
            mime="application/json",
            key=f"e3_receipt_download_{target_hash}",
        )
    except (ValueError, ValidationError) as exc:
        st.error(f"Web 回执或结果交接未通过合同校验：{exc}")


def main() -> None:
    st.set_page_config(page_title="腾讯特效 Web E3 真实闭环", page_icon="🧪", layout="wide")
    settings = AppSettings()
    store = _store(settings)
    session = st.session_state.get("e3_session")
    if not isinstance(session, dict):
        created = store.create_session(state="E3_WEB_REAL_CLOSED_LOOP")
        session = {"session_id": created.session_id, "user_id": created.anonymous_user_id}
        st.session_state.e3_session = session
    session_id = str(session["session_id"])
    user_id = str(session["user_id"])

    st.title("腾讯特效 Web｜E3 真实闭环")
    st.caption(
        "把候选 Web SDK 放进真实产品链路：母版安全/Profile → 目标安全/同人 → "
        "Web EditPlan → 浏览器处理 → 共同 VerificationResult。"
    )
    st.warning(
        "这是受邀测试和准入证据页，不是公开生产入口。只显示结果和脱敏事实；"
        "不展示隐藏思维链，不把 SDK 成功当成母版一致性成功。"
    )
    if not settings.has_tencent_credentials:
        st.error("当前环境缺少 TENCENT_SECRET_ID/KEY；不能运行 IMS 与 CompareFace。")
        return
    if not settings.has_tencent_effect_credentials:
        st.error("当前环境缺少腾讯特效 Web 的 APPID/License Key/License Token Secrets。")
        return

    reference_upload = st.file_uploader(
        "1. 上传一张本人单人母版（JPG/PNG/WebP）",
        type=["jpg", "jpeg", "png", "webp"],
        key="e3_reference_upload",
    )
    profile: ReferenceProfile | None = None
    reference_bytes = st.session_state.get("e3_reference_bytes")
    if reference_upload is not None:
        profile = _prepare_reference(
            upload=reference_upload,
            settings=settings,
            store=store,
            session_id=session_id,
            user_id=user_id,
        )
        if profile is not None:
            reference_bytes = reference_upload.getvalue()
            st.session_state.e3_reference_bytes = reference_bytes
    profile_payload = st.session_state.get("e3_profile")
    if profile is None and isinstance(profile_payload, dict):
        try:
            profile = ReferenceProfile.model_validate(profile_payload)
        except ValueError:
            st.session_state.pop("e3_profile", None)
            profile = None
    if profile is None or not isinstance(reference_bytes, bytes):
        st.info("先完成母版检查和锁定，之后再上传目标样本。")
        return

    targets = st.file_uploader(
        "2. 上传一到三张本人目标照（用于 E3 多样本证据）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="e3_target_uploads",
    )
    if not targets:
        st.info("上传目标照后，按每张照片完成一次预检和 Web 处理。")
        return
    for index, target in enumerate(targets[:3], start=1):
        st.divider()
        st.subheader(f"目标样本 {index}：{target.name}")
        prepared = _prepare_target(
            upload=target,
            sample_id=f"e3_target_{index:03d}",
            reference_bytes=reference_bytes,
            profile=profile,
            settings=settings,
            store=store,
            session_id=session_id,
        )
        if prepared is None:
            continue
        quality_payload, _ = prepared
        _render_target_web_flow(
            upload=target,
            sample_id=f"e3_target_{index:03d}",
            reference_bytes=reference_bytes,
            profile=profile,
            target_payload=quality_payload,
            settings=settings,
            store=store,
            session_id=session_id,
        )


if __name__ == "__main__":
    main()
