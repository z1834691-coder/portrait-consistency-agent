# 本地运行壳与 Trace

## 当前可运行内容

`app.py` 是一个只监听本机的 Streamlit 壳。它可以：

- 创建匿名本地 session；
- 在浏览器内存中预览两张上传图片；
- 将用户本轮文字解析为 `IntentFrame`：用户勾选文字发送同意且本机存在 DeepSeek Key 时调用 DeepSeek；否则明确走本地 `template_fallback`；
- 将 session、六合同脱敏投影和事件写入 SQLite/JSONL；
- 在页面展示脱敏 trace。
- 在完成质量/安全/同人门和 IntentFrame 后，页面可生成检查点 8A 的逐特征差异诊断与 `EditPlan` 草案；用户阅读告知、勾选并点击确认后，检查点 8B 会重新校验照片/Profile/Gate/scope/期限并且只调用 Tencent BeautifyPic 一次，保存脱敏 ProviderRun；结果图仅在当前浏览器会话内预览/下载。
- 检查点 8C-1/8C-2 可在会话内重新观察结果图、生成 `VerificationResult`、在证据/首次确认范围都满足时生成父子血缘子计划并自动以上一结果图发起下一轮调用；每次调用前后写入自动触发/结果 Trace，页面在最终停止或达标后接收点赞、点踩、文字 hash 反馈并支持计划族硬停止。
- 在 `pages/1_运营数据看板.py` 展示本地管理员的脱敏运营聚合：会话、建档、意图、工具成功、复测、显式反馈、重传和 WAU/MAU；它不是用户研究结论或训练 Dataset。
- 在 `pages/2_RAG知识库与检索.py` 演示 RAG P0-A 的本地知识查询：已审核的能力/限制资料先经 metadata 过滤，再做 SQLite FTS5 检索，页面只展示紧凑依据卡和脱敏 Trace；它不读取上传照片、不调用 LLM/Tencent，也不生成/执行修图参数。
- 在 `pages/3_RAG本地混合检索.py` 演示 RAG P0-B：在同一份审核知识上合并 FTS 与本地语义候选、RRF 和本地 reranker；页面只使用固定本地缓存模型，若权重缺失就明确显示 P0-A 稀疏回退，不下载模型、不读用户图片或原话。
- 在 `pages/4_RAG治理看板.py` 展示本机管理员的 RAG 治理视图：审核知识卡/原子规则、生命周期、检索/建议路由、bad case、复审提醒、派生向量索引和最近脱敏记录，并嵌入三份 allow-listed 脱敏 HTML 报告。它只读独立知识账本，不读照片、原话、知识全文、向量、密钥或 Provider 图片请求；不是自动 worker、Gold 指标计算器或生产管理员后台。
- 8A 生成计划前和 8C 策略建议前会调用 P0-C：它将检索结果分为 direct/reference/conflict，留下紧凑依据与脱敏 bad case；`execution_authorized=false`，所以不会新增图片调用、参数或 external/hybrid 复测。

## 当前刻意不做的内容

