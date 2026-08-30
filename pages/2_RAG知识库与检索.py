"""Inspectable local RAG P0-A demo: reviewed knowledge -> FTS -> evidence."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.rag_contracts import RagQuery, RagStage
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.rag_p0a import (
    RagP0ARetriever,
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_knowledge_store(database_path: Path) -> LocalKnowledgeStore:
    store = LocalKnowledgeStore(database_path)
    store.initialize()
    return store


def _scenario_query(scenario: str) -> RagQuery:
    if scenario == "瘦脸：查询现有工具能力":
        return build_plan_edit_query(
            query_id="rag_demo_face_lifting",
            requested_features=[EditableFeature.FACE_LIFTING],
            allowed_features=[EditableFeature.FACE_LIFTING],
        )
    if scenario == "唇厚：未接入自动能力时如何降级":
        return build_plan_edit_query(
            query_id="rag_demo_lips_thickness",
            requested_features=[EditableFeature.LIPS_THICKNESS],
            allowed_features=[EditableFeature.LIPS_THICKNESS],
        )
    if scenario == "多人图：为什么不能直接只修选中的脸":
        return build_plan_edit_query(
            query_id="rag_demo_multiface",
            requested_features=[],
            allowed_features=[],
            face_count=2,
        )
    if scenario == "同人比对：为什么不能证明五官已对齐":
        return RagQuery(
            query_id="rag_demo_compare_scope",
            stage=RagStage.VERIFICATION_STRATEGY,
            provider_candidates=["tencent_cloud"],
            operation_candidates=["CompareFace"],
        )
    return build_plan_edit_query(
        query_id="rag_demo_missing_slot",
        requested_features=[EditableFeature.EYE_ENLARGING],
        allowed_features=[],
        missing_critical_slots=["allowed_features"],
    )


def _route_message(route: str) -> tuple[str, str]:
    messages = {
        "evidence_found": ("success", "找到了当前可用的工具依据；这仍不是一次图片调用。"),
        "manual_suggestion": ("warning", "找到的是限制或未接入能力，因此只能降级为手动建议。"),
        "baseline_fallback": (
            "info",
            "没有可安全采用的直接依据，系统会保守回退，不会猜测或调用工具。",
        ),
        "query_underspecified": ("warning", "关键产品槽位还没填全，应先澄清而不是开始检索/执行。"),
        "conflict_blocked": ("error", "有效知识存在硬冲突，系统已阻断，等待人工审核。"),
        "index_unavailable": ("error", "本地检索索引不可用，系统不会假装找到了答案。"),
    }
    return messages[route]


def main() -> None:
    st.set_page_config(page_title="RAG 知识库与检索｜母版人像一致性 Agent", page_icon="📚")
    settings = AppSettings()
    store = get_knowledge_store(PROJECT_ROOT / settings.knowledge_database_path)
    seed = seed_reviewed_provider_knowledge(store)
    snapshot = store.snapshot()

    st.title("RAG 知识库与检索（P0-A）")
    st.caption(
        "这里展示的是 Agent 如何查阅已审核的工具说明书。它只运行本地 SQLite/FTS，"
        "不读取照片、原始用户话术、人脸向量、密钥，也不调用 LLM、腾讯或任何修图 API。"
    )
    st.warning(
        "P0-A 的结果只是一条带来源的工具知识依据：不会自动写 EditPlan、不会给参数、"
        "不会创建 ProviderRun、更不会扩大当前已接入的图片编辑能力。"
    )

    metrics = st.columns(4)
    metrics[0].metric("已审核来源卡", snapshot["knowledge_items"])
    metrics[1].metric("可检索原子规则", snapshot["knowledge_chunks"])
    metrics[2].metric("当前有效来源", snapshot["active_items"])
    metrics[3].metric("本地检索 Trace", snapshot["query_runs"])
    if seed.items_written:
        st.caption(
            f"本次启动已同步 {seed.items_written} 张来源卡、{seed.chunks_written} 条原子规则。"
        )

    st.subheader("选择一个结构化任务场景")
    scenario = st.selectbox(
        "P0-A 不把用户原话放进检索；下面每个场景都先转成经过 Schema 校验的任务槽位。",
        [
            "瘦脸：查询现有工具能力",
            "唇厚：未接入自动能力时如何降级",
            "多人图：为什么不能直接只修选中的脸",
            "同人比对：为什么不能证明五官已对齐",
            "关键槽位缺失：先澄清而不是猜测",
        ],
    )
    query = _scenario_query(scenario)
    safe_query = query.model_dump(mode="json")
    safe_query.pop("created_at", None)
    st.json(safe_query, expanded=False)

    if st.button("运行本地检索", type="primary"):
        run = RagP0ARetriever(store).retrieve(query)
        level, message = _route_message(run.result.route.value)
        getattr(st, level)(message)

        st.subheader("用户可见的依据卡")
        cards = run.result.user_evidence_cards()
        if not cards:
            st.info("本次没有可安全采用的依据卡；系统已按保守路径降级。")
        for card in cards:
            with st.container(border=True):
                st.write(card["结论"])
                st.caption(f"来源：{card['来源']}｜版本：{card['版本']}｜状态：{card['状态']}")

        st.subheader("这次代码实际做了什么")
        st.write(
            "先检查关键槽位与版本/地区等 metadata，再用 SQLite FTS 从最多 5 条候选中找依据；"
            "随后检查权限、出站限制、Adapter 状态、过期/冲突和恶意知识。最后只记录路由与来源，"
            "没有发出任何外部请求。"
        )
        st.json(list(run.trace), expanded=False)
        st.caption(
            "后台保留完整 knowledge refs 和淘汰原因；页面不展示原始资料全文、检索分数、"
            "隐藏思维链或任何用户照片数据。"
        )


if __name__ == "__main__":
    main()
