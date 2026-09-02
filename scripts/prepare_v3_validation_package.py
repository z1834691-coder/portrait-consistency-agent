#!/usr/bin/env python3
"""Derive a product-owner-unlocked V3 validation package.

The original V3 files remain outside the project as the historical Holdout-A
record.  After an explicit product decision to use V3 for diagnosis, this
script creates a clearly reclassified, reproducible validation copy in the
workspace.  It never changes the original owner-only files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_OWNER_DIR = Path(
    "/Users/fengzihan/Documents/Codex/"
    "portrait-consistency-agent-v3-holdout-final-owner-only-2026-09-01"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_OUT = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
DEFAULT_ANNOTATIONS_OUT = PROJECT_ROOT / "data/evaluation/rag_v3_validation_annotations_v1.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-dir", type=Path, default=DEFAULT_OWNER_DIR)
    parser.add_argument("--cases-out", type=Path, default=DEFAULT_CASES_OUT)
    parser.add_argument("--annotations-out", type=Path, default=DEFAULT_ANNOTATIONS_OUT)
    return parser


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    source_cases = _read(args.owner_dir / "v3_holdout_reviewed_runtime_owner_only.json")
    source_annotations = _read(args.owner_dir / "v3_holdout_reviewed_answer_key_owner_only.json")
    version = "rag-v3-validation-unlocked-2026-09-02"
    cases = {
        "dataset_version": version,
        "status": "owner_unlocked_validation",
        "source_status": "historical_v3_holdout_reclassified_by_product_owner",
        "source_holdout_run_preserved": True,
        "cases": [
            {
                "case_id": row["case_id"],
                "split": "validation",
                "query": row["query"],
                "tags": [],
            }
            for row in source_cases["cases"]
        ],
    }
    annotations = {
        "dataset_version": version,
        "status": "owner_unlocked_validation_annotations",
        "answer_key_is_private": False,
        "source_status": "derived_from_owner_reviewed_v3_key_after_explicit_unlock",
        "canonical_safety_event_catalog_version": source_annotations.get(
            "canonical_safety_event_catalog_version", "unknown"
        ),
        "review_source": source_annotations.get("review_source", "owner_reviewed_v3"),
        "annotations": source_annotations["annotations"],
    }
    _write(args.cases_out, cases)
    _write(args.annotations_out, annotations)
    print(
        json.dumps(
            {
                "status": "complete",
                "dataset_version": version,
                "case_count": len(cases["cases"]),
                "cases_out": str(args.cases_out),
                "annotations_out": str(args.annotations_out),
                "original_files_changed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
