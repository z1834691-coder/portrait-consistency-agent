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
