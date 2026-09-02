"""Small, explicit Tencent Effect Web SDK admission/smoke page.

This page is intentionally separate from the main portrait workflow.  It
starts with Tencent's official sample image, keeps the result in the browser,
and records only a redacted browser receipt.  The page never turns a
successful browser run into a production Provider Card automatically.
"""

from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path
from typing import Any

import streamlit as st
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if SOURCE_ROOT.is_dir() and str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# ruff: noqa: E402 - the page bootstraps the src-layout for direct Streamlit Cloud execution.
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.provider_cards import load_tencent_effect_web_card
from portrait_consistency_agent.services.tencent_effect_web import (
    MAX_DATA_URL_BYTES,
    TencentEffectWebAdapter,
    TencentEffectWebConfigurationError,
    TencentEffectWebCredentialsMissingError,
    get_or_create_effect_web_request,
    render_tencent_effect_web,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore

SAMPLE_URL = "https://webar-static.tencent-cloud.com/docs/test/m4-1080.jpg"


@st.cache_resource
def get_store(database_path: Path, trace_path: Path) -> LocalTraceStore:
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    return store


def _session_context(store: LocalTraceStore) -> tuple[str, str]:
    record = st.session_state.get("effect_web_session")
    if isinstance(record, dict) and record.get("session_id") and record.get("user_id"):
        return str(record["session_id"]), str(record["user_id"])
    created = store.create_session(state="EFFECT_WEB_SPIKE")
    st.session_state.effect_web_session = {
        "session_id": created.session_id,
        "user_id": created.anonymous_user_id,
    }
    return created.session_id, created.anonymous_user_id


def _component_result_value(result: object, key: str) -> object | None:
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key, None)


def _data_url(upload: Any) -> tuple[str, str, str]:
    value = upload.getvalue()
    digest = hashlib.sha256(value).hexdigest()
    mime = (
        upload.type
        if isinstance(upload.type, str) and upload.type.startswith("image/")
        else "image/png"
    )
    encoded = base64.b64encode(value).decode("ascii")
    return f"data:{mime};base64,{encoded}", digest, mime


