"""Evidence-first E3 harness for the Tencent Effect Web candidate.

E3 is deliberately different from the offline contract regression in
``tencent_effect_web_regression``.  The regression suite proves that the
project-owned receipt/result boundary rejects tampering.  This module prepares
an owner-supplied set of real images and records only redacted preflight facts
so live browser receipts can be joined to the correct sample without copying
photos, result bytes or local paths into the repository.

    The harness never calls Tencent, promotes a Provider Card, or treats a good
    quality route as proof of visual improvement.  A successful preflight means
    only that a sample is eligible for a candidate Web trial; subject match,
    content safety, visual effect and vendor terms remain separate evidence.
"""

from __future__ import annotations

import hashlib
import html
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from portrait_consistency_agent.core.contracts import PhotoRole, QualityFlag
from portrait_consistency_agent.services.photo_quality import PhotoObservation, analyze_photo_bytes

E3_HARNESS_VERSION = "effect_web_e3_harness_v0.1"
E3_ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp"})
E3_MAX_SAMPLE_BYTES = 5_242_880

SampleRole = Literal["reference_candidate", "target"]
PreflightStatus = Literal["eligible", "warning", "rejected"]
LiveReceiptStatus = Literal["succeeded", "failed"]
VerificationHandoffStatus = Literal["not_run", "metadata_only", "completed", "failed"]

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,127}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class E3SampleSpec:
    """A user-authorized sample reference.

    ``path`` exists only while the runner reads the file.  It is intentionally
    excluded from all report projections.  ``angle``, ``lighting`` and
    ``expression`` are owner-provided strata labels; ``unknown`` is honest when
    the runner cannot infer a label from pixels.
    """

    sample_id: str
    path: Path
    role: SampleRole
    angle: str = "unknown"
    lighting: str = "unknown"
    expression: str = "unknown"


@dataclass(frozen=True)
class E3PreflightItem:
    sample_id: str
    role: SampleRole
    status: PreflightStatus
    file_name: str
    sha256: str
    bytes_read: int
    width: int | None
    height: int | None
    image_format: str | None
    face_count: int
    quality_confidence: float
    editability_confidence: float
    quality_flags: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    angle: str = "unknown"
    lighting: str = "unknown"
    expression: str = "unknown"

    def projection(self) -> dict[str, object]:
        """Return a safe manifest row with no local path or image payload."""

        return {
            "sample_id": self.sample_id,
            "role": self.role,
            "status": self.status,
            "file_name": self.file_name,
            "sha256": self.sha256,
            "bytes_read": self.bytes_read,
            "dimensions": (
                f"{self.width}x{self.height}"
                if self.width is not None and self.height is not None
                else None
            ),
            "image_format": self.image_format,
            "face_count": self.face_count,
            "quality_confidence": round(self.quality_confidence, 4),
            "editability_confidence": round(self.editability_confidence, 4),
            "quality_flags": list(self.quality_flags),
            "reason_codes": list(self.reason_codes),
            "strata": {
                "angle": self.angle,
                "lighting": self.lighting,
                "expression": self.expression,
            },
            "path_saved": False,
            "image_bytes_saved": False,
        }


