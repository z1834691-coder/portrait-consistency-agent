# 母版人像一致性 Agent

## 2026-09-01 Cloud ImageModeration 页面失败的根因与修复

第一位用户在 Cloud 页面看到 `Tencent ImageModeration request failed`。Cloud 运行日志的稳定异常是 Streamlit 控件重跑时重复写入同一个 `photo_quality_result_id`，SQLite 抛出 `UNIQUE constraint failed`；这不是可以绕过的内容安全结果。代码已改为：同一业务唯一键和相同脱敏事实幂等复用，事实发生变化则以可识别冲突停止，不覆盖旧证据；重复重放也不会重复计入完成类运营事件。页面仍只展示脱敏腾讯 `error_code`/`RequestId`，不自动重试、不放行 `Review/Block`、不保存原图或密钥。

本机用明确授权照片完成的真实 IMS smoke 返回 `status=succeeded`、`Pass`、RequestId=`c95e1359-9ecb-45ac-aa94-3776fbccc0ad`；这证明本机服务链可用，但不代替 Cloud 新版本回执。提交并重建后，请刷新 Private App、重新执行一次内容安全检查；如果仍失败，只回传页面显示的 `error_code` 和 `RequestId`。

当前阶段：`Contract v0.4 frozen / Checkpoint 8A + 8B + 8C-1/8C-2 offline Gates passed / RAG P0-A + P0-B + P0-C + governance + optimization dashboards verified / Gold Set v2 public+private aggregate baseline FAIL / private GitHub package pushed / Streamlit Cloud Private app created / Tencent Web License normal / Effect Web browser smoke succeeded once after Canvas fix; Provider Card remains candidate pending admission evidence`

