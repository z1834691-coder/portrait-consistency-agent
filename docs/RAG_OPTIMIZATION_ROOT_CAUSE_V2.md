# RAG 优化根因与迭代记录（v2）

> 状态：`implemented / proposal-only`。本文记录本轮真实代码、数据和回归结果，不把开发集提升写成 v3 Holdout 泛化通过，也不改变现役 RAG、Provider、权限或六个业务合同。

## 1. 为什么上一轮三代没有任何效果

上一轮的 V0、V1、V2 并没有在“用户问题进入检索器之前”修复失败。V1 只是对已经生成的 `Prediction` 重新做一次同义词归一化；V2 只是把已有的 relation 名称换成 canonical 名称。当前 52 道公开题的 baseline 早已输出 canonical route、evidence set 和 relation，因此这两个候选没有可以修正的对象。

本轮用代码逐条比较后得到：

| 检查项 | 结果 | 含义 |
|---|---:|---|
| V0→V1 route/evidence/relation 改变 | 0 条 | V1 只改变 Trace 标识和临时检索耗时，不改变预测事实 |
| V1→V2 route/evidence/relation 改变 | 0 条 | V2 的 relation 规范化对当前 canonical 输出是 no-op |
| V0 public route/evidence/relation | 100%/100%/100% | 公开集没有提供这三类算法失败样本 |
| public 唯一异常 | 51/52 题 Gold 少于 3 条 | 固定 Precision@3 的分母问题，不是检索器漏召回 |
| v3 Holdout | Route 30.56%、relation 23.61%、Recall@5 59.72% | 只提供 aggregate 失败类型，不能按题调参 |

因此之前“优化了但分数没动”的真正原因有三层：

1. 候选改在了错误的层：改了输出对象，没有改查询理解、路由优先级或证据采用。
2. 公开集过于容易：公开题干覆盖的是 baseline 已知表达，不能代表分布外复合表达。
3. 指标和质量问题混在一起：固定 Precision 的低值主要由 Gold 稀疏分母造成，继续添加证据反而会污染检索质量。

另一个架构事实也必须说清：当前在线 P0-A/P0-B 的输入合同是经过校验的 `RagQuery`，不是原始用户句子；旧 Gold runner 直接用 phrase projector 把题干映射到投影。因此 v3 低分同时暴露了“自然语言→结构化查询”这一上游缺口，不能全部归咎于 FTS、向量或 reranker。

## 2. 本轮采用的正确优化边界

本轮新建 `rag_failure_driven_dev_v1`，由冻结产品规则工程化生成 28 道新表达/组合题，分为 16 道 dev 和 12 道 challenge。它不读取 v3 的题干、逐题答案或答案键；annotations 状态为 `owner_review_required`，在产品负责人审核前只能作为候选开发证据。

新的候选位置是：

```text
用户自然语言（只在内存中）
→ 受审核的领域词表归一化
→ QuerySignals（功能、动作、权限、生命周期、批量、信息请求）
→ 安全/生命周期优先级编译成结构化投影
→ P0-B FTS + dense + RRF + rerank
→ evidence relation 与 route 输出
```

候选不做以下事情：不按 case ID 写规则、不把 LLM/Provider 分数当答案、不读取照片/向量、不调用网络、不发图片、不授予 `execution_authorized`。

## 3. 每类失败模式与修正

### 3.1 上游查询投影漏召回

**问题：** `脸颊太宽`、`下颌线收窄`、`双眼偏小`、英文 `jawline` 等表达没有命中旧的窄词表，P0-B 根本拿不到代表用户目标的结构化槽位，最后只能返回 `UNKNOWN`。

**修正：** V2 使用受审核的同义词/错别字归一化，并抽取 `executable_features`、`unsupported_features`、`subject_match`、`moderation` 等显式信号。词表只覆盖已审核的产品概念，未覆盖的表达仍然保持 UNKNOWN，不由模型猜。

### 3.2 “能不能”与“请执行”混在一句话

**问题：** `能不能把下颌线收窄` 同时有疑问句和动作；旧投影只看到问句，误路由成信息查询。

**修正：** 把“是否想了解”与“是否包含明确动作”拆成两个信号。出现可执行部位和动作词时，执行意图优先；只有没有明确动作时才走 `REFERENCE`。

### 3.3 隐私/权限/提示注入被能力词覆盖

**问题：** `不外发但要云端修图`、`把原图和人脸特征给模型` 仍提到了修图能力；如果先识别能力再处理权限，可能误进工具路径。

