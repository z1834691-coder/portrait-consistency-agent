# RAG 决策与开发 Gate（P0-A / P0-B / P0-C 已完成；外部能力仍待决）

> 这不是“已经上线、能自动修图”的完整 RAG。本文件记录产品负责人逐项确认、工程再实现的工作底稿。2026-08-29 已完成本地 P0-A（权威知识 + FTS）、P0-B（本地混合检索）和 P0-C（受限 evidence 回接 8A/8C 提议层）；三者都只查已审核工具知识。P0-C 只能提议/留证，不能产生参数、授权工具或调用外部/混合复测。仍有会改变工具权限、出站、参数或用户体验的事项，明确保留在第 21 节，不能提前写入执行代码。

## 1. 先用一句话理解 RAG

RAG（Retrieval-Augmented Generation）就是：Agent 回答或决定之前，先从一批经过审核的资料里找出相关内容，再把这些内容连同来源交给 LLM。它像“先查工具说明书，再决定怎么做”，不是让 LLM 获得视觉能力，也不是自动安装 API。

知识库不等于向量数据库。知识库是“要让 Agent 查到的内容”；向量数据库只是保存和按语义相似度查找这些内容的一种技术。少量资料可以先用 JSON/SQLite + 关键词检索；资料变多后才考虑向量索引，==实际产品常用 metadata 过滤 + 关键词 + 向量的混合方式。==

## 2. 在这个项目里知识放在哪里

当前已经存在的 `data/provider_cards/` 是 RAG P0 基线：每个工具一张结构化卡片，记录能力、参数、版本、限制、隐私、费用/延迟字段和失败策略。它由项目维护者审核后进入 Git，属于“能不能调用”的事实来源；P0-B 已在其外建立独立的本地向量索引与重排路径，但没有自动抓网页、没有新 Provider，也没有把检索结果接入图片执行**授权**链。P0-C 可以把受限 evidence 回接给 8A/8C 提议层，仍不能让检索结果产生参数、权限或外部调用。

未来的完整 RAG 可以拆成四层：

```text
已审核原始资料
→ 规范化、切片、加 metadata
→ 关键词/向量索引
→ 检索、过滤、融合、引用
→ LLM 受限提议 + 确定性策略校验
```

RAG 资料只保存工具和规则知识，不保存原始人像、Base64、完整人脸向量、密钥或未经脱敏的用户文本。==运行账本和 RAG 知识库是两件事：前者记录发生过什么，后者说明系统允许做什么。==

## 3. 什么叫“实时性”

RAG 不会自动实时。实时性来自知识更新流程：发现官方 API 变更 → 重新审核 → 更新卡片/文档版本 → 重新切片和索引 → 运行检索回归 → 发布新知识版本。每条知识都应有 `source`、`source_version`、`retrieved_at`、`effective_from`、`expires_at` 或 `review_due_at`，并在过期或来源撤回时停止用于工具放行。

==第一版可以采用“人工审核后更新”的低频方案，成本低且适合 Demo；不建议直接抓网页后自动进库。以后如果工具变化频繁，再增加定时检查，但自动抓取仍只能产生候选更新，不能绕过审核和回归测试。==

## 4. 建议的知识范围

| 内容 | 用途 | 是否进入第一版候选 |
|---|---|---|
| Provider Card/API 能力 | 判断参数、输入、版本和调用限制 | 是 |
| SDK/License/地区/隐私/成本 | 判断能否合法、可承受地调用 | 是 |
| 失败与降级手册 | 侧脸、多脸、超限、超时等路由 | 是 |
| 已审计 bad case | 解释为什么上次方案失败 | 后续加入 |
| 用户原始照片/人脸向量 | 不应进入知识库 | 否 |
| 未审核网页、论坛、模型自由生成结论 | 可能过期或被提示注入 | 否 |

RAG 能告诉 Agent“哪个工具支持唇厚”，也可以让产品从当前腾讯能力扩展到新的、经过审核并真实接入的 Provider；但==只有在该工具同时有版本化 Provider Card、Adapter、权限、成本和测试后，系统才可以执行。否则只能返回“当前未接入，给出手动建议”==。这意味着 RAG 会扩大产品可解决的问题，但不会把未知 API 直接变成可调用工具。

## 5. RAG 在哪些节点调用

本项目的方向是：RAG 不只用于质量门，而是凡是需要查工具能力或失败规则的地方都可以调用，例如：

- 8A 规划前：先确认某个目标特征是否有真实工具支持，再生成 `EditPlan`；
- 多脸/质量异常：查对应的降级和输入要求；
- `VERIFICATION_STRATEGY_SELECT`：比较本地复测、CompareFace、其他已接入验证工具；
- Provider 失败后：查可恢复条件和用户解释文案。

但“每个节点都查”不等于“每一步都把结果交给 LLM”。纯视觉测量、参数截断、权限判断和 API 回执仍由确定性模块负责；RAG 只在确实需要能力/规则知识时被调用，并留下 evidence 引用。既有外部处理同意也不能让一条 RAG 检索结果自行扩大可执行范围；P0 是否允许 8C 外部/混合候选在既有 scope 内执行，仍以第 19 节的最终产品决定为准。在该决定前，RAG 只能提出候选，状态机仍按当前白名单和权限 Gate 路由。

## 5A. 本轮补充：知识库、存储位置、实时性与调用边界

### 5A.1 RAG 知识库是不是向量数据库？

不是。知识库：你希望 Agent 能查到的内容。向量数据库：保存这些内容、并按语义相似度检索的一种技术。现在已经有很多现成的向量数据库和检索工具，例如 FAISS、Chroma、Qdrant、pgvector，也有 LangChain、LlamaIndex 等框架。但它们只提供“存储和搜索能力”，不会自动替你准备这个项目需要的知识。你的项目需要自己整理和审核：各个图片工具支持什么参数；参数范围和调用方式；哪些工具支持唇厚、眼距、鼻翼；工具的图片限制、费用、延迟和隐私规则；多脸、侧脸、遮挡、超时等失败处理方法；不同工具的版本和适用区域；已验证的 bad case 和降级方案。

当前项目的 `data/provider_cards/` 就是最早的知识库雏形。它是结构化 JSON，不是完整向量 RAG。未来完整链路会是：

```text
官方文档/工具卡/失败案例
→ 清洗、切片、加版本和权限信息
→ 保存到知识库并建立索引
→ Agent 根据当前问题检索
→ LLM 提出工具方案
→ 确定性权限校验
→ 调用真实 Adapter
```

所以没有一个“现成的母版人像修图 RAG 知识库”可以直接拿来用。现成的是基础设施，具体知识需要你作为产品负责人定义和审核。

### 5A.2 知识库存在什么地方？

Demo 阶段可以这样放：

```text
data/provider_cards/       # 已审核的工具能力卡
data/knowledge_sources/    # 后续加入的官方文档和失败手册
data/rag_index/            # 由脚本生成的索引
```

开发初期甚至可以只用：

```text
JSON/Markdown + SQLite 全文检索
```

资料量变多后，再升级成：

```text
SQLite/全文检索 + 向量数据库
```

部署后，知识源和索引会放在服务器的持久化存储中，而不是浏览器里。用户照片和人脸向量不进入 RAG 知识库。

### 5A.3 RAG 怎么保持“实时”？

RAG 本身不会自动实时。如果官方 API 今天变了，但你没有更新知识库，Agent 仍然会依据旧资料做判断。真正的实时性来自一套更新机制：

```text
发现官方文档变化
→ 更新工具卡
→ 修改版本号
→ 重新切片和建立索引
→ 运行检索回归测试
→ 发布新知识版本
```

第一版建议采用人工审核更新，因为：工具数量少；成本低；更容易保证可靠；不会因为网页变化自动让 Agent 误调用错误工具。后续可以增加定时检查，但自动抓到的新内容只能作为“待审核更新”，不能自动进入执行链。每份知识最好保存：来源；来源版本；生效时间；最近审核时间；下次复审时间；是否已过期；适用 Provider 和地区。过期知识不能继续直接放行工具。

### 5A.4 RAG 是否可以在每次需要工具调用时使用？

方向上合理，但不需要机械地“每调用一次 API 就重新查一次”。更合理的是：

```text
需要判断工具能力/限制/失败方案
→ 调用 RAG
→ 形成当前任务的工具知识上下文
→ 在同一个任务内复用
```

适合调用 RAG 的地方包括：质量门发现照片异常，需要查失败处理规则；规划前，需要确认某个五官特征是否有真实工具支持；8C 的 `VERIFICATION_STRATEGY_SELECT`，需要比较本地复测、CompareFace 或其他工具；Provider 失败后，需要查是否能恢复以及如何向用户解释；未来加入新 Provider 时，需要查版本、权限和参数兼容性。

不需要每次调用 RAG 的地方包括：计算脸宽高比例；计算眼睛面积；把参数截断到 0—100；校验用户是否已确认；保存真实 `ProviderRun`；解析腾讯 API 回执。

这些仍然由确定性代码负责。所以，RAG 是 Agent 的“工具知识查询层”，不是所有模块的替代品。

## 6. 初始待决策清单（历史问题；本轮回答与剩余决策见第 17、19 节）

这些事项目前全部开放，不能由代码默认决定：

1. **知识源权威**：只允许官方文档，还是允许经审核的 SDK/案例/内部 bad case？冲突时谁优先？
2. **存储方式**：继续 JSON/SQLite/全文索引，还是使用向量数据库，或采用混合架构？
3. **切片策略**：按 API、功能、参数、错误码还是按文档标题切片；每片允许多长，是否保留上下文。
4. **召回策略**：==关键词、metadata 过滤、向量相似度各自解决什么问题==；召回多少条；是否需要重排。
5. **融合规则**：关键词和向量结果如何合并，冲突的 Provider Card 如何处理，是否优先新版本/高权威来源。
6. **新鲜度规则**：多久复审一次；过期卡是警告、降级还是直接禁止调用。
7. **引用与解释**：Agent 是否必须展示来源 ID、版本和选择理由；用户看到多少，后台 Trace 保存多少。
8. **安全边界**：如何防止知识片段中的提示注入覆盖状态机、权限和安全策略。
9. **评测 Gate**：至少评估能力卡 Recall@k、引用正确率、过期拦截率、unsupported rate、一次任务增加的延迟和成本。

