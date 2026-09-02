"""Allow-listed local RAG reports for the read-only Streamlit dashboards.

The dashboard must never discover arbitrary files below the project root.  A
small explicit registry makes the two evaluation reports and the aggregate
failure-analysis report visible while keeping the product-owner answer key,
photos, SQLite files and traces outside the UI boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RagReportArtifact:
    """One safe, generated report that may be shown in a local dashboard."""

    key: str
    title: str
    filename: str
    description: str
    scope: str

    def path(self, project_root: Path) -> Path:
        """Resolve the allow-listed report below ``<root>/reports``."""

        reports_root = (project_root / "reports").resolve()
        candidate = (reports_root / self.filename).resolve()
        if candidate.parent != reports_root:
            raise ValueError("RAG report must remain directly under the reports directory")
        return candidate


RAG_REPORT_ARTIFACTS: tuple[RagReportArtifact, ...] = (
    RagReportArtifact(
        key="public_evaluation",
        title="Gold Set v2｜公开集评测",
        filename="rag_gold_v2_baseline_evaluation.html",
        description="52 道公开 dev/challenge 题的离线指标与安全结果。",
        scope="public_aggregate",
    ),
    RagReportArtifact(
        key="holdout_aggregate",
        title="Gold Set v2｜隐藏集聚合评测",
        filename="rag_gold_v2_holdout_private_aggregate.html",
        description="仅展示隐藏集聚合指标，不包含题干、案例编号或答案。",
        scope="private_holdout_aggregate_only",
    ),
    RagReportArtifact(
        key="failure_analysis",
        title="RAG｜失败模式与优化 SOP",
        filename="rag_failure_patterns_v1.html",
        description="公开集诊断与隐藏集聚合错误类型的脱敏分析。",
        scope="public_aggregate_plus_private_aggregate_only",
    ),
    RagReportArtifact(
        key="lifecycle_audit",
        title="RAG｜知识生命周期审计",
        filename="rag_lifecycle_audit.html",
        description="来源生命周期、复审提醒和派生索引一致性的脱敏审计。",
        scope="knowledge_metadata_only",
    ),
    RagReportArtifact(
        key="optimization_loop",
        title="RAG｜自动优化迭代 Dashboard",
        filename="rag_optimization_loop_v1.html",
        description="公开集逐题诊断、候选代际回归、Rubric 和反过拟合状态。",
        scope="public_iteration_plus_private_aggregate_context",
    ),
    RagReportArtifact(
        key="failure_driven_loop",
        title="RAG｜失败驱动优化 Dashboard",
        filename="rag_failure_driven_loop_v1.html",
        description="新失败驱动开发集上的查询编译候选、根因和版本化回归。",
        scope="owner_review_required_development_set_only",
    ),
    RagReportArtifact(
        key="v3_validation_diagnostics",
        title="RAG｜V3 解冻验证集逐题诊断",
        filename="rag_v3_validation_diagnostics_v1.html",
        description="产品负责人明确解冻后的 V3 验证集：逐题结论、完整安全 Trace 与公开回归守门。",
        scope="owner_unlocked_validation_only",
    ),
    RagReportArtifact(
        key="v4_holdout_blind_aggregate",
        title="RAG｜V4 独立 Holdout 盲测聚合",
        filename="rag_v4_holdout_blind_aggregate.html",
        description="V4 一次性 answerless 盲测的聚合指标；不展示题目、案例编号或答案键。",
        scope="independent_holdout_aggregate_only",
    ),
    RagReportArtifact(
        key="v4_validation_diagnostics",
        title="RAG｜V4 解冻验证集逐题诊断",
        filename="rag_v4_validation_diagnostics_v1.html",
        description="盲测快照封存后、经产品负责人授权的 V4 逐题失败模式、Trace 与候选修正。",
        scope="owner_unlocked_v4_validation_only",
    ),
    RagReportArtifact(
        key="low_success_reflection_audit",
        title="RAG｜低成功率反思审计",
        filename="rag_low_success_reflection_audit.html",
        description="只读公开事实审计：拆分上游查询、真实检索、知识覆盖、评测口径和泛化风险。",
        scope="public_artifacts_only_no_promotion",
    ),
    RagReportArtifact(
        key="fair_process_audit",
        title="RAG｜公平评测过程监督",
        filename="rag_fair_process_audit_v1.html",
        description="独立过程考官检查 V3/V4 每题是否完整进入 RAG，以及答案/投影/外部调用是否泄露。",
        scope="answerless_process_integrity_only",
    ),
    RagReportArtifact(
        key="fair_gold_join",
        title="RAG｜公平 Gold 连接与双轨基线（口径修正版）",
        filename="rag_fair_gold_join_v2.html",
        description=(
            "过程门通过后，一次性连接负责人 Gold，分开展示编译轨道与真实检索轨道；"
            "检索轨道不把路由混入评分。"
        ),
        scope="private_gold_join_aggregate_only_corrected_metric_scope",
    ),
    RagReportArtifact(
        key="fair_gold_join_v1_historical",
        title="RAG｜公平 Gold 连接与双轨基线（历史口径）",
        filename="rag_fair_gold_join_v1.html",
        description="保留 v0.1 历史聚合结果；其中检索轨道曾混入下游路由分数，仅供审计对照。",
        scope="historical_private_gold_join_aggregate_only",
    ),
    RagReportArtifact(
        key="policy_coverage_candidate",
        title="RAG｜Policy Card 覆盖与操作覆盖候选",
        filename="rag_policy_coverage_candidate_v2.html",
        description=(
            "公开开发/回归候选：查询编译、Policy Card、关系判定和多操作覆盖的逐轨指标；"
            "不改现役 baseline。"
        ),
        scope="public_candidate_only_no_promotion",
    ),
    RagReportArtifact(
        key="candidate_diagnostics",
        title="RAG｜候选逐题失败诊断",
        filename="rag_candidate_diagnostics_v1.html",
        description="公开开发/回归候选的逐题变化、根因和 SOP，不含 V3/V4 私有答案。",
        scope="public_candidate_diagnostics_only",
    ),
    RagReportArtifact(
        key="v5_holdout_process_audit",
        title="RAG｜V5 独立 Holdout 过程监督",
        filename="rag_v5_holdout_process_audit.html",
        description="V5 60 题答案盲运行的完整性与泄露检查聚合，不含题目和质量分数。",
        scope="answerless_process_integrity_only",
    ),
    RagReportArtifact(
        key="v5_holdout_gold_aggregate",
        title="RAG｜V5 独立 Holdout Gold 聚合评分",
        filename="rag_v5_holdout_gold_aggregate.html",
        description=(
            "负责人授权后的 V5 一次性聚合评分；不展示题目、案例编号、Gold 答案或私有答案键。"
        ),
        scope="owner_authorised_private_gold_aggregate_only",
    ),
    RagReportArtifact(
        key="v5_failure_analysis",
        title="RAG｜V5 失败模式聚合分析",
        filename="rag_v5_failure_analysis_v1.html",
        description=("V5 Gold join 的脱敏失败模式、根因和下一步 SOP；不输出逐题内容，不自动调参。"),
        scope="owner_authorised_aggregate_diagnosis_only",
    ),
)


def available_rag_reports(project_root: Path) -> tuple[tuple[RagReportArtifact, Path], ...]:
    """Return only existing allow-listed reports, never arbitrary files."""

    return tuple(
        (artifact, artifact.path(project_root))
        for artifact in RAG_REPORT_ARTIFACTS
        if artifact.path(project_root).is_file()
    )


def read_rag_report(artifact: RagReportArtifact, project_root: Path) -> str:
    """Read one allow-listed report for an inline local preview."""

    path = artifact.path(project_root)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")
