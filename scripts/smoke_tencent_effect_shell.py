"""Offline smoke for the Tencent Effect SDK candidate adapter shell.

This script must remain network-free.  It demonstrates the candidate card,
typed request envelope, fail-closed gate and redacted trace; it never reads a
photo, imports a vendor SDK or uses credentials.
"""

from __future__ import annotations

import json

from portrait_consistency_agent.services.tencent_effect import (
    EffectPlatform,
    TencentEffectAdapter,
)


def main() -> None:
    adapter = TencentEffectAdapter()
    request = adapter.prepare_request(
        request_ref="effect_smoke_001",
        input_artifact_ref="photo_artifact_001",
        platform=EffectPlatform.WEB,
        parameters={"lips_thickness": 8, "face_shape": 12},
        batch_size=2,
    )
    result = adapter.dry_run(request)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
