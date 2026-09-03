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
The latest cross-check is `180 passed, 4 warnings`; Ruff, compileall and `git diff --check`
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

## 2026-08-30 visual design snapshot (historical; superseded below)

The earlier visual interaction structure is retained only as history and is not implemented in Streamlit: the
product will use a centre-stage alignment workspace, Reference Profile, and result
history as three spaces. The selected visual baseline is the reference image's mist
grey-purple field, cream/peach stage, and ink navigation hierarchy, without copying
photography or page assets. The eventual UI must use 3–5 primary colors, short labels,
low decoration density, and a prominent natural-language Agent input. The owner has
frozen the color family to mist purple, powder pink/cream, ink black, and peach-red;
do not add blue, green, or yellow. The new Occam-style page candidate uses only one
current upload action and one natural-language input on the first screen, but remains
unimplemented until owner approval. This historical paragraph's palette restriction is superseded by the
latest visual override below, which explicitly permits sparse acid-green state accents. Any UI work must preserve real consent, errors,
tool states, results, feedback, evidence visibility, and the prohibition on exposing
hidden chain-of-thought.

## 2026-09-02 visual design override

The owner has superseded the earlier exploratory palette and frozen Tweakcn Party Rock
raw Light/Dark tokens and PingFang SC as the formal UI font. For the current candidate
round, the solid black area is limited to the far-left navigation rail; the middle and
right surfaces remain warm ivory, with purple/lilac soft frames and paths and sparse
acid-green active nodes. The screenshot contributes only the ivory-canvas/black-rail/
purple-highlight relationship; it is not a content or asset reference. The token/font
freeze is a design input, not a Streamlit implementation or a change to consent, tool,
result, Trace, or privacy behavior. See `docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`,
`docs/PRODUCT_RULES.md` and section 29 of the execution PRD for the authoritative record.

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
`180 passed, 4 warnings`; Ruff check/format, compileall, `git diff --check`, the
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

The current repository snapshot has passed `.venv/bin/pytest -q` (`189 passed, 4 warnings`), `ruff check`, `ruff format --check` (`184 files already formatted`), `compileall`, and `git diff --check`. The V3/V4 validation runners and P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke runs also exit 0. The four warnings are existing Pillow deprecation warnings. This is an engineering-consistency receipt only: the RAG project Gate remains `FAIL`, RAG remains proposal-only, the active baseline is unchanged, and the original answerless V3 Holdout snapshot is not reclassified as a promotion result.

## 2026-09-02 current V4 truth override

V4 is now the latest independent RAG quality evidence: 48 non-overlapping answerless cases were run once and sealed before private aggregate scoring. The blind baseline is Route=12.50%, Evidence relation=18.75%, Recall@5=57.99%, MRR=81.25%, nDCG@5=63.22%, hard-safety=0/48 PASS, project quality Gate=FAIL. After the owner explicitly authorized a validation copy, the V4 candidate reached 100% on semantic diagnostic metrics, but this is not a new blind score; `blind_snapshot_match=true`, `active_baseline_changed=false`, and `proposal_only=true` remain mandatory. Do not promote the candidate or call RAG productized. See `docs/RAG_V4_HOLDOUT.md`, `reports/rag_v4_holdout_blind_aggregate.html`, and `reports/rag_v4_validation_diagnostics_v1.html`.

The next RAG quality evidence must be a new Holdout not used for diagnosis. Fixed/effective/returned Precision must stay side by side because V4 Gold is sparse; fixed project Gate remains authoritative. V4 traces and reports must not be used to grant Provider permission, create image parameters, or send photos out.

## 2026-09-02 reflection audit override

Before adding another Holdout or tuning retrieval, run the public-artifact-only
reflection audit in `docs/RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md` and keep its
scope flags explicit. The current V4 score is a mixed measurement: only 8/48
questions created a structured retrieval query, while the offline baseline also
projects route/evidence aliases before retrieval. Treat the leading issue as the
measurement and natural-language-to-query boundary, not as proven BGE/reranker
failure. The next product gate is still pending owner confirmation: split the
compiler benchmark from the canonical retrieval benchmark, add reviewed
Policy/Rule Cards for facts that must be retrieved, and run 10–15 public smoke
cases with a complete query→retrieval→adopted-evidence→route trace. Do not read
new Holdout answers, change the active baseline, promote a candidate, or call RAG
productized from this audit.

