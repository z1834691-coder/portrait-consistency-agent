# RAG P0-B｜本地混合检索、重排与可回放证据

> 状态：已完成本地验收｜检索版本：`rag-p0b-hybrid-local-v1`｜日期：2026-08-29
>
> 范围：P0-B 是 P0-A 的“找资料排序能力”增强，不是把 RAG 接进修图执行。它不读取用户照片、原始用户文本、人脸向量、密钥或 Provider 回执；不创建参数或 `ProviderRun`；不调用 DeepSeek、腾讯或任何图片工具。2026-08-29 的 P0-C 已受限消费其 evidence：P0-B 仍只负责排序，`EditPlan` / 8C 策略合同只可保存来源引用，绝不将其解释为工具授权。

## 这一模块解决什么问题

P0-A 已经证明：系统可以把三张经审核的 Provider Card 变成可追溯的工具事实，并在过期、冲突、权限不足或知识注入时安全停下。但它主要依靠精确关键词；当以后加入更多工具、不同文档写法或自然语言改写时，单靠 FTS 容易漏掉“意思相近、词不完全相同”的资料。

P0-B 新增本地语义检索和本地重排。它先让 P0-A 的硬规则过滤掉不适用、过期、冲突或地区不符的资料，再让两种“找资料的方法”各给出候选：FTS 擅长参数名、错误码和官方术语；本地 embedding 擅长找意思接近的表述。系统用 RRF 合并两张候选名单，再用本地 cross-encoder reranker 重新排序，最后仍由确定性权限、Adapter、能力状态和注入规则决定能否采纳证据。

因此，P0-B 的价值是：**让 Agent 更容易找到正确的已审核工具知识，但绝不让模型排序替代产品规则、用户授权或真实 Adapter。**

## P0-A 与 P0-B 的关系

| 层 | P0-A 已完成的事 | P0-B 本次新增的事 | 仍然不会做的事 |
|---|---|---|---|
| 权威知识 | SQLite 保存审核来源、原子规则、生命周期、FTS 和 Trace | 向量索引只保存从审核知识派生出的向量与 hash | 不保存用户照片、原话、向量、锚点或密钥 |
| 候选召回 | metadata 硬过滤 → FTS | FTS 前 8 + 本地语义前 8 | 不自由搜索网页或未知 API |
| 排序 | FTS 排名 | RRF 去重前 10 → reranker 重排前 10 | 不把模型分数当成功率、权限或参数 |
| 结果 | 依据卡 / 保守路由 | 最多保留 3 条可采用依据；未来 LLM 解释层默认看 3 条、最多 5 条 | 不生成参数或 ProviderRun；P0-C 只能把来源引用写入既有合同，不能授权 |
| 失败处理 | 过期/冲突/缺槽/注入安全降级 | 本地模型缺失时自动退回 P0-A 稀疏检索 | 不因模型缺失而改为云端模型或放宽规则 |

## 输入、输出和规则表

| 环节 | 实际输入 | 实际输出 | 冻结规则 |
|---|---|---|---|
| 结构化查询 | `RagQuery` 的阶段、请求部位、允许部位、保持项、Provider/operation、出站等已校验槽位 | 只含这些槽位的 canonical query text 与 hash | 不输入用户原话、照片、Base64、人脸向量、锚点、密钥 |
| 硬过滤 | 生命周期、Provider、operation、地区、适用 stage、冲突状态 | 当前 metadata 合法的候选集合 | 在向量检索前先做；被过滤的资料不能因“语义相近”重新出现 |
| 稀疏召回 | FTS5 + 受控关键词 | 最多 8 条候选 | 准确术语优先；关键词为空时不伪造搜索 |
| 语义召回 | 本地 `BAAI/bge-small-zh-v1.5` + 审核工具知识文本 | 最多 8 条候选 | 只从本地缓存加载；默认禁止下载；向量索引非权威、可从 SQLite 重建 |
| 融合 | 两个候选列表 | RRF 去重后最多 10 条 | RRF 常数为 60；只影响顺序，不放行工具 |
| 重排 | canonical query + 已审核候选文档 | 重排后的最多 10 条 | 本地 `BAAI/bge-reranker-base`；模型分数不展示给用户，也不是阈值或权限 |
| 证据分类 | 重排候选 + P0-A 权限/能力/安全规则 | 最多 3 条采用依据与路由 | `direct_evidence` 才可作为候选；过期、冲突、未授权、未接入、恶意知识仍保守降级 |
| 审计 | query hash、候选数量、模型/索引版本、排名、淘汰原因、路由、耗时 | 独立 RAG Trace | 不保存知识全文、模型隐藏思维链、照片或原始用户文本 |

