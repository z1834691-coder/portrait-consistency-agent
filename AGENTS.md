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
- `make run` binds only to `127.0.0.1:8501`; the checked-in `app.py` is also safe to run as a Community Cloud entrypoint after the deployment Gate.

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

The user has frozen the V0 subject-match, content-safety, LLM/data, anchor-lifecycle,
feedback, multi-face, and 8A planning boundaries. Checkpoint 6 is complete for local
quality, current-session CompareFace, geometry-only Profile v0, and the redacted
operational ledger; CompareFace has a successful live receipt. Tencent ImageModeration
has both a real `Block` receipt (`21bf408d-929a-46ec-83aa-78f071eff556`) and a separate
explicitly authorized `Pass` receipt (`211483d5-4ee0-41e8-b5d5-156f81557a69`). These
verify two provider outcomes, not complete content-safety coverage; never send the
blocked photo onward or call it safe.

Checkpoint 7 is complete: DeepSeek text-only IntentFrame Adapter, Schema validation,
explicit text consent, template fallback, 9 focused tests, and one real valid Schema
receipt all pass. Checkpoint 8A is complete: strict two-eye measurement, local
per-feature diagnosis, deterministic versioned mapping, proposed `EditPlan`, Streamlit
display, five planner tests, and a redacted end-to-end fixture trace. Checkpoint 8B is
complete for offline verification: user click → system structured confirmation intent
→ 10-minute scope/hash/Gate validation → exactly one BeautifyPic Adapter attempt
→ redacted ProviderRun → session-memory-only result display. Six execution tests and
the fixture Trace pass. Do not claim a new UI live-photo receipt, visual improvement,
automatic retry, persisted result image, or distributed exactly-once behavior. The
8C-1/8C-2 implementation slices are now complete: structured post-edit observation,
bounded `VERIFICATION_STRATEGY_SELECT`, `VerificationResult`, parent/child plan-family
continuation, bounded automatic follow-up execution/verification, and explicit feedback
hard stops. The initial confirmation may cover a plan family of at most three rounds;
every follow-up is a new child plan/ProviderRun with result-image hash lineage and must
show measurable cumulative improvement. Within that unchanged scope the Agent may make
one automatically-triggered chargeable call per child after deterministic preflight;
it must never bypass scope, consent, budget, idempotency or safety checks. Remaining work is real external/hybrid
verification, LLM free-form strategy, multi-face/batch handling, and production
resilience. RAG P0-A/P0-B are implemented as a separate local SQLite authority store:
three reviewed Provider Cards become ten atomic rules; metadata filtering and FTS5, then
local dense/RRF/reranking, return safe evidence/fallback routes with a redacted trace.
They read no photo or raw user text, call no LLM/Tencent/API, and do not create parameters,
EditPlans, or ProviderRuns. P0-B uses only fixed local model revisions and falls back to P0-A
when local weights are unavailable. P0-C is now wired into 8A plan preflight and 8C strategy
preflight as a bounded evidence consumer: it separates direct/reference/conflict evidence,
records safe bad cases, and is contractually `execution_authorized=false`. It cannot generate
parameters, authorize an Adapter, or introduce external/hybrid verification. A local read-only RAG
Governance Dashboard now visualizes redacted knowledge/route/bad-case facts; it does not add
permissions, use photos, run workers, or prove quality. Gold Set v2 review/thresholds, automated
workers, any new Provider, and external/hybrid adapters require their own frozen Gate.

Do not claim real AES-GCM subject-anchor storage, multi-face isolate/paste-back, public
deployment, full verification, RAG auto-editing, a live-ready new Provider, or external/hybrid
verification before their own checkpoints and tests pass. P0-C is a governed advisory integration,
not a tool-permission or image-editing system. Gold Set v2 的范围、指标门槛和单一人工事实审核者
已冻结。公开 52 题确定性基线已完成，私有 20 题隐藏集已在产品负责人受限目录中做过**仅聚合**
评分；当前基线未通过，不能把 public 的高分写成泛化或产品有效性。隐藏键、题干和逐题 Gold 不得
回流开发工作区；若继续优化，只能在 public/dev/challenge 上进行，并先处理指标定义与独立新
holdout 的产品决策门。两条新 Provider 候选（火山美颜 API V2.0、腾讯特效 SDK）必须分别完成
真实 schema/License/隐私/成本、live receipt、Gold 回归和产品负责人冻结。

## 2026-08-30 implementation snapshot

`services/rag_gold_eval.py`、`scripts/evaluate_rag_gold_v2.py` and the answerless
public/holdout packages are present. `services/rag_gold_baseline.py` has emitted
redacted predictions: public 52 题在当前确定性基线上除固定分母的 `Precision@3=47.44%` 外均为
100%，但 project Gate 为 `FAIL`；私有 holdout 仅回流安全聚合结果，route accuracy 为 25%，
project Gate 亦为 `FAIL`。私有 Markdown key 的自然语言 `must_not` 尚未标准化为事件 ID，因此
hard-safety 只能标 `MANUAL_REVIEW_REQUIRED`，不得写成安全 Gate 通过。

`services/volc_beauty.py` and `services/tencent_effect.py` remain candidate-only
shells with no SDK import, image egress or network path. Existing Tencent IMS and
BeautifyPic each have one newly authorized internal smoke receipt; this verifies a
single existing-provider route, not visual effectiveness or candidate-provider readiness.
The latest cross-check is `146 passed, 4 warnings`; Ruff, compileall and `git diff --check`
must be rerun after each change. The hidden answer key remains outside the developer-readable
workspace and must never be copied into tests, reports, prompts, or source control.

The latest evaluation-governance freeze is implemented: Precision C keeps fixed,
coverage-aware and returned-list Precision side by side; Holdout A retains v2 only as a
historical aggregate and prepares an independent v3 answerless template; Safety ID C maps
known labels through `RAG_EVT_*` and sends unknown labels to manual review. The current
project Gate is still `FAIL`; do not call these reporting changes a RAG quality pass.

## 2026-08-30 failure-analysis snapshot

`services/rag_failure_analysis.py` and `services/rag_correction_candidate.py` are
proposal-only offline evaluation helpers. They read public annotations/predictions and an
optional hidden aggregate only; they do not read hidden answers, photos, vectors, raw user
text, secrets, LLMs or providers. `pages/4_RAG治理看板.py` now embeds the allow-listed public
evaluation, hidden aggregate and failure-analysis HTML reports; `pages/5_RAG优化看板.py`
shows aggregate failure patterns, candidate deltas and the SOP. Neither page can apply a
candidate or grant execution permission. The current project Gate remains `FAIL`.

The current GitHub/Streamlit deployment package is intentionally private and excludes
`.env`, photos, result images, SQLite/JSONL, model cache, hidden answers, and local
evaluation reports. Community Cloud data hosting and ephemeral disk are not evidence of
production persistence, data-residency compliance, or a public service.
