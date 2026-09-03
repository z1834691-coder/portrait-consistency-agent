# RAG 优化任务树 v1

> 这是一棵可回滚的工程任务树。V5 已封存，不能用 V5 题目或答案调参；RAG 继续保持 `proposal-only`，当前 active baseline 不变。

## 目标

让 RAG 的改动真正触达“结构化查询 → 真实候选 → 证据关系 → 最终路径”链路，并用公开开发集、公开回归集和安全测试证明改动，而不是只修改结果文字。

## 监督 Prompt

```text
你是人像一致性 Agent 的 RAG 质量负责人和过程监督者。

先读取并冻结当前 active baseline、知识版本、公开数据版本、评测口径和安全边界。不得读取 V5/V6 隐藏答案或题目做规则特例，不得把 Gold、上游投影或答案别名写入 Prediction。

每次只改一个实际层。第一候选修复“结构化查询提出的路径没有可靠传到最终结果”的断点：只允许在实际检索证据支持时采纳提出的路径；冲突、缺关键槽位、索引异常和无证据必须保守降级。第二候选修复“多个操作共用一个证据篮子”的断点：按请求操作和功能部位分配已审核证据，并把直接依据、参考信息、冲突信息分开。

每个候选必须同时记录：版本、假设、修改文件、真实改变的 Prediction 数、证据引用来源、路由来源、完整 Trace、耗时、成本代理、安全事实、公开开发结果、公开回归结果和回滚方法。候选只能 proposal-only，不得调用图片 Provider、网络或 LLM，不得改变 active baseline、权限或图片出站。

先运行最小 Smoke，再跑公开开发和公开回归，再跑 hard-safety。若安全出现错误放行、公开回归退化、Trace 无法证明真实候选改变，立即回滚。只有候选在公开数据上产生可解释增益且无退化，才可以建议建立一套全新 Holdout；新 Holdout 必须先封存答案、一次无答案运行、过程监督通过，再做一次负责人授权的 Gold join。

指标是证据而不是目标：保留历史 fixed Precision，同时看 effective/returned Precision、Recall@5、Hit@5、MRR、nDCG@5、关系准确率、路由准确率、hard-safety、Trace 完整率、空召回、延迟和成本。不得塞入无关证据、改变分母、降低安全阈值、按题目写特例或重复考试来抬分。

最终以 plain-language 解释交付：问题发生在哪一层、改了什么、真实改变了什么、哪些指标改善/退化、为什么候选仍不能 promotion、下一道产品决策门是什么。
```

## 分阶段执行树

```text
T0 冻结与审计
├─ 保存 V5 聚合基线与 active baseline 指纹
├─ 检查代码/合同/文档/测试一致性
└─ 禁止读取 V5 私有题目和答案

T1 路径交接候选（已完成，proposal-only）
├─ 让结构化查询提出的路径进入受限决策函数
├─ 只在真实检索证据支持时接受
├─ 记录 handoff Trace 与 lineage
└─ 公开开发 + 公开回归 + 安全

T2 证据关系与操作槽位候选（已完成，proposal-only）
├─ 每个功能部位/操作保留自己的证据槽
├─ 具体功能才可标 direct，泛化说明标 reference
├─ 冲突/过期永远不能被当成 direct
└─ 公开开发 + 公开回归 + 安全

T3 选择
├─ 若真实增益且无回归：候选保留为 proposal-only（本轮已完成）
├─ 若退化或无变化：回滚并转向上游查询/知识覆盖
└─ 只有需要泛化证据时才建立全新 V6 Holdout（下一道产品门）

T4 独立泛化 Gate（未来）
├─ 题目/答案与 V3/V4/V5 去重
├─ 一次 answerless 运行
├─ 独立过程监督
└─ 负责人授权后一次 Gold join
```

## 回滚点

- T1 回滚：不传入 `route_handoff`，Prediction 恢复 `route_source=retrieval_result`。
- T2 回滚：不传入 specificity-aware relation resolver，恢复现有 resolver。
- 任何候选都不能改写 V5 历史报告、active Provider Card 或执行权限。

## 本轮执行回执｜2026-09-03｜真实链路候选 v0.4

### 已完成的任务

本轮不是增加题目数量，而是修复 V5 失败分析指出的三个连接断点：

1. `route_handoff`：把结构化查询提出的路径交给一个受限决策层；只有真实检索证据支持时才采纳，硬冲突、缺槽位和索引异常优先。
2. `feature-specificity`：按请求的功能部位整理证据；具体且可执行的能力才是 direct，泛化说明、未请求参数、CompareFace/ImageModeration 只作 reference，过期/冲突保持 conflict。
3. `route-scoped explanation selection`：解释页按当前任务范围选择最多三条已检索资料；缺少范围时仍可检索限制说明，但不会因此越过 CLARIFY 或执行门。

评测器另外修正了一个只影响评分的编号问题：Provider 卡使用带版本的内部引用，Gold 使用稳定别名；现在只在评测层做确定性别名归一化，不增加运行时证据，也不修改 Gold 或 active baseline。

### 当前候选结论

候选只在公开开发集和公开回归集运行，未读取 V5/V6 题目或答案，未调用网络、LLM、照片、向量或图片 Provider。开发集 28 题、公开回归 52 题均完成完整 Trace；三项候选均 `proposal_only=true`、`active_baseline_changed=false`、`execution_authorized=false`。候选确实改变了真实最终路径和采用证据，因此不是早期“只改结果文字”的 no-op。

| 轨道 | 开发集 | 公开回归 | 解释 |
|---|---:|---:|---|
| 路径交接后 Route | 100% | 92.31% | 开发集已接通；回归仍有 4 个已知路径不一致案例，后续由 specificity/证据覆盖继续处理 |
| 解释证据最终 exact/relation | 100% / 100% | 100% / 100% | 只在公开资料范围内按任务范围选证据 |
| 解释证据 Recall@5、MRR、nDCG@5 | 100% / 100% / 100% | 100% / 100% / 100% | 公开候选结果，不代表新问题泛化 |
| 固定 Precision@3 | 47.62% | 47.44% | Gold 证据稀疏下的历史可比口径，仍使 project Gate=FAIL |
| Hard-safety | PASS | PASS | 0 次错误放行；不等于质量通过 |

固定 Precision 低于历史项目门槛，且公开题与当前审核卡高度对齐；因此不能把上述 100% 写成产品化或 Holdout 成绩。T3 结论是“保留候选、停止继续在同一公开集堆补丁”，下一步只有在产品负责人要求泛化证明时才建立与 V3/V4/V5 不重叠的 V6。

### 下一道产品决策门

在进入 V6 前，负责人需要看候选逐题 Trace，确认是否接受“候选已改变真实路由/证据，但固定 Gate 仍 FAIL”的事实。若接受，再设计独立 V6；若不接受，回滚候选并回到最早失败层。无论哪条路，RAG 继续只能提议，不能调用图片工具、授予权限或自动 promotion。
