"""Create the redacted real-sample manifest used by Tencent Effect Web E3.

Example::

    python scripts/run_effect_web_e3_preflight.py \
      --reference /path/to/reference.jpg \
      --target /path/to/target-a.jpg \
      --target /path/to/target-b.jpg

The command never calls Tencent and never writes input or result image bytes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from portrait_consistency_agent.services.tencent_effect_web_e3 import (  # noqa: E402
    E3SampleSpec,
    preflight_e3_samples,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a redacted Tencent Effect Web E3 preflight")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--target", action="append", required=True, type=Path)
    parser.add_argument(
        "--negative",
        action="append",
        default=[],
        type=Path,
        help="Optional deliberately invalid input placed before valid targets to test isolation",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_preflight_v1.json",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_preflight_v1.html",
    )
    parser.add_argument("--reference-angle", default="front")
    parser.add_argument("--reference-lighting", default="unknown")
    parser.add_argument("--reference-expression", default="neutral")
    parser.add_argument(
        "--target-meta",
        action="append",
        default=[],
        metavar="INDEX:ANGLE:LIGHTING:EXPRESSION",
        help="Optional owner labels for a target, e.g. 1:three_quarter:indoor:smile",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    specs = [
        E3SampleSpec(
            sample_id="e3_reference_001",
            path=args.reference,
            role="reference_candidate",
            angle=args.reference_angle,
            lighting=args.reference_lighting,
            expression=args.reference_expression,
        )
    ]
    target_metadata: dict[int, tuple[str, str, str]] = {}
    for raw in args.target_meta:
        parts = raw.split(":", 3)
        if len(parts) != 4 or not parts[0].isdigit():
            raise SystemExit("--target-meta must use INDEX:ANGLE:LIGHTING:EXPRESSION")
        target_metadata[int(parts[0])] = (parts[1], parts[2], parts[3])
    for index, path in enumerate(args.negative, start=1):
        specs.append(
            E3SampleSpec(
                sample_id=f"e3_negative_{index:03d}",
                path=path,
                role="target",
                angle="not_applicable",
                lighting="not_applicable",
                expression="not_applicable",
            )
        )
    for index, path in enumerate(args.target, start=1):
        angle, lighting, expression = target_metadata.get(index, ("unknown", "unknown", "unknown"))
        specs.append(
            E3SampleSpec(
                sample_id=f"e3_target_{index:03d}",
                path=path,
                role="target",
                angle=angle,
                lighting=lighting,
                expression=expression,
            )
        )
    report = preflight_e3_samples(specs)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report.projection(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_html.write_text(report.to_html(), encoding="utf-8")
    print(json.dumps(report.projection(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ready_for_candidate_trials else 2


if __name__ == "__main__":
    raise SystemExit(main())