## 7. 与 8A/8C 的关系和开发顺序

==当前代码先完成 8C 的确定性 baseline：Agent 接收结构化修后证据，提出允许集合中的策略，确定性校验后再决定执行。8C 只预留 RAG 查询和 evidence 引用，不提前引入向量数据库。产品方向已经改变：RAG Gate 通过后，8A 生成 `EditPlan` 之前也要查一次工具能力证据，避免规划器只看一张腾讯卡片就把“当前工具能做什么”当成“用户目标已经被满足”。==

这段是 2026-08-28 的历史入口：当时要求 8C 的 `VerificationResult → STOP/REPLAN/RESHOOT` 闭环通过测试后，再进入本文件对应的 RAG 决策 Gate。第 19.1 节现已完成冻结，P0-A/P0-B/P0-C 均已完成本地验收；8A/8C 现在只能消费 P0-C 的版本化受限 evidence，仍不能把 Provider Card 读取之外的能力写成“RAG 自动修图”。

## 8. 本模块的协作方式

进入 RAG Gate 后，仍按“背景 → 候选方案 → 产品负责人决策 → 工程实现 → 3—5 个案例 → 一条完整 Trace → 验收”推进。最终 Trace 必须能回答：查了哪些知识、为什么召回、哪个版本生效、Agent 提出了什么、策略校验拒绝了什么、最后实际调用了哪个 Adapter。

## 9. 先把“知识库”与“向量数据库”分开

### 9.1 知识库是什么

知识库是产品允许 Agent 查阅的一组**经过审核的事实**。在本项目里，它不是用户照片集合，而是“工具说明书 + 产品规则 + 失败处理手册”。例如一条知识可以说明：腾讯 BeautifyPic 支持 `FaceLifting`，参数范围为 0—100，不能指定多人照片中的目标脸，美白/磨皮需要额外告知，调用失败时不应自动重试。Agent 查到这条知识后，才能向规划器提出“当前工具可以尝试瘦脸，但不能执行唇厚”的证据。

知识库可以先是几个结构化 JSON 文件，也可以是 SQLite 表、全文索引或向量索引。**向量数据库不是知识库本身**，只是当资料变多时，帮助系统按“意思相近”找到相关片段的一种存储/检索技术。把文件放进向量库并不会自动变成可靠 RAG；可靠性取决于资料是否权威、版本是否有效、召回是否正确、引用是否可追溯以及最终是否经过权限和工具白名单校验。

### 9.2 知识库存在哪里

P0 可以继续放在仓库的 `data/knowledge/` 或 `data/provider_cards/`，随 Git 版本控制；小规模时程序启动读取 JSON/SQLite 即可。未来如果资料和并发增长，可以选择：

| 方案 | 知识放置 | 适合阶段 | 主要代价 |
|---|---|---|---|
| A. 结构化文件 | JSON/YAML + Git | Demo、少量 Provider Card | 需要人工维护，语义搜索能力弱 |
| B. SQLite 全文/关键词 | 本地 SQLite FTS 或同类全文索引 | 受邀 Beta、小规模工具目录 | 仍需自己做 embedding/语义召回（如确有需要） |
| C. 本地向量/混合库 | 本地向量索引 + metadata/关键词 | 多 Provider、较多失败手册 | 多一个索引构建、模型和评测维护面 |
| D. 托管数据库 | 云端 Postgres/pgvector 或向量服务 | 多用户、团队运营、频繁更新 | 费用、出境、权限、备份和供应商留存治理 |

当前没有“现成且自动正确”的本项目知识库。官方文档可以作为原始资料，但仍要由项目维护者挑选、清洗、结构化、加版本和审核后才进入执行链。

## 10. ==这套产品的完整 RAG 链路==

```text
官方/内部候选资料
→ 人工审核与去噪
→ 规范化成 Provider/Policy Knowledge Item
→ 按语义单元切片并加 metadata
→ 建立关键词/向量/混合索引
→ 根据当前任务构造结构化 query
→ metadata 过滤
→ 召回候选片段
→ 去重、版本/生效期过滤、重排
→ 输出带来源的 KnowledgeEvidence
→ Agent 受限提出工具/策略候选
→ 状态机、权限、预算与 Provider Card 校验
→ 使用首次确认留下的有效 scope（若出站/用途超出 scope 才重新授权）
→ Adapter 执行
→ ProviderRun/VerificationResult 记录真实结果
```

==这条链里最容易被误解的部分是：RAG 只负责“找资料并带来源”，不负责计算照片差异，也不负责替代 `mapping_policy`、Safety Policy 或首次外部处理同意。即使 LLM 看见一条“支持唇厚”的知识，系统也必须继续检查：对应 Adapter 是否真实存在、权限是否已开、参数范围是否有测试、用户是否允许该部位、当前外部处理同意是否覆盖该用途、是否需要新的图片出境。任何一项不成立，都只能输出 suggestion-only 或手动建议；不能靠 RAG 结果自行扩大权限。==

## 11. 需要产品负责人参与的规则面

下面每一项都会影响产品边界、成本、延迟、隐私或面试可解释性，不能由工程师悄悄替你决定。

### 11.1 知识源与权威等级

候选知识源包括：官方 API/SDK 文档、已审核 Provider Card、License/地区/隐私/成本说明、内部失败手册、经确认的 bad case、用户常见问题和经过审核的参数经验。需要确定：

- 哪些来源可以进入“可执行事实”，哪些只能用于解释；
- 官方文档与内部经验冲突时谁优先；
- Provider 文档、SDK 版本、控制台实际能力和 smoke 结果不一致时，是否立即把该能力降级为不可执行；
- 谁负责审核、多久复审一次、什么证据能让知识升级为“可执行”。

建议初版：只有官方资料 + 已通过真实 smoke 的 Provider Card 才能影响执行；bad case 和用户经验先只能影响解释/候选，不直接放行 API。

### 11.2 ==知识条目的最小结构==

==每条条目建议至少有：==

| 字段 | 通俗含义 | 为什么需要 |
|---|---|---|
| `knowledge_id` | 这条知识的编号 | Trace 能指回原条目 |
| `type` | 能力、参数、限制、失败、隐私、成本或解释 | 决定它能影响什么 |
| `content` | 经过审核的事实 | 给 Agent/规划器读取 |
| `provider/operation` | 属于哪个工具和动作 | 防止把 A 工具规则套给 B 工具 |
| `source_uri/source_title` | 原始出处 | 便于复核 |
| `source_version` | 文档/SDK/卡片版本 | 避免旧规则继续生效 |
| `authority_level` | 权威等级 | 冲突时可排序 |
| `effective_from/review_due_at/expires_at` | 何时生效、何时复审、何时过期 | 处理实时性 |
| `capability_status` | 可执行、建议-only、已撤回 | 直接连接工具白名单 |
| `privacy/cost/region` | 是否出境、预计成本、区域 | 给权限/预算策略用 |
| `allowed_intents` | 只允许在哪些任务节点使用 | 防止跨场景误用 |

### 11.3 切片策略

切片就是把长文档拆成适合检索的小段，不是越碎越好。切得太大，召回时夹带很多无关限制；切得太小，参数和适用条件会被拆散，Agent 只看到“支持瘦脸”却看不到“不能指定目标脸”。候选策略：

- ==按标题/语义单元切：一块尽量完整表达一个能力、参数、限制或失败规则；==
- ==保留必要的父级上下文：Provider、版本、操作名不能被切掉；==
- ==结构化字段和自然语言说明分开存，但在检索结果中一起返回；==
- ==小规模先不追求固定 token 数，先用 3—6 条人工审核的能力卡做可读回归；资料变多后再测试长度和 overlap。==

产品负责人需要决定：切片是否按 Provider、功能、参数、错误码、隐私规则分开；同一条限制是否允许被多个条目引用；一条条目多长算“可审计”。

### 11.4 查询构造

不要把整段用户聊天原文直接拿去搜。先由系统把当前任务整理成结构化 query，例如：

```json
{
  "stage": "PLAN_EDIT",
  "requested_features": ["face_shape", "eye_size", "lip_thickness"],
  "allowed_features": ["face_shape", "eye_size"],
  "photo_mode": "single_face",
  "outbound_allowed": true,
  "region": "local_demo",
  "provider_status": "authorized_only"
}
```

这样检索目标是“当前阶段允许的工具能力”，而不是“全网有没有人说过大眼”。==需要决定的规则包括：哪些槽位进入 query、是否把用户原话先脱敏、是否把当前照片视觉事实放入 query（建议只放结构化标签，不放图片/向量）、query 缺字段时是追问还是走 baseline。==

### 11.5 召回策略

召回回答“先找哪些候选知识”。三种基本方式：

| 方式     | 擅长什么                        | 问题               |
| ------ | --------------------------- | ---------------- |
| 关键词/全文 | 参数名、错误码、Provider 名、版本号      | 换一种说法时可能找不到      |
| 向量语义   | “让脸更窄”与“瘦脸能力”这种表达差异         | 可能召回语义相近但不能执行的内容 |
| ==混合召回==   | ==先用 metadata/关键词排硬边界，再用向量补语义== | ==实现和评测更复杂，但更适合本项目== |

==建议的安全顺序是：先用 metadata 过滤 Provider/版本/授权/阶段，再用关键词和向量召回候选；任何被过滤掉的过期、未授权或 suggestion-only 条目不能因为相似度高重新出现。==产品负责人还要决定 top-k、是否重排、无结果阈值以及低置信时是追问、baseline 还是人工复核。

### 11.6 融合与重排

融合就是把关键词结果、向量结果、版本和权威等级合并成一个有序证据包。==推荐的确定性优先级：==

```text
授权/有效期/Provider 状态硬过滤
→ 官方/已 smoke 的高权威来源优先
→ 与当前阶段和特征匹配优先
→ 同一事实去重
→ 冲突时保留冲突并降级，不让 LLM 自行拍板
```

==LLM 可以根据证据生成用户可读解释，但不应自行平均两个冲突参数，也不能把“可能支持”改写成“已经支持”。所有被采用的条目都要留下 `knowledge_refs`；未采用但造成拒绝的高风险冲突也应记录 reason code，便于 bad case 归因。==

### 11.7 实时性与版本发布

