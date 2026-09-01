# 母版人像一致性 Agent

## 2026-09-01 Cloud ImageModeration 页面失败的根因与修复

第一位用户在 Cloud 页面看到 `Tencent ImageModeration request failed`。Cloud 运行日志的稳定异常是 Streamlit 控件重跑时重复写入同一个 `photo_quality_result_id`，SQLite 抛出 `UNIQUE constraint failed`；这不是可以绕过的内容安全结果。代码已改为：同一业务唯一键和相同脱敏事实幂等复用，事实发生变化则以可识别冲突停止，不覆盖旧证据；重复重放也不会重复计入完成类运营事件。页面仍只展示脱敏腾讯 `error_code`/`RequestId`，不自动重试、不放行 `Review/Block`、不保存原图或密钥。

本机用明确授权照片完成的真实 IMS smoke 返回 `status=succeeded`、`Pass`、RequestId=`c95e1359-9ecb-45ac-aa94-3776fbccc0ad`；这证明本机服务链可用，但不代替 Cloud 新版本回执。提交并重建后，请刷新 Private App、重新执行一次内容安全检查；如果仍失败，只回传页面显示的 `error_code` 和 `RequestId`。

当前阶段：`Contract v0.4 frozen / Checkpoint 8A + 8B + 8C-1/8C-2 offline Gates passed / RAG P0-A + P0-B + P0-C + governance + optimization dashboards verified / Gold Set v2 public+private aggregate baseline FAIL / two Provider candidates fail-closed / private GitHub package pushed / Streamlit Cloud Private app created / Tencent Web License normal`

> **最新状态（2026-09-01）：** 产品负责人已审核 v3 Holdout 36 题并完成一次私有聚合盲测；Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、hard-safety=PASS，但 project quality Gate=`FAIL`。第一位用户已完成母版/目标照 IMS、Profile 建立和 CompareFace；目标照原始分 `56.231842041015625` 为 `uncertain`，旧页面在 8A 因缺少本人/编辑权确认入口而暂停。代码已补齐一次性确认路径，Cloud 重建后可继续 8A→8B→8C；尚无真实 BeautifyPic ProviderRun/VerificationResult。

目标：在 2026-09-04 前完成一个真实可运行、可录屏、可追溯的 Demo。它帮助用户以一张确认的母版建立五官与脸型标准，再对本人单张或同组照片进行诊断、受确认保护的编辑和复测；它不是身份搜索、审美评分或生产服务。

```text
母版确认 → Profile → 质量 / 内容安全 / 当前会话同人门
→ 自然语言意图澄清 → 差异与编辑计划 → 用户确认 → 图片编辑 API
→ 修后复测 → 停止 / 重规划 / 重传 / 开发者复核
```

## 当前真实能力

