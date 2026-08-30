# RAG Failure Pattern 分析与自校正 SOP（v0.1）

> 本文是当前 RAG 优化的执行手册。它记录“怎样从失败得到一个可回滚候选”，不是把候选自动发布成产品规则。

## 目标

当 public/holdout 评测或真实运行出现错误时，回答四个问题：到底是哪一层出错、证据是什么、下一次只改什么、改动后有没有安全回退。RAG 只能提供建议，不能借此获得图片出站、Provider、参数或执行权限。

## 数据边界

分析器可以读取 public cases、public annotations、redacted predictions，以及产品负责人私有评分器输出的聚合 JSON。它禁止读取 hidden answer key、隐藏逐题 Gold/题干、用户照片、人脸向量、原始用户文本、密钥、完整 Prompt、Provider 请求体或网络。隐藏集只能回流总体指标和错误类型。

## 六步流程

1. **冻结事实快照**：记录代码/知识版本、输入包、预测文件、评测报告和 Trace 引用；旧报告不覆盖。
2. **按层定位**：分别查看指标口径、检索召回、证据关系、路由安全、Provider 准入；不把一个总分当成根因。
3. **提出单一候选**：一次只改一个可解释变量（例如同义词归一化或 evidence packing），不自动降低阈值、不读取 hidden 逐题答案。
4. **公开集回归**：重跑 route/evidence/relation/排序和 hard-safety；任何安全回退都拒绝候选。
5. **独立 holdout 聚合**：只运行 answerless holdout，由产品负责人受限环境回流聚合指标；同一 holdout 不反复试错。
6. **人工批准或回滚**：产品负责人查看候选差值、成本/延迟和风险，批准后才能开新版本；未批准继续使用 active baseline。

## 当前实例

`rag-correction-candidate-v0.1` 只增加经审核的中英/领域同义词归一化。它在临时本地 SQLite/索引中运行，公开 52 题的可比指标均无回退，`regression_gate=PASS`，但 `project_threshold_gate` 仍为 `FAIL`，所以 `active_baseline_changed=false`、`promotion_decision=not_promoted_proposal_only`。公开集中 51/52 题 Gold evidence 少于 3 条，固定分母 Precision@3=47.44% 的口径张力保留给产品负责人另行决策；隐藏集只保留 17/20 错误等聚合事实，不用于逐题补规则。

## 可观测产物与回滚

- JSON：`reports/rag_failure_patterns_v1.json`，含版本、证据级别、模式、候选指标 delta、网络/Provider 布尔事实和 SOP。
- HTML：`reports/rag_failure_patterns_v1.html`，可在 RAG 治理看板和 RAG 优化看板中只读查看。
- 回滚：删除/停用候选 profile，恢复 `rag-gold-baseline-deterministic-v0.2`；不需要修改 Provider、权限或业务合同。

## 重跑命令

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/analyze_rag_failures.py
```

任何候选通过本 SOP 只能说明“公开回归没有回退、过程可审计”，不能直接说明 RAG 已通过、已上线或图片修图有效。

## 2026-08-30 评测治理更新

本轮产品负责人冻结了三项治理规则，并已接入本 SOP：

- **Precision C**：同时保留固定分母、覆盖式和返回式 Precision，并按 Gold 证据条数分层；固定分母仍是历史 Gate，不能用覆盖式结果把 `FAIL` 改成 `PASS`。
- **Holdout A**：v2 隐藏集只保留聚合诊断；新建 v3 独立 runtime 模板和工作区外答案保管流程，v3 未完成前不得用 v2 逐题答案调参。
- **安全事件 ID C**：使用版本化确定性字典映射已知标签；未知标签不猜，hard-safety 必须是 `MANUAL_REVIEW_REQUIRED`，由产品负责人确认后才可自动评分。

当前报告新增 `precision_at_k_effective`、`precision_at_k_returned`、按 Gold 条数分层结果、`safety_event_catalog_version` 和未知事件计数；这些是可追溯证据，不是自动自校正授权。候选修正仍然 proposal-only，RAG 仍不能授予图片出站或 Provider 调用权限。

## 2026-08-30 生命周期审计接入

在六步 failure SOP 之前增加一个只读前置检查：先运行 `scripts/audit_rag_lifecycle.py`，确认来源状态和派生索引快照。若条目过期、撤回、冲突、尚未生效、候选未发布、缺来源 URI 或没有原子规则，先把它记录为知识生命周期问题，禁止用同义词、rerank 或 Prompt 补丁掩盖；若 dense manifest 与 active chunk/vector 数量不一致，先记录索引 stale，再重建派生索引并回归。审计只报告，不自动改状态、发布、删除或重建。

生命周期干净但检索仍错，才进入原有“指标→召回→证据关系→安全→路由”定位；检索 miss 必须区分“知识库没有资料”“过滤掉了过期/未发布资料”“FTS/dense 空召回”和“rerank 排序错误”。每次审计都生成 `RagLifecycleAudit`、安全元数据摘要和可回放 Trace；报告与 Dashboard 不展示来源正文、照片、向量、答案键或密钥。该前置步骤让知识时效问题与 retriever failure 分开，避免错误地把产品事实问题当模型调参问题。

重跑命令：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/audit_rag_lifecycle.py
```
