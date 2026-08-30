# RAG Gold Set v3 独立 Holdout 保管说明

## 目的

本文件把产品负责人冻结的 Holdout A 方案落成可执行边界：现有 `rag_gold_v2_holdout_runtime.json` 和它的私有聚合结果继续保留，但只作为历史泛化诊断；发布前不再在它上面反复试错。新的 v3 holdout 必须独立构造、独立保管，并在第一次正式验收前不把答案键放进开发工作区。

## 当前状态

| 包 | 用途 | 开发者是否可读答案 | 状态 |
|---|---|---:|---|
| v2 `H01–H20` runtime | 历史基线和趋势观察 | 否 | 仅诊断，不再逐题调参 |
| v3 runtime template | 新独立集的格式模板 | 无答案 | 已创建，尚未填题 |
| v3 answer key | 与 runtime 分离的产品负责人私有文件 | 否 | 待产品负责人独立生成、审核并保管 |

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
- [ ] 私有 `must_not` 已转换为产品负责人确认过的 canonical event ID，仍有未知标签则保持 `MANUAL_REVIEW_REQUIRED`；
- [ ] 聚合报告不含题干、case ID、Gold、答案键路径、照片、向量或密钥。

## 不可夸写边界

在 v3 题目和答案键完成、正式评分并达到冻结 Gate 前，README、简历和面试材料只能写“已建立独立 Holdout 保管与验收流程”，不能写“RAG 已通过”或“泛化达到上线标准”。