- Pydantic 六个业务合同、版本化 Policy、SQLite/JSONL 脱敏 Trace 已升级至 `v0.4`；
- 本地质量门：Pillow + OpenCV Haar，可做安全解码、格式/尺寸预检、清晰度、曝光、人脸数和粗粒度脸框/眼睛几何；
- 当前会话同人门：腾讯 IAI CompareFace 3.0。真实同图 smoke 已成功，原始分仅作后台证据，不显示为相似度或概率；
- Profile v0：只保存归一化几何和版本信息，不保存母版原图、EXIF、肤色/妆面、身体、明文向量或密钥；
- 检查点 8A：已接入严格双眼测量、逐特征差异诊断和确定性 `EditPlan` 草案；页面可展示规则、局部差异和脱敏 Trace；
- <span style="color:#C00000"><strong>8A 同人不确定路径：CompareFace 为 `uncertain` 时，用户确认“目标照是本人且有权编辑”后，系统把一次性 `subject_match_uncertain_acknowledged` 放入有界 scope，继续规划；不改成 `match`、不更新长期主体锚点，`no_match` 仍硬拒绝。</strong></span>
- 检查点 8B：页面已接入“明确告知 → 用户确认 → 照片/Profile/Gate/scope 校验 → 一次 BeautifyPic 调用 → 脱敏 ProviderRun → 当前会话内预览/下载”。6 个离线执行案例和 fixture Trace 已通过；开发期间未新发起 UI 真实照片调用；8C-1/8C-2 可在会话内对结果复测、生成下一轮子计划并保留父子血缘；
- BeautifyPic：已完成一次历史真实工具调用 Gate；8B 首轮页面执行链只在用户实际勾选/点击并使用授权照片时才可能调用腾讯，绝不自动发送照片；8C-2 在同一首次授权 scope 内由 Agent 受限自动续跑子轮，调用前后写入 preflight/ProviderRun/Verification Trace，scope 改变则停止并重新授权；
- 运营账本：匿名 `product_events` 与本地管理员 Dashboard 已实现，用于会话、建档、意图、工具调用、复测、显式反馈、重传和 WAU/MAU 的脱敏聚合；后续还需真实采集 Profile 建立率、首次成功修图率、7/30 日回访、会话完成率、失败后重传率和明确满意/不满意比例；它不是 Dataset，也不是线上 KPI 结论；
- LLM：DeepSeek V4 Flash 的文本 `IntentFrame` Adapter、显式文字授权、Pydantic Schema 校验和本地模板 fallback 已接入；固定无个人信息文本的真实 live smoke 已返回合法 Schema（2957 ms、1471 tokens），但这不代表图片编辑或多轮 Agent 已验证。
- <span style="color:#C00000"><strong>8C-1/8C-2：已实现结果图本地观察、受限 `VERIFICATION_STRATEGY_SELECT` baseline、逐特征趋势、结构化目标证据、父子子计划/ProviderRun 血缘、三轮上限和点赞/点踩/文字 hash 反馈。首次确认范围仍有效且证据满足时，系统会自动执行并自动复测下一轮；每次触发前后都有脱敏 Trace，超出范围不会调用。</strong></span>
- <span style="color:#C00000"><strong>RAG P0-A / P0-B / P0-C：已实现独立本地 SQLite 权威知识库、metadata 硬过滤、FTS5、local dense、RRF、local reranker、来源依据卡、脱敏 Trace，以及对 8A/8C 的受限 evidence 回接。</strong>当前导入 3 张人工审核的 Tencent Provider Card、拆成 10 条原子规则；P0-B 只从本地缓存读取固定模型 revision，模型缺失时退回 P0-A。P0-C 把结果分为 direct/reference/conflict，`execution_authorized=false`；它不读取照片或用户原话，不调用 LLM/Tencent/API，不生成参数或新的工具权限。另有一个只读本机 RAG 治理 Dashboard，展示脱敏知识/路由/bad-case 聚合；它不是自动 worker、外部/混合复测或“RAG 自动修图”。</span>
- <span style="color:#C00000"><strong>Gold Set v2/v3：v2 保留为历史诊断；v3 已由产品负责人审核 36 题，并按 Holdout A 完成一次私有聚合盲测。v3 结果为 Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、hard-safety=PASS、project Gate=`FAIL`。逐题答案不回流开发，不能据此宣称 RAG 泛化通过。</strong></span>
- <span style="color:#C00000"><strong>Provider 扩展：火山美颜 API V2.0 与腾讯特效 SDK 已建立 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 smoke 入口；两者均未接入 SDK/API、未发送图片、未使用密钥，状态保持 `candidate`/fail-closed。产品决策是火山 V0 暂不购买/接入，当前执行链只用 Tencent。</strong></span>
- <span style="color:#C00000"><strong>RAG failure-pattern：已生成脱敏的公开分层指标、隐藏集聚合错误类型、SOP 与 proposal-only 自校正候选；候选公开回归无指标回退但未推广，project Gate 仍为 `FAIL`。RAG 治理看板现可嵌入公开评测、隐藏聚合和失败分析 HTML，另有只读 RAG 优化看板。</strong></span>
- <span style="color:#C00000"><strong>RAG 生命周期审计：已实现 metadata-only `RagLifecycleAudit`、显式审计脚本、SQLite 审计账本、dense manifest 一致性检查和治理看板入口。当前 3 张审核 Tencent Card/10 条有效规则审计为 `complete`、issue 数为 0、index=`in_sync`；审计不自动发布/改状态/删除/重建索引，RAG 仍只能提议。</strong></span>
- <span style="color:#C00000"><strong>部署包：已补齐 Community Cloud 可直接读取的 `uv.lock` 环境声明、`src/` 入口兼容、云端配置和部署说明，并已推送到私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)。Streamlit Cloud Private App 已创建，URL 为 [`portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`](https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app)，页面已在浏览器打开待第一位用户操作；腾讯 Web License 已以纯主机名提交并在控制台显示“正常”（2026-08-30 至 2026-09-13）。仓库发布边界仍排除密钥、照片、SQLite/JSONL、模型缓存、隐藏答案和本机评测报告。</strong></span>
- <span style="color:#C00000"><strong>Cloud 凭据入口：本机 `.env` 不会随部署进入 Cloud；要触发真实腾讯安全/同人/修图请求，必须在该 App 的 Settings → Secrets 以根级变量配置 `TENCENT_SECRET_ID` 与 `TENCENT_SECRET_KEY`，保存后重启。缺少任一项时系统 fail-closed，不发送照片。</strong></span>
- <span style="color:#C00000"><strong>Cloud 腾讯错误回执：如果 ImageModeration 已读到密钥但请求失败，页面现在会安全显示腾讯 `error_code` 与 `RequestId`，并将同样的非敏感字段写入脱敏 Trace；不会显示原图、密钥或腾讯原始错误全文。没有 `RequestId` 时明确显示“未返回”，不能把失败误写成内容安全通过。</strong></span>
- <span style="color:#C00000"><strong>视觉交互方向已冻结、尚未实现：</strong>产品采用“中心舞台式首页／对齐工作台 + 母版档案 + 结果记录”的三空间结构；Agent 只在澄清、真实进度、边界与结果时用人话发声，参数/回执/脱敏 Trace 位于第二层。参考图的层次语法与雾紫、肉粉／奶油粉、墨黑、桃红四色体系已冻结；页面遵守奥卡姆剃刀，只突出当前任务、一个上传动作和一个自然语言入口。当前低实体页面样张仍待产品负责人审核，不等于已部署 UI，不改变照片权限、工具调用或数据边界。</span>
- <span style="color:#C00000"><strong>第一位用户 UX 反馈（待 UI Gate）：</strong>上传等待过长；首屏不应展示脱敏 JSON；A/B/C 检查点和按钮过多；自然语言入口被 GUI 挤压；视觉偏工程文档。当前只记录为事实反馈，尚未擅自改 UI 或删除必要权限门。</span>

