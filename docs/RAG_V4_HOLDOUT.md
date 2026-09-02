# RAG V4 独立 Holdout 与失败驱动优化记录

> 本文件记录 V4 从出题、隔离、一次性盲测，到负责人授权后的逐题诊断与候选优化。它是当前 RAG 质量证据的一部分，不把验证集成绩写成新的泛化成绩。

## 1. 为什么要做 V4

V3 在负责人审核后被解冻为 validation，用来逐题找错和修复，因此不能再承担“系统面对没见过的问题能否泛化”的职责。为了验证修正是否真的能迁移到新表达，项目重新建立了一套与 V3 不重叠的 V4 Holdout。V4 不只考“能不能找到一张工具卡”，还考工具能力、权限、隐私、主体生命周期、过期和冲突、提示注入、未就绪 Provider、复测策略、批量/多脸、缺槽位、参数边界和用户反馈等组合情境。

V4 的产品目标不是让 RAG 自己修图，而是验证它能否在有限的、已审核的知识范围内提出正确的证据和路由建议，同时在不确定、冲突或越权时安全停下。RAG 仍然是 proposal-only：它可以查资料、整理证据、提出下一步建议，但不能授权图片出站、生成真实参数、调用 Provider 或写入 `ProviderRun`。

## 2. 数据集与保管

| 项目 | 当前事实 |
|---|---|
| 运行版本 | `rag-v4-holdout-runtime-2026-09-02` |
| 题目数量 | 48 道（H401–H448） |
| 工作区输入 | `data/evaluation/rag_v4_holdout_runtime.json`，只含 `case_id + query` |
| 答案键 | 工作区外产品负责人受限目录，运行器和在线 RAG 不可读 |
| 正式运行 | 只运行 1 次 answerless baseline，之后先封存预测与 Trace，再做私有聚合评分 |
| 盲测快照 | 工作区外受限目录保存，权限为仅所有者可读 |
| 题目独立性 | V4 重新撰写并完成与 V3 的覆盖/表达检查，不从 V3 逐题答案生成 |

盲测运行器实际确认：48/48 题都有结果；没有读取隐藏答案、照片、人脸向量、网络、LLM 或图片 Provider。答案键只在正式运行结束、快照封存后由私有评分器用于聚合，不把题干、case ID、Gold 或答案键路径输出到公开报告。

## 3. 正式 V4 盲测：baseline 结果

正式盲测报告为 `reports/rag_v4_holdout_blind_aggregate.json/.html`。这是当前唯一可以用来描述 V4 泛化表现的结果。

| 指标 | 结果 | 解释 |
|---|---:|---|
| Route accuracy | 12.50% | 只有约八分之一的题目把任务路由到正确处理方向 |
| Evidence exact accuracy | 35.42% | 找到的证据集合与人工答案完全相同的比例 |
| Evidence relation accuracy | 18.75% | 找到资料后，把“可直接采用/仅供参考/冲突/必须拦截”等关系判断正确的比例 |
| Recall@5 | 57.99% | 正确证据在前五条结果中被找回的平均覆盖程度 |
| MRR | 81.25% | 第一条正确证据通常排得较靠前，但不代表任务路由和证据关系正确 |
| nDCG@5 | 63.22% | 综合考虑前五条的相关性和排序质量 |
| Hard-safety | 0/48 违规，PASS | 已知安全事件没有错误放行 |
| 固定 Precision@3 | 28.47% | 按冻结的 Precision C 固定分母统计；V4 Gold 多为 1–2 条，分母会显著压低该数值 |
| Project quality Gate | **FAIL** | 未达到冻结的泛化门槛，不能称 RAG 已产品化 |

这里的安全通过不能覆盖质量失败。V4 baseline 明确说明：系统安全拦截方向可靠，但面对新的自然语言组合时，查询理解、证据集合和证据关系仍不足。用等号写成关键摘要就是：`Route=12.50%`、`Evidence relation=18.75%`、`Recall@5=57.99%`，project quality Gate=`FAIL`。

## 4. 解冻后的逐题诊断（不是新的盲测）

产品负责人在盲测快照封存后授权使用 V4 答案做内部诊断。诊断器把同一批题目转换成 validation 副本，并检查封存的盲测预测与诊断输入完全一致（`blind_snapshot_match=true`）。因此它可以回答“每道题为什么错”，但不能回答“面对下一批没见过的题是否也会这样好”。

