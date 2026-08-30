"""Audit-only lifecycle checks for the reviewed RAG knowledge authority.

The lifecycle audit turns the documented refresh rules into a repeatable,
observable check.  It never changes a ``KnowledgeItem`` status, publishes a
candidate source, deletes a source, rebuilds an index, or grants a Provider
permission.  A human must review the resulting action suggestions.
"""

from __future__ import annotations

import html
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from portrait_consistency_agent.core.rag_contracts import (
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    RagIndexAudit,
    RagIndexStatus,
    RagLifecycleAction,
    RagLifecycleAudit,
    RagLifecycleIssueCode,
    RagLifecycleItemAudit,
)
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

RAG_LIFECYCLE_AUDIT_VERSION = "rag-lifecycle-audit-v0.1"


@dataclass(frozen=True)
class RagLifecycleRun:
    """One safe lifecycle audit and its redacted replay trace."""

    audit: RagLifecycleAudit
    trace: tuple[dict[str, object], ...]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    """Make legacy naive fixture timestamps comparable without changing them."""

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _item_audit(
    *,
    item: KnowledgeItem,
    chunk_count: int,
    now: datetime,
) -> RagLifecycleItemAudit:
    status = item.lifecycle_status
    effective_from = _aware(item.effective_from)
    review_due_at = _aware(item.review_due_at)
    expires_at = _aware(item.expires_at) if item.expires_at else None
    issues: list[RagLifecycleIssueCode] = []

    if status == KnowledgeLifecycleStatus.WITHDRAWN:
        issues.append(RagLifecycleIssueCode.WITHDRAWN)
    if status == KnowledgeLifecycleStatus.EXPIRED or (expires_at is not None and expires_at <= now):
        issues.append(RagLifecycleIssueCode.EXPIRED)
    if status == KnowledgeLifecycleStatus.CONFLICTED_PENDING_REVIEW:
        issues.append(RagLifecycleIssueCode.CONFLICT_PENDING_REVIEW)
    if status == KnowledgeLifecycleStatus.CANDIDATE:
        issues.append(RagLifecycleIssueCode.CANDIDATE_NOT_PUBLISHED)
    if effective_from > now:
        issues.append(RagLifecycleIssueCode.NOT_YET_EFFECTIVE)
    if status == KnowledgeLifecycleStatus.REVIEWED_ACTIVE and review_due_at <= now:
        issues.append(RagLifecycleIssueCode.REVIEW_DUE)
    if not item.source_uris:
        issues.append(RagLifecycleIssueCode.MISSING_SOURCE_URI)
    if chunk_count == 0:
        issues.append(RagLifecycleIssueCode.ZERO_CHUNKS)

    blocked = {
        RagLifecycleIssueCode.EXPIRED,
        RagLifecycleIssueCode.WITHDRAWN,
        RagLifecycleIssueCode.CONFLICT_PENDING_REVIEW,
    }
    if any(code in blocked for code in issues):
        action = RagLifecycleAction.BLOCKED_FROM_RETRIEVAL
    elif RagLifecycleIssueCode.NOT_YET_EFFECTIVE in issues or (
        RagLifecycleIssueCode.CANDIDATE_NOT_PUBLISHED in issues
    ):
        action = RagLifecycleAction.HOLD_NOT_YET_EFFECTIVE
    elif issues:
        action = RagLifecycleAction.REVIEW_REQUIRED
    else:
        action = RagLifecycleAction.KEEP_ACTIVE

    return RagLifecycleItemAudit(
        knowledge_id=item.knowledge_id,
        provider=item.provider,
        operation=item.operation,
        source_version=item.source_version,
        lifecycle_status=status,
        effective_from=effective_from,
        review_due_at=review_due_at,
        expires_at=expires_at,
        chunk_count=chunk_count,
        source_uri_count=len(item.source_uris),
        issue_codes=issues,
        recommended_action=action,
    )


