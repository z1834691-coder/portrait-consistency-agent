from __future__ import annotations

from pathlib import Path

from portrait_consistency_agent.core.contracts import PhotoRole, QualityFlag
from portrait_consistency_agent.services import tencent_effect_web_e3 as e3
from portrait_consistency_agent.services.photo_quality import PhotoObservation


def _observation(photo_id: str, *, face_count: int = 1, quality: float = 0.92) -> PhotoObservation:
    return PhotoObservation(
        photo_id=photo_id,
        photo_sha256="a" * 64,
        photo_role=PhotoRole.REFERENCE if "reference" in photo_id else PhotoRole.TARGET,
        width=640,
        height=480,
        image_format="JPEG",
        face_count=face_count,
        selected_face_ref=f"{photo_id}_face_0" if face_count == 1 else None,
        quality_confidence=quality,
        editability_confidence=quality,
        quality_flags=(QualityFlag.MULTIPLE_FACES,) if face_count > 1 else (),
        reason_codes=("multiple_faces_require_target_selection",) if face_count > 1 else (),
    )


def test_e3_manifest_redacts_paths_and_keeps_role_and_strata(tmp_path: Path, monkeypatch) -> None:
    reference = tmp_path / "reference.jpg"
    target = tmp_path / "target.jpg"
    reference.write_bytes(b"reference-bytes")
    target.write_bytes(b"target-bytes")

    def fake_analyse(image_bytes: bytes, *, photo_id: str, photo_role: PhotoRole):
        return _observation(photo_id)

    monkeypatch.setattr(e3, "analyze_photo_bytes", fake_analyse)
    report = e3.preflight_e3_samples(
        [
            e3.E3SampleSpec(
                "reference_001",
                reference,
                "reference_candidate",
                angle="front",
                lighting="studio",
                expression="neutral",
            ),
            e3.E3SampleSpec("target_001", target, "target", angle="three_quarter"),
        ]
    )

    projection = report.projection()
    assert report.ready_for_candidate_trials is True
    assert projection["report_contains_image_bytes"] is False
    assert projection["report_contains_local_paths"] is False
    assert projection["items"][0]["file_name"] == "reference.jpg"
    assert str(tmp_path) not in str(projection)
    assert projection["items"][0]["strata"]["lighting"] == "studio"


def test_e3_preflight_rejects_multiface_and_continues_after_it(tmp_path: Path, monkeypatch) -> None:
    reference = tmp_path / "reference.jpg"
    bad = tmp_path / "bad.jpg"
    good = tmp_path / "good.jpg"
    reference.write_bytes(b"reference")
    bad.write_bytes(b"bad")
    good.write_bytes(b"good")

    def fake_analyse(image_bytes: bytes, *, photo_id: str, photo_role: PhotoRole):
        if photo_id == "bad":
            return _observation(photo_id, face_count=2)
        return _observation(photo_id)

    monkeypatch.setattr(e3, "analyze_photo_bytes", fake_analyse)
    report = e3.preflight_e3_samples(
        [
            e3.E3SampleSpec("reference", reference, "reference_candidate"),
            e3.E3SampleSpec("bad", bad, "target"),
            e3.E3SampleSpec("good", good, "target"),
        ]
    )

    assert report.rejected_samples == 1
    assert report.target_samples == 1
    assert report.batch_failure_isolation_ready is True
    assert [item.status for item in report.items] == ["eligible", "rejected", "eligible"]


def test_e3_missing_or_unsupported_file_is_redacted_rejection(tmp_path: Path) -> None:
    unsupported = tmp_path / "unsupported.gif"
    unsupported.write_bytes(b"not-an-image")
    report = e3.preflight_e3_samples(
        [
            e3.E3SampleSpec("unsupported", unsupported, "target"),
        ]
    )

    item = report.projection()["items"][0]
    assert item["status"] == "rejected"
    assert "path_saved" in item and item["path_saved"] is False
    assert "unsupported_file_suffix" in item["reason_codes"]


def _preflight_projection() -> dict[str, object]:
    return {
        "reference_sample_id": "reference_001",
        "items": [
            {
                "sample_id": "reference_001",
                "role": "reference_candidate",
                "status": "eligible",
                "sha256": "a" * 64,
            },
            {
                "sample_id": "target_001",
                "role": "target",
                "status": "warning",
                "sha256": "b" * 64,
            },
        ],
    }


def test_e3_live_evidence_joins_hashes_and_keeps_card_candidate() -> None:
    report = e3.build_e3_evidence_report(
        _preflight_projection(),
        (
            e3.E3LiveReceipt(
                sample_id="reference_001",
                receipt_id="receipt_reference_001",
                input_sha256="a" * 64,
                status="succeeded",
                elapsed_ms=100,
                output_sha256="c" * 64,
                handoff_accepted=True,
                verification_status="metadata_only",
            ),
            e3.E3LiveReceipt(
                sample_id="target_001",
                receipt_id="receipt_target_001",
                input_sha256="b" * 64,
                status="succeeded",
                elapsed_ms=120,
                output_sha256="d" * 64,
                handoff_accepted=True,
                verification_status="metadata_only",
            ),
        ),
        offline_contract_regression_passed=True,
        batch_failure_isolation_verified=True,
        formal_admission_evidence={
            "license_active": True,
            "exact_domain_bound": True,
            "provider_permission_granted": True,
        },
    )
    payload = report.projection()
    assert report.live_success_count == 2
    assert report.sample_hashes_match_preflight is True
    assert report.all_target_receipts_present is True
    assert report.promotion_status == "candidate"
    assert report.visual_generalization_status == "not_established"
    assert "visual_effect_generalization_not_established" in report.blockers
    assert payload["report_contains_data_urls"] is False
    assert payload["report_contains_image_bytes"] is False