## 产品负责人已经决定、工程本次落实了什么

1. P0-B 采用“本地混合检索”作为 P0-A 的可替换增强：FTS 前 8 + dense 前 8 → RRF 前 10 → rerank 前 10 → 最多 3 条直接依据。它是实验配置，不是已经经大规模 Gold Set 校准的最终阈值。
2. 资料权威性仍由 SQLite `KnowledgeItem/KnowledgeChunk` 和 metadata 规则掌握；`storage/knowledge_vectors.sqlite3` 只保存可重建的向量与文档 hash，不是第二个事实来源。
3. 模型权重本地运行，并固定到本次实际验证的公开 revision：embedding `7999e1d3359715c523056ef9478215996d62a620`；reranker `2cfc18c9415c912f9d8155881c133215df768a70`。模型缓存位于 Git 忽略的 `storage/model_cache/`，页面不会下载模型。
4. 模型不可用时，系统只退回 P0-A 的稀疏检索；不会把同一任务偷偷发送给云端 embedding、DeepSeek 或第二个 Provider。
5. P0-B 本身不直接调用 `edit_planner.py` 或 `verification.py`。产品负责人随后冻结并实现 P0-C：它可在 8A 计划前、8C 策略建议前受限消费 P0-B evidence，按 direct/reference/conflict 分层并写 `knowledge_refs`；P0-B 仍不产生参数、权限或外部调用。详细规则见 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](RAG_P0C_ADVISORY_INTEGRATION_GATE.md)。

