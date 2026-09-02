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
## 2026-09-02｜V4 失败驱动 SOP 与停止规则

V4 的正式 baseline 先作为一次性独立考试运行，再在快照封存且得到负责人明确授权后转成 validation 副本。这个顺序不能颠倒：如果先看答案再改规则，后面的高分只能说明“练习题做对了”，不能说明系统对新问题有效。

### 逐题分析顺序

1. 先看安全、隐私、出站、主体生命周期、过期、冲突和提示注入；命中 hard block 时不被能力词覆盖。
2. 再看用户是在问能力、要建议、要求执行、要求复测，还是在要求拒绝/降级；多意图必须保留，不压成单一类别。
3. 再看查询是否把自然语言编译成正确的领域词和任务信号，确认是否召回直接证据。
4. 将检索结果分为直接证据、参考信息、冲突信息和不可用/过期信息；关系错误不能用“相似度高”掩盖。
5. 最后看集合、排序和指标口径，单独标记 Gold 少于 K 的稀疏分母提醒。

### V4 基线失败模式

| 代码 | 题数 | SOP 处理 |
|---|---:|---|
| `route_mismatch` | 42 | 前移到自然语言→QuerySignals；先判任务和安全策略 |
| `evidence_relation_mismatch` | 46 | 明确 direct/reference/conflict 三类关系，冲突优先停下 |
| `evidence_set_mismatch` | 31 | 用能力/限制/权限/生命周期的证据 union，避免只返回一张 Card |
| `rank_mismatch` | 9 | 双路召回后 RRF/重排，但不凭排序替代权威级别 |
| `metric_sparse_gold_denominator` | 47 | fixed/effective/returned 并列展示，不补无关证据、不改冻结分母 |

计数可重叠，不能相加当成 145 道错误题。每个 case 必须留下“观察事实→根因→修正→回归结果”，而不是只记录一个总分。

### 候选修正与回滚

候选必须作用于真实输入层或明确的证据整理层，每代只改一个变量，输出 `changed_prediction_count`，同时跑公开回归、V4 validation、安全硬门和 anti-overfit。候选只供诊断，不能写入 active baseline。若公开回归退化、安全出现未知/错误放行、或候选需要读取 holdout 答案，立即回滚并记录原因。

V4 的 G0→G5 结果为：baseline → 既有查询编译 → 通用同义词/策略优先查询编译 → 关系归一化 → 证据打包。G2 后语义诊断达到 100%，G3–G5 连续没有新的预测改变，因此按“连续两代增益小于 0.01 且未跨 project Gate 即停止”规则结束。固定 project Gate 仍 FAIL，RAG 仍 proposal-only。

### 当前可回放证据