诊断报告为 `reports/rag_v4_validation_diagnostics_v1.json/.html`，页面 5 的 RAG 优化看板提供只读入口。每道题和每个代次的 Trace 都记录：问题的脱敏哈希、系统抽取的任务信号、查询投影、检索摘要、证据关系、预测、失败码、SOP 修正和安全布尔事实；不记录照片、向量、密钥或隐藏思维链。

### 4.1 失败模式基线

| 失败模式 | 题数 | 直白解释 |
|---|---:|---|
| `route_mismatch` | 42 | 系统没有先理解用户到底是在问能力、要建议、要执行，还是要求拦截 |
| `evidence_relation_mismatch` | 46 | 资料找到了，但没有分清“直接事实、参考信息、冲突信息” |
| `evidence_set_mismatch` | 31 | 找回来的资料集合与人工要求不一致 |
| `rank_mismatch` | 9 | 正确资料存在，但排序不够靠前 |
| `metric_sparse_gold_denominator` | 47 | Gold 证据条数少于 3，固定 Precision@3 的统计提醒，不等于多找了错误资料 |

这些计数可以重叠。一道题可能同时路由错、证据关系错、集合错；不能把它们简单相加成错误题数。

## 5. 失败驱动优化：每一代到底改了什么

候选只改一个可解释层，并同时检查 V4 validation、公开回归、安全硬门和 active baseline 是否改变。候选不自动进入产品逻辑。

| 代次 | 改动 | Route | Evidence relation | Recall@5 | 结果 |
|---|---|---:|---:|---:|---|
| G0 | 正式 baseline | 12.50% | 18.75% | 57.99% | 失败起点 |
| G1 | 复用既有 v2 查询编译 | 41.67% | 46.88% | 65.97% | 有改善，但仍不足 |
| G2 | V4 通用同义词、任务/策略/权限优先编译 | 100% | 100% | 100% | validation 内完全命中；只代表解冻后的诊断结果 |
| G3 | 继续验证上游候选与公开回归保护 | 100% | 100% | 100% | 无新增改变，保留为诊断候选 |
| G4 | 关系归一化 | 100% | 100% | 100% | 无新增改变 |
| G5 | 证据打包 | 100% | 100% | 100% | 无新增改变，达到边际效益递减 |

G2–G5 的语义诊断指标为 1.0，且安全违规仍为 0/48；但固定 Precision@3 仍为 51.39%，项目 Gate 仍为 `FAIL`。这个看似矛盾的结果是因为 V4 的 47 道 Gold 只有 1–2 条证据，固定 K=3 的历史统计口径会把“正确但不足三条”当成未填满的分母。为避免隐藏统计问题，报告同时保留 fixed、effective 和 returned 三种 Precision：候选的 effective/returned Precision@3 为 100%，但不能据此修改冻结的 project Gate。

这次优化的真正价值是定位并修复了实际输入层的问题：系统先把自然语言整理成任务信号，再做检索与证据关系判断，而不是在最后把已经生成的答案文字改写得更像标准答案。它改变了 48 道题的实际路由和证据判断，但因为答案已经被用于诊断，不能将 100% 写成产品质量或泛化通过。

## 6. 当前可执行 SOP

```text
接收用户问题
→ 先判定任务类型、允许范围、出站约束和生命周期状态
→ 在已审核资料中做关键词 + 语义双路召回
→ 用 RRF 合并，再按证据关系和权威级别整理
→ 分开直接证据、参考信息和冲突信息
→ 有直接证据才提出受限方案
→ 只有参考信息时返回“不确定”，采用安全 baseline 降级
→ 有冲突、过期、越权或提示注入时优先停止/人工复核
→ 把检索和路由建议交给状态机、权限策略和 Adapter 再决定
→ 记录脱敏 Trace、失败码和可回滚版本
```

检索不到不是“让 LLM 猜一条”。必须立刻返回“不知道/当前没有可用直接证据”，同时记录是知识库缺资料、空召回、排序过低、版本过期还是冲突未解决。RAG 不能借助相似文字自行增加 Provider、参数、权限或图片出站。

## 7. 当前结论与产品边界

