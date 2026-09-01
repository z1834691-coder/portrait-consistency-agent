# RAG Gold Set v2 离线评测器

## 它解决什么问题

RAG 能不能找到正确工具资料，不能靠“模型回答得像不像”来判断。评测器把产品负责人审核后的答案键和被测系统的脱敏预测分开，逐题计算证据召回、排序、路由和安全错误，并把开发集/挑战集的错误留给后续迭代。它是离线评分工具，不是线上 Agent，也不替系统决定是否调用工具。

## 输入、输出和边界

| 输入/输出 | 内容 | 规则 |
|---|---|---|
| `data/evaluation/rag_gold_v2_public.json` | 52 道 dev/challenge 题的 `case_id`、`split`、题干和标签 | 不得出现 `gold_*`、`must_not`、答案或运行版本 |
| `data/evaluation/rag_gold_v2_annotations.json` | 独立的 dev/challenge 答案键 | 评分时才读取；不含 H01–H20；不交给被测系统 |
| `data/evaluation/rag_gold_v2_holdout_runtime.json` | 20 道隐藏题的 `case_id`、题干 | holdout 运行器只读这两个字段，不读取答案键 |
| 预测 JSON | `route`、排序的 `evidence_refs`、证据关系、确定性 `observed_events`、白名单机器计时/计数 | 不接受原话、照片、Base64、向量、密钥或 Gold 派生分数 |
| JSON/Markdown/HTML 报告 | 每题结果、Precision/Recall/Hit@K、MRR、nDCG、路由/证据准确率、安全违规数和项目阈值状态 | 缺少预测显示 `pending`，不当作 0 分或通过 |

当前评测器明确保证：不读照片、不调用 DeepSeek/LLM、不调用腾讯或其他 Provider、不下载 embedding、不读取隐藏答案键。预测文件应由独立 runner 从真实 Trace 投影而来；评测器不会从自然语言猜测“是否违规”。

## 指标规则

- `Precision@K`：前 K 条证据中命中 Gold evidence 的比例；
- `Recall/Hit@K`：Gold evidence 是否在前 K 条及命中比例；
- `MRR`：第一条正确证据排名的倒数；
- `nDCG@K`：按排名衡量证据质量（当前答案键采用有/无相关的保守二元相关）；
- `route_accuracy`：预测路由是否落在允许的 Gold route 集；
- `evidence_exact_accuracy`：预测证据集合是否与 Gold 集完全一致；
- `evidence_relation_accuracy`：`direct/reference/conflict` 关系是否标对；
- `hard_safety_violation_count`：确定性 Trace 中观察到的禁止事件与答案键的交集数量；硬安全 Gate 只有在全部题有预测且该数量为 0 时才显示 `PASS`。
- `project_threshold_gate`：只有全部题有预测、硬安全 Gate 通过，且 Recall@5、Precision@3、MRR、nDCG@5、route accuracy、evidence relation accuracy 均达到本项目冻结门槛时才显示 `PASS`；缺预测显示 `PENDING`，任一指标不足显示 `FAIL`。

这些指标分层报告，不能用平均分抵消一次过期知识、冲突、注入或越权调用。

## 怎么运行

```bash
# 生成不含答案的预测模板
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/evaluate_rag_gold_v2.py \
  --emit-template /tmp/rag_predictions.json

# 评分并生成三种本地报告（把模板填成真实脱敏预测后再运行）
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/evaluate_rag_gold_v2.py \
  --predictions /tmp/rag_predictions.json \
  --output /tmp/rag_eval.json \
  --markdown /tmp/rag_eval.md \
  --html /tmp/rag_eval.html

# 仅准备隐藏集输入包；无指标、无答案读取
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/evaluate_rag_gold_v2.py \
  --mode holdout --output /tmp/rag_holdout_input.json
```

## 盲审 Judge 入口

`build_blind_judge_input()` 只给未来 Judge：题干、系统输出、证据摘要和不含 Gold 的机器事实摘要；不传开发标签、Gold route/evidence、实现版本或答案键。`run_fake_judge()` 是离线结构检查器，只能返回“候选人工复核/需要复核”，不能判事实通过。`run_live_judge()` 默认抛出禁用错误，即使显式允许也会提示 Adapter 尚未实现；未来接 DeepSeek/OpenRouter 前必须另建数据出境、脱敏、留存和 Prompt 版本 Gate。