@dataclass(frozen=True)
class E3PreflightReport:
    harness_version: str
    reference_sample_id: str | None
    total_samples: int
    eligible_samples: int
    warning_samples: int
    rejected_samples: int
    target_samples: int
    reference_present: bool
    batch_failure_isolation_ready: bool
    strata: dict[str, dict[str, int]]
    items: tuple[E3PreflightItem, ...] = field(default_factory=tuple)

    @property
    def ready_for_candidate_trials(self) -> bool:
        """Whether at least one reference and target passed basic preflight."""

        return (
            self.reference_present
            and self.target_samples > 0
            and self.eligible_samples + self.warning_samples >= 2
        )

    def projection(self) -> dict[str, object]:
        """JSON-safe report; never includes raw bytes or paths."""

        return {
            "harness_version": self.harness_version,
            "reference_sample_id": self.reference_sample_id,
            "total_samples": self.total_samples,
            "eligible_samples": self.eligible_samples,
            "warning_samples": self.warning_samples,
            "rejected_samples": self.rejected_samples,
            "target_samples": self.target_samples,
            "reference_present": self.reference_present,
            "ready_for_candidate_trials": self.ready_for_candidate_trials,
            "batch_failure_isolation_ready": self.batch_failure_isolation_ready,
            "strata": self.strata,
            "items": [item.projection() for item in self.items],
            "report_contains_image_bytes": False,
            "report_contains_local_paths": False,
        }

    def to_html(self) -> str:
        """Render a small static report for human review and dashboard linking."""

        rows: list[str] = []
        for item in self.items:
            p = item.projection()
            dimensions = p["dimensions"] or "—"
            flags = "、".join(item.quality_flags) or "—"
            reasons = "、".join(item.reason_codes) or "—"
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(item.sample_id))}</td>"
                f"<td>{html.escape(item.role)}</td>"
                f"<td>{html.escape(item.status)}</td>"
                f"<td>{html.escape(str(dimensions))}</td>"
                f"<td>{item.face_count}</td>"
                f"<td>{item.quality_confidence:.3f}</td>"
                f"<td>{item.editability_confidence:.3f}</td>"
                f"<td>{html.escape(flags)}</td>"
                f"<td>{html.escape(reasons)}</td>"
                "</tr>"
            )
        projection = self.projection()
        summary = (
            f"{self.total_samples} 张样本；可试验 {self.eligible_samples} 张；"
            f"质量提醒 {self.warning_samples} 张；拒绝 {self.rejected_samples} 张。"
        )
        return (
            """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>腾讯特效 Web E3 样本预检</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;margin:32px;
color:#1f2024}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid
#d9d9df;padding:8px;text-align:left}th{background:#f2eff8}.meta{background:#faf8f2;
border-left:4px solid #7b61a8;padding:12px;margin:16px 0}
code{font-size:12px}</style></head><body>
<h1>腾讯特效 Web E3 样本预检</h1>
<div class="meta"><p><strong>结论：</strong>__SUMMARY__</p>
<p>这是候选 Provider 的样本资格检查，不是视觉效果通过、同人确认或 Card promotion。</p>
<p>报告不含图片 bytes、不含本地路径；哈希只用于把浏览器回执绑定到样本。</p></div>
<table><thead><tr><th>样本</th><th>角色</th><th>预检</th><th>尺寸</th><th>人脸数</th>
<th>质量路由置信度</th><th>可编辑路由置信度</th><th>质量标记</th><th>原因</th></tr></thead>
<tbody>__ROWS__</tbody></table>
<h2>分层标签</h2><pre><code>__STRATA__</code></pre>
<h2>安全边界</h2><p>样本只在运行时内存读取；本报告没有复制图片、结果图或完整路径。
供应商出站、区域、留存、费用、License 与多样本视觉效果仍需独立证据。</p>
</body></html>""".replace("__SUMMARY__", html.escape(summary))
            .replace("__ROWS__", "".join(rows))
            .replace("__STRATA__", html.escape(str(projection["strata"])))
        )


