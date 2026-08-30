from datetime import datetime, timedelta, timezone

import pytest

from portrait_consistency_agent.core.contracts import (
    ContentSafetyEvidence,
    ContentSafetyStatus,
    EditableFeature,
    MeasurementUnit,
    PhotoRole,
    ProfileStatus,
    QualityRoute,
    SubjectAnchorMetadata,
)
from portrait_consistency_agent.core.policies import build_v0_data_retention_policy
from portrait_consistency_agent.services.photo_quality import (
    FaceObservation,
    PhotoObservation,
    to_photo_quality_result,
)
from portrait_consistency_agent.services.reference_profile import (
    ReferenceProfileBuildError,
    build_reference_profile,
    extract_normalized_features,
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def make_observation(**overrides: object) -> PhotoObservation:
    values: dict[str, object] = {
        "photo_id": "photo_reference",
        "photo_sha256": SHA,
        "photo_role": PhotoRole.REFERENCE,
        "width": 1000,
        "height": 1200,
        "image_format": "JPEG",
        "face_count": 1,
        "faces": (
            FaceObservation(
                index=0,
                x=250,
                y=180,
                width=500,
                height=620,
                eye_count=2,
                eye_centers=((0.35, 0.42), (0.65, 0.43)),
                eye_boxes=((0.28, 0.36, 0.12, 0.07), (0.60, 0.37, 0.12, 0.07)),
            ),
        ),
        "selected_face_ref": "photo_reference_face_0",
        "quality_confidence": 0.94,
        "editability_confidence": 0.92,
        "metrics": {"sharpness_laplacian_variance": 200.0},
        "analysis_version": "opencv-haar-quality-v0",
    }
    values.update(overrides)
    return PhotoObservation(**values)


def make_reference_quality(observation: PhotoObservation, **overrides: object):
    values: dict[str, object] = {
        "session_id": "session_001",
        "quality_result_id": "quality_reference",
        "content_safety_status": ContentSafetyStatus.PASSED,
        "content_safety_evidence": ContentSafetyEvidence(
            provider="fixture_safety_adapter",
            operation="classify_image_safety",
            provider_version="fixture-v1",
            policy_version="safety-v0",
            receipt_ref="safety_receipt_001",
            evaluated_at=NOW,
        ),
    }
    values.update(overrides)
    return to_photo_quality_result(observation, **values)


def test_profile_extracts_normalized_face_and_eye_geometry_only() -> None:
    features = extract_normalized_features(make_observation())
    by_code = {feature.feature_code: feature for feature in features}

    assert by_code["face_width_height_ratio"].value == pytest.approx(500 / 620)
    assert by_code["eye_distance_face_ratio"].unit == MeasurementUnit.NORMALIZED_RATIO
    assert by_code["eye_distance_face_ratio"].value == pytest.approx(0.30)
    assert by_code["eye_area_mean_face_ratio"].value == pytest.approx(0.12 * 0.07)
    assert all(feature.value is not None for feature in features)


def test_profile_marks_eye_size_unavailable_without_exactly_two_eye_boxes() -> None:
    observation = make_observation(
        faces=(
            FaceObservation(
                index=0,
                x=250,
                y=180,
                width=500,
                height=620,
                eye_count=1,
                eye_centers=((0.35, 0.42),),
                eye_boxes=((0.28, 0.36, 0.12, 0.07),),
            ),
        ),
    )
    by_code = {
        feature.feature_code: feature for feature in extract_normalized_features(observation)
    }

    assert by_code["eye_area_mean_face_ratio"].status.value == "unavailable"
    assert by_code["eye_area_mean_face_ratio"].value is None


def test_profile_without_anchor_is_geometry_only_and_has_provider_mappings() -> None:
    observation = make_observation()
    quality = make_reference_quality(observation)
    profile = build_reference_profile(
        observation,
        quality,
        user_id="user_001",
        profile_id="profile_001",
        version=1,
        feature_snapshot_ref="snapshot_001",
    )

    assert profile.status == ProfileStatus.GEOMETRY_ONLY
    assert profile.subject_anchor is None
    assert {mapping.feature for mapping in profile.provider_mappings} == {
        EditableFeature.FACE_LIFTING,
        EditableFeature.EYE_ENLARGING,
        EditableFeature.WHITENING,
        EditableFeature.SMOOTHING,
    }
    assert not any(
        feature.feature_code in {"skin_tone", "makeup"} for feature in profile.normalized_features
    )


def test_profile_with_separate_anchor_consent_is_active_for_six_months() -> None:
    observation = make_observation()
    quality = make_reference_quality(observation)
    anchor = SubjectAnchorMetadata(
        anchor_ref="anchor_001",
        consent_record_ref="consent_001",
        status="active",
        created_at=NOW,
        expires_at=NOW + timedelta(days=183),
        retention_policy=build_v0_data_retention_policy(),
        access_policy_version="restricted-v1",
    )
    profile = build_reference_profile(
        observation,
        quality,
        user_id="user_001",
        profile_id="profile_001",
        version=1,
        feature_snapshot_ref="snapshot_001",
        subject_anchor=anchor,
    )

    assert profile.status == ProfileStatus.ACTIVE
    assert profile.subject_anchor is not None
    assert profile.subject_anchor.expires_at == NOW + timedelta(days=183)


def test_profile_rejects_non_continuable_or_multi_face_reference() -> None:
    observation = make_observation()
    quality = make_reference_quality(
        observation,
        content_safety_status=ContentSafetyStatus.NOT_EVALUATED,
        content_safety_evidence=None,
    )
    # The contract intentionally routes an unevaluated safety result away from
    # locking; the builder must not silently turn it into a profile.
    assert quality.route == QualityRoute.SAFETY_CHECK_REQUIRED
    with pytest.raises(ReferenceProfileBuildError, match="must pass"):
        build_reference_profile(
            observation,
            quality,
            user_id="user_001",
            profile_id="profile_001",
            version=1,
            feature_snapshot_ref="snapshot_001",
        )

    multi = make_observation(
        face_count=2,
        faces=make_observation().faces
        + (
            FaceObservation(
                index=1,
                x=50,
                y=100,
                width=100,
                height=120,
                eye_count=2,
                eye_centers=((0.35, 0.42), (0.65, 0.43)),
                eye_boxes=((0.28, 0.36, 0.12, 0.07), (0.60, 0.37, 0.12, 0.07)),
            ),
        ),
        selected_face_ref=None,
    )
    with pytest.raises(ReferenceProfileBuildError, match="exactly one"):
        extract_normalized_features(multi)