## 重要边界

- V0 不展示 0—100 一致性指数、固定 90 分线或未经校准的接受概率；
- 质量、同人、内容安全、用户意图、参数规划、API 回执和修后验证由不同模块负责；LLM 不看原图、不算视觉数值、不猜参数、不自行授权；
- 图片、Base64、人脸向量、主体锚点、密钥、确认引用和原始文本不会进入 Trace；DeepSeek 远程调用也只会收到经常见 PII 脱敏的最小必要文字和不含不透明 ID 的上下文；失败先走本地模板，不自动转发第二个云 Provider；OpenRouter/跨境默认关闭，ZDR 需另行核验；
- 腾讯结果图只保留在当前浏览器会话内，用户可主动下载；会话结束、服务重启或最多 10 分钟后不可取。结果 Base64 不写 SQLite、JSONL、Trace 或 `storage/results`；8B 每份确认计划只允许一次外部尝试，超时/网络错误也不自动重试；8C 若在计划族内继续，必须新建子 plan/ProviderRun，并以父回执和结果 hash 血缘相连；同一首次确认 scope 内的后续调用由 Agent 自动触发，但每次都必须经过 preflight/idempotency 检查并写 Trace，不能重试同一计划。
- 主体锚点的产品规则已冻结为：独立同意、183 天保存、30/7 天提醒、撤回后立即停用、主存储 24 小时删除/备份 7 天清理；真实 AES-GCM 存储、TTL/delete worker 与密钥管理尚未实现；
- 多脸的后续路线是“检测 → 用户选脸 → 隔离/裁剪 → 编辑 → 回贴 → 复测”。当前完整链路未实现，系统必须要求用户上传单脸或先裁剪；
- 腾讯 IMS ImageModeration Adapter 已完成两条真实 live 证据：一张样本返回 `Block`（`RequestId=21bf408d-929a-46ec-83aa-78f071eff556`），本次明确授权照片返回 `Pass`（`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`）。这只验证了服务、权限、签名、解析和两种路由样例，不代表所有照片都安全；`Block` 样本仍不得进入修图；
- 当前默认仍只在本机运行。部署包可供 Community Cloud 受邀 Beta 使用，但平台容器位于美国且磁盘不保证持久化；没有完成数据出境确认、访问名单、Secrets、费用和删除策略前，不开放真实照片公网测试。

