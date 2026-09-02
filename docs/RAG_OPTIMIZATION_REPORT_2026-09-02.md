# RAG 深度优化阶段报告（2026-09-02）

> 这是一份过程与证据报告，不是上线声明。当前 RAG 仍为 `proposal-only`；V5 已完成一次授权聚合但质量 Gate=`FAIL`，不能称为产品化通过。

## 1. 背景

项目已经完成多轮 RAG 迭代，但 V3/V4 的低分仍然暴露出路由、证据关系和召回问题。继续增加题目或重复调整排序，可能只是在追一个分数，并不能说明用户换一种说法后系统也能工作。因此本轮把目标改成：先证明每道题真实走完整条检索链路，再只改一个能改变系统真实判断的变量，最后用一套没参与修正的新题验证是否泛化。

## 2. 审计发现

早期 no-op 的根因是修正发生在结果整理层：预测里的文字或关系被重写了，但真实候选池没有变化。另一类问题是多操作请求中，前几名证据可能被一个操作占满，导致另一个操作的已审核资料没有进入候选。V3/V4 解冻后的高分只能用来诊断，不能当新的泛化成绩；旧 Holdout 快照也不能补写或重跑。

## 3. 本轮处理

1. 冻结 V0 active baseline 和代码/知识/数据版本。
2. 将候选变量放到真实检索层：扩大 sparse/dense 候选池，在有效的 `reviewed_active` 知识中按请求 `(operation, provider)` 保留代表证据。
3. 保留原有 metadata、RRF、重排、证据关系、安全和权限检查；候选不创建知识、不新增 Provider、不改变权限。
4. 每题保存可审计 Trace，包含查询、候选池、采用/排除原因、证据关系、路由来源和候选版本；没有原始照片、向量、答案键或隐藏思维链。
5. 引入独立过程监督：新 Holdout 先只跑无答案流程，过程门通过后才允许单独 Gold join。

## 4. 结果

| 数据层 | 题数 | Evidence relation | Recall@5 | MRR | nDCG@5 | Hard-safety | 结论 |
|---|---:|---:|---:|---:|---:|---|---|
| 开发集 baseline | 28 | 25.00% | 46.43% | 55.95% | 45.80% | PASS | 基线 |
| 开发集候选 | 28 | 100.00% | 100.00% | 100.00% | 99.43% | PASS | 候选改善 |
| 公开回归 baseline | 52 | 15.38% | 39.10% | 41.99% | 35.24% | PASS | 基线 |
| 公开回归候选 | 52 | 100.00% | 100.00% | 93.27% | 95.30% | PASS | 候选改善 |

候选改变了开发集 26 条、公开回归 49 条 Prediction 事实，说明这次不是只改展示文本。公开回归 fixed Precision@3=`46.79%`、effective=`99.36%`、returned=`61.86%`；三种口径保留用于不同解释，不能替代独立 Holdout 或项目 Gate。

## 5. V5 泛化检查

V5 共有 60 道与 V3/V4 不重叠的题，覆盖隐含目标、组合操作、否定范围、隐私/出站、生命周期/冲突、注入、未知 Provider/Adapter、多脸/批量、复测、空召回、跨语言和参数边界。运行器未读取答案、标注、照片、向量或密钥，也未调用 LLM、网络或图片 Provider；60/60 题均产生完整输入、查询、检索、Prediction 和 Trace，过程门为 `PASS`。

答案键仍在工作区外的负责人目录。当前质量状态是 `READY_AFTER_SEPARATE_GOLD_JOIN`，不是质量通过。负责人审核 `v5_holdout_review_form.md` 并明确授权后，才能运行一次聚合评分；评分前禁止用 V5 题目修改规则。

## 6. 失败模式 SOP

```text
先确认过程完整
→ 判断最早失败层
→ 一次只改一个真实变量
→ 开发集 + 公开回归 + hard-safety
→ 比较逐题 Trace 和 changed_prediction_count
→ 新 Holdout 只跑一次 answerless
→ 负责人审核后一次 Gold join
→ 根据泛化结果决定保留、回滚或停止
```

