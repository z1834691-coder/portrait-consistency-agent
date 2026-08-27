from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import numpy as np
from PIL import Image

from portrait_consistency_agent.core.contracts import (
    ContentSafetyEvidence,
    ContentSafetyStatus,
    PhotoRole,
    QualityFlag,
    QualityRoute,
    SubjectMatchStatus,
)
from portrait_consistency_agent.services import photo_quality


def image_bytes(*, width: int = 320, height: int = 320, color: int = 128) -> bytes:
    image = Image.fromarray(
        np.full((height, width, 3), color, dtype=np.uint8),
        mode="RGB",
    )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FakeCascade:
    def __init__(self, *, eyes: bool) -> None:
        self.eyes = eyes

    def detectMultiScale(self, image: object, **kwargs: object) -> np.ndarray:  # noqa: N802
        if self.eyes:
            return np.array([[30, 30, 24, 16], [82, 30, 24, 16]])
        return np.array([[70, 40, 180, 220]])


def test_invalid_upload_is_returned_as_a_readable_reupload_observation() -> None:
    result = photo_quality.analyze_photo_bytes(
        b"not-an-image",
        photo_id="photo_bad",
        photo_role=PhotoRole.REFERENCE,
    )

    assert result.quality_confidence == 0.0
    assert QualityFlag.PROVIDER_UNSUPPORTED_INPUT in result.quality_flags
    assert "image_decode_failed" in result.reason_codes


def test_real_decoder_and_metrics_run_without_persisting_image_bytes() -> None:
    result = photo_quality.analyze_photo_bytes(
        image_bytes(),
        photo_id="photo_no_face",
        photo_role=PhotoRole.REFERENCE,
    )

    assert result.photo_sha256
    assert result.width == 320
    assert result.height == 320
    assert result.face_count == 0
    assert QualityFlag.NO_FACE in result.quality_flags
    assert "photo_bytes" not in result.public_projection()
    user_projection = result.user_projection()
    assert "quality_confidence" not in user_projection
    assert "editability_confidence" not in user_projection
    assert user_projection["quality_status"] in {
        "可以进入下一步",
        "存在质量警告，确认后继续",
        "需要重新上传",
    }


def test_quality_gate_detects_face_and_eye_visibility(monkeypatch: object) -> None:
    def fake_cascade(filename: str) -> FakeCascade:
        return FakeCascade(eyes=filename == photo_quality.EYE_CASCADE)

    monkeypatch.setattr(photo_quality, "_new_face_cascade", fake_cascade)
    result = photo_quality.analyze_photo_bytes(
        image_bytes(),
        photo_id="photo_valid",
        photo_role=PhotoRole.REFERENCE,
    )

    assert result.face_count == 1
    assert result.selected_face_ref == "photo_valid_face_0"
    assert result.metrics["largest_face_eye_count"] == 2.0
    assert result.quality_confidence > 0.0
    assert result.editability_confidence > 0.0
    assert QualityFlag.NO_FACE not in result.quality_flags


def test_quality_contract_keeps_safety_gate_explicit(monkeypatch: object) -> None:
    def fake_cascade(filename: str) -> FakeCascade:
        return FakeCascade(eyes=filename == photo_quality.EYE_CASCADE)

    monkeypatch.setattr(photo_quality, "_new_face_cascade", fake_cascade)
    observation = photo_quality.analyze_photo_bytes(
        image_bytes(),
        photo_id="photo_reference",
        photo_role=PhotoRole.REFERENCE,
    )
    result = photo_quality.to_photo_quality_result(
        observation,
        session_id="session_001",
        quality_result_id="quality_001",
    )

    assert result.route == QualityRoute.SAFETY_CHECK_REQUIRED
    assert result.content_safety_status == ContentSafetyStatus.NOT_EVALUATED


def test_target_uncertain_subject_is_independent_from_quality(monkeypatch: object) -> None:
    def fake_cascade(filename: str) -> FakeCascade:
        return FakeCascade(eyes=filename == photo_quality.EYE_CASCADE)

    monkeypatch.setattr(photo_quality, "_new_face_cascade", fake_cascade)
    observation = photo_quality.analyze_photo_bytes(
        image_bytes(),
        photo_id="photo_target",
        photo_role=PhotoRole.TARGET,
    )
    result = photo_quality.to_photo_quality_result(
        observation,
        session_id="session_001",
        quality_result_id="quality_002",
        subject_match_status=SubjectMatchStatus.UNCERTAIN,
        subject_match_evidence={
            "provider": "fixture_subject_adapter",
            "operation": "compare_subject",
            "model_version": "fixture-v1",
            "threshold_policy_version": "subject-v0",
            "receipt_ref": "receipt_001",
            "raw_score": 0.5,
            "raw_score_min": 0.0,
            "raw_score_max": 1.0,
            "calibrated": False,
            "evaluated_at": "2026-08-27T00:00:00Z",
        },
        content_safety_status=ContentSafetyStatus.PASSED,
        content_safety_evidence=ContentSafetyEvidence(
            provider="fixture_safety_adapter",
            operation="classify_image_safety",
            provider_version="fixture-v1",
            policy_version="safety-v0",
            receipt_ref="safety_receipt_001",
            evaluated_at=datetime.now(timezone.utc),
        ),
    )

    assert result.route == QualityRoute.SUBJECT_CONFIRMATION_REQUIRED
    assert result.quality_confidence > 0.5