- 不把图片写入 SQLite、JSONL 或 Git；
- Streamlit 页面已接入检查点 6 的本地质量门，并提供需要用户明确勾选同意后才执行的 Tencent ImageModeration、CompareFace 和 Profile v0 按钮；BeautifyPic 真实调用已成功一次，CompareFace 已真实 smoke 成功一次；ImageModeration 已真实返回一条 `Block` 决定，因此拒绝路径不能写成审核通过，也不会进入编辑；
- 页面不计算母版一致性总分或接受概率。8B 已接入取消、改口使旧计划失效、明确确认和单次执行；8C-1/8C-2 已接入会话内结果观察、逐特征趋势、受限策略提议、父子计划续跑、反馈控件和硬停止。完整跨会话多轮状态恢复、external/hybrid 复测、LLM 自由策略和批量模式尚未接入。DeepSeek 已完成固定文本的单轮真实 `IntentFrame` 解析与一个候选澄清问题；质量门、Profile v0、CompareFace、IMS 的拒绝/允许样例、8A 规划器、8B 确认 Gate 和 8C-1/8C-2 可以在页面和 Python 服务层运行。
- 页面只展示照片格式、尺寸、人脸数量、定性质量状态和失败原因；质量/可编辑性内部置信度、CompareFace 原始分和隐藏思维链不会展示；P0-C 只注入带版本的审核工具 evidence，不把未审核文本或原始图片送入检索/LLM，也不改变执行权限；RAG 治理页同样只显示脱敏聚合，不能作为图片/用户数据浏览器；
- `AGENT_PROMPTS.md` 的 DeepSeek/text-only/fallback 策略已落地；页面只会发送本轮经常见 PII 脱敏的文字和最小上下文，不发照片、向量、锚点、密钥、原始 Trace 或不透明 ID。合同已升级为 `v0.4`；页面已有 `EditPlan` 草案、确认后的单次图片执行 Gate 和 8C-1/8C-2 `VerificationResult`/计划族/反馈 UI；RAG P0-A/P0-B/P0-C 有本地检索与受限 advice 输入，但不构成自由动态策略。完整 ReAct 编排、external/hybrid 复测、跨会话恢复和新 Provider 准入仍待后续 Gate；
- 当前本地运行不部署公网；后续受邀 Streamlit URL 只作为小范围测试入口，不等于开放公网，也不代表用户自动授权执行修图。平台、密码、地区、费用和服务器设备尚未决定。

## 数据位置

| 数据 | 默认位置 | Git 状态 |
|---|---|---|
| SQLite session/六合同脱敏投影/匿名运营事件 | `storage/demo.sqlite3` | 忽略 |
| RAG 审核知识、FTS 索引、advisory/bad-case 脱敏回执 | `storage/knowledge.sqlite3` | 忽略；独立于用户运行账本 |
| RAG P0-B 可重建 dense 索引 | `storage/knowledge_vectors.sqlite3` | 忽略；仅审核知识派生的向量、hash 和索引 manifest，不是权威知识源 |
| RAG P0-B 本地模型缓存 | `storage/model_cache/` | 忽略；固定 revision 的公开权重；正常页面/产品任务不下载 |
| JSONL trace | `logs/events.jsonl` | 忽略 |
| 腾讯结果图（当前产品） | 当前 Streamlit 会话内存，最多 10 分钟 | 不持久化 |
| 历史 BeautifyPic smoke 结果 | `storage/results/` | 忽略；产生于 8B 会话内结果规则前，仅保留为历史 Gate 证据 |

Trace 会红删密钥、确认引用、主体锚点、Base64 图片、原图/input artifact payload 和签名 URL。上传文件名、原始文本和图片内容不写入 trace；检查点 7 增加解析路径、是否联网、模型/Prompt 版本、耗时、token、Schema 结果、fallback 原因和脱敏类别，检查点 8A 增加局部测量、映射策略、降级原因和待确认计划状态，8B 增加确认期限/允许部位、scope 校验结果、单次执行、ProviderRun 和会话内结果生命周期，8C-1 增加结果观察、策略提议、before/after gap、趋势和路由，8C-2 增加父子 plan/run/hash 血缘、后继参数依据和文字反馈 hash。RAG P0-A/P0-B/P0-C 的独立 Trace 只记录结构化任务槽位、过滤/淘汰原因、来源/模型/索引版本、候选数量、排名、fallback、direct/reference/conflict、advisory route、bad-case 诊断和耗时，不包含照片、原话、LLM 或 Provider 回执。SQLite 迁移 `contract_v0_2_tables` 保留六类业务合同表，`contract_v0_3_analytics_lifecycle` 增加匿名 user ID 与 `product_events`，8B 增加 ProviderRun 本地 idempotency key，8C 增加 `contract_v0_4_verification_observation` 版本标记；页面能写入质量结果、Profile、安全/同人事件、Intent、EditPlan、ProviderRun、VerificationResult 和脱敏反馈事件，不写结果图。

## 启动与验证

