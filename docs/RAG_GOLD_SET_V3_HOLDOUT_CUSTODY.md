# RAG Gold Set v3 独立 Holdout 保管说明

## 目的

本文件把产品负责人冻结的 Holdout A 方案落成可执行边界：现有 `rag_gold_v2_holdout_runtime.json` 和它的私有聚合结果继续保留，但只作为历史泛化诊断；发布前不再在它上面反复试错。新的 v3 holdout 必须独立构造、独立保管，并在第一次正式验收前不把答案键放进开发工作区。

## 当前状态

| 包 | 用途 | 开发者是否可读答案 | 状态 |
|---|---|---:|---|
| v2 `H01–H20` runtime | 历史基线和趋势观察 | 否 | 仅诊断，不再逐题调参 |
| v3 runtime template | 新独立集的格式模板 | 无答案 | 仍保留为格式模板；不用于本次正式评分 |
| v3 reviewed runtime | 工作区外的 36 道审核后无答案题目 | 无答案 | 已生成并完成一次正式盲测；只含 `case_id + query` |
| v3 reviewed inline / answer key | 与 runtime 分离的产品负责人私有审核材料 | 否 | 已审核并继续受限保管；不被应用、检索器或公开报告读取 |

模板位置：`data/evaluation/rag_gold_v3_holdout_runtime.template.json`。它故意是空题集，不能被误称为已完成的 Holdout，也不会产生通过分数。填充后的运行包只能包含 `case_id` 和 `query`；禁止加入 `gold_*`、`must_not`、答案、标签、实现版本或图片。

## 独立性规则

1. v3 题目不得从 v2 的逐题答案、错误类型或隐藏题干直接改写；可以沿用产品主题覆盖面，但必须重新写表达和组合。
2. v3 的答案键由产品负责人在工作区外单独保管；运行器只接收无答案输入，评分器才在产品负责人本地内存中读取答案。
3. v2 的聚合指标可以用于判断“是否存在泛化风险”，不能作为 v3 的逐题监督信号。
4. 每次正式验收最多运行一次；若要调整规则，先冻结快照、在 public/dev/challenge 回归，再用下一份独立 holdout。
5. v3 发布前必须记录数据版本、生成日期、覆盖维度、保管位置（不写具体私有路径）和产品负责人确认状态。

## 通过前检查

- [ ] 题目与答案键已分离，开发工作区没有答案键；
- [ ] 题目覆盖工具能力、权限、隐私、过期、冲突、提示注入和未就绪 Adapter；
- [ ] 预测文件只含脱敏 route/evidence/observed event/Trace 摘要；
- [ ] 双口径 Precision、Recall@5、MRR、nDCG@5、route/relation 和 hard-safety 口径已固定；
- [x] 私有 `must_not` 已转换为产品负责人确认过的 canonical event ID；未知标签仍保持 `MANUAL_REVIEW_REQUIRED`；
- [x] 聚合报告不含题干、case ID、Gold、答案键路径、照片、向量或密钥。

## 2026-08-30 状态更新

产品负责人已审核通过公开 `rag-safety-events-v0.1` 目录，因此 v3 草案的安全禁项使用 `RAG_EVT_*` canonical ID。v3 草案位于项目工作区之外的受限目录 `portrait-consistency-agent-v3-holdout-owner-review/`，包含题目、分离答案候选和逐题审核表；当前应用、evaluator 和 Dashboard 不读取该目录。它是供产品负责人审核的候选材料，不是已经冻结的 Gold，也没有产生正式分数。

产品负责人完成审核后，保留一份只含 `case_id + query` 的 runtime 输入；答案键继续由产品负责人独立控制，正式验收最多运行一次。若答案键被开发者读取或题目被用于调参，应重新生成下一份独立 Holdout。此前 v2 的 aggregate 仍只作历史泛化诊断。

## 2026-09-01｜审核完成与一次性正式盲测回执

产品负责人已审核 v3 的 36 道题、证据关系、路由和 canonical Safety Event。根据 Holdout A，运行器只读取工作区外导出的 answerless runtime；私有答案键只在产品负责人控制的环境中用于 aggregate-only 评分，未复制回项目工作区。

本次盲测运行回执：`cases=36`、`predictions=36`、`missing_predictions=0`；`hidden_answer_key_read=false`、`llm_called=false`、`photo_or_face_vector_read=false`、`external_provider_called=false`、`network_called=false`。质量 `project_threshold_gate=FAIL`，但 hard-safety `0/36` 违规，安全 Gate=`PASS`。聚合报告已写入私有受限目录，未输出逐题答案、题干、case ID、Gold 或答案键路径。

