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
