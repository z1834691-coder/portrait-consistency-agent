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
真实 schema/License/隐私/成本、live receipt、Gold 回归和产品负责人冻结。腾讯特效 Web
目前已经有独立的浏览器 Adapter、Streamlit page 6 和 Browser Receipt 合同，但 Card 仍是
candidate，尚未取得新的 live receipt；2026-09-01 Cloud 已完成最新代码重建并解决旧 ImportError，
本轮 smoke 因三项 Effect Web Secrets 缺失而尚未运行；移动/PC 细项 shell 仍不含 SDK 或图片出站。

## 2026-08-30 implementation snapshot

`services/rag_gold_eval.py`、`scripts/evaluate_rag_gold_v2.py` and the answerless
public/holdout packages are present. `services/rag_gold_baseline.py` has emitted
redacted predictions: public 52 题在当前确定性基线上除固定分母的 `Precision@3=47.44%` 外均为
100%，但 project Gate 为 `FAIL`；私有 holdout 仅回流安全聚合结果，route accuracy 为 25%，
project Gate 亦为 `FAIL`。私有 Markdown key 的自然语言 `must_not` 尚未标准化为事件 ID，因此
hard-safety 只能标 `MANUAL_REVIEW_REQUIRED`，不得写成安全 Gate 通过。

`services/volc_beauty.py` and `services/tencent_effect.py` remain candidate-only
shells with no SDK import, image egress or network path. The separate
`services/tencent_effect_web.py` is an implemented browser-side candidate adapter: its
offline contract path is tested, but it remains fail-closed until the bound Cloud page
returns a real Browser Receipt and the admission evidence is manually reviewed. Existing Tencent IMS and
BeautifyPic each have one newly authorized internal smoke receipt; this verifies a
single existing-provider route, not visual effectiveness or candidate-provider readiness.
The latest cross-check is `178 passed, 4 warnings`; Ruff, compileall and `git diff --check`
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

## 2026-08-30 RAG lifecycle audit snapshot

`RagLifecycleAudit` is now the metadata-only preflight for the local RAG knowledge base.
It checks reviewed Card/Policy status, validity dates, source URI, atomic-rule counts and
the derived dense manifest; it writes only a redacted audit ledger/report and never changes
knowledge state, publishes candidates, deletes data, rebuilds indexes, calls a model/provider,
or grants execution permission. The current snapshot is 3 reviewed Tencent Cards, 10 active
chunks, no lifecycle issues and `index_status=in_sync`. Full regression after this addition
is 150 passed with 4 existing Pillow deprecation warnings; the RAG project quality Gate is
still FAIL. If a future task changes RAG code or policy, rerun the lifecycle audit and the
full consistency checklist before describing the RAG work as closed.

## 2026-08-30 visual design snapshot

The visual interaction structure is frozen but is not implemented in Streamlit: the
product will use a centre-stage alignment workspace, Reference Profile, and result
history as three spaces. The selected visual baseline is the reference image's mist
grey-purple field, cream/peach stage, and ink navigation hierarchy, without copying
photography or page assets. The eventual UI must use 3–5 primary colors, short labels,
low decoration density, and a prominent natural-language Agent input. The owner has
frozen the color family to mist purple, powder pink/cream, ink black, and peach-red;
do not add blue, green, or yellow. The new Occam-style page candidate uses only one
current upload action and one natural-language input on the first screen, but remains
unimplemented until owner approval. Any UI work must preserve real consent, errors,
tool states, results, feedback, evidence visibility, and the prohibition on exposing
hidden chain-of-thought.

## 2026-09-01 current truth override

The owner has completed the v3 Holdout review. A 36-case answerless runtime was run
once through the deterministic baseline and privately aggregated outside the workspace.
The run read no hidden answers, photos, vectors, LLMs, providers, or network. Current
aggregate quality is Route=30.56%, Recall@5=59.72%, MRR=77.78%, nDCG@5=63.81%,
evidence-relation accuracy=23.61%; hard-safety violations are 0/36 (PASS), while the
project quality Gate is `FAIL`. Do not tune the hidden set or describe this as RAG
quality passing.

The Streamlit Community Cloud Private page is open and ready for the owner to perform
the first real user flow. No agent has uploaded a real photo or created a new UI
Tencent image receipt in this snapshot. 8C-1/8C-2 remain code/fixture-verified; a
real multi-round UI receipt and visual improvement require the owner to operate the
page. See `docs/FIRST_USER_E2E_TEST.md` and `docs/MIDTERM_STATUS_2026-09-01.md`.

## 2026-09-01 failure-driven RAG current truth

