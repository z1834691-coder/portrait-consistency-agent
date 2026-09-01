# RAG 迭代评测 Rubric（v0.1）

> 用途：给“失败模式分析 → 候选修正 → 回归 → 是否停止”提供同一把尺子。
> 本 Rubric 是工程评测规则，不是线上用户满意度，也不是把一次小样本结果包装成生产 KPI。

## 1. 先看什么，再看多少分

RAG 是工具知识查询层。它的目标不是让答案看起来更像人，而是把正确的工具能力、限制、权限和失败处理证据交给后续 Agent。评测分成两层：

1. **安全硬门**：任何越权出站、提示注入放行、冲突知识直接放行、未知安全事件被猜成已知，均不能用其他高分抵消。必须是 0 次违规、0 个未知安全标签，才算 `hard_safety_gate=PASS`。
2. **质量门**：在安全门通过后，再看路由、证据集合、证据关系和排序质量。项目冻结门槛仍然使用固定 Precision@3，所以不能用覆盖式 Precision 把历史 `FAIL` 改成 `PASS`。

## 2. 指标的通俗含义

| 指标 | 它回答什么问题 | 当前项目门槛 | 解释 |
|---|---|---:|---|
| Route accuracy | 系统有没有选对“直接回答/建议/阻断/未知”等处理方向 | ≥90% | 这是能否进入正确产品分支的基础 |
| Evidence exact accuracy | 返回的证据集合是否与人工审核集合一致 | 观察项 | 体现有没有漏掉关键依据或夹带无关依据 |
| Evidence relation accuracy | 是否正确区分 direct/reference/conflict | ≥90% | 这是防止把参考信息误当成可执行事实的关键 |
| Recall@5 | 前 5 条里有没有找到该找的证据 | ≥90% | 适合看“有没有漏召回” |
| MRR | 第一条相关证据排得是否靠前 | ≥80% | 体现用户/LLM 是否能很快看到正确依据 |
| nDCG@5 | 前 5 条的整体排序是否合理 | ≥85% | 同时考虑多条证据的顺序 |
| Precision@3（固定） | 前 3 个位置按历史口径有多少命中 | ≥80% | 继续保留，保证跨版本可比；Gold 只有 1—2 条时会产生结构性折损 |
| Precision@3（覆盖式） | 命中数 / `min(3, Gold 条数)` | 诊断 | 说明稀疏 Gold 是否被找全，不替代项目门槛 |
| Precision@3（返回式） | 命中数 / 实际返回条数 | 诊断 | 说明返回列表有没有噪声，不替代项目门槛 |

为什么同时保留三个 Precision：当前公开集 52 题中 51 题的 Gold evidence 少于 3 条。若只使用固定分母，系统即使准确返回唯一正确证据，也会被记成 33.33%；若只改成返回式，又会丢掉历史可比性。因此三种口径并列，不能挑好看的一个当通过证明。

## 3. Composite 只是 Dashboard 的比较分

为了让产品负责人能看 V0→Vn 的趋势，优化看板计算一个加权比较分：

```text
Route 20% + Evidence exact 15% + Evidence relation 20%
+ Recall@5 15% + MRR 10% + nDCG@5 10% + 固定 Precision@3 10%
```

它不是新的发布 Gate。比如当前 baseline 的公共 Composite 约为 `0.947436`，看起来不低，但固定 Precision@3 只有 `47.44%`，所以 project Gate 仍是 `FAIL`。安全门也不纳入“可抵消的平均分”，而是单独硬门。

## 4. 一代候选怎样才算没有回退

每个候选只能改变一个可解释变量，并同时满足：

- dev 和 challenge 都重新运行；
- route、evidence exact、relation、Recall@5、MRR、nDCG@5 和 hard-safety 不低于当前基线；
- 候选 Trace 明确 `network_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`；
- 代码不按 case ID 或 hidden Gold 写特例；
- 不改变 Provider 白名单、参数上限、权限、执行确认或 `execution_authorized=false`；
- 没有产品负责人批准时，候选只在独立 profile 中运行，不能替换 active baseline。

## 5. 什么时候停止自动迭代