@dataclass(frozen=True)
class E3LiveReceipt:
    """One redacted receipt captured during an owner-authorized browser run.

    The manifest deliberately stores metadata only.  The browser output stays
    in the browser session, while the input/output hashes let us prove that a
    receipt belongs to the preflighted sample.  ``request_ref`` is optional so
    a manually transcribed receipt cannot invent a request-generation ID; when
    it is absent, the report explicitly marks that linkage as incomplete.
    """

    sample_id: str
    receipt_id: str
    input_sha256: str
    status: LiveReceiptStatus
    elapsed_ms: int
    output_sha256: str | None = None
    request_ref: str | None = None
    output_width: int | None = None
    output_height: int | None = None
    handoff_accepted: bool = False
    result_retention: Literal["browser_session_only"] = "browser_session_only"
    verification_status: VerificationHandoffStatus = "not_run"
    # These are redacted projections of the shared VerificationResult.  They
    # let the E3 gate distinguish “the browser returned bytes” from “the
    # returned bytes produced measurable, non-worsening evidence” without
    # persisting a result image or raw landmarks.
    verification_id: str | None = None
    verification_decision: str | None = None
    overall_trend: str | None = None
    target_evidence_sufficient: bool | None = None
    measured_feature_count: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"succeeded", "failed"}:
            raise ValueError("status must be succeeded or failed")
        if self.verification_status not in {"not_run", "metadata_only", "completed", "failed"}:
            raise ValueError("verification_status is not supported")
        if not _SAFE_ID_RE.fullmatch(self.sample_id):
            raise ValueError("sample_id must be a safe identifier")
        if not _SAFE_ID_RE.fullmatch(self.receipt_id):
            raise ValueError("receipt_id must be a safe identifier")
        if self.request_ref is not None and not _SAFE_ID_RE.fullmatch(self.request_ref):
            raise ValueError("request_ref must be a safe identifier when present")
        if self.verification_id is not None and not _SAFE_ID_RE.fullmatch(self.verification_id):
            raise ValueError("verification_id must be a safe identifier when present")
        if not _SHA256_RE.fullmatch(self.input_sha256):
            raise ValueError("input_sha256 must be a lowercase SHA-256")
        if self.output_sha256 is not None and not _SHA256_RE.fullmatch(self.output_sha256):
            raise ValueError("output_sha256 must be a lowercase SHA-256 when present")
        if self.elapsed_ms < 0 or self.elapsed_ms > 900_000:
            raise ValueError("elapsed_ms must stay inside the browser receipt limit")
        if self.status == "succeeded" and not self.output_sha256:
            raise ValueError("a succeeded live receipt requires output_sha256")
        if self.status == "failed" and self.output_sha256 is not None:
            raise ValueError("a failed live receipt cannot carry output_sha256")
        if self.output_width is not None and not 1 <= self.output_width <= 20_000:
            raise ValueError("output_width is outside the browser receipt limit")
        if self.output_height is not None and not 1 <= self.output_height <= 20_000:
            raise ValueError("output_height is outside the browser receipt limit")
        if self.status == "failed" and self.handoff_accepted:
            raise ValueError("a failed receipt cannot be marked as handed off")
        if self.measured_feature_count is not None and self.measured_feature_count < 0:
            raise ValueError("measured_feature_count cannot be negative")
        if self.verification_status == "completed":
            if self.verification_id is None or self.overall_trend is None:
                raise ValueError(
                    "completed verification receipts require verification_id and overall_trend"
                )

    @classmethod
    def from_mapping(cls, value: dict[str, object]) -> E3LiveReceipt:
        """Parse a redacted manifest row without accepting arbitrary fields."""

        allowed = {
            "sample_id",
            "receipt_id",
            "receipt_ref",
            "request_ref",
            "input_sha256",
            "status",
            "elapsed_ms",
            "output_sha256",
            "output_width",
            "output_height",
            "handoff_accepted",
            "result_retention",
            "verification_status",
            "verification_id",
            "verification_decision",
            "overall_trend",
            "target_evidence_sufficient",
            "measured_feature_count",
            "note",
            "notes",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("live receipt row contains unsupported fields")
        receipt_id = value.get("receipt_id", value.get("receipt_ref"))
        note = value.get("note", value.get("notes"))
        if not isinstance(receipt_id, str):
            raise ValueError("live receipt row requires receipt_id")
        if note is not None and not isinstance(note, str):
            raise ValueError("live receipt note must be text")
        result_retention = value.get("result_retention", "browser_session_only")
        if result_retention != "browser_session_only":
            raise ValueError("E3 live receipts must remain browser_session_only")
        return cls(
            sample_id=str(value.get("sample_id", "")),
            receipt_id=receipt_id,
            request_ref=(
                value.get("request_ref") if isinstance(value.get("request_ref"), str) else None
            ),
            input_sha256=str(value.get("input_sha256", "")),
            status=value.get("status", "failed"),  # type: ignore[arg-type]
            elapsed_ms=int(value.get("elapsed_ms", -1)),
            output_sha256=(
                value.get("output_sha256") if isinstance(value.get("output_sha256"), str) else None
            ),
            output_width=(
                int(value["output_width"]) if value.get("output_width") is not None else None
            ),
            output_height=(
                int(value["output_height"]) if value.get("output_height") is not None else None
            ),
            handoff_accepted=bool(value.get("handoff_accepted", False)),
            result_retention="browser_session_only",
            verification_status=value.get("verification_status", "not_run"),  # type: ignore[arg-type]
            verification_id=(
                value.get("verification_id")
                if isinstance(value.get("verification_id"), str)
                else None
            ),
            verification_decision=(
                value.get("verification_decision")
                if isinstance(value.get("verification_decision"), str)
                else None
            ),
            overall_trend=(
                value.get("overall_trend") if isinstance(value.get("overall_trend"), str) else None
            ),
            target_evidence_sufficient=(
                bool(value.get("target_evidence_sufficient"))
                if value.get("target_evidence_sufficient") is not None
                else None
            ),
            measured_feature_count=(
                int(value["measured_feature_count"])
                if value.get("measured_feature_count") is not None
                else None
            ),
            note=note,
        )

    def projection(self) -> dict[str, object]:
        """Return a receipt row safe for a report or dashboard."""

        return {
            "sample_id": self.sample_id,
            "receipt_id": self.receipt_id,
            "request_ref": self.request_ref,
            "request_ref_recorded": self.request_ref is not None,
            "input_sha256": self.input_sha256,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "output_sha256": self.output_sha256,
            "output_dimensions": (
                f"{self.output_width}x{self.output_height}"
                if self.output_width is not None and self.output_height is not None
                else None
            ),
            "handoff_accepted": self.handoff_accepted,
            "result_retention": self.result_retention,
            "verification_status": self.verification_status,
            "verification_id": self.verification_id,
            "verification_decision": self.verification_decision,
            "overall_trend": self.overall_trend,
            "target_evidence_sufficient": self.target_evidence_sufficient,
            "measured_feature_count": self.measured_feature_count,
            "note": self.note,
            "image_bytes_saved": False,
            "data_url_saved": False,
        }


@dataclass(frozen=True)
class E3EvidenceReport:
    """Join preflight facts, live receipts and admission evidence.

    This is intentionally an evidence report rather than a promotion command.
    It can prove that browser calls returned and that sample hashes line up, but
    it keeps visual generalization and vendor terms as explicit open gates.  The
    separate ``promote_effect_web_card.py`` command evaluates the same evidence
    with a fail-closed checklist and is the only code path allowed to write a
    Card promotion.
    """

    evidence_version: str
    reference_sample_id: str | None
    preflight_summary: dict[str, object]
    live_receipts: tuple[E3LiveReceipt, ...]
    live_success_count: int
    live_failed_count: int
    all_target_receipts_present: bool
    sample_hashes_match_preflight: bool
    request_refs_recorded: bool
    handoff_success_count: int
    batch_failure_isolation_verified: bool
    offline_contract_regression_passed: bool
    visual_generalization_status: Literal["not_established", "established"]
    formal_admission_evidence: dict[str, bool]
    promotion_status: Literal["candidate", "verified"]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]

    def projection(self) -> dict[str, object]:
        live_total = len(self.live_receipts)
        return {
            "evidence_version": self.evidence_version,
            "reference_sample_id": self.reference_sample_id,
            "preflight_summary": self.preflight_summary,
            "live_summary": {
                "total_receipts": live_total,
                "succeeded": self.live_success_count,
                "failed": self.live_failed_count,
                "success_rate": round(self.live_success_count / live_total, 4)
                if live_total
                else 0.0,
                "all_target_receipts_present": self.all_target_receipts_present,
                "sample_hashes_match_preflight": self.sample_hashes_match_preflight,
                "request_refs_recorded": self.request_refs_recorded,
                "handoff_accepted": self.handoff_success_count,
                "result_payloads_persisted": False,
            },
            "offline_contract_regression": {
                "passed": self.offline_contract_regression_passed,
                "batch_failure_isolation_verified": self.batch_failure_isolation_verified,
            },
            "visual_generalization_status": self.visual_generalization_status,
            "formal_admission_evidence": self.formal_admission_evidence,
            "promotion_status": self.promotion_status,
            "blockers": list(self.blockers),
            "next_actions": list(self.next_actions),
            "report_contains_image_bytes": False,
            "report_contains_local_paths": False,
            "report_contains_data_urls": False,
            "receipts": [receipt.projection() for receipt in self.live_receipts],
        }

    def to_html(self) -> str:
        """Render a static, human-readable E3 evidence report."""

        payload = self.projection()
        rows: list[str] = []
        for receipt in self.live_receipts:
            row = receipt.projection()
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(row['sample_id']))}</td>"
                f"<td>{html.escape(str(row['receipt_id']))}</td>"
                f"<td>{html.escape(str(row['status']))}</td>"
                f"<td>{html.escape(str(row['elapsed_ms']))} ms</td>"
                f"<td>{'是' if row['handoff_accepted'] else '否'}</td>"
                f"<td>{'是' if row['request_ref_recorded'] else '否'}</td>"
                f"<td>{html.escape(str(row['verification_status']))}</td>"
                "</tr>"
            )
        blockers = "".join(f"<li>{html.escape(item)}</li>" for item in self.blockers)
        actions = "".join(f"<li>{html.escape(item)}</li>" for item in self.next_actions)
        return (
            "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
            "<title>腾讯特效 Web E3 真实证据</title>"
            "<style>body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
            "max-width:1200px;margin:32px auto;color:#1f2024}table{border-collapse:collapse;"
            "width:100%;font-size:14px}th,td{border:1px solid #d9d9df;padding:8px;text-align:left}"
            "th{background:#f2eff8}.meta{background:#faf8f2;border-left:4px solid #7b61a8;"
            "padding:14px;margin:16px 0}.ok{color:#087f23}.warn{color:#9a6700}"
            "code{font-size:12px;word-break:break-all}</style><body>"
            "<h1>腾讯特效 Web｜E3 真实多样本证据</h1>"
            "<div class='meta'><p><strong>当前结论：</strong>"
            f"真实浏览器回执 {self.live_success_count}/{len(self.live_receipts)} 成功；"
            f"Card 仍为 <strong>{html.escape(self.promotion_status)}</strong>。</p>"
            "<p>这份报告证明的是回执、哈希绑定、结果交接和失败隔离；"
            "它不把一次或多次 SDK 成功调用当作母版视觉一致性已经泛化。</p>"
            "<p>报告不含图片 bytes、data URL 或本地路径；输出哈希只用于证据关联。</p></div>"
            "<h2>实时回执</h2><table><thead><tr><th>样本</th><th>receipt</th><th>状态</th>"
            "<th>耗时</th><th>结果交接</th><th>request_ref</th><th>复测状态</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
            "<h2>证据摘要</h2><pre><code>" + html.escape(json_projection(payload)) + "</code></pre>"
            "<h2>仍未闭合的 Gate</h2><ul>"
            + blockers
            + "</ul><h2>下一步</h2><ul>"
            + actions
            + "</ul></body></html>"
        )


