"""Local-only administrator dashboard for redacted product-operation events."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.storage.local_store import LocalTraceStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_store(database_path: Path, trace_path: Path) -> LocalTraceStore:
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    return store


def main() -> None:
    st.set_page_config(page_title="运营数据看板｜母版人像一致性 Agent", page_icon="📊")
    settings = AppSettings()
    store = get_store(
        PROJECT_ROOT / settings.database_path,
        PROJECT_ROOT / settings.trace_path,
    )
    snapshot = store.dashboard_snapshot()

    st.title("运营数据看板（本地管理员原型）")
    st.caption(
        "这里是产品运行账本的聚合视图，不显示照片、原文、人脸特征、嵌入向量、密钥或腾讯请求体。"
    )
    st.warning(
        "当前仅适合本机开发者查看；受邀测试部署前必须补管理员访问控制。样本量不足时，"
        "这些数字不能被称为用户研究结论、留存结论或产品 KPI。"
    )

    first_row = st.columns(4)
    first_row[0].metric("累计会话", snapshot["total_sessions"])
    first_row[1].metric("母版建立", snapshot["profile_created"])
    first_row[2].metric("提交意图", snapshot["intent_submitted"])
    first_row[3].metric("成功工具调用", snapshot["provider_succeeded"])

    second_row = st.columns(4)
    second_row[0].metric("完成复测", snapshot["verification_completed"])
    second_row[1].metric("显式反馈", snapshot["explicit_feedback"])
    second_row[2].metric("近 7 日活跃用户", snapshot["wau"])
    second_row[3].metric("近 30 日活跃用户", snapshot["mau"])

    st.subheader("最近脱敏产品事件")
    st.dataframe(store.recent_product_events(), use_container_width=True, hide_index=True)
    st.caption(
        "“退出/沉默”只记录为路径中止或未知行为，不会自动写成不满意；首次 Prompt 是意图信号，"
        "不是满意度标签。"
    )


if __name__ == "__main__":
    main()
