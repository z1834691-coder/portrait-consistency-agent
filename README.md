# 母版人像一致性 Agent

当前阶段：`Contract v0.4 frozen / Checkpoint 8A + 8B + 8C-1/8C-2 offline Gates passed / RAG P0-A + P0-B + P0-C + governance + optimization dashboards verified / Gold Set v2 public+private aggregate baseline FAIL / two Provider candidates fail-closed / private GitHub package pushed / Streamlit Cloud Private app created / Tencent Web License normal`

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
- 检查点 8B：页面已接入“明确告知 → 用户确认 → 照片/Profile/Gate/scope 校验 → 一次 BeautifyPic 调用 → 脱敏 ProviderRun → 当前会话内预览/下载”。6 个离线执行案例和 fixture Trace 已通过；开发期间未新发起 UI 真实照片调用；8C-1/8C-2 可在会话内对结果复测、生成下一轮子计划并保留父子血缘；
- BeautifyPic：已完成一次历史真实工具调用 Gate；8B 首轮页面执行链只在用户实际勾选/点击并使用授权照片时才可能调用腾讯，绝不自动发送照片；8C-2 在同一首次授权 scope 内由 Agent 受限自动续跑子轮，调用前后写入 preflight/ProviderRun/Verification Trace，scope 改变则停止并重新授权；
- 运营账本：匿名 `product_events` 与本地管理员 Dashboard 已实现，用于会话、建档、意图、工具调用、复测、显式反馈、重传和 WAU/MAU 的脱敏聚合；后续还需真实采集 Profile 建立率、首次成功修图率、7/30 日回访、会话完成率、失败后重传率和明确满意/不满意比例；它不是 Dataset，也不是线上 KPI 结论；
- LLM：DeepSeek V4 Flash 的文本 `IntentFrame` Adapter、显式文字授权、Pydantic Schema 校验和本地模板 fallback 已接入；固定无个人信息文本的真实 live smoke 已返回合法 Schema（2957 ms、1471 tokens），但这不代表图片编辑或多轮 Agent 已验证。
- <span style="color:#C00000"><strong>8C-1/8C-2：已实现结果图本地观察、受限 `VERIFICATION_STRATEGY_SELECT` baseline、逐特征趋势、结构化目标证据、父子子计划/ProviderRun 血缘、三轮上限和点赞/点踩/文字 hash 反馈。首次确认范围仍有效且证据满足时，系统会自动执行并自动复测下一轮；每次触发前后都有脱敏 Trace，超出范围不会调用。</strong></span>
- <span style="color:#C00000"><strong>RAG P0-A / P0-B / P0-C：已实现独立本地 SQLite 权威知识库、metadata 硬过滤、FTS5、local dense、RRF、local reranker、来源依据卡、脱敏 Trace，以及对 8A/8C 的受限 evidence 回接。</strong>当前导入 3 张人工审核的 Tencent Provider Card、拆成 10 条原子规则；P0-B 只从本地缓存读取固定模型 revision，模型缺失时退回 P0-A。P0-C 把结果分为 direct/reference/conflict，`execution_authorized=false`；它不读取照片或用户原话，不调用 LLM/Tencent/API，不生成参数或新的工具权限。另有一个只读本机 RAG 治理 Dashboard，展示脱敏知识/路由/bad-case 聚合；它不是自动 worker、外部/混合复测或“RAG 自动修图”。</span>
- <span style="color:#C00000"><strong>Gold Set v2：已实现独立离线评测器、无答案 public 集（34 dev + 18 challenge）、20 题 holdout 输入包、独立答案键、盲审输入合同和可视化 HTML 报告生成。当前 public deterministic baseline 与私有 holdout aggregate 均已运行且 `FAIL`：公开集的固定分母 Precision@3=47.44%，私有隐藏集 Route=25.00%。这说明当前基线还不具备可宣称的泛化效果。</strong></span>
- <span style="color:#C00000"><strong>Provider 扩展：火山美颜 API V2.0 与腾讯特效 SDK 已建立 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 smoke 入口；两者均未接入 SDK/API、未发送图片、未使用密钥，状态保持 `candidate`/fail-closed。产品决策是火山 V0 暂不购买/接入，当前执行链只用 Tencent。</strong></span>
- <span style="color:#C00000"><strong>RAG failure-pattern：已生成脱敏的公开分层指标、隐藏集聚合错误类型、SOP 与 proposal-only 自校正候选；候选公开回归无指标回退但未推广，project Gate 仍为 `FAIL`。RAG 治理看板现可嵌入公开评测、隐藏聚合和失败分析 HTML，另有只读 RAG 优化看板。</strong></span>
- <span style="color:#C00000"><strong>RAG 生命周期审计：已实现 metadata-only `RagLifecycleAudit`、显式审计脚本、SQLite 审计账本、dense manifest 一致性检查和治理看板入口。当前 3 张审核 Tencent Card/10 条有效规则审计为 `complete`、issue 数为 0、index=`in_sync`；审计不自动发布/改状态/删除/重建索引，RAG 仍只能提议。</strong></span>
- <span style="color:#C00000"><strong>部署包：已补齐 Community Cloud 可直接读取的 `uv.lock` 环境声明、`src/` 入口兼容、云端配置和部署说明，并已推送到私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)。Streamlit Cloud Private App 已创建，URL 为 [`portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`](https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app)；只读探针返回登录跳转。腾讯 Web License 已以纯主机名提交并在控制台显示“正常”（2026-08-30 至 2026-09-13）。仓库发布边界仍排除密钥、照片、SQLite/JSONL、模型缓存、隐藏答案和本机评测报告。</strong></span>