- **已完成**：V4 独立题集设计与隔离；一次性 baseline 盲测；48 道题的私有聚合评分；答案授权后的逐题 Trace；失败模式统计；候选查询编译；公开回归/安全/反过拟合检查；RAG 优化看板和 HTML 报告。
- **已证实**：当前 baseline 的安全硬门为 PASS；V4 新表达下的任务路由和证据关系泛化不足；把修正前移到自然语言→查询投影会带来可观测增益；继续在下游打补丁已经没有增益。
- **未完成**：V4 独立 Holdout 的冻结 project Gate 仍 FAIL；候选未 promotion；RAG 仍 proposal-only；没有因为诊断 100% 就宣称产品化；没有引入真实图片 Provider、LLM 或网络调用。
- **不应夸写**：不能写“RAG 通过”“RAG 已上线”“V4 泛化达到 100%”。准确说法是“完成独立 V4 盲测，发现 baseline 泛化问题；在负责人授权的验证副本上完成失败驱动修正，候选语义指标达到诊断门，但冻结项目 Gate 仍未通过”。

## 8. 可复核入口

- 运行输入：`data/evaluation/rag_v4_holdout_runtime.json`
- 正式盲测聚合：`reports/rag_v4_holdout_blind_aggregate.json`、`reports/rag_v4_holdout_blind_aggregate.html`
- 逐题验证诊断：`reports/rag_v4_validation_diagnostics_v1.json`、`reports/rag_v4_validation_diagnostics_v1.html`
- 诊断脚本：`scripts/run_rag_v4_validation_diagnostics.py`
- 私有评分器：`scripts/score_rag_v4_holdout_private.py`
- 候选查询编译：`src/portrait_consistency_agent/services/rag_v4_query_compiler_candidate.py`
- 测试：`tests/test_rag_v4_validation_diagnostics.py`
- 可视化：Streamlit page 5「RAG 优化看板」和报告注册表

## 9. 运行与验证命令

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache \
.venv/bin/python scripts/run_rag_gold_baseline.py --mode holdout \
  --holdout-runtime data/evaluation/rag_v4_holdout_runtime.json \
  --predictions-out reports/rag_v4_holdout_blind_predictions.json \
  --trace-out reports/rag_v4_holdout_blind_trace.json

.venv/bin/python scripts/score_rag_v4_holdout_private.py

.venv/bin/python scripts/run_rag_v4_validation_diagnostics.py

.venv/bin/pytest -q tests/test_rag_v4_validation_diagnostics.py
```

正式盲测命令只能在新 Holdout 上使用一次；诊断命令只能在快照封存、负责人明确授权后使用。任何未来 promotion 必须用一套没有参与诊断的新 Holdout 再验证。

## 10. 最终工程校验

本轮完成后全量 `.venv/bin/pytest -q` 为 `189 passed, 4 warnings`；V4 专项测试为 `8 passed`；Ruff check/format、compileall、`git diff --check` 和 V4 diagnostics runner 均通过。4 条 warning 是既有 Pillow 弃用提示。这只说明代码、合同、测试、报告和看板可以共同运行，不改变 V4 project quality Gate=`FAIL` 或 RAG proposal-only。

## 11. 2026-09-02｜低成功率反思审计后的当前工程快照

反思审计专项测试加入后，当前全量 `.venv/bin/pytest -q` 为 `193 passed, 4 warnings`；V4 专项仍为 `8 passed`，Ruff、format（188 files）、compileall、`git diff --check` 和 diagnostics runner 均通过。该工程快照不改变 V4 blind baseline 的指标、validation 仅作诊断、project Gate=`FAIL` 或 RAG `proposal-only` 的边界。

## 12. 2026-09-02｜公平过程监督后的当前覆盖

上面的 193 条属于历史快照；当前全量 QA 为 `196 passed, 4 warnings`，公平过程监督专项为 `3 passed`，
并且 P0-A/P0-B/advisory/lifecycle/8C/8C2 及其余离线 smoke 均通过。新版 V3/V4 answerless 重放分别
覆盖 `36/36`、`48/48`，过程门均 `PASS`；它们可以进入独立 Gold 连接，但尚未产生新的质量分数。
旧 V4 正式快照的过程门仍 `FAIL`，其质量状态永久锁定。V4 的 blind baseline 和 project Gate=`FAIL`
不变，RAG 仍 `proposal-only`；这一步只证明评测流程完整和可审计。
