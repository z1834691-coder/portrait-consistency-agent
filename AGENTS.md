# Project working agreement

## Purpose

Build a traceable C-end portrait consistency Agent demo for the 2026-09-04 submission. The product aligns the user's own authorized portrait photos to a confirmed facial-geometry Reference Profile. It is not identity search, beauty scoring, or a production service.

## Current truth

- `docs/母版人像一致性Agent-执行版PRD.md` is the current product/implementation truth source.
- `docs/PRODUCT_RULES.md`, `docs/CONTRACTS.md`, and `docs/AGENT_PROMPTS.md` are specialist specifications.
- The original blueprint under the parent `outputs/` directory is historical planning, not current behavior.
- Code/tests/runtime evidence override prose claims about what is implemented.

## Stack and commands

- Python 3.10, `uv`, Pydantic v2, Streamlit, SQLite/JSONL, Tencent FMU SDK.
- `uv sync --all-groups`
- `make check-env`
- `make test`
- `make lint`
- `uv run ruff format --check .`
- `make run` binds only to `127.0.0.1:8501`.

## Product-change protocol

- Product contracts are discussed before code: user draft → assistant gaps/tradeoffs → user confirmation → explicit freeze → code/tests.
- Do not silently turn a candidate rule into a frozen decision.
- Configurable thresholds, round limits, budgets, and retry limits belong in versioned Policy snapshots, not permanent field types.
- After a frozen rule or implementation changes, sync the execution PRD, specialist doc, `DECISION_LOG.md`, `DEVELOPMENT_PROGRESS.md`, README, code, and tests.

## Safety and evidence

- Never commit `.env`, credentials, photos, generated results, SQLite files, or JSONL logs.
- Do not put raw/Base64 images, signed URLs, secrets, subject anchors, confirmation refs, or full face vectors into Trace.
- External editing requires bounded user confirmation. LLMs never calculate visual facts, parameters, permissions, or provider receipts.
- Do not expose hidden chain-of-thought; show verifiable progress, evidence, tool receipts, and concise decision summaries.
- Label work precisely as implemented/verified, frozen/not implemented, or future candidate.

## Current next step

First freeze the V0 subject-match provider, content-safety mechanism, and Profile persistence scope with the user. Then implement and audit two separate paths: MediaPipe/OpenCV for face geometry, quality, and editability; a dedicated subject-match Adapter for same-person routing. Build the real Reference Profile v0 only after those inputs are explicit. Do not jump to RAG, LangGraph, UI polish, or public deployment before this module passes its cases and Trace review.
