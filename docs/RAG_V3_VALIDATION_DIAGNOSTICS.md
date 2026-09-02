# V3 解冻验证集：逐题失败模式、Trace 与 RAG 迭代记录

## 1. 这份文档回答什么问题

V3 最初是一次性、answerless 的独立 Holdout。第一次盲测只能合法返回聚合指标，不能告诉我们 H01 到 H36 每一道题具体错在哪里。产品负责人在 2026-09-02 明确把 V3 **重新分类为验证集**，授权本轮读取已经审核过的题目与答案，用来做失败模式分析和候选迭代；原始一次性盲测文件仍然保存在工作区之外，没有被重跑或覆盖。

因此，本文件和对应报告不是新的独立泛化证据，而是一份“解冻后的验证诊断包”：它把题干、人工 Gold、baseline 预测、每一代候选预测、失败码、根因解释和完整安全 Trace 放在同一个可回放链路里。

## 2. 评测边界与数据来源

| 项目 | 当前规则 |
|---|---|
| 数据集 | `rag-v3-validation-unlocked-2026-09-02`，36 题 H01–H36 |
| 题目用途 | 失败诊断、候选修正、SOP 验证；不再作为独立 Holdout |
| 原盲测快照 | 保留在工作区外；本轮没有重复运行 |
| 答案读取 | 仅因为产品负责人明确解冻而读取已审核 annotations；不进入在线 RAG 或 active baseline |
| 图片/向量 | 不读取照片、Base64、人脸向量或密钥 |
| 外部调用 | `network_called=false`、`llm_called=false`、`provider_api_called=false` |
| RAG 权限 | 仍为 proposal-only；候选不能改 Provider 白名单、权限、参数、执行授权 |
| 下一份独立证据 | 必须新建与 V3 不重叠的 V4 Holdout |

运行包和 annotations 由脚本从产品负责人工作区外的审核材料派生生成：

- `data/evaluation/rag_v3_validation_cases_v1.json`：只含 `case_id + validation split + query`；
- `data/evaluation/rag_v3_validation_annotations_v1.json`：本轮显式解冻后的诊断 annotations；
- `scripts/prepare_v3_validation_package.py`：不修改原始 owner-only 文件；
- `scripts/run_rag_v3_validation_diagnostics.py`：离线运行诊断并生成 JSON/HTML。

## 3. 为什么上一轮三代没有效果

上一轮 `rag_optimization_loop_v1` 连续几代 Composite 都是 `0.947436`，不是因为“模型不够聪明”，而是候选修改了已经生成的 `Prediction` 后处理层。public baseline 的 route、evidence 和 relation 本来已经是 canonical，后处理只是换了表示，实际被评分的事实没有变化，所以 `changed_prediction_count=0`。

V3 的失败发生在更早的地方：用户自然语言还没有被稳定转换成结构化 `RagQuery`/任务路由，系统就已经丢失了“这是能力查询、执行请求、权限限制、冲突、生命周期问题还是反馈停止”。因此本轮把修正前移到“自然语言 → QuerySignals → 受限投影 → P0-B 检索”边界，并要求每代报告真实改变了多少 Prediction。

## 4. G0 → G5 实际迭代结果

| 代次 | 做了什么 | V3 Route | Evidence exact | Relation | Recall@5 | Composite | 改变预测数 | 公开回归 Route | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| G0 | 原 deterministic baseline | 30.56% | 41.67% | 23.61% | 59.72% | 0.429780 | — | 100% | 失败起点 |
| G1 | v0.1 查询编译/有限同义词与动作识别 | 58.33% | 55.56% | 52.78% | 77.78% | 0.629499 | 18 | 71.15% | 有真实增益，但公共回归退化 |
| G2 | v0.2 安全、生命周期、权限、多意图优先级 | 100.00% | 100.00% | 100.00% | 100.00% | 0.950000 | 25 | 61.54% | V3 全部命中，但存在过拟合 |
| G3 | v0.3 公开回归守门：低置信改动回退 baseline | 100.00% | 100.00% | 97.22% | 100.00% | 0.944444 | 1（相对 G2） | 100% | 推荐的保守候选 |
| G4 | 关系字段下游规范化 | 100.00% | 100.00% | 97.22% | 100.00% | 0.944444 | 0 | 100% | no-op |
| G5 | 证据稳定去重/打包 | 100.00% | 100.00% | 97.22% | 100.00% | 0.944444 | 0 | 100% | no-op |

说明：固定 `Precision@3` 在 V3 只有 1–2 条 Gold evidence，因此 G2/G3 的固定值均为 50.00%，不能用它单独判断是否找全；覆盖式和返回式 Precision@3 为 100%。项目 Gate 仍然是 `FAIL`，因为固定 Gate、独立泛化和生产级准入尚未满足。