> **最新状态（2026-09-02）：** Canvas 修复已部署，Tencent Effect Web page 6 已完成一次真实成功 Browser Receipt（`web_receipt_effect_web_4d58ea15a0794370`，2601ms，输出哈希已保存）。Provider Card 仍是 `candidate`；这只证明一次浏览器静态图调用成功，不代表细项五官、批量、供应商留存/区域/费用或主流程准入已经完成。

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
- <span style="color:#C00000"><strong>Gold Set v2/v3：v2 保留为历史诊断；v3 的一次性 answerless 盲测快照仍保留，结果为 Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、hard-safety=PASS、project Gate=`FAIL`。产品负责人随后明确授权一份独立的 V3 validation 副本用于逐题失败诊断和候选优化；这份副本不进入在线 RAG，也不能被当作新的 Holdout 或泛化通过证据。</strong></span>
- <span style="color:#C00000"><strong>Provider 扩展：火山美颜 API V2.0 仍是 candidate shell；腾讯特效 Web 已建立独立 Web Card、浏览器 Adapter、Streamlit page 6、ProviderRun 联合合同和离线 smoke。Cloud page 6 已在 Canvas 修复后取得一次真实成功回执，但 Card 仍为 `candidate`，因为供应商隐私/区域/费用、多样本回归和人工准入尚未完成。两者都不能由 RAG/LLM 自动授权，当前主执行链仍只用已验证的 Tencent BeautifyPic。</strong></span>
- <span style="color:#C00000"><strong>RAG failure-pattern：已生成脱敏的公开分层指标、隐藏集聚合错误类型、SOP 与 proposal-only 自校正候选；候选公开回归无指标回退但未推广，project Gate 仍为 `FAIL`。RAG 治理看板现可嵌入公开评测、隐藏聚合和失败分析 HTML，另有只读 RAG 优化看板。</strong></span>
- <span style="color:#C00000"><strong>RAG 生命周期审计：已实现 metadata-only `RagLifecycleAudit`、显式审计脚本、SQLite 审计账本、dense manifest 一致性检查和治理看板入口。当前 3 张审核 Tencent Card/10 条有效规则审计为 `complete`、issue 数为 0、index=`in_sync`；审计不自动发布/改状态/删除/重建索引，RAG 仍只能提议。</strong></span>
- <span style="color:#C00000"><strong>V3 验证诊断与失败驱动优化：已生成 H01–H36 的逐题结论、根因、SOP、每代查询投影和完整安全 Trace。G0→G5 的最终保守候选把 validation Route 从 30.56% 提升到 100%、Evidence relation 从 23.61% 提升到 97.22%、Recall@5 从 59.72% 提升到 100%；G2 的 100% 因 public regression 退化被拒绝，G3 才保留。固定 Precision/project Gate 仍 `FAIL`，hard-safety `PASS`，G4/G5 无增益，任何候选未 promotion；详见 `reports/rag_v3_validation_diagnostics_v1.html`。</strong></span>
- <span style="color:#C00000"><strong>部署包：已补齐 Community Cloud 可直接读取的 `uv.lock` 环境声明、`src/` 入口兼容、云端配置和部署说明，并已推送到私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)。Streamlit Cloud Private App 已创建，URL 为 [`portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`](https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app)，页面已在浏览器打开待第一位用户操作；腾讯 Web License 已以纯主机名提交并在控制台显示“正常”（2026-08-30 至 2026-09-13）。仓库发布边界仍排除密钥、照片、SQLite/JSONL、模型缓存、隐藏答案和本机评测报告。</strong></span>
- <span style="color:#C00000"><strong>Cloud 凭据入口：本机 `.env` 不会随部署进入 Cloud；要触发真实腾讯安全/同人/修图请求，必须在该 App 的 Settings → Secrets 以根级变量配置 `TENCENT_SECRET_ID` 与 `TENCENT_SECRET_KEY`，保存后重启。缺少任一项时系统 fail-closed，不发送照片。</strong></span>
- <span style="color:#C00000"><strong>Cloud 腾讯错误回执：如果 ImageModeration 已读到密钥但请求失败，页面现在会安全显示腾讯 `error_code` 与 `RequestId`，并将同样的非敏感字段写入脱敏 Trace；不会显示原图、密钥或腾讯原始错误全文。没有 `RequestId` 时明确显示“未返回”，不能把失败误写成内容安全通过。</strong></span>
- <span style="color:#C00000"><strong>视觉交互设计已冻结、尚未实现：</strong>产品采用“对齐首页／Agent 对话子页面 + 母版档案 + 结果记录”的三空间信息分组，桌面壳固定为“全局导航 + 项目/母版上下文 + 中央对齐工作区 + 右侧 Agent 对话”轻量四区；Agent 只在澄清、真实进度、边界与结果时用人话发声，参数/回执/脱敏执行记录位于第二层。正式视觉采用 Tweakcn Party Rock 原始 Light/Dark token 与苹方（PingFang SC）；紫色与米白共同主导面积、紫色在关键视觉块中略强，黑色承担侧栏/暗流底/文字/分隔等结构，珊瑚红、暗红及其他颜色只作少量语义点缀。活跃关键帧已收敛为 E01 入口与 E02 Agent 对话；关键帧 Prompt 与可编辑 HTML/SVG 见 [`docs/FRONTEND_UI_KEYFRAME_PROMPT.md`](docs/FRONTEND_UI_KEYFRAME_PROMPT.md) 和 [`design/keyframes/party-rock-pingfang/`](design/keyframes/party-rock-pingfang/)。样张不等于已部署 UI，不改变照片权限、工具调用或数据边界。</span>
- <span style="color:#C00000"><strong>第一位用户 UX 反馈（待 UI Gate）：</strong>上传等待过长；首屏不应展示脱敏 JSON；A/B/C 检查点和按钮过多；自然语言入口被 GUI 挤压；视觉偏工程文档。当前只记录为事实反馈，尚未擅自改 UI 或删除必要权限门。</span>
- <span style="color:#C00000"><strong>Web 回执关联与结果捕获修复（2026-09-02）：</strong>修复 Streamlit 重跑导致的 `request_ref` 错位，并修复 SDK Canvas 不可调整尺寸导致的结果捕获错误；同一输入/参数代次复用请求引用，签名可刷新，旧代次回执安全忽略。该修复通过 Web 专项回归，且 page 6 已取得一次真实成功回执；Card 仍为 `candidate`，不代表正式准入。</span>
- <span style="color:#C00000"><strong>Tencent Web → Meta-Agent 控制面（2026-09-02）：</strong>新增只读 `ToolRegistry` 与结构化 `ToolProposal`，将 verified BeautifyPic baseline 和 candidate Web Card 放入同一工具目录；Meta-Agent 能提出 WebARImage 候选、列出准入检查并提供 baseline fallback，但 `execution_authorized=false`，不读图片、不发网络、不创建 ProviderRun。该切片已由专项测试和离线 smoke 验证，不等于 Web Card promotion 或主流程结果复测已完成。</span>

