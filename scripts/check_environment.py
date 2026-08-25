"""Non-sensitive local environment check for the project foundation."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "pyproject.toml",
    ".env.example",
    "docs/DEVELOPMENT_PROGRESS.md",
    "docs/DECISION_LOG.md",
)


def main() -> int:
    failures: list[str] = []
    if sys.version_info[:2] != (3, 10):
        failures.append(f"Expected Python 3.10, got {sys.version.split()[0]}")

    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).is_file():
            failures.append(f"Missing required file: {relative_path}")

    for relative_path in ("logs", "storage", "data/provider_cards"):
        if not (PROJECT_ROOT / relative_path).is_dir():
            failures.append(f"Missing required directory: {relative_path}")

    if failures:
        print("Environment check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Environment check passed.")
    print(f"Python: {sys.version.split()[0]}")
    print("Default server: http://127.0.0.1:8501 (not started by this check)")
    print("Secrets: .env is ignored and no secret value is printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
