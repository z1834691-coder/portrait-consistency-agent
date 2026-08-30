.DEFAULT_GOAL := help

.PHONY: help sync test lint format check-env run rag-audit clean-local

help:
	@printf "Targets: sync, test, lint, format, check-env, run, rag-audit, clean-local\n"

sync:
	uv sync --all-groups

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check-env:
	uv run python scripts/check_environment.py

run:
	uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8501

rag-audit:
	uv run python scripts/audit_rag_lifecycle.py

clean-local:
	@printf "This project never deletes photos or .env automatically. Remove only a reviewed local path manually.\n"
