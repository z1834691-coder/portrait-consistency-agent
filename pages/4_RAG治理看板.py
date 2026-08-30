"""Local-only, redacted RAG governance dashboard.

This page is deliberately a read-only window into the RAG authority store.
It visualizes reviewed knowledge, routing and bad-case records without reading
photos, raw user text, face vectors, model prompts, secrets or provider media.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as render_component

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.rag_lifecycle import audit_rag_lifecycle
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_report_registry import (
    available_rag_reports,
    read_rag_report,
)
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_store(database_path: Path) -> LocalKnowledgeStore:
    """Open the independent local RAG authority store once per UI process."""

    store = LocalKnowledgeStore(database_path)
    store.initialize()
    seed_reviewed_provider_knowledge(store)
    return store


def _chart_rows(counts: dict[str, int]) -> list[dict[str, object]]:
    return [
        {"标签": label, "数量": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _render_count_chart(title: str, counts: dict[str, int], empty_message: str) -> None:
    st.subheader(title)
    rows = _chart_rows(counts)
    if not rows:
        st.info(empty_message)
        return
    maximum = max(row["数量"] for row in rows)
    for row in rows:
        label_column, value_column = st.columns([5, 1])
        label_column.write(f"**{row['标签']}**")
        value_column.write(str(row["数量"]))
        st.progress(int(int(row["数量"]) / int(maximum) * 100))
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _safe_query_rows(store: LocalKnowledgeStore) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in store.recent_query_runs(limit=20):
        result = run["result"]
        if not isinstance(result, dict):
            continue
        knowledge_refs = result.get("knowledge_refs", [])
        reason_codes = result.get("reason_codes", [])
        rows.append(
            {
                "时间": run["created_at"],
                "检索任务": run["query_id"],
                "路由": run["route"],
                "依据条数": len(knowledge_refs) if isinstance(knowledge_refs, list) else 0,
                "原因代码": ", ".join(reason_codes) if isinstance(reason_codes, list) else "",
                "外部调用": "否（RAG 本身）",
            }
        )
    return rows


def _safe_advisory_rows(store: LocalKnowledgeStore) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in store.recent_advisory_runs(limit=20):
        decision = run["decision"]
        if not isinstance(decision, dict):
            continue
        direct_refs = decision.get("direct_evidence_refs", [])
        reference_refs = decision.get("reference_information_refs", [])
        conflict_refs = decision.get("conflict_information_refs", [])
        rows.append(
            {
                "时间": run["created_at"],
                "建议任务": run["advice_id"],
                "节点": run["stage"],
                "建议路由": run["advisory_route"],
                "直接依据": len(direct_refs) if isinstance(direct_refs, list) else 0,
                "参考信息": len(reference_refs) if isinstance(reference_refs, list) else 0,
                "冲突信息": len(conflict_refs) if isinstance(conflict_refs, list) else 0,
                "是否授权执行": "否（固定边界）",
            }
        )
    return rows


def _safe_bad_case_rows(store: LocalKnowledgeStore) -> list[dict[str, object]]:
    return [
        {
            "时间": record["created_at"],
            "Bad case": record["bad_case_id"],
            "节点": record["stage"],
            "诊断": record["diagnosis"],
            "处理": "记录后停止 / 保守基线降级；不允许模型编造工具能力",
        }
        for record in store.recent_bad_cases(limit=20)
    ]


def _safe_lifecycle_rows(audit: object) -> list[dict[str, object]]:
    """Project lifecycle contracts to a compact, source-body-free table."""

    item_audits = getattr(audit, "item_audits", [])
    return [
        {
            "来源": item.knowledge_id,
            "Provider": item.provider,
            "操作": item.operation,
            "版本": item.source_version,
            "生命周期": item.lifecycle_status.value,
            "问题": ", ".join(code.value for code in item.issue_codes) or "无",
            "建议动作": item.recommended_action.value,
        }
        for item in item_audits
    ]


def _render_report_collection() -> None:
    """Show the allow-listed visual reports without exposing private keys."""

    st.subheader("评测与优化报告集合")
    st.caption(
        "这里嵌入的是已经生成的脱敏 HTML。隐藏集只显示聚合指标；答案键、题干、照片和原始 Trace "
        "不在报告集合中。"
    )
    reports = available_rag_reports(PROJECT_ROOT)
    if not reports:
        st.info(
            "尚无生成的评测报告。可运行 Gold evaluator 或 "
            "scripts/analyze_rag_failures.py 后刷新页面。"
        )
        return
    for artifact, path in reports:
        with st.expander(f"{artifact.title}｜{artifact.scope}", expanded=False):
            st.write(artifact.description)
            st.caption(f"文件：{path.name}")
            st.download_button(
                "下载 HTML 报告",
                data=path.read_bytes(),
                file_name=path.name,
                mime="text/html",
                key=f"download_{artifact.key}",
            )
            try:
                render_component(
                    read_rag_report(artifact, PROJECT_ROOT), height=620, scrolling=True
                )
            except OSError as exc:
                st.error(f"报告读取失败：{exc}")


def main() -> None:
    st.set_page_config(page_title="RAG 治理看板｜母版人像一致性 Agent", page_icon="🛡️")
    settings = AppSettings()
    store = get_store(PROJECT_ROOT / settings.knowledge_database_path)
    snapshot = store.rag_dashboard_snapshot()
    dense_index = LocalDenseIndex(PROJECT_ROOT / settings.rag_vector_database_path)
    dense_snapshot = dense_index.snapshot()

    st.title("RAG 治理看板（本地管理员原型）")
    st.caption(
        "这是一张“说明书、检索与安全路由”的健康检查表：它帮助开发者知道 Agent 依据了什么、"
        "有没有冲突或空召回、有没有安全降级。"
    )
    st.warning(
        "它不是用户画像、不是照片库、不是模型训练数据，也不是 RAG 质量已经通过的证明。"
        "Gold Set v2 的公开与隐藏聚合评测已经运行，但当前 project Gate 仍为 FAIL；"
        "隐藏集只回流聚合指标，不能用来逐题补规则。"
    )

    top = st.columns(4)
    top[0].metric("审核知识卡", snapshot["knowledge_items"])
    top[1].metric("可检索规则", snapshot["knowledge_chunks"])
    top[2].metric("本地检索运行", snapshot["query_runs"])
    top[3].metric("RAG 建议运行", snapshot["advisory_runs"])

    second = st.columns(4)
    second[0].metric("已记录 Bad case", snapshot["rag_bad_cases"])
    second[1].metric("当前有效来源", snapshot["active_items"])
    second[2].metric("临近复审（14 天）", snapshot["review_due_within_14_days"])
    second[3].metric("逾期未复审", snapshot["review_overdue"])

    st.subheader("这张看板如何防止黑箱")
    st.write(
        "每一次 RAG 只查询审核过的工具知识，并把结果分为“直接依据、参考信息、冲突信息”。"
        "看板能看到每一步的路由和 bad case；但它不会展示用户照片、原话、人脸向量、模型提示词、"
        "密钥、供应商图片请求或隐藏思维链。"
    )

    overview, traces, governance = st.tabs(["运行概览", "最近 Trace", "知识治理"])
    with overview:
        left, right = st.columns(2)
        with left:
            _render_count_chart(
                "检索结果路由",
                snapshot["retrieval_routes"],
                "还没有本地检索记录。可以先到 P0-A/P0-B 页面运行一个预置场景。",
            )
        with right:
            _render_count_chart(
                "RAG 建议路由",
                snapshot["advisory_routes"],
                "还没有 P0-C 建议记录。它出现后仍只会作为证据建议，不会授权执行。",
            )
        left, right = st.columns(2)
        with left:
            _render_count_chart(
                "RAG 被消费的节点",
                snapshot["advisory_stages"],
                "目前还没有建议记录。",
            )
        with right:
            _render_count_chart(
                "Bad case 诊断分布",
                snapshot["bad_case_diagnoses"],
                "目前没有 bad case；这不是质量结论，只代表本地账本中暂无记录。",
            )

        st.subheader("本地向量索引状态")
        index_metrics = st.columns(3)
        index_metrics[0].metric("索引 manifest", dense_snapshot["dense_index_manifests"])
        index_metrics[1].metric("派生向量条数", dense_snapshot["dense_vectors"])
        index_metrics[2].metric("模型下载", "关闭")
        st.caption(
            "向量索引只缓存已审核工具文本的派生向量；SQLite 中的审核知识才是权威来源。"
            "模型权重不存在时，P0-B 会退回关键词检索，而不是向云端发送内容。"
        )

    with traces:
        st.subheader("最近检索记录（脱敏）")
        query_rows = _safe_query_rows(store)
        if query_rows:
            st.dataframe(query_rows, use_container_width=True, hide_index=True)
        else:
            st.info("尚无记录。")

        st.subheader("最近 P0-C 证据建议（脱敏）")
        advisory_rows = _safe_advisory_rows(store)
        if advisory_rows:
            st.dataframe(advisory_rows, use_container_width=True, hide_index=True)
        else:
            st.info("尚无记录。")

        st.subheader("最近 Bad case（脱敏）")
        bad_case_rows = _safe_bad_case_rows(store)
        if bad_case_rows:
            st.dataframe(bad_case_rows, use_container_width=True, hide_index=True)
        else:
            st.info("尚无记录。")

    with governance:
        left, right = st.columns(2)
        with left:
            _render_count_chart(
                "知识生命周期",
                snapshot["knowledge_lifecycle"],
                "尚未导入审核知识。",
            )
        with right:
            _render_count_chart(
                "检索任务节点",
                snapshot["query_stages"],
                "尚无检索任务。",
            )

        st.subheader("已审核来源卡目录（不展示正文）")
        st.dataframe(store.knowledge_catalog(), use_container_width=True, hide_index=True)
        st.caption(
            "新增 Provider 不能只靠这张卡：仍必须经历 Card、Adapter、权限/预算、真实回执、"
            "Gold 回归和产品冻结，才能进入 reviewed_active。"
        )

        st.subheader("知识生命周期审计（明确触发、只生成建议）")
        st.caption(
            "审计会检查待复审、到期、撤回、冲突、尚未生效和派生索引失配；不会自动改状态、"
            "发布候选、删除资料或重建索引。"
        )
        if st.button("运行一次生命周期审计", key="run_rag_lifecycle_audit"):
            lifecycle_run = audit_rag_lifecycle(store, dense_index=dense_index, persist=True)
            st.success(
                f"已记录审计 {lifecycle_run.audit.audit_id}；索引状态："
                f"{lifecycle_run.audit.index.status.value}。未修改知识状态。"
            )
            st.dataframe(
                _safe_lifecycle_rows(lifecycle_run.audit),
                use_container_width=True,
                hide_index=True,
            )
            st.json({"trace": list(lifecycle_run.trace)})
        else:
            recent_audits = store.recent_lifecycle_audits(limit=1)
            if recent_audits:
                latest = recent_audits[0]
                audit_payload = latest["audit"]
                if isinstance(audit_payload, dict):
                    st.info(
                        f"最近审计：{latest['created_at']}；索引状态："
                        f"{audit_payload.get('index', {}).get('status', 'unknown')}；"
                        f"问题摘要：{audit_payload.get('issue_counts', {}) or '无'}"
                    )
            else:
                st.info("尚未运行生命周期审计；点击上方按钮生成第一条可回放记录。")

        _render_report_collection()


if __name__ == "__main__":
    main()
