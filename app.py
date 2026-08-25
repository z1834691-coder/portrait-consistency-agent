"""Local Streamlit shell for the first traceable demo interaction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import streamlit as st

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    EditableFeature,
    FieldSource,
    IntentAction,
    IntentFrame,
    IntentGoal,
    Route,
)
from portrait_consistency_agent.core.settings import AppSettings
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


def build_template_intent(session_id: str, *, turn: int) -> IntentFrame:
    """A clearly marked fallback until the LLM intent adapter is implemented."""

    return IntentFrame(
        session_id=session_id,
        turn=turn,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.PROVIDE_PLAN,
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        blocked_features=[EditableFeature.SKIN_TONE, EditableFeature.MAKEUP],
        adjustment_mode=AdjustmentMode.BALANCED,
        max_rounds=2,
        field_sources={
            "goal": FieldSource.PRODUCT_DEFAULT,
            "route": FieldSource.PRODUCT_DEFAULT,
            "action": FieldSource.PRODUCT_DEFAULT,
            "allowed_features": FieldSource.PRODUCT_DEFAULT,
        },
        confidence=0.0,
        model_provider="template_fallback",
        prompt_version="intent-template-v0",
    )


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
        st.caption("腾讯 API：本页面未调用")
        st.caption("LLM：当前使用模板 fallback")
        if st.button("创建新的本地会话"):
            st.session_state.local_session_id = store.create_session().session_id
            st.session_state.pop("latest_intent", None)
            st.rerun()

    st.title("母版人像一致性 Agent")
    st.info(
        "检查点 5：当前页面只验证本地会话、上传内存预览、模板 IntentFrame 和 trace。"
        "它还没有调用腾讯 API、LLM、MediaPipe，也没有计算一致性指数。"
    )

    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("1. 候选母版（仅内存预览）")
        reference_upload = st.file_uploader(
            "上传一张你有权使用的候选母版",
            type=["png", "jpg", "jpeg", "bmp"],
            key="reference_upload",
        )
        if reference_upload:
            st.image(reference_upload, caption="本地预览：尚未保存、未上传到外部服务")

    with right_column:
        st.subheader("2. 目标照片（仅内存预览）")
        target_upload = st.file_uploader(
            "上传一张你有权使用的目标照片",
            type=["png", "jpg", "jpeg", "bmp"],
            key="target_upload",
        )
        if target_upload:
            st.image(target_upload, caption="本地预览：尚未保存、未上传到外部服务")

    st.subheader("3. 用一句话表达你的目标")
    user_text = st.text_area(
        "例如：把这张照片向我的母版靠拢，但保持妆面不变，先给我参数建议。",
        placeholder="此检查点只在浏览器内显示原话；写入 trace 的是文本哈希，不是原文。",
    )
    if st.button("保存本轮本地意图（模板模式）", type="primary"):
        if reference_upload is None or target_upload is None:
            st.warning("请先各上传一张母版和目标照片；文件仍只在当前页面内存中预览。")
        else:
            intent = build_template_intent(session_id, turn=store.next_intent_turn(session_id))
            store.save_intent_frame(intent)
            store.record_event(
                session_id,
                "uploads_previewed_and_template_intent_created",
                {
                    "reference": upload_metadata(reference_upload),
                    "target": upload_metadata(target_upload),
                    "user_text_sha256": hashlib.sha256(user_text.encode("utf-8")).hexdigest(),
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

    st.caption("下一检查点才会加入 MediaPipe 质量门；腾讯 API 和 LLM 需要相应的明确确认与配置。")


if __name__ == "__main__":
    main()
