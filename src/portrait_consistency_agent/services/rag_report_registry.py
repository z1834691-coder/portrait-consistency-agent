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