```bash
make run
# 或
./start.sh
# 仅运行 8A 离线规划 Trace（不读真实照片、不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_edit_planner.py
# 仅运行 8B 离线确认/执行 Trace（Fake Provider，不读真实照片、不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_execution_8b.py
# 仅运行 8C-1 离线复测与策略提议 Trace（fixture，不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_verification_8c.py
# 仅运行 8C-2 父子计划/反馈 Trace（fixture，不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_plan_family_8c2.py
# 仅运行 RAG P0-A 本地 SQLite/FTS Trace（不读照片、不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_p0a.py
# 仅运行 RAG P0-B 本地混合检索 Trace（只读本地模型缓存，不读照片、不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_p0b.py
# 仅运行 RAG P0-C evidence 回接 Trace（只读本地模型缓存，不读照片、不联网）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_advisory.py
```

浏览器打开 `http://127.0.0.1:8501`。关闭终端即可停止本地服务；这不等同于删除本地 trace，删除/TTL 将在后续隐私检查点实现。

`.streamlit/config.toml` 关闭匿名使用统计，并保留 CORS/XSRF 保护；本地 `make run` 显式绑定到 `127.0.0.1`。受邀 Streamlit 部署需额外配置访问控制、Secrets、删除策略、费用上限和数据出境边界，详见 [部署说明](STREAMLIT_DEPLOYMENT.md)。Cloud 构建默认使用轻量 `uv.lock` 依赖；本地 BGE 权重需显式 `uv sync --all-groups --extra rag-local`。

## 2026-08-30 当前新增的离线入口

Gold Set v2 评测器与两个 Provider candidate shell 已加入本地运行壳，但不会改变主图片链路：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/evaluate_rag_gold_v2.py \
  --output reports/rag_gold_v2_pending.json \
  --markdown reports/rag_gold_v2_pending.md \
  --html reports/rag_gold_v2_pending.html
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_volc_beauty.py
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_tencent_effect_shell.py
```

上述命令如果不传入 predictions，会故意生成 `pending` 的空评测报告；这只表示“没有输入预测”，不代表当前实际基线状态。当前已生成的真实脱敏报告见 `reports/rag_gold_v2_baseline_evaluation.*`（public 52 题）和 `reports/rag_gold_v2_holdout_private_aggregate.*`（holdout 20 题聚合），两者均为 `FAIL`，且私有 hard-safety 仍为 `MANUAL_REVIEW_REQUIRED`。候选 smoke 为 fail-closed 且 `network_call=not_attempted`；它们不会读用户照片、调用 LLM/Tencent/火山或创建图片 `ProviderRun`。

## 2026-08-30｜Failure Pattern 与两个 RAG Dashboard

生成脱敏失败分析（不会读私有答案键）：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/analyze_rag_failures.py
```

默认输出：`reports/rag_failure_patterns_v1.json` 与 `reports/rag_failure_patterns_v1.html`。它会记录公开集分层指标、隐藏集聚合错误类型、指标稀疏诊断、proposal-only 候选差值和六步 SOP；候选在临时 SQLite/索引中运行，不改变现役 baseline。

启动本机看板：

```bash
make run
```

在 Streamlit 左侧打开“RAG治理看板”可查看三份 allow-listed HTML（公开评测、隐藏聚合、失败分析）；打开“RAG优化看板”可查看错误类型、候选回归差值和 SOP。两个页面均为只读管理员原型，不读答案键、照片、人脸向量、原始用户文本或密钥，也不提供应用候选或调用 Provider 的按钮。
## 2026-08-30 评测治理当前状态

Precision C、Holdout A、Safety ID C 已实现：public 报告同时显示固定/覆盖式/返回式 Precision；v2 hidden 只作历史 aggregate，v3 只创建了 answerless 模板；已知安全标签可映射为 `RAG_EVT_*`，未知标签保持人工复核。重跑 public/failure analyzer 时必须显式提供 predictions；不能用空 pending 报告替代正式结果。

## 2026-08-30｜RAG lifecycle audit

