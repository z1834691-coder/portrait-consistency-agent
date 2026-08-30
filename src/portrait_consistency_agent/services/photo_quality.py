"""Local, explainable photo-quality and editability gate.

This module deliberately does not decide whether two photos are the same person
and does not calculate a portrait-consistency score.  It answers a narrower
question: can the current image be analysed and edited reliably enough to move
to the next step?  Image bytes are processed in memory and are never written by
this module.

The V0 detector uses OpenCV's bundled frontal-face/eye cascades plus Pillow for
safe decoding and EXIF orientation.  The thresholds are a versioned engineering
policy, not a calibrated probability model; the resulting confidences are only
for quality/editability routing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from typing import Final

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from portrait_consistency_agent.core.contracts import (
    ContentSafetyEvidence,
    ContentSafetyStatus,
    IsolationStatus,
    PhotoQualityResult,
    PhotoRole,
    QualityFlag,
    QualityRoute,
    QualityRoutingPolicySnapshot,
    SubjectMatchEvidence,
    SubjectMatchStatus,
)
from portrait_consistency_agent.core.policies import build_v0_quality_routing_policy

ALLOWED_FORMATS: Final[frozenset[str]] = frozenset({"PNG", "JPEG", "JPG", "BMP"})
FACE_CASCADE: Final[str] = "haarcascade_frontalface_default.xml"
EYE_CASCADE: Final[str] = "haarcascade_eye_tree_eyeglasses.xml"


@dataclass(frozen=True)
class PhotoQualityPolicy:
    """Versioned, deliberately provisional detector settings.

    The product's 0.50/0.80 routing policy remains in
    :class:`QualityRoutingPolicySnapshot`.  These values only turn observable
    image measurements into quality/editability evidence and can be replaced by
    a benchmark-backed policy later without changing the six contracts.
    """

    policy_id: str = "photo_quality_heuristic_v0"
    policy_version: str = "2026-08-27"
    max_input_bytes: int = 5_242_880
    max_single_side_px: int = 4_000
    min_short_side_px: int = 64
    recommended_min_face_px: int = 34
    blur_variance_bad: float = 25.0
    blur_variance_good: float = 120.0
    exposure_low_luma: float = 25.0
    exposure_high_luma: float = 245.0
    exposure_fraction_warn: float = 0.35
    analysis_version: str = "opencv-haar-quality-v0"


@dataclass(frozen=True)
class FaceObservation:
    """An in-memory face box used during this call; never persisted to trace."""

    index: int
    x: int
    y: int
    width: int
    height: int
    eye_count: int
    eye_centers: tuple[tuple[float, float], ...] = ()
    # Normalized (x, y, width, height) boxes for the detected eyes.  These are
    # kept in memory only.  The eye-size features derived from them are useful
    # for a bounded V0 plan, but the raw boxes never enter a contract or trace.
    eye_boxes: tuple[tuple[float, float, float, float], ...] = ()

    @property
    def short_side(self) -> int:
        return min(self.width, self.height)

    @property
    def area_ratio(self) -> float:
        return float(self.width * self.height)


@dataclass(frozen=True)
class PhotoObservation:
    """Safe output of the local gate, before it is joined with subject/safety evidence."""

    photo_id: str
    photo_sha256: str
    photo_role: PhotoRole
    width: int | None
    height: int | None
    image_format: str | None
    face_count: int
    faces: tuple[FaceObservation, ...] = field(default_factory=tuple)
    selected_face_ref: str | None = None
    quality_confidence: float = 0.0
    editability_confidence: float = 0.0
    quality_flags: tuple[QualityFlag, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    metrics: dict[str, float] = field(default_factory=dict)
    analysis_version: str = "opencv-haar-quality-v0"
    provider_card_id: str = "tencent-beautify-pic-2019-12-13"
    provider_card_version: str = "reviewed_2026-08-27"

    @property
    def largest_face(self) -> FaceObservation | None:
        return max(self.faces, key=lambda face: face.area_ratio, default=None)

    def public_projection(self) -> dict[str, object]:
        """Return a UI/trace-safe projection without raw face coordinates."""

        return {
            "photo_id": self.photo_id,
            "photo_sha256": self.photo_sha256,
            "photo_role": self.photo_role.value,
            "width": self.width,
            "height": self.height,
            "image_format": self.image_format,
            "face_count": self.face_count,
            "selected_face_ref": self.selected_face_ref,
            "quality_confidence": round(self.quality_confidence, 4),
            "editability_confidence": round(self.editability_confidence, 4),
            "quality_flags": [flag.value for flag in self.quality_flags],
            "reason_codes": list(self.reason_codes),
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "analysis_version": self.analysis_version,
            "provider_card_id": self.provider_card_id,
            "provider_card_version": self.provider_card_version,
        }

    def user_projection(self) -> dict[str, object]:
        """Return a user-facing summary without internal confidence numbers.

        The contract keeps quality/editability confidences for routing and
        evaluation, but V0 must not present either value as an acceptance
        probability.  The page therefore receives only a qualitative next-step
        hint and concrete reasons the user can act on.
        """

        strictest = min(self.quality_confidence, self.editability_confidence)
        if self.face_count == 0 or any(
            flag in self.quality_flags
            for flag in (
                QualityFlag.PROVIDER_UNSUPPORTED_INPUT,
                QualityFlag.NO_FACE,
                QualityFlag.BLUR,
            )
        ):
            quality_status = "需要重新上传"
        elif self.face_count > 1:
            quality_status = "需要先选择或裁剪目标人脸"
        elif strictest <= 0.50:
            quality_status = "需要重新上传"
        elif strictest < 0.80:
            quality_status = "存在质量警告，确认后继续"
        else:
            quality_status = "可以进入下一步"
        return {
            "photo_role": self.photo_role.value,
            "image_format": self.image_format,
            "dimensions": (
                f"{self.width}×{self.height}"
                if self.width is not None and self.height is not None
                else None
            ),
            "face_count": self.face_count,
            "quality_status": quality_status,
            "quality_flags": [flag.value for flag in self.quality_flags],
            "reason_codes": list(self.reason_codes),
            "analysis_version": self.analysis_version,
        }


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _score_between(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clip((value - low) / (high - low))


def _new_face_cascade(filename: str) -> cv2.CascadeClassifier:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + filename)
    if cascade.empty():  # pragma: no cover - protects broken OpenCV installs
        raise RuntimeError(f"OpenCV cascade unavailable: {filename}")
    return cascade


def _empty_observation(
    *,
    photo_id: str,
    photo_sha256: str,
    photo_role: PhotoRole,
    flags: tuple[QualityFlag, ...],
    reason_codes: tuple[str, ...],
    policy: PhotoQualityPolicy,
    image_format: str | None = None,
) -> PhotoObservation:
    return PhotoObservation(
        photo_id=photo_id,
        photo_sha256=photo_sha256,
        photo_role=photo_role,
        width=None,
        height=None,
        image_format=image_format,
        face_count=0,
        quality_confidence=0.0,
        editability_confidence=0.0,
        quality_flags=flags,
        reason_codes=reason_codes,
        metrics={},
        analysis_version=policy.analysis_version,
    )


def analyze_photo_bytes(
    image_bytes: bytes,
    *,
    photo_id: str,
    photo_role: PhotoRole,
    policy: PhotoQualityPolicy | None = None,
) -> PhotoObservation:
    """Analyse one real image in memory and return quality/editability evidence.

    Decode and provider-preflight failures are returned as a low-confidence
    observation so the caller can show a readable re-upload reason instead of
    crashing the Streamlit session.  The function never writes the image to a
    file or includes pixel data in its return value.
    """

    policy = policy or PhotoQualityPolicy()
    photo_sha256 = hashlib.sha256(image_bytes).hexdigest()
    if not image_bytes:
        return _empty_observation(
            photo_id=photo_id,
            photo_sha256=photo_sha256,
            photo_role=photo_role,
            flags=(QualityFlag.PROVIDER_UNSUPPORTED_INPUT,),
            reason_codes=("empty_upload",),
            policy=policy,
        )
    if len(image_bytes) > policy.max_input_bytes:
        return _empty_observation(
            photo_id=photo_id,
            photo_sha256=photo_sha256,
            photo_role=photo_role,
            flags=(QualityFlag.PROVIDER_UNSUPPORTED_INPUT,),
            reason_codes=("input_bytes_exceed_provider_limit",),
            policy=policy,
        )

    try:
        with Image.open(BytesIO(image_bytes)) as opened:
            image_format = (opened.format or "").upper() or None
            if image_format not in ALLOWED_FORMATS:
                return _empty_observation(
                    photo_id=photo_id,
                    photo_sha256=photo_sha256,
                    photo_role=photo_role,
                    flags=(QualityFlag.PROVIDER_UNSUPPORTED_INPUT,),
                    reason_codes=("unsupported_image_format",),
                    policy=policy,
                    image_format=image_format,
                )
            image = ImageOps.exif_transpose(opened).convert("RGB")
            width, height = image.size
            has_alpha = "A" in opened.getbands()
            image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return _empty_observation(
            photo_id=photo_id,
            photo_sha256=photo_sha256,
            photo_role=photo_role,
            flags=(QualityFlag.PROVIDER_UNSUPPORTED_INPUT,),
            reason_codes=("image_decode_failed",),
            policy=policy,
        )

    flags: list[QualityFlag] = []
    reason_codes: list[str] = []
    if has_alpha:
        flags.append(QualityFlag.PROVIDER_UNSUPPORTED_INPUT)
        reason_codes.append("alpha_channel_not_supported_by_provider")
    if max(width, height) > policy.max_single_side_px:
        flags.append(QualityFlag.PROVIDER_UNSUPPORTED_INPUT)
        reason_codes.append("single_side_exceeds_provider_limit")
    if min(width, height) < policy.min_short_side_px:
        flags.append(QualityFlag.LOW_RESOLUTION)
        reason_codes.append("short_side_below_provider_minimum")

    rgb = np.asarray(image, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_luma = float(gray.mean())
    low_exposure_fraction = float((gray <= policy.exposure_low_luma).mean())
    high_exposure_fraction = float((gray >= policy.exposure_high_luma).mean())

    face_cascade = _new_face_cascade(FACE_CASCADE)
    eye_cascade = _new_face_cascade(EYE_CASCADE)
    detected = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(max(24, policy.recommended_min_face_px),) * 2,
    )
    faces: list[FaceObservation] = []
    image_area = float(width * height)
    for index, (x, y, face_width, face_height) in enumerate(detected):
        face_gray = gray[y : y + face_height, x : x + face_width]
        eyes = eye_cascade.detectMultiScale(
            face_gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(8, 8),
        )
        sorted_eyes = sorted(eyes, key=lambda item: (int(item[0]), int(item[1])))
        faces.append(
            FaceObservation(
                index=index,
                x=int(x),
                y=int(y),
                width=int(face_width),
                height=int(face_height),
                eye_count=min(4, len(sorted_eyes)),
                eye_centers=tuple(
                    (
                        float(eye_x + eye_width / 2) / float(face_width),
                        float(eye_y + eye_height / 2) / float(face_height),
                    )
                    for eye_x, eye_y, eye_width, eye_height in sorted_eyes[:4]
                ),
                eye_boxes=tuple(
                    (
                        float(eye_x) / float(face_width),
                        float(eye_y) / float(face_height),
                        float(eye_width) / float(face_width),
                        float(eye_height) / float(face_height),
                    )
                    for eye_x, eye_y, eye_width, eye_height in sorted_eyes[:4]
                ),
            )
        )
    faces.sort(key=lambda face: face.area_ratio, reverse=True)
    faces = [
        FaceObservation(
            index=index,
            x=face.x,
            y=face.y,
            width=face.width,
            height=face.height,
            eye_count=face.eye_count,
            eye_centers=face.eye_centers,
            eye_boxes=face.eye_boxes,
        )
        for index, face in enumerate(faces)
    ]

    face_count = len(faces)
    largest = faces[0] if faces else None
    if face_count == 0:
        flags.append(QualityFlag.NO_FACE)
        reason_codes.append("no_frontal_face_detected")
    elif face_count > 1:
        flags.append(QualityFlag.MULTIPLE_FACES)
        reason_codes.append("multiple_faces_require_target_selection")

    face_short_side = float(largest.short_side) if largest else 0.0
    face_area_ratio = (largest.area_ratio / image_area) if largest else 0.0
    eye_count = float(largest.eye_count) if largest else 0.0
    if largest and largest.short_side < policy.recommended_min_face_px:
        flags.append(QualityFlag.LOW_RESOLUTION)
        reason_codes.append("face_below_recommended_edit_size")
    if largest and largest.eye_count < 2:
        flags.append(QualityFlag.OCCLUSION)
        reason_codes.append("two_eyes_not_reliably_visible")
    if largest and (
        largest.x <= 0
        or largest.y <= 0
        or largest.x + largest.width >= width
        or largest.y + largest.height >= height
    ):
        flags.append(QualityFlag.FACE_INCOMPLETE)
        reason_codes.append("face_touches_image_boundary")
    if sharpness < policy.blur_variance_bad:
        flags.append(QualityFlag.BLUR)
        reason_codes.append("low_laplacian_sharpness")
    if low_exposure_fraction >= policy.exposure_fraction_warn:
        flags.append(QualityFlag.LOW_EXPOSURE)
        reason_codes.append("large_dark_region")
    if high_exposure_fraction >= policy.exposure_fraction_warn:
        flags.append(QualityFlag.OVER_EXPOSURE)
        reason_codes.append("large_clipped_highlight_region")

    sharpness_score = _score_between(
        sharpness,
        policy.blur_variance_bad,
        policy.blur_variance_good,
    )
    exposure_score = _clip(
        1.0
        - max(low_exposure_fraction, high_exposure_fraction)
        / max(policy.exposure_fraction_warn, 0.01)
    )
    size_score = _score_between(
        face_short_side,
        float(policy.recommended_min_face_px),
        float(max(policy.recommended_min_face_px * 4, 160)),
    )
    visibility_score = _clip(eye_count / 2.0)
    face_presence_score = 1.0 if largest else 0.0
    quality_confidence = _clip(
        0.35 * sharpness_score
        + 0.25 * exposure_score
        + 0.25 * size_score
        + 0.15 * face_presence_score
    )
    editability_confidence = _clip(
        0.35 * quality_confidence + 0.35 * size_score + 0.30 * visibility_score
    )
    if has_alpha or max(width, height) > policy.max_single_side_px:
        quality_confidence = 0.0
        editability_confidence = 0.0

    metrics = {
        "sharpness_laplacian_variance": sharpness,
        "mean_luma": mean_luma,
        "low_exposure_fraction": low_exposure_fraction,
        "high_exposure_fraction": high_exposure_fraction,
        "largest_face_short_side_px": face_short_side,
        "largest_face_area_ratio": face_area_ratio,
        "largest_face_eye_count": eye_count,
    }
    selected_face_ref = f"{photo_id}_face_0" if face_count == 1 else None
    return PhotoObservation(
        photo_id=photo_id,
        photo_sha256=photo_sha256,
        photo_role=photo_role,
        width=width,
        height=height,
        image_format=image_format,
        face_count=face_count,
        faces=tuple(faces),
        selected_face_ref=selected_face_ref,
        quality_confidence=quality_confidence,
        editability_confidence=editability_confidence,
        quality_flags=tuple(dict.fromkeys(flags)),
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        metrics=metrics,
        analysis_version=policy.analysis_version,
    )


def to_photo_quality_result(
    observation: PhotoObservation,
    *,
    session_id: str,
    quality_result_id: str,
    subject_match_status: SubjectMatchStatus | None = None,
    subject_match_confidence: float | None = None,
    subject_match_evidence: SubjectMatchEvidence | None = None,
    content_safety_status: ContentSafetyStatus = ContentSafetyStatus.NOT_EVALUATED,
    content_safety_evidence: ContentSafetyEvidence | None = None,
    isolation_status: IsolationStatus = IsolationStatus.NOT_REQUIRED,
    selected_face_ref: str | None = None,
    routing_policy: QualityRoutingPolicySnapshot | None = None,
) -> PhotoQualityResult:
    """Join local quality evidence with separately produced gates.

    A target/result photo must provide an independent subject-match evidence
    object before this function can create the six-contract ``PhotoQualityResult``.
    Content safety is intentionally explicit; if it has not run, the contract
    routes to ``safety_check_required`` rather than silently continuing.
    """

    routing_policy = routing_policy or build_v0_quality_routing_policy()
    if subject_match_status is None:
        subject_match_status = SubjectMatchStatus.NOT_APPLICABLE
    if selected_face_ref is None:
        selected_face_ref = observation.selected_face_ref

    if content_safety_status == ContentSafetyStatus.BLOCKED:
        route = QualityRoute.REJECT_REUPLOAD
        route_reason = "content_safety_blocked"
    elif content_safety_status == ContentSafetyStatus.NOT_EVALUATED:
        route = QualityRoute.SAFETY_CHECK_REQUIRED
        route_reason = "safety_not_evaluated"
    elif observation.face_count == 0:
        route = QualityRoute.REJECT_REUPLOAD
        route_reason = "no_face"
    elif observation.face_count > 1 and selected_face_ref is None:
        route = QualityRoute.SELECT_FACE
        route_reason = "target_face_selection_required"
    elif observation.face_count > 1 and isolation_status == IsolationStatus.FAILED:
        route = QualityRoute.REQUIRE_USER_CROP
        route_reason = "automatic_face_isolation_failed"
    elif observation.face_count > 1 and isolation_status != IsolationStatus.SUCCEEDED:
        route = QualityRoute.ISOLATION_PENDING
        route_reason = "face_isolation_pending"
    elif (
        observation.photo_role != PhotoRole.REFERENCE
        and subject_match_status == SubjectMatchStatus.NO_MATCH
    ):
        route = QualityRoute.REJECT_REUPLOAD
        route_reason = "subject_no_match"
    elif (
        observation.photo_role != PhotoRole.REFERENCE
        and subject_match_status == SubjectMatchStatus.UNCERTAIN
    ):
        route = QualityRoute.SUBJECT_CONFIRMATION_REQUIRED
        route_reason = "subject_match_uncertain"
    else:
        strictest = min(observation.quality_confidence, observation.editability_confidence)
        if strictest <= routing_policy.reject_at_or_below:
            route = QualityRoute.REJECT_REUPLOAD
            route_reason = "quality_or_editability_low"
        elif strictest < routing_policy.continue_at_or_above:
            route = QualityRoute.WARN_CONTINUE
            route_reason = "quality_or_editability_medium"
        else:
            route = QualityRoute.CONTINUE
            route_reason = "quality_and_editability_sufficient"

    reason_codes = list(observation.reason_codes)
    if route_reason not in reason_codes:
        reason_codes.append(route_reason)
    return PhotoQualityResult(
        quality_result_id=quality_result_id,
        session_id=session_id,
        photo_id=observation.photo_id,
        photo_sha256=observation.photo_sha256,
        photo_role=observation.photo_role,
        face_count=observation.face_count,
        selected_face_ref=selected_face_ref,
        isolation_status=isolation_status,
        subject_match_status=subject_match_status,
        subject_match_confidence=subject_match_confidence,
        subject_match_evidence=subject_match_evidence,
        quality_confidence=observation.quality_confidence,
        editability_confidence=observation.editability_confidence,
        content_safety_status=content_safety_status,
        content_safety_evidence=content_safety_evidence,
        quality_flags=list(observation.quality_flags),
        reason_codes=reason_codes,
        metrics=observation.metrics,
        route=route,
        routing_policy=routing_policy,
        analysis_version=observation.analysis_version,
        provider_card_id=observation.provider_card_id,
        provider_card_version=observation.provider_card_version,
    )