## 2026-09-02 fair evaluation supervisor current truth

The product owner has now confirmed the reflection Gate: evaluate natural-language
understanding and canonical retrieval as separate tracks, keep the historical fixed
Precision alongside diagnostic bands, and require an independent answerless process
supervisor before any Gold join. The current knowledge base is intentionally not
expanded in this step and RAG remains proposal-only.

`services/rag_process_supervisor.py` and `scripts/run_rag_fair_process_audit.py` now
replay the existing V3 validation copy and V4 holdout input without reading answers,
annotations, photos, face vectors or secrets and without network/LLM/Provider calls.
The fresh process gate is PASS for V3 (36/36) and V4 (48/48); unknown compiler cases
receive a neutral legal query and are counted as `unknown_fallback`, not silently
discarded. The historical V4 formal snapshot is still FAIL because it lacks required
stages/governance facts and contains projection injection. That snapshot is immutable
history; do not patch it into PASS. The fresh run's process gate is PASS and its
`quality_scoring_gate` is `READY_AFTER_SEPARATE_GOLD_JOIN`; the historical snapshot's
quality gate remains `LOCKED_HISTORICAL_PROCESS_AUDIT`. No validation score, promotion,
or productization claim is allowed until Gold is joined only to the fresh run and
interpreted under the two-track rubric. See `reports/rag_fair_process_audit_v1.json/.html` and
`docs/RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md`.

After sealing the four redacted answerless artifacts, the current full QA is
`.venv/bin/pytest -q` = `196 passed, 4 warnings`; Ruff check/format, compileall and
`git diff --check` pass. The four warnings are existing Pillow deprecations. This is
engineering consistency evidence only; V4 project quality remains FAIL and RAG remains
proposal-only.

## 2026-09-02 latest visual override

The owner’s latest visual feedback supersedes the earlier purple-black dark-flow direction for
active UI work. Party Rock raw token values and PingFang SC remain unchanged, but every current
candidate uses a solid black far-left navigation rail only; the middle and right surfaces stay
warm ivory. Purple/lilac appear as soft rounded frames, labels and provenance/alignment paths;
fluorescent acid green is sparse and reserved for active nodes or motion; dark ink supplies
type, rules and flexible outlines. Do not use a purple-black shadow background, dark center,
large fluorescent-green field, or a dense dashboard. The active visual package is three
candidates (A Archive Ribbon, B Soft Index, C Open Provenance), each exactly two keyframes—E01
entry and E02 Agent conversation. The four-state files and previous single E01/E02 package
remain recoverable under `design/keyframes/party-rock-pingfang/` and
`archive/v1-four-state/`; they are historical references until the owner selects a direction.
This is a visual/documentation change only; it does not alter contracts, consent, Provider
permissions, persistence, Trace, RAG, or the claim that Streamlit UI migration is unfinished.
See `docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md` and
`design/keyframes/party-rock-pingfang/candidates/candidate-review.html`.

The latest visual execution candidate is the Getty × Thread Track 1 under
`design/visual-tracks/getty-thread-party-rock/` with its detailed rules in
`docs/UI_VISUAL_DESIGN_SPEC_DETAILED.md`. It keeps only E01 `/align` and E02
`/align/:session`, uses the three-column black-nav/ivory-stage/ivory-thread shell,
and keeps E01/E02 free of raster environment art. A separate K00 cover candidate
uses the locally sourced, manifested historical artwork wall under
`cover/artwork/`; it is not part of the E01/E02 task surface. The track's HTML,
SVG and artwork are review assets only; they do not change the Streamlit
implementation, consent, Provider, persistence, Trace, RAG or privacy boundaries.

## 2026-09-03 latest visual asset override

The owner has now requested one additional K00 cover keyframe alongside the two
product keyframes E01 `/align` and E02 `/align/:session`. K00 is a separate
入口/brand-cover candidate, not a third business screen: it may use a purple
field, black top rail, ivory paper/cards and sparse acid-green entry marker, plus
the locally downloaded historical artwork registered in
`design/visual-tracks/getty-thread-party-rock/cover/artwork/SOURCES.md`. Do not
generate or hot-link artworks. The cover wall's nearest-card lift must have
keyboard, touch, pause and reduced-motion equivalents. Keep E01/E02 backgrounds
pure ivory with no environment assets; the archived `ambient-assets-v1` files
remain recoverable history only. `docs/UI_COVER_KEYFRAME_PROMPT.md` is the
single execution prompt for K00. All assets remain visual review sources and do
not change product contracts, permissions, Provider admission, privacy, Trace or
the unfinished Streamlit migration.