若公开回归退化、安全门出现未知或错误放行、候选没有真实改变检索，立即回滚。若连续两代无真实增益，转向知识覆盖或输入理解，不继续堆同义词。指标不能通过改分母、塞无关证据、按题目写特例或重复跑 Holdout 获得。

## 7. 当前交接

- 候选检索：已实现、已回归、未 promotion；
- 逐题诊断与 SOP：已生成，可在 page 5 看板查看；
- V5 过程门：已通过；
- V5 质量评分：已完成一次负责人授权聚合，project Gate=`FAIL`；
- RAG 产品化：未通过，不能对外宣称；
- 下一步：依据 V5 聚合失败模式在公开集设计候选；需要泛化证明时建立新的 V6，或回到端到端用户测试。

相关入口：

- [RAG 深度优化 Prompt](RAG_DEEP_OPTIMIZATION_PROMPT.md)
- [RAG 优化进展](RAG_OPTIMIZATION_PROGRESS.md)
- [失败分析 SOP](RAG_FAILURE_ANALYSIS_SOP.md)
- [评测 Rubric](RAG_OPTIMIZATION_RUBRIC.md)
- [RAG 决策 Gate](RAG_DECISION_GATE.md)
- [候选 Dashboard](../pages/5_RAG优化看板.py)
- `reports/rag_policy_coverage_candidate_v2.html`
- `reports/rag_candidate_diagnostics_v1.html`
- `reports/rag_v5_holdout_process_audit.html`

## 8. V3/V4 双轨 Gold 连接补充

按公平过程门通过后的规则，已将工作区外受控的 V3/V4 答案键与各自封存的无答案运行包连接一次。连接只在内存中按哈希对齐，报告只保留聚合，不含题目、答案、case 级结论或私有路径。拆分后的基线为：V3 编译 Route=`30.56%`、真实检索 Recall@5=`34.72%`、Evidence relation=`16.67%`；V4 编译 Route=`12.50%`、真实检索 Recall@5=`41.32%`、Evidence relation=`24.65%`；两代 hard-safety 均 PASS，质量均未通过。

这条结果只用于校准“理解问题”和“找资料”的测量对象，不回写旧 Holdout，也不作为继续修改同一题集的输入。该段“V5 仍保持答案未连接”与 `217 passed, 4 warnings` 属于 Gold join 前历史状态；负责人现已授权并完成一次连接，当前回执见第 9 节及本文件末尾。
## 9. V5 Gold join 与失败模式

负责人审核通过后，V5 答案键只在内存与已封存的 60 题 answerless 运行对齐一次。聚合评分为：Route=`16.67%`、
Evidence exact=`1.67%`、Evidence relation=`26.39%`、Recall@5=`73.89%`、MRR=`90.33%`、nDCG@5=`75.36%`，
hard-safety=`PASS`、project quality Gate=`FAIL`。过程监督仍为 60/60 完整且治理干净；这说明“没有作弊”
和“内容正确”是两个不同结论。

失败模式分析报告只保留聚合：路由不一致 50/60、证据集合不一致 59/60、关系不一致 54/60，前五条完全
miss 2/60；33 题没有可靠投影，20 题已有投影却回退 BASELINE。根因不是简单的召回空缺，而是路由传递、
证据操作覆盖和关系标签规则。早期 no-op 与多操作证据挤出问题因此得到可量化的当前证据。

## 10. 交接与下一步

V5 快照已经封存，不在同一题集上反复试错。下一候选先在公开开发/回归集验证“显式意图→路由、按操作
分配证据、来源/能力/生命周期→关系”三项修正；若要证明泛化，必须建立新的 V6 Holdout。无论结果如何，
RAG 继续 `proposal-only`，不自动改变权限、Provider 或 active baseline。

本轮优化报告、V5 聚合失败分析、看板和测试同步后的全量工程 QA 为 `220 passed, 4 warnings`；Ruff check、
format、compileall 与 `git diff --check` 均通过。该回执仅证明工程链路一致，不代表 RAG 已产品化。