## 重要边界

- V0 不展示 0—100 一致性指数、固定 90 分线或未经校准的接受概率；
- 质量、同人、内容安全、用户意图、参数规划、API 回执和修后验证由不同模块负责；LLM 不看原图、不算视觉数值、不猜参数、不自行授权；
- 图片、Base64、人脸向量、主体锚点、密钥、确认引用和原始文本不会进入 Trace；DeepSeek 远程调用也只会收到经常见 PII 脱敏的最小必要文字和不含不透明 ID 的上下文；失败先走本地模板，不自动转发第二个云 Provider；OpenRouter/跨境默认关闭，ZDR 需另行核验；
- 腾讯结果图只保留在当前浏览器会话内，用户可主动下载；会话结束、服务重启或最多 10 分钟后不可取。结果 Base64 不写 SQLite、JSONL、Trace 或 `storage/results`；8B 每份确认计划只允许一次外部尝试，超时/网络错误也不自动重试；8C 若在计划族内继续，必须新建子 plan/ProviderRun，并以父回执和结果 hash 血缘相连；同一首次确认 scope 内的后续调用由 Agent 自动触发，但每次都必须经过 preflight/idempotency 检查并写 Trace，不能重试同一计划。
- 主体锚点的产品规则已冻结为：独立同意、183 天保存、30/7 天提醒、撤回后立即停用、主存储 24 小时删除/备份 7 天清理；真实 AES-GCM 存储、TTL/delete worker 与密钥管理尚未实现；
- 多脸的后续路线是“检测 → 用户选脸 → 隔离/裁剪 → 编辑 → 回贴 → 复测”。当前完整链路未实现，系统必须要求用户上传单脸或先裁剪；
- 腾讯 IMS ImageModeration Adapter 已完成两条真实 live 证据：一张样本返回 `Block`（`RequestId=21bf408d-929a-46ec-83aa-78f071eff556`），本次明确授权照片返回 `Pass`（`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`）。这只验证了服务、权限、签名、解析和两种路由样例，不代表所有照片都安全；`Block` 样本仍不得进入修图；
- 当前默认仍只在本机运行。部署包可供 Community Cloud 受邀 Beta 使用，但平台容器位于美国且磁盘不保证持久化；没有完成数据出境确认、访问名单、Secrets、费用和删除策略前，不开放真实照片公网测试。

当前产品和工程的共同真相源是 [执行版 PRD](docs/母版人像一致性Agent-执行版PRD.md)。规则见 [PRODUCT_RULES.md](docs/PRODUCT_RULES.md)，合同见 [CONTRACTS.md](docs/CONTRACTS.md)，LLM Prompt 边界见 [AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md)，检查点 7 的输入/输出/案例/Trace 见 [DEEPSEEK_INTENT_GATE.md](docs/DEEPSEEK_INTENT_GATE.md)，RAG 决策与后续 Gate 见 [RAG_DECISION_GATE.md](docs/RAG_DECISION_GATE.md)，failure pattern SOP 见 [RAG_FAILURE_ANALYSIS_SOP.md](docs/RAG_FAILURE_ANALYSIS_SOP.md)，P0-A/P0-B/P0-C 实际实现/Trace 见 [RAG_P0A_RETRIEVAL_GATE.md](docs/RAG_P0A_RETRIEVAL_GATE.md)、[RAG_P0B_HYBRID_RETRIEVAL_GATE.md](docs/RAG_P0B_HYBRID_RETRIEVAL_GATE.md) 与 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](docs/RAG_P0C_ADVISORY_INTEGRATION_GATE.md)，Gold evaluator/盲审约束见 [RAG_GOLD_EVALUATOR.md](docs/RAG_GOLD_EVALUATOR.md)、逐题人工模板见 [RAG_GOLD_SET_V2_HUMAN_REVIEW.md](docs/RAG_GOLD_SET_V2_HUMAN_REVIEW.md)，待人工审阅的 [Gold Set v2](docs/RAG_GOLD_SET_V2_REVIEW.md) 与 [隐藏答案键保管回执](docs/RAG_GOLD_SET_V2_HOLDOUT_CUSTODY.md) 均不进入调参/训练，Provider 候选对比见 [PROVIDER_EXPANSION_RESEARCH.md](docs/PROVIDER_EXPANSION_RESEARCH.md)，决策过程见 [DECISION_LOG.md](docs/DECISION_LOG.md)，逐步证据见 [DEVELOPMENT_PROGRESS.md](docs/DEVELOPMENT_PROGRESS.md)。