def json_projection(payload: dict[str, object]) -> str:
    """Stable JSON formatting kept local to avoid importing a report writer."""

    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_e3_evidence_report(
    preflight: dict[str, object],
    live_receipts: Iterable[E3LiveReceipt],
    *,
    offline_contract_regression_passed: bool,
    batch_failure_isolation_verified: bool,
    formal_admission_evidence: dict[str, bool] | None = None,
) -> E3EvidenceReport:
    """Join a redacted preflight projection with live browser evidence.

    The function is fail-closed for linkage: an unknown sample or a mismatched
    input hash makes the evidence incomplete rather than silently attributing a
    receipt to another photo.
    """

    items = preflight.get("items")
    if not isinstance(items, list):
        raise ValueError("preflight report must contain an items list")
    preflight_rows = [item for item in items if isinstance(item, dict)]
    hashes_by_sample = {
        str(item.get("sample_id")): str(item.get("sha256"))
        for item in preflight_rows
        if item.get("sample_id") and item.get("sha256")
    }
    target_ids = {
        str(item.get("sample_id"))
        for item in preflight_rows
        if item.get("role") == "target" and item.get("status") != "rejected"
    }
    receipts = tuple(live_receipts)
    if len({receipt.receipt_id for receipt in receipts}) != len(receipts):
        raise ValueError("live receipt IDs must be unique")
    if len({receipt.sample_id for receipt in receipts}) != len(receipts):
        raise ValueError("one live receipt per sample is required in the E3 manifest")
    linked = all(
        receipt.sample_id in hashes_by_sample
        and hashes_by_sample[receipt.sample_id] == receipt.input_sha256
        for receipt in receipts
    )
    unique_sample_ids = {receipt.sample_id for receipt in receipts}
    all_targets_present = target_ids.issubset(unique_sample_ids)
    request_refs_recorded = bool(receipts) and all(
        receipt.request_ref is not None for receipt in receipts
    )
    live_success = sum(receipt.status == "succeeded" for receipt in receipts)
    live_failed = sum(receipt.status == "failed" for receipt in receipts)
    handoff_success = sum(receipt.handoff_accepted for receipt in receipts)
    target_receipts = [receipt for receipt in receipts if receipt.sample_id in target_ids]
    # “Visual generalization” is deliberately narrower than SDK success.  It
    # is established only when every preflighted target has a completed shared
    # verification, all measured trends are non-worsening, and at least one
    # target contains positive geometry evidence.  An LLM or a browser status
    # cannot manufacture this flag.
    target_verification_complete = bool(target_receipts) and all(
        receipt.status == "succeeded"
        and receipt.handoff_accepted
        and receipt.verification_status == "completed"
        and receipt.overall_trend in {"improved", "no_change"}
        and receipt.measured_feature_count is not None
        and receipt.measured_feature_count > 0
        for receipt in target_receipts
    )
    target_improvement_observed = any(
        receipt.overall_trend == "improved" for receipt in target_receipts
    )
    visual_evidence_complete = (
        all_targets_present
        and linked
        and request_refs_recorded
        and target_verification_complete
        and target_improvement_observed
    )
    formal = {
        "license_active": False,
        "exact_domain_bound": False,
        "provider_permission_granted": False,
        "outbound_data_policy_approved": False,
        "region_approved": False,
        "estimated_cost_known": False,
        "adapter_ready": True,
        "static_image_smoke_succeeded": live_success > 0 and linked,
        "multi_sample_visual_review_complete": False,
        "product_owner_promotion_approved": False,
    }
    if formal_admission_evidence:
        for key, value in formal_admission_evidence.items():
            if key in formal:
                formal[key] = bool(value)
    # A caller may supply the non-visual vendor checklist, but it may not
    # override missing result→VerificationResult evidence.  This keeps the
    # promotion gate tied to factual receipts rather than a copied boolean.
    formal["multi_sample_visual_review_complete"] = visual_evidence_complete
    blockers: list[str] = []
    if not linked:
        blockers.append("live_receipt_input_hash_not_linked_to_preflight")
    if not all_targets_present:
        blockers.append("all_preflighted_target_receipts_not_present")
    if not request_refs_recorded:
        blockers.append("request_ref_not_recorded_for_every_manual_receipt")
    if not offline_contract_regression_passed:
        blockers.append("offline_contract_regression_not_passed")
    if not batch_failure_isolation_verified:
        blockers.append("batch_failure_isolation_not_verified")
    if visual_evidence_complete:
        formal["multi_sample_visual_review_complete"] = True
    if not formal["multi_sample_visual_review_complete"]:
        blockers.append("visual_effect_generalization_not_established")
    blockers.extend(
        key
        for key, value in formal.items()
        if not value and key not in {"multi_sample_visual_review_complete"}
    )
    if not formal["product_owner_promotion_approved"]:
        blockers.append("product_owner_promotion_approval_required")
    # Keep order stable while avoiding duplicate explanations when a caller
    # supplied the same missing evidence twice.
    blockers = list(dict.fromkeys(blockers))
    next_actions = (
        "把每张结果图完成一次浏览器→Python 内存 handoff，并生成共同 VerificationResult",
        "对真实样本做盲化前后视觉复核，记录可复测的几何变化和异常，而不是只看 SDK 成功",
        "补齐供应商 License、精确域名、图片出站/留存、地区、费用和预算证据",
        "在上述证据齐全后由产品负责人单独决定 candidate 是否 promotion",
    )
    reference_id = preflight.get("reference_sample_id")
    preflight_summary = {
        key: preflight.get(key)
        for key in (
            "total_samples",
            "eligible_samples",
            "warning_samples",
            "rejected_samples",
            "target_samples",
            "reference_present",
            "ready_for_candidate_trials",
            "batch_failure_isolation_ready",
        )
    }
    return E3EvidenceReport(
        evidence_version="effect_web_e3_evidence_v0.1",
        reference_sample_id=str(reference_id) if reference_id else None,
        preflight_summary=preflight_summary,
        live_receipts=receipts,
        live_success_count=live_success,
        live_failed_count=live_failed,
        all_target_receipts_present=all_targets_present,
        sample_hashes_match_preflight=linked,
        request_refs_recorded=request_refs_recorded,
        handoff_success_count=handoff_success,
        batch_failure_isolation_verified=batch_failure_isolation_verified,
        offline_contract_regression_passed=offline_contract_regression_passed,
        visual_generalization_status=(
            "established" if formal["multi_sample_visual_review_complete"] else "not_established"
        ),
        formal_admission_evidence=formal,
        promotion_status="candidate",
        blockers=tuple(blockers),
        next_actions=next_actions,
    )