新增本地命令：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/audit_rag_lifecycle.py
```

它只审计知识卡元数据和派生 dense manifest，输出 `reports/rag_lifecycle_audit.json/.html` 并记录到 `rag_lifecycle_audits`；不读取照片/原文/向量/答案键/密钥，不联网，也不自动修改知识库。当前快照为 3 张审核 Tencent Card、10 条 active 规则、无 issue、`index_status=in_sync`。历史幂等修复快照为 `160 passed, 4 warnings`，当前全量回归为 `178 passed, 4 warnings`，RAG 质量 Gate 仍为 `FAIL`。Cloud ImageModeration 若真实调用失败，页面和 Trace 会保留脱敏错误码与 RequestId 供定位。

## 2026-09-01｜v3 Holdout 与第一位用户入口

v3 Holdout 已由产品负责人逐题审核，并在项目工作区外按 Holdout A 完成一次正式的 answerless 私有聚合盲测。运行器只读取 `case_id + query`，未读取答案键、照片、人脸向量，未调用 LLM、Provider 或网络；质量 project Gate=`FAIL`，hard-safety=PASS。聚合结果为 Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、evidence relation=23.61%。逐题答案不回流开发，不能用这份 hidden 继续调参。

Streamlit Community Cloud Private 页面已打开，第一位用户应按 [第一位用户端到端测试说明](FIRST_USER_E2E_TEST.md) 亲自完成上传、授权、首次执行、8C 复测和反馈。Codex 不代上传照片、不代点击外部图片调用；当前没有新的 UI 真实多轮图片回执。8C-1/8C-2 的自动化 fixture 只证明控制逻辑和 Trace。

## 2026-09-01｜第一位用户 8A 阻塞修复与下一次运行

第一位用户的真实 Trace 已到达 8A：母版/目标照 IMS Pass、Profile 建立成功，CompareFace 原始分 `56.231842041015625` 为 `uncertain`。旧页面因没有本人/编辑权确认入口而阻断，未调用 BeautifyPic；RAG 只提供了 Tencent 能力 evidence，`execution_authorized=false`。代码现已增加 `subject_match_uncertain_acknowledged` 一次性确认，并在 `edit_planner`、8B `confirm_execution`、执行前 Gate 中重复校验；`no_match` 仍硬拒绝，Trace 记录确认事件和策略版本。

Cloud 重建后，产品负责人刷新页面，在同人不确定提示处确认“目标照是本人且有权编辑”，再生成 8A；随后继续原有 8B/8C 流程。该确认不代表同人已经被模型证实，也不更新长期主体锚点。首轮真实 `ProviderRun`、`VerificationResult`、视觉改善和用户反馈仍需页面实际产生。

## 2026-09-01｜Cloud 页面异常恢复

如果页面显示 `Tencent ImageModeration request failed`，先查看页面下方的脱敏 `error_code`/`RequestId`。本轮 Cloud 日志还发现了另一条确定性根因：Streamlit 重跑重复插入同一 `photo_quality_result_id`，触发 SQLite 唯一键异常并中断页面。已在 `LocalTraceStore` 增加幂等复用与变化内容冲突保护；历史修复回归为 `160 passed, 4 warnings`，当前全量回归为 `178 passed, 4 warnings`。

Cloud 拉取新版本后无需重新配置本机 `.env`：只需刷新页面，重新执行一次当前照片的 IMS 检查。Cloud Secrets 仍必须保留在 Cloud App 的根级设置中；若新的真实腾讯错误仍出现，只回传错误码和 RequestId，不绕过安全门或重复上传无授权照片。

第一位用户同时反馈上传等待过长、首屏显示 JSON、按钮/检查点过多、自然语言入口被工程选项挤压和视觉偏工程文档；这些先作为 UI Gate 输入。当前页面仍是工程验证壳，暂不把上述反馈冒险改成权限或路由变更。

## 2026-09-01｜腾讯特效 Web Adapter 运行说明

左侧页面新增“腾讯特效 Web 试验”。它使用官方示例图作为默认输入，避免第一次试验就发送个人照片；只有用户明确勾选后，才会将授权图片交给浏览器 SDK。首次运行前在本机 `.env` 或 Cloud App Settings → Secrets 配置 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`。Token 仅用于 Python 生成短时签名，页面和 Trace 不显示。

