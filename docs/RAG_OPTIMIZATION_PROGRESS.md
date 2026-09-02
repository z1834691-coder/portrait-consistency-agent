# RAG 优化进展与自动迭代记录

> 版本：`v0.1`｜日期：2026-09-01  
> 用途：记录从 v3 baseline 失败模式到候选迭代的真实过程。它是当前优化实验账本，不是“RAG 已上线”的证明。

> **2026-09-02 当前覆盖：**V4 已按后文完成独立盲测和授权后的 validation 诊断；文中“待建立独立 v4”的句子属于 V4 创建前的历史快照。当前 V4 project Gate 仍为 `FAIL`，候选未 promotion；再次验收必须使用未参与 V4 诊断的新 Holdout。

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

V0 逐题事实统计为：`route_mismatch=24`、`evidence_relation_mismatch=23`、`evidence_set_mismatch=18`、`rank_mismatch=10`；另有 28 条 `metric_sparse_gold_denominator`，它是评测口径提示而非检索器缺陷。错误码可以重叠，不能相加当作独立坏题。V2 之后 22 条预测事实相对 V1 发生改变，从 V0 到终态共有 24 条 Prediction 事实发生改变；开发集的 route/relation/recall@5 达到 100%。这证明候选修复触达了正确层，但因数据集/annotations 尚待产品负责人审核，不能当正式发布 Gate。逐题对照见 [RAG_FAILURE_CASE_REVIEW_V2.md](RAG_FAILURE_CASE_REVIEW_V2.md)。

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

停止原因：V3/V4 连续两代 Composite 增益 `<0.01`，且 public regression 的固定 Precision@3 仍导致 project Gate=`FAIL`，所以没有继续堆下游补丁。所有候选 Trace 的 `network_called=false`、`llm_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`，anti-overfit=`PASS`。V2 仍只是 owner-review development evidence，不改变现役 P0-A/P0-B/P0-C。报告同时保存 `final_candidate_diagnostics`，使 V0/终态差异可逐题复盘。

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
- 逐题复盘：[RAG_FAILURE_CASE_REVIEW_V2.md](RAG_FAILURE_CASE_REVIEW_V2.md)

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
  uv run python scripts/run_rag_optimization_loop.py \
  --private-aggregate /path/to/v3_holdout_blind_aggregate.json