def _scope_hash(*, input_hash: str, request_ref: str, parameters: dict[str, int]) -> str:
    canonical = "|".join(
        [
            input_hash,
            request_ref,
            *(f"{name}={parameters[name]}" for name in sorted(parameters)),
            "effect_web_test_v0",
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _show_safe_card(card: dict[str, object]) -> None:
    static_image = card.get("static_image")
    evidence = card.get("evidence")
    st.dataframe(
        [
            {
                "Card": card.get("card_id"),
                "版本": card.get("card_version"),
                "审核状态": card.get("review_status"),
                "静态图状态": static_image.get("status") if isinstance(static_image, dict) else "—",
                "历史 live receipt": evidence.get("live_smoke_status")
                if isinstance(evidence, dict)
                else "—",
            }
        ],
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    st.set_page_config(page_title="腾讯特效 Web 试验｜母版人像一致性 Agent", page_icon="🧩")
    settings = AppSettings()
    store = get_store(PROJECT_ROOT / settings.database_path, PROJECT_ROOT / settings.trace_path)
    session_id, anonymous_user_id = _session_context(store)
    card = load_tencent_effect_web_card()

    st.title("腾讯特效 Web SDK：静态图准入试验")
    st.caption(
        "这是独立的 Provider Spike，不是主流程。Tencent Effect Web 是浏览器 SDK：图片进入浏览器，"
        "结果也留在当前浏览器；Python 只接收脱敏回执。"
    )
    _show_safe_card(card)
    st.warning(
        "当前 Card 仍是 candidate。即使浏览器处理成功，也只证明这一次 Web 静态图回执；"
        "不会自动放行主流程，也不会把移动/PC 的唇厚、鼻翼等候选能力写成已支持。"
    )

    st.subheader("1. 选择测试输入")
    input_mode = st.radio(
        "先用哪张图？",
        ["腾讯官方示例图（推荐）", "我有明确授权的单人图片"],
        horizontal=True,
    )
    upload = None
    if input_mode == "我有明确授权的单人图片":
        st.caption("仅上传你本人或已取得全部肖像授权的单人图片；图片不写入数据库或 Trace。")
        upload = st.file_uploader(
            "选择一张 JPG/PNG 图片",
            type=["jpg", "jpeg", "png", "webp"],
            key="effect_web_upload",
        )
        if upload is None:
            st.info("未选择图片时仍可先查看官方示例流程。")

    if upload is None:
        input_value = SAMPLE_URL
        input_hash = hashlib.sha256(SAMPLE_URL.encode("utf-8")).hexdigest()
        input_source = "sample_url"
        input_ref = "effect_web_official_sample"
        st.image(SAMPLE_URL, caption="腾讯官方示例图（仅作 SDK Spike）", width=360)
    else:
        try:
            input_value, input_hash, _ = _data_url(upload)
        except (TypeError, ValueError) as exc:
            st.error(f"图片读取失败：{exc}")
            return
        if len(input_value.encode("utf-8")) > MAX_DATA_URL_BYTES:
            st.error("图片过大，当前 Web bridge 只接受不超过 8MB 的数据 URL。")
            return
        input_source = "data_url"
        input_ref = "effect_web_user_image"

    st.subheader("2. 选择本次试验参数")
    left, right = st.columns(2)
    with left:
        face_lifting = st.slider("瘦脸（产品刻度 0—100）", 0, 100, 10, key="effect_web_lift")
    with right:
        eye_enlarging = st.slider("大眼（产品刻度 0—100）", 0, 100, 10, key="effect_web_eye")
    st.caption("本次不会默认打开美白或磨皮；它们只在你明确调高并重新授权时才进入请求。")
    parameters = {"face_lifting": face_lifting, "eye_enlarging": eye_enlarging}
    consent = st.checkbox(
        "我确认允许腾讯特效 Web SDK 在当前浏览器处理这张测试图，并接受结果仅保留在本次浏览器会话。",
        key="effect_web_consent",
    )

    try:
        adapter = TencentEffectWebAdapter(settings)
        request, request_changed = get_or_create_effect_web_request(
            st.session_state,
            adapter,
            input_artifact_ref=input_ref,
            input_artifact_sha256=input_hash,
            parameters=parameters,
            input_source=input_source,
        )
        if request_changed:
            st.session_state.pop("effect_web_stale_receipt_hash", None)
    except (ValueError, TencentEffectWebConfigurationError) as exc:
        st.error(f"请求合同无法建立：{exc}")
        return

    if not settings.has_tencent_effect_credentials:
        st.info(
            "尚未配置腾讯特效 Web 的三项 Secrets：TENCENT_EFFECT_APP_ID、"
            "TENCENT_EFFECT_LICENSE_KEY、TENCENT_EFFECT_LICENSE_TOKEN。"
            "配置后刷新本页；Token 只留在服务端签名，不要填进页面或聊天。"
        )
        st.code(
            "Streamlit Cloud → App Settings → Secrets\n"
            'TENCENT_EFFECT_APP_ID = "..."\n'
            'TENCENT_EFFECT_LICENSE_KEY = "..."\n'
            'TENCENT_EFFECT_LICENSE_TOKEN = "..."',
            language="text",
        )
        return
    if not consent:
        st.info("勾选当前测试图片的处理同意后，才会生成浏览器调用载荷。")
        return

    try:
        payload = adapter.build_component_payload(request, input_value=input_value)
    except (TencentEffectWebCredentialsMissingError, TencentEffectWebConfigurationError) as exc:
        st.error(str(exc))
        return

    st.subheader("3. 在浏览器中执行一次")
    st.caption("点击组件内按钮后，浏览器才会加载 SDK 并处理图片；Python 不会上传或保存输出图。")
    result = render_tencent_effect_web(payload, key="effect_web_spike_component")
    receipt_value = _component_result_value(result, "completed")
    if not isinstance(receipt_value, dict):
        st.caption("等待浏览器回执；如果组件没有出现，请先刷新页面或检查浏览器控制台。")
        return

    try:
        receipt = adapter.validate_browser_receipt(receipt_value, request=request)
        scope_hash = _scope_hash(
            input_hash=input_hash,
            request_ref=request.request_ref,
            parameters=parameters,
        )
        run = adapter.build_provider_run(
            request=request,
            receipt=receipt,
            session_id=session_id,
            plan_id=f"effect_web_spike_plan_{request.request_ref}",
            photo_id=f"effect_web_photo_{input_hash[:16]}",
            confirmation_ref=f"effect_web_consent_{request.request_ref}",
            confirmation_scope_hash=scope_hash,
        )
        if not st.session_state.get("effect_web_saved_receipt"):
            store.save_provider_run(run)
            store.record_event(
                session_id,
                "effect_web_smoke_receipt_saved",
                {
                    "run_id": run.run_id,
                    "status": run.status,
                    "provider": run.provider,
                    "operation": run.operation,
                    "provider_request_id": run.provider_request_id,
                    "input_sha256": input_hash,
                    "receipt_has_output": run.result_artifact_sha256 is not None,
                    "anonymous_user_id": anonymous_user_id,
                },
            )
            st.session_state.effect_web_saved_receipt = run.run_id
        st.success("已收到浏览器回执，并保存了脱敏 ProviderRun。")
        st.json(
            {
                "status": run.status.value,
                "provider": run.provider,
                "operation": run.operation,
                "provider_request_id": run.provider_request_id,
                "sdk_version": receipt.sdk_version,
                "elapsed_ms": receipt.elapsed_ms,
                "error_code": receipt.error_code,
                "safe_error": receipt.safe_error,
                "result_retention": "browser_session_only",
                "output_hash_saved": run.result_artifact_sha256 is not None,
                "card_review_status_still": card["review_status"],
            }
        )
    except (ValueError, ValidationError) as exc:
        error_text = str(exc)
        if "request_ref does not match" in error_text:
            st.info(
                "检测到上一次组件回执对应旧请求，已安全忽略；请点击当前请求的处理按钮重新运行。"
            )
        elif "input hash does not match" in error_text:
            st.info("检测到回执图片不是当前输入，已安全忽略；请保持当前图片不变后重新运行。")
        else:
            st.error(f"浏览器回执未通过合同校验：{exc}")


if __name__ == "__main__":
    main()