def _index_audit(
    *,
    dense_index: LocalDenseIndex | None,
    active_chunk_count: int,
) -> RagIndexAudit:
    if dense_index is None:
        return RagIndexAudit(
            status=RagIndexStatus.NOT_CHECKED,
            active_chunk_count=active_chunk_count,
            manifest_document_count=0,
            indexed_vector_count=0,
            reason_codes=["DENSE_INDEX_NOT_PROVIDED"],
        )
    try:
        manifests = dense_index.manifest_snapshot()
    except (OSError, sqlite3.Error):
        return RagIndexAudit(
            status=RagIndexStatus.UNAVAILABLE,
            active_chunk_count=active_chunk_count,
            manifest_document_count=0,
            indexed_vector_count=0,
            reason_codes=["DENSE_INDEX_UNAVAILABLE"],
        )
    if not manifests:
        return RagIndexAudit(
            status=RagIndexStatus.NOT_BUILT,
            active_chunk_count=active_chunk_count,
            manifest_document_count=0,
            indexed_vector_count=0,
            reason_codes=["NO_INDEX_MANIFEST"],
        )

    # The most recently written manifest is the one the local retriever would
    # use for this audit.  Older model revisions remain visible in the raw
    # SQLite file but never affect this status calculation.
    manifest = manifests[0]
    manifest_count = int(manifest["document_count"])
    vector_count = int(manifest["indexed_vector_count"])
    reasons: list[str] = []
    if manifest_count != active_chunk_count:
        reasons.append("ACTIVE_CHUNK_COUNT_MISMATCH")
    if vector_count != manifest_count:
        reasons.append("VECTOR_COUNT_MISMATCH")
    status = RagIndexStatus.IN_SYNC if not reasons else RagIndexStatus.STALE
    return RagIndexAudit(
        status=status,
        index_key=str(manifest["index_key"]),
        model_id=str(manifest["model_id"]),
        actual_revision=str(manifest["actual_revision"]),
        active_chunk_count=active_chunk_count,
        manifest_document_count=manifest_count,
        indexed_vector_count=vector_count,
        reason_codes=reasons,
    )


def audit_rag_lifecycle(
    store: LocalKnowledgeStore,
    *,
    dense_index: LocalDenseIndex | None = None,
    now: datetime | None = None,
    audit_id: str | None = None,
    persist: bool = True,
) -> RagLifecycleRun:
    """Audit lifecycle metadata and optionally persist the redacted result.

    ``persist=True`` records the audit in the RAG authority's audit table.  It
    still does not modify ``knowledge_items`` or the derived vector index.
    """

    as_of = _aware(now or utc_now())
    items = store.knowledge_lifecycle_items()
    item_audits = [
        _item_audit(item=item, chunk_count=chunk_count, now=as_of) for item, chunk_count in items
    ]
    issue_counts = Counter(issue.value for item in item_audits for issue in item.issue_codes)
    active_items = [
        item
        for item, _ in items
        if item.lifecycle_status == KnowledgeLifecycleStatus.REVIEWED_ACTIVE
        and _aware(item.effective_from) <= as_of
        and (item.expires_at is None or _aware(item.expires_at) > as_of)
    ]
    active_item_ids = {item.knowledge_id for item in active_items}
    active_chunk_count = sum(
        chunk_count for item, chunk_count in items if item.knowledge_id in active_item_ids
    )
    index = _index_audit(dense_index=dense_index, active_chunk_count=active_chunk_count)
    generated_id = audit_id or f"rag_lifecycle_audit_{int(as_of.timestamp() * 1_000_000)}"
    audit = RagLifecycleAudit(
        audit_id=generated_id,
        audit_version=RAG_LIFECYCLE_AUDIT_VERSION,
        as_of=as_of,
        knowledge_item_count=len(items),
        active_item_count=len(active_items),
        active_chunk_count=active_chunk_count,
        issue_counts=dict(sorted(issue_counts.items())),
        item_audits=item_audits,
        index=index,
    )
    action_counts = Counter(item.recommended_action.value for item in item_audits)
    trace: list[dict[str, object]] = [
        {
            "step": "authority_metadata_read",
            "knowledge_item_count": len(items),
            "active_item_count": len(active_items),
            "source_body_read": False,
            "user_photo_read": False,
            "raw_user_text_read": False,
            "network_called": False,
        },
        {
            "step": "lifecycle_classification",
            "issue_counts": dict(sorted(issue_counts.items())),
            "recommended_action_counts": dict(sorted(action_counts.items())),
            "knowledge_status_mutated": False,
            "candidate_published": False,
            "knowledge_deleted": False,
        },
        {
            "step": "derived_index_check",
            "status": index.status.value,
            "index_key": index.index_key,
            "active_chunk_count": index.active_chunk_count,
            "manifest_document_count": index.manifest_document_count,
            "indexed_vector_count": index.indexed_vector_count,
            "rebuild_triggered": False,
        },
        {
            "step": "audit_route",
            "audit_id": audit.audit_id,
            "recommended_next_step": "human_review_or_explicit_index_rebuild",
            "auto_status_change_allowed": False,
            "auto_publish_allowed": False,
            "external_calls": 0,
        },
    ]
    if persist:
        store.record_lifecycle_audit(audit=audit, trace=trace)
    return RagLifecycleRun(audit=audit, trace=tuple(trace))