RAG 的“实时”不是每次回答都去网上搜，而是知识版本更新足够及时、且旧知识不会继续放行。候选更新流程：

```text
发现官方变更/Provider smoke 异常
→ 建立候选知识版本
→ 人工审核与冲突检查
→ 运行检索回归和工具 smoke
→ 发布新索引/卡片版本
→ 记录生效时间，旧版本停止执行但保留历史 Trace
```

需要冻结：复审频率、`review_due_at` 到期动作（警告/只解释/禁止执行）、索引重建方式、是否允许旧版本在已有确认 scope 内继续、供应商临时故障是否立即撤回能力。建议 ==Demo 采用“人工更新 + 启动时加载 + 版本号切换”；不要直接抓网页自动进执行链。定时抓取最多生成候选 diff，不能绕过审核。==

### 11.8 引用与用户可见性

==后台 Trace 至少保存 `knowledge_id`、source、source_version、retrieved_at、是否采用、淘汰原因和策略版本。用户界面不必展示整段文档，但应能看到简短依据，例如“当前工具卡显示 BeautifyPic 支持瘦脸；唇厚能力未在已授权工具中找到，因此只给手动建议”。需要决定是否展示来源名称/版本、是否允许用户展开证据、用户是否能看到“未采用原因”。==

### 11.9 安全与提示注入

知识片段本身也可能包含错误指令或恶意文本。硬规则应是：

- 只允许审核过的来源进入执行知识库；
- 知识内容作为 evidence，不作为系统 Prompt 或权限指令；
- 片段不能覆盖状态机、安全策略、用户同意、Provider Card 的硬字段；
- 不把用户评论、论坛帖子或模型自由生成的建议直接当知识；
- 知识内容若要求泄露密钥、跳过确认或调用未知 API，必须被当作恶意/无效内容并记录；
- 召回服务故障、空结果或知识冲突时，走已知 Provider Card baseline/手动建议，不能扩大工具白名单。

### 11.10 成本、延迟与数据边界

==每次 RAG 会增加索引查询、可能的 embedding/重排和 LLM 上下文长度。需要观察：检索延迟、返回条数、上下文 token、一次任务增加的成本、无结果比例和 fallback 比例。

Trace 保存 query 的 hash、知识版本、top-k、耗时和采用结果，不保存原图、向量、密钥或原始自由文本。
RAG 运行在本地时可避免新的出境；若使用托管 embedding/向量服务，必须单独确认数据所在地、留存/ZDR、费用和用户文本出境同意。当前 Demo 默认不向 OpenRouter 或其他跨境服务发送这些数据。

## 12. RAG 与 Agent 的边界：什么可以“智能”，什么必须确定性

| 环节 | Agent/LLM 可以做 | 确定性系统必须做 |
|---|---|---|
| 找知识 | 根据结构化 query 提议需要查哪类证据 | 过滤来源、版本、授权、过期和工具白名单 |
| 解释 | 把已采用证据说成人话 | 不新增证据外的能力/参数 |
| 选策略 | 在允许集合中提出候选及理由 | 状态、预算、权限、确认和出站放行 |
| 规划 | 读取证据说明用户目标可能由什么工具处理 | 视觉差异、`mapping_policy`、0—100 参数边界 |
| 失败归因 | 根据已记录事实提出候选根因 | 真实 ProviderRun、错误码、重试/停止和回滚 |

==因此，未来的 8A 主链应是：==

```text
Profile/PhotoQuality/IntentFrame
→ 构造 PLAN_EDIT query
→ RAG 返回能力/限制 evidence
→ 过滤不可执行、过期和未授权能力
→ 视觉事实 + mapping_policy 生成 EditPlan
→ 首次确认 scope 内直接执行；只有范围/用途/出境变化才重新授权
```

==未来的 8C 主链应是：==

```text
VerificationResult 前置证据
→ 构造 VERIFICATION_STRATEGY_SELECT query
→ RAG 返回各复测工具的能力/成本/隐私/失败证据
→ Agent 提出 local/external/hybrid/manual 候选
→ 状态机/权限/预算校验
→ 在既有外部处理同意内直接执行；若是新用途/新出境方则先进入授权 Gate
→ Adapter 真实调用并落 ProviderRun
```

## 13. 初始方案选型（历史候选；本轮 P0/P0-B 方向见第 17、19 节）

| 方案                    | 做法                                                            | 优点               | 风险/代价            | 适合本项目的阶段          |
| --------------------- | ------------------------------------------------------------- | ---------------- | ---------------- | ----------------- |
| A. 不做完整 RAG           | 继续直接读 Provider Card                                           | 最便宜、最可解释、零新依赖    | 无法展示检索/多工具扩展能力   | 当前 Demo baseline  |
| ==B. 结构化目录 + SQLite FTS== | ==Provider Card/规则入 SQLite，metadata + 关键词检索，保留 `knowledge_refs`== | ==成本低、容易学、证据清楚、可离线== | ==语义改写能力有限==         | ==推荐第一版 RAG==         |
| ==C. 本地混合检索==             | ==B + 本地 embedding/向量索引 + rerank==                                | ==更能处理自然语言、多工具扩展==   | ==模型许可、索引、评测和延迟增加==  | ==有多 Provider/真实查询后== |
| D. 托管向量/pgvector      | 云端 embedding + 托管索引                                           | 多用户和更新更方便        | 费用、跨境、留存、权限和部署复杂 | 受邀 Beta 之后        |

==我的工程建议是先选 B 作为 RAG 学习和验证切片：先让你看懂“知识条目 → metadata 过滤 → 关键词召回 → evidence → 规划器”的完整证据链；如果真实测试证明关键词无法覆盖用户表达，再把 C 作为可替换召回层。这样 RAG 不会因为一开始选了复杂向量基础设施而变成黑箱。==

## 14. 初始 RAG 评测与通过标准（历史候选；本轮评测与监控方向见第 18 节）

至少准备一组**工具问题 Gold Set**，每条问题有人工确定的相关知识 ID、正确工具状态、正确限制和应该拒绝的工具。评测应包括：

- Recall@k：正确知识是否在前 k 条中出现；
- Precision/unsupported rate：召回内容是否会诱导系统声称不存在的能力；
- 引用正确率：回答中的来源是否真的支持该结论；
- 过期拦截率：过期或撤回能力是否被阻止执行；
- 冲突处理率：官方/旧版本冲突时是否按规则降级；
- query 成功率：自然语言变体是否能找到同一事实；
- 延迟与成本：一次 8A/8C 任务增加多少毫秒和 token/费用；
- fallback 正确率：索引故障、空结果、低置信是否回到 Provider Card/manual，而不是自由搜索。

通过标准不能只看“模型回答像不像”，还要看有没有越权工具、有没有错误参数、有没有漏掉关键限制，以及每条结果能否回放到知识版本。

## 15. 初始决策清单（历史问题；本轮已确认与待确认事项见第 17、19 节）

1. 第一版知识源是否只允许官方文档 + 已真实 smoke 的 Provider Card？内部 bad case/用户经验先只用于解释，是否接受？
2. P0 存储是否采用“结构化 JSON/SQLite + 关键词/全文检索”，等多 Provider 或召回失败后再上本地向量/混合检索？
3. 8A/8C 的查询是否只传结构化标签，不传图片、向量和原始文本？无结果时是追问、baseline 还是手动建议？
4. 切片是否按“一个能力/限制/失败规则一个条目”，保留 Provider、版本、适用阶段等上下文？
5. 是否采用 metadata 硬过滤 → 关键词召回 → 可选向量补召回 → 确定性重排，而不是让 LLM 自己挑结果？
6. top-k、低置信阈值、冲突规则、过期动作（警告/只解释/禁止执行）如何定？
7. 用户是否看到来源名称/版本和“为什么没有采用某工具”的简短依据？后台是否必须保存完整 `knowledge_refs`？
8. 知识版本由谁审核、多久复审、Provider smoke 失败是否立即撤回？已有确认 scope 是否允许用旧卡完成一次？
9. RAG 查询、embedding、重排是否必须本地运行；若使用云服务，是否接受新的数据出境、ZDR/留存与费用决策？
10. 8A 的第一版 RAG 是否只影响“工具能力查询”，不直接生成参数；8C 是否允许它提出外部/混合复测候选，并在既有外部处理同意和 scope 覆盖时直接执行、超出时才重新授权？

## 16. 下一次模块协作合同

产品负责人完成第 19.1 节的最终确认后，下一次只实现一个 RAG P0 纵向切片，交付仍按既定协作机制：

1. 一页中文说明：它解决什么问题、知识库和向量索引分别是什么；
2. 输入、输出和规则表：知识条目、结构化 query、召回结果、evidence、fallback；
3. 由产品负责人决定的规则：知识源、切片、top-k、过期和冲突处理、引用和成本；
4. 3—5 个实际案例：支持能力、未接入能力、过期卡、冲突来源、索引故障；
5. 一条完整 Trace：从条目版本、query hash、召回/过滤/重排到 Agent 提议、状态机拒绝或 Adapter 放行。

**历史快照（截至 2026-08-28；已由第 21 节覆盖）。** 当时 RAG 仅有一批产品负责人确认的治理、数据边界、P0 存储方向、查询边界、用户可见依据和评测/监控要求（第 17、18 节）；切片粒度、P0 的混合检索时点、Top-K/低置信阈值、动态上下文/overlap 与 8C 外部执行范围仍需第 19 节的最终确认。当时尚没有新增向量数据库、embedding 服务、RAG 运行代码或新的 Provider 能力；2026-08-29 的实际 P0-A/P0-B/P0-C 状态以第 21 节为准。

## 17. RAG 产品设计与已确认决策（2026-08-28）

> 历史状态（2026-08-28）：本节记录当时产品负责人已明确确认的方向；其中相互矛盾、尚需评测或会改变执行权限的项目，不伪装成“已冻结”，统一列在第 19 节。当时尚未新增 RAG 运行代码、合同字段或外部图片调用；当前冻结与实现以第 21 节为准。

### 17.1 背景、调研与核心判断

**背景与问题。** 当前系统只有腾讯 Provider Card 的结构化读取。它能说明“已经接入的工具能做什么”，但无法在多个工具、版本、失败规则、隐私限制与新能力之间做带来源的检索；如果把它直接当成完整 RAG，或让 LLM 根据网页/记忆自由决定工具，都会使“能不能执行”失去可审计边界。