本轮新增的执行 Prompt 与探索树见 [`docs/TENCENT_EFFECT_META_AGENT_INTEGRATION_PROMPT.md`](docs/TENCENT_EFFECT_META_AGENT_INTEGRATION_PROMPT.md) 和 [`docs/TENCENT_EFFECT_META_AGENT_EXPLORATION_TREE.md`](docs/TENCENT_EFFECT_META_AGENT_EXPLORATION_TREE.md)。当前全量回归以本轮最终命令输出为准：新增 Meta-Agent 代码后已通过全量测试、Ruff、format、compileall 与 `git diff --check`；Web Card 仍 `candidate`。

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
当前产品和工程的共同真相源是 [执行版 PRD](docs/母版人像一致性Agent-执行版PRD.md)。前端和交互执行规格见 [前端与交互设计需求文档](docs/前端与交互设计需求文档.md)。规则见 [PRODUCT_RULES.md](docs/PRODUCT_RULES.md)，合同见 [CONTRACTS.md](docs/CONTRACTS.md)，LLM Prompt 边界见 [AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md)，腾讯特效 Web 适配器与准入见 [TENCENT_EFFECT_WEB_ADAPTER.md](docs/TENCENT_EFFECT_WEB_ADAPTER.md)，检查点 7 的输入/输出/案例/Trace 见 [DEEPSEEK_INTENT_GATE.md](docs/DEEPSEEK_INTENT_GATE.md)，RAG 决策与后续 Gate 见 [RAG_DECISION_GATE.md](docs/RAG_DECISION_GATE.md)，failure pattern SOP 见 [RAG_FAILURE_ANALYSIS_SOP.md](docs/RAG_FAILURE_ANALYSIS_SOP.md)，P0-A/P0-B/P0-C 实际实现/Trace 见 [RAG_P0A_RETRIEVAL_GATE.md](docs/RAG_P0A_RETRIEVAL_GATE.md)、[RAG_P0B_HYBRID_RETRIEVAL_GATE.md](docs/RAG_P0B_HYBRID_RETRIEVAL_GATE.md) 与 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](docs/RAG_P0C_ADVISORY_INTEGRATION_GATE.md)，Gold evaluator/盲审约束见 [RAG_GOLD_EVALUATOR.md](docs/RAG_GOLD_EVALUATOR.md)、逐题人工模板见 [RAG_GOLD_SET_V2_HUMAN_REVIEW.md](docs/RAG_GOLD_SET_V2_HUMAN_REVIEW.md)，v3 保管与一次性运行边界见 [RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md](docs/RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md)，第一位用户操作见 [FIRST_USER_E2E_TEST.md](docs/FIRST_USER_E2E_TEST.md)，中期快照见 [MIDTERM_STATUS_2026-09-01.md](docs/MIDTERM_STATUS_2026-09-01.md)，Provider 候选对比见 [PROVIDER_EXPANSION_RESEARCH.md](docs/PROVIDER_EXPANSION_RESEARCH.md)，决策过程见 [DECISION_LOG.md](docs/DECISION_LOG.md)，逐步证据见 [DEVELOPMENT_PROGRESS.md](docs/DEVELOPMENT_PROGRESS.md)。

## 下一开发 Gate

RAG P0-A/P0-B/P0-C 与只读治理 Dashboard 已完成本地可审计闭环；Gold Set v2 的 public baseline、无答案 holdout 和私有 aggregate 比对也已完成，但当前基线没有通过。Precision C、Holdout A、Safety ID C 已冻结并落地：评测保留固定分母并并行展示覆盖式/返回式 Precision；v2 只作历史诊断；v3 已在工作区外完成产品负责人审核并完成一次正式 answerless 盲测，质量 project Gate=`FAIL`、hard-safety=`PASS`。已知安全事件映射为 `RAG_EVT_*`，未知事件保持 `MANUAL_REVIEW_REQUIRED`。当前真实用户流程已到达 8A 的 `uncertain` 确认边界；Cloud 重建后完成一次确认即可继续，尚无真实 ProviderRun/VerificationResult。随后再收集体验反馈并进入 UI Gate；候选 Provider 的 License/隐私/价格/区域/真实 receipt/Gold 准入仍独立推进。P0-C 只提议和留证，不能改变图片执行权限。