def write_lifecycle_audit_report(
    run: RagLifecycleRun,
    *,
    json_path: Path,
    html_path: Path,
) -> None:
    """Write safe JSON/HTML artifacts for the local governance dashboard."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"audit": run.audit.model_dump(mode="json"), "trace": list(run.trace)}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_lifecycle_audit_html(run), encoding="utf-8")


def render_lifecycle_audit_html(run: RagLifecycleRun) -> str:
    """Render metadata-only lifecycle findings without source body text."""

    audit = run.audit
    issue_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.knowledge_id)}</td>"
        f"<td>{html.escape(item.provider)}</td>"
        f"<td>{html.escape(item.operation)}</td>"
        f"<td>{html.escape(item.source_version)}</td>"
        f"<td>{html.escape(', '.join(code.value for code in item.issue_codes) or 'none')}</td>"
        f"<td>{html.escape(item.recommended_action.value)}</td>"
        "</tr>"
        for item in audit.item_audits
    )
    issue_summary = (
        ", ".join(f"{html.escape(name)}={value}" for name, value in audit.issue_counts.items())
        or "none"
    )
    audit_time = html.escape(audit.as_of.isoformat())
    index_status = html.escape(audit.index.status.value)
    trace_json = html.escape(json.dumps(list(run.trace), ensure_ascii=False, indent=2))
    knowledge_count = audit.knowledge_item_count
    active_item_count = audit.active_item_count
    active_chunk_count = audit.active_chunk_count
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'>
<title>RAG 知识生命周期审计</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
max-width:1180px;margin:30px auto;padding:0 22px;color:#17202a}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:12px;margin:18px 0}}
.card{{border:1px solid #d9e2ec;border-radius:12px;padding:15px;background:#fff}}
.k{{font-size:13px;color:#5b6875}}.v{{font-size:23px;font-weight:700;margin-top:7px}}
.note{{background:#fff8e1;border-left:4px solid #f0ad00;padding:13px 16px;margin:18px 0}}
table{{border-collapse:collapse;width:100%;margin:12px 0 26px}}
th,td{{border:1px solid #d9e2ec;padding:9px;text-align:left;vertical-align:top}}
th{{background:#f5f7fa}}
</style></head><body>
<h1>RAG 知识生命周期审计</h1>
<p class='note'>本报告只检查知识元数据与派生索引计数。
它不会自动发布、删除、改状态、重建索引或授权工具；任何建议都需要人工审核。</p>
<div class='grid'>
<div class='card'><div class='k'>审计时间</div><div class='v'>{audit_time}</div></div>
<div class='card'><div class='k'>知识来源</div><div class='v'>{knowledge_count}</div></div>
<div class='card'><div class='k'>当前有效来源</div><div class='v'>{active_item_count}</div></div>
<div class='card'><div class='k'>当前有效规则</div><div class='v'>{active_chunk_count}</div></div>
<div class='card'><div class='k'>索引状态</div><div class='v'>{index_status}</div></div>
</div>
<h2>问题摘要</h2><p>{issue_summary}</p>
<h2>来源级结果（不含正文）</h2>
<table><thead><tr><th>来源</th><th>Provider</th><th>操作</th><th>版本</th><th>问题</th><th>建议动作</th></tr></thead>
<tbody>{issue_rows}</tbody></table>
<h2>可回放 Trace</h2><pre>{trace_json}</pre>
</body></html>"""
