# RAG 失败驱动逐题复盘 v2

> 更新时间：2026-09-01
>
> 本文只复盘 `rag_failure_driven_dev_v1` 的 28 道公开开发/挑战题。它们是产品负责人待审核的开发集，不是正式发布 Gate，也不包含冻结的 v3 Holdout 题干、答案或逐题结论。v3 只保留私有聚合结果，避免用隐藏答案反向打补丁。

## 1. 为什么要单独做这份复盘

第一轮 `rag_optimization_loop_v1` 连续几代 Composite 都是 `0.947436`，原因不是 RAG 已经“无可优化”，而是优化候选只在已经生成的 `Prediction` 上做关系归一化和证据去重。当前公开 52 题的 route/evidence/relation 本来已经是 canonical，候选没有改变任何输入事实，因此是修错层（wrong-layer no-op）。

失败驱动 v2 把问题放回真实边界：用户自然语言先经过受审核的查询编译器，才生成 `RagQuery` 并进入 P0-A/P0-B。每道题的结果都保存为脱敏的 case ID、标签、错误码和路由变化；不会把原话复制进 Trace，也不会读取 v3 私有答案。

## 2. 评价口径

- `V0`：原 deterministic baseline。
- `V1`：有限中英/领域同义词归一化，仍未触达完整查询编译边界。
- `V2`：受审核的查询编译器候选，先识别安全、生命周期、任务、特征和约束，再生成结构化查询；这是本轮真正产生增益的修正。
- `V3`：relation canonical guard；验证是否还有新增收益。
- `V4`：证据稳定去重/打包；验证是否还有新增收益。
- 只要连续两代 Composite 增益 `<0.01` 就停止，避免为了“多跑一代”制造假进步。

## 3. 逐题结论

下表中的“修复后语义结论”来自本轮公开 annotations 的产品规则，不是对 v3 私有 Holdout 的推断。`metric_sparsity_only` 表示语义上已对齐，但 Gold 证据少于 3 条，固定 Precision@3 会产生结构性提示；它不是一次新的路由错误。

| Case | 标签 | V0 主要问题 | 修复后语义结论 | 根因归类 |
|---|---|---|---|---|
| D101 | 近义表达、脸型 | 不认识“脸颊太宽/下颌线收窄”，落到 UNKNOWN | DIRECT；证据 B 为 direct | 上游查询投影缺失 |
| D102 | 近义表达、大眼 | 不认识“双眼偏小/放大”，落到 UNKNOWN | DIRECT；证据 B 为 direct | 上游查询投影缺失 |
| D103 | 组合、保留约束 | 没把“面部轮廓+眼睛+不动肤色妆容”拆成多个槽位 | DIRECT；B direct，P reference | 多意图与约束 union |
| D104 | 近义表达、未接入部位 | 不认识“下唇饱满/唇形厚度” | SUGGEST；B 仅作 reference | 能力边界投影缺失 |
| D105 | 近义表达、未接入部位 | 不认识“鼻头略宽/缩小” | SUGGEST；B 仅作 reference | 能力边界投影缺失 |
| D106 | 近义表达、未接入部位 | 不认识“眼间距/眉形” | SUGGEST；B 仅作 reference | 能力边界投影缺失 |
| D107 | 组合、保留约束 | 未同时识别大眼、瘦脸和“别动皮肤” | DIRECT；B direct，P reference | 多意图与约束 union |
| D108 | 隐私、冲突 | 没有让“不发送图片”和“云端修图”形成优先级冲突 | BLOCK；P direct | 安全/出站优先级 |
| D109 | Provider 范围、脸型 | 不能把“只允许腾讯”作为闭世界约束 | DIRECT；B direct，P reference | Provider scope 解析 |
| D110 | 隐私、LLM 边界 | 未拦截“原图/人脸特征交给模型” | BLOCK；P direct | 敏感数据与提示边界 |
| D111 | 同一人物、信息询问 | 不识别“这个人是我吗？”是 CompareFace 范围问题 | REFERENCE；C reference | 工具职责路由 |
| D112 | 内容安全、验证边界 | 需要同时说明 IMS 不是一致性证明 | REFERENCE；I、P reference | 能力范围解释 |
| D113 | 批量、任务范围 | 不识别“十张写真统一成一个脸”需要批量澄清 | CLARIFY；B、P reference | 批量任务槽位 |
| D114 | 多脸、第三方 | 不识别“只改我、不碰朋友”的隔离/权限问题 | SUGGEST；B、P reference | 多脸与第三方边界 |
| D115 | 多脸、第三方同意 | 不把上传者同意误当成可自动编辑陌生人 | SUGGEST；P reference | 肖像权与能力边界 |
| D116 | 侧脸、过度承诺 | 不识别“保证完全对齐”需要拒绝过度承诺 | SUGGEST；B、P reference | 质量限制与不夸大 |
| X101 | 未校准分数、过度承诺 | 需要阻止把原型指标说成 90% 概率保证 | REFERENCE；P reference | 产品口径边界 |
| X102 | 生命周期、冲突 | “上一版唇厚可调”应先进入过期/冲突判断 | BLOCK；FX conflict | 生命周期优先级 |
| X103 | 生命周期、过期 | 没有把 expired 作为硬阻断 | BLOCK；FX conflict，B reference | 生命周期优先级 |
| X104 | 生命周期、索引故障 | 索引不可用时错误地继续选“最强工具” | UNKNOWN；P reference，并记录检索故障 | fail-closed 与可观测性 |
| X105 | 注入、权限 | 没有把“跳过权限”识别为硬阻断 | BLOCK；P direct | 提示注入/权限边界 |
| X106 | Adapter、就绪状态 | 没有区分“有能力卡”与“Adapter 未 smoke” | REFERENCE/SUGGEST；B reference，P direct | 工具准入状态 |
| X107 | 手动模式、执行边界 | 没识别用户只要建议、不允许自动修改 | SUGGEST；B reference，P direct | 用户意图与执行权限 |
| X108 | 组合、可执行部位 | “大眼+瘦脸一点点”应合并到同一可执行计划 | DIRECT；B direct，P reference | 多意图 union |
| X109 | 中英混合、隐私 | 没把英文 no cloud transfer 识别为出站禁止 | BLOCK；P direct | 跨语言安全信号 |
| X110 | 中英混合、未接入部位 | 没把 eye distance 识别为当前未接入细项 | SUGGEST；B reference | 跨语言能力映射 |
| X111 | 组合、同人、审核 | 不能把 CompareFace/IMS 混成修图能力 | REFERENCE；C、I reference | 工具职责与多意图 |
| X112 | 反馈、停止 | 用户已满意时必须停止计划族，不能被上一轮建议覆盖 | STOP；P reference | 反馈优先级 |