## 一条可回放 Trace（示例）

```text
读 public cases（只取 case_id/query）
→ 读独立 dev/challenge annotations（holdout 模式不执行这一步）
→ 读脱敏 prediction（route + evidence_refs + observed_events）
→ 规范化路由别名并逐题计算排名指标
→ 计算禁止事件交集
→ 输出 JSON/Markdown/HTML；记录 offline_scoring_only
```

## 当前未实现边界

真实 LLM Judge 和任何新 Provider/图片调用仍未实现。当前的 `fake` Judge 只检查结果 JSON 是否缺字段，不能判断事实正确。隐藏集已完成无答案 prediction/trace 运行，且产品负责人已在工作区外的私有目录执行一次**仅聚合**比对：私有答案键在本机内存中解析，开发 runner、正常 evaluator、RAG 索引和报告均不读取它；输出不含题目、case ID、Gold、答案键路径或逐题错误。

当前 baseline 也不是正式用户意图识别器。它仅为评测把**公开题干**临时投影成一个脱敏 `RagQuery`，再调用既有 P0-B/P0-C；原句不会写进 prediction、SQLite Trace 或报告。产品端的自然语言 IntentFrame Adapter 仍是另一条独立链路。

## 2026-08-30 实际基线运行（public 52 题）

新增 `services/rag_gold_baseline.py` 和 `scripts/run_rag_gold_baseline.py`。它在 `public` 模式只接受 `D*` / `X*` 的 answerless dev/challenge 题，在 `holdout` 模式只接受 `H*` 的 `case_id + query` 运行包；没有 annotations、LLM、图片、Provider、网络或私有答案键参数。运行时使用临时 SQLite 索引、已审核的三张 Provider Card、既有 P0-B 本地混合检索和 P0-C advisory consumer，并使用确定性本地 token embedding/reranker；因此不会下载模型权重或读取照片。

实际生成的产物为：

- `reports/rag_gold_v2_baseline_predictions.json`：52 条脱敏 prediction；
- `reports/rag_gold_v2_baseline_trace.json`：52 条无原题的安全 Trace；
- `reports/rag_gold_v2_baseline_evaluation.json` / `.md` / `.html`：与独立 public dev/challenge 答案键的离线评分结果。
- `reports/rag_gold_v2_holdout_baseline_predictions.json` / `_trace.json`：20 条 input-only holdout prediction/Trace；不含 metrics、Gold 或答案键。
- `scripts/score_rag_gold_private.py`：产品负责人本地私有评分入口；必须显式传入 `--private-answer-key` 和输出路径，且只输出聚合指标/错误类型，永不输出题目、case ID、Gold 或私有路径。2026-08-30 已由产品负责人授权运行一次 Markdown 私有 key 的内存解析；生成的汇总 JSON/HTML 没有上述敏感字段。

产品负责人在自己的私有目录保管答案键后，才可本地执行（示例中的路径仅是占位符）：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/score_rag_gold_private.py \
  --predictions reports/rag_gold_v2_holdout_baseline_predictions.json \
  --private-answer-key /你的私有目录/rag_gold_v2_holdout_answers.md \
  --output /你的私有目录/rag_gold_v2_holdout_aggregate.json
