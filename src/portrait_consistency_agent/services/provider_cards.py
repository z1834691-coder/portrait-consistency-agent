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


class ProviderCardError(RuntimeError):
    """Raised when the reviewed provider capability card is missing or invalid."""


def load_tencent_beautify_card() -> dict[str, Any]:
    """Load the reviewed Tencent BeautifyPic card without invoking any network API."""

    try:
        data = json.loads(TENCENT_BEAUTIFY_CARD_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderCardError("Tencent BeautifyPic provider card is missing") from exc
    except json.JSONDecodeError as exc:
        raise ProviderCardError("Tencent BeautifyPic provider card is invalid JSON") from exc

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

    try:
        data = json.loads(TENCENT_COMPARE_FACE_CARD_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderCardError("Tencent CompareFace provider card is missing") from exc
    except json.JSONDecodeError as exc:
        raise ProviderCardError("Tencent CompareFace provider card is invalid JSON") from exc

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

    try:
        data = json.loads(TENCENT_IMAGE_MODERATION_CARD_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderCardError("Tencent ImageModeration provider card is missing") from exc
    except json.JSONDecodeError as exc:
        raise ProviderCardError("Tencent ImageModeration provider card is invalid JSON") from exc

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