## 下一开发 Gate

RAG P0-A/P0-B/P0-C 与只读治理 Dashboard 已完成本地可审计闭环；Gold Set v2 的 public baseline、无答案 holdout 和私有 aggregate 比对也已完成，但当前基线没有通过。Precision C、Holdout A、Safety ID C 已冻结并落地：评测保留固定分母并并行展示覆盖式/返回式 Precision；v2 只作历史诊断；v3 已在工作区外生成 `OWNER_REVIEW_DRAFT`（正式 runtime 仍为空模板）；已知安全事件映射为 `RAG_EVT_*`，未知事件保持 `MANUAL_REVIEW_REQUIRED`。下一步是产品负责人逐题审核 v3 草案，再决定正式 runtime 与一次性盲测；候选 Provider 的 License/隐私/价格/区域/真实 receipt/Gold 准入仍独立推进。P0-C 只提议和留证，不能改变图片执行权限。

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
├── docs/                          # PRD、规则、合同、Prompt、进展、决策、RAG Gate 与 API Gate
├── scripts/                       # 默认不联网；含 8C-2 计划族 fixture smoke
├── src/portrait_consistency_agent/
│   ├── agent/                     # DeepSeek 文本解析 Adapter + 本地模板 fallback
│   ├── core/                      # v0.4 合同、独立 RAG 合同、Policy、本地设置
│   ├── services/                  # 质量门 / Profile / 8A/8B/8C / RAG 检索+advice+评测+失败分析+生命周期审计 / Provider Adapter shells
│   └── storage/                   # 运行账本 SQLite/JSONL + 独立 RAG SQLite/FTS/派生向量索引
├── storage/                       # 本地脱敏 DB（Git 忽略；当前产品不写结果图）
├── logs/                          # 本地 JSONL trace（Git 忽略）
└── tests/                         # 当前 150 个自动化测试（另有 4 条 Pillow 已知弃用警告）
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
uv run python scripts/audit_rag_lifecycle.py
uv run python scripts/evaluate_rag_gold_v2.py --html reports/rag_gold_v2_pending.html
uv run python scripts/smoke_volc_beauty.py
uv run python scripts/smoke_tencent_effect_shell.py
# 只在需要首次下载公开本地模型时显式执行；正常页面/运行不会下载：
uv run python scripts/smoke_rag_p0b.py --allow-model-download
# DeepSeek 已验证；仅在密钥轮换或重新部署后才需要：
uv run python scripts/smoke_deepseek_intent.py --allow-live
```

2026-08-30 当前收尾校验：全量 `pytest` 实际为 `150 passed, 4 warnings`；`ruff format --check`、`ruff check`、`compileall`、public/holdout baseline、私有 aggregate scorer、RAG advisory、RAG lifecycle audit、两个 Provider shell smoke 和 `git diff --check` 均通过。四条 warning 均为既有 Pillow 已知弃用警告。private scorer 只输出聚合结果和错误类型；它不调用 LLM/Provider/网络，也不输出题目、case ID、Gold、答案键路径或图片。当前 RAG project Gate 为 `FAIL`，不得写成通过。

## 2026-08-30 评测治理冻结

Precision 采用 C：固定、覆盖式、返回式三种口径并行；固定口径继续作为历史 Gate，覆盖式/返回式只做诊断。Holdout 采用 A：v2 仅历史聚合，v3 正式 runtime 模板位于 `data/evaluation/rag_gold_v3_holdout_runtime.template.json`，题目/答案草案已在项目工作区外独立生成并待审核。安全事件采用 C：版本化确定性字典 + 产品负责人确认，已知标签映射为 `RAG_EVT_*`，未知标签必须人工复核。相关报告、看板和测试已同步；当前 project Gate 仍 `FAIL`。

不要将 `.env`、真实照片、下载后的结果图片、SQLite 文件或 JSONL 日志提交到 Git。DeepSeek Key 必须从密码管理器直接粘贴到本机 `.env`，不要发送到聊天。外部腾讯首轮调用只能在用户明确同意且使用已授权照片时，以 `--allow-live` 或页面的明确确认触发；8C-2 后继调用若仍在同一首次授权 scope 内，需先通过自动 preflight 并写入 Trace，scope 变化则重新确认。DeepSeek smoke 同样必须显式传 `--allow-live`。

## 2026-08-30 RAG 生命周期审计收口

`scripts/audit_rag_lifecycle.py` 会对审核知识卡的状态、有效期、来源 URI、原子规则数和 dense manifest 做一次 metadata-only 审计，并把 `RagLifecycleAudit` 写入本地脱敏账本、JSON/HTML 和 RAG 治理看板。当前快照为 3 张 Tencent Card、10 条 active 规则、issue 数 0、index=`in_sync`。它不会读照片、来源正文、用户原话、向量、答案键或密钥，也不会联网、调用 LLM/Provider、自动发布、改状态、删除或重建索引；知识变更仍需人工审核后重建并回归。该模块完成的是 RAG 工程治理闭环，不代表 public/holdout project Gate 通过。
