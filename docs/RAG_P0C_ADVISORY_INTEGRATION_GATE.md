# RAG P0-C｜受限证据回接 8A / 8C

> 状态：**已实现并完成本地验收**｜版本：`rag-advisory-v0.1`｜日期：2026-08-29
>
> 这一步把已完成的 P0-A / P0-B 从“独立查工具说明书”变成“能给 8A/8C 提供受限证据的 Agent 组件”。它不是新图片工具、不是自动联网搜索，也不会因为检索到一段资料就新增执行权限。

## 1. 它解决什么问题

此前，系统已经能从三张人工审核的腾讯 Provider Card 中检索能力、限制和失败规则，但 `EditPlan` 与 `VerificationResult` 还不能留下“这份计划/策略参考了哪条审核知识”的证据。直接把检索结果交给 LLM 或工具又会带来一个危险：一条看起来相关的资料，可能被误当成“现在可以直接调用新 API”的许可。

P0-C 因此把 RAG 定义为**受限证据顾问**：它只把已审核知识分成“可直接参考、补充参考、存在冲突”三类，交给已有规划器或策略选择器。真正的图片执行仍必须经过既有的状态机、确认/作用域、预算、安全 Policy、Provider Card、Adapter 和真实回执链。

一句话概括：**RAG 可以说“我查到哪些说明书”，不能说“所以我已经替你调用了什么”。**

## 2. 输入、输出和规则表

| 环节 | 输入 | 输出 | 冻结规则 |
|---|---|---|---|
| 8A 生成计划前 | 已校验的 `IntentFrame`、`ReferenceProfile`、单脸/部位等结构化槽位 | 工具能力/限制的 `RagAdvisoryDecision` 与 `knowledge_refs` | 参数仍由确定性 `mapping_policy` 生成；RAG 不计算脸部差异、不生成参数 |
| 8C 选择复测策略时 | profile 版本、轮次、已校验的策略范围 | 关于 CompareFace 等工具用途/限制的证据建议 | 8C 的真实白名单仍由状态机/Policy 管；当前不因 RAG 调用外部复测 |
| Provider 失败后 | Provider、operation、脱敏错误类别 | 可用的已审核降级/说明证据 | 不上传错误原文、照片或回执正文；未知时停止该分支 |
| 新增 Provider 时 | 候选 Card 的结构化属性 | 只可作为审核清单/候选知识 | 没有 Card、Adapter、权限、smoke、回归和产品冻结，不进入 `reviewed_active` 或执行 |
| 参数/权限冲突 | 已审核 Card / Policy 的结构化条件 | 冲突来源、停止原因、人工下一步 | 用户或 LLM 只能选人工复核、手动建议或停止，不能选择哪条冲突事实直接执行 |

## 3. 已冻结的回接规则

### 3.1 RAG 只能提议，不能授权

`RagAdvisoryDecision.execution_authorized` 在合同中被限定为 `false`。因此 RAG、LLM 或页面不能把检索命中改成工具授权；它们只能把证据交给现有的确定性 Gate。当前已存在、独立配置且已通过全部前置 Gate 的 Provider Card baseline 可以继续按自己的规则走，但 RAG miss 不能创造、扩大或替换这种 baseline。

### 3.2 证据分层与冲突处理

每次 P0-C 检索都输出三类引用：

- `direct_evidence`：当前、适用、无硬冲突的已审核事实；可作为已有规划器/策略选择器的输入，并写入 `EditPlan.knowledge_refs` 或 `VerificationResult.knowledge_refs`。
- `reference_information`：说明背景或限制的辅助信息；可解释，但不能单独放行。
- `conflict_information`：同一关键事实存在矛盾时，完整带回的冲突来源。

没有冲突时，系统采用 `direct_evidence`，并把 `reference_information` 作为辅助解释。出现硬冲突时，P0-C 把所有受限范围内的冲突引用都带回、写入 Trace 和 bad case，且强制 `CONFLICT_BLOCKED`：不能继续 baseline、不能生成计划、不能调用工具。用户/LLM 只能选择 `manual_review`、`manual_suggestion` 或 `stop` 这三条**非执行**路径。

### 3.3 检索 miss 不是“让 LLM 猜一猜”

对依赖 RAG 的新能力/新策略，空召回、索引不可用、缺关键槽位或没有直接证据时，系统立即停止该 RAG 分支并返回“当前没有足够的已审核依据，我不知道”；不能让 LLM 编造能力。系统会写入脱敏 `RagBadCaseRecord`，区分：知识库没有相关文档、召回为空、重排后没有 direct evidence、索引不可用、关键槽位缺失、硬事实冲突。

