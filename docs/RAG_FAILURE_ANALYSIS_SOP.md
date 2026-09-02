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

## 自动化迭代 Loop（v0.1）

为避免“分析写成了 SOP，却没有真的按 SOP 跑候选”，本项目新增了一个可重复的本地 loop：

```text
读取 public dev/challenge + 独立人工 annotations
→ 运行 V0 active baseline
→ 每次只提出一个候选
→ 运行 route/evidence/relation/排序/hard-safety 回归
→ 记录 Composite、指标 delta、Trace 与 anti-overfit
→ 连续两代增益 < 0.01 时停止剩余候选
→ 保持 active baseline 不变，等产品负责人批准
```

当前候选代次的含义是：

| 代次 | 改动 | 状态 |
|---|---|---|
| V0 | `rag-gold-baseline-deterministic-v0.2`，现役公开 baseline 参照 | 已运行 |
| V1 | `rag-correction-candidate-v0.1`，经审核的中英/领域同义词归一化 | 已运行，未推广 |
| V2 | relation canonical 化，只处理已审核关系别名 | 已运行，未推广 |
| V3 | evidence 稳定去重与最多 5 条打包 | 因边际效益递减跳过 |
| V4 | 冲突/空证据 fail-closed 路由保护 | 因边际效益递减跳过 |

本轮 public 逐题分析显示：52 题的 route、evidence set 和 evidence relation 均已正确；51 题仅出现 `metric_sparse_gold_denominator`，原因是 Gold evidence 少于 3 条而固定 Precision@3 仍使用历史分母。v3 Holdout 的 `evidence_relation_mismatch`、`evidence_set_mismatch`、`route_mismatch` 只能保留为 aggregate pattern，不能拆成逐题补丁。

对 v3 aggregate 的解释必须分成三层：`aggregate_fact`（计数本身）、`aggregate_fact_plus_hypothesis`（基于计数提出的可能原因）和 `case_fact`（只有新的独立 Holdout 逐题证据才能得到）。relation=31、set=21、route=25 三个计数可能重叠；本轮只记录“观察到什么、可能为什么、下一份数据要补什么”，不得把假设写成隐藏题结论。优化报告的 `private_pattern_interpretations` 和 page 5 看板按这个层级展示。

loop 入口：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_optimization_loop.py \
  --private-aggregate /path/to/v3_holdout_blind_aggregate.json