当前 loop 使用一个可解释的停止规则：**连续两代 Composite 增益小于 0.01，且没有跨过项目质量门时，停止继续尝试剩余候选。** 这不是把项目宣布为通过，而是避免在没有新证据时继续堆补丁。

首次 proposal-only loop 的结果（保留作历史复盘）是：V0 baseline → V1 同义词归一化 → V2 relation canonical 化，两个候选的 Composite 增益都是 `0.0`；它们只改写了已经生成的结构化 Prediction，没有触达真实的自然语言查询编译边界，因此属于 no-op。后续如果新增独立语料或新的 Gold/holdout，应重新打开一轮，而不是在当前公开集上反复试错。

## 6. 当前结果的正确表述

- public 52 题：route、evidence exact、relation、Recall@5、MRR、nDCG@5 均为 `100%`；固定 Precision@3=`47.44%`，覆盖式/返回式=`100%`，project Gate=`FAIL`；逐题唯一异常是 51 题的 Gold 稀疏分母。
- v3 private holdout：只回流 aggregate，Route=`30.56%`、Recall@5=`59.72%`、MRR=`77.78%`、nDCG@5=`63.81%`、hard-safety=`PASS`，主要错误类型为 relation/set/route。不能从聚合结果推断每道题具体错因，也不能把 v3 逐题答案拿来调规则。
- v3 的三类聚合错误会在看板中显示“事实/假设/下一份证据”三列：假设只用于设计新 Holdout，不用于 case-specific patch；三类计数允许重叠。
- 因此当前结论是“优化闭环可运行、公开集没有回退、隐藏集暴露泛化不足”，不是“RAG 已产品化通过”。若要再次正式验收，必须新建独立 Holdout v4。

## 7. 2026-09-01 失败驱动 Loop v2：真正改变上游输入后的评测

上一轮指标不变的根因已被单独记录：候选只在结果后处理层运行，而线上 P0-B 的输入合同是经过校验的 `RagQuery`。因此本轮新建 28 题、`owner_review_required` 的开发/挑战集，把候选放到“自然语言 → 结构化查询”边界，仍然不触碰 active baseline、Provider、权限或图片。

| 代次 | 实际改动 | changed_prediction_count | Composite | 相对上一代 | Route | Relation | Recall@5 | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| V0 | 旧窄短语投影 baseline | — | 0.355614 | — | 14.29% | 28.57% | 50.00% | 参照 |
| V1 | 已审核中英/领域同义词归一化 | 2 | 0.403233 | +0.047619 | 21.43% | 35.71% | 53.57% | 候选 |
| V2 | 上游查询编译：动作/能力/隐私/生命周期/冲突优先级 | 22 | 0.947619 | +0.544386 | 100.00% | 100.00% | 100.00% | 候选 |
| V3 | relation guard | 0 | 0.947619 | +0.000000 | 100.00% | 100.00% | 100.00% | 无增益 |
| V4 | evidence packing | 0 | 0.947619 | +0.000000 | 100.00% | 100.00% | 100.00% | 无增益 |

V2 的增益是开发集事实，不是产品质量 Gate：该数据集和 annotations 尚待产品负责人审核，且 public regression 的历史固定 Precision@3=`47.44%` 仍使 regression/project Gate=`FAIL`。本轮安全回执为 `network_called=false`、`llm_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`，anti-overfit=`PASS`。停止原因是 V3、V4 连续两代增益小于 `0.01`；这表示当前候选的边际收益递减，不表示 RAG 已通过。

### 7.1 失败代码的正确解释

新开发集 V0 的主要失败代码是 `route_mismatch=24`、`evidence_relation_mismatch=23`、`evidence_set_mismatch=18`、`rank_mismatch=10`；`metric_sparse_gold_denominator=28` 是评测口径诊断，不是检索器缺陷。V2 通过修复上游查询投影、动作/提问歧义和安全/生命周期优先级，使 22 条预测事实发生改变；V3/V4 的 0 条改变证明继续在下游打补丁没有边际收益。

该结果只允许进入开发集 SOP 和下一份独立 Holdout v4 的设计，不允许把 D/X case ID 写进规则，也不允许读取 v3 私有逐题答案来继续调参。