def _item_status(observation: PhotoObservation, *, bytes_read: int) -> PreflightStatus:
    """Classify eligibility without converting a confidence into probability."""

    if bytes_read <= 0 or observation.face_count != 1:
        return "rejected"
    if QualityFlag.PROVIDER_UNSUPPORTED_INPUT in observation.quality_flags:
        return "rejected"
    strictest = min(observation.quality_confidence, observation.editability_confidence)
    return "eligible" if strictest >= 0.80 else "warning"


def _read_and_analyse(spec: E3SampleSpec) -> E3PreflightItem:
    """Read one authorized file in memory and immediately discard its bytes."""

    try:
        if not spec.path.is_file():
            raise OSError("sample_file_missing")
        if spec.path.suffix.lower() not in E3_ALLOWED_SUFFIXES:
            raise OSError("unsupported_file_suffix")
        image_bytes = spec.path.read_bytes()
        digest = hashlib.sha256(image_bytes).hexdigest()
        if len(image_bytes) > E3_MAX_SAMPLE_BYTES:
            raise OSError("input_bytes_exceed_provider_limit")
        observation = analyze_photo_bytes(
            image_bytes,
            photo_id=spec.sample_id,
            photo_role=(
                PhotoRole.REFERENCE if spec.role == "reference_candidate" else PhotoRole.TARGET
            ),
        )
        status = _item_status(observation, bytes_read=len(image_bytes))
        return E3PreflightItem(
            sample_id=spec.sample_id,
            role=spec.role,
            status=status,
            file_name=spec.path.name,
            sha256=digest,
            bytes_read=len(image_bytes),
            width=observation.width,
            height=observation.height,
            image_format=observation.image_format,
            face_count=observation.face_count,
            quality_confidence=observation.quality_confidence,
            editability_confidence=observation.editability_confidence,
            quality_flags=tuple(flag.value for flag in observation.quality_flags),
            reason_codes=observation.reason_codes,
            angle=spec.angle,
            lighting=spec.lighting,
            expression=spec.expression,
        )
    except (OSError, ValueError) as exc:
        # Even failed files receive a stable hash when possible; no path or
        # bytes are retained.  A missing/unreadable file gets the empty hash.
        try:
            raw = spec.path.read_bytes() if spec.path.is_file() else b""
        except OSError:
            raw = b""
        return E3PreflightItem(
            sample_id=spec.sample_id,
            role=spec.role,
            status="rejected",
            file_name=spec.path.name,
            sha256=hashlib.sha256(raw).hexdigest(),
            bytes_read=len(raw),
            width=None,
            height=None,
            image_format=None,
            face_count=0,
            quality_confidence=0.0,
            editability_confidence=0.0,
            quality_flags=(QualityFlag.PROVIDER_UNSUPPORTED_INPUT.value,),
            reason_codes=(str(exc),),
            angle=spec.angle,
            lighting=spec.lighting,
            expression=spec.expression,
        )