- V4 独立盲测聚合：`reports/rag_v4_holdout_blind_aggregate.json/.html`；只含聚合，不含题干、Gold 或答案键路径。
- V4 逐题 validation：`reports/rag_v4_validation_diagnostics_v1.json/.html`；允许负责人授权后的题干/Gold/Trace，仅供诊断。
- 完整说明：[RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。

这个 SOP 的“优化完成”只表示失败分析和候选迭代流程已经跑通；它不等于 RAG 质量 Gate 通过。要讨论 promotion，必须建立一套未参与诊断的新 Holdout，并再次完成 answerless 盲测。

## 2026-09-02｜公平评测前置 SOP

在任何失败分析、指标计算或候选修正之前，先运行独立过程监督考官：

```text
同一题目清单去重/计数
→ 检查答案、标注、照片、向量、密钥和外部调用均为 0
→ 检查原题只保留哈希
→ 检查编译状态显式记录；未知也生成中性 RagQuery
→ 检查每题完整 retrieval Trace 和 finalized 标记
→ 检查 Prediction 只来自 retrieval_result
→ 检查证据引用能回溯到实际候选/采用列表
→ 过程门 PASS 后，才允许单独连接 Gold 计算质量
```

过程门失败的题不能进入质量平均分；旧 Holdout 快照不得补写 Trace 或回填 Projection。新版同题重放只能作为“评测流程修复证据”，不得改写历史质量分数。当前报告 `reports/rag_fair_process_audit_v1.json/.html` 同时展示新版重放和旧 V4 快照，避免把二者混成一场考试；新版脱敏运行包已经封存，可按题目哈希连接 Gold，不需要重新跑题。

过程门通过后，继续按“根因→一次一个候选→公开回归→独立 Holdout”迭代。诊断带低于三分之一/达到三分之一/达到三分之二只用于观察边际效果；固定 Precision 和 hard-safety/project Gate 的原口径不变。RAG 仍 proposal-only，过程考官不授予工具权限。

## 8. 连续低分时先做反思审计

如果连续两代以上的改动没有带来可信增益，或者新的 Holdout 同时出现 Route、Evidence relation 和 Recall 下降，不能马上继续补同义词、调 Top-K 或更换重排模型。先按 [RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md](RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md) 重建实际被测链路：原话是否进入结构化查询、查询是否进入真实检索、证据是否来自可索引 chunk、路由是否由被测层产生、评测分母是否可达。

反思审计必须把以下四件事分开：

- **听懂问题**：自然语言是否被编译成正确任务、部位、安全和生命周期信号；
- **找到资料**：真实检索是否返回了正确 chunk，而不是评测器预先写入的别名；
- **整理证据**：是否正确区分直接依据、参考信息、冲突或过期信息；
- **统计分数**：Gold 是否稀疏、固定 K 是否数学可达、多意图和额外关系是否按合同评分。

只有每一层有独立证据，才能把失败转成下一条 SOP。反思期间不读取新的隐藏答案，不把解冻验证的高分写成泛化通过；候选继续保持 `proposal-only`。

## 9. 2026-09-02｜Operation coverage 候选与 V5 过程监督 SOP

### 9.1 适用问题

当一条用户请求同时包含多个操作（例如既要比较瘦脸能力，又要判断大眼或隐私限制），单纯取排序前几条可能让一个操作挤掉另一个操作。此时不能直接增加无关证据，也不能凭题目标签补证据；先检查结构化查询是否真的包含多个 operation，再在已审核、有效的知识池中为每个请求 operation/provider 选一条代表候选。

### 9.2 单变量修正步骤

```text
冻结 V0/当前候选快照
→ 记录请求 operation/provider
→ 扩大真实 sparse/dense 候选池
→ 只从 reviewed_active 且未过期条目选代表证据
→ 原有 RRF/rerank/关系分类继续执行
→ 比较 before/after 的逐题证据与 Trace
→ 跑 public regression + hard-safety
→ 只有无退化才进入独立 Holdout
```

候选 Trace 必须记录 `operation_coverage_pool`、覆盖到的 operation/provider、是否发生重复、是否因为冲突/权限/生命周期而排除；它不能把操作名转换成新的能力事实。若没有有效 direct evidence，仍返回“不知道/降级”，不能由 LLM 或规则猜测。

### 9.3 V5 公平过程门

V5 运行前答案键必须封存；运行器只接收题目，过程监督器逐题检查：输入计数、Trace 计数、Prediction 计数、合法查询、实际检索、`route_source=evidence`、`finalized=true`、无答案/标签/题干泄露、无网络/LLM/Provider/照片/向量副作用。过程门通过后才可做一次 Gold join；本项目已完成该授权连接，结果与后续失败模式见 9.6。

### 9.4 回滚与停止

如果公开回归退化、hard-safety 出现未知或错误放行、候选 Trace 不能证明真实检索改变，立即删除候选 profile，恢复上一版 baseline。若连续两代没有新的真实预测变化，停止在该层补丁，转向知识覆盖或输入理解审计。当前 operation coverage 候选公开检索指标无退化，故保留为 proposal-only 诊断分支，尚未 promotion。

### 9.5 V3/V4 双轨基线回执

公平过程门通过后，V3/V4 答案键只在内存按哈希与封存的 answerless 运行连接一次，输出 `rag_fair_gold_join_v2` 聚合。V3 真实检索 Recall@5=`34.72%`、Evidence relation=`16.67%`；V4 分别为 `41.32%`、`24.65%`；两代 hard-safety 均 PASS、质量未通过。连接结果用于区分“自然语言理解失败”和“真实召回/关系失败”，不能回写 Holdout 或继续按 case 调参。V5 已由负责人审核后完成一次授权 Gold join，当前聚合结果见 9.6。
### 9.6 V5 Gold join 后的失败分析 SOP

负责人授权后，V5 只做一次 Gold join；结果为聚合诊断，不把 V5 题目变成训练样本。当前观察到的顺序是：

```text
过程完整性/治理先过
→ 聚合评分，不输出题目与答案
→ 分离理解、召回、关系、路由错误
→ 形成一个候选修正假设
→ 只在公开开发/回归集验证
→ 安全或回归退化就回滚
→ 泛化需要新 V6，不重跑 V5
```

V5 的聚合根因是：路由不一致 `50/60`、证据集合不一致 `59/60`、关系不一致 `54/60`，而前五条
完全 miss 只有 `2/60`。因此下一轮优先修“意图到路由的传递、按操作分配证据、关系规则化”，不再
机械增加 Top-K。特别禁止三种 Goodhart 操作：改结果整理层冒充候选变化；用无关证据抬 Precision；
在已经看过答案的 V5 上反复试错。

本轮 SOP、聚合失败分析、registry/看板与测试同步后的全量工程 QA 为 `220 passed, 4 warnings`；Ruff check、
format、compileall 与 `git diff --check` 均通过。该回执证明流程可复核，不代表 V5 质量 Gate 通过。