**修正：** 固定安全优先级：硬阻断/图片出站限制 → 过期/冲突 → 索引不可用 → 其他能力。`P` 作为 direct policy evidence，路由为 `BLOCK`，不进入图片 Adapter。

### 3.4 生命周期信号与部位信号竞争

**问题：** `上一版说唇厚可调，现在还有效吗` 同时包含“唇厚”和“可调”；旧投影容易先落到 unsupported feature，返回 `B`，漏掉 `FX` 冲突事实。

**修正：** 先处理 expired/conflict/review_due/superseded，再处理 feature。过期走 `BLOCK + FX conflict`；新版替代旧卡走 `DIRECT + B direct + FX reference`；有冲突但无法确认的资料不生成工具能力。

### 3.5 多意图证据集合被压扁

**问题：** `同一个人 + 安全审核` 需要同时返回 `C` 和 `I`；`内容审核通过是否代表一致` 还需要 `P` 解释范围。旧路径通常只建立一个 retriever kind，导致证据集合不完整。

**修正：** QuerySignals 先保存多个工具意图，再用 union 方式组织 evidence；每条证据的 relation 由规则确定，检索只验证知识是否存在，不让一个排序结果覆盖另一条已审核事实。

### 3.6 固定 Precision 不是算法修正目标

**问题：** Gold 只有 1—2 条时，固定 Precision@3 的分母仍是 3，会把准确的短答案记成 33.33% 或 66.67%。

**修正：** 同时报告 fixed/effective/returned Precision，禁止为了抬固定分数补充无关证据。项目 Gate 仍按冻结 fixed Precision 口径；这是评测治理事实，不伪装成 RAG 算法增益。

## 4. 真实迭代结果

运行入口：`scripts/run_rag_failure_driven_loop.py`。每代都重新跑 dev/challenge，并在既有 v2 public 上做回归；结果图表见 `reports/rag_failure_driven_loop_v1.html` 和 Streamlit page 5。

| 代次 | 实际改动 | Composite | Route | Relation | Recall@5 | 相对增益 | 结论 |
|---|---|---:|---:|---:|---:|---:|---|
| V0 | 旧 phrase projector baseline | 0.355614 | 14.29% | 28.57% | 50.00% | — | 失败驱动集基线 |
| V1 | 领域同义词归一化 | 0.403233 | 21.43% | 35.71% | 53.57% | +0.047619 | 有真实但有限增益 |
| V2 | 查询理解 + 安全/生命周期/关系优先级编译 | 0.947619 | 100% | 100% | 100% | +0.544386 | 主要失败模式被修正 |
| V3 | relation canonical guard | 0.947619 | 100% | 100% | 100% | 0 | no-op |
| V4 | evidence 去重/打包 | 0.947619 | 100% | 100% | 100% | 0 | no-op |

V2 在 16 道 dev 和 12 道 challenge 上均达到 route/evidence/relation/排序指标 100%；既有 v2 public regression 每代保持原有 `project Gate=FAIL`，没有把 proposal 候选写入 active baseline。固定 Precision 仍因为 Gold 稀疏而不是 100%，符合当前 Precision C 规则。

“V3/V4 没有增益”这次是有意义的：它们确实比较了输出是否变化，结果为 0 条变化，说明下一步不应继续堆同类后处理补丁。连续两代增益小于 0.01 后停止，达到边际效益递减条件。

## 5. 交叉验证与风险

- `hidden_answer_key_read=false`、`same_v3_holdout_rerun=false`；v3 仅使用 aggregate pattern。
- `network_called=false`、`llm_called=false`、`provider_api_called=false`、`photo_or_face_vector_read=false`。
- 28 道开发集 labels 是基于产品规则的工程草案，仍需产品负责人审核；不能替代独立 Holdout。
- 现役 RAG P0-C 仍 `execution_authorized=false`；候选只影响离线“如何编译查询”的实验输出。
- 真正声明“质量通过”前必须新建独立 Holdout v4，并让它只接收 answerless `case_id + query`，评分在独立环境完成。

## 6. 下一步

1. 产品负责人审核 `rag_failure_driven_dev_v1_annotations.json` 的每道题与答案关系。
2. 审核通过后，再把查询编译器抽象为生产 IntentFrame→RagQuery 的候选模块，而不是直接替换现役 baseline。
3. 生成全新、与 v3 无重叠的 Holdout v4；先跑一次 answerless，再回流聚合指标。
4. 若 v4 通过安全硬门且质量达到冻结阈值，才讨论是否 promotion；否则继续按新失败模式开下一代候选。