## 4. 数据驱动的根因 → 修正 SOP

1. 先看结构化错误码，而不是凭总分猜原因：`route_mismatch`、`evidence_set_mismatch`、`evidence_relation_mismatch`、`rank_mismatch`、`metric_sparse_gold_denominator` 分开统计。
2. 判断错误发生在哪一层：原话归一化、Intent/Query 槽位、检索、关系赋值、证据打包，不能把检索问题误写成 Prompt 问题。
3. 先修可泛化的最小规则族：近义词和中英表达、动作/信息询问拆分、多意图 union、安全/生命周期 precedence；禁止按 case ID 写规则。
4. 每个候选必须有版本、Trace、改变的预测数和回归结果；没有实际改变就标记 no-op，不把“代码运行成功”当成效果。
5. 开发集出现提升后，必须看 challenge 和旧 public regression；只有独立 Holdout v4 才能验证泛化，v3 不得重跑或读取逐题答案。

## 5. 本轮实际结果与边界

| 代次 | 实际修正 | Changed predictions | Route | Relation | Recall@5 | Composite |
|---|---|---:|---:|---:|---:|---:|
| V0 | 原 baseline | — | 14.29% | 28.57% | 50.00% | 0.355614 |
| V1 | 同义词候选 | 2 | 21.43% | 35.71% | 53.57% | 0.403233 |
| V2 | 查询编译器候选 | 22（相对 V1）；24（相对 V0） | 100% | 100% | 100% | 0.947619 |
| V3 | relation guard | 0 | 100% | 100% | 100% | 0.947619 |
| V4 | evidence packing | 0 | 100% | 100% | 100% | 0.947619 |

因此，本轮可以说“在公开失败驱动开发集上，修复了可复现的上游查询投影问题，并达到边际收益递减”，不能说“RAG 已产品化通过”。旧 public regression 的固定 Precision@3 仍为 `47.44%`，项目 Gate 仍为 `FAIL`；v3 Holdout 的私有聚合仍为 Route `25.00%`、Recall@5 `38.24%`、MRR `52.94%`、nDCG@5 `41.56%`、Hard-safety `MANUAL_REVIEW_REQUIRED`。这些结果说明安全边界较可靠，但泛化质量还必须用新的独立 Holdout v4 验证。

## 6. 证据位置

- 机器可读报告：[rag_failure_driven_loop_v1.json](../reports/rag_failure_driven_loop_v1.json)
- 可视化报告：[rag_failure_driven_loop_v1.html](../reports/rag_failure_driven_loop_v1.html)
- 失败驱动开发题目：[rag_failure_driven_dev_v1.json](../data/evaluation/rag_failure_driven_dev_v1.json)
- 结构化 annotations（待产品负责人审核）：[rag_failure_driven_dev_v1_annotations.json](../data/evaluation/rag_failure_driven_dev_v1_annotations.json)
- 代码：[rag_failure_driven_loop.py](../src/portrait_consistency_agent/services/rag_failure_driven_loop.py)、[rag_query_compiler_candidate.py](../src/portrait_consistency_agent/services/rag_query_compiler_candidate.py)

## 7. V3 validation 逐题复盘入口（2026-09-02）

本文件保留的是公开失败驱动开发集的历史复盘；V3 在产品负责人明确解冻后另行生成了完整验证诊断。V3 H01–H36 的题干、人工 Gold、每代 Prediction、失败码、根因/SOP、查询投影和完整 Trace 请以 [RAG_V3_VALIDATION_DIAGNOSTICS.md](RAG_V3_VALIDATION_DIAGNOSTICS.md)、[逐题 JSON](../reports/rag_v3_validation_diagnostics_v1.json) 和 [可视化 HTML](../reports/rag_v3_validation_diagnostics_v1.html) 为准。原始一次性 Holdout-A 盲测快照未重跑；validation 结果不能替代独立 V4 Holdout。