def preflight_e3_samples(samples: Iterable[E3SampleSpec]) -> E3PreflightReport:
    """Build a redacted E3 manifest, continuing after individual failures."""

    items = tuple(_read_and_analyse(sample) for sample in samples)
    reference_items = [item for item in items if item.role == "reference_candidate"]
    reference = next((item for item in reference_items if item.status != "rejected"), None)
    counters = {
        "angle": Counter(item.angle for item in items),
        "lighting": Counter(item.lighting for item in items),
        "expression": Counter(item.expression for item in items),
    }
    rejected_index = next(
        (index for index, item in enumerate(items) if item.status == "rejected"), None
    )
    continues_after_rejection = rejected_index is not None and any(
        item.status != "rejected" for item in items[rejected_index + 1 :]
    )
    return E3PreflightReport(
        harness_version=E3_HARNESS_VERSION,
        reference_sample_id=reference.sample_id if reference else None,
        total_samples=len(items),
        eligible_samples=sum(item.status == "eligible" for item in items),
        warning_samples=sum(item.status == "warning" for item in items),
        rejected_samples=sum(item.status == "rejected" for item in items),
        target_samples=sum(item.role == "target" and item.status != "rejected" for item in items),
        reference_present=reference is not None,
        batch_failure_isolation_ready=continues_after_rejection,
        strata={name: dict(counter) for name, counter in counters.items()},
        items=items,
    )
