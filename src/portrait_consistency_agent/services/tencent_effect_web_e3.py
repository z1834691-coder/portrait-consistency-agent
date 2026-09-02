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