## 2026-08-30 RAG 优化闭环（当前真实状态）

failure analyzer 已把“公开指标、隐藏聚合、错误模式、候选修正、回归差值、SOP”串成可重放链路。当前候选 `rag-correction-candidate-v0.1` 只做经审核的同义词归一化，公开回归 `regression_gate=PASS`，但 project Gate 仍为 `FAIL`，所以没有写入现役检索或权限逻辑。报告和 Dashboard 都是本机只读治理工具，不是生产监控、自动修复器、训练 Dataset 或图片编辑器。

候选 Provider 当前状态为：火山 V2 `not_run`；腾讯特效 Web `candidate / browser-smoke-failed-auth-config`。Cloud page 6 已取得真实失败 Browser Receipt（未生成输出图）；原 `request_ref` 错位已修复，但 SDK 鉴权码 100 暴露出 `TENCENT_EFFECT_APP_ID` 需要改为腾讯账号数字 APPID，不能使用绑定域名。修正 Secret 后再运行一次官方示例图；在成功回执及准入清单完成前，不能声称 Web 图片、细项五官或批量已验证。两条路线均须按 Card → Adapter → 权限/预算/隐私 → live receipt → Gold 回归 → 产品负责人冻结的顺序推进；只有当前 Tencent BeautifyPic/IMS 路径有既有真实回执，火山 V0 仍不购买/接入。

## 当前项目树

```text
portrait-consistency-agent/
├── app.py                         # 本机 Streamlit：质量/安全/同人/Profile/IntentFrame/8A/8B/8C 复测、计划族与反馈
├── pages/1_运营数据看板.py          # 仅本机管理员的脱敏运营 Dashboard
├── pages/2_RAG知识库与检索.py       # 本地 RAG P0-A 依据卡与 Trace 演示页
├── pages/3_RAG本地混合检索.py       # 本地 RAG P0-B FTS+dense+rerank 演示页
├── pages/4_RAG治理看板.py            # 本机管理员：脱敏知识/路由/bad-case 聚合，不读照片或原话
├── pages/5_RAG优化看板.py             # 本机管理员：failure pattern、候选差值与 SOP
├── pages/6_腾讯特效Web试验.py          # 独立 Tencent Effect Web 静态图准入/浏览器 smoke
├── data/provider_cards/           # 版本化 Provider Card（含已审核 Tencent 与 candidate 扩展）
├── data/evaluation/               # Gold Set v2 + v3 Holdout 模板/安全事件目录（答案键与运行包分离）
├── reports/                        # 本次无答案评测的 JSON/Markdown/HTML 审计产物
├── docs/                          # PRD、规则、合同、Prompt、进展、决策、RAG Gate、API Gate 与第一位用户测试说明
├── scripts/                       # 默认不联网；含 8C-2 计划族 fixture smoke
├── src/portrait_consistency_agent/
│   ├── agent/                     # DeepSeek 文本解析 Adapter + 本地模板 fallback
│   ├── core/                      # v0.4 合同、独立 RAG 合同、Policy、本地设置
│   ├── services/                  # 质量门 / Profile / 8A/8B/8C / RAG 检索+advice+评测+失败分析+生命周期审计 / Provider Adapters
│   └── storage/                   # 运行账本 SQLite/JSONL + 独立 RAG SQLite/FTS/派生向量索引
├── storage/                       # 本地脱敏 DB（Git 忽略；当前产品不写结果图）

## 2026-09-01 RAG 失败驱动优化 v2（当前真实状态）

上一轮 `rag_optimization_loop_v1` 的 V0/V1/V2 Composite 都是 `0.947436`，因为候选只改了已经生成的 Prediction，实际没有改变输入事实；这被确认是“修错层”，不是指标失灵。本轮新增 `rag_query_compiler_candidate.py`，在自然语言进入 `RagQuery`、P0-B 检索之前做受审核的同义词归一化、动作/信息请求拆分、安全/生命周期优先级和多意图 evidence union。

当前失败驱动 Loop 使用 28 道 `owner_review_required` 题（16 dev + 12 challenge）：V0 Composite=`0.355614`；V1=`0.403233`（+0.047619，改变 2 条预测）；V2=`0.947619`（+0.544386，改变 22 条预测）；V3/V4 各改变 0 条预测，连续两代增益 `<0.01` 后停止。V0 failure code 主要为 route 24、relation 23、set 18、rank 10；稀疏 Gold 分母提示 28 条单独统计。所有候选无网络/LLM/Provider/hidden-answer 访问，active baseline 未改变，anti-overfit=`PASS`。

这是开发集工程增益，不是产品质量通过：public regression 的固定 Precision@3=`47.44%`、project Gate=`FAIL`，RAG 仍 advisory-only。新题和 annotations 需产品负责人审核；之后必须建立独立 Holdout v4，才能验证泛化并决定是否 promotion。报告与可视化在 `reports/rag_failure_driven_loop_v1.json/.html` 和 page 5。

### 本轮最终工程校验

当前全量 `.venv/bin/pytest -q` 为 `196 passed, 4 warnings`；Ruff check、`ruff format --check`、compileall、`git diff --check`、RAG failure-driven loop、过程监督、P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 均通过。4 条 warning 是既有 Pillow 弃用提示。这个 QA 结果证明代码和治理产物一致，不改变 public/project Gate=`FAIL`，也不把候选升级为 active。
├── logs/                          # 本地 JSONL trace（Git 忽略）
└── tests/                         # 当前 196 个自动化测试（另有 4 条 Pillow 已知弃用警告）
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
# Web Effect 适配器离线合同 smoke（不联网、不读照片、不读密钥）
uv run python scripts/smoke_tencent_effect_web.py
# 只在需要首次下载公开本地模型时显式执行；正常页面/运行不会下载：
uv run python scripts/smoke_rag_p0b.py --allow-model-download
# DeepSeek 已验证；仅在密钥轮换或重新部署后才需要：
uv run python scripts/smoke_deepseek_intent.py --allow-live
```