本次结果只作为一次独立质量证据：Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、Evidence relation=23.61%。不得根据这份 hidden 逐题结果直接补规则；后续只能在 public/dev/challenge 上做可回归改动，并在需要再次验收时建立另一份独立 Holdout。

## 不可夸写边界

即使 v3 已完成一次正式评分，只要质量 Gate 为 `FAIL`，README、简历和面试材料也只能写“完成独立 Holdout 隔离与一次盲测，发现当前 baseline 泛化不足；hard-safety 通过”，不能写“RAG 已通过”或“泛化达到上线标准”。

## 2026-09-02｜产品负责人明确解冻：V3 改为验证集（原盲测快照不变）

产品负责人在完成 v3 审核后明确要求补齐逐题结论、失败模式和完整 Trace，并允许依据 v3 做候选优化。因此，v3 的**新用途**从“独立 Holdout”改为 `validation`；这不是重新运行原盲测，也不是把旧结果擦掉。

- 原始一次性 answerless 盲测快照继续保留在工作区外，作为不可污染的历史证据；本轮没有重跑它；
- `data/evaluation/rag_v3_validation_cases_v1.json` 和 `..._annotations_v1.json` 是从产品负责人已审核材料派生出的明确验证副本，服务于逐题诊断；
- 验证副本允许报告显示题干、Gold、失败码和完整脱敏 Trace，但不被在线 RAG、active baseline 或 Provider 执行链读取；
- 本轮答案键被读取是产品负责人明确授权后的诊断行为，不能再把这份副本称为独立 Holdout，也不能用它证明泛化；
- 任何候选要晋升为产品逻辑，必须先通过 public regression，再用一份与 V3 不重叠的新 V4 Holdout；
- 看板和报告必须同时显示 `owner_unlocked_v3=true`、`historical_holdout_a_snapshot_preserved=true`、`new_independent_v4_required_for_promotion=true`，避免后续把两类证据混称。

本次验证诊断报告为 `reports/rag_v3_validation_diagnostics_v1.json/.html`，其中每个代次都保存 H01–H36 的题干、Gold、Prediction、failure analysis、检索 Trace 和安全布尔事实。它是产品负责人授权的内部诊断材料，不是对外质量承诺。

### 当前解释（2026-09-02）

“答案键不回流开发”仍适用于原始 answerless Holdout-A 运行和在线 RAG；本轮负责人明确授权的 validation 副本是一个不同用途的诊断材料，因此其 annotations 可被离线诊断器读取。两者不能混称：原始盲测结果仍是一次性历史证据，validation 结果只能指导失败分析和候选回归，不能作为新的泛化通过或 promotion 依据。任何 promotion 都需要与 V3 不重叠的新 V4 Holdout。
## 2026-09-02｜V4 独立 Holdout 保管与诊断边界

V3 已在负责人授权后改作 validation，因此本轮新建与 V3 不重叠的 V4。V4 runtime 在工作区只保存 48 个 `case_id + query`，私有答案键、盲测快照和负责人审阅材料位于工作区外受限目录。答案键不进入代码、测试、在线 RAG、Prompt 或公开报告。

### V4 正式盲测回执

盲测最多运行一次，实际 48/48 题完成；运行时未读取答案/annotations、照片/向量、网络、LLM 或 Provider。快照先封存，再由负责人授权的私有 scorer 输出聚合：Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、MRR=81.25%、nDCG@5=63.22%、hard-safety=0/48 PASS、project Gate=FAIL。

### V4 解冻验证

负责人授权后，答案键只供离线诊断器读取，用于逐题 Trace、失败模式和候选查询编译；这份副本不再是独立 Holdout。`blind_snapshot_match=true` 保证诊断没有偷偷换题，`active_baseline_changed=false` 保证候选没有进入现役系统。G2–G5 语义诊断指标达到 100% 不能替代独立泛化证据，RAG 仍 proposal-only。

### 复核入口

完整说明见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)；盲测聚合与 validation 逐题报告分别见 `reports/rag_v4_holdout_blind_aggregate.json/.html` 和 `reports/rag_v4_validation_diagnostics_v1.json/.html`。若要 promotion，必须另建未参与诊断的新 Holdout，而不是重跑 V4。