### 4.1 这次到底解决了什么

G2 触达了之前没有触达的上游根因：

1. 把“脸部收窄/腮帮收/双眼面积”等口语表达映射到审核过的能力槽位；
2. 把“直接执行”和“只是询问能力”分开，不再只看一个“能不能”；
3. 把安全、隐私、出站、未授权 Provider、生命周期和轮次上限放在能力词之前；
4. 保留多意图的证据集合与 `direct_evidence/reference_context/conflict_evidence` 关系；
5. 空召回时返回 UNKNOWN/BASELINE，禁止 LLM 自由补能力。

G3 进一步证明了为什么不能只看验证集：它让 public regression 恢复到 baseline 的 100% 语义指标，只允许显式高置信信号改变已知结果；低置信候选会回退，并在 Trace 里写明原因。

## 5. G0 失败模式的逐题归因

G0 的机器统计（模式可重叠）：

| 失败代码 | 题数 | 直觉解释 |
|---|---:|---|
| `route_mismatch` | 25 | 查询理解阶段没有稳定识别正确任务路由 |
| `evidence_set_mismatch` | 21 | 必要证据漏召回或多带了不应采用的资料 |
| `evidence_relation_mismatch` | 31 | 找到了资料，但 direct/reference/conflict 关系错了 |
| `rank_mismatch` | 8 | 关键证据出现了，但排序不够靠前 |
| `metric_sparse_gold_denominator` | 36 | 评测口径提醒，不是产品错误 |

三类主失败可以在同一题同时出现。例如 H02 同时有 route/集合/关系问题：baseline 只识别到“可执行”，没有把“眼睛面积差异”和对应的背景规则一起带进证据包。

### 5.1 逐题结论如何阅读

报告的 `generations[*].case_diagnostics` 对 H01–H36 每题保存以下信息：

```text
题干
→ 人工 Gold route / evidence / relation / prohibited event
→ 当前代次 Prediction
→ route / evidence exact / relation / rank / safety 分数
→ failure_codes
→ root_cause（机器错误码对应的人话）
→ correction（下一版 SOP 的修正动作）
→ trace（查询投影、信号、检索、证据、守门决策）
```

HTML 展示逐题结论和 Trace 摘要；JSON 保存完整字段。几个代表性案例：

| Case | G0 发生了什么 | 修正后的规则 |
|---|---|---|
| H01 | “脸部收窄”口语被当成无法结构化的 UNKNOWN | 归一化到 `face_lifting`，能力查询取 B 直接证据 |
| H03 | 美白/磨皮请求没有识别为明确部位与范围 | 明确区分“用户请求”与“默认关闭”，保留安全/工具边界 |
| H10 | “只允许腾讯”没有稳定形成 Provider scope | 把闭世界 Provider 限制作为直接策略事实 |
| H14/H17 | 过期与尚未生效规则可能被当成当前能力 | 生命周期先于能力；过期 BLOCK，未生效 UNKNOWN |
| H18/H19 | 冲突来源被当成普通相关资料 | 保留 conflict evidence，权威冲突不自行拍板 |
| H20/H21 | 知识/用户提示注入可能覆盖策略 | 注入只能 BLOCK，不能扩大工具或出站权限 |
| H24 | 空召回时可能让模型自行补答案 | 立即 UNKNOWN，并走已审核 baseline |
| H25 | “腮帮收一点但别修得假”被当成未知词 | 口语同义词归一化 + 自然偏好仅作约束，不生成客观分数 |
| H29/H30 | 复测结果和不满意反馈可能被重写成下一轮参数 | 复测事实只来自结构化结果；负反馈先停当前计划族 |
| H35/H36 | API 成功或超范围字段可能被误当成达标 | 结果必须复测；参数必须经过确定性 0–100 安全校验 |

## 6. 一条完整 Trace（H01 示例）

下面是最终代次保存的脱敏 Trace 的阅读方式。它不包含照片、人脸向量、密钥、原始 Prompt 持久化或隐藏答案路径：

```text
case_id=H01
runner_version=rag-evidence-packing-candidate-v0.1
query_sha256=<题干哈希>
signal_flags={information_request:true, executable_feature_count:1, ...}
compile_projection={
  route: DIRECT,
  category_codes: [reviewed_executable_feature],
  requested_features: [face_lifting],
  allowed_features: [face_lifting],
  evidence_aliases: [B],
  evidence_relations: {B: direct_evidence},
  outbound_allowed: true
}
structured_query_created=true
retrieval_route=evidence_found
retrieval_trace=[
  FTS candidate count / dense candidate count / RRF / rerank / selected knowledge refs
]
prediction_route=DIRECT
evidence_refs=[B]
network_called=false
llm_called=false
provider_api_called=false
regression_guard={decision: accept_candidate or fallback_to_baseline, reason: ...}
active_baseline_changed=false
```