当前产品和工程的共同真相源是 [执行版 PRD](docs/母版人像一致性Agent-执行版PRD.md)。前端和交互执行规格见 [前端与交互设计需求文档](docs/前端与交互设计需求文档.md)。规则见 [PRODUCT_RULES.md](docs/PRODUCT_RULES.md)，合同见 [CONTRACTS.md](docs/CONTRACTS.md)，LLM Prompt 边界见 [AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md)，检查点 7 的输入/输出/案例/Trace 见 [DEEPSEEK_INTENT_GATE.md](docs/DEEPSEEK_INTENT_GATE.md)，RAG 决策与后续 Gate 见 [RAG_DECISION_GATE.md](docs/RAG_DECISION_GATE.md)，failure pattern SOP 见 [RAG_FAILURE_ANALYSIS_SOP.md](docs/RAG_FAILURE_ANALYSIS_SOP.md)，P0-A/P0-B/P0-C 实际实现/Trace 见 [RAG_P0A_RETRIEVAL_GATE.md](docs/RAG_P0A_RETRIEVAL_GATE.md)、[RAG_P0B_HYBRID_RETRIEVAL_GATE.md](docs/RAG_P0B_HYBRID_RETRIEVAL_GATE.md) 与 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](docs/RAG_P0C_ADVISORY_INTEGRATION_GATE.md)，Gold evaluator/盲审约束见 [RAG_GOLD_EVALUATOR.md](docs/RAG_GOLD_EVALUATOR.md)、逐题人工模板见 [RAG_GOLD_SET_V2_HUMAN_REVIEW.md](docs/RAG_GOLD_SET_V2_HUMAN_REVIEW.md)，v3 保管与一次性运行边界见 [RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md](docs/RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md)，第一位用户操作见 [FIRST_USER_E2E_TEST.md](docs/FIRST_USER_E2E_TEST.md)，中期快照见 [MIDTERM_STATUS_2026-09-01.md](docs/MIDTERM_STATUS_2026-09-01.md)，Provider 候选对比见 [PROVIDER_EXPANSION_RESEARCH.md](docs/PROVIDER_EXPANSION_RESEARCH.md)，决策过程见 [DECISION_LOG.md](docs/DECISION_LOG.md)，逐步证据见 [DEVELOPMENT_PROGRESS.md](docs/DEVELOPMENT_PROGRESS.md)。

## 下一开发 Gate

RAG P0-A/P0-B/P0-C 与只读治理 Dashboard 已完成本地可审计闭环；Gold Set v2 的 public baseline、无答案 holdout 和私有 aggregate 比对也已完成，但当前基线没有通过。Precision C、Holdout A、Safety ID C 已冻结并落地：评测保留固定分母并并行展示覆盖式/返回式 Precision；v2 只作历史诊断；v3 已在工作区外完成产品负责人审核并完成一次正式 answerless 盲测，质量 project Gate=`FAIL`、hard-safety=`PASS`。已知安全事件映射为 `RAG_EVT_*`，未知事件保持 `MANUAL_REVIEW_REQUIRED`。当前真实用户流程已到达 8A 的 `uncertain` 确认边界；Cloud 重建后完成一次确认即可继续，尚无真实 ProviderRun/VerificationResult。随后再收集体验反馈并进入 UI Gate；候选 Provider 的 License/隐私/价格/区域/真实 receipt/Gold 准入仍独立推进。P0-C 只提议和留证，不能改变图片执行权限。

## 2026-08-30 RAG 优化闭环（当前真实状态）

