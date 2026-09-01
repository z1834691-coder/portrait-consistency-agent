# RAG 优化进展与自动迭代记录

> 版本：`v0.1`｜日期：2026-09-01  
> 用途：记录从 v3 baseline 失败模式到候选迭代的真实过程。它是当前优化实验账本，不是“RAG 已上线”的证明。

## 1. 背景

v3 Holdout 已按 Holdout A 完成一次正式盲测，质量 Gate=`FAIL`。聚合错误主要是 `evidence_relation_mismatch`、`evidence_set_mismatch` 和 `route_mismatch`。产品目标不是把分数调好看，而是找到可解释、可回滚、不会越权的修正方法，并能在后续新增独立 Holdout 时验证泛化。

同一份 v3 不能再次正式运行，也不能读取逐题答案调参。因此本轮开发只使用公开 v2 的 52 道 dev/challenge 题、公开人工 annotations、baseline predictions，以及产品负责人已经提供的 v3 aggregate。v3 的题干、逐题答案、答案键路径、照片和向量都没有进入本轮运行。

## 2. Baseline 事实

| 范围 | 事实 |
|---|---|
| Public cases | 52（dev 34 + challenge 18） |
| Public route / evidence exact / relation | 均 100% |
| Public Recall@5 / MRR / nDCG@5 | 均 100% |
| Public fixed Precision@3 | 47.44% |
| Public effective/returned Precision@3 | 均 100% |
| Public 逐题异常 | 51/52 题 Gold evidence 少于 3 条，属于固定分母的结构性折损 |
| v3 private aggregate | Route 30.56%、Recall@5 59.72%、MRR 77.78%、nDCG@5 63.81%、hard-safety=PASS |
| v3 主要 aggregate pattern | relation 31、evidence set 21、route 25 |

解释：公开集的“检索/路由本身已正确”与 v3 的“未见表达泛化不足”同时成立。公开集不能提供足够的 route/relation 失败样本来驱动改进；不能用隐藏聚合数字假装知道每道题的根因。

### 2.1 聚合模式的事实、推断与下一份证据

v3 只回流错误类型计数，因此下面的“观察”是聚合事实，“可能原因”是待验证假设，不是逐题答案；三类计数可以在同一道题上重叠，不能相加当作错误题数。

| 模式 | 观察到的事实 | 当前可检验的假设（不是结论） | 下一份独立 Holdout 要补的证据 |
|---|---|---|---|
| `evidence_relation_mismatch`（31） | 返回证据，但 direct/reference/conflict 关系不一致 | 复合问题把能力事实、背景限制和冲突信息压成一个关系；关系词未覆盖 | 逐题 canonical relation 对照、脱敏 relation trace |
| `evidence_set_mismatch`（21） | 最终证据集合与审核集合不完全一致 | 组合意图漏召回部分依据，或把相关但非 adopted 的参考信息带入 | Gold 条数、召回候选、adopted 集合及缺失/多余原因 |
| `route_mismatch`（25） | 最终处理路由与审核路由不一致 | 能力/权限/隐私/执行请求同时出现时，优先级或未知/冲突分支不稳定 | canonical route、关键槽位、冲突标志和拒绝原因逐题对照 |

本表的作用是指导下一份数据怎么设计，而不是让本轮凭聚合数字写 case-specific 补丁。报告和 Dashboard 会同时展示 `aggregate_fact_plus_hypothesis` 标记。

## 3. 每道题如何分析

旧 `reports/rag_optimization_loop_v1.json` 仍作为第一轮历史记录：它的 public 52 题逐题诊断显示 51 题只是稀疏 Gold 分母提示，不能驱动算法修正；v3 仍只有 aggregate，不能输出隐藏题 ID 或逐题诊断。

本轮新建 `data/evaluation/rag_failure_driven_dev_v1.json`（16 dev + 12 challenge）及其待审核 annotations。`reports/rag_failure_driven_loop_v1.json` 的 `baseline.case_diagnostics` 为 28 条逐题记录。每条只保存 `case_id`、`split`、标签、题干 SHA-256、预测/Gold 证据数量和结构化错误代码，不保存 v3 私有题干或答案。

V0 逐题事实统计为：`route_mismatch=24`、`evidence_relation_mismatch=23`、`evidence_set_mismatch=18`、`rank_mismatch=10`；另有 28 条 `metric_sparse_gold_denominator`，它是评测口径提示而非检索器缺陷。错误码可以重叠，不能相加当作独立坏题。V2 之后 22 条预测事实发生改变，开发集的 route/relation/recall@5 达到 100%；这证明候选修复触达了正确层，但因数据集/annotations 尚待产品负责人审核，不能当正式发布 Gate。

## 4. 自动化候选代次（首次 loop，历史快照）