**调研与判断。** 产品负责人将 RAG 定义为 Agent 的“工具知识查询层”，而非视觉算法、参数规划器或自由 API 搜索器。混合检索的合理分工是：metadata 先排除不允许的 Provider/版本/区域/权限，关键词保留参数名、错误码和官方术语的精确命中，向量检索补足用户自然语言表达；二者的候选再由轻量 reranker 排序。Qdrant 的官方混合检索文档也明确将 dense/sparse 两路以 RRF 融合，并建议在较小候选集上 rerank；Sentence Transformers 将 CrossEncoder 定义为“先检索、后重排”的第二阶段模型，而不是全库逐条计算。[Qdrant 混合检索](https://qdrant.tech/documentation/search/hybrid-queries/)｜[Qdrant 重排教程](https://qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search/)｜[Sentence Transformers CrossEncoder](https://www.sbert.net/docs/cross_encoder/usage/usage.html)

**核心产品边界。** RAG 只负责“找经审核的资料并带来源”。视觉事实仍由 CV，参数仍由确定性 `mapping_policy`，是否执行仍由状态机、权限、预算、Provider Card 和真实 Adapter 共同放行。即使检索到“支持唇厚”的文档，只要对应 Adapter、权限、参数测试、用户允许范围、出境范围或确认 scope 任何一项不成立，系统只能给出 `suggestion_only` 或手动建议。

### 17.2 已确认的知识源、内容边界与审核责任

以下规则已确认：

| 规则面 | 已确认决策 | 不能被 RAG 覆盖的边界 |
|---|---|---|
| 知识源 | 只接受官方 API/SDK/License/地区/隐私/成本文档，以及项目人工审核内容；能影响执行的 Provider Card 必须同时有官方来源和真实 smoke/Adapter 证据 | 未审核网页、论坛、参数教程和模型自由生成内容不能进入执行知识库 |
| 入库内容 | Provider Card、失败/降级规则、权限规则、已验证 API 回执、经审计 bad case、后续 Provider 的官方能力说明均可入库 | 用户原图、Base64、人脸向量、主体锚点、密钥、未脱敏用户文本不入库 |
| 事实等级 | 官方资料 + 已 smoke 的 Provider Card 可影响执行；内部 bad case、用户经验和常见问题先只影响解释/候选，不能直接放行 API | “有人反馈有效”不是“工具已可执行”的证据 |
| 审核人和更新 | 产品负责人审核；Demo 采用人工更新、启动时加载、版本号切换；常规人工复审暂定每两周一次 | 定时抓取只能产出候选 diff，不能自动入库、自动发布或改变工具白名单 |
| 失效/异常 | 新版本发布后旧版本保留历史 Trace，但停止参与新工具放行；Provider smoke 失败时立即撤回该能力的可执行资格 | 已有确认 scope 不能让已经撤回/过期的能力再执行 |

### 17.3 统一知识对象、标签与生命周期

为解决“不同来源口径不同、版本冲突、无法回放”的问题，未来 RAG 不把一段文字当作裸文本，而是先规范成 `KnowledgeItem`（完整来源版本）和 `KnowledgeChunk`（可检索片段）。`KnowledgeItem` 保留一份来源文档的完整身份；`KnowledgeChunk` 才是检索和引用单位。这样既保留“整篇文档”的版本/溯源，也不把整篇文档一次塞给 LLM。

每个条目/片段至少统一标记：`knowledge_id`、`chunk_id`、`source_type`、`source_uri`、`source_title`、`source_version`、`authority_level`、`effective_from`、`review_due_at`、`expires_at`、`lifecycle_status`、`provider`、`operation`、`region`、`stage`、`claim_type`、`capability_status`、`adapter_status`、`smoke_status`、`privacy_class`、`cost_tier`、`heading_path`、`supersedes`、`conflict_group_id` 和内容 hash。它们分别解决来源、版本、权限、工具、适用场景、过期、冲突和可追溯问题。

生命周期状态至少包括：`candidate`、`reviewed_active`、`superseded`、`expired`、`withdrawn`、`conflicted_pending_review` 和 `explanation_only`。本地 `knowledge_lifecycle_worker` 的职责是检查复审到期、官方变更候选、Provider smoke 异常、版本替换和索引是否需要重建；它只能生成待审任务、告警和 Trace，不得自行把候选知识升级为可执行能力。

### 17.4 冲突处理：排序用于解释，硬冲突必须阻断

产品负责人确认需要统一标签、来源、版本、生效时间和可信度，并将冲突量、过期召回率、溯源完整率纳入知识库管理看板。为避免“让 LLM 或用户替 Provider 事实拍板”，冲突分为两类：

- **硬事实冲突**：同一 Provider/operation/参数范围/隐私出境/地区/权限/是否可执行出现相互矛盾的有效证据。系统展示不同来源、版本、权威等级和时间，但禁止工具调用，进入 `conflicted_pending_review`；由人工审核更新能力卡。LLM 只能解释冲突，不能选择、平均或绕过它。
- **软性解释冲突**：例如修图风格建议、非执行性说明或用户偏好。LLM 可以把不同观点连同来源摆给用户，由用户选择偏好；该选择不能改变可执行事实、参数硬边界或权限。

默认排序用于呈现和召回重排，而不是越权放行：`reviewed_active` > 非 active；官方/已 smoke 的 Provider Card > 已审计内部规则 > explanation-only；当前有效版本 > 旧版本。同一高风险事实若仍冲突，排序不等于裁决，必须降级并阻断。

### 17.5 已确认的查询、规划与工具调用边界

RAG query 必须由 `IntentFrame`、Provider Card 状态和当前结构化任务事实共同生成。推荐最小槽位为：

```text
stage / task_mode / requested_features / allowed_features / preserve_constraints
profile_version / photo_quality_route / face_count / subject_match_route / safety_route
provider_candidates / adapter_status / provider_card_versions / region
confirmation_scope_summary / outbound_allowed / budget_remaining / round_number
previous_provider_error_category / verification_route / intent_slots_present
```

RAG query 只使用已经过 Schema 校验的 `IntentFrame` 槽位和当前结构化任务事实；用户原话（即使已脱敏）不作为 RAG 检索输入。文本 IntentFrame Adapter 如需读用户文字，仍遵守独立的最小必要/脱敏边界；它与 RAG query 是两条不同数据流。照片、人脸向量和原始视觉数据也不进入 query，只允许使用如 `single_face`、`side_face`、`eye_measurement_available` 之类的结构化标签。影响安全、权限、Provider 或参数边界的关键槽位缺失时，Agent 必须追问；非关键缺失时走当前已审核 Provider Card baseline。空结果必须先标注原因（`QUERY_UNDERSPECIFIED`、`RETRIEVER_MISS_SUSPECT`、`NO_ACTIVE_KNOWLEDGE`、`CONFLICT_BLOCKED`、`INDEX_UNAVAILABLE`），再走 baseline/手动建议，不能假装“没有工具”。

8A 的第一版 RAG 只查询“工具能力、限制、权限和失败处理”，不直接生成参数；`mapping_policy` 仍是参数唯一的确定性生成者。8C 可以让 RAG 依据工具能力、成本、隐私和失败规则提出 `local/external/hybrid/manual` 候选；RAG 不计算修后几何差异，也不生成 `ProviderRun`。8C 的外部/混合候选能否执行仍需第 19 节的最终范围决定。

### 17.6 本地优先的存储与演进方向

已确认 P0 从本地 SQLite 开始，保留未来升级为“SQLite + 本地 embedding + 本地向量索引”的可能。第一阶段的权威事实库是 SQLite：保存版本化 `KnowledgeItem`、`KnowledgeChunk`、metadata、生命周期、冲突、审计事件和 FTS/关键词索引。资料、SQLite 文件、索引构建 manifest、embedding 模型版本与 chunk 版本均需可打包迁移；真正出现受邀用户测试后，再单独决定是否迁到云端、数据所在地、留存/ZDR、费用和用户文本出境同意。

这意味着本轮不把 embedding、rerank 或向量服务送往云端。此前“允许新的云端数据出境”的宽泛想法，被后续更具体的“先本地运行，真实用户测试后再决定上云”覆盖；未来云迁移是保留的能力，而不是当前默认。

### 17.7 证据分类、动态上下文与可观测性

检索结果进入 Agent 前必须分为三类：

- `direct_evidence`：直接回答当前能力、限制、权限或失败处理的问题；
- `reference_context`：提供背景但不能单独支持可执行结论；
- `conflict_evidence`：与其他有效事实互相矛盾，必须触发降级/人工审核。

每条 evidence 返回来源、版本、权威等级、生命周期、检索路径、相关性分数、关联类型和 `knowledge_id#chunk_id`。LLM 生成解释时应优先引用 direct evidence，显式标出 conflict，而不是把冲突片段缝成一个虚假结论。后台 Trace 必须保存完整 `knowledge_refs`、query hash、过滤/召回/融合/重排阶段、淘汰原因、采用状态、索引版本、模型版本、耗时与成本；这些事实将用于评测和 bad case 归因。

用户对“只留 Trace”与“用户可看来源/未采用原因”的两轮思考，最终以更具体的后一轮回答为准：P0 用户界面展示紧凑依据卡——结论、来源名称、版本、是否支持/为何降级；后台保存完整 `knowledge_refs` 和淘汰原因。P0 不展示原文全文、相关性分数、完整 Trace 或隐藏思维链；“是否允许展开受控摘要”放入第 19.2 节 P1 队列。

## 18. 评测、监控与 Gold Set 方向（已确认，阈值待定）

### 18.1 指标体系与安全红线

产品负责人确认 RAG 不只看“答案像不像”，而要同时监测检索、生成、安全和成本。初版评测集必须包含可回答、不可回答、过期、冲突、权限不足、异常 Provider、自然语言改写和恶意知识片段等任务。指标分层如下：

| 层级 | 已确认需监测的指标 | 用途 |
|---|---|---|
| 检索 | `Recall@k`、`Precision@k`、Hit Rate、MRR、rerank 后 `nDCG@k` | 检查该找的知识是否找回、无关知识是否靠前、排序是否正确 |
| 生成/引用 | Context Precision、Context Relevance/Recall、Faithfulness、Answer Relevancy、引用正确率/溯源完整率 | 检查最终解释是否被证据支持、是否回答了问题 |
| 安全/权限 | 过期拦截率、硬冲突安全降级率、unsupported rate、错误外部图片调用数、8A `suggestion_only` 正确率、8C 未额外授权时的外部复测拒绝率 | 防止错误知识扩大能力或数据出境 |
| 运行 | 查询延迟、返回条数、上下文 token、单任务增量成本、空结果率、fallback 正确率、索引故障率 | 判断体验、成本与降级是否可接受 |
| 知识治理 | 冲突量、过期召回尝试率、复审逾期率、来源/版本/Trace 完整率 | 识别知识库本身是否失控 |

RAGAS 官方文档将 context precision/recall 归为检索层，将 faithfulness 和 answer relevancy 归为生成层；但这些自动指标不能代替“是否会越权调用工具”的确定性安全测试。[RAGAS 评测说明](https://docs.ragas.io/en/v0.1.21/getstarted/evaluation.html)

安全通过线的方向已确认：过期或撤回能力不得触发工具调用；硬冲突不得自动执行；没有可靠 evidence 时必须走已审核 baseline 或手动建议；8A 不支持能力必须变成 `suggestion_only`；8C 不得因 RAG 结果跳过新的外部出站/权限 Gate。

### 18.2 监控 worker 与 Dashboard 设计

未来新增两个独立、不可替代的后台角色：

1. `knowledge_lifecycle_worker`：检查复审周期、候选官方变更、版本替换、过期、冲突和 Provider smoke 异常，只创建待审任务/告警，不自动发布知识。
2. `rag_observability_worker`：为每一轮 query、过滤、召回、融合、重排、context packing、LLM 解释、fallback 与工具策略写脱敏事件；按知识版本、Provider、stage、错误类、模型、query 类型聚合指标，并把异常指标反查到完整 Trace。

RAG 专属本地管理员页面已实现为 [`pages/4_RAG治理看板.py`](../pages/4_RAG治理看板.py)：它从独立知识账本聚合审核知识卡/原子规则数量、生命周期、检索/建议路由、bad case、复审提醒、派生向量索引状态和最近脱敏记录。它不读取照片、用户原话、知识全文、向量、密钥或 Provider 图片请求；也不输出 Gold 指标、p50/p95、成本、自动告警或用户研究结论。上面两个 worker、**Dashboard 内的 Gold 指标聚合**和部署级管理员鉴权仍未实现；Gold 指标目前由独立 evaluator 生成。不能把“能看当前账本”写成“已自动监控 RAG 质量”。

### 18.3 Gold Set 草案

历史 v1 见 [RAG Gold Set 草案](RAG_GOLD_SET_DRAFT.md)。当前待产品负责人审核的是 [Gold Set v2](RAG_GOLD_SET_V2_REVIEW.md)：34 道开发题、18 道挑战题、20 道流程型隐藏题，覆盖工具能力、权限、隐私、过期、冲突和提示注入。v2 的答案、人工评审人数、Judge 供应商/校准和数值通过线均未冻结；不得拿它调参、训练或称为已通过评测。完整隐藏答案键需要在冻结后由产品负责人移出开发工作区，才构成真正盲测。

## 19. 一致性审计：五项 P0 决策已冻结（2026-08-29）

产品负责人已明确“通过”下列五项推荐。它们从候选方案变为本项目 RAG P0 的版本化产品规则：P0-A 先完成 SQLite + metadata + FTS 的可审计纵向切片，随后按同一边界完成 P0-B 本地 embedding/向量/RRF/rerank；二者均不提前回接图片执行链。

| 优先级 | 发现的冲突/待定项 | 推荐方案 | 原因与验证方式 |
|---|---|---|---|
| P0 | “整篇文档切片”与“一个能力/限制/失败规则一个条目”同时存在 | 采用双层结构：整篇来源为 `KnowledgeItem`；检索单元为按标题/段落/语义切出的 `KnowledgeChunk`；能力/限制/失败规则作为原子 claim 标签 | 兼顾整篇文档溯源和精确检索，避免把整篇文档塞给 LLM。用 Gold Set 比较标题切片、段落切片和语义切片的 `Recall@10`、`Precision@3`、引用正确率 |
| P0 | “先 SQLite”与“第一版混合检索”同时存在 | 分 P0-A / P0-B：P0-A SQLite + metadata + FTS5/关键词；P0-B 在同一 SQLite 权威库外接本地 embedding + 向量索引 + RRF + rerank。P0-A 先跑通 Trace，再以可替换的本地模型完成 P0-B | SQLite/FTS 先证明知识治理和 retrieval trace；混合检索新增模型、索引和评测面。两层都已完成本地验收，但未因“可检索”而扩大工具权限 |
| P0 | 召回数量与低置信阈值尚未校准 | 初始实验配置：关键词候选 8、向量候选 8；RRF 去重后取 10；CrossEncoder 重排这 10；只向 LLM 打包 3 条 direct evidence，最多 5 条。低置信先不用裸向量分数放行：要求 metadata 合法、存在 active direct evidence、关键槽位覆盖、无硬冲突；若使用归一化 reranker 分数，先以 `>=0.70` 且 top-1 与 top-2 差 `>=0.10` 作为“可解释候选”标记，低于则降级，不用于执行放行 | 5—10 可以是最终候选范围，但应区分“召回池、重排池、送给 LLM 的上下文”。不同模型/语料分数不可直接通用；Qdrant 也明确 score threshold 需要按数据和模型调参。用 Gold Set 选择满足 `Precision@3` 高且 unsupported rate 为 0 的阈值 |
| P0 | 固定“前后各 20% 上下文”缺乏语料证据 | 不设统一 20%。结构化文档保留 heading path、Provider、operation、版本和父级上下文，默认不复制固定 overlap；长文章按段落/语义组块，初始仅在同一节补相邻 1 段或约 10%—15% 上下文，超过 LLM 预算时从低 rank 的 `reference_context` 开始裁剪 | 结构化工具文档的关键上下文常是标题和参数条件，不是相邻字符。Microsoft 的 RAG 指引同样指出 chunking/overlap 需依语料迭代、没有一刀切大小。用完整限制是否被召回和引用正确率验证 |
| P0 | 8C 一处写“RAG 可提议但不能执行”，另一处写“已有 scope 覆盖可直接执行” | 推荐 P0 只允许 RAG 提议外部/混合复测，统一路由至 `manual_review`/当前本地 baseline；P1 在真实外部 Adapter、Provider Card、出站/预算 Policy、真实 receipt 和回归集都具备后，才允许在既有有效 scope 内受限自动执行 | 这不回溯现有 D-PROD-037/038：当前已实现的、同一 Tencent Provider/同一计划族内确定性自动续跑仍按原 scope 执行；本行只约束“由 RAG 新提出的外部/混合复测”，避免因为“有一条知识”就新增图片出站或误称已完成外部验证 |
| P1 | 本地 embedding/reranker 的具体模型与资源配置 | 推荐先用本地中文 `BAAI/bge-small-zh-v1.5` 做 dense embedding，SQLite FTS 做稀疏检索；候选量足够后再加本地 `BAAI/bge-reranker-base`。资料变多或出现多语言工具文档再评估更强模型 | FlagEmbedding 官方资料列出 `bge-small-zh-v1.5`，也将 `bge-reranker-base` 标为中英轻量 reranker。先小后大更符合单机 Demo 与可回滚目标 |
| P1 | 更新检查频率与人工负担 | 维持人工双周复审；本地 worker 每日只检查 `review_due_at`、smoke 状态和待审候选，产生提醒。官方文档变化检测可在每周做一次候选 diff，不自动发布 | “每日自动更新执行知识”风险过高；双周人工复审与日常提醒兼顾实时性和治理 |

### 19.1 已冻结的 P0-A / P0-B 实施包（历史；P0-C 见第 21 节）

2026-08-29 已冻结：① 双层 `KnowledgeItem/KnowledgeChunk`；② P0-A 先 SQLite FTS、P0-B 再本地混合检索；③ P0-A 仅使用关键词候选前 5，P0-B 采用关键词 8 + 向量 8 → RRF 10 → rerank 10 → LLM 3（最多 5）的实验配置，裸分数不放行工具；④ 不固定 20% overlap，结构化卡保留父级 metadata，长文只补同节相邻段/约 10%—15% 上下文；⑤ P0 的 RAG 只能提议外部/混合复测，不能执行。用户证据卡已冻结为“来源名称/版本/简短降级理由”。P0-A 已实际建立 SQLite schema、导入首批知识、FTS 检索器、Trace、定向回归和最小 Streamlit 演示；P0-B 已在同一边界内完成本地 dense/RRF/rerank、定向回归和第二个演示页。**这是当时的实施边界**：当时尚未实现 RAG worker、RAG Dashboard、新 Provider 或正式 8A/8C 回接；当前 P0-C 回接和只读 Dashboard 已在后续章节/D-TECH-039、D-TECH-040 中更新，其他能力仍待 Gate。

### 19.2 P0-A / P0-B 当时工程边界（历史；当前边界见第 21 节）

本检查点已证明两条独立本地路径：P0-A 为“已审核知识 → metadata 硬过滤 → SQLite FTS 候选 → evidence/降级理由 → 脱敏 Trace”；P0-B 在同一硬过滤之后增加“FTS 前 8 + 本地 dense 前 8 → RRF 前 10 → 本地 rerank → 同一 evidence/降级规则”。3 张审核 Provider Card 被导入为 10 条原子规则；P0-A 有 9 条回归，P0-B 有 6 条回归，二者均有默认禁止模型下载的本地 smoke。P0-B 固定记录 embedding/reranker revision，向量库仅存可重建向量/hash，模型不可用即退回 P0-A。两者都不会调用 LLM、Tencent 或任何外部图片 API；不会生成参数或授权外部复测。它们现已通过 P0-C 受限地向 `EditPlan` / 策略建议提供 evidence，具体限制见第 21 节。

### 19.3 后续优先级队列（不阻塞 P0-B，但不能遗忘）

| 优先级 | 后续选择 | 推荐方向 | 为什么现在不写死 |
|---|---|---|---|
| P1 | 首批 Gold Set 的数值通过线与告警阈值 | 先人工审阅 G01—G12，并用 Dev 集调参、Holdout 集验收；安全指标（过期/硬冲突/越权调用）要求 100% 正确，检索/生成平均指标在有足够题量后再冻结 | 当前知识库只有少量 Provider Card，先拍一个平均分会伪精确；Hit Rate 是数据集汇总指标，不能单独判断某一次 query 是否可靠 |
| P1 | 用户证据卡是否允许展开到原文段落 | P0 仅展示来源名称、版本、简短理由；公开 Beta 后根据用户是否真正需要再决定“展开受控摘要” | 原文可能长、过时或带供应商条款，不适合直接堆给 C 端用户 |
| P1 | 官方文档候选 diff 的实现和复审频率 | 每周生成候选 diff、每天检查 review/smoke 到期、每两周人工复审；任何候选都不自动发布 | 当前工具数量少，自动抓取/发布的治理成本高于收益 |
| P1 | 本地模型的多语言与资源升级 | 先以中文/中英混合工具资料的轻量本地模型验证；新增多语种 Provider 或本机延迟不达标时再改模型 | 这会改变索引重建时间、召回基线和设备要求，应以真实资料与测量结果决定 |
| P2 | 云端 embedding/向量库/托管检索迁移 | 只在受邀用户测试证明本机容量或并发不足后，单独决定数据所在地、留存/ZDR、预算、访问控制和迁移/回滚方案 | 当前已冻结“本地优先”，不能把未来可能上云误写成现在已授权的数据出境 |
| P2 | 已审计用户反馈/bad case 何时升级为可影响执行的知识 | 首先只用于解释和人工复盘；若要影响执行，必须由产品负责人复审、关联官方或真实 smoke 证据，并进入新版 Gold Set | 用户经验容易带偏、且可能与 Provider 事实冲突；不能直接变成工具放行规则 |

## 20. P0-B 实现同步与当时的下一产品决策门（历史；已由第 21 节完成）

### 20.1 已实现的 P0-B

P0-B 已采用本地 `BAAI/bge-small-zh-v1.5` embedding 和本地 `BAAI/bge-reranker-base`，以固定 revision 运行；模型正常运行只从 `storage/model_cache/` 读取，页面不触发下载。独立 `storage/knowledge_vectors.sqlite3` 仅保存来源 chunk 的归一化向量和 hash；SQLite `knowledge.sqlite3` 仍是审核知识的唯一权威来源。默认禁止下载的真实 smoke 已完成：不读照片、原话或人脸向量，不调用 LLM、腾讯或图片工具，瘦脸/唇厚/外发拒绝/缺槽四种路由均符合预期。完整工程、测试、Trace 和冷/热启动证据见 [RAG_P0B_HYBRID_RETRIEVAL_GATE.md](RAG_P0B_HYBRID_RETRIEVAL_GATE.md)。

### 20.2 现在必须停下的原因

P0-B 只解决“在什么已审核资料中、以什么顺序找证据”。一旦将它正式接到 8A/8C，就会改变 Agent 的真实行为：某条 evidence 是否可作为规划输入、检索 miss 是否应停下、是否能提出新 Provider、何时注入给 LLM、怎样评测错误选择，都需要产品负责人决定，不能由本地排序模型默认决定。

### 20.3 下一个产品负责人决策 Gate：RAG 回接 8A / 8C

进入下一模块前，需要按“背景 → 候选 → 冻结 → 开发 → 真实 Trace”讨论并决定：

1. 哪些节点先回接：只接 8A 规划前，还是同时接质量门、8C 策略选择和失败路由；
2. `evidence_found`、`manual_suggestion`、`baseline_fallback`、`retriever_miss_suspect` 各应怎样影响原有确定性 baseline；
3. 新 Provider Card / Adapter 的准入顺序、是否先做一个非图片工具，及任何图片出站如何重新走权限/预算 Gate；
4. 首批人工 Gold Set 的 Dev/Holdout、允许调参的范围和何时冻结 Recall/引用/安全指标；
5. RAG evidence 进入 LLM 时的最大条数、用户可见解释、Trace 与 Dashboard 字段。

在这些项冻结前，P0-B 不能驱动图片编辑、外部/混合复测或自动新工具调用。

## 21. P0-C 正式回接 8A / 8C：冻结决策、实现与验收（2026-08-29）

> 本节优先于第 20 节的“下一 Gate”历史描述。第 20 节记录当时为什么必须停下；本节记录产品负责人完成讨论后的实际冻结与工程结果。

### 21.1 产品设计：把“聪明检索”限制为可审计建议

**背景与问题。** P0-A/P0-B 已能回答“哪个已审核工具有这项能力”，但若它们始终不回接 8A/8C，就只能证明本地检索器存在，不能说明 Agent 如何利用工具知识。反过来，若把排名结果当作工具授权，RAG 又会绕过外部图片处理同意、Provider Card、Adapter、预算、状态机和真实回执。

**调研与判断。** 产品负责人将“检索证据”“执行能力”“用户/LLM 的交互选择”拆开审计：检索器可以错召回、没有召回或遇到互相矛盾的资料；LLM 可以解释/建议，但不能裁决硬事实；只有确定性系统才知道当前 scope、Adapter、权限、成本与状态是否允许真实动作。

**冻结决策。** RAG 只能提议，不能授权。它可在以下节点被消费：

1. 8A 生成 `EditPlan` 前；
2. 8C 选择复测策略时；
3. 工具失败后寻找降级方式时；
4. 新增 Provider 时；
5. 参数或权限存在冲突时。

`RagAdvisoryDecision.execution_authorized` 永远为 `false`。即使 Agent/LLM 建议一条下一步，也必须经状态机、权限/预算 Policy、有效确认 scope、Provider Card、Adapter 和真实 receipt 逐项放行。该规则只约束“由 RAG 新提出的能力或 external/hybrid 复测”；原有同一 Tencent 计划族的确定性自动续跑仍按其既有 scope/Policy 执行，不被 RAG 扩大或改变。

### 21.2 P0-A / P0-B 的分层检索与 LLM 上下文边界

```text
P0-A: FTS 前 5                    ← 关键词通道，快速兜底精确匹配

P0-B: 关键词 8 + 向量 8           ← 双路召回：FTS 取 8 条 + 向量搜索取 8 条
       ↓
       RRF 前 10                  ← 用 RRF 融合两路结果，取 Top 10
       ↓
       重排前 10                  ← 用 Cross-Encoder 等重排序模型精排
       ↓
       给 LLM 3 条、最多 5 条      ← 最终上下文，控制 Token 消耗
```

P0-A 的 FTS 前 5 是快速、可解释的精确匹配兜底；P0-B 的 8+8/RRF/rerank 用于处理同义表达和文档措辞差异。当前 P0-B/P0-C **没有调用 LLM**：运行时最多采纳 3 条 evidence。最后一行是未来 LLM 解释层的上下文预算——默认 3 条 direct evidence，硬上限 5 条；它不是“给模型更多资料就可执行”的放行规则。Top-K、重排分数和上下文长度必须由 Gold Set/holdout 校准，不能永久拍脑袋或变成工具权限阈值。

### 21.3 direct / reference / conflict 的三层证据路由

| 证据类别 | 含义 | 系统可以做什么 | 系统绝不能做什么 |
|---|---|---|---|
| `direct_evidence` | 当前有效、适用且无硬冲突的已审核事实 | 作为已有规划器/策略选择器的参考，写入 `knowledge_refs` | 生成参数、替代确认、授权执行 |
| `reference_information` | 解释背景、限制或上下文的辅助资料 | 给用户/LLM 解释，帮助人工判断 | 单独放行工具 |
| `conflict_information` | 同一关键事实存在相互矛盾的已审核来源 | 带回所有限定范围内的冲突来源、写 Trace/bad case、停止执行 | 由用户或 LLM 任选一条冲突事实执行 |

无冲突时，采用 direct evidence，reference information 只补充解释。出现冲突时强制 `CONFLICT_BLOCKED`：系统必须把两侧来源和冲突原因摆出来，并且只允许用户/LLM 选择 `manual_review`、`manual_suggestion` 或 `stop` 的非执行路径；不能选择哪条事实直接放行，不能继续现有 baseline。

### 21.4 miss、baseline 与 bad case 的精确规则

对“依赖 RAG 的新能力/新策略”，检索器 miss、索引不可用、关键槽位缺失或重排后没有 direct evidence 时，流程立即停止该 RAG 分支并返回“当前没有足够的已审核依据，我不知道”。LLM 不能补写能力、参数或 API。系统同时以 `RagBadCaseRecord` 记录脱敏 query hash、stage、候选计数、引用和 reason code，将原因明确归到：

- `no_active_knowledge`：知识库没有可用文档；
- `retriever_empty`：metadata 合法但召回为空；
- `reranker_no_direct_evidence`：召回/重排后没有可采纳的直接证据；
- `index_unavailable`、`missing_critical_slots` 或 `hard_fact_conflict`。

若当前已有一个**独立配置且已经过普通 Gate** 的 Provider Card baseline，系统可按原规则保留它，路由为 `baseline_degraded`；这只是“不让 RAG 故障破坏原有安全能力”，不是以 RAG 放行、替换或扩大 baseline。没有这种 baseline 时必须 `unknown_stopped`，只能手动建议或停止。

### 21.5 新 Provider 的准入顺序

新增工具被 RAG 检索到后，仍必须经过：官方来源/License/地区/隐私/成本资料 → 候选 Card → Adapter shell 与测试替身 → CAM/权限/预算 Gate → 真实 smoke 与 receipt → RAG Gold 回归 → 产品负责人冻结 → `reviewed_active`。任一环节未通过时，RAG 只能解释候选，不能上传图片或产生执行计划。

### 21.6 首批 Gold Set / holdout 锚点

产品负责人冻结首批验收锚点为 `RAG-G01` 与 `RAG-G09`：

- `G01`：`FaceLifting` 直接证据可进入确定性规划器，但绝不生成滑杆值或执行授权；`EditPlan` 仍须确认。
- `G09`：两条 active fixture 对同一关键事实冲突时，必须带回双方来源、阻断执行并留 `hard_fact_conflict` bad case；用户/LLM 不能解除阻断。

二者已经实现为自动化安全回归，是先行验收锚点；尚未替代未来人工 Gold Set 的问法、评审人数、holdout 划分和数值指标。

### 21.7 实际工程实现与本地 Trace

`services/rag_advisory.py` 把 P0-B 输出转换成 `RagAdvisoryDecision`；`storage/knowledge_store.py` 记录 advisory run 和 RAG bad case；`EditPlan`、`VerificationStrategyProposal` 与 `VerificationResult` 增加可追溯 `knowledge_refs`。`app.py` 在 8A 生成计划前、8C 选择策略前调用本地 P0-C。P0-C 不接收照片、原始用户文本、人脸向量、密钥或 Provider 回执正文，也不调用 LLM、腾讯或任何新 Provider。

真实本地 smoke `scripts/smoke_rag_advisory.py` 已跑通：G01 为 `advisory_available` 且 `execution_authorized=false`；G09 返回两条 fixture 来源且 `conflict_blocked`；未知能力为 `unknown_stopped`。临时知识账本显示 5 个来源、12 条规则、3 条 advisory run、2 条 bad case。该 smoke 只证明本地受限 evidence/路由链，不证明图片效果、external/hybrid 复测或新 Provider 已可用。详细交付见 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](RAG_P0C_ADVISORY_INTEGRATION_GATE.md)。

### 21.8 仍待讨论的下一门

下一产品决策门不再是“是否把 RAG 回接 8A/8C”，而是：Gold Set v2 的逐题审核与运行、lifecycle/observability worker、候选新 Provider 的正式准入，以及 external/hybrid 复测 Adapter。P0-C 与本地 Dashboard 已实现，但不自动授权上述任何能力。

## 22. 2026-08-29｜评测范围、Provider 方向、混合复测与 Dashboard（当前状态）

### 22.1 已冻结的产品方向

| 方向 | 冻结结论 | 已实现 / 未实现边界 |
|---|---|---|
| RAG 评测范围 | 同时评估工具能力、权限、隐私、过期、冲突与提示注入；产品负责人是唯一人工事实权威；盲审 LLM Judge 可看机器分数摘要但不能看 Gold 答案，暂不加入第二位人工评审 | v2 评测材料、离线运行器与盲审输入已实现；public/holdout deterministic predictions 与一次私有聚合评分已完成，当前基线 `FAIL`，未用于 hidden 逐题调参或训练 |
| 细项/批量扩展 | 选择“参数级人像美化 SDK/API”路线，目标覆盖五官细项、脸型细分和逐图独立批量一致性；两条候选路线并行准入 | 火山美颜 API V2.0 与腾讯特效 SDK 的 Candidate Card/Adapter/权限预算/离线测试已实现；真实 live smoke、Gold 回归和产品冻结仍未完成 |
| external/hybrid 复测 | 本地几何是“是否朝母版改善”的主证据；CompareFace 只能作同一人物辅助 guard | 新 Adapter、出站策略、真实回执和回归集未实现；RAG 只能提议，不能执行 |
| RAG Dashboard | 保留 SQLite/Trace 为权威账本，并新增本机只读管理员可视化 | 页面与安全聚合测试已完成；无自动 worker、无 Gold 指标、无生产鉴权 |

### 22.2 Gold Set v2 的审核与建议门槛

详见 [RAG_GOLD_SET_V2_REVIEW.md](RAG_GOLD_SET_V2_REVIEW.md)。没有跨项目通用的“平均 80 分就通过”：安全类题必须 `100%` fail-closed / `0` 次错误放行；其余 `Recall@5` ≥90%、`Precision@3` ≥80%、MRR ≥80%、nDCG@5 ≥85%、路由/证据关系正确率 ≥90% 分开报告。未来自由生成解释时，Faithfulness/引用支持率 ≥95%、人审—Judge 一致率 ≥80%、Hidden—Dev 主要指标差距 ≤10 个百分点。以上是产品负责人已冻结的项目发布门槛，不是行业统一标准、更不是已经跑出的结果；必须同时报告样本数和错误清单。

### 22.3 Dashboard 的当前最小证据链

```text
已审核 KnowledgeItem / KnowledgeChunk
→ 独立 SQLite 脱敏 query / advisory / bad-case 事实
→ rag_dashboard_snapshot + knowledge_catalog
→ Streamlit 本机管理员页面
```

页面只呈现安全聚合和最近脱敏记录；不能反推照片、用户原话、source body、向量、密钥或隐藏思维链。它帮助定位“知识是否过期、检索路由是否频繁 fallback、哪类 bad case 增多”，但不替代 Gold Set、人工审核或真正的监控 worker。

## 23. 2026-08-30｜Gold Set 门槛与双 Provider 并行准入（当前冻结）

### 23.1 评测冻结

产品负责人已冻结：v2 使用 34 道开发题、18 道挑战题、20 道隐藏题；同时测工具能力、权限、隐私、生命周期、冲突和提示注入。唯一人工事实审核由产品负责人完成，暂不增加第二位人工评审；盲审 LLM Judge 可看到本次运行的机器分数/指标摘要，但看不到 Gold 答案、答案键、开发标签或实现版本。安全题 100% 正确拦截、0 次错误放行；检索/路由门槛为 Recall@5 ≥90%、Precision@3 ≥80%、MRR ≥80%、nDCG@5 ≥85%、路由/证据关系正确率 ≥90%；未来生成解释的 Faithfulness ≥95%、人审—Judge 一致率 ≥80%、Hidden—Dev 差距 ≤10 个百分点。隐藏集运行器只能接收无答案输入，答案键由产品负责人单独保管后才进行真正盲测。Precision C、Holdout A、Safety ID C 的后续冻结与实现，以本文件 26 节为准。

### 23.2 双 Provider 准入冻结

产品负责人选择同时推进火山美颜 API V2.0 静态/批量路线与腾讯特效 SDK 细粒度参数路线。两条路线当前只允许建立候选 Card、Adapter shell、权限/预算 preflight、离线测试和 live smoke 入口；任一候选都必须完成官方能力/License/隐私/地区/成本证据、真实 receipt、Gold 回归和产品负责人冻结，才能变为 `reviewed_active`。RAG 仍只能提议，不能替候选 Provider 授权或发送照片。

### 23.3 评测与 Provider 的关系

Gold Set 先验证检索、证据分层和路由安全；新 Provider 的参数效果、真实费用、p50/p95、批量并发、图片留存和 License 另做 Provider Gate。不能用 RAG 命中率替代图片效果，也不能用一次 Provider smoke 替代 RAG 安全评测。

## 24. 2026-08-30｜Gold evaluator 与双 Provider candidate shell 实施收口

### 24.1 本轮已完成

- `services/rag_gold_eval.py` 与 `scripts/evaluate_rag_gold_v2.py` 已实现离线评分：Precision/Recall/Hit@K、MRR、nDCG、route/evidence/relation accuracy、hard-safety Gate，以及本项目冻结阈值的 `project_threshold_gate`。
- public 运行包为 34 道 dev + 18 道 challenge（仅题干）；答案键独立保存；holdout 运行包为 20 道 `case_id + query`，不读取答案键。
- 盲审输入只包含题干、系统输出和安全的机器事实摘要（候选数量/耗时/实际证据计数等）；产品负责人仍是唯一事实审核者，暂无第二位人工评审。live LLM Judge 入口保留但默认禁用，当前只提供本地 fake Judge 结构检查。
- 火山美颜 API V2.0、腾讯特效 SDK 均已建立 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 smoke；代码不导入 SDK、不发送图片、不读取密钥，候选未升级为 `reviewed_active`。

### 24.2 当前真实运行结果

```text
pytest                                      → 146 passed, 4 warnings
Gold public deterministic baseline          → 52 题；Precision@3=47.44%，其余当前公开指标=100%，project_threshold_gate=FAIL
Gold holdout deterministic baseline         → 20 题仅输入包；hidden_answer_key_read=false
Private holdout aggregate score             → route=25.00%，Recall@5=38.24%，MRR=52.94%，nDCG@5=41.56%，project_threshold_gate=FAIL
Private Markdown hard safety                → MANUAL_REVIEW_REQUIRED（natural-language must_not 尚未机评化）
Volcengine candidate smoke                  → status=not_run，allow_live_required，network_call=not_attempted
Tencent Effect candidate smoke              → status=blocked，candidate/admission gates 未满足，network_call=not_attempted
```

HTML/Markdown/JSON 审计产物位于 `reports/`；它们不含答案键、原始照片、向量、密钥或系统隐藏推理。当前结果是“评测基础设施可运行、候选准入壳可回放”，不是 RAG 通过、图片效果通过或新 Provider 可调用。

### 24.3 下一道 Gate

隐藏答案键已于 2026-08-30 移至产品负责人独立保管位置，流程见 [保管回执](RAG_GOLD_SET_V2_HOLDOUT_CUSTODY.md)。公开与私有聚合评测现已跑完，且当前基线未通过。下一道 Gate 不是“继续按隐藏题补规则”，而是审核 canonical 事件目录、在工作区外独立生成/保管 v3 holdout 与 machine-normalized 答案键，并完成候选 Provider 的书面能力/License/隐私/地区/价格/延迟证据、真实 receipt、Gold 回归和新的产品冻结。Precision C、Holdout A、Safety ID C 已冻结；RAG 继续只能提议，不能改变图片执行权限。

## 25. 2026-08-30｜Failure Pattern 分析、自校正候选与可视化闭环

### 25.1 背景与产品判断

Gold Set v2 的公开集表现较高、隐藏集聚合表现较低，说明“把当前公开题跑通”不等于 RAG 已具备泛化能力。本轮没有读取隐藏答案、题干或逐题 ID 来补规则，而是将公开逐题事实与隐藏集仅聚合的错误类型分开，建立一个可以反复运行、可回滚、可审计的 failure-pattern 闭环。核心边界保持不变：自校正只能提出候选，不能自动改变权限、Provider 白名单、参数阈值或执行链。

### 25.2 实际证据与分层诊断

`services/rag_failure_analysis.py` 只读取 public cases/annotations/predictions，以及可选的私有 aggregate JSON；它不读取私有答案键、隐藏题目、图片、人脸向量、原始用户文本、LLM、网络或 Provider。当前报告发现：

1. **稀疏 Gold 分母模式（观察事实）。**公开 52 题中 51 题的 Gold evidence 少于 3 条；固定分母 Precision@3 为 47.44%，按实际返回条数计算的诊断值为 100%。这说明固定 K=3 与稀疏答案之间存在测量口径张力，但不能据此擅自修改已冻结 Gate。
2. **隐藏集分布外模式（聚合事实 + 有限推断）。**隐藏 20 题中有 17 题被聚合为错误；错误类型计数为 route mismatch 15、evidence set mismatch 14、relation mismatch 13。由于没有逐题 Gold，报告只把它解释为“未见表达/组合或路由泛化风险”，不把某个具体根因写成事实。
3. **硬安全事件格式模式（观察事实）。**隐藏 hard-safety 当前为 `MANUAL_REVIEW_REQUIRED`，原因是私有 `must_not` 仍是自然语言，尚未安全转换为 canonical event ID；不能伪报 `PASS`。
4. **执行边界模式（运行事实）。**公开 hard-safety 为 `PASS`，候选 Provider smoke 均未联网；因此优化范围只能是查询归一化、证据组织和评测可观测性，不能以“提高召回”为由放宽图片出站或工具授权。

### 25.3 SOP 与本轮自校正候选

当前 SOP 固定为六步：冻结事实快照 → 按指标/检索/关系/安全层定位 → 一次只提出一个受限修正 → 公开集安全回归 → answerless holdout 聚合验证 → 产品负责人人工批准后发布。每一步都有禁止事项：不读取隐藏答案、不把 LLM 自评当事实、不降低安全/项目阈值、不删除失败题、不自动升级候选 Provider。

本轮候选为 `rag-correction-candidate-v0.1`：仅增加经审核的英文/领域同义词归一化（例如 `slim face`→`瘦脸`、`eye width`→`眼宽`、`no cloud transfer`→`不外发照片`），并在内存中运行，不写入现役 baseline。公开 52 题回归的 route/evidence/relation/MRR/Recall@5/nDCG@5/hard-safety 均未回退，候选与现役指标差值记录为 0；`regression_gate=PASS`，但 `project_threshold_gate` 仍为 `FAIL`。因此本轮候选**不升级、不改变当前规则**，可随时丢弃并回到 deterministic baseline。

### 25.4 报告、看板与可回放 Trace

脚本 `scripts/analyze_rag_failures.py` 生成脱敏 `reports/rag_failure_patterns_v1.json/.html`。`pages/4_RAG治理看板.py` 通过 allow-list 展示公开评测 HTML、隐藏集聚合 HTML 和 failure-pattern HTML；`pages/5_RAG优化看板.py` 展示分层指标、隐藏错误类型、失败模式、候选回归差值和 SOP。看板只读，不提供“应用修正”按钮；不发现任意文件，不读答案键、照片、向量、原始文本或密钥。

可回放链路为：

```text
answerless public run
→ evaluator + public annotations（独立步骤）
→ private holdout aggregate（仅产品负责人受限环境）
→ failure analyzer
→ proposal-only correction candidate
→ public regression + delta
→ JSON/HTML report
→ 两个本机只读 Dashboard
→ 产品负责人批准/回滚
```

本轮结论是“问题可定位、候选可回归、过程可观察”，不是“RAG 已通过”。下一道真正决策门仍是稀疏 Precision 口径、下一份独立 holdout、canonical hard-safety 事件以及新 Provider 的正式准入；在这些门冻结前，failure analyzer 不会改变 P0-C 的 `execution_authorized=false`。

## 26. 2026-08-30｜三项评测治理决策冻结与实现

### 26.1 Precision：C，双口径并行报告

**背景与问题。**公开集 52 题中 51 题的 Gold evidence 少于 3 条。若固定用 3 做分母，即使题目只有一条正确依据且系统准确找回，单题最高也只有 `1/3`；但如果直接把公式改宽，又会破坏历史可比性并把指标变成“为了通过而修改”。

**调研与判断。**因此把“是否找到该找到的知识”和“返回列表里有多少噪声”分开看，并保留旧口径作为历史事实。评测器现在同时计算：固定 `Precision@K`（命中数 / K，继续作为历史 `project_threshold_gate` 的输入）、覆盖式 `Precision@K`（命中数 / `min(K, Gold 条数)`，解释稀疏 Gold 的覆盖情况）、返回式 `Precision@K`（命中数 / 实际返回条数，诊断额外噪声）。另外按 Gold 证据条数分层，避免一个聚合数字掩盖样本结构。

**冻结决策。**采用 C：三项指标并行展示，固定分母不删除、不追溯改写；覆盖式和返回式先作为诊断与产品分析，不自动替换当前发布门槛。当前 public 结果因此是固定 `Precision@3=47.44%`、覆盖式 `Precision@3=100%`、返回式 `Precision@3=100%`，`project_threshold_gate` 仍为 `FAIL`，不能写成 RAG 已通过。

### 26.2 Holdout：A，保留 v2 诊断并新建独立 v3

**背景与问题。**已有 v2 隐藏集已被用于一次私有聚合诊断；若继续用它逐题调参，会让 holdout 失去独立性。完全删除旧结果又会丢失“公开集高、隐藏集低”的真实证据。

**冻结决策。**采用 A：v2 runtime 和聚合结果保留为历史趋势/泛化诊断，不再作为逐题监督；创建 `data/evaluation/rag_gold_v3_holdout_runtime.template.json` 作为新独立集的无答案格式模板。v3 的题目和答案必须由产品负责人在工作区外独立生成和保管，开发者只接收 `case_id + query`，正式评分最多一次；模板为空不代表 v3 已完成或已通过。

### 26.3 安全事件 ID：C，确定性字典 + 产品负责人确认

**背景与问题。**私有 Markdown key 的 `must_not` 是自然语言，系统无法安全判断“观察到的事件”和“禁止事件”是否同一件事。若工程师凭语义猜测，就可能把未知风险伪报成 `PASS`。

**调研与判断。**安全事件不是 LLM 分类任务，而是评测合同中的受限词表。新增 `core/rag_safety_events.py` 与 `data/evaluation/rag_safety_event_catalog_v0.json`：48 个公开历史标签映射到稳定的 `RAG_EVT_*` ID；已知别名可确定性归一化，拼写错误/新措辞不做模糊匹配。遇到未知标签时，评分器输出 `MANUAL_REVIEW_REQUIRED`，而不是猜一个近似 ID。

**冻结决策。**采用 C：字典版本化、映射可审计、由产品负责人确认后才作为安全自动门；当前公开词表已可自动复测，私有旧 Markdown 仍保持人工复核。该实现不把 hidden 答案带回工作区，机器化 key 仍需由产品负责人在受限目录中迁移/确认。

### 26.4 已实现链路与下一道门

```text
双口径 evaluator
→ canonical safety event dictionary
→ v2 历史诊断 / v3 独立 holdout template
→ public regression + safety regression
→ 脱敏 JSON/Markdown/HTML + RAG 优化看板
```

已更新 `services/rag_gold_eval.py`、私有 aggregate 投影、failure analyzer、page 5 看板、公开事件目录和 v3 custody 文档，并补充单元测试。评测仍是离线、无网络、无照片、无 LLM；RAG 的 `execution_authorized=false`、候选 Provider fail-closed 和 hidden 独立性未改变。下一道门是产品负责人审核 canonical 事件目录、生成并审核 v3 Gold/holdout，以及决定是否批准某个候选 Provider 进入正式准入流程。

### 26.5 2026-08-30｜审核确认、v3 工作区外草案与腾讯测试 License

<span style="color:#C00000"><strong>本轮状态更新。</strong> 产品负责人已审核通过公开 `rag-safety-events-v0.1` 目录。目录状态由 pending 更新为 `product_owner_approved_2026-08-30`；已知 legacy label 和 `RAG_EVT_*` 仍可确定性归一化，未知事件继续 `MANUAL_REVIEW_REQUIRED`，不因审核通过而放宽安全门。</span>

<span style="color:#C00000"><strong>v3 Holdout。</strong> 按 Holdout A 生成了工作区外的 `OWNER_REVIEW_DRAFT`：36 道重新表述题目、分离的 canonical event 答案草案和逐题审核表，位置在项目仓库之外的受限目录。它们不被当前 evaluator、RAG retriever、应用或公开报告读取；产品负责人完成审核后，正式 runtime 仍只能导入无答案的 `case_id + query`。在审核完成前，不称为正式 Gold、不运行正式盲测、不用来逐题调参。</span>

<span style="color:#C00000"><strong>腾讯 Web License。</strong> 产品负责人允许提交测试 License。控制台当前已显示项目 `portrait-consistency-agent-demo` 与精确主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app` 的测试 License 为“正常”，有效期显示为 2026-08-30 至 2026-09-13。密钥和 Token 属于敏感凭据，永不写入本仓库、Trace、报告或回复；该资源状态只作为外部控制台事实记录。</span>

<span style="color:#C00000"><strong>下一道门。</strong> 现在不是继续修改当前 baseline，而是请产品负责人逐题审核 v3 草案；审核通过后再由受限 runner 导出 answerless runtime，并仅做一次正式验收。候选 Provider 的 License/预算/隐私/真实 receipt/Gold 回归仍独立 fail-closed；RAG 继续只能提议，不能授权图片出站。</span>

## 27. 2026-08-30 当前 Provider 与部署收口

火山美颜 API V2 的官方准入/计费资料已补齐到 [Provider Spike](PROVIDER_VOLCENGINE_SPIKE.md)：需要购买支持后付费 API 的创点套餐，公开资料没有个人免费额度或按次 API 价格；公开 SDK 年包起价也不是 V2 API 报价。产品负责人因此冻结 V0 不购买、不填 Key、不发图片，火山只保留 `candidate`/fail-closed 壳；RAG 命中它的知识不能改变这一权限。当前图片执行只走已验证的腾讯 BeautifyPic。

部署方面，代码已推送至私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)，Streamlit Community Cloud 仍需用户在控制台创建 Private App、选择 `main/app.py` 并配置 Secrets。部署包已通过 `pytest 146 passed, 4 warnings`、Ruff、format、compileall、`git diff --check` 和 HTTP 200 启动探针；这些是构建/启动证据，不是 RAG 通过、生产持久化或公网用户测试证据。
