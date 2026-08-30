"""Reference Profile v0 builder from a validated reference photo.

The builder converts the local quality gate's in-memory face observation into a
small, interpretable set of normalized geometry measurements.  It deliberately
does not save the source image, EXIF, skin tone, makeup, body attributes, raw
landmark arrays, or a plaintext embedding.  A future landmark model can replace
the extractor while keeping the ``ReferenceProfile`` contract stable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    CapabilityMode,
    EditableFeature,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    PhotoQualityResult,
    PhotoRole,
    PreserveAttribute,
    ProfileStatus,
    ProviderFeatureMapping,
    QualityRoute,
    ReferenceProfile,
    SubjectAnchorMetadata,
)
from portrait_consistency_agent.services.photo_quality import PhotoObservation


class ReferenceProfileBuildError(ValueError):
    """Raised when a reference photo is not safe to lock as a profile."""


CURRENT_PROVIDER_CARD_ID = "tencent-beautify-pic-2019-12-13"
CURRENT_PROVIDER_CARD_VERSION = "reviewed_2026-08-27"
CURRENT_PROVIDER_API_VERSION = "2019-12-13"


def _measured(
    feature_code: str,
    value: float,
    unit: MeasurementUnit,
    confidence: float,
) -> NormalizedFeature:
    return NormalizedFeature(
        feature_code=feature_code,
        value=float(value),
        unit=unit,
        status=MeasurementStatus.MEASURED,
        confidence=max(0.0, min(1.0, float(confidence))),
    )


def _provider_mappings() -> list[ProviderFeatureMapping]:
    return [
        ProviderFeatureMapping(
            feature=feature,
            capability_mode=CapabilityMode.EXECUTABLE,
            provider_card_id=CURRENT_PROVIDER_CARD_ID,
            provider_card_version=CURRENT_PROVIDER_CARD_VERSION,
            provider_parameter=parameter,
        )
        for feature, parameter in (
            (EditableFeature.FACE_LIFTING, "FaceLifting"),
            (EditableFeature.EYE_ENLARGING, "EyeEnlarging"),
            (EditableFeature.WHITENING, "Whitening"),
            (EditableFeature.SMOOTHING, "Smoothing"),
        )
    ]


def extract_normalized_features(
    observation: PhotoObservation,
) -> list[NormalizedFeature]:
    """Extract V0 face-box/eye geometry without retaining raw coordinates.

    Eye area is intentionally measured only when the detector returns exactly
    two eye boxes.  Eye-centre distance is not treated as eye size: if the
    stricter measurement is unavailable, the profile carries an explicit
    unavailable field so the planner can explain why it did not propose an
    ``EyeEnlarging`` value.
    """

    if observation.face_count != 1 or observation.largest_face is None:
        raise ReferenceProfileBuildError(
            "Reference Profile v0 requires exactly one detectable face."
        )
    if observation.width is None or observation.height is None:
        raise ReferenceProfileBuildError("Reference image dimensions are unavailable.")

    face = observation.largest_face
    width = float(observation.width)
    height = float(observation.height)
    face_confidence = min(observation.quality_confidence, observation.editability_confidence)
    face_width_ratio = face.width / width
    face_height_ratio = face.height / height
    center_x = (face.x + face.width / 2.0) / width
    center_y = (face.y + face.height / 2.0) / height
    margins = {
        "face_margin_left_ratio": face.x / width,
        "face_margin_right_ratio": (observation.width - face.x - face.width) / width,
        "face_margin_top_ratio": face.y / height,
        "face_margin_bottom_ratio": (observation.height - face.y - face.height) / height,
    }
    features = [
        _measured(
            "face_width_height_ratio",
            face.width / float(face.height),
            MeasurementUnit.NORMALIZED_RATIO,
            face_confidence,
        ),
        _measured(
            "face_width_image_ratio",
            face_width_ratio,
            MeasurementUnit.NORMALIZED_RATIO,
            face_confidence,
        ),
        _measured(
            "face_height_image_ratio",
            face_height_ratio,
            MeasurementUnit.NORMALIZED_RATIO,
            face_confidence,
        ),
        _measured(
            "face_area_image_ratio",
            face.area_ratio / (width * height),
            MeasurementUnit.NORMALIZED_RATIO,
            face_confidence,
        ),
        _measured("face_center_x", center_x, MeasurementUnit.NORMALIZED_POSITION, face_confidence),
        _measured("face_center_y", center_y, MeasurementUnit.NORMALIZED_POSITION, face_confidence),
    ]
    features.extend(
        _measured(code, value, MeasurementUnit.NORMALIZED_POSITION, face_confidence)
        for code, value in margins.items()
    )

    eye_centers = sorted(face.eye_centers, key=lambda point: point[0])
    if len(eye_centers) >= 2:
        left_eye, right_eye = eye_centers[0], eye_centers[-1]
        eye_distance = right_eye[0] - left_eye[0]
        eye_line_slope = (right_eye[1] - left_eye[1]) / max(eye_distance, 1e-6)
        features.extend(
            [
                _measured(
                    "eye_distance_face_ratio",
                    eye_distance,
                    MeasurementUnit.NORMALIZED_RATIO,
                    face_confidence,
                ),
                _measured(
                    "left_eye_center_x",
                    left_eye[0],
                    MeasurementUnit.NORMALIZED_POSITION,
                    face_confidence,
                ),
                _measured(
                    "right_eye_center_x",
                    right_eye[0],
                    MeasurementUnit.NORMALIZED_POSITION,
                    face_confidence,
                ),
                _measured(
                    "eye_center_y_mean",
                    (left_eye[1] + right_eye[1]) / 2.0,
                    MeasurementUnit.NORMALIZED_POSITION,
                    face_confidence,
                ),
                _measured(
                    "eye_line_slope",
                    eye_line_slope,
                    MeasurementUnit.NORMALIZED_RATIO,
                    face_confidence,
                ),
            ]
        )

    eye_size_fields = (
        ("eye_width_mean_face_ratio", MeasurementUnit.NORMALIZED_RATIO),
        ("eye_height_mean_face_ratio", MeasurementUnit.NORMALIZED_RATIO),
        ("eye_area_mean_face_ratio", MeasurementUnit.NORMALIZED_RATIO),
    )
    if len(face.eye_boxes) == 2:
        mean_width = sum(box[2] for box in face.eye_boxes) / 2.0
        mean_height = sum(box[3] for box in face.eye_boxes) / 2.0
        mean_area = sum(box[2] * box[3] for box in face.eye_boxes) / 2.0
        measured_values = (mean_width, mean_height, mean_area)
        features.extend(
            _measured(code, value, unit, face_confidence)
            for (code, unit), value in zip(eye_size_fields, measured_values, strict=True)
        )
    else:
        features.extend(
            NormalizedFeature(
                feature_code=code,
                unit=unit,
                status=MeasurementStatus.UNAVAILABLE,
                value=None,
                confidence=None,
            )
            for code, unit in eye_size_fields
        )
    return features


def build_reference_profile(
    observation: PhotoObservation,
    quality_result: PhotoQualityResult,
    *,
    user_id: str,
    profile_id: str,
    version: int,
    feature_snapshot_ref: str,
    subject_anchor: SubjectAnchorMetadata | None = None,
    allow_quality_warning: bool = False,
    allowed_features: list[EditableFeature] | None = None,
    blocked_features: list[EditableFeature] | None = None,
) -> ReferenceProfile:
    """Create a geometry-only or separately-consented anchored Profile v0."""

    if quality_result.photo_role != PhotoRole.REFERENCE:
        raise ReferenceProfileBuildError("Profile input must use photo_role=reference.")
    if quality_result.route not in {QualityRoute.CONTINUE, QualityRoute.WARN_CONTINUE}:
        raise ReferenceProfileBuildError(
            "Reference photo must pass safety, quality and editability gates before locking."
        )
    if quality_result.route == QualityRoute.WARN_CONTINUE and not allow_quality_warning:
        raise ReferenceProfileBuildError(
            "Reference photo has a quality warning; explicit user acknowledgement is required."
        )
    if quality_result.photo_id != observation.photo_id:
        raise ReferenceProfileBuildError(
            "Quality result and observation refer to different photos."
        )
    if quality_result.photo_sha256 != observation.photo_sha256:
        raise ReferenceProfileBuildError("Quality result hash does not match the uploaded photo.")
    normalized_features = extract_normalized_features(observation)
    now = datetime.now(timezone.utc)
    status = ProfileStatus.ACTIVE if subject_anchor is not None else ProfileStatus.GEOMETRY_ONLY
    return ReferenceProfile(
        profile_id=profile_id,
        user_id=user_id,
        version=version,
        status=status,
        feature_snapshot_ref=feature_snapshot_ref,
        normalized_features=normalized_features,
        reference_quality_result_id=quality_result.quality_result_id,
        allowed_features=(
            allowed_features
            if allowed_features is not None
            else [
                EditableFeature.FACE_LIFTING,
                EditableFeature.EYE_ENLARGING,
                EditableFeature.WHITENING,
                EditableFeature.SMOOTHING,
            ]
        ),
        blocked_features=blocked_features if blocked_features is not None else [],
        preserve_attributes=[
            PreserveAttribute.SKIN_TONE,
            PreserveAttribute.MAKEUP,
            PreserveAttribute.EXPRESSION,
            PreserveAttribute.BACKGROUND,
            PreserveAttribute.HAIR,
            PreserveAttribute.BODY,
        ],
        adjustment_mode=AdjustmentMode.BALANCED,
        provider_mappings=_provider_mappings(),
        subject_anchor=subject_anchor,
        profile_schema_version="profile-v0.3",
        extractor_version="opencv-haar-geometry-v0",
        canonicalization_version="canonical-v0",
        consent_policy_version="consent-v0",
        created_at=now,
        updated_at=now,
    )