failure analyzer 已把“公开指标、隐藏聚合、错误模式、候选修正、回归差值、SOP”串成可重放链路。当前候选 `rag-correction-candidate-v0.1` 只做经审核的同义词归一化，公开回归 `regression_gate=PASS`，但 project Gate 仍为 `FAIL`，所以没有写入现役检索或权限逻辑。报告和 Dashboard 都是本机只读治理工具，不是生产监控、自动修复器、训练 Dataset 或图片编辑器。

两个候选 Provider 的真实状态仍为：火山 V2 `not_run`、腾讯特效 SDK `blocked`；两者均未导入 SDK、未读取用户照片、未发送图片、未生成真实 ProviderRun。只有当前 Tencent BeautifyPic/IMS 路径有既有真实回执；由于火山官方准入要求购买创点且公开价格/试用额度未闭合，V0 已明确暂不购买/接入。未来若重新开启候选，仍需按 Card → Adapter → 权限/预算 → live receipt → Gold 回归 → 产品负责人冻结的顺序推进。

## 当前项目树

```text
portrait-consistency-agent/
├── app.py                         # 本机 Streamlit：质量/安全/同人/Profile/IntentFrame/8A/8B/8C 复测、计划族与反馈
├── pages/1_运营数据看板.py          # 仅本机管理员的脱敏运营 Dashboard
├── pages/2_RAG知识库与检索.py       # 本地 RAG P0-A 依据卡与 Trace 演示页
├── pages/3_RAG本地混合检索.py       # 本地 RAG P0-B FTS+dense+rerank 演示页
├── pages/4_RAG治理看板.py            # 本机管理员：脱敏知识/路由/bad-case 聚合，不读照片或原话
├── pages/5_RAG优化看板.py             # 本机管理员：failure pattern、候选差值与 SOP
├── data/provider_cards/           # 版本化 Provider Card（含已审核 Tencent 与 candidate 扩展）
├── data/evaluation/               # Gold Set v2 + v3 Holdout 模板/安全事件目录（答案键与运行包分离）
├── reports/                        # 本次无答案评测的 JSON/Markdown/HTML 审计产物
├── docs/                          # PRD、规则、合同、Prompt、进展、决策、RAG Gate、API Gate 与第一位用户测试说明
├── scripts/                       # 默认不联网；含 8C-2 计划族 fixture smoke
├── src/portrait_consistency_agent/
│   ├── agent/                     # DeepSeek 文本解析 Adapter + 本地模板 fallback
│   ├── core/                      # v0.4 合同、独立 RAG 合同、Policy、本地设置
│   ├── services/                  # 质量门 / Profile / 8A/8B/8C / RAG 检索+advice+评测+失败分析+生命周期审计 / Provider Adapter shells
│   └── storage/                   # 运行账本 SQLite/JSONL + 独立 RAG SQLite/FTS/派生向量索引
├── storage/                       # 本地脱敏 DB（Git 忽略；当前产品不写结果图）
├── logs/                          # 本地 JSONL trace（Git 忽略）
└── tests/                         # 当前 160 个自动化测试（另有 4 条 Pillow 已知弃用警告）
```

## 本地命令

```bash
uv sync --all-groups
# 只有需要本地 BGE embedding/reranker 权重时才额外安装（云端不需要）
uv sync --all-groups --extra rag-local
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
make run
uv run python scripts/smoke_deepseek_intent.py
uv run python scripts/smoke_edit_planner.py
uv run python scripts/smoke_execution_8b.py
uv run python scripts/smoke_verification_8c.py
uv run python scripts/smoke_plan_family_8c2.py
uv run python scripts/smoke_rag_p0a.py
uv run python scripts/smoke_rag_p0b.py
uv run python scripts/smoke_rag_advisory.py
uv run python scripts/analyze_rag_failures.py
uv run python scripts/run_rag_optimization_loop.py
uv run python scripts/audit_rag_lifecycle.py
uv run python scripts/evaluate_rag_gold_v2.py --html reports/rag_gold_v2_pending.html
uv run python scripts/smoke_volc_beauty.py
uv run python scripts/smoke_tencent_effect_shell.py
# 只在需要首次下载公开本地模型时显式执行；正常页面/运行不会下载：
uv run python scripts/smoke_rag_p0b.py --allow-model-download
# DeepSeek 已验证；仅在密钥轮换或重新部署后才需要：
uv run python scripts/smoke_deepseek_intent.py --allow-live
```