2026-09-01 历史收尾校验（幂等修复前）：全量 `pytest` 为 `160 passed, 4 warnings`；该快照保留用于时间线。此前 `180`/`189`/`193` 条记录也保留为历史快照，当前 QA 以本轮 `196 passed, 4 warnings` 为准。v3 private scorer 只输出聚合结果和安全事实；它不调用 LLM/Provider/网络，也不输出题目、case ID、Gold、答案键路径或图片。当前 RAG project quality Gate 为 `FAIL`，不得写成通过；真实 UI 照片流程尚未由 Codex 代跑。

## 2026-08-30 评测治理冻结

Precision 采用 C：固定、覆盖式、返回式三种口径并行；固定口径继续作为历史 Gate，覆盖式/返回式只做诊断。Holdout 采用 A：v2 仅作历史 aggregate，v3 已在工作区外完成产品负责人审核并完成一次正式 answerless 盲测。安全事件采用 C：版本化确定性字典 + 产品负责人确认，已知标签映射为 `RAG_EVT_*`，未知标签必须人工复核。相关报告、看板和测试已同步；v3 quality Gate 仍 `FAIL`。

不要将 `.env`、真实照片、下载后的结果图片、SQLite 文件或 JSONL 日志提交到 Git。DeepSeek Key 必须从密码管理器直接粘贴到本机 `.env`，不要发送到聊天。外部腾讯首轮调用只能在用户明确同意且使用已授权照片时，以 `--allow-live` 或页面的明确确认触发；8C-2 后继调用若仍在同一首次授权 scope 内，需先通过自动 preflight 并写入 Trace，scope 变化则重新确认。DeepSeek smoke 同样必须显式传 `--allow-live`。

## 2026-09-01 RAG 自动优化 Loop（历史错误层快照）

早期版本有一条 proposal-only 的失败模式自校正循环：读取 public 52 题和公开 annotations，逐题生成错误代码，再做后处理候选。v3 Holdout 只提供私有 aggregate 上下文，逐题答案没有读取，也没有重复正式运行。该节保留作为历史快照；当前以“失败驱动优化 v2”结果为准。

历史结果：V0/V1/V2 Composite 均为 `0.947436`，候选增益均为 `0.0`；这是因为候选只改已经生成的 Prediction，实际 `changed_prediction_count=0`，属于修错层。该历史 Gate 仍为 `FAIL`，不代表当前候选结果。