```

产物为 `reports/rag_optimization_loop_v1.json/.html`，page 5 的 RAG 优化看板会显示代次趋势、逐题错误代码、Composite、停止原因和反过拟合状态。HTML/JSON 不保存原始题干；逐题行只保留 public case ID、split、标签、题干 SHA-256 和结构化错误代码。

## 不能自动做的事

- 不能读 v3 逐题答案、用隐藏题目反向写规则或重复正式运行同一份 v3；
- 不能因 public Composite 高就替换固定 project Gate，也不能把覆盖式 Precision 当成通过；
- 不能自动发布候选、扩大 Provider 白名单、改变权限/预算/参数上限或让 RAG 获得图片出站；
- 不能把 public 逐题“没有算法错误”推断为隐藏集已泛化；需要新独立 Holdout v4 才能再次正式验收。

## 2026-08-30 评测治理更新

本轮产品负责人冻结了三项治理规则，并已接入本 SOP：

- **Precision C**：同时保留固定分母、覆盖式和返回式 Precision，并按 Gold 证据条数分层；固定分母仍是历史 Gate，不能用覆盖式结果把 `FAIL` 改成 `PASS`。
- **Holdout A**：v2 隐藏集只保留聚合诊断；新建 v3 独立 runtime 模板和工作区外答案保管流程，v3 未完成前不得用 v2 逐题答案调参。
- **安全事件 ID C**：使用版本化确定性字典映射已知标签；未知标签不猜，hard-safety 必须是 `MANUAL_REVIEW_REQUIRED`，由产品负责人确认后才可自动评分。

当前报告新增 `precision_at_k_effective`、`precision_at_k_returned`、按 Gold 条数分层结果、`safety_event_catalog_version` 和未知事件计数；这些是可追溯证据，不是自动自校正授权。候选修正仍然 proposal-only，RAG 仍不能授予图片出站或 Provider 调用权限。

## 2026-09-01 根因校验补充：先证明候选真的改变了哪一层

上一轮 V1/V2 的失败不是“指标不够灵敏”，而是候选改在了错误位置：V1/V2 只变换已经生成的 `Prediction`，而当前 public baseline 的 route、evidence set、relation 本来就是 canonical，因而 0 条预测事实发生变化。今后的每一代候选必须在运行前后比较 `route/evidence_refs/evidence_relations`，并记录 `changed_prediction_count`；若为 0，必须标记为 no-op，不能把 Trace 名称变化写成质量提升。

failure analysis 还必须先做一项架构诊断：在线 P0-A/P0-B 的输入是校验后的 `RagQuery`，不是原始用户句子；如果评测 runner 使用硬编码 phrase projector，则测到的是“自然语言→结构化查询”的上游能力，而不是检索器本身。应该把问题拆为：查询理解/策略编译、检索召回、证据关系、路由和安全五层，分别设计 Gold 和修正。

本轮已用新建的 `rag_failure_driven_dev_v1`（16 dev + 12 challenge，状态 `owner_review_required`）验证这个方法：V0 旧短语投影 Composite=`0.355614`；V1 同义词归一化=`0.403233`；V2 在检索前做受审核 QuerySignals 和安全/生命周期优先级编译，Composite=`0.947619`，route/relation/Recall@5 均为 100%；V3 relation guard、V4 evidence packing 都是 0 条预测变化，连续两代增益 `<0.01` 后停止。该结果是开发集事实，不是 v3 Holdout 泛化结论。

每个失败模式的 SOP 记录必须包含：观察到的输入层/检索层/策略层；失败代码；可验证的根因假设；一次只改的候选；改动前后实际变化条数；dev/challenge 回归；既有 public regression；安全/隐私/越权布尔证据；回滚方式。安全和生命周期优先级必须在能力词识别之前执行；多意图必须保留证据 union；不能用补充无关证据的方式抬高固定 Precision。

## 2026-08-30 生命周期审计接入

在六步 failure SOP 之前增加一个只读前置检查：先运行 `scripts/audit_rag_lifecycle.py`，确认来源状态和派生索引快照。若条目过期、撤回、冲突、尚未生效、候选未发布、缺来源 URI 或没有原子规则，先把它记录为知识生命周期问题，禁止用同义词、rerank 或 Prompt 补丁掩盖；若 dense manifest 与 active chunk/vector 数量不一致，先记录索引 stale，再重建派生索引并回归。审计只报告，不自动改状态、发布、删除或重建。

生命周期干净但检索仍错，才进入原有“指标→召回→证据关系→安全→路由”定位；检索 miss 必须区分“知识库没有资料”“过滤掉了过期/未发布资料”“FTS/dense 空召回”和“rerank 排序错误”。每次审计都生成 `RagLifecycleAudit`、安全元数据摘要和可回放 Trace；报告与 Dashboard 不展示来源正文、照片、向量、答案键或密钥。该前置步骤让知识时效问题与 retriever failure 分开，避免错误地把产品事实问题当模型调参问题。

重跑命令：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/audit_rag_lifecycle.py
```

## 2026-09-01 失败驱动 Loop v2：从“写 SOP”到“按 SOP 真正修复”

上一轮 Loop 的核心问题不是运行器坏了，而是修正位置错了：V1/V2 只改已经生成的 `Prediction` 后处理，当前公开 baseline 的 route、evidence 和 relation 又本来是 canonical，所以 `changed_prediction_count=0`，指标自然不动。新的 SOP 在运行候选前先回答“它是否改变了真实输入层”，把线上输入合同 `RagQuery` 与旧评测器的 raw-text phrase projector 明确分开。