2026-09-01 当前收尾校验：全量 `pytest` 实际为 `160 passed, 4 warnings`；`ruff format --check`、`ruff check`、`compileall`、8C-1/8C-2 smoke、RAG advisory、RAG lifecycle audit 和 `git diff --check` 均通过。四条 warning 均为既有 Pillow 已知弃用警告。v3 private scorer 只输出聚合结果和安全事实；它不调用 LLM/Provider/网络，也不输出题目、case ID、Gold、答案键路径或图片。当前 RAG project quality Gate 为 `FAIL`，不得写成通过；真实 UI 照片流程尚未由 Codex 代跑。

## 2026-08-30 评测治理冻结

Precision 采用 C：固定、覆盖式、返回式三种口径并行；固定口径继续作为历史 Gate，覆盖式/返回式只做诊断。Holdout 采用 A：v2 仅作历史 aggregate，v3 已在工作区外完成产品负责人审核并完成一次正式 answerless 盲测。安全事件采用 C：版本化确定性字典 + 产品负责人确认，已知标签映射为 `RAG_EVT_*`，未知标签必须人工复核。相关报告、看板和测试已同步；v3 quality Gate 仍 `FAIL`。

不要将 `.env`、真实照片、下载后的结果图片、SQLite 文件或 JSONL 日志提交到 Git。DeepSeek Key 必须从密码管理器直接粘贴到本机 `.env`，不要发送到聊天。外部腾讯首轮调用只能在用户明确同意且使用已授权照片时，以 `--allow-live` 或页面的明确确认触发；8C-2 后继调用若仍在同一首次授权 scope 内，需先通过自动 preflight 并写入 Trace，scope 变化则重新确认。DeepSeek smoke 同样必须显式传 `--allow-live`。

## 2026-09-01 RAG 自动优化 Loop（当前真实状态）

本项目现在有一条 proposal-only 的失败模式自校正循环：读取 public dev/challenge 52 题和公开 annotations，逐题生成错误代码，按 Rubric 运行 V0 baseline、V1 同义词归一化、V2 relation canonical 化，再做 anti-overfit 和边际效益判断。v3 Holdout 只提供私有 aggregate 上下文，逐题答案没有读取，也没有重复正式运行。

真实结果：V0/V1/V2 Composite 均为 `0.947436`，候选增益均为 `0.0`；public route/evidence/relation/Recall@5/MRR/nDCG@5 均 `100%`，固定 Precision@3=`47.44%`（51/52 题 Gold 少于 3 条），project Gate 仍 `FAIL`。连续两代增益小于 `0.01` 后，V3/V4 按停止规则跳过；anti-overfit=`PASS`，active baseline、权限、Provider、参数和 `execution_authorized=false` 均未改变。

优化产物：[RAG_OPTIMIZATION_PROGRESS.md](docs/RAG_OPTIMIZATION_PROGRESS.md)、[RAG_OPTIMIZATION_RUBRIC.md](docs/RAG_OPTIMIZATION_RUBRIC.md)、`reports/rag_optimization_loop_v1.json/.html`、Streamlit page 5。Dashboard 还会把 v3 聚合错误拆成“事实/假设/下一份证据”，但不提供逐题 hidden 结论。它是只读可视化治理工具，不是自动训练、自动发布或生产监控；如要再次正式验收，必须新建独立 Holdout v4。

## 2026-08-30 RAG 生命周期审计收口

`scripts/audit_rag_lifecycle.py` 会对审核知识卡的状态、有效期、来源 URI、原子规则数和 dense manifest 做一次 metadata-only 审计，并把 `RagLifecycleAudit` 写入本地脱敏账本、JSON/HTML 和 RAG 治理看板。当前快照为 3 张 Tencent Card、10 条 active 规则、issue 数 0、index=`in_sync`。它不会读照片、来源正文、用户原话、向量、答案键或密钥，也不会联网、调用 LLM/Provider、自动发布、改状态、删除或重建索引；知识变更仍需人工审核后重建并回归。该模块完成的是 RAG 工程治理闭环，不代表 public/holdout project Gate 通过。
