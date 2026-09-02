"""Generate a public-artifact-only audit of persistently low RAG scores.

The audit is intentionally different from a quality run.  It reads only
answerless V4 aggregate/trace files, the public evaluation, the public
failure-driven loop and the lifecycle summary.  It does not read any private
answer key, unlocked validation case, photo, vector, secret or user message.
It reports where the measurement and product boundaries diverge; it never
changes the active baseline or a knowledge item.
"""

# The report renderer contains long Chinese prose and inline CSS/HTML templates.
# Keep those literal lines readable in the generated report; other lint rules
# remain enabled for the script.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = (PROJECT_ROOT / "reports").resolve()
DEFAULT_OUTPUT = REPORTS_ROOT / "rag_low_success_reflection_audit.json"
DEFAULT_HTML = REPORTS_ROOT / "rag_low_success_reflection_audit.html"

_ALLOWED_REPORTS = frozenset(
    {
        "rag_v4_holdout_blind_aggregate.json",
        "rag_v4_holdout_blind_trace.json",
        "rag_gold_v2_baseline_evaluation.json",
        "rag_failure_driven_loop_v1.json",
        "rag_lifecycle_audit.json",
    }
)
_ALLOWED_SOURCE_FILES = frozenset(
    {
        "src/portrait_consistency_agent/services/rag_gold_baseline.py",
        "src/portrait_consistency_agent/services/rag_p0b.py",
        "src/portrait_consistency_agent/services/rag_gold_eval.py",
        "src/portrait_consistency_agent/services/rag_advisory.py",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved.parent != REPORTS_ROOT or resolved.name not in _ALLOWED_REPORTS:
        raise ValueError(f"audit input is not an allow-listed public report: {path}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"audit input must be a JSON object: {path}")
    return payload


def _read_source(relative: str) -> str:
    if relative not in _ALLOWED_SOURCE_FILES:
        raise ValueError(f"source is not allow-listed: {relative}")
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _pct(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _max_reachable_fixed_precision(metrics: dict[str, Any]) -> float | None:
    """Compute the best possible fixed P@3 for the observed Gold sizes.

    This is a diagnostic bound, not a replacement for the frozen project
    metric.  With a Gold set of one or two evidence items, a fixed denominator
    of three cannot reach 1.0 even when every returned item is correct.
    """

    groups = metrics.get("precision_by_gold_evidence_count")
    if not isinstance(groups, dict):
        return None
    total = 0
    numerator = 0.0
    for count_text, row in groups.items():
        if not isinstance(row, dict):
            continue
        try:
            gold_count = int(count_text)
            cases = int(row.get("cases", 0))
        except (TypeError, ValueError):
            continue
        if gold_count < 0 or cases < 0:
            continue
        total += cases
        numerator += cases * min(gold_count, 3) / 3
    return numerator / total if total else None


def _metric_subset(metrics: dict[str, Any]) -> dict[str, object]:
    names = (
        "route_accuracy",
        "evidence_exact_accuracy",
        "evidence_relation_accuracy",
        "precision_at_3",
        "precision_at_3_effective",
        "precision_at_3_returned",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "hard_safety_gate",
        "project_threshold_gate",
    )
    return {name: metrics.get(name) for name in names}


def _code_boundary_facts() -> dict[str, object]:
    baseline = _read_source("src/portrait_consistency_agent/services/rag_gold_baseline.py")
    p0b = _read_source("src/portrait_consistency_agent/services/rag_p0b.py")
    evaluator = _read_source("src/portrait_consistency_agent/services/rag_gold_eval.py")
    advisory = _read_source("src/portrait_consistency_agent/services/rag_advisory.py")
    return {
        "gold_runner_declares_evaluation_bridge": "evaluation bridge" in baseline,
        "gold_runner_uses_projection_route": "projection.route_override" in baseline,
        "gold_runner_uses_fixture_embedding": "DeterministicTokenEmbeddingBackend" in baseline,
        "gold_runner_uses_fixture_reranker": "TokenOverlapReranker" in baseline,
        "p0b_requires_validated_rag_query": "validated ``RagQuery``" in p0b,
        "advisory_execution_is_false": "execution_authorized=False" in advisory,
        "evaluator_has_fixed_precision_formula": "precision_at_3" in evaluator
        and "gold_evidence_count" in evaluator,
    }


def build_audit(
    *,
    v4_aggregate_path: Path,
    v4_trace_path: Path,
    public_evaluation_path: Path,
    failure_loop_path: Path,
    lifecycle_path: Path,
) -> dict[str, object]:
    v4_aggregate = _read_json(v4_aggregate_path)
    v4_trace = _read_json(v4_trace_path)
    public = _read_json(public_evaluation_path)
    failure_loop = _read_json(failure_loop_path)
    lifecycle = _read_json(lifecycle_path)

    v4_metrics = v4_aggregate.get("metrics", {})
    v4_metrics = v4_metrics if isinstance(v4_metrics, dict) else {}
    public_metrics = public.get("metrics", {})
    public_metrics = public_metrics if isinstance(public_metrics, dict) else {}
    traces = v4_trace.get("traces", [])
    traces = traces if isinstance(traces, list) else []
    structured_count = sum(
        1 for row in traces if isinstance(row, dict) and row.get("structured_query_created") is True
    )
    retrieval_count = sum(
        1 for row in traces if isinstance(row, dict) and bool(row.get("retrieval_trace"))
    )
    category_counts = Counter(
        category
        for row in traces
        if isinstance(row, dict)
        for category in row.get("category_codes", [])
        if isinstance(category, str)
    )

    lifecycle_audit = lifecycle.get("audit", {})
    lifecycle_audit = lifecycle_audit if isinstance(lifecycle_audit, dict) else {}
    lifecycle_index = lifecycle_audit.get("index", {})
    lifecycle_index = lifecycle_index if isinstance(lifecycle_index, dict) else {}

    generations = failure_loop.get("generations", [])
    generations = generations if isinstance(generations, list) else []
    generation_summary: list[dict[str, object]] = []
    for generation in generations:
        if not isinstance(generation, dict):
            continue
        metrics = generation.get("metrics", {})
        metrics = metrics if isinstance(metrics, dict) else {}
        generation_summary.append(
            {
                "generation_id": generation.get("generation_id"),
                "version": generation.get("version"),
                "changed_prediction_count": generation.get("changed_prediction_count"),
                "composite_score": generation.get("composite_score"),
                "composite_gain_vs_previous": generation.get("composite_gain_vs_previous"),
                "route_accuracy": metrics.get("route_accuracy"),
                "evidence_relation_accuracy": metrics.get("evidence_relation_accuracy"),
                "recall_at_5": metrics.get("recall_at_5"),
                "regression_gate": generation.get("regression_gate"),
                "promotion_decision": generation.get("promotion_decision"),
            }
        )

    v4_max_fixed_precision = _max_reachable_fixed_precision(v4_metrics)
    public_max_fixed_precision = _max_reachable_fixed_precision(public_metrics)
    facts = {
        "v4_blind": {
            "case_count": v4_aggregate.get("case_count"),
            "metrics": _metric_subset(v4_metrics),
            "max_reachable_fixed_precision_at_3": v4_max_fixed_precision,
            # The aggregate was produced after the owner's separate private
            # scoring step.  This audit itself never opens that key; keeping
            # both facts prevents a historical report flag from being
            # mistaken for a new answer-key read.
            "current_audit_read_answer_key": False,
            "source_aggregate_historical_key_flag": v4_aggregate.get("hidden_answer_key_read"),
            "network_called": v4_aggregate.get("network_called"),
            "llm_called": v4_aggregate.get("llm_called"),
            "photo_or_face_vector_read": v4_aggregate.get("photo_or_face_vector_read"),
        },
        "v4_trace_boundary": {
            "trace_count": len(traces),
            "structured_query_created_count": structured_count,
            "structured_query_not_created_count": len(traces) - structured_count,
            "retrieval_trace_present_count": retrieval_count,
            "category_counts": dict(category_counts),
            "raw_prompt_persisted_count": sum(
                1
                for row in traces
                if isinstance(row, dict) and row.get("raw_prompt_persisted") is True
            ),
        },
        "public_regression": {
            "case_count": public.get("counts", {}).get("cases")
            if isinstance(public.get("counts"), dict)
            else None,
            "metrics": _metric_subset(public_metrics),
            "max_reachable_fixed_precision_at_3": public_max_fixed_precision,
        },
        "knowledge_snapshot": {
            "knowledge_items": lifecycle_audit.get("knowledge_item_count"),
            "active_items": lifecycle_audit.get("active_item_count"),
            "active_chunks": lifecycle_audit.get("active_chunk_count"),
            "issue_counts": lifecycle_audit.get("issue_counts"),
            "index_status": lifecycle_index.get("status"),
            "indexed_vectors": lifecycle_index.get("indexed_vector_count"),
        },
        "failure_driven_loop": {
            "dataset_version": failure_loop.get("dataset_version"),
            "generations": generation_summary,
            "active_baseline_unchanged": failure_loop.get("anti_overfit", {})
            .get("checks", {})
            .get("active_baseline_changed", {})
            .get("passed")
            if isinstance(failure_loop.get("anti_overfit"), dict)
            else None,
        },
        "code_boundary_facts": _code_boundary_facts(),
    }

    findings = [
        {
            "id": "R1_measurement_boundary",
            "rank": 1,
            "severity": "critical",
            "title": "大多数 V4 题没有真正进入检索",
            "fact": f"V4 盲测 {len(traces)} 题中只有 {retrieval_count} 题留下检索 Trace，{len(traces) - retrieval_count} 题在结构化查询之前就结束。",
            "meaning": "因此低路由分数主要反映‘自然语言有没有被整理成检索请求’，不能直接解释成向量召回或重排序算法失败。",
            "confidence": "high",
            "evidence": [
                "reports/rag_v4_holdout_blind_trace.json",
                "src/portrait_consistency_agent/services/rag_p0b.py:RagP0BHybridRetriever.retrieve",
            ],
        },
        {
            "id": "R2_projection_injection",
            "rank": 2,
            "severity": "critical",
            "title": "评测结果混入了上游投影事实",
            "fact": "Gold runner 的 Prediction 会先使用 projection 的路由/证据别名，再追加检索结果；P/FX 等评测别名也不是当前三张 Provider Card 的可检索知识。",
            "meaning": "候选即使改变了投影规则，也可能改变分数而不是改变‘检索器找到并采用了哪条真实知识’；这让 RAG 成功率和查询理解成功率混在一起。",
            "confidence": "high",
            "evidence": [
                "src/portrait_consistency_agent/services/rag_gold_baseline.py:project_runtime_prompt, _run_case",
                "src/portrait_consistency_agent/services/rag_p0a.py:seed_reviewed_provider_knowledge",
            ],
        },
        {
            "id": "R3_corpus_coverage",
            "rank": 3,
            "severity": "high",
            "title": "知识库太小，无法支撑题目要求的全部政策判断",
            "fact": f"生命周期审计显示只有 {lifecycle_audit.get('knowledge_item_count')} 张审核知识卡、{lifecycle_audit.get('active_chunk_count')} 条有效规则；当前主要是 BeautifyPic、CompareFace、ImageModeration。",
            "meaning": "题目要求回答的隐私、同意、过期、冲突、提示注入和反馈规则，并没有都作为可检索的一手知识进入权威库，很多判断只能靠编译器或评测别名补出来。",
            "confidence": "high",
            "evidence": [
                "reports/rag_lifecycle_audit.json",
                "src/portrait_consistency_agent/services/rag_p0a.py:seed_reviewed_provider_knowledge",
            ],
        },
        {
            "id": "R4_fixture_retrieval_backend",
            "rank": 4,
            "severity": "high",
            "title": "盲测使用的是离线测试后端，不是真正的语义模型链路",
            "fact": "Gold baseline 明确使用 deterministic token embedding 和 token-overlap reranker；它们用于可重复测试，不等于 BGE 的语义检索效果。",
            "meaning": "这能保证离线安全和可重复，但不能用来判断真实 BGE 语义模型是否能理解同义表达；同时 V4 大多数题没有进入检索，所以换排序模型不会解决主问题。",
            "confidence": "high",
            "evidence": [
                "src/portrait_consistency_agent/services/rag_gold_baseline.py:RagGoldDeterministicBaseline._run",
                "src/portrait_consistency_agent/services/local_rag_models.py:DeterministicTokenEmbeddingBackend/TokenOverlapReranker",
            ],
        },
        {
            "id": "R5_metric_unreachable",
            "rank": 5,
            "severity": "high",
            "title": "固定 Precision@3 的项目门槛在当前 Gold 结构下数学上不可达",
            "fact": f"按 V4 的 Gold 条数分布，固定 Precision@3 的理论最高值约为 {v4_max_fixed_precision:.4f}；公开集约为 {public_max_fixed_precision:.4f}，即使所有返回证据都正确也达不到 0.80。",
            "meaning": "固定 Precision 的低分需要作为评测治理问题单独处理，不能继续用它指导检索器调参，也不能偷偷改掉已冻结的项目 Gate。",
            "confidence": "high",
            "evidence": [
                "reports/rag_v4_holdout_blind_aggregate.json:precision_by_gold_evidence_count",
                "src/portrait_consistency_agent/services/rag_gold_eval.py:precision_at_k",
            ],
        },
        {
            "id": "R6_validation_overfit",
            "rank": 6,
            "severity": "high",
            "title": "解冻验证副本的高分不能证明泛化",
            "fact": "V3/V4 答案授权后才产生逐题诊断和候选；候选在验证副本达到 100% 只说明它能解释这批已看过的题，原始 V4 盲测仍是低分。",
            "meaning": "之前的迭代顺序没有根本错误，但实验对象已经从‘未知考试’变成‘看过答案后的练习题’；继续在同一副本上迭代只会增加过拟合风险。",
            "confidence": "high",
            "evidence": [
                "docs/RAG_V4_HOLDOUT.md:解冻后的逐题诊断",
                "reports/rag_v4_validation_diagnostics_v1.json:generations",
                "reports/rag_v4_holdout_blind_aggregate.json:metrics",
            ],
        },
        {
            "id": "R7_layer_contract_gap",
            "rank": 7,
            "severity": "medium",
            "title": "线上链路和离线盲测链路不是同一个对象",
            "fact": "线上先由 DeepSeek 把用户文字解析成 IntentFrame，再由应用生成 RagQuery；V4 blind runner 为了离线可重复，刻意不调用 LLM，使用 phrase projector。",
            "meaning": "V4 分数不能直接当作线上 IntentFrame Agent 的成功率；线上也不能因为离线候选分数高就宣称已验证。两条链路必须拆开评测。",
            "confidence": "high",
            "evidence": [
                "app.py:DeepSeekIntentAdapter → build_plan_advisory_query",
                "src/portrait_consistency_agent/services/rag_gold_baseline.py:project_runtime_prompt",
                "reports/rag_v4_holdout_blind_aggregate.json:llm_called",
            ],
        },
    ]

    recommendations = [
        {
            "priority": 1,
            "action": "先拆成两条评测轨道",
            "detail": "轨道 A 只接受已经构造好的 RagQuery，Gold 直接引用真实可索引 chunk ID 和 direct/reference/conflict 关系；轨道 B 只测原始自然语言到结构化查询和路由。Prediction 必须来自被测层，不能由 projection 预先注入。",
            "success": "能分别回答‘理解错了’还是‘检索错了’，且每条证据都有真实来源。",
        },
        {
            "priority": 2,
            "action": "把缺失的政策事实整理成审核知识",
            "detail": "隐私、出站同意、过期、撤回、冲突、提示注入、未知/人工复核等规则如果要由 RAG 查到，就需要版本化 Policy/Rule Card；在没有入库前，不把 P/FX 评测别名当作真实召回。",
            "success": "每个被评分的证据都能追到审核来源、版本和生命周期状态。",
        },
        {
            "priority": 3,
            "action": "先用 10–15 道公开 smoke 验证检索真的被执行",
            "detail": "覆盖同义词、多意图、权限冲突和过期四类题；逐条检查自然语言、结构化查询、候选排名、采用证据和最终路由。通过后才讨论是否重新校准 Precision/阈值和建立新的独立 Holdout。",
            "success": "每题都有完整‘输入→查询→召回→采用→路由’Trace，且候选改变了真实检索输入/结果，不只是改标签。",
        },
    ]

    return {
        "audit_version": "rag-low-success-reflection-audit-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_no_promotion",
        "scope": {
            "read_only_public_artifacts": True,
            "private_answer_key_read": False,
            "unlocked_validation_case_read": False,
            "photo_or_face_vector_read": False,
            "network_called": False,
            "llm_called": False,
            "provider_called": False,
            "active_baseline_changed": False,
        },
        "headline": "当前低成功率首先是评测对象和系统边界错位，其次才是检索质量问题；在拆开两层之前继续加题或调排序模型，不能得到可信增益。",
        "facts": facts,
        "findings": findings,
        "recommendations": recommendations,
        "next_gate": {
            "name": "评测合同与真实检索边界 Gate",
            "not_a_quality_pass": True,
            "owner_decisions_needed": [
                "是否接受把‘自然语言→结构化查询’与‘结构化查询→真实知识召回’拆成两套指标和数据集",
                "是否把隐私/生命周期/冲突规则整理成可审核的 Policy/Rule Card 后再纳入检索质量评分",
                "是否在保留历史固定 Precision@3 的前提下，新增不受稀疏 Gold 影响的诊断口径，并把两者明确分开",
            ],
        },
    }


def _render_table(rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for label, _ in columns)
    body: list[str] = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(key, '—')))}</td>" for _, key in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_html(report: dict[str, object]) -> str:
    facts = report.get("facts", {})
    facts = facts if isinstance(facts, dict) else {}
    v4 = facts.get("v4_blind", {})
    v4 = v4 if isinstance(v4, dict) else {}
    trace = facts.get("v4_trace_boundary", {})
    trace = trace if isinstance(trace, dict) else {}
    findings = report.get("findings", [])
    findings = findings if isinstance(findings, list) else []
    recommendations = report.get("recommendations", [])
    recommendations = recommendations if isinstance(recommendations, list) else []
    finding_rows = [
        {
            "优先级": item.get("rank"),
            "问题": item.get("title"),
            "严重度": item.get("severity"),
            "结论": item.get("meaning"),
        }
        for item in findings
        if isinstance(item, dict)
    ]
    recommendation_rows = [
        {
            "优先级": item.get("priority"),
            "动作": item.get("action"),
            "通过标准": item.get("success"),
        }
        for item in recommendations
        if isinstance(item, dict)
    ]
    metrics = v4.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    metric_rows = [
        {"指标": key, "V4 盲测": value}
        for key, value in metrics.items()
        if key
        in {
            "route_accuracy",
            "evidence_relation_accuracy",
            "precision_at_3",
            "precision_at_3_effective",
            "recall_at_5",
            "mrr",
            "ndcg_at_5",
            "hard_safety_gate",
            "project_threshold_gate",
        }
    ]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>RAG 低成功率反思审计</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;max-width:1180px;margin:32px auto;padding:0 20px;color:#242133;line-height:1.6;background:#fbf9fd}}
h1{{margin-bottom:4px}} h2{{margin-top:28px;color:#5d426c}} .notice{{padding:14px 18px;background:#fff0f0;border-left:5px solid #c00000;margin:16px 0}} .cards{{display:flex;gap:12px;flex-wrap:wrap}} .card{{background:#fff;padding:14px 18px;border:1px solid #e4ddea;border-radius:10px;min-width:180px}} .num{{font-size:24px;font-weight:700}} table{{border-collapse:collapse;width:100%;background:#fff;margin:10px 0 20px}} th,td{{border:1px solid #e5dfeb;padding:9px;vertical-align:top;text-align:left}} th{{background:#f0e8f4}} code{{background:#f2eef5;padding:2px 4px;border-radius:4px}} .small{{color:#665d6d;font-size:13px}}
</style></head><body>
<h1>RAG 低成功率反思审计</h1>
<p class="small">版本：{html.escape(str(report.get("audit_version")))}｜状态：{html.escape(str(report.get("status")))}</p>
<div class="notice"><strong>一句话结论：</strong>{html.escape(str(report.get("headline")))}<br><strong>本报告不是质量通过。</strong>它只回答“为什么目前的分数不能直接说明检索器好坏”。</div>
<h2>先看最关键的事实</h2>
<div class="cards">
<div class="card">V4 题目<div class="num">{html.escape(str(v4.get("case_count", "—")))}</div></div>
<div class="card">真正留下检索 Trace<div class="num">{html.escape(str(trace.get("retrieval_trace_present_count", "—")))}</div></div>
<div class="card">没有生成结构化查询<div class="num">{html.escape(str(trace.get("structured_query_not_created_count", "—")))}</div></div>
<div class="card">固定 P@3 理论上限<div class="num">{html.escape(str(v4.get("max_reachable_fixed_precision_at_3", "—")))}</div></div>
</div>
<h2>V4 盲测当前数字</h2>
{_render_table(metric_rows, [("指标", "指标"), ("V4 盲测", "V4 盲测")])}
<p class="small">固定 P@3 的理论上限是按每题 Gold 证据条数计算的数学上限，不是把项目门槛改掉；历史冻结 Gate 仍保留。</p>
<h2>根因排序</h2>
{_render_table(finding_rows, [("优先级", "优先级"), ("问题", "问题"), ("严重度", "严重度"), ("为什么重要", "结论")])}
<h2>最小下一步</h2>
{_render_table(recommendation_rows, [("优先级", "优先级"), ("动作", "动作"), ("通过标准", "通过标准")])}
<h2>边界声明</h2>
<p>本审计只读取公开聚合、answerless Trace、公开评测、失败驱动公开实验和生命周期摘要；不读取新的隐藏答案、不调用网络/LLM/Provider、不改变 active baseline。RAG 继续保持 <code>proposal-only</code>。</p>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument(
        "--v4-aggregate",
        type=Path,
        default=REPORTS_ROOT / "rag_v4_holdout_blind_aggregate.json",
    )
    parser.add_argument(
        "--v4-trace",
        type=Path,
        default=REPORTS_ROOT / "rag_v4_holdout_blind_trace.json",
    )
    parser.add_argument(
        "--public-evaluation",
        type=Path,
        default=REPORTS_ROOT / "rag_gold_v2_baseline_evaluation.json",
    )
    parser.add_argument(
        "--failure-loop",
        type=Path,
        default=REPORTS_ROOT / "rag_failure_driven_loop_v1.json",
    )
    parser.add_argument(
        "--lifecycle",
        type=Path,
        default=REPORTS_ROOT / "rag_lifecycle_audit.json",
    )
    args = parser.parse_args()
    report = build_audit(
        v4_aggregate_path=args.v4_aggregate,
        v4_trace_path=args.v4_trace,
        public_evaluation_path=args.public_evaluation,
        failure_loop_path=args.failure_loop,
        lifecycle_path=args.lifecycle,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(render_html(report), encoding="utf-8")
    trace = report["facts"]["v4_trace_boundary"]
    v4 = report["facts"]["v4_blind"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "v4_cases": v4["case_count"],
                "retrieval_trace_present": trace["retrieval_trace_present_count"],
                "structured_query_not_created": trace["structured_query_not_created_count"],
                "v4_route_accuracy": v4["metrics"]["route_accuracy"],
                "v4_evidence_relation_accuracy": v4["metrics"]["evidence_relation_accuracy"],
                "v4_recall_at_5": v4["metrics"]["recall_at_5"],
                "output": str(args.output),
                "html": str(args.html),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