本轮建立 28 题、16 dev + 12 challenge 的 `rag_failure_driven_dev_v1` 开发集（题目和 annotations 均标记 `owner_review_required`），不读取 v3 私有逐题答案。V0 的逐题 failure code 计数为：`route_mismatch=24`、`evidence_relation_mismatch=23`、`evidence_set_mismatch=18`、`rank_mismatch=10`；另有 28 条 `metric_sparse_gold_denominator`，后者是固定 Precision 口径提示，不是检索器坏了。

| 失败模式 | 证据定位 | 这轮修正 | 结果 |
|---|---|---|---|
| 上游查询投影漏召回 | 窄短语词表把“下颌线收窄/双眼偏小/jawline”等变成 `UNKNOWN` | 在检索前做受审核同义词归一化和 `QuerySignals` 抽取 | V1 有限改善；V2 继续覆盖领域表达 |
| 动作与提问歧义 | “能不能把……”被误当纯信息查询 | 区分 `information_request` 与明确动作，动作+部位优先 | V2 路由/证据关系恢复 |
| 安全/生命周期优先级 | 隐私、注入、冲突、过期被能力词覆盖 | 先处理 hard block、出站、生命周期、冲突，再处理能力 | V2 保持 hard-safety=PASS |
| 多意图证据被压扁 | 同句要求同人确认+内容审核时只返回一类证据 | `QuerySignals` 保存多个意图，证据按 union 组织 | V2 evidence exact/relation=100%（开发集） |
| 稀疏 Gold 分母 | 1—2 条 Gold 仍按固定 K=3 计分 | 并行保留 fixed/effective/returned Precision，不补无关证据 | 不再把评测问题伪装成算法增益 |

真实代际回执：V0 Composite=`0.355614`；V1=`0.403233`（+0.047619，改变 2 条预测）；V2=`0.947619`（+0.544386，改变 22 条预测）；V3 relation guard 和 V4 evidence packing 均改变 0 条预测，连续两代增益 `<0.01` 后停止。候选 Trace 全部为 `network_called=false`、`llm_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`，anti-overfit=`PASS`。

这次“有增益”仍只代表 owner-review 开发集上的工程事实。public regression 的固定 Precision 和 project Gate 仍为 `FAIL`；RAG 仍是 advisory-only。只有产品负责人审核新 annotations、再用全新独立 Holdout v4 验收后，才可讨论把 query compiler 候选提升为 active。

为满足逐题复盘要求，报告同时输出 `final_candidate_diagnostics`，把 V0 与终态的状态、错误码、路由和是否变化并列保存；不保存原始题干，不读取 v3 私有逐题答案。人工解释见 [RAG_FAILURE_CASE_REVIEW_V2.md](RAG_FAILURE_CASE_REVIEW_V2.md)。

## 2026-09-02｜V3 验证集逐题 SOP（经负责人解冻）

V3 的原始 answerless Holdout-A 运行仍是不可重跑的历史快照；本节只适用于负责人明确授权后派生的 `rag-v3-validation-unlocked-2026-09-02` 验证副本。对 H01–H36 逐题读取题干与人工 Gold，依次生成 G0 baseline、G1 查询编译、G2 policy-first 编译、G3 public regression guard、G4 relation guard、G5 evidence packing，并为每代保留完整安全 Trace。

逐题分析顺序固定为：先看 hard-safety 和生命周期，再看查询投影/路由，再看证据集合、关系和排序，最后区分真正失败与 `metric_sparse_gold_denominator` 统计提醒。修复必须触达真实输入层；每代只改一个可解释变量，记录 `changed_prediction_count`，同时跑 validation 与 public regression；候选始终 proposal-only，G2 若造成公开回归必须回退，不能用 V3 高分覆盖回归事实。

本轮最终 G3 的 validation Route=100%、Evidence relation=97.22%、Recall@5=100%；G4/G5 无新增改变，说明继续在下游打补丁已到边际效益递减。固定 Precision/project Gate 仍 `FAIL`、hard-safety `PASS`，所以 SOP 的“优化完成”只表示诊断闭环已执行，不表示 RAG 已产品化通过。下一次泛化必须新建不与 V3 重叠的 V4 Holdout。
