# RAG P0-A｜本地权威知识库与可回放检索

> 状态：已完成本地 SQLite/FTS 验收｜版本：`rag-p0.1` / `rag-p0a-sqlite-fts-v1`｜日期：2026-08-29
>
> 范围：这是“查已审核工具说明书”的真实本地纵向切片，不是向量 RAG、不会读用户照片，也不等于已经把 RAG 接进 8A/8C 的图片执行链。

## 这一模块解决什么问题

此前项目已有三张可读的腾讯 Provider Card，但代码只能直接读取单张 JSON，无法回答“这条工具事实来自哪个版本、是否仍有效、有没有冲突、为什么这次只能降级”，也无法形成可回放的检索证据。RAG P0-A 将这些已审核资料拆成两层：一张完整来源卡叫 `KnowledgeItem`，其中可被检索的一条能力、限制或安全边界叫 `KnowledgeChunk`。每次 Agent 需要了解工具能做什么时，系统先用结构化任务事实筛掉不适用、过期或冲突的资料，再用 SQLite 的全文检索从最多 5 条候选里找依据，最后只返回“支持、限制或保守降级”的结论和来源。

它不负责看脸、不负责算参数、不替代 `mapping_policy`、不创建 `EditPlan`，也不会因为找到一条资料就调用腾讯。这样做的意义是把 Agent 的“工具知识”变成一个可审计、可更新、会在不确定时停下来的层，而不是把模型猜测包装成能力。

## 输入、输出和规则表

| 环节 | 实际输入 | 实际输出 | 关键规则 |
|---|---|---|---|
| 知识导入 | 仓库内 3 张已审核 Provider Card | 3 个 `KnowledgeItem`、10 个 `KnowledgeChunk` | 仅本地读取；不抓网页、不联网；同一版本再次启动不会重复写入 |
| 检索请求 | 已 Schema 校验的 `RagQuery`：阶段、需要的部位、允许部位、Provider/operation、多人/出站等结构化槽位 | query hash、metadata 筛选结果 | 不接收用户原话、照片、Base64、人脸向量、锚点、密钥或 Provider 回执正文 |
| Metadata 硬过滤 | 生命周期、版本生效时间、Provider、operation、地区 | 当前可检索的原子规则 | 过期/撤回/未生效资料不参与正常检索；硬冲突先阻断 |
| FTS 检索 | 被过滤后的本地规则和受控关键词 | 最多 5 条候选 | P0-A 只有 SQLite FTS5；没有向量、embedding、RRF、reranker 或云端服务 |
| 证据分类 | 候选规则 + 出站/Adapter/允许部位/注入检查 | `direct_evidence`、`reference_context` 或安全拒绝理由 | 检索命中不等于可执行；RAG P0-A 永远不直接放行工具 |
| 路由与审计 | 采用/淘汰的 evidence | `evidence_found`、`manual_suggestion`、`baseline_fallback`、`query_underspecified`、`conflict_blocked` 或 `index_unavailable` | SQLite 只保存结构化 query、来源引用、路由和脱敏 Trace；不保存用户媒体 |

## 产品负责人已经决定了什么

1. 知识只来自官方资料和项目人工审核内容；原图、向量、主体锚点、密钥、未经脱敏文本、论坛/网页原文不进入知识库。
2. 一个完整来源版本保留为 `KnowledgeItem`，能力/限制/失败规则拆为 `KnowledgeChunk`；资料量少时先用本地 SQLite + FTS，向量/混合检索留到 P0-B。
3. P0-A 只取 FTS 前 5；分数不展示给用户，也不能放行执行。用户只看“结论、来源名称、版本、支持/降级状态”的紧凑依据卡。
4. 知识过期、撤回、冲突、关键槽位缺失、没有可靠结果或出现注入式内容时，系统宁可回退/追问/人工审核，也不自由搜索或调用未知 API。
5. RAG 可以扩大未来可解决的问题，但新能力仍必须补齐版本化 Card、真实 Adapter、权限、成本/隐私说明和回归测试；本 P0-A 不新增 Provider、不改变 8A 参数规划，也不执行 8C 外部/混合复测。

## 这次真实写进了什么