def test_e3_live_evidence_rejects_hash_mismatch_and_duplicate_sample() -> None:
    receipt = e3.E3LiveReceipt(
        sample_id="reference_001",
        receipt_id="receipt_reference_002",
        input_sha256="f" * 64,
        status="succeeded",
        elapsed_ms=100,
        output_sha256="c" * 64,
    )
    report = e3.build_e3_evidence_report(
        _preflight_projection(),
        (receipt,),
        offline_contract_regression_passed=True,
        batch_failure_isolation_verified=True,
    )
    assert report.sample_hashes_match_preflight is False
    assert "live_receipt_input_hash_not_linked_to_preflight" in report.blockers

    duplicate = e3.E3LiveReceipt(
        sample_id="reference_001",
        receipt_id="receipt_reference_003",
        input_sha256="a" * 64,
        status="succeeded",
        elapsed_ms=100,
        output_sha256="e" * 64,
    )
    try:
        e3.build_e3_evidence_report(
            _preflight_projection(),
            (receipt, duplicate),
            offline_contract_regression_passed=True,
            batch_failure_isolation_verified=True,
        )
    except ValueError as exc:
        assert "one live receipt per sample" in str(exc)
    else:
        raise AssertionError("duplicate sample receipts must be rejected")


def test_e3_manifest_row_rejects_unknown_payload_field() -> None:
    try:
        e3.E3LiveReceipt.from_mapping(
            {
                "sample_id": "target_001",
                "receipt_id": "receipt_target_001",
                "input_sha256": "a" * 64,
                "status": "succeeded",
                "elapsed_ms": 100,
                "output_sha256": "b" * 64,
                "raw_output_data_url": "data:image/png;base64,not-persisted",
            }
        )
    except ValueError as exc:
        assert "unsupported fields" in str(exc)
    else:
        raise AssertionError("raw output payload must never enter the E3 manifest")


def test_e3_visual_gate_requires_completed_non_worsening_verification() -> None:
    preflight = {
        "reference_sample_id": "reference_001",
        "items": [
            {
                "sample_id": "reference_001",
                "role": "reference_candidate",
                "status": "eligible",
                "sha256": "a" * 64,
            },
            {
                "sample_id": "target_001",
                "role": "target",
                "status": "eligible",
                "sha256": "b" * 64,
            },
        ],
    }
    receipt = e3.E3LiveReceipt(
        sample_id="target_001",
        receipt_id="receipt_target_001",
        request_ref="request_target_001",
        input_sha256="b" * 64,
        status="succeeded",
        elapsed_ms=100,
        output_sha256="c" * 64,
        handoff_accepted=True,
        verification_status="completed",
        verification_id="verification_target_001",
        verification_decision="replan",
        overall_trend="improved",
        target_evidence_sufficient=False,
        measured_feature_count=2,
    )
    report = e3.build_e3_evidence_report(
        preflight,
        (receipt,),
        offline_contract_regression_passed=True,
        batch_failure_isolation_verified=True,
        formal_admission_evidence={
            "license_active": True,
            "exact_domain_bound": True,
            "provider_permission_granted": True,
        },
    )
    assert report.visual_generalization_status == "established"
    assert report.formal_admission_evidence["multi_sample_visual_review_complete"] is True


def test_e3_visual_gate_rejects_unverifiable_or_worsened_target() -> None:
    preflight = {
        "reference_sample_id": "reference_001",
        "items": [
            {
                "sample_id": "reference_001",
                "role": "reference_candidate",
                "status": "eligible",
                "sha256": "a" * 64,
            },
            {
                "sample_id": "target_001",
                "role": "target",
                "status": "eligible",
                "sha256": "b" * 64,
            },
        ],
    }
    receipt = e3.E3LiveReceipt(
        sample_id="target_001",
        receipt_id="receipt_target_002",
        request_ref="request_target_002",
        input_sha256="b" * 64,
        status="succeeded",
        elapsed_ms=100,
        output_sha256="c" * 64,
        handoff_accepted=True,
        verification_status="completed",
        verification_id="verification_target_002",
        verification_decision="manual_review",
        overall_trend="worsened",
        target_evidence_sufficient=False,
        measured_feature_count=2,
    )
    report = e3.build_e3_evidence_report(
        preflight,
        (receipt,),
        offline_contract_regression_passed=True,
        batch_failure_isolation_verified=True,
    )
    assert report.visual_generalization_status == "not_established"
    assert "visual_effect_generalization_not_established" in report.blockers
