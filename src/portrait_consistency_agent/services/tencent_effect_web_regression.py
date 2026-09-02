"""Offline regression harness for the Tencent Effect Web result handoff.

The browser SDK is an external, licensed JavaScript surface, so a local
regression suite cannot pretend to reproduce its visual effects.  This module
tests the part the product owns: a collection of Browser Receipt/result pairs
must be validated independently, malformed or mismatched results must be
rejected, and one bad sample must not prevent the remaining samples from being
checked.  It never calls Tencent, reads a photo from disk, or persists result
bytes/data URLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from portrait_consistency_agent.services.tencent_effect_web import (
    EffectWebRequest,
    TencentEffectWebAdapter,
    TencentEffectWebConfigurationError,
)

ExpectedSampleOutcome = Literal["accepted_success", "accepted_failure", "rejected"]


@dataclass(frozen=True)
class EffectWebRegressionSample:
    """One redacted request/receipt/result fixture.

    ``result`` is accepted only as an ephemeral input to the validator.  It is
    deliberately not copied into the report or the returned trace.
    """

    case_id: str
    category: str
    request: EffectWebRequest
    receipt: dict[str, object]
    result: dict[str, object] | None
    expected: ExpectedSampleOutcome


@dataclass(frozen=True)
class EffectWebRegressionItem:
    case_id: str
    category: str
    expected: ExpectedSampleOutcome
    observed: Literal["accepted_success", "accepted_failure", "rejected"]
    passed: bool
    anomaly_code: str | None
    output_bytes_seen: int
    trace: tuple[dict[str, object], ...]

    def projection(self) -> dict[str, object]:
        """Return a report-safe item without payloads or image bytes."""

        return {
            "case_id": self.case_id,
            "category": self.category,
            "expected": self.expected,
            "observed": self.observed,
            "passed": self.passed,
            "anomaly_code": self.anomaly_code,
            "output_bytes_seen": self.output_bytes_seen,
            "trace": list(self.trace),
            "result_payload_persisted": False,
        }


@dataclass(frozen=True)
class EffectWebRegressionReport:
    suite_version: str
    total: int
    passed: int
    failed: int
    rejected_cases: int
    accepted_successes: int
    accepted_failures: int
    batch_failure_isolation_passed: bool
    hard_safety_passed: bool
    items: tuple[EffectWebRegressionItem, ...]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def projection(self) -> dict[str, object]:
        return {
            "suite_version": self.suite_version,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "rejected_cases": self.rejected_cases,
            "accepted_successes": self.accepted_successes,
            "accepted_failures": self.accepted_failures,
            "batch_failure_isolation_passed": self.batch_failure_isolation_passed,
            "hard_safety_passed": self.hard_safety_passed,
            "result_payloads_persisted": False,
            "items": [item.projection() for item in self.items],
        }


def _anomaly_code(exc: Exception) -> str:
    text = str(exc).lower()
    if "request_ref" in text:
        return "request_ref_mismatch"
    if "input hash" in text:
        return "input_hash_mismatch"
    if "output hash" in text:
        return "output_hash_mismatch"
    if "input hash" in text:
        return "input_hash_mismatch"
    if "dimension" in text:
        return "dimensions_mismatch"
    if "mime" in text or "data url" in text:
        return "result_format_invalid"
    if "size" in text or "8mb" in text or "6mb" in text or "too_long" in text or "too long" in text:
        return "result_size_exceeded"
    if "failed browser receipt" in text or "failed" in text:
        return "failed_receipt_result_conflict"
    return "browser_contract_invalid"


def evaluate_effect_web_sample(
    adapter: TencentEffectWebAdapter,
    sample: EffectWebRegressionSample,
) -> EffectWebRegressionItem:
    """Evaluate one sample and keep going even when the sample is malformed."""

    trace: list[dict[str, object]] = [
        {
            "step": "regression_sample_received",
            "case_id": sample.case_id,
            "category": sample.category,
            "expected": sample.expected,
            "payload_read": True,
            "payload_persisted": False,
        }
    ]
    output_bytes_seen = 0
    observed: Literal["accepted_success", "accepted_failure", "rejected"] = "rejected"
    anomaly_code: str | None = None
    try:
        receipt = adapter.validate_browser_receipt(sample.receipt, request=sample.request)
        trace.append(
            {
                "step": "receipt_contract_validation",
                "status": "passed",
                "receipt_status": receipt.status,
                "request_ref_bound": True,
                "hash_bound": receipt.input_sha256 in {None, sample.request.input_artifact_sha256},
            }
        )
        if receipt.status == "succeeded":
            result_bytes = adapter.validate_browser_result(
                sample.result or {},
                request=sample.request,
                receipt=receipt,
            )
            output_bytes_seen = len(result_bytes)
            observed = "accepted_success"
            trace.append(
                {
                    "step": "result_handoff_validation",
                    "status": "passed",
                    "decoded_bytes_in_memory": output_bytes_seen,
                    "result_persisted": False,
                }
            )
        else:
            observed = "accepted_failure"
            trace.append(
                {
                    "step": "failed_receipt_route",
                    "status": "passed",
                    "safe_error_code_present": bool(receipt.error_code),
                    "result_persisted": False,
                }
            )
    except (TypeError, ValueError, TencentEffectWebConfigurationError) as exc:
        anomaly_code = _anomaly_code(exc)
        trace.append(
            {
                "step": "contract_anomaly_detected",
                "status": "rejected",
                "anomaly_code": anomaly_code,
                "error_type": type(exc).__name__,
                "result_persisted": False,
            }
        )

    passed = observed == sample.expected
    trace.append(
        {
            "step": "regression_case_verdict",
            "status": "passed" if passed else "failed",
            "observed": observed,
            "expected": sample.expected,
            "result_payload_persisted": False,
        }
    )
    return EffectWebRegressionItem(
        case_id=sample.case_id,
        category=sample.category,
        expected=sample.expected,
        observed=observed,
        passed=passed,
        anomaly_code=anomaly_code,
        output_bytes_seen=output_bytes_seen,
        trace=tuple(trace),
    )


def run_effect_web_regression(
    adapter: TencentEffectWebAdapter,
    samples: tuple[EffectWebRegressionSample, ...],
    *,
    suite_version: str = "effect_web_regression_v0.1",
) -> EffectWebRegressionReport:
    """Run a deterministic, failure-isolated Web handoff regression suite."""

    items = tuple(evaluate_effect_web_sample(adapter, sample) for sample in samples)
    passed = sum(item.passed for item in items)
    rejected = sum(item.observed == "rejected" for item in items)
    accepted_successes = sum(item.observed == "accepted_success" for item in items)
    accepted_failures = sum(item.observed == "accepted_failure" for item in items)
    expected_rejected = sum(item.expected == "rejected" for item in items)
    first_rejected_index = next(
        (index for index, item in enumerate(items) if item.observed == "rejected"),
        None,
    )
    batch_failure_isolation_passed = first_rejected_index is not None and any(
        index > first_rejected_index and item.observed in {"accepted_success", "accepted_failure"}
        for index, item in enumerate(items)
    )
    # Hard safety answers one question: did every deliberately malformed or
    # tampered sample get rejected?  Failure isolation is a separate E2 gate;
    # a suite whose rejected sample happens to be last must not be reported as
    # a safety failure merely because it did not contain a later sample to
    # prove continuation.
    hard_safety_passed = (
        all(item.passed for item in items if item.expected == "rejected")
        and rejected == expected_rejected
    )
    return EffectWebRegressionReport(
        suite_version=suite_version,
        total=len(items),
        passed=passed,
        failed=len(items) - passed,
        rejected_cases=rejected,
        accepted_successes=accepted_successes,
        accepted_failures=accepted_failures,
        batch_failure_isolation_passed=batch_failure_isolation_passed,
        hard_safety_passed=hard_safety_passed,
        items=items,
    )
