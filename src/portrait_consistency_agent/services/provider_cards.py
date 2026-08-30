"""Versioned capability-card retrieval for the V0 provider knowledge baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TENCENT_BEAUTIFY_CARD_PATH = PROJECT_ROOT / "data/provider_cards/tencent_beautify_pic.json"
TENCENT_COMPARE_FACE_CARD_PATH = PROJECT_ROOT / "data/provider_cards/tencent_compare_face.json"
TENCENT_IMAGE_MODERATION_CARD_PATH = (
    PROJECT_ROOT / "data/provider_cards/tencent_image_moderation.json"
)
TENCENT_EFFECT_CARD_PATH = PROJECT_ROOT / "data/provider_cards/tencent_effect_sdk.json"
VOLC_BEAUTY_CARD_PATH = PROJECT_ROOT / "data/provider_cards/volcengine_beauty_api_v2.json"


class ProviderCardError(RuntimeError):
    """Raised when the reviewed provider capability card is missing or invalid."""


def _load_json_card(path: Path, provider_label: str) -> dict[str, Any]:
    """Load one JSON capability card without treating it as execution permission."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderCardError(f"{provider_label} provider card is missing") from exc
    except json.JSONDecodeError as exc:
        raise ProviderCardError(f"{provider_label} provider card is invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProviderCardError(f"{provider_label} provider card must be a JSON object")
    return data


def load_tencent_beautify_card() -> dict[str, Any]:
    """Load the reviewed Tencent BeautifyPic card without invoking any network API."""

    data = _load_json_card(TENCENT_BEAUTIFY_CARD_PATH, "Tencent BeautifyPic")

    required_fields = {
        "card_id",
        "provider",
        "operation",
        "api_version",
        "card_version",
        "endpoint",
        "parameters",
        "input",
        "output",
        "source",
        "review_status",
    }
    missing = sorted(required_fields - set(data))
    if missing:
        raise ProviderCardError(f"Tencent BeautifyPic provider card missing: {', '.join(missing)}")
    if data["review_status"] != "verified":
        raise ProviderCardError("Tencent BeautifyPic provider card is not reviewed")
    return data


def load_tencent_compare_face_card() -> dict[str, Any]:
    """Load the reviewed current-session subject-match capability card."""

    data = _load_json_card(TENCENT_COMPARE_FACE_CARD_PATH, "Tencent CompareFace")

    required_fields = {
        "card_id",
        "provider",
        "operation",
        "api_version",
        "card_version",
        "endpoint",
        "input",
        "output",
        "routing_policy",
        "source",
        "review_status",
    }
    missing = sorted(required_fields - set(data))
    if missing:
        raise ProviderCardError(f"Tencent CompareFace provider card missing: {', '.join(missing)}")
    if data["review_status"] != "verified":
        raise ProviderCardError("Tencent CompareFace provider card is not reviewed")
    return data


def load_tencent_image_moderation_card() -> dict[str, Any]:
    """Load the reviewed ImageModeration safety capability card."""

    data = _load_json_card(TENCENT_IMAGE_MODERATION_CARD_PATH, "Tencent ImageModeration")

    required_fields = {
        "card_id",
        "provider",
        "operation",
        "api_version",
        "card_version",
        "endpoint",
        "input",
        "output",
        "v0_policy",
        "source",
        "review_status",
    }
    missing = sorted(required_fields - set(data))
    if missing:
        raise ProviderCardError(
            f"Tencent ImageModeration provider card missing: {', '.join(missing)}"
        )
    if data["review_status"] != "verified":
        raise ProviderCardError("Tencent ImageModeration provider card is not reviewed")
    return data


def load_tencent_effect_card() -> dict[str, Any]:
    """Load the *candidate* Tencent Effect SDK card without touching a network.

    Unlike the three active V0 cards, this card is intentionally not required
    to be ``verified``.  The loader accepts only ``candidate`` so a future
    implementation cannot accidentally treat a modified JSON file as a live
    provider.  The adapter shell performs a second, typed readiness check.
    """

    data = _load_json_card(TENCENT_EFFECT_CARD_PATH, "Tencent Effect SDK candidate")

    required_fields = {
        "card_id",
        "provider",
        "operation",
        "api_version",
        "card_version",
        "review_status",
        "platforms",
        "parameters",
        "license",
        "permission_budget_gate",
        "data_boundary",
        "batch",
        "evidence_review",
        "source",
    }
    missing = sorted(required_fields - set(data))
    if missing:
        raise ProviderCardError(f"Tencent Effect SDK candidate card missing: {', '.join(missing)}")
    if data["review_status"] != "candidate":
        raise ProviderCardError(
            "Tencent Effect SDK card must remain candidate until License, static-image, "
            "permission, budget, smoke, and Gold gates are complete"
        )
    if not isinstance(data["parameters"], list) or not data["parameters"]:
        raise ProviderCardError("Tencent Effect SDK candidate card must list parameters")
    return data


def load_volc_beauty_card() -> dict[str, Any]:
    """Load the candidate Volcengine card without promoting it to executable."""

    data = _load_json_card(VOLC_BEAUTY_CARD_PATH, "Volcengine Beauty API V2")
    required_fields = {
        "card_id",
        "provider",
        "operation",
        "api_version",
        "card_version",
        "endpoint",
        "parameters",
        "input",
        "output",
        "auth",
        "privacy",
        "cost",
        "latency",
        "batch",
        "admission",
        "source",
        "review_status",
    }
    missing = sorted(required_fields - set(data))
    if missing:
        raise ProviderCardError(
            f"Volcengine Beauty API V2 provider card missing: {', '.join(missing)}"
        )
    if data["review_status"] != "candidate":
        raise ProviderCardError(
            "Volcengine Beauty API V2 card must remain candidate until its admission gate passes"
        )
    admission = data["admission"]
    if not isinstance(admission, dict) or admission.get("ready_for_execution") is not False:
        raise ProviderCardError(
            "Volcengine Beauty API V2 candidate card must explicitly disable execution"
        )
    return data