```

当前报告只把 v3 aggregate 作为上下文；不传 `--private-aggregate` 也可以完整运行 public loop。

## 8. 2026-09-02｜V3 解冻后的验证优化（当前最新）

产品负责人明确允许读取已审核 V3 题目和答案，因此本轮不再把 V3 当作“不可逐题读取的 Holdout”，而是使用单独的 validation 副本做失败模式分析；原始一次性盲测快照保持不变、不重跑。新增 `scripts/prepare_v3_validation_package.py`、`services/rag_v3_validation_diagnostics.py` 和 `scripts/run_rag_v3_validation_diagnostics.py`，产出 36 题逐题结论、根因、SOP、G0–G5 完整 Trace、JSON/HTML 和 page 5 看板。

| 代次 | 实际处理 | V3 Route | V3 Relation | V3 Recall@5 | Public regression | 结论 |
|---|---|---:|---:|---:|---:|---|
| G0 | 原 baseline | 30.56% | 23.61% | 59.72% | 基线 | 失败起点 |
| G1 | v0.1 查询编译 | 58.33% | 52.78% | 77.78% | 退化 | 不采纳 |
| G2 | v0.2 policy-first 编译 | 100% | 100% | 100% | 退化 | 不采纳，验证过拟合 |
| G3 | public regression guard | 100% | 97.22% | 100% | 保持基线 | 保守候选 |
| G4/G5 | 下游关系/打包检查 | 100% | 97.22% | 100% | 保持基线 | 0 改变，停止 |

V3 的最终失败只剩 1 条 `evidence_relation_mismatch` 和 36 条 `metric_sparse_gold_denominator`；后者是固定 Precision 口径提醒，不是检索缺陷。最终固定 Precision/project Gate 仍 `FAIL`，hard-safety `PASS`，active baseline 未改变。报告中的 `hidden_answer_key_read=true` 仅表示这次负责人授权的离线 validation 诊断，不是在线流程，也不构成正式 Holdout 通过。完整报告见 `reports/rag_v3_validation_diagnostics_v1.json/.html`；推广仍需新建独立 V4 Holdout。
## 2026-09-02｜V4 独立 Holdout 优化闭环（当前）

V3 已成为负责人授权的 validation，不能继续作为独立泛化证明。本轮先冻结 48 道与 V3 不重叠的 V4 题目，使用无答案运行包完成一次 baseline 盲测；快照封存后才生成私有聚合和逐题诊断。这样可以把“真实考试成绩”和“看答案后的错题练习”分开。

| 代次 | 修正位置 | Route | Evidence relation | Recall@5 | 固定 Precision@3 | 状态 |
|---|---|---:|---:|---:|---:|---|
| G0 | V4 独立 baseline | 12.50% | 18.75% | 57.99% | 28.47% | 真实盲测基线 |
| G1 | 复用 v2 查询编译 | 41.67% | 46.88% | 65.97% | 33.33% | validation 候选 |
| G2 | V4 通用同义词 + 策略/权限优先查询编译 | 100% | 100% | 100% | 51.39% | validation 候选，不 promotion |
| G3 | 回归守门确认 | 100% | 100% | 100% | 51.39% | 无新增改变 |
| G4 | 关系归一化 | 100% | 100% | 100% | 51.39% | 无新增改变 |
| G5 | 证据打包 | 100% | 100% | 100% | 51.39% | 无新增改变，停止 |

G2–G5 的 100% 只属于 owner-unlocked validation；fixed Precision 的低值来自 Gold 稀疏（47/48 题少于三条证据），不是允许通过增加无关证据抬分的理由。effective/returned Precision 作为诊断口径并列展示，冻结的 project Gate 仍 FAIL。

本轮候选改变了真实的“自然语言→查询投影”判断，而不是只改最终答案文字；所有代次都保持 `active_baseline_changed=false`、`proposal_only=true`，没有读取照片/向量、调用网络/LLM/Provider 或写入图片执行合同。G3–G5 连续无新增预测变化，按停止规则达到边际效益递减，未继续堆补丁。

详细题集和盲测/诊断边界见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。

## 9. 2026-09-02｜多轮低成功率反思审计：先确认测量对象，再继续优化

本轮没有继续新增 Holdout，也没有读取新的隐藏答案。原因是连续几轮的低分可能来自不同层：用户原话没有被整理成检索请求、知识库没有对应规则、检索器没有召回、证据关系判断错误，或者评测分母本身不可达。若不先拆开这些层，下一轮分数无法说明改动究竟解决了什么。

独立审计只读取公开代码、V4 answerless 聚合与 Trace、公开失败驱动 Loop 和生命周期摘要。事实为：V4 48 题中只有 8 题生成了结构化检索请求，40 题在检索前结束；当前知识库为 3 张审核卡、10 条有效规则；离线盲测使用确定性词元 fixture，不等于线上 BGE 语义模型；V4 fixed Precision@3 的理论最高值约为 51.39%，而冻结门槛是 80%。因此 V4 的 Route/Relation 低分首先说明上游查询编译和评测边界不足，不能直接说“向量检索只有 12.5% 的能力”。

本轮形成三个待产品负责人确认的下一 Gate：

1. 将“自然语言→结构化查询”和“结构化查询→真实检索”拆为两条指标与数据轨道；每条证据必须来自真实可索引 chunk，禁止评测投影预先注入证据别名。
2. 将隐私、出站、过期、撤回、冲突、提示注入和人工复核等事实整理为版本化、可审核的 Policy/Rule Card；没有入库的内容不能被计为 RAG 已召回。
3. 用 10—15 道公开 smoke 先验证每题都留下“原话→结构化查询→召回→采用证据→路由”Trace，再决定是否校准 Precision 口径、加载真正的本地模型或新建下一份 Holdout。

这是一份反思与工程证据，不是质量通过。RAG 仍为 proposal-only，active baseline 未改变，V4 project Gate 仍为 `FAIL`。可复核材料见 [RAG 低成功率反思审计](RAG_LOW_SUCCESS_REFLECTION_AUDIT.md)、`reports/rag_low_success_reflection_audit.json` 和 `reports/rag_low_success_reflection_audit.html`。

本轮最终交叉校验：`.venv/bin/pytest -q`=`193 passed, 4 warnings`；Ruff check、format（188 files）、compileall、`git diff --check` 和 `audit_rag_low_success.py` 均通过。4 条 warning 为既有 Pillow 弃用提示；该工程回执不改变 V4 project Gate=`FAIL`、RAG `proposal-only` 或 active baseline 未改变。