离线合同检查：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/smoke_tencent_effect_web.py
```

该命令应输出 `status=not_run`、`network_called=false`，不读取照片、不加载浏览器 SDK。真实 smoke 必须打开已绑定精确域名的 page 6，点击组件内“开始腾讯特效处理”，然后观察页面是否收到 Browser Receipt；成功回执只能证明单次 Web 静态图处理，不代表 Card 已升级或主流程可用。当前 Web Card 仍为 `candidate`，移动/PC 细项和批量能力继续保持未验证。

### Cloud 当前运行记录（2026-09-01）

最新提交在 Cloud 重建后 page 6 已正常加载；此前旧进程缓存产生的导入错误已消失。Cloud Secrets
仍缺少 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`，
所以 Browser smoke 尚未运行，未产生图片或回执。已有 Tencent REST Secret ID/Key 不可替代这三个
Effect Web 配置。配置完成后刷新 page 6，先使用官方示例图；回执只保留脱敏状态、hash、尺寸、
SDK 版本和耗时。

## 2026-09-01 RAG 失败驱动 Loop v2 运行态

使用 `scripts/run_rag_failure_driven_loop.py` 可在本机重放 V0→V4 的开发/挑战回归与 public regression：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_failure_driven_loop.py
```

本次真实报告为 `reports/rag_failure_driven_loop_v1.json/.html`。V0 Composite=`0.355614`，V1=`0.403233`（2 条预测改变），V2=`0.947619`（22 条预测改变），V3/V4 各 0 条改变并按两代低增益停止。运行器不联网、不调用 LLM/Provider、不读照片/向量/hidden 答案，且不修改 active baseline；报告和 page 5 看板是只读治理证据。开发 annotations 尚待产品负责人审核，public regression/project Gate 仍 `FAIL`，不得将 V2 写成 RAG 产品化通过。

## 2026-09-02｜V3 validation 诊断运行态

V3 原始 answerless Holdout-A 盲测快照保持在工作区外，本轮没有重跑；产品负责人明确授权的验证副本位于 `data/evaluation/rag_v3_validation_cases_v1.json` 与 `..._annotations_v1.json`。运行命令：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_v3_validation_diagnostics.py
```

该命令离线运行 G0–G5，生成 `reports/rag_v3_validation_diagnostics_v1.json/.html`，并在 page 5 提供只读入口。每个 H01–H36 都有题目、Gold、Prediction、根因/SOP、查询投影、FTS/dense/RRF/rerank 和完整安全 Trace；没有照片、向量、密钥、网络、LLM 或 Provider。最终 G3 Route=100%、Relation=97.22%、Recall@5=100%，G4/G5 无增益；固定 Precision/project Gate=`FAIL`、hard-safety=`PASS`，候选未推广。验证副本只用于诊断，下一次正式泛化必须用独立 V4。

## Web 回执错位后的页面行为

若 page 6 发生 Streamlit 重跑，当前输入/参数代次会继续使用同一 `request_ref`，不会再把正常回执
误判为“prepared request 不匹配”。如果用户换图或改参数，旧回执会被安全忽略，页面提示重新点击当前
请求；不要把旧回执手动复制到新请求。真实 smoke 仍须在 Secrets 配齐后运行官方示例图。

2026-09-02 更新：Secrets 配齐并完成 Canvas 修复部署后，官方示例图真实浏览器调用成功，回执为
`web_receipt_effect_web_4d58ea15a0794370`、耗时 2601ms、输出哈希已保存。离线 smoke 仍保持
`status=not_run`/`network_called=false`，因为它按设计不加载浏览器 SDK；真实成功只记录在 Cloud
page 6 的 Browser Receipt，Card 仍为 `candidate`。
## 2026-09-02｜V4 独立 Holdout 与诊断入口

V4 的正式运行包是 `data/evaluation/rag_v4_holdout_runtime.json`，只含 48 道无答案题目。它先在本机离线运行一次并封存预测/Trace，再由负责人授权的私有评分器输出聚合；正式 baseline 为 Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、hard-safety=0/48 PASS、project Gate=FAIL。诊断副本和逐题答案不进入在线 RAG。

page 5「RAG 优化看板」现在同时提供 V4 盲测聚合和 owner-unlocked validation 诊断入口。validation 候选把同一批题目的语义指标提升到 100%，但它不是新的泛化成绩；`blind_snapshot_match=true`、`active_baseline_changed=false`、`proposal_only=true`。完整保管、Trace、失败模式和运行命令见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。