如果当前已有独立、已审核、已通过普通 Gate 的 baseline，系统可以保持该 baseline 原样继续；这叫 `baseline_degraded`，不是 RAG 放行。没有这种 baseline 时路由为 `unknown_stopped`，只给手动建议或停止。

### 3.4 新工具的准入生命周期

RAG 发现新工具不等于产品已经获得新能力。候选工具必须依次完成：官方来源/License/地区/隐私/成本资料 → 候选 Provider Card → Adapter shell 与测试替身 → 权限/预算检查 → 真实 smoke 及真实回执 → RAG Gold 回归 → 产品负责人冻结 → `reviewed_active`。在此之前只能解释或标为候选，不得把用户图片发送给它。

### 3.5 首批验收案例

首批人工审阅的验收锚点选择：

- `RAG-G01`：瘦脸能力存在时，RAG 可提供 `FaceLifting` 的直接证据，但不得生成滑杆数值、不得授权执行；规划器仍生成必须确认的计划。
- `RAG-G09`：两条 active fixture 对同一关键事实矛盾时，必须带回两条来源、阻断执行并留存 `hard_fact_conflict` bad case；用户/LLM 不能解除阻断。

这两个案例目前已作为自动化安全回归实现；它们是首批验收锚点，不等于已经完成有统计效力的人审 Gold Set 或 holdout 指标。

## 4. P0-A / P0-B 的分层检索设计

```text
P0-A: FTS 前 5                    ← 关键词通道，快速兜底精确匹配

P0-B: 关键词 8 + 向量 8           ← 双路召回：FTS 取 8 条 + 向量搜索取 8 条
       ↓
       RRF 前 10                  ← 用 RRF 融合两路结果，取 Top 10
       ↓
       重排前 10                  ← 用 Cross-Encoder 等重排序模型精排
       ↓
       给 LLM 3 条、最多 5 条      ← 未来 LLM 消费证据时的上下文预算，控制 Token 消耗
```

当前 P0-B 本身**不调用 LLM**；运行时最多采纳 3 条已审核 evidence。上图最后一行是后续确实需要把证据交给 LLM 解释时的上下文预算：默认 3 条 direct evidence，绝不超过 5 条，且仍不可成为权限或参数放行条件。Top-K、分数、overlap 都是版本化实验配置，未来必须用 Gold Set 校准，不能把模型裸分变成执行阈值。

## 5. 这次实际写进代码的链路

```text
8A / 8C 的已校验结构化槽位
→ P0-B metadata 硬过滤 + FTS / dense / RRF / rerank
→ P0-A 安全分类
→ RagAdvisoryDecision（direct/reference/conflict）
→ 确定性 planner / verification policy
→ 既有状态机、确认、Provider Card、Adapter、真实回执
```

新增 `services/rag_advisory.py` 将检索结果转换为受限建议；`storage/knowledge_store.py` 新增脱敏 advisory run 与 RAG bad case 账本；`EditPlan`、`VerificationStrategyProposal`、`VerificationResult` 可保存版本化 `knowledge_refs`，但它们不把引用解释为授权。`app.py` 在 8A 生成计划前和 8C 选择复测策略时调用本地 P0-B advice；页面只显示紧凑依据，不显示原文、裸分、原始 query 或隐藏推理。

## 6. 实际测试案例与完整 Trace

| 案例 | 预期 | 已验证事实 |
|---|---|---|
| G01 直接证据 | 允许已有计划参考瘦脸能力，但不可授权 | `execution_authorized=false`；`EditPlan.knowledge_refs` 有来源；`requires_confirmation=true` |
| G09 硬冲突 | 展示两条来源并阻断 | `conflict_blocked`；只能人工复核/手动建议/停止；`hard_fact_conflict` 入账 |
| 未知新能力 | 停止 RAG 分支，不编造 | `unknown_stopped`；`no_active_knowledge` 入账 |
| 既有 baseline + miss | 不扩大能力，只保留原 baseline | `baseline_degraded`；`execution_authorized=false` |

2026-08-29 的本地真实 smoke 运行 `scripts/smoke_rag_advisory.py`：模型下载关闭；未读照片/原始用户文本；未调用 LLM、腾讯或其他 Provider API。输出 G01 的 `advisory_available`、G09 的两条 fixture 冲突引用和 `conflict_blocked`、未知能力的 `unknown_stopped`；临时知识账本快照为 5 个来源、12 条规则、3 条 advisory run、2 条 bad case。该回执只证明本地受限检索与路由链，**不**证明图片修图效果、外部复测或新工具可执行。

