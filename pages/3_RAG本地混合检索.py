"""Inspectable P0-B hybrid retrieval: FTS plus local semantic reranking.

The page never downloads models or sends any user data.  It consumes only
reviewed Provider Cards and validated demo slots, then shows the safe Trace.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.rag_contracts import RagQuery, RagStage
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.local_rag_models import (
    BgeEmbeddingBackend,
    BgeRerankerBackend,
)
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_retriever(
    knowledge_path: Path,
    vector_path: Path,
    model_cache_path: Path,
    embedding_model: str,
    embedding_revision: str,
    reranker_model: str,
    reranker_revision: str,
) -> tuple[LocalKnowledgeStore, RagP0BHybridRetriever]:
    """Build a local-cache-only P0-B retriever once per Streamlit process."""

    store = LocalKnowledgeStore(knowledge_path)
    store.initialize()
    seed_reviewed_provider_knowledge(store)
    return store, RagP0BHybridRetriever(
        store=store,
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


def _scenario_query(scenario: str) -> RagQuery:
    if scenario == "瘦脸：关键词与语义证据如何合并":
        return build_plan_edit_query(
            query_id="rag_p0b_demo_face_lifting",
            requested_features=[EditableFeature.FACE_LIFTING],
            allowed_features=[EditableFeature.FACE_LIFTING],
        )
    if scenario == "唇厚：模型找得到相关资料，也不能假装能执行":
        return build_plan_edit_query(
            query_id="rag_p0b_demo_lips_thickness",
            requested_features=[EditableFeature.LIPS_THICKNESS],
            allowed_features=[EditableFeature.LIPS_THICKNESS],
        )
    if scenario == "不同意图片外发：排序再高也不能放行":
        return build_plan_edit_query(
            query_id="rag_p0b_demo_outbound_denied",
            requested_features=[EditableFeature.FACE_LIFTING],
            allowed_features=[EditableFeature.FACE_LIFTING],
            outbound_allowed=False,
        )
    if scenario == "关键槽位缺失：模型不会被启动":
        return build_plan_edit_query(
            query_id="rag_p0b_demo_missing_slot",
            requested_features=[EditableFeature.EYE_ENLARGING],
            allowed_features=[],
            missing_critical_slots=["allowed_features"],
        )
    return RagQuery(
        query_id="rag_p0b_demo_compare_scope",
        stage=RagStage.VERIFICATION_STRATEGY,
        provider_candidates=["tencent_cloud"],
        operation_candidates=["CompareFace"],
    )


def _route_message(route: str) -> tuple[str, str]:
    messages = {
        "evidence_found": ("success", "找到了可作为后续规划候选的当前工具证据；没有调用图片工具。"),
        "manual_suggestion": ("warning", "相关资料证明当前能力只能降级为建议，不能自动执行。"),
        "baseline_fallback": ("info", "没有可安全采用的直接依据，系统已保守回退。"),
        "query_underspecified": ("warning", "关键任务槽位缺失；检索模型没有启动。"),
        "conflict_blocked": ("error", "知识硬冲突已阻断，等待人工审核。"),
        "index_unavailable": ("error", "本地知识索引不可用，系统不会假装找到答案。"),
    }
    return messages[route]


def main() -> None:
    st.set_page_config(page_title="本地混合检索｜母版人像一致性 Agent", page_icon="🧭")
    settings = AppSettings()
    store, retriever = get_retriever(
        PROJECT_ROOT / settings.knowledge_database_path,
        PROJECT_ROOT / settings.rag_vector_database_path,
        PROJECT_ROOT / settings.rag_model_cache_path,
        settings.rag_embedding_model,
        settings.rag_embedding_revision,
        settings.rag_reranker_model,
        settings.rag_reranker_revision,
    )
    snapshot = store.snapshot()

    st.title("RAG 本地混合检索（P0-B）")
    st.caption(
        "这页展示 Agent 如何在已审核的工具知识中，同时用关键词和本地语义排序找证据。"
        "它只使用结构化任务槽位和 Provider Card，不读取照片、原话、人脸向量或密钥。"
    )
    st.warning(
        "模型只从本地缓存加载；页面不会下载模型，也不会调用 DeepSeek、腾讯或任何修图 API。"
        "即使语义模型缺失，系统也只会降级为 P0-A 的关键词检索，不能借此扩大工具权限。"
    )

    metrics = st.columns(5)
    metrics[0].metric("审核来源卡", snapshot["knowledge_items"])
    metrics[1].metric("原子规则", snapshot["knowledge_chunks"])
    metrics[2].metric("知识 Trace", snapshot["query_runs"])
    metrics[3].metric("稀疏候选上限", "8")
    metrics[4].metric("最终依据上限", "3")

    st.subheader("这一次的可解释链路")
    st.code(
        "结构化任务 → metadata 硬过滤 → FTS 前 8 + 本地语义前 8 → RRF 合并前 10 "
        "→ 本地 reranker 重排 → 最多 3 条依据 → 权限/能力规则决定路由",
        language=None,
    )
    st.caption(
        "RRF 和 reranker 只决定‘先看哪几条资料’，不能决定参数、授权或工具调用。"
        "有效期、冲突、Adapter、出站和允许部位仍由确定性规则最终裁决。"
    )

    scenario = st.selectbox(
        "选择一个已经 Schema 校验的任务场景",
        [
            "瘦脸：关键词与语义证据如何合并",
            "唇厚：模型找得到相关资料，也不能假装能执行",
            "不同意图片外发：排序再高也不能放行",
            "关键槽位缺失：模型不会被启动",
            "CompareFace：只能辅助同人，不能验收五官对齐",
        ],
    )
    query = _scenario_query(scenario)
    safe_query = query.model_dump(mode="json")
    safe_query.pop("created_at", None)
    st.json(safe_query, expanded=False)

    if st.button("运行本地混合检索", type="primary"):
        with st.spinner("只在本机读取审核知识与本地模型缓存…"):
            run = retriever.retrieve(query)
        level, message = _route_message(run.result.route.value)
        getattr(st, level)(message)

        result_metrics = st.columns(4)
        result_metrics[0].metric("稀疏候选", run.sparse_candidate_count)
        result_metrics[1].metric("语义候选", run.dense_candidate_count)
        result_metrics[2].metric("融合候选", run.fused_candidate_count)
        result_metrics[3].metric("最终路由", run.result.route.value)

        st.subheader("用户可见的依据卡")
        cards = run.result.user_evidence_cards()
        if not cards:
            st.info("本次没有可安全采用的依据；系统已按保守路径降级。")
        for card in cards:
            with st.container(border=True):
                st.write(card["结论"])
                st.caption(f"来源：{card['来源']}｜版本：{card['版本']}｜状态：{card['状态']}")

        st.subheader("代码这次实际做了什么")
        st.write(
            "它先过滤不适用、过期和冲突的资料，再并行产生 FTS 与本地语义候选，"
            "用 RRF 合并、用 reranker 排序，最后重新套用权限、能力、出站和恶意知识规则。"
            "本页只展示候选数量、排名和最终依据，不展示模型分数、知识全文或隐藏思维链。"
        )
        st.json(list(run.trace), expanded=False)


if __name__ == "__main__":
    main()