The first optimization loop was a no-op because its candidates changed only
post-processed `Prediction` objects while the public baseline was already canonical.
The current, separate `rag_failure_driven_dev_v1` set (28 owner-review cases: 16 dev +
12 challenge) evaluates a candidate at the real natural-language → `RagQuery` boundary.
Its redacted report is `reports/rag_failure_driven_loop_v1.json/.html` and its read-only
visualization is page 5. V0 Composite is `0.355614`; V1 is `0.403233` (+0.047619,
2 predictions changed); V2 query compilation is `0.947619` (+0.544386, 22 predictions
changed); V3/V4 each changed 0 predictions and stopped after two gains below `0.01`.

This is development-set engineering evidence, not a product-quality pass: annotations
are `owner_review_required`, public regression/project Gate remains `FAIL`, and a new
independent Holdout v4 is required before promotion. Every candidate trace proves no
network/LLM/Provider/hidden-answer access and `active_baseline_changed=false`; RAG remains
advisory-only with `execution_authorized=false`. At the time of this historical snapshot,
the private v3 per-case answer key was not read. On 2026-09-02 the product owner explicitly
unlocked a derived V3 validation copy for diagnosis; that later exception is recorded below
and does not alter this historical run. The previous `160 passed` line is a historical snapshot. The
report also keeps V0-versus-terminal per-case diagnostics in
`final_candidate_diagnostics`; the human-readable review is
`docs/RAG_FAILURE_CASE_REVIEW_V2.md`.

## 2026-09-02 V3 validation override and current RAG truth

The product owner explicitly reclassified the reviewed V3 questions from a one-time
Holdout-A acceptance run into a separate `validation` copy for per-case diagnosis. The
original answerless blind snapshot remains outside the workspace and was not rerun. The
derived files are `data/evaluation/rag_v3_validation_cases_v1.json` and
`data/evaluation/rag_v3_validation_annotations_v1.json`; they are not read by the online
RAG path and do not change the active baseline.

The diagnostic runner records H01–H36 question, Gold, prediction, root cause, SOP,
query projection, FTS/dense/RRF/rerank summary and full safe Trace for G0–G5. The final
candidate improves V3 validation Route from 30.56% to 100%, Evidence relation from 23.61%
to 97.22% and Recall@5 from 59.72% to 100%; G2's apparent 100% was rejected by public
regression, while G3 preserves the known public baseline. G4/G5 are downstream no-ops.
Fixed Precision/project Gate remains `FAIL`; hard-safety is `PASS`; no candidate is
promoted. All traces are offline (`network_called=false`, `llm_called=false`,
`provider_api_called=false`, `photo_or_face_vector_read=false`) and proposal-only. A new,
non-overlapping V4 Holdout is still required before any promotion discussion.

After the failure-driven Loop v2 change, the current full-suite verification is
`178 passed, 4 warnings`; Ruff check/format, compileall, `git diff --check`, the
failure-driven loop, P0-A/P0-B/advisory/lifecycle/8C/8C2 smokes all pass. The four
warnings remain the existing Pillow deprecation warnings. This updates the historical
160-test snapshot above; it does not change the RAG quality Gate (`FAIL`) or promote V2.

## 2026-09-01 Tencent Effect Web Cloud gate

Cloud 在拉取 `14b692b` 后已成功重建，page 6 能正常加载；此前的
`load_tencent_effect_web_card` ImportError 是旧进程缓存旧代码造成的，重启后已消失。
当前 Cloud Settings → Secrets 页面已打开，但尚未配置腾讯特效 Web 所需的三项根级配置：
`TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`。
因此本轮没有加载 Web SDK、没有处理图片、没有 Browser Receipt，也没有更新 Card 的
`live_smoke_status`；用户补齐三项 Secrets 后才可运行官方示例图 smoke。已有 Tencent REST
密钥与这三项 Web License 配置是两套不同凭据，不能互相替代。`TENCENT_EFFECT_LICENSE_TOKEN`
只用于服务端签名，禁止进入页面、Trace、仓库或聊天。

## 2026-09-02 current QA override

The current repository snapshot has passed `.venv/bin/pytest -q` (`178 passed, 4 warnings`), `ruff check`, `ruff format --check` (`138 files already formatted`), `compileall`, and `git diff --check`. The V3 validation runner and P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke runs also exit 0. The four warnings are existing Pillow deprecation warnings. This is an engineering-consistency receipt only: the RAG project Gate remains `FAIL`, RAG remains proposal-only, the active baseline is unchanged, and the original answerless V3 Holdout snapshot is not reclassified as a promotion result.