| 代次 | 做了什么 | 结果 | 是否推广 |
|---|---|---|---|
| V0 | 当前 deterministic baseline 参照 | Composite `0.947436`，project Gate=`FAIL` | 现役参照 |
| V1 | 审核过的中英/领域同义词归一化（`rag-correction-candidate-v0.1`） | Composite 增益 `0.0`；安全和可比指标无回退 | 否，proposal-only |
| V2 | 已审核 relation 别名 canonical 化 | Composite 增益 `0.0`；安全和可比指标无回退 | 否，proposal-only |
| V3 | evidence 稳定去重/最多 5 条 | 未运行：连续两代增益 `<0.01` | 按停止规则跳过 |
| V4 | 冲突/空证据 fail-closed 路由 | 未运行：连续两代增益 `<0.01` | 按停止规则跳过 |

Composite 的权重和 project Gate 见 [RAG 优化 Rubric](RAG_OPTIMIZATION_RUBRIC.md)。上表保留的是第一次错误层候选的历史事实；它不能代表本轮失败驱动集的结果。

## 4.1 失败驱动 Loop v2（当前实验）

| 代次 | 候选与修正层 | 改变预测数 | Composite | 增益 | Route | Relation | Recall@5 | 回归/推广 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| V0 | 窄短语投影 baseline | — | 0.355614 | — | 14.29% | 28.57% | 50.00% | active 参照 |
| V1 | 同义词归一化 | 2 | 0.403233 | +0.047619 | 21.43% | 35.71% | 53.57% | proposal-only |
| V2 | 上游自然语言查询编译 | 22 | 0.947619 | +0.544386 | 100.00% | 100.00% | 100.00% | proposal-only |
| V3 | relation guard | 0 | 0.947619 | 0.000000 | 100.00% | 100.00% | 100.00% | 无增益 |
| V4 | evidence packing | 0 | 0.947619 | 0.000000 | 100.00% | 100.00% | 100.00% | 无增益 |

停止原因：V3/V4 连续两代 Composite 增益 `<0.01`，且 public regression 的固定 Precision@3 仍导致 project Gate=`FAIL`，所以没有继续堆下游补丁。所有候选 Trace 的 `network_called=false`、`llm_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`，anti-overfit=`PASS`。V2 仍只是 owner-review development evidence，不改变现役 P0-A/P0-B/P0-C。

## 5. 完整可回放链路

```text
owner-review development dev/challenge + annotations
→ V0 窄短语 baseline
→ 逐题 failure code + 根因归类
→ V1 同义词候选
→ V2 上游 query compiler 候选
→ V3 relation guard / V4 evidence packing 验证是否还有增益
→ Rubric + public regression + hard-safety + anti-overfit
→ 两代增益 <0.01，停止候选
→ JSON + HTML + page 5 可回放
→ 产品负责人审核 / 新独立 Holdout v4 / 批准或回滚
```

## 6. 结论

本轮已经把 SOP 从文字流程变成真正作用于上游查询边界的 proposal-only loop。V2 在 owner-review development set 上带来 `+0.544386` Composite 和 22 条预测改变，说明上一轮“0 增益”确实是修错层导致的；V3/V4 无增益又证明继续在下游打补丁没有价值。安全、active baseline 与权限均未改变，public regression/project Gate 仍为 `FAIL`。

下一步要提升真实泛化，必须先由产品负责人审核这 28 题和 annotations，再按同一 rubric 建立独立 Holdout v4。不得用 v3 私有逐题答案调参；只有新的 v4 在安全硬门和质量门均通过，并经产品负责人批准，才可考虑把 query compiler 候选提升为 active。

## 7. 产物与命令

- 代码：`src/portrait_consistency_agent/services/rag_optimization_loop.py`
- 新查询编译候选：`src/portrait_consistency_agent/services/rag_query_compiler_candidate.py`
- 失败驱动 Loop：`src/portrait_consistency_agent/services/rag_failure_driven_loop.py`
- 开发/挑战集：`data/evaluation/rag_failure_driven_dev_v1.json`、`data/evaluation/rag_failure_driven_dev_v1_annotations.json`
- 失败驱动运行器：`scripts/run_rag_failure_driven_loop.py`
- 运行器：`scripts/run_rag_optimization_loop.py`
- JSON：`reports/rag_optimization_loop_v1.json`
- HTML：`reports/rag_optimization_loop_v1.html`
- 当前 JSON/HTML：`reports/rag_failure_driven_loop_v1.json`、`reports/rag_failure_driven_loop_v1.html`
- 看板：`pages/5_RAG优化看板.py`
- SOP：[RAG_FAILURE_ANALYSIS_SOP.md](RAG_FAILURE_ANALYSIS_SOP.md)
- Rubric：[RAG_OPTIMIZATION_RUBRIC.md](RAG_OPTIMIZATION_RUBRIC.md)

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_optimization_loop.py \
  --private-aggregate /path/to/v3_holdout_blind_aggregate.json
```

当前报告只把 v3 aggregate 作为上下文；不传 `--private-aggregate` 也可以完整运行 public loop。