## 2026-09-02 latest Tencent Web Meta-Agent integration override

The current integration slice adds a read-only `ToolRegistry` and a
deterministic, structured `ToolProposal` layer. The registry exposes the
reviewed BeautifyPic baseline and the separate Tencent Effect Web candidate;
the proposal layer may explain a candidate route and a baseline fallback, but
it never authorizes execution, reads image bytes, holds credentials, creates a
ProviderRun, or calls a network/API. Keep `tencent_effect_web` as `candidate`
until the product owner freezes the result handoff (browser-side verification,
bounded Python handoff, or display/download only) and completes the remaining
privacy, region, cost, regression and admission evidence. Do not change the
BeautifyPic-only EditPlan contract silently.

## 2026-09-02 current Web integration override

The owner has frozen result handoff B. `EditPlan` and `ProviderRun` now support
the Web Card through a separate `TencentEffectWebParams` contract; the browser
returns a bounded, one-time result data URL and Python validates request/hash,
dimensions, MIME and size before giving in-memory bytes to the common
`VerificationResult`. The Web Card is still `candidate`: only an explicit
candidate-trial path may receive it, and the proposal layer remains
`execution_authorized=false`. E1 is fixture-verified and E2 is fixture-verified
with eight isolated success/failure/tamper cases (including input-hash and size
limits); E3 still requires live diverse
effect evidence, vendor privacy/region/retention/cost evidence and owner
approval. The latest implementation, rather than the historical paragraph
above, is the current truth.

The current full-suite receipt after the binding test and E2 metric correction
is `215 passed, 4 warnings`; the four warnings are existing Pillow deprecation
warnings. Ruff, compileall and diff checks also pass. This remains engineering
evidence only: Web Card is `candidate`, E3 is not approved, and RAG remains
proposal-only.

## 2026-09-03 current E3 evidence override

E3 has now run four owner-authorized real JPEG candidate trials on the deployed
exact-domain page 6. All four browser calls returned `succeeded`; the input
hashes match the preflight manifest, all four handoff flags are present, and
the offline Web contract/batch-isolation regression is green. A redacted
summary is in `reports/effect_web_e3_evidence_v1.json/.html` and the read-only
page 8 dashboard. The manifest intentionally does not invent `request_ref`
values; the report therefore keeps `request_ref_not_recorded_for_every_manual_receipt`
as an open blocker.

This is not visual generalization, common `VerificationResult` evidence, or
vendor admission. Do not promote `tencent_effect_web` from `candidate`, do not
claim the four images became more like the reference, and do not describe
supplier region/cost/retention as verified. Results and data URLs remain
browser-session-only; reports contain hashes and metadata, never image bytes or
paths. The next gate is human visual review plus common verification handoff
and supplier evidence, followed by explicit product-owner promotion.

## 2026-09-03 current limited-scope closeout override

For today's Demo recording, the owner explicitly deferred any new browser
manual upload/click step. The automatic closeout was saved at checkpoint
`a08197c` and pushed to `origin/main`. The current bridge is
`bridge_2026-09-03_static_capture_v6_rerun_recovery`; the evidence report was
rebuilt, E2 offline Web contract/batch-isolation regression is `8/8`, and the
E1 common `VerificationResult` handoff is fixture-verified.

The deterministic command
`python scripts/promote_effect_web_card.py --owner-approved --write-if-allowed`
was run and fail-closed with `card_changed=false`. Its current hard blockers
are `region_not_approved`, `estimated_cost_unknown`, and
`multi_sample_regression_not_passed`; therefore
`data/provider_cards/tencent_effect_web.json` must remain `candidate`. Do not
invent request references, visual improvement, vendor terms, or new live
receipts. Historical four-row Browser Receipt evidence may support a Demo
description of a real candidate SDK response, but it is not common visual
VerificationResult evidence or formal promotion. The next evidence gate is
still a new associable receipt/output review plus supplier region/cost/
retention evidence. RAG remains `proposal-only`.