优化产物：[RAG_OPTIMIZATION_PROGRESS.md](docs/RAG_OPTIMIZATION_PROGRESS.md)、[RAG_OPTIMIZATION_RUBRIC.md](docs/RAG_OPTIMIZATION_RUBRIC.md)、[RAG_FAILURE_CASE_REVIEW_V2.md](docs/RAG_FAILURE_CASE_REVIEW_V2.md)、`reports/rag_failure_driven_loop_v1.json/.html`、Streamlit page 5。Dashboard 现在同时显示 V0/最终候选逐题状态，但不提供 v3 hidden 结论。它是只读可视化治理工具，不是自动训练、自动发布或生产监控；如要再次正式验收，必须新建独立 Holdout v4。

## 2026-08-30 RAG 生命周期审计收口

`scripts/audit_rag_lifecycle.py` 会对审核知识卡的状态、有效期、来源 URI、原子规则数和 dense manifest 做一次 metadata-only 审计，并把 `RagLifecycleAudit` 写入本地脱敏账本、JSON/HTML 和 RAG 治理看板。当前快照为 3 张 Tencent Card、10 条 active 规则、issue 数 0、index=`in_sync`。它不会读照片、来源正文、用户原话、向量、答案键或密钥，也不会联网、调用 LLM/Provider、自动发布、改状态、删除或重建索引；知识变更仍需人工审核后重建并回归。该模块完成的是 RAG 工程治理闭环，不代表 public/holdout project Gate 通过。

## 2026-09-02 V3 validation 逐题诊断与优化（当前最新）

原始 V3 answerless Holdout-A 快照仍保留；产品负责人明确授权后，系统从审核材料派生出 `validation` 副本，用于 H01–H36 逐题失败模式分析。报告 [JSON](reports/rag_v3_validation_diagnostics_v1.json) / [HTML](reports/rag_v3_validation_diagnostics_v1.html) 现在包含每题 Gold、Prediction、根因、SOP、查询投影、检索步骤和完整安全 Trace，page 5 可只读查看。

G0→G5 的最终保守候选把 validation Route 从 30.56% 提升到 100%、Evidence relation 从 23.61% 提升到 97.22%、Recall@5 从 59.72% 提升到 100%；G2 的 100% 因 public regression 退化拒绝，G3 保住公开基线，G4/G5 无新增增益。固定 Precision/project Gate 仍 `FAIL`、hard-safety `PASS`，active baseline 未改变，RAG 仍 proposal-only。验证副本不是新的 Holdout，推广前必须建立不重叠的 V4 Holdout。
## 2026-09-02 V4 Holdout 与 RAG 当前边界

V4 是与 V3 不重叠的 48 题独立 Holdout。项目已完成一次 answerless baseline 盲测并封存预测/Trace；正式结果为 Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、MRR=81.25%、nDCG@5=63.22%，hard-safety=0/48（PASS），project quality Gate=`FAIL`。因此不能在 README、简历或演示中写“RAG 已通过/已产品化”。

负责人授权后，离线诊断器在同一批题目上完成 G0–G5 失败分析和查询编译候选；语义诊断指标达到 100%，但这是解冻 validation，不是新的泛化成绩。候选保持 `proposal_only=true`，`active_baseline_changed=false`，不读照片/向量、不调用网络/LLM/Provider，也不生成图片参数或权限。固定 Precision@3 的稀疏 Gold 口径继续作为项目 Gate，effective/returned 仅用于解释。

可查看 [V4 Holdout 记录](docs/RAG_V4_HOLDOUT.md)、[盲测聚合](reports/rag_v4_holdout_blind_aggregate.html)、[逐题诊断](reports/rag_v4_validation_diagnostics_v1.html) 和 page 5「RAG 优化看板」。RAG 仍是审核知识范围内的受限参谋，不是自动发布、自动训练或图片执行系统；任何 promotion 需要新的、未参与诊断的 Holdout 和完整准入证据。

本轮最终工程校验（历史 V4 诊断快照）：`.venv/bin/pytest -q`=`189 passed, 4 warnings`；V4 专项测试=`8 passed`；Ruff check/format、compileall、`git diff --check` 和 V4 diagnostics runner 均通过。当前最新过程监督后的 QA 以文末 `196 passed, 4 warnings` 为准。4 条 warning 是既有 Pillow 弃用提示。该工程回执不等于 RAG 质量 Gate 通过。