这里的关键不是“模型说自己理解对了”，而是：每个信号、每个证据关系、每个过滤/守门动作都有机器字段，任何候选都不能直接产生图片执行授权。

## 7. 迭代后的 SOP

1. 冻结 G0 事实快照，不覆盖历史报告；
2. 对每题同时看 route、evidence set、relation、rank、hard-safety 和稀疏 Gold 提示；
3. 找到最早发生错误的层：查询投影、召回、融合、重排、关系或路由；
4. 每一代只改一个可解释候选；记录真正改变的 Prediction 数；
5. 先在 V3 验证候选是否修复已知模式，再立即跑 public regression；
6. 任何已知 baseline 被改变，都要通过高置信信号和回归守门；否则回退；
7. 连续两代 Composite 增益低于 `0.01` 且质量门未过，停止下游重复优化；
8. 最终推广前必须用全新的 V4 Holdout，不能把 V3 验证集成绩写成泛化通过。

## 8. 当前结论

- V3 的逐题问题和完整 Trace 已补齐，机器报告可逐题回放；
- G2 证明把修正前移到查询编译层确实能解决 V3 的三类主失败；
- G3 证明公开回归守门可以抑制过拟合，但会牺牲极少量验证集关系分；这是有意的保守取舍；
- G4/G5 没有额外增益，说明继续堆 relation/evidence 后处理已经进入边际效益递减；
- 当前不把 G2/G3 设为 active baseline，RAG 仍 proposal-only，project Gate 仍 `FAIL`；
- 下一步质量门是创建、审核并运行与 V3 不重叠的 V4 Holdout；在此之前不宣称 RAG 产品化通过。

## 9. 产物索引

- [逐题 JSON 与完整 Trace](../reports/rag_v3_validation_diagnostics_v1.json)
- [可视化 HTML 报告](../reports/rag_v3_validation_diagnostics_v1.html)
- [运行脚本](../scripts/run_rag_v3_validation_diagnostics.py)
- [验证集题目包](../data/evaluation/rag_v3_validation_cases_v1.json)
- [验证集 annotations（本轮解冻后）](../data/evaluation/rag_v3_validation_annotations_v1.json)
- [RAG 评测 Rubric](RAG_OPTIMIZATION_RUBRIC.md)
- [失败分析 SOP](RAG_FAILURE_ANALYSIS_SOP.md)

## 10. 2026-09-02 最终工程回执

本报告在本轮重新生成并通过全量一致性检查：V3 validation runner、失败驱动 Loop、P0-A、P0-B、advisory、生命周期审计、8C 和 8C2 smoke 均 exit 0；全量 `.venv/bin/pytest -q` 为 `178 passed, 4 warnings`，Ruff check、`ruff format --check`（138 files）、compileall 和 `git diff --check` 均通过。4 条 warning 是既有 Pillow 弃用提示。

本回执不改变报告中的产品边界：V3 是负责人授权的 validation，不是新的 Holdout；`hidden_answer_key_read=true` 只反映这次离线诊断读取了已授权 Gold，不代表在线读取；RAG 仍 proposal-only，active baseline 未改变，固定 Precision/project Gate 仍为 `FAIL`，正式推广必须使用不与 V3 重叠的 V4 Holdout。

## 2026-09-02｜公平重放后的当前状态

上面的工程数字属于历史验证快照；当前全量回归为 `196 passed, 4 warnings`。V3 validation 副本已被
重新用于无答案过程完整性重放：`36/36` 题均完成合法查询、检索和 finalized Trace，其中 `structured=5`、
`unknown_fallback=31`。这只是过程证据，不能覆盖原始 V3 质量结果或把 validation 叫作新的 Holdout；
若要评分，必须消费已封存的公平运行包并单独连接 Gold。
## 2026-09-02 当前边界

本文件只描述 V3 的 owner-unlocked validation 诊断；它不是新的 Holdout，也不再承担泛化证明。V3 诊断完成后，新的独立质量证据已经转移到 [RAG V4 Holdout](RAG_V4_HOLDOUT.md)。V4 的 answerless blind 运行和 validation 诊断分别在 `reports/rag_v4_holdout_blind_aggregate.json/.html` 与 `reports/rag_v4_validation_diagnostics_v1.json/.html` 中保存。