```

该命令不应在开发共享工作区或 CI 中执行；私有 key 的路径不会出现在生成的 aggregate JSON 中。

运行事实：52/52 条 public prediction 与 20/20 条 holdout input-only prediction 均可被合同校验；所有运行均为 `hidden_answer_key_read=false`、`annotations_read=false`（baseline runner 本身）、`llm_called=false`、`photo_or_face_vector_read=false`、`external_provider_called=false`、`network_called=false`；P0-C 的 `execution_authorized` 为 72/72 `false`。评分器在**后续独立步骤**读取 public dev/challenge annotations，生成如下公开开发回归指标：

| 指标 | 实际结果 | 冻结门槛 | 本轮解释 |
|---|---:|---:|---|
| 硬安全错误放行 | 0 | 0 | `PASS`；不代表完整产品安全已通过 |
| Route accuracy | 100% | ≥90% | public 开发回归 `PASS` |
| Evidence relation accuracy | 100% | ≥90% | public 开发回归 `PASS` |
| Recall@5 | 100% | ≥90% | public 开发回归 `PASS` |
| MRR | 100% | ≥80% | public 开发回归 `PASS` |
| nDCG@5 | 100% | ≥85% | public 开发回归 `PASS` |
| Precision@3 | 47.44% | ≥80% | 现有固定分母公式下 `FAIL` |
| Project threshold gate | `FAIL` | 全部满足 | 基线未通过，不能作为发布结论 |

这组数仍只是**公开开发/挑战集回归**，不是泛化或产品发布结论。此次修复的是明确可复现的桥接缺口：Provider scope、内容安全/同人/不支持能力的组合、批量/多脸约束、生命周期/索引 fixture、Policy direct/reference 关系与既有 P0-B/P0-C advisory 投影。它没有新增工具权限，也没有让 RAG 变成执行器。

## 2026-08-30 私有隐藏集的实际聚合结果

产品负责人已将 20 条无答案 holdout prediction 与项目工作区外、仅所有者可访问的私有 Markdown 答案键在本机内存中比对。该命令没有调用 LLM、Provider、网络、图片或人脸向量；生成的 [聚合 JSON](../reports/rag_gold_v2_holdout_private_aggregate.json) 与 [可视化汇总](../reports/rag_gold_v2_holdout_private_aggregate.html) 不含题目、case ID、Gold、原始文本、照片或私有路径。

| 项目 | 聚合结果 | 含义 |
|---|---:|---|
| 覆盖题数 / 缺失预测 | 20 / 0 | 运行器能处理所有隐藏输入，不等于答对 |
| Route accuracy | 25.00% | 与公开集 100% 存在明显泛化落差 |
| Evidence exact / relation | 17.65% / 38.24% | 当前稳定规则未覆盖不少未见表达或组合 |
| Recall@5 / MRR / nDCG@5 | 38.24% / 52.94% / 41.56% | 未达到冻结发布门槛 |
| `project_threshold_gate` | `FAIL` | 当前 RAG 基线不能作为通过或上线结论 |
| hard safety | `MANUAL_REVIEW_REQUIRED` | 私有 Markdown 的自然语言 `must_not` 尚未映射成机器事件 ID；不能伪报 `PASS` |

这是一次有效的**泛化诊断**，而不是可用于继续调参的训练信号：隐藏集的逐题答案不会回流。该段记录的是冻结前的历史状态；2026-08-30 已由 Precision C、Holdout A、Safety ID C 关闭这三个评测定义问题。当前只能在 public/dev/challenge 上定位问题；v2 hidden 继续仅作聚合诊断，不得按逐题答案“补规则”。

### 历史评测设计 Gate（已由 2026-08-30 的 Precision C / Holdout A / Safety ID C 覆盖）

当前 evaluator 的 `Precision@3` 固定以 3 为分母；但 Gold Set 中存在大量只有 1 条正确证据的题。按现有公式，即使系统只返回这 1 条完全正确证据，单题 Precision@3 最高也只有 `1/3`。因此冻结的 `Precision@3 ≥ 0.80` 在这些单证据题占比很高时可能数学上不可达，不能单凭本轮 38.46% 就归因为检索器差。

这段是当时尚未决策的候选；现在采用方案 C：保留固定 K 分母，同时并行报告覆盖式和返回式 Precision，并按 Gold 条数分层。当前固定分母 Precision@3 仍为 `47.44%`，覆盖式/返回式为 `100%`，project Gate 仍按固定口径为 `FAIL`；新口径不能自动放宽门槛。下一步可在公开开发/挑战集上做受限改进，v2 hidden 仍不得逐题调参。

## 2026-08-30｜Failure Pattern 分析与自校正回归

本轮在不读取隐藏答案键的前提下新增 `services/rag_failure_analysis.py` 与 `scripts/analyze_rag_failures.py`。分析器读取 public 的 cases/annotations/predictions，以及产品负责人私有评分器输出的**聚合** JSON；它不读取 hidden 题干、逐题 ID、Gold、原始用户文本、照片、人脸向量、LLM 或 Provider。报告中的每个诊断都标出证据级别，避免把聚合推断写成逐题事实。

实际发现如下：公开集 52 题中 51 题的 Gold evidence 少于 3 条，导致固定分母 Precision@3=47.44%，而按返回条数的诊断值=100%；这是指标口径风险，不是自动证明检索器差。隐藏集 20 题仅回流聚合：17 题错误，route mismatch=15、evidence set mismatch=14、relation mismatch=13；只能说明分布外表达/组合与路由泛化需要继续验证，不能据此按隐藏题逐题补规则。私有 hard-safety 因自然语言 `must_not` 尚未转换成 canonical event ID，保持 `MANUAL_REVIEW_REQUIRED`。

### 本轮候选与门槛

`rag-correction-candidate-v0.1` 只测试经审核的领域同义词/中英归一化；它在临时本地 RAG store 中运行，权限、Provider、参数和阈值完全不变。公开回归 route/evidence/relation/MRR/Recall@5/nDCG@5/hard-safety 均无回退，候选 `regression_gate=PASS`，但 project Gate 仍为 `FAIL`，`active_baseline_changed=false`。候选的每项指标差值、网络/Provider 调用布尔值和 Trace 数量都写入 `rag_failure_patterns_v1.json`，可用新版本替换并回滚。

### 迭代 SOP（产品负责人批准前）

```text
冻结事实快照
→ 按指标/召回/证据关系/安全分层定位
→ 一次只提出一个可解释候选修正
→ 公开集安全回归
→ answerless holdout 只回流聚合
→ 产品负责人批准或回滚
```

不得用隐藏逐题答案写规则，不得把 LLM 自评当 Gold，不得降低安全/项目阈值，不得自动升级 Provider 或把 RAG 变成执行器。该流程已由 `tests/test_rag_failure_analysis.py` 覆盖：候选只能 proposal-only，报告不得含 hidden answer material，allow-list 报告集合不会读取任意文件。

## 2026-08-30 冻结后的当前评测口径

### Precision C：三项并行报告

为了保留历史可比性，`precision_at_k` 仍是命中数除以固定 K，并继续作为当前项目 `project_threshold_gate` 的输入。评测器同时输出 `precision_at_k_effective`（命中数 / `min(K, Gold 条数)`）和 `precision_at_k_returned`（命中数 / 实际返回条数），并输出 `precision_by_gold_evidence_count` 分层表。覆盖式指标不能替代固定 Gate，返回式指标不能单独代表检索质量。

公开基线重跑后的事实是：固定 `Precision@3=0.474359`，覆盖式和返回式 `Precision@3=1.0`；其余公开指标保持原结果，`project_threshold_gate=FAIL`。这不是把门槛改宽，而是把“历史门槛”“稀疏 Gold 覆盖”“返回噪声”拆成三个可解释问题。

### 安全事件 ID C：字典 + 产品负责人确认

`core/rag_safety_events.py` 使用 `rag-safety-events-v0.1` 的显式字典把已知历史标签映射为 `RAG_EVT_*`。大小写、空格和连字符变化只做确定性归一化；未知标签不做模糊匹配，直接把 hard-safety 路由为 `MANUAL_REVIEW_REQUIRED`。`data/evaluation/rag_safety_event_catalog_v0.json` 是可人工审核的公开词表；私有 Markdown key 仍不自动猜测，迁移为 machine-normalized JSON 后才可用作正式自动安全门。

### Holdout A：v2 诊断、v3 独立验收

v2 的 H01–H20 和私有 aggregate 保留为历史泛化诊断，不再用于逐题调参；新的 `data/evaluation/rag_gold_v3_holdout_runtime.template.json` 只提供无答案格式，待产品负责人在工作区外独立生成题目和答案。v3 完成前不能写“泛化已通过”。详见 [RAG Gold Set v3 独立 Holdout 保管说明](RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md)。

### 当前审计边界

上述变更只扩展评测的可解释性和保管流程，不改变 RAG `execution_authorized=false`、候选 Provider fail-closed、图片/向量不入库、不调用 LLM/Provider 的离线边界。正式质量报告必须显式传入 predictions；不传预测时的 `pending` 安全默认继续保留。

## 2026-08-30 当前同步

评测器之外新增的 P0-D 生命周期审计不会改变 Gold 题目、答案隔离或评分口径；它只在运行前检查审核知识卡元数据和派生索引 manifest。历史幂等修复快照为 `160 passed, 4 warnings`，当前全量回归为 `173 passed, 4 warnings`；public 固定分母 Precision@3=`47.44%`、project Gate=`FAIL`；v2 holdout 仍只作历史 aggregate，v3 已完成一次性 answerless 盲测且质量 Gate=`FAIL`。生命周期审计通过不等于 RAG 质量通过。

## 2026-09-01 当前状态覆盖

上面的 v3“待审核/模板为空”描述属于历史快照。产品负责人已经审核 v3 的 36 道题，并按 Holdout A 完成了一次正式 answerless 盲测；runtime 只含 `case_id + query`，预测与 Trace 均未暴露答案事实。私有聚合为 Route `30.56%`、Recall@5 `59.72%`、MRR `77.78%`、nDCG@5 `63.81%`、Evidence relation `23.61%`，hard-safety `0/36`、质量 project Gate=`FAIL`。按照“一次性 Holdout”规则，不再用这次逐题结果调参；后续改动只能先在 public/dev/challenge 回归，再建立新的独立 Holdout。

本评测器仍不启用 live LLM Judge；确定性基线和私有聚合只提供质量证据，不会改变 RAG `execution_authorized=false`、工具白名单或图片出站权限。第一位用户的真实 UI 8C 多轮图片回执尚未产生，不能用 fixture 预测替代。

## 2026-09-01 自动优化 Loop 评测接口

`services/rag_optimization_loop.py` 在本评测器之上增加版本化候选运行：V0 使用当前 public baseline，V1/V2 分别只做审核过的同义词归一化和 evidence relation canonical 化。它为每道 public 题输出结构化失败代码，计算 Rubric 指标和诊断 Composite，并检查 dev/challenge 是否都被评分、候选是否联网/调用 Provider、是否读取 hidden 答案以及 active baseline 是否被改变。

v3 的 `evidence_relation_mismatch`、`evidence_set_mismatch`、`route_mismatch` 只以 aggregate 形式进入优化报告；报告另存“观察事实 / 可验证假设 / 下一份 Holdout 证据”，三类计数不互斥，不能据此生成隐藏题逐题规则。正式泛化验收仍需新建独立 Holdout v4。

Composite 不是新的 Gate；project threshold 和 hard-safety 的原有判定保持不变。当前 V0/V1/V2 Composite 均为 `0.947436`，连续两代增益 `<0.01`，所以剩余候选按停止规则跳过。该 loop 不能重复正式运行 v3，也不能从 v3 aggregate 反推出逐题答案；要再次证明泛化，必须建立独立 Holdout v4。

## 2026-09-01 失败驱动评测接口 v2（当前）

上面的自动优化 Loop 章节记录的是第一轮“后处理候选”的历史快照，上一轮 V0/V1/V2 的预测事实没有变化。当前运行器 `scripts/run_rag_failure_driven_loop.py` 改在自然语言→`RagQuery` 的上游边界评测，使用独立的 28 题 owner-review 开发/挑战集，并仍对 public v2 做回归。

当前真实结果：V0 Composite=`0.355614`；V1=`0.403233`（改变 2 条预测）；V2=`0.947619`（改变 22 条预测，route/relation/Recall@5=100%）；V3/V4 各改变 0 条预测，连续两代增益 `<0.01` 后停止。28 题的 failure code、候选版本、指标 delta、Trace 布尔事实和停止原因写入 `reports/rag_failure_driven_loop_v1.json/.html`，page 5 只读展示。

V2 的分数是开发集工程证据，不是正式 Gate；annotations 尚待产品负责人审核，public regression 的固定 Precision@3=`47.44%` 和 project Gate 仍为 `FAIL`。候选没有读取 v3 逐题答案、没有联网、没有调用 LLM/Provider、没有读照片/向量，active baseline 未改变。Holdout A 仍有效；需新独立 Holdout v4 才能验证泛化和讨论 promotion。

本轮最终 QA：全量 pytest=`173 passed, 4 warnings`；Ruff、format、compileall、`git diff --check`、failure-driven Loop 和 P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 均通过。该 QA 不改变质量 Gate 或 Holdout A 隔离。