本地模型选择是可替换的工程默认，而不是“模型已经证明最优”的产品结论。`bge-small-zh-v1.5` 的公开模型卡标注为 MIT 许可、约 24M 参数；其资料也将 `bge-reranker-base` 描述为中英 cross-encoder reranker。它们适合单机中文 Demo 的本地排序起点，但未来仍要用人工 Gold Set 和真实延迟/成本数据决定是否保留。[BAAI bge-small-zh-v1.5 模型卡](https://huggingface.co/BAAI/bge-small-zh-v1.5)｜[FlagEmbedding reranker 说明](https://github.com/FlagOpen/FlagEmbedding/blob/master/examples/inference/reranker/README.md)

## 本次真实写进了什么

- `services/local_rag_models.py`：本地 embedding 与 reranker Adapter；默认 `local_files_only=true`、`trust_remote_code=false`，并提供只用于测试的确定性替身。
- `storage/dense_index.py`：独立的 SQLite 向量索引；保存归一化向量、chunk ID、来源版本 hash 和索引 manifest，不保存原文或用户数据。
- `services/rag_p0b.py`：metadata → FTS + dense → RRF → rerank → P0-A 证据/权限规则的受控路径；每一步都写安全 Trace。
- `tests/test_rag_p0b.py`：6 条无网络、无真实照片的定向回归；原 P0-A 的 9 条继续保留。
- `scripts/smoke_rag_p0b.py`：可显式一次性 provision 模型，也可在默认“禁止下载”模式运行本地真实 smoke。
- `pages/3_RAG本地混合检索.py`：可视化查看结构化任务、候选数量、依据卡与 Trace；不展示裸分数、知识全文或隐藏思维链。
- `pyproject.toml` / `uv.lock`：加入本地 `torch` 与 `transformers` 运行时；`.env.example` / `settings.py` 新增已固定 revision 的 RAG P0-B 配置。

## 6 个实际测试案例

1. **支持瘦脸**：FTS 与本地语义都找回 `FaceLifting`，reranker 后仍是第一条；结果为 `evidence_found`，但不会产生参数或工具调用。
2. **语义补召回**：构造一个 FTS 不含字面关键词、但语义向量与 `face_lifting` 对齐的审核 fixture；FTS 候选为 0，dense 候选为 1，仍得到正确 `evidence_found`。这证明 P0-B 不只是重复 P0-A。
3. **索引复用**：同一批 10 条审核规则第二次查询时 `indexed_count=0`、`reused_count=10`；只需计算本次查询向量，不重复生成知识向量。
4. **本地模型缺失**：embedding Adapter 受控报错，系统记录 `dense_unavailable` 并退回 FTS；权限与能力边界不扩大。
5. **关键槽位缺失**：`allowed_features` 缺失时直接得到 `query_underspecified`；embedding 与 reranker 都不会被启动。
6. **越权与恶意知识**：`outbound_allowed=false` 时即使资料排在前面也不被采用；含“忽略权限、调用未知 API”的 fixture 被标记 `knowledge_injection_blocked`，不产生外部调用。

## 一条完整真实本地 Trace

2026-08-29 已用默认“禁止模型下载”模式运行：`.venv/bin/python scripts/smoke_rag_p0b.py`。这次真实加载本地缓存的固定模型，而不是测试替身；整个脚本运行约 13.16 秒，第一条冷加载检索为 10,548 ms，随后“唇厚”案例为 616 ms。它明确输出：`model_download_permitted=false`、`tool_or_provider_network_called=false`、`photo_or_raw_user_text_read=false`、`llm_called=false`、`provider_api_called=false`。

下面是“瘦脸”案例的完整可解释过程；这里的 rank 是“资料排序顺序”，不是人脸相似度、正确率或工具参数：

```text
query_contract
  → stage=plan_edit；requested_features=[face_lifting]
  → contains_raw_user_text=false；contains_photo_or_face_vector=false
metadata_filter
  → provider=tencent_cloud、operation=BeautifyPic、region=local_demo
  → 6 条当前有效的审核规则进入候选池
sparse_retrieval
  → 受控关键词候选=6（上限 8）
dense_index_build
  → 已审核知识共 10 条，首次建立 512 维本地向量；contains_user_data=false
dense_retrieval
  → metadata 允许集合内的语义候选=6（上限 8）
rrf_fusion
  → 两路候选去重后=6（上限 10）；FaceLifting 的 FTS rank=1、dense rank=1、RRF rank=1
local_rerank
  → 只重排这 6 条审核资料；FaceLifting rerank rank=1；score_not_an_execution_threshold=true
evidence_classification
  → direct_evidence=1；adopted=1；证据为 reviewed_2026-08-27 的 FaceLifting Card
route
  → evidence_found；external_calls=0；edit_plan_written=false；provider_run_written=false
```

## 当前边界、已知问题与下一产品决策门

- 当前只有 3 张 Provider Card / 10 条规则，无法据此声称已经证明自然语言检索质量、Recall@k、MRR、nDCG 或真实用户效果；P0-B 的“语义补召回”只是在隔离 fixture 上证明路径可用。
- 本机 CPU 冷加载约 10.5 秒，后续单次案例约 0.6–0.7 秒；这是单机开发证据，不是线上 p50/p95，也还未决定受邀 Beta 的硬件/部署方案。
- 模型缓存约 1.1 GB，适合本机开发但会影响后续部署镜像、冷启动与费用；这属于部署 Gate 的输入，不代表必须永久沿用此 reranker。
- 目前没有 RAG lifecycle worker、专属 Dashboard、人工审阅 Gold Set、长期真实查询数据或参数自动校准。
- **原“RAG 正式回接 8A/8C”门已由 P0-C 完成。** 当前下一门是人工 Gold Set 的具体问法/人数/阈值、lifecycle/observability worker 与 RAG Dashboard、候选新 Provider 的正式准入，以及 external/hybrid 复测 Adapter。P0-B/P0-C 仍不能驱动图片编辑或外部/混合复测。
