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

## 3. 每道公开题如何分析

`reports/rag_optimization_loop_v1.json` 的 `baseline.case_diagnostics` 为 52 条逐题记录。每条只保存：`case_id`、`split`、标签、题干 SHA-256、预测证据数量、Gold 证据数量和结构化错误代码，不保存原始题干。

本次逐题结果：

- 51 题：`status=metric_sparsity_only`，唯一代码为 `metric_sparse_gold_denominator`；这不是检索器漏召回，也不是路由错误；
- 1 题：`status=pass`，没有失败代码；
- public 逐题没有 `route_mismatch`、`evidence_set_mismatch` 或 `evidence_relation_mismatch`，所以本轮没有按 case ID 写规则补丁；
- v3 只能记录 aggregate pattern，不能输出隐藏题 ID 或逐题诊断。

## 4. 自动化候选代次

| 代次 | 做了什么 | 结果 | 是否推广 |
|---|---|---|---|
| V0 | 当前 deterministic baseline 参照 | Composite `0.947436`，project Gate=`FAIL` | 现役参照 |
| V1 | 审核过的中英/领域同义词归一化（`rag-correction-candidate-v0.1`） | Composite 增益 `0.0`；安全和可比指标无回退 | 否，proposal-only |
| V2 | 已审核 relation 别名 canonical 化 | Composite 增益 `0.0`；安全和可比指标无回退 | 否，proposal-only |
| V3 | evidence 稳定去重/最多 5 条 | 未运行：连续两代增益 `<0.01` | 按停止规则跳过 |
| V4 | 冲突/空证据 fail-closed 路由 | 未运行：连续两代增益 `<0.01` | 按停止规则跳过 |

Composite 的权重和 project Gate 见 [RAG 优化 Rubric](RAG_OPTIMIZATION_RUBRIC.md)。V1/V2 的 Trace 均确认 `network_called=false`、`provider_api_called=false`、`llm_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`；反过拟合检查为 `PASS`。

## 5. 完整可回放链路

```text
public cases + public annotations + baseline predictions
→ V0 baseline 评测
→ 每道题生成结构化 failure code
→ V1 同义词候选回归
→ V2 relation 候选回归
→ Composite / project Gate / hard-safety 对照
→ anti-overfit 检查
→ 连续两代低增益，停止 V3/V4
→ JSON + HTML + page 5 看板
→ 产品负责人批准 / 回滚（本轮未推广）
```

## 6. 结论

本轮已经把 SOP 从“文字流程”变成真实可运行的 proposal-only loop，并把 52 道公开题逐题归因。它成功证明：候选可以安全运行、过程可追溯、没有越权；但没有产生质量增益，project Gate 仍为 `FAIL`。这不是失败隐藏起来，而是说明当前公开集已经不能提供修正 v3 泛化问题所需的新监督信号。

下一步要提升真实质量，必须先增加经过人工审核的独立表达/组合数据，并新建 Holdout v4；不得重复使用 v3 逐题答案。只有在新数据上候选稳定通过安全和质量门，产品负责人批准后，才可考虑把某一候选升级为 active。

## 7. 产物与命令

- 代码：`src/portrait_consistency_agent/services/rag_optimization_loop.py`
- 运行器：`scripts/run_rag_optimization_loop.py`
- JSON：`reports/rag_optimization_loop_v1.json`
- HTML：`reports/rag_optimization_loop_v1.html`
- 看板：`pages/5_RAG优化看板.py`
- SOP：[RAG_FAILURE_ANALYSIS_SOP.md](RAG_FAILURE_ANALYSIS_SOP.md)
- Rubric：[RAG_OPTIMIZATION_RUBRIC.md](RAG_OPTIMIZATION_RUBRIC.md)

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_optimization_loop.py \
  --private-aggregate /path/to/v3_holdout_blind_aggregate.json
```

当前报告只把 v3 aggregate 作为上下文；不传 `--private-aggregate` 也可以完整运行 public loop。