腾讯特效 Web 的最新明确重试仍为失败：回执 `web_receipt_effect_web_3a3c71bec3f24557`、SDK 错误码 `100`/规范化码 `20001001`、耗时 628ms、无输出图；Card 保持 `candidate`。这不是 RAG 或主链 Provider 的成功证据，不能在演示中宣称 Web 细项已接入。

最新完整流程重试将耗时更新为 `10360ms`；SDK 仍返回 `100/20001001`，没有输出图。稳定回执引用是同一
请求代次的设计，本次为新的明确点击；Web Card 仍为 `candidate`，不得写成已接入或已验证。

前端结果捕获曾出现 Canvas 生命周期错误：SDK 输出 Canvas 在初始化后不可再次调整尺寸。现已改为使用独立结果 Canvas 写入 `ImageData`，避免 `Cannot resize canvas after call to transfer...`。该修复不代表 Web Provider 已通过鉴权或准入，仍需以新的 Cloud smoke 成功回执为准。

## 2026-09-02 RAG 低成功率反思审计（当前边界）

<span style="color:#C00000"><strong>当前结论：</strong>V4 低分首先来自自然语言→结构化查询的上游边界和评测事实混合，而不是可以直接归因于 P0-B 向量算法。V4 48 题中只有 8 题真正留下检索 Trace，40 题在检索前结束；知识库当前为 3 张审核 Card/10 条有效规则。fixed Precision@3 在 V4 Gold 结构下理论最高约为 0.513889，现行 0.80 门槛在该结构下不可达；Route/Relation 的低分仍是真实问题，二者不能混为一谈。</strong></span>

本轮新增只读反思审计 Prompt、Markdown 解释、机器 JSON/HTML 报告和 4 条审计测试。审计不读取新的隐藏答案、不调用网络/LLM/Provider、不改 active baseline；RAG 继续 `proposal-only`。下一步先拆两条评测轨道（自然语言→结构化查询/路由；结构化查询→真实 chunk 召回/排序/关系），补齐需要计入 RAG 的 Policy/Rule Card，并用 10–15 道公开 smoke 验证完整 Trace；在这道 Gate 前不建立新 Holdout、不推广候选。

可复核入口：[RAG 低成功率反思审计说明](docs/RAG_LOW_SUCCESS_REFLECTION_AUDIT.md)、[可复用 Prompt](docs/RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md)、[JSON](reports/rag_low_success_reflection_audit.json)、[HTML 可视化报告](reports/rag_low_success_reflection_audit.html)。运行命令：

```bash
uv run python scripts/audit_rag_low_success.py
```

## 2026-09-02｜公平评测过程监督（当前）

反思审计后，评测被拆成两条轨道：一条看自然语言有没有被整理成结构化查询，另一条只看真实知识块有没有被召回、排序和正确分类。新增独立过程监督考官，先检查题目是否一题不漏、答案和上游标签是否没有泄露、每题是否完整走过 RAG，以及最终结果是否真的来自检索回执。

本轮使用已有 V3 validation copy 和 V4 holdout runtime 做无答案过程重放，不增加新题、不读取答案、不调用网络/LLM/Provider。新版重放结果为 V3 `36/36`、V4 `48/48` 均有完整检索 Trace；其中 V3 `5` 题、V4 `8` 题能被当前编译器直接理解，其余明确标记为“理解未知但继续检索”，不是伪装成成功。旧 V4 正式快照仍因缺少检索阶段且存在 projection 注入而保持历史 FAIL，不能被补写或改名为通过。

过程报告：[公平评测过程监督](reports/rag_fair_process_audit_v1.html)；可复用规则：[RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md](docs/RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md)。新运行过程门通过只说明考试流程完整，不说明 RAG 内容正确；新运行可以进入单独 Gold 验证，但历史 V4 快照质量继续锁定，RAG 仍 `proposal-only`，active baseline 未改变。脱敏运行包见 `reports/rag_fair_v3_answerless_*.json` 与 `reports/rag_fair_v4_answerless_*.json`。

本轮新增过程考官和脱敏运行包后，全量 `.venv/bin/pytest -q` 为 `196 passed, 4 warnings`；`ruff check`、`ruff format --check`、compileall、`git diff --check` 和公平评测脚本均通过。4 条 warning 仍为既有 Pillow 弃用提示；工程通过不等于 RAG 质量或产品化通过。