P0-C 收尾**当时**的交叉校验：`.venv/bin/pytest -q` 实际为 `106 passed, 4 warnings`；`.venv/bin/ruff format --check .`、`.venv/bin/ruff check .`、`compileall` 与 `git diff --check` 均通过。四条 warning 均为既有 Pillow 弃用警告，不改变 P0-C 的合同或安全结论。后续只读 Dashboard 的新增安全聚合测试已使当前全量回归为 `107 passed, 4 warnings`；当前总状态见 `DEVELOPMENT_PROGRESS.md` 与 D-TECH-040。

## 7. 当前边界与下一个决策门

当前已完成的是“RAG 给已有 8A/8C 提供受限证据”，只读本机 RAG 专属 Dashboard，以及 P0-D metadata-only lifecycle audit：它们读取独立知识账本的脱敏聚合/元数据，不改变 P0-C 的行为或权限。尚未完成：Gold Set v3 正式盲测/Judge 决策、自动 lifecycle/observability worker、任何新 Provider 的完整准入，以及 external/hybrid 复测 Adapter。下一产品决策门应只讨论这些未完成项，不能因为 P0-C、Dashboard 或 P0-D 已存在就把它们误称为已上线能力。

## 8. 2026-08-30｜Failure Pattern 看板对 P0-C 的影响

新增的 failure-pattern 分析器、候选归一化和优化看板属于评测/治理层，不改变本 Gate 的 `execution_authorized=false`。它们可以定位 RAG miss、证据关系错误、指标口径问题和隐藏集聚合风险，但不会生成参数、改写 `RagAdvisoryDecision`、放行图片出站或升级 Provider。候选修正只有在公开安全回归通过并得到产品负责人批准后，才可能进入另一个版本化 Gate；本轮候选未推广。

## 2026-08-30 当前同步：P0-D 生命周期审计

P0-D 在 P0-C 之前提供知识安全元数据快照：当前 3 张审核 Tencent Card、10 条 active chunks、`issue_counts={}`、dense `in_sync`。它只生成审计建议和 Trace，不改变 `RagAdvisoryDecision`、不自动发布/改状态/删除/重建索引，也不新增执行授权；因此 P0-C 的 `execution_authorized=false` 保持不变。

## 2026-09-02｜V3 validation 诊断对 P0-C 的补充边界

V3 原始 answerless Holdout-A 快照仍只保留一次性 aggregate；产品负责人明确授权的 validation 副本用于离线逐题诊断，不改变 P0-C 的在线行为。`rag_v3_validation_diagnostics` 仅消费审核标注来比较 G0–G5 查询编译候选，输出逐题证据关系、根因、SOP 和完整安全 Trace；它不调用 P0-C 生产入口，不生成 `RagAdvisoryDecision` 以外的权限，也不写 `ProviderRun`。

最终 G3 validation Route=100%、Relation=97.22%、Recall@5=100%，但固定 Precision/project Gate 仍 `FAIL`；G2 因 public regression 退化而拒绝，G4/G5 无增益。该结果只能作为验证集工程证据，RAG `execution_authorized=false`、Provider 白名单和六个业务合同不变；正式 promotion 必须另建独立 V4 Holdout。

## 2026-09-02｜V4 当前边界覆盖

V4 已作为新的独立 Holdout 完成一次 answerless baseline（48 题），随后在快照封存且得到负责人授权后才生成 validation 逐题诊断。blind baseline 的 Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%，hard-safety=0/48 PASS，project quality Gate=FAIL。解冻候选的 100% 只用于失败驱动诊断，不能改变 P0-C 的 advisory-only 状态。

P0-C 可以把审核过的工具能力、限制、生命周期和复测规则作为证据建议交给 8A/8C；它不能生成参数、增加 Provider、授予权限、写 ProviderRun 或发送图片。V4 的 `active_baseline_changed=false`、`proposal_only=true` 和 fixed project Gate 继续是 Promotion 前的硬边界。完整题目、Trace、失败模式和命令见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。

## 2026-09-02｜Web Card 消费边界覆盖

P0-C 现在也可以为 Web `EditPlan` 和 8C 复测策略提供已审核工具证据，但仍只负责 advisory：它不能把 Web candidate 变成授权，也不能生成 Web 参数、签名、ProviderRun 或图片出站。Meta-Agent 读取同一份 advisory 后输出 `ToolProposal.execution_authorized=false`；状态机/Policy 和 Web Adapter 继续独立校验候选试验、同意、scope、预算、幂等与 Browser Receipt。

在 B handoff 路径中，RAG 的证据只影响“可提议哪种工具/复测方案”，不影响结果 data URL 的留存边界。Web handoff 通过共同 `VerificationResult` 后，仍需 E2 真实样本和 E3 准入才可 promotion；RAG `proposal-only` 与 Web Card `candidate` 两条硬边界保持不变。
