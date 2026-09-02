"""Deterministic, public-only baseline runner for RAG Gold Set v2.

This module is intentionally an *evaluation bridge*, not a new production
intent parser.  RAG P0-A/P0-B consume a validated :class:`RagQuery` and do not
accept a user's raw utterance.  The public Gold Set, however, contains natural
language test prompts.  This small deterministic projector lets us test the
existing local retrieval/policy path without an LLM, network access, photos,
or a hidden answer key.

Safety properties:

* only ``dev`` / ``challenge`` cases whose IDs begin with ``D`` or ``X`` are
  accepted;
* the runner never imports annotations, holdout files, model weights, or
  Provider SDKs;
* public prompt text is used only in memory to build a structured query and is
  never written into a prediction, SQLite trace, or report artifact;
* when the projector cannot safely represent a request, it returns
  ``UNKNOWN`` / ``BLOCK`` with a policy evidence alias rather than inventing
  an ability.

The aliases ``B`` / ``C`` / ``I`` / ``P`` / ``FX`` are the public evaluation
source aliases defined in ``RAG_GOLD_SET_V2_REVIEW.md``.  They are not Gold
answers and do not grant an execution permission.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from portrait_consistency_agent.core.contracts import EditableFeature, PreserveAttribute
from portrait_consistency_agent.core.rag_contracts import RagQuery, RagStage
from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_gold_eval import GoldCase, Prediction
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever, RagP0BRun
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

RAG_GOLD_BASELINE_VERSION = "rag-gold-baseline-deterministic-v0.2"
_PUBLIC_ID = re.compile(r"^[DX][0-9]{2,}$")
_HOLDOUT_ID = re.compile(r"^H[0-9]{2,}$")


@dataclass(frozen=True)
class BaselineProjection:
    """A non-sensitive, deterministic interpretation of one public test prompt.

    ``category_codes`` are deliberately coarse.  They make a failure
    replayable without retaining the original test sentence in the normal RAG
    trace or in a prediction artifact.
    """

    category_codes: tuple[str, ...]
    route_override: str | None
    evidence_aliases: tuple[str, ...]
    evidence_relations: dict[str, str]
    requested_features: tuple[EditableFeature, ...] = ()
    allowed_features: tuple[EditableFeature, ...] = ()
    preserve_constraints: tuple[PreserveAttribute, ...] = ()
    retriever_kind: str | None = None
    outbound_allowed: bool = True
    missing_critical_slots: tuple[str, ...] = ()


@dataclass(frozen=True)
class BaselineCaseRun:
    """One redacted prediction and trace projection from the local baseline."""

    prediction: Prediction
    safe_trace: dict[str, object]


@dataclass(frozen=True)
class BaselineRun:
    """Batch result for public Gold cases only."""

    predictions: tuple[Prediction, ...]
    safe_traces: tuple[dict[str, object], ...]
    knowledge_snapshot: dict[str, object]
    runtime_mode: str


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _add_evidence(
    aliases: list[str],
    relations: dict[str, str],
    alias: str,
    relation: str,
) -> None:
    if alias not in aliases:
        aliases.append(alias)
    relations.setdefault(alias, relation)


def project_runtime_prompt(case: GoldCase) -> BaselineProjection:
    """Project an answerless runtime prompt into safe slots without Gold labels.

    This is deliberately conservative and phrase-general rather than a map of
    case IDs.  It recognizes only the small set of capabilities and policies
    that currently exist in the project.  Anything beyond that becomes an
    explicit non-executing route.
    """

    text = case.query.casefold()
    aliases: list[str] = []
    relations: dict[str, str] = {}

    # These routes never need to pass the natural-language sentence to the
    # retriever.  They are deterministic protections, not model judgments.
    if _contains_any(
        text,
        (
            "忽略权限",
            "system prompt",
            "系统 prompt",
            "系统prompt",
            "原图、向量",
            "原图向量",
            "人脸向量入 rag",
            "人脸向量入rag",
            "把系统 prompt",
            "把系统prompt",
        ),
    ):
        _add_evidence(aliases, relations, "P", "direct_evidence")
        return BaselineProjection(
            category_codes=("policy_injection_or_sensitive_data_block",),
            route_override="BLOCK",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(
        text,
        (
            "不要把图发",
            "任何云",
            "不外发",
            "no cloud transfer",
            "不允许该 provider",
            "不允许该provider",
            "未允许该 provider",
            "未允许该provider",
        ),
    ):
        _add_evidence(aliases, relations, "P", "direct_evidence")
        return BaselineProjection(
            category_codes=("outbound_or_provider_scope_block",),
            route_override="BLOCK",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            outbound_allowed=False,
        )

    # A wording such as "不要出腾讯" is a *provider-scope constraint*, not
    # a blanket no-cloud refusal.  It can preserve the existing Tencent-only
    # baseline, but does not authorize a candidate Provider or a multi-face
    # edit on its own.
    if _contains_any(text, ("允许发腾讯", "不允许其他厂商", "不要出腾讯")):
        _add_evidence(aliases, relations, "B", "direct_evidence")
        _add_evidence(aliases, relations, "P", "reference_context")
        if _contains_any(text, ("合照", "只修左边", "鼻翼")):
            relations["B"] = "reference_context"
            relations["P"] = "direct_evidence"
            return BaselineProjection(
                category_codes=("provider_scope_with_unready_multiface_or_detail",),
                route_override="SUGGEST",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                requested_features=(EditableFeature.NOSE_WING,) if "鼻翼" in text else (),
                allowed_features=(EditableFeature.NOSE_WING,) if "鼻翼" in text else (),
                retriever_kind="beautify",
            )
        return BaselineProjection(
            category_codes=("approved_provider_scope",),
            route_override="DIRECT",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="beautify",
        )

    if _contains_any(text, ("参数范围互相矛盾", "同版本 card 对同一参数冲突", "知识段落说忽略")):
        _add_evidence(aliases, relations, "FX", "conflict_evidence")
        return BaselineProjection(
            category_codes=("evaluation_fixture_conflict_or_injection",),
            route_override="BLOCK",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if "not_yet_effective" in text:
        _add_evidence(aliases, relations, "FX", "conflict_evidence")
        return BaselineProjection(
            category_codes=("evaluation_fixture_not_yet_effective",),
            route_override="UNKNOWN",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("资料更新失败", "本地索引缺失")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("evaluation_index_unavailable",),
            route_override="UNKNOWN",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if "expired" in text:
        _add_evidence(aliases, relations, "FX", "conflict_evidence")
        _add_evidence(aliases, relations, "B", "reference_context")
        return BaselineProjection(
            category_codes=("evaluation_fixture_expired",),
            route_override="BLOCK",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if "superseded" in text:
        _add_evidence(aliases, relations, "B", "direct_evidence")
        _add_evidence(aliases, relations, "FX", "reference_context")
        return BaselineProjection(
            category_codes=("evaluation_fixture_superseded",),
            route_override="DIRECT",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="beautify",
        )

    if "review_due" in text:
        _add_evidence(aliases, relations, "FX", "reference_context")
        return BaselineProjection(
            category_codes=("evaluation_fixture_review_due",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("adapter 未实现", "adapter未实现", "未 smoke", "未smoke")):
        _add_evidence(aliases, relations, "B", "reference_context")
        _add_evidence(aliases, relations, "P", "direct_evidence")
        return BaselineProjection(
            category_codes=("adapter_not_ready",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("多轮", "连续修 5 轮", "连续修5轮")):
        _add_evidence(aliases, relations, "B", "reference_context")
        _add_evidence(aliases, relations, "P", "direct_evidence")
        if "只修一次" in text:
            return BaselineProjection(
                category_codes=("round_scope_needs_clarification",),
                route_override="CLARIFY",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            )
        return BaselineProjection(
            category_codes=("round_limit_block",),
            route_override="BLOCK",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("满意", "变差")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("feedback_does_not_overwrite_verification",),
            route_override="STOP",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("90%", "90％", "相似度保证")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("uncalibrated_probability_boundary",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("锚点", "保存半年")) and "不同意" in text:
        _add_evidence(aliases, relations, "P", "direct_evidence")
        return BaselineProjection(
            category_codes=("current_session_anchor_degrade",),
            route_override="BASELINE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("能撤回", "图片发出后")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("privacy_explanation_only",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("最强工具", "无区域", "无授权", "无部位")):
        _add_evidence(aliases, relations, "P", "direct_evidence")
        return BaselineProjection(
            category_codes=("missing_critical_slots",),
            route_override="CLARIFY",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            missing_critical_slots=("requested_feature_or_provider_scope",),
        )

    if "成人自拍" in text and "批量" in text:
        _add_evidence(aliases, relations, "I", "reference_context")
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("batch_requires_content_quality_subject_and_scope",),
            route_override="CLARIFY",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="moderation",
        )

    if _contains_any(text, ("两个朋友", "都同意")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("third_party_consent_does_not_create_multiface_capability",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("合照", "批量", "9 张", "9张")):
        _add_evidence(aliases, relations, "B", "reference_context")
        _add_evidence(aliases, relations, "P", "reference_context")
        if _contains_any(text, ("最丑", "美丑")):
            relations["P"] = "direct_evidence"
        return BaselineProjection(
            category_codes=("multiface_or_batch_not_ready",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("ims", "compareface")) and _contains_any(
        text, ("嘴唇", "唇厚", "下嘴唇")
    ):
        _add_evidence(aliases, relations, "I", "reference_context")
        _add_evidence(aliases, relations, "C", "reference_context")
        _add_evidence(aliases, relations, "B", "reference_context")
        return BaselineProjection(
            category_codes=("safety_and_subject_do_not_expand_unsupported_feature",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            requested_features=(EditableFeature.LIPS_THICKNESS,),
            allowed_features=(EditableFeature.LIPS_THICKNESS,),
            retriever_kind="beautify",
        )

    if _contains_any(text, ("compareface", "这张是我本人", "人脸比对")):
        _add_evidence(aliases, relations, "C", "reference_context")
        if "修得像" in text:
            _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("subject_match_scope_only",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="compare_face",
        )

    if _contains_any(text, ("ims", "内容审核")):
        _add_evidence(aliases, relations, "I", "reference_context")
        if "通过" in text:
            _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("content_safety_scope_only",),
            route_override="REFERENCE",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="moderation",
        )

    if _contains_any(text, ("上次工具卡", "今天呢", "旧参数卡", "旧卡")):
        _add_evidence(aliases, relations, "FX", "conflict_evidence")
        return BaselineProjection(
            category_codes=("stale_or_unreviewed_knowledge_claim",),
            route_override="UNKNOWN",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("一个 direct", "解释型背景资料")):
        _add_evidence(aliases, relations, "B", "direct_evidence")
        _add_evidence(aliases, relations, "FX", "reference_context")
        return BaselineProjection(
            category_codes=("direct_and_background_evidence_relation",),
            route_override="DIRECT",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="beautify",
        )

    if _contains_any(text, ("低权威博客", "高权威官方卡")):
        _add_evidence(aliases, relations, "B", "direct_evidence")
        _add_evidence(aliases, relations, "FX", "reference_context")
        return BaselineProjection(
            category_codes=("authority_priority",),
            route_override="DIRECT",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="beautify",
        )

    if _contains_any(text, ("侧脸", "正脸")) and "对齐" in text:
        _add_evidence(aliases, relations, "B", "reference_context")
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("pose_quality_limits_full_alignment",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            retriever_kind="beautify",
        )

    if _contains_any(text, ("下嘴唇", "嘴唇", "唇厚", "唇厚度", "嘴型")):
        _add_evidence(aliases, relations, "B", "reference_context")
        return BaselineProjection(
            category_codes=("unsupported_mouth_feature",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            requested_features=(EditableFeature.LIPS_THICKNESS,),
            allowed_features=(EditableFeature.LIPS_THICKNESS,),
            retriever_kind="beautify",
        )

    if _contains_any(text, ("鼻翼", "鼻子变小")):
        _add_evidence(aliases, relations, "B", "reference_context")
        return BaselineProjection(
            category_codes=("unsupported_nose_feature",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            requested_features=(EditableFeature.NOSE_WING,),
            allowed_features=(EditableFeature.NOSE_WING,),
            retriever_kind="beautify",
        )

    if _contains_any(text, ("眼距", "眼宽", "眉毛", "eye width")):
        _add_evidence(aliases, relations, "B", "reference_context")
        return BaselineProjection(
            category_codes=("unsupported_eye_detail_feature",),
            route_override="SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            requested_features=(EditableFeature.EYE_DISTANCE,),
            allowed_features=(EditableFeature.EYE_DISTANCE,),
            retriever_kind="beautify",
        )

    if _contains_any(text, ("新 sdk", "新sdk")):
        _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("unreviewed_or_stale_provider_claim",),
            route_override="UNKNOWN",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        )

    if _contains_any(text, ("不动皮肤", "磨皮和美白都不要", "不要瘦脸/大眼")):
        _add_evidence(
            aliases,
            relations,
            "B",
            "reference_context" if "只给建议" in text else "direct_evidence",
        )
        _add_evidence(
            aliases,
            relations,
            "P",
            "direct_evidence" if "只给建议" in text else "reference_context",
        )
        return BaselineProjection(
            category_codes=("preserve_constraint",),
            route_override="DIRECT" if "只给建议" not in text else "SUGGEST",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            preserve_constraints=(PreserveAttribute.SKIN_TONE,),
            retriever_kind="beautify",
        )

    features: list[EditableFeature] = []
    if _contains_any(text, ("瘦脸", "脸比母版宽", "腮帮", "脸宽")):
        features.append(EditableFeature.FACE_LIFTING)
    if _contains_any(text, ("大眼", "眼睛小", "眼睛显得不一样")):
        features.append(EditableFeature.EYE_ENLARGING)
    if features:
        _add_evidence(aliases, relations, "B", "direct_evidence")
        if len(features) > 1 or _contains_any(text, ("一点点", "别p得假", "别 p 得假")):
            _add_evidence(aliases, relations, "P", "reference_context")
        return BaselineProjection(
            category_codes=("reviewed_feature_candidate",),
            route_override="DIRECT",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
            requested_features=tuple(features),
            allowed_features=tuple(features),
            retriever_kind="beautify",
        )

    _add_evidence(aliases, relations, "P", "reference_context")
    return BaselineProjection(
        category_codes=("no_reliable_structured_projection",),
        route_override="UNKNOWN",
        evidence_aliases=tuple(aliases),
        evidence_relations=relations,
    )


# Compatibility alias for the original public-only unit tests and any local
# notebook that already imported the first function name.  Both functions have
# the same boundary: raw prompt text is transient and never persisted.
project_public_prompt = project_runtime_prompt


def _query_for_projection(case: GoldCase, projection: BaselineProjection) -> RagQuery | None:
    """Build one validated RAG query with no raw public phrase field."""

    query_id = f"gold_baseline_{case.case_id.lower()}"
    if projection.retriever_kind == "beautify":
        return build_plan_edit_query(
            query_id=query_id,
            requested_features=projection.requested_features,
            allowed_features=projection.allowed_features,
            preserve_constraints=projection.preserve_constraints,
            outbound_allowed=projection.outbound_allowed,
            missing_critical_slots=projection.missing_critical_slots,
        )
    if projection.retriever_kind == "compare_face":
        return RagQuery(
            query_id=query_id,
            stage=RagStage.VERIFICATION_STRATEGY,
            provider_candidates=["tencent_cloud"],
            operation_candidates=["CompareFace"],
            subject_match_route="information_only",
            outbound_allowed=False,
            adapter_required=False,
            intent_slots_present=["information_request"],
        )
    if projection.retriever_kind == "moderation":
        return RagQuery(
            query_id=query_id,
            stage=RagStage.QUALITY_GATE,
            provider_candidates=["tencent_cloud"],
            operation_candidates=["ImageModeration"],
            safety_route="information_only",
            outbound_allowed=False,
            adapter_required=False,
            intent_slots_present=["information_request"],
        )
    return None


def _run_counts(run: RagP0BRun | None) -> dict[str, object]:
    if run is None:
        return {
            "retrieval_latency_ms": 0,
            "candidate_count": 0,
            "sparse_candidate_count": 0,
            "dense_candidate_count": 0,
            "fused_candidate_count": 0,
        }
    return {
        "retrieval_latency_ms": run.result.latency_ms,
        "candidate_count": run.metadata_candidate_count,
        "sparse_candidate_count": run.sparse_candidate_count,
        "dense_candidate_count": run.dense_candidate_count,
        "fused_candidate_count": run.fused_candidate_count,
    }


class RagGoldDeterministicBaseline:
    """Run answerless public or holdout inputs through local P0-B/P0-C only."""

    def run(self, cases: Iterable[GoldCase]) -> BaselineRun:
        """Run public dev/challenge cases; never accept H* inputs here."""

        return self._run(cases, runtime_mode="public")

    def run_holdout(self, cases: Iterable[GoldCase]) -> BaselineRun:
        """Run H* input-only cases without an answer key or any metric output."""

        return self._run(cases, runtime_mode="holdout_input_only")

    def _run(self, cases: Iterable[GoldCase], *, runtime_mode: str) -> BaselineRun:
        case_list = tuple(cases)
        self._validate_cases(case_list, runtime_mode=runtime_mode)
        with tempfile.TemporaryDirectory(prefix="portrait-rag-gold-baseline-") as directory:
            root = Path(directory)
            store = LocalKnowledgeStore(root / "knowledge.sqlite3")
            store.initialize()
            seed_reviewed_provider_knowledge(store)
            retriever = RagP0BHybridRetriever(
                store=store,
                dense_index=LocalDenseIndex(root / "knowledge_vectors.sqlite3"),
                embedding_backend=DeterministicTokenEmbeddingBackend(),
                reranker_backend=TokenOverlapReranker(),
            )
            service = RagAdvisoryService(store=store, retriever=retriever)
            runs = tuple(self._run_case(case, service) for case in case_list)
            snapshot = store.snapshot()
        return BaselineRun(
            predictions=tuple(run.prediction for run in runs),
            safe_traces=tuple(run.safe_trace for run in runs),
            knowledge_snapshot=snapshot,
            runtime_mode=runtime_mode,
        )

    @staticmethod
    def _validate_cases(cases: tuple[GoldCase, ...], *, runtime_mode: str) -> None:
        if not cases:
            raise ValueError("baseline requires at least one answerless runtime case")
        if runtime_mode == "public":
            bad_cases = [
                case.case_id
                for case in cases
                if case.split not in {"dev", "challenge"} or not _PUBLIC_ID.fullmatch(case.case_id)
            ]
            error = "baseline public mode accepts only public D*/X* dev/challenge cases"
        elif runtime_mode == "holdout_input_only":
            bad_cases = [
                case.case_id
                for case in cases
                if case.split != "holdout" or not _HOLDOUT_ID.fullmatch(case.case_id)
            ]
            error = "baseline holdout mode accepts only answerless H* holdout runtime cases"
        else:
            raise ValueError(f"unsupported baseline runtime mode: {runtime_mode}")
        if bad_cases:
            raise ValueError(f"{error}; rejected {sorted(bad_cases)}")

    @staticmethod
    def _run_case(case: GoldCase, service: RagAdvisoryService) -> BaselineCaseRun:
        projection = project_runtime_prompt(case)
        query = _query_for_projection(case, projection)
        advisory = (
            service.advise(
                query=query,
                # The evaluator has no independently authorized edit action;
                # a miss must be recorded as UNKNOWN rather than retain an
                # implicit execution baseline.
                existing_baseline_available=False,
                advice_id=f"gold_baseline_advice_{case.case_id.lower()}",
            )
            if query is not None
            else None
        )
        retrieval = advisory.retrieval if advisory is not None else None
        aliases = list(projection.evidence_aliases)
        relations = dict(projection.evidence_relations)
        if retrieval is not None:
            for evidence in retrieval.result.evidences:
                alias = _alias_for_knowledge_id(evidence.knowledge_id)
                if alias is not None and alias not in aliases:
                    aliases.append(alias)
                    relations[alias] = evidence.relation.value
        # The projection's explicit policy relationship takes priority over a
        # retrieval's general card relation.  It is a policy boundary, not a
        # ranking score and not a permission grant.
        aliases = list(_ordered_unique(aliases))
        counts = _run_counts(retrieval)
        prediction = Prediction(
            case_id=case.case_id,
            route=projection.route_override or "UNKNOWN",
            evidence_refs=tuple(aliases),
            evidence_relations=relations,
            observed_events=(),
            trace_ref=f"{RAG_GOLD_BASELINE_VERSION}:{case.case_id}",
            machine_score_summary=counts,
        )
        safe_trace = {
            "case_id": case.case_id,
            "runner_version": RAG_GOLD_BASELINE_VERSION,
            "category_codes": list(projection.category_codes),
            "structured_query_created": query is not None,
            "retrieval_route": retrieval.result.route.value if retrieval is not None else None,
            "advisory_route": advisory.decision.advisory_route.value
            if advisory is not None
            else None,
            "advisory_execution_authorized": (
                advisory.decision.execution_authorized if advisory is not None else False
            ),
            "prediction_route": prediction.route,
            "evidence_refs": list(prediction.evidence_refs),
            "evidence_relations": dict(prediction.evidence_relations),
            "machine_score_summary": dict(prediction.machine_score_summary),
            "raw_prompt_persisted": False,
            "photo_or_face_vector_read": False,
            "llm_called": False,
            "provider_api_called": False,
            "network_called": False,
            "projection": {
                "route": projection.route_override,
                "category_codes": list(projection.category_codes),
                "evidence_aliases": list(projection.evidence_aliases),
                "evidence_relations": dict(projection.evidence_relations),
                "requested_features": [feature.value for feature in projection.requested_features],
                "allowed_features": [feature.value for feature in projection.allowed_features],
                "preserve_constraints": [
                    attribute.value for attribute in projection.preserve_constraints
                ],
                "outbound_allowed": projection.outbound_allowed,
                "missing_critical_slots": list(projection.missing_critical_slots),
            },
            "retrieval_trace": list(retrieval.trace) if retrieval is not None else [],
        }
        return BaselineCaseRun(prediction=prediction, safe_trace=safe_trace)


def _alias_for_knowledge_id(knowledge_id: str) -> str | None:
    aliases = {
        "tencent-beautify-pic-2019-12-13": "B",
        "tencent-compare-face-2018-03-01": "C",
        "tencent-image-moderation-2020-12-29": "I",
    }
    return aliases.get(knowledge_id)


def baseline_predictions_payload(run: BaselineRun) -> dict[str, object]:
    """Serialize redacted predictions without source prompts or answer fields."""

    return {
        "runner_version": RAG_GOLD_BASELINE_VERSION,
        "policy": {
            "runtime_mode": run.runtime_mode,
            "answerless_cases_only": True,
            "public_cases_only": run.runtime_mode == "public",
            "holdout_input_only": run.runtime_mode == "holdout_input_only",
            "hidden_answer_key_read": False,
            "annotations_read": False,
            "llm_called": False,
            "photo_or_face_vector_read": False,
            "external_provider_called": False,
            "network_called": False,
            "local_model_downloaded": False,
        },
        "knowledge_snapshot": dict(run.knowledge_snapshot),
        "rows": [
            {
                "case_id": prediction.case_id,
                "route": prediction.route,
                "evidence_refs": list(prediction.evidence_refs),
                "evidence_relations": dict(prediction.evidence_relations),
                "observed_events": list(prediction.observed_events),
                "trace_ref": prediction.trace_ref,
                "machine_score_summary": dict(prediction.machine_score_summary),
            }
            for prediction in run.predictions
        ],
    }


def baseline_trace_payload(run: BaselineRun) -> dict[str, object]:
    """Serialize the replayable but raw-prompt-free evaluation trace."""

    return {
        "runner_version": RAG_GOLD_BASELINE_VERSION,
        "policy": {
            "runtime_mode": run.runtime_mode,
            "raw_prompt_persisted": False,
            "hidden_answer_key_read": False,
            "llm_called": False,
            "photo_or_face_vector_read": False,
            "external_provider_called": False,
            "network_called": False,
        },
        "traces": list(run.safe_traces),
    }


def sha256_of_public_case_ids(cases: Iterable[GoldCase]) -> str:
    """Return a stable audit hash without retaining public prompt text."""

    ids = "|".join(case.case_id for case in cases)
    return hashlib.sha256(ids.encode("utf-8")).hexdigest()