本轮最终工程 QA：全量 pytest=`189 passed, 4 warnings`，V4 专项=`8 passed`，Ruff、format、compileall、`git diff --check` 和 diagnostics runner 均通过。当前知识库仍是 3 张审核 Card、10 条 active 规则；RAG 质量 Gate 仍 FAIL。

## 2026-09-02｜公平评测过程监督后的当前运行真相

上面的 189 条是历史快照；当前全量回归为 `196 passed, 4 warnings`，Ruff check/format、compileall、
`git diff --check` 及全部离线 smoke 均通过。公平过程报告显示新 V3 `36/36`、V4 `48/48` 都完成
“理解/未知降级 → 合法查询 → 检索 → Trace”，新过程门 `PASS`；旧 V4 快照的完整性问题保持历史
`FAIL`，不能补写或复用。质量分数仍未连接 Gold，RAG 仍 `proposal-only`，下一步是仅对封存的新运行包
进行独立 Gold join。

## 2026-09-02｜Tencent Web Meta-Agent 控制面当前回执

本轮新增的 `ToolRegistry`/`MetaAgentToolSelector` 可在本地离线运行：读取 Web candidate Card 和 BeautifyPic baseline，输出结构化 `ToolProposal` 与脱敏 Trace；不加载浏览器 SDK、不读图片、不读 Secret、不发网络、不创建 `ProviderRun`。本地 smoke 的 `network_called=false`、`image_bytes_read=false`、`provider_run_created=false` 已通过测试。Web 的真实浏览器处理仍只在 Cloud page 6 产生过一次成功回执，Card 继续 `candidate`；主流程结果交接 A/B/C 尚未冻结。

本轮新增代码后的最终 QA：全量 `.venv/bin/pytest -q`=`205 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 和相关离线 smoke 均通过。文档中的 196/189/178 条是历史快照，不覆盖本节当前回执。

## 2026-09-02｜Web B handoff 与共同复测（当前）

Web 现在有一条本地可回放的纵向链路：`MetaAgentToolSelector` 提议 Web candidate → `diagnose_and_plan(provider_id="tencent_effect_web")` 生成 Web `EditPlan` → 浏览器回传 result/Receipt → `accept_effect_web_browser_result()` 校验并生成共同 `ProviderRun` → `verify_result()` 生成 `VerificationResult`。proposal 仍 `execution_authorized=false`；只有显式 candidate trial 才能接收 Web 结果。

可运行命令：

```bash
uv run python scripts/smoke_effect_web_b_handoff.py
uv run python scripts/run_effect_web_regression.py
```

当前 E1 smoke 为 fixture-only、`network_called=false`、`result_bytes_persisted=false`；E2 报告为 8/8，通过成功/失败/请求/输入/输出哈希错位/非法 MIME/尺寸/大小和批量失败隔离。两者不证明真实视觉改善或 Provider promotion；结果图不写入数据库、Trace、RAG 或 Git。

新增 Meta-Agent→Web EditPlan 绑定测试、输入哈希/大小异常样例，并修正“安全拦截”和“批量继续”分开统计后，最新全量 `.venv/bin/pytest -q`=`216 passed, 4 warnings`；其余静态检查和离线 smoke 均通过。此前的 205/196/189 等数字均为历史快照。

## 2026-09-03｜E3 真实 Web 候选回放

E3 已在部署后的精确域名 page 6 使用四张负责人授权 JPEG 完成真实候选试验，4/4 Browser Receipt 成功；输入 SHA-256 与预检 manifest 全部匹配，透明 PNG 异常样本在预检阶段被拒绝。运行时只在浏览器会话保留结果图，E3 报告只保存脱敏 receipt、hash、尺寸、状态和耗时：`reports/effect_web_e3_evidence_v1.json/.html`。只读展示页是 `pages/8_腾讯特效Web_E3证据看板.py`。

复核命令：

```bash
uv run python scripts/build_effect_web_e3_evidence.py
uv run python scripts/run_effect_web_regression.py
uv run python scripts/smoke_effect_web_b_handoff.py
```

注意：四条手工回执尚未记录完整 `request_ref`，报告会显示该阻塞；真实视觉复测、供应商地区/费用/留存证据和负责人 promotion 仍未完成。Web Card 继续 `candidate`，不要将本次回放写成视觉效果或正式上线证据。