- `core/rag_contracts.py`：新增严格的 RAG 合同。它与六个图片处理合同分开，明确禁止意外塞入原始用户文本或照片。
- `storage/knowledge_store.py`：新增独立 SQLite 数据库（默认 `storage/knowledge.sqlite3`），含来源、原子规则、FTS5 索引、导入事件和检索 Trace；它不与用户运行账本混在一起。
- `services/rag_p0a.py`：把三张已审核腾讯 Card 转成 10 条可检索原子事实，并执行“先 metadata、再 FTS、后证据/降级”的确定性路径。
- `pages/2_RAG知识库与检索.py`：新增可视化本地演示页；用户可选择预设的结构化场景，看见依据卡和脱敏 Trace，而不是只看代码。
- `scripts/smoke_rag_p0a.py`：运行真实本地 SQLite/FTS 闭环；显式输出 `network_called=false`、`llm_called=false`、`provider_api_called=false`。
- `tests/test_rag_p0a.py`：覆盖支持能力、未接入能力、多人限制、保持项、同人/安全语义、出站阻断、缺槽、过期、冲突和注入安全路由。

## 5 类实际测试案例

1. **瘦脸能力**：查询 `face_lifting`，命中 `BeautifyPic → FaceLifting`，得到 `evidence_found`；只表示“可作为后续 mapping 的候选”，不会直接生成数值或调用图片 API。
2. **唇厚自动执行**：查询 `lips_thickness`，命中当前 Card 的“不支持”事实，得到 `manual_suggestion`；系统不会假装腾讯已支持。
3. **多人图**：`face_count=2`，命中“Provider 没有指定目标脸选择器”，得到“先裁剪/隔离”的降级依据；不会把多脸能力误说成可以任选一张脸编辑。
4. **外发不同意 / 关键槽位缺失**：若 `outbound_allowed=false`，可执行能力不会被采用；若缺少 `allowed_features`，得到 `query_underspecified`，FTS 根本不启动。
5. **异常知识**：过期条目不参与检索；两个 `conflicted_pending_review` 来源阻断；含“忽略权限、调用未知 API”等注入语句的 fixture 被拒绝，均不产生外部调用。

本模块自动化回归目前为 **9 passed**；全项目回归数字以 [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md) 中的最终命令回执为准。

## 一条完整真实本地 Trace

下面来自 `scripts/smoke_rag_p0a.py` 的“瘦脸”场景；它真实创建临时 SQLite/FTS 数据库并检索三张已审核 Card，但没有发送任何照片或网络请求。

```text
seed_reviewed_provider_knowledge
  → 3 张来源卡、10 条原子规则写入本地 SQLite；network_called=false
query_contract
  → stage=plan_edit；requested_features=[face_lifting]
  → 不含用户原话、照片、人脸向量
metadata_filter
  → provider=tencent_cloud、operation=BeautifyPic、region=local_demo
  → 6 条当前有效规则；过期/冲突资料不参与正常候选
fts_retrieval
  → 受控关键词检索，最多返回 5 条候选
evidence_classification
  → 1 条 direct evidence 被采用：FaceLifting（版本 reviewed_2026-08-27）
route
  → evidence_found；external_calls=0；edit_plan_written=false；provider_run_written=false
```

## 当前已知边界和下一步

- P0-A 的中文自然语言召回能力还不应被夸写：当前依靠受控 feature/Provider 关键词和 FTS，不是 embedding/向量语义检索。
- **历史说明（已由 P0-C 覆盖）：** 当时 P0-A 尚未接入 `edit_planner.py` 或 `verification.py`。现在 P0-C 已受限消费 P0-A/P0-B evidence：8A/8C 仅获得 direct/reference/conflict 引用和 bad case，`execution_authorized=false`；参数、权限、Adapter 与外部调用仍不由检索器决定。
- 没有 RAG lifecycle worker、RAG 专属 Dashboard、真实用户检索数据、Recall@k/MRR/nDCG 阈值或生产级知识更新任务；这些属于后续 P0-B/产品数据阶段。
- P0-B/P0-C 现已完成本地混合检索与受限 evidence 回接；仍不能说已经有 LLM 工具路由、RAG 自动修图或新图片 Provider。完整决策依据见 [RAG_DECISION_GATE.md](RAG_DECISION_GATE.md)，当前回接实现见 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](RAG_P0C_ADVISORY_INTEGRATION_GATE.md)，人工 Gold Set 见 [RAG_GOLD_SET_DRAFT.md](RAG_GOLD_SET_DRAFT.md)。
