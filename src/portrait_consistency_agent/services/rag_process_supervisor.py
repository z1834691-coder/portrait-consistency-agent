"""Fair, answerless RAG process runner and independent process supervisor.

The historical Gold runner mixed three different things into one prediction:
natural-language projection, retrieval facts, and evaluation aliases.  This
module creates a clean evidence boundary before any answer key is joined:

* the compiler may report a transient interpretation of the question;
* a validated :class:`RagQuery` is always sent through the local RAG path,
  including an explicit neutral fallback when compilation is unknown;
* the retrieval prediction is built only from the actual retrieval result;
* an independent supervisor checks stage coverage, lineage, answer leakage,
  and forbidden external calls before a quality scorer may consume a run.

It is deliberately offline.  It reads no annotations, hidden answers,
photos, vectors, secrets, LLMs, or providers.  The supervisor is a process
judge, not a semantic quality judge: a PASS means that the exam procedure is
complete and auditable, not that the RAG answers are correct.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from portrait_consistency_agent.core.rag_contracts import RagQuery, RagStage
from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_evidence_selection_candidate import (
    EvidenceSelectionDecision,
)
from portrait_consistency_agent.services.rag_gold_baseline import (
    BaselineProjection,
    _query_for_projection,
    project_runtime_prompt,
)
from portrait_consistency_agent.services.rag_gold_eval import GoldCase
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever, RagP0BRun
from portrait_consistency_agent.services.rag_route_handoff_candidate import RouteHandoffDecision
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

FAIR_EVALUATION_VERSION = "rag-fair-evaluation-v0.1"
PROCESS_SUPERVISOR_VERSION = "rag-process-supervisor-v0.1"

FairQueryBuilder = Callable[[GoldCase, BaselineProjection], tuple[RagQuery, bool]]
QueryTermExpander = Callable[[RagQuery], Iterable[str]]
RouteHandoff = Callable[[BaselineProjection, RagQuery, RagP0BRun], RouteHandoffDecision]
EvidenceSelection = Callable[[RagQuery, RagP0BRun], EvidenceSelectionDecision]

_FORBIDDEN_KEYS = frozenset(
    {
        "gold_route",
        "gold_routes",
        "gold_evidence",
        "gold_evidence_relations",
        "prohibited_events",
        "hard_safety",
        "must_not",
        "answer_key",
        "answer_key_read",
        "annotations",
        "annotation",
    }
)
_RAW_TEXT_KEYS = frozenset({"query", "question", "raw_prompt", "prompt_text", "user_text"})
_EXTERNAL_POLICY_KEYS = (
    "hidden_answer_key_read",
    "annotations_read",
    "network_called",
    "llm_called",
    "provider_api_called",
    "external_provider_called",
    "photo_or_face_vector_read",
    "raw_prompt_persisted",
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _case_hash(case_id: str) -> str:
    return _sha256(case_id)


def _query_id(case_id: str) -> str:
    """Make a trace identifier that does not expose the holdout case ID."""

    return f"fair_q_{_case_hash(case_id)[:24]}"


def _json_safe(value: object) -> object:
    """Return a JSON-safe copy without preserving arbitrary custom objects."""

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _query_for_fair_run(case: GoldCase, projection: BaselineProjection) -> tuple[RagQuery, bool]:
    """Build a query for every case without putting projection facts in a prediction.

    A known projection is used only to create structured retrieval slots.  If
    the compiler cannot represent the sentence, the case still receives an
    explicit neutral quality-gate query.  That fallback is counted in the
    compiler track and is *not* presented as a successful understanding.
    """

    projected = _query_for_projection(case, projection)
    if projected is not None:
        return projected.model_copy(update={"query_id": _query_id(case.case_id)}), True
    return (
        RagQuery(
            query_id=_query_id(case.case_id),
            stage=RagStage.QUALITY_GATE,
            region="local_demo",
            outbound_allowed=False,
            adapter_required=False,
            intent_slots_present=["fair_evaluation_unknown_projection"],
        ),
        False,
    )


def _retrieval_refs(retrieval: object) -> tuple[str, ...]:
    result = getattr(retrieval, "result", None)
    evidences = getattr(result, "evidences", []) if result is not None else []
    return tuple(
        str(evidence.knowledge_ref)
        for evidence in evidences
        if getattr(evidence, "knowledge_ref", None)
    )


def _adopted_refs(retrieval: object) -> tuple[str, ...]:
    result = getattr(retrieval, "result", None)
    refs = getattr(result, "knowledge_refs", []) if result is not None else []
    return tuple(str(ref) for ref in refs)


def _relation_map(retrieval: object) -> dict[str, str]:
    result = getattr(retrieval, "result", None)
    evidences = getattr(result, "evidences", []) if result is not None else []
    return {
        str(evidence.knowledge_ref): str(evidence.relation.value)
        for evidence in evidences
        if getattr(evidence, "knowledge_ref", None)
    }


@dataclass(frozen=True)
class FairEvaluationRun:
    """A complete answerless run, kept in memory until the report is redacted."""

    dataset_version: str
    runtime_mode: str
    predictions: tuple[dict[str, object], ...]
    traces: tuple[dict[str, object], ...]
    knowledge_snapshot: Mapping[str, object]
    policy: Mapping[str, object]


@dataclass(frozen=True)
class ProcessViolation:
    """One deterministic process-integrity finding."""

    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class FairCaseAudit:
    """Supervisor result for one case; the question text is never retained."""

    case_id: str
    compiler_track: str
    retrieval_track: str
    required_stages: Mapping[str, bool]
    violations: tuple[ProcessViolation, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_dict(self, *, ordinal: int, redact_case_id: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "case_ordinal": ordinal,
            "case_id_sha256": _case_hash(self.case_id),
            "compiler_track": self.compiler_track,
            "retrieval_track": self.retrieval_track,
            "required_stages": dict(self.required_stages),
            "process_status": "PASS" if self.passed else "FAIL",
            "violations": [item.to_dict() for item in self.violations],
        }
        if not redact_case_id:
            payload["case_id"] = self.case_id
        return payload


@dataclass(frozen=True)
class FairProcessAuditReport:
    """Aggregate process gate; it is not a semantic quality score."""

    dataset_version: str
    runtime_mode: str
    run_id: str
    case_count: int
    trace_count: int
    prediction_count: int
    eligible_count: int
    excluded_count: int
    process_gate: str
    quality_scoring_gate: str
    policy: Mapping[str, object]
    counts: Mapping[str, int]
    violations_by_code: Mapping[str, int]
    case_audits: tuple[FairCaseAudit, ...] = field(default_factory=tuple)

    def to_dict(self, *, redact_case_ids: bool = True) -> dict[str, object]:
        return {
            "supervisor_version": PROCESS_SUPERVISOR_VERSION,
            "dataset_version": self.dataset_version,
            "runtime_mode": self.runtime_mode,
            "run_id": self.run_id,
            "case_count": self.case_count,
            "trace_count": self.trace_count,
            "prediction_count": self.prediction_count,
            "eligible_count": self.eligible_count,
            "excluded_count": self.excluded_count,
            "process_gate": self.process_gate,
            "quality_scoring_gate": self.quality_scoring_gate,
            "policy": dict(self.policy),
            "counts": dict(self.counts),
            "violations_by_code": dict(self.violations_by_code),
            "case_audits": [
                audit.to_dict(ordinal=index, redact_case_id=redact_case_ids)
                for index, audit in enumerate(self.case_audits, start=1)
            ],
        }


def _nested_keys(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _nested_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_keys(child)


def _forbidden_field_violations(value: object) -> list[ProcessViolation]:
    violations: list[ProcessViolation] = []
    for raw_key in _nested_keys(value):
        key = raw_key.casefold()
        if key in _FORBIDDEN_KEYS or key.startswith("gold_"):
            violations.append(ProcessViolation("ANSWER_OR_GOLD_FIELD_PRESENT", raw_key))
        if key in _RAW_TEXT_KEYS:
            violations.append(ProcessViolation("RAW_QUESTION_FIELD_PRESENT", raw_key))
    return violations


def _global_policy_violations(policy: Mapping[str, object]) -> list[ProcessViolation]:
    violations: list[ProcessViolation] = []
    for key in _EXTERNAL_POLICY_KEYS:
        value = policy.get(key)
        if value is not False:
            violations.append(ProcessViolation("FORBIDDEN_SIDE_EFFECT_OR_LEAK", f"{key}={value!r}"))
    if policy.get("quality_score_joined") is True:
        violations.append(
            ProcessViolation("GOLD_JOINED_BEFORE_PROCESS_GATE", "quality_score_joined=true")
        )
    return violations


def _step_names(retrieval_trace: object) -> set[str]:
    if not isinstance(retrieval_trace, list):
        return set()
    return {
        str(event.get("step"))
        for event in retrieval_trace
        if isinstance(event, Mapping) and event.get("step")
    }


def _candidate_refs_from_trace(retrieval_trace: object) -> set[str]:
    refs: set[str] = set()
    if not isinstance(retrieval_trace, list):
        return refs
    for event in retrieval_trace:
        if not isinstance(event, Mapping):
            continue
        records = event.get("candidate_rank_records")
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, Mapping) and record.get("knowledge_ref"):
                refs.add(str(record["knowledge_ref"]))
    return refs


class RagProcessSupervisor:
    """Independent deterministic process judge for an answerless run."""

    def audit(
        self,
        *,
        dataset_version: str,
        runtime_mode: str,
        run_id: str,
        case_ids: Sequence[str],
        traces: Sequence[Mapping[str, object]],
        predictions: Sequence[Mapping[str, object]],
        policy: Mapping[str, object],
        redact_case_ids: bool = True,
    ) -> FairProcessAuditReport:
        input_ids = tuple(str(value) for value in case_ids)
        trace_by_id: dict[str, Mapping[str, object]] = {}
        prediction_by_id: dict[str, Mapping[str, object]] = {}
        global_violations = _global_policy_violations(policy)
        for trace in traces:
            case_id = trace.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                continue
            if case_id in trace_by_id:
                global_violations.append(ProcessViolation("DUPLICATE_TRACE_CASE", case_id))
            trace_by_id[case_id] = trace
            global_violations.extend(_forbidden_field_violations(trace))
        for prediction in predictions:
            case_id = prediction.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                continue
            if case_id in prediction_by_id:
                global_violations.append(ProcessViolation("DUPLICATE_PREDICTION_CASE", case_id))
            prediction_by_id[case_id] = prediction
            global_violations.extend(_forbidden_field_violations(prediction))

        input_counter = Counter(input_ids)
        if any(count > 1 for count in input_counter.values()):
            global_violations.append(
                ProcessViolation("DUPLICATE_INPUT_CASE", "input case IDs repeat")
            )
        expected = set(input_ids)
        missing_trace = expected - set(trace_by_id)
        extra_trace = set(trace_by_id) - expected
        missing_prediction = expected - set(prediction_by_id)
        extra_prediction = set(prediction_by_id) - expected
        if missing_trace:
            global_violations.append(
                ProcessViolation("MISSING_CASE_TRACE", f"count={len(missing_trace)}")
            )
        if extra_trace:
            global_violations.append(
                ProcessViolation("UNEXPECTED_TRACE_CASE", f"count={len(extra_trace)}")
            )
        if missing_prediction:
            global_violations.append(
                ProcessViolation("MISSING_CASE_PREDICTION", f"count={len(missing_prediction)}")
            )
        if extra_prediction:
            global_violations.append(
                ProcessViolation("UNEXPECTED_PREDICTION_CASE", f"count={len(extra_prediction)}")
            )

        case_audits: list[FairCaseAudit] = []
        for case_id in input_ids:
            trace = trace_by_id.get(case_id, {})
            prediction = prediction_by_id.get(case_id, {})
            case_violations = list(_forbidden_field_violations(trace))
            case_violations.extend(_forbidden_field_violations(prediction))
            compiler = trace.get("compiler")
            retrieval = trace.get("retrieval")
            pred = trace.get("prediction")
            governance = trace.get("governance")
            compiler_ok = isinstance(compiler, Mapping)
            retrieval_ok = isinstance(retrieval, Mapping)
            pred_ok = isinstance(pred, Mapping)
            governance_ok = isinstance(governance, Mapping)
            required = {
                "compiler_input_hash": bool(
                    compiler_ok
                    and isinstance(compiler.get("input_sha256"), str)
                    and len(str(compiler.get("input_sha256"))) == 64
                ),
                "compiler_status_explicit": bool(
                    compiler_ok and compiler.get("status") in {"structured", "unknown_fallback"}
                ),
                "validated_query": bool(compiler_ok and isinstance(compiler.get("query_id"), str)),
                "retrieval_trace_present": bool(
                    retrieval_ok
                    and isinstance(retrieval.get("trace"), list)
                    and bool(retrieval.get("trace"))
                ),
                "retrieval_query_contract": False,
                "retrieval_route": False,
                "prediction_lineage": bool(
                    pred_ok
                    and pred.get("evidence_source") == "retrieval_result"
                    and (
                        pred.get("route_source") == "retrieval_result"
                        or (
                            pred.get("route_source") == "validated_route_handoff"
                            and isinstance(trace.get("route_handoff"), Mapping)
                            and trace.get("route_handoff", {}).get("accepted") is True
                            and trace.get("route_handoff", {}).get("selected_route")
                            == pred.get("route")
                            and trace.get("route_handoff", {}).get("execution_authorized") is False
                        )
                    )
                ),
                "finalized": bool(trace.get("finalized") is True),
                "governance_boundary": governance_ok,
                "route_handoff_lineage": True,
                "evidence_selection_lineage": True,
            }
            if pred_ok and pred.get("route_source") == "validated_route_handoff":
                handoff = trace.get("route_handoff")
                required["route_handoff_lineage"] = bool(
                    isinstance(handoff, Mapping)
                    and handoff.get("accepted") is True
                    and handoff.get("selected_route") == pred.get("route")
                    and handoff.get("proposal_only") is True
                    and handoff.get("execution_authorized") is False
                )
            if pred_ok and isinstance(trace.get("evidence_selection"), Mapping):
                selection = trace.get("evidence_selection", {})
                selected = selection.get("selected_refs", [])
                actual = (
                    trace.get("retrieval", {}).get("actual_evidence_refs", [])
                    if isinstance(trace.get("retrieval"), Mapping)
                    else []
                )
                required["evidence_selection_lineage"] = bool(
                    selection.get("accepted") is True
                    and selection.get("proposal_only") is True
                    and selection.get("execution_authorized") is False
                    and isinstance(selected, list)
                    and len(selected) <= 3
                    and all(isinstance(item, str) and item in actual for item in selected)
                )
            retrieval_trace = retrieval.get("trace") if retrieval_ok else []
            steps = _step_names(retrieval_trace)
            required["retrieval_query_contract"] = "query_contract" in steps
            required["retrieval_route"] = "route" in steps
            for name, passed in required.items():
                if not passed:
                    case_violations.append(ProcessViolation("MISSING_REQUIRED_STAGE", name))

            if isinstance(governance, Mapping):
                for key in _EXTERNAL_POLICY_KEYS:
                    if governance.get(key) is not False:
                        case_violations.append(
                            ProcessViolation(
                                "FORBIDDEN_SIDE_EFFECT_OR_LEAK", f"{key}={governance.get(key)!r}"
                            )
                        )
            else:
                case_violations.append(ProcessViolation("MISSING_GOVERNANCE_FACTS", "governance"))

            if "projection" in trace or "projection" in prediction:
                case_violations.append(
                    ProcessViolation(
                        "PROJECTION_INJECTED_INTO_EVALUATION", "projection field present"
                    )
                )
            if "evidence_aliases" in trace or "evidence_aliases" in prediction:
                case_violations.append(
                    ProcessViolation(
                        "PROJECTION_EVIDENCE_ALIAS_PRESENT", "evidence_aliases field present"
                    )
                )

            if retrieval_ok:
                actual_refs = retrieval.get("actual_evidence_refs", [])
                adopted_refs = retrieval.get("adopted_evidence_refs", [])
                if not isinstance(actual_refs, list) or not all(
                    isinstance(item, str) for item in actual_refs
                ):
                    case_violations.append(
                        ProcessViolation("MISSING_RETRIEVAL_EVIDENCE_LINEAGE", "actual refs")
                    )
                    actual_refs = []
                if not isinstance(adopted_refs, list) or not all(
                    isinstance(item, str) for item in adopted_refs
                ):
                    case_violations.append(
                        ProcessViolation("MISSING_RETRIEVAL_EVIDENCE_LINEAGE", "adopted refs")
                    )
                    adopted_refs = []
                if pred_ok:
                    pred_refs = pred.get("evidence_refs", [])
                    if not isinstance(pred_refs, list) or not all(
                        isinstance(item, str) for item in pred_refs
                    ):
                        case_violations.append(
                            ProcessViolation("PREDICTION_EVIDENCE_SHAPE_INVALID", "evidence_refs")
                        )
                    else:
                        selection = trace.get("evidence_selection")
                        selected_via_candidate = isinstance(selection, Mapping)
                        allowed_refs = actual_refs if selected_via_candidate else adopted_refs
                        if not set(pred_refs).issubset(set(allowed_refs)):
                            case_violations.append(
                                ProcessViolation(
                                    "PREDICTION_EVIDENCE_NOT_RETRIEVED",
                                    "prediction refs not in allowed retrieval lineage",
                                )
                            )
                trace_refs = _candidate_refs_from_trace(retrieval_trace)
                if trace_refs and not set(actual_refs).intersection(trace_refs):
                    case_violations.append(
                        ProcessViolation(
                            "RETRIEVAL_LINEAGE_MISMATCH", "result refs absent from candidate trace"
                        )
                    )

            case_audits.append(
                FairCaseAudit(
                    case_id=case_id,
                    compiler_track=(
                        "structured"
                        if required["compiler_status_explicit"]
                        and compiler.get("status") == "structured"
                        else "unknown_fallback"
                    ),
                    retrieval_track=("complete" if all(required.values()) else "incomplete"),
                    required_stages=required,
                    violations=tuple(case_violations),
                )
            )

        # Global findings are attached to the first synthetic case only in the
        # private in-memory object; the serialized report keeps their counts.
        if global_violations and case_audits:
            first = case_audits[0]
            case_audits[0] = FairCaseAudit(
                case_id=first.case_id,
                compiler_track=first.compiler_track,
                retrieval_track=first.retrieval_track,
                required_stages=first.required_stages,
                violations=tuple((*first.violations, *global_violations)),
            )

        violations = [item for audit in case_audits for item in audit.violations]
        violations.extend(global_violations if not case_audits else [])
        violations_by_code = Counter(item.code for item in violations)
        eligible = sum(1 for audit in case_audits if audit.passed)
        gate = (
            "PASS" if len(case_audits) == len(input_ids) and eligible == len(input_ids) else "FAIL"
        )
        quality_gate = (
            "READY_AFTER_SEPARATE_GOLD_JOIN" if gate == "PASS" else "LOCKED_PROCESS_AUDIT"
        )
        counts = {
            "input_cases": len(input_ids),
            "trace_cases": len(trace_by_id),
            "prediction_cases": len(prediction_by_id),
            "compiler_structured": sum(a.compiler_track == "structured" for a in case_audits),
            "compiler_unknown_fallback": sum(
                a.compiler_track == "unknown_fallback" for a in case_audits
            ),
            "retrieval_complete": sum(a.retrieval_track == "complete" for a in case_audits),
            "retrieval_incomplete": sum(a.retrieval_track != "complete" for a in case_audits),
            "case_pass": eligible,
            "case_fail": len(case_audits) - eligible,
        }
        safe_policy = {
            "answerless_runtime": True,
            "hidden_answer_key_read": False,
            "answer_key_read": False,
            "annotations_read": False,
            "quality_score_joined": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "external_provider_called": False,
            "photo_or_face_vector_read": False,
            "raw_prompt_persisted": False,
            "projection_injected_into_prediction": any(
                item.code == "PROJECTION_INJECTED_INTO_EVALUATION" for item in violations
            ),
            "redacted_case_ids": redact_case_ids,
        }
        return FairProcessAuditReport(
            dataset_version=dataset_version,
            runtime_mode=runtime_mode,
            run_id=run_id,
            case_count=len(input_ids),
            trace_count=len(traces),
            prediction_count=len(predictions),
            eligible_count=eligible,
            excluded_count=len(input_ids) - eligible,
            process_gate=gate,
            quality_scoring_gate=quality_gate,
            policy=safe_policy,
            counts=counts,
            violations_by_code=dict(violations_by_code),
            case_audits=tuple(case_audits),
        )


class RagFairEvaluationRunner:
    """Run every answerless case through a separated compiler/retrieval trace."""

    def run(
        self,
        cases: Iterable[GoldCase],
        *,
        dataset_version: str,
        runtime_mode: str,
        projection_compiler: Callable[[GoldCase], tuple[BaselineProjection, object]] | None = None,
        compiler_version: str = "project-runtime-prompt-v0.2",
        knowledge_seeder: Callable[[LocalKnowledgeStore], object] | None = None,
        query_builder: FairQueryBuilder | None = None,
        relation_resolver: Callable[[RagQuery, object, object], object] | None = None,
        query_term_expander: QueryTermExpander | None = None,
        operation_coverage: bool = False,
        route_handoff: RouteHandoff | None = None,
        evidence_selection: EvidenceSelection | None = None,
    ) -> FairEvaluationRun:
        case_list = tuple(cases)
        if not case_list:
            raise ValueError("fair evaluation requires at least one answerless case")
        if len({case.case_id for case in case_list}) != len(case_list):
            raise ValueError("fair evaluation case IDs must be unique")
        with tempfile.TemporaryDirectory(prefix="portrait-rag-fair-evaluation-") as directory:
            root = Path(directory)
            store = LocalKnowledgeStore(root / "knowledge.sqlite3")
            store.initialize()
            seed_reviewed_provider_knowledge(store)
            if knowledge_seeder is not None:
                # Candidate experiments may add reviewed policy knowledge in
                # an isolated temporary store.  The active runtime seeder is
                # unchanged, so this cannot silently promote a new source.
                knowledge_seeder(store)
            retriever = RagP0BHybridRetriever(
                store=store,
                dense_index=LocalDenseIndex(root / "knowledge_vectors.sqlite3"),
                embedding_backend=DeterministicTokenEmbeddingBackend(),
                reranker_backend=TokenOverlapReranker(),
                relation_resolver=relation_resolver,  # type: ignore[arg-type]
                query_term_expander=query_term_expander,
                operation_coverage=operation_coverage,
            )
            service = RagAdvisoryService(store=store, retriever=retriever)
            predictions: list[dict[str, object]] = []
            traces: list[dict[str, object]] = []
            for case in case_list:
                if projection_compiler is not None:
                    projection, _signals = projection_compiler(case)
                else:
                    projection = project_runtime_prompt(case)
                query, structured = (
                    query_builder(case, projection)
                    if query_builder is not None
                    else _query_for_fair_run(case, projection)
                )
                advisory = service.advise(
                    query=query,
                    existing_baseline_available=False,
                    advice_id=f"fair_advice_{_case_hash(case.case_id)[:24]}",
                )
                retrieval = advisory.retrieval
                actual_refs = list(_retrieval_refs(retrieval))
                adopted_refs = list(_adopted_refs(retrieval))
                relation_map = _relation_map(retrieval)
                retrieval_route = retrieval.result.route.value
                handoff_decision = (
                    route_handoff(projection, query, retrieval)
                    if route_handoff is not None
                    else None
                )
                evidence_selection_decision = (
                    evidence_selection(query, retrieval) if evidence_selection is not None else None
                )
                final_route = (
                    handoff_decision.selected_route
                    if handoff_decision is not None and handoff_decision.accepted
                    else retrieval_route
                )
                route_source = (
                    "validated_route_handoff"
                    if handoff_decision is not None and handoff_decision.accepted
                    else "retrieval_result"
                )
                prediction_evidence_refs = (
                    list(evidence_selection_decision.selected_refs)
                    if evidence_selection_decision is not None
                    and evidence_selection_decision.accepted
                    else adopted_refs
                )
                prediction_evidence_relations = (
                    dict(evidence_selection_decision.selected_relations)
                    if evidence_selection_decision is not None
                    and evidence_selection_decision.accepted
                    else {ref: relation_map[ref] for ref in adopted_refs if ref in relation_map}
                )
                prediction = {
                    "case_id": case.case_id,
                    "route": final_route,
                    "evidence_refs": prediction_evidence_refs,
                    "evidence_relations": prediction_evidence_relations,
                    "route_source": route_source,
                    "evidence_source": "retrieval_result",
                    "trace_ref": f"{FAIR_EVALUATION_VERSION}:{_case_hash(case.case_id)[:24]}",
                }
                safe_trace = {
                    "case_id": case.case_id,
                    "runner_version": FAIR_EVALUATION_VERSION,
                    "compiler": {
                        "compiler_version": compiler_version,
                        "status": "structured" if structured else "unknown_fallback",
                        "input_sha256": _sha256(case.query),
                        "query_id": query.query_id,
                        "query_created": structured,
                        "proposed_route": projection.route_override,
                        "category_codes": list(projection.category_codes),
                        "requested_feature_count": len(projection.requested_features),
                        "retriever_kind": projection.retriever_kind,
                    },
                    "retrieval": {
                        "query_id": query.query_id,
                        "query_sha256": retrieval.result.query_sha256,
                        "route": retrieval_route,
                        "actual_evidence_refs": actual_refs,
                        "adopted_evidence_refs": adopted_refs,
                        "evidence_relations": relation_map,
                        "trace": list(retrieval.trace),
                    },
                    "prediction": prediction,
                    "governance": {
                        "hidden_answer_key_read": False,
                        "annotations_read": False,
                        "network_called": False,
                        "llm_called": False,
                        "provider_api_called": False,
                        "external_provider_called": False,
                        "photo_or_face_vector_read": False,
                        "raw_prompt_persisted": False,
                        "quality_score_joined": False,
                    },
                    "finalized": True,
                }
                if handoff_decision is not None:
                    safe_trace["route_handoff"] = handoff_decision.to_trace()
                if evidence_selection_decision is not None:
                    safe_trace["evidence_selection"] = evidence_selection_decision.to_trace()
                predictions.append(prediction)
                traces.append(safe_trace)
            snapshot = store.snapshot()
        return FairEvaluationRun(
            dataset_version=dataset_version,
            runtime_mode=runtime_mode,
            predictions=tuple(predictions),
            traces=tuple(traces),
            knowledge_snapshot=snapshot,
            policy={
                "answerless_runtime": True,
                "hidden_answer_key_read": False,
                "answer_key_read": False,
                "annotations_read": False,
                "network_called": False,
                "llm_called": False,
                "provider_api_called": False,
                "external_provider_called": False,
                "photo_or_face_vector_read": False,
                "raw_prompt_persisted": False,
                "projection_injected_into_prediction": False,
                "quality_score_joined": False,
            },
        )


def audit_fair_run(run: FairEvaluationRun, *, run_id: str) -> FairProcessAuditReport:
    """Audit a fresh fair run without opening an answer key."""

    case_ids = [str(case.get("case_id")) for case in run.predictions]
    return RagProcessSupervisor().audit(
        dataset_version=run.dataset_version,
        runtime_mode=run.runtime_mode,
        run_id=run_id,
        case_ids=case_ids,
        traces=run.traces,
        predictions=run.predictions,
        policy=run.policy,
    )


def audit_trace_payload(
    *,
    dataset_version: str,
    runtime_mode: str,
    run_id: str,
    case_ids: Sequence[str],
    traces: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    policy: Mapping[str, object],
) -> FairProcessAuditReport:
    """Audit an existing redacted snapshot, useful for historical evidence."""

    return RagProcessSupervisor().audit(
        dataset_version=dataset_version,
        runtime_mode=runtime_mode,
        run_id=run_id,
        case_ids=case_ids,
        traces=traces,
        predictions=predictions,
        policy=policy,
    )


def fair_run_payload(run: FairEvaluationRun) -> dict[str, object]:
    """Serialize a fair run for internal review without questions or answers."""

    return {
        "runner_version": FAIR_EVALUATION_VERSION,
        "dataset_version": run.dataset_version,
        "runtime_mode": run.runtime_mode,
        "policy": dict(run.policy),
        "knowledge_snapshot": dict(run.knowledge_snapshot),
        "rows": [
            {key: value for key, value in row.items() if key != "case_id"}
            | {"case_id_sha256": _case_hash(str(row["case_id"]))}
            for row in run.predictions
        ],
    }


def fair_trace_payload(run: FairEvaluationRun) -> dict[str, object]:
    """Serialize traces with hashed case IDs for the safe report boundary."""

    redacted: list[dict[str, object]] = []
    for row in run.traces:
        copy = dict(row)
        case_id = str(copy.pop("case_id", ""))
        prediction = copy.get("prediction")
        if isinstance(prediction, Mapping):
            prediction_copy = dict(prediction)
            prediction_copy.pop("case_id", None)
            copy["prediction"] = prediction_copy
        copy["case_id_sha256"] = _case_hash(case_id)
        redacted.append(_json_safe(copy))  # type: ignore[arg-type]
    return {
        "runner_version": FAIR_EVALUATION_VERSION,
        "dataset_version": run.dataset_version,
        "runtime_mode": run.runtime_mode,
        "policy": dict(run.policy),
        "traces": redacted,
    }


__all__ = [
    "FAIR_EVALUATION_VERSION",
    "PROCESS_SUPERVISOR_VERSION",
    "FairEvaluationRun",
    "FairProcessAuditReport",
    "RagFairEvaluationRunner",
    "RagProcessSupervisor",
    "audit_fair_run",
    "audit_trace_payload",
    "fair_run_payload",
    "fair_trace_payload",
]
