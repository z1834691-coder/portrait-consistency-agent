# 开发进展｜母版人像一致性 Agent

> 这份文档是项目的运行记录。每完成一个检查点，必须更新“完成内容、验证证据、未做事项、待决策项和下一步”。
>
> 说明：早期检查点中的“未完成”是当时的历史快照；当前真实状态以本文档末尾最新检查点和对应证据为准。

## 总目标

在 2026-09-04 前完成可运行 Demo、可录制演示和可追问证据包；核心闭环为“母版 → 同一人物/质量门 → 澄清 → 特征差异与计划 → 确认 → 腾讯 API → 修后复测 → 可接受/继续调整/重新上传/人工复核”。

## 检查点总览

| 检查点 | 内容 | 状态 | 通过标准 |
|---|---|---|---|
| 1 | 项目骨架、Git、进展/决策记录 | 已完成 | 树结构清晰，Git 可追踪，文档说明上下文与待决策项 |
| 2 | 本地 Python 环境与开发命令 | 已完成 | 可创建隔离环境、同步依赖、运行基础检查 |
| 3 | 六个数据合同与合同测试 | 已完成 | 合法数据可序列化，非法数据被拒绝 |
| 4 | 腾讯能力卡、API Adapter、smoke 脚本 | 已完成（含真实 live Gate） | 无密钥时安全失败；有密钥时可保存 RequestId/结果/错误 |
| 5 | 最小 Streamlit 外壳、SQLite/JSONL trace | 已完成 | 从界面创建 session，并能追溯 IntentFrame、脱敏事件和预置的 ProviderRun 审计投影 |
| 5.5 | 产品规则与六合同人工审计 | 已完成并冻结 | 用户确认的产品语义、遗漏决策和合同影响有单一记录 |
| 5.6 | 后四合同审计、Prompt 规格与耦合检查 | 已完成并冻结 | 四合同字段、完整 Prompt、跨模块不变量和五项最终决策可追溯 |
| 5.7 | 合同 v0.2、六表存储与执行版 PRD | 已完成（历史） | 当时 29 个测试通过；后续升级见 6.6 |
| 6 | 几何/质量 CV + 独立主体匹配门 + Profile v0 | 已完成（CompareFace live 成功；IMS Pass/Block 路由样例均有真实回执） | 单张有效/无效输入有可读结果，且不输出未经校准的指数；IMS 两种样例路由已验证 |
| 6.6 | 产品设计冻结、合同 v0.3、匿名运营账本与 Dashboard | 已完成 | 54 个测试通过；规则、合同、迁移、Dashboard、文档和失败回执同步 |
| 7 | LLM 意图澄清与 fallback | 已完成并真实 live 验证 | DeepSeek 文本 Adapter、Schema、显式文字授权、本地 fallback 和一次真实 Provider receipt 均已验证 |
| 8A | 局部差异诊断与确定性 EditPlan 草案 | 已完成 | 严格双眼测量、逐特征差异、版本化映射、待确认计划和脱敏 Trace 可重复运行 |
| 8B | 用户确认 → BeautifyPic → ProviderRun（修后复测不含在本步） | 已完成（离线验证） | Happy Path + 过期/换图/超时/取消/重复点击均可重复演示；不得跳过确认、不得自动重试、结果不得落盘 |
| 8C-1 | 修后结果观察 → `VERIFICATION_STRATEGY_SELECT` → VerificationResult 趋势路由 | 已完成首个工程切片 | 结果图内存解码、逐特征趋势、目标证据、策略 allow-list、脱敏 Trace；6 条测试 + fixture smoke |
| 8C-2 | 有界三轮计划族、父子回执血缘、自动续跑与反馈硬停止 | 已完成离线验证；自动续跑代码已同步 | 每轮新子 plan/run；只有可验证累积改善才能生成子计划；首次确认 scope 内自动执行/复测，preflight、trigger、hash 和结果全留 Trace |
| RAG Gate / P0-A + P0-B + P0-C | 工具知识库、索引、召回/融合、受限 evidence 回接 | **已完成本地验收** | 已实现独立 SQLite 权威库、3 张审核 Card/10 条原子规则、metadata + FTS5、local dense/RRF/rerank、依据卡、脱敏 Trace，以及 8A/8C 的 direct/reference/conflict evidence 回接；不接 LLM、新 Provider、图片执行或 external/hybrid 复测 |
| Gold Set v2 evaluator / blind input | public/annotations/holdout 隔离、指标、人工审核材料 | **已完成本地验收；当前基线未通过** | 52 题 public + 20 题 holdout 输入、阈值 Gate、HTML/Markdown/JSON 报告和私有 aggregate-only scorer 已实现；public/private aggregate 均 `FAIL`；live Judge 未实现 |
| 新 Provider candidate shells | 火山美颜 API V2.0、腾讯特效 SDK | **已完成离线验收；火山 V0 暂缓** | Card、typed Adapter、权限/预算 preflight、smoke 已实现；两者均未联网/发图，仍为 `candidate`，当前实际执行链只用 Tencent |

## 检查点 6.1｜真实照片质量门（已完成并验收）

### 本小步目标

先把“这张照片能不能稳定分析/修图”从主流程中独立出来。质量门不判断是否为同一人物，不计算母版一致性，也不把质量置信度展示成接受概率。

### 已完成

- 2026-08-27：增加 `services/photo_quality.py`，使用 Pillow 做安全解码、EXIF 方向归一化，使用 OpenCV 内置正面人脸/眼睛级联做 V0 可解释检测；图像只在内存处理，不写入数据库或 trace。
- 2026-08-27：增加真实输入预检：PNG/JPEG/BMP、文件大小、长边/短边、透明通道等 Provider 约束；不合格输入返回可读的重新上传原因。
- 2026-08-27：增加清晰度（Laplacian 方差）、曝光比例、人脸尺寸、人脸完整性、眼睛可见性等指标，并生成只用于质量/可编辑性路由的两个置信度。
- 2026-08-27：增加 `PhotoObservation` 安全投影，不暴露人脸坐标；增加 `to_photo_quality_result`，要求把同人证据和内容安全证据作为独立输入后才能组成完整合同。
- 2026-08-27：`pyproject.toml` 增加 `numpy` 与 `opencv-python-headless`，并更新 `uv.lock`。

### 验证证据

- `uv run pytest tests/test_photo_quality.py -q`：`5 passed`；覆盖损坏文件、真实 Pillow 解码/指标、模拟正脸检测、未完成安全门、同人不确定与质量分层路由。
- `uv run ruff check src/portrait_consistency_agent/services/photo_quality.py tests/test_photo_quality.py`：通过。
- `uv run ruff format --check src/portrait_consistency_agent/services/photo_quality.py tests/test_photo_quality.py`：通过。

### 当前边界与下一步

- Haar 级联只是 Demo 的可解释基线，不宣称对所有角度、遮挡、妆容稳定；阈值是版本化工程策略，后续用授权样本和人工标注校准。
- Streamlit 已能运行本地质量门并展示路由结果；页面提供安全检查、Profile 锁定和当前会话 CompareFace 按钮。页面侧真实 `PhotoQualityResult` 需要安全/同人门通过后才落库；CompareFace live 已验证，后续进入意图澄清与端到端执行开发。

## 检查点 6.2｜当前会话同人 Adapter（已实现并完成真实 live 验证）

### 本小步目标

把“是不是同一位本人”从质量置信度和未来一致性判断中分离出来，只对当前会话上传的母版与目标照做 1:1 比对；供应商原始分只用于后台路由证据，不向 V0 用户展示为概率或一致性分数。

### 已完成

- 2026-08-27：增加 `services/tencent_subject.py`，接腾讯 IAI `CompareFace` API `2018-03-01`，固定请求模型 `3.0`、`QualityControl=0`、`NeedRotateDetection=0`。
- 2026-08-27：增加 `SubjectMatchPolicy`，将原始分按版本化策略路由为 `match/uncertain/no_match`（V0 临时边界为 70/50，后续可用授权样本校准）；未校准原始分永远不填 `subject_match_confidence`。
- 2026-08-27：增加 `smoke_tencent_compare_face.py`，默认不读图不联网，live 模式只读用户明确授权的两张图片并输出脱敏 evidence。
- 2026-08-27：新增 `data/provider_cards/tencent_compare_face.json`，记录官方端点、输入限制、模型和路由策略。

### 历史验证证据与阻塞（权限/服务开通前）

- request 构造、原始分保持、缺密钥安全失败和 Provider Card 测试均通过。
- 真实同图对同图 smoke 已到达腾讯并返回 `RequestId=b1584fbb-f750-4536-b4a5-2b6c3803a67b`，但错误为 `AuthFailure.UnauthorizedOperation`；说明端点、SDK、签名和错误回执通路已工作，当前 CAM 身份缺少 `iai:CompareFace` 调用权限。
- 在权限补齐前，不会重复发起付费请求，也不把失败写成“同人能力已验证”。

## 检查点 6.3｜内容安全 Adapter（已实现；真实拒绝与允许样例已验证）

- 2026-08-27：增加 `services/tencent_safety.py`，接腾讯 IMS `ImageModeration` API `2020-12-29`，输入只在本次调用内存中转为 Base64；`BizType` 可由 `.env` 配置。
- `Pass` 映射为 `PASSED`；`Review/Block` 在 V0 都保守映射为 `BLOCKED`，防止未定义人工审核策略时放行高风险图片。
- 新增 `data/provider_cards/tencent_image_moderation.json` 和对应测试；随后已进行一次用户授权的显式 live smoke，返回 `RequestId=42c6ed4d-f035-466c-b775-4728dd43ca93` 与 `UnauthorizedOperation.Unauthorized`。
- 该回执证明签名、端点和错误审计通路存在，但没有产生 `Pass/Review/Block` 结果；需补齐 IMS 服务/调用权限后才重测，不能称为内容审核成功。

### 检查点 6.3.1｜用户关联 IMS 后的第二次真实复测（仍未通过）

- 2026-08-27：用户确认 IMS 已关联后，对同一张明确授权的单人 JPEG 再运行一次 `smoke_tencent_image_moderation.py --allow-live`；
- 请求真实返回新的 `RequestId=9385fe01-f182-4d74-9a52-3e6eb8be824a`，仍为 `UnauthorizedOperation.Unauthorized`，未产生 `Pass/Review/Block`；
- 结论：这不是“还没重跑”的问题，当前运行凭据仍未获得有效审核权限。腾讯官方权限文档将同类返回对应为 SecretId 所属主体缺少 `ims:ImageModeration` 对资源 `*` 的允许权限；下一步需核对策略关联主体，而不是重复发起同一请求；
- 当前产品仍 fail closed：内容安全没有 `PASSED` 事实，任何完整编辑链都不能以 IMS 已放行的名义继续。

### 检查点 6.3.2｜CAM/密钥核对后的第三次真实复测（服务开通阻塞已定位）

- 2026-08-27：用户确认本机 `TENCENT_SECRET_ID` 与 `agent+beautify` 子用户 API 密钥相同；对同一张明确授权的单人 JPEG 只再运行一次 live smoke。
- 请求真实返回 `RequestId=365e169e-427e-4550-8f60-316ab3dc94d5`，仍为 `UnauthorizedOperation.Unauthorized`，未产生 `Pass/Review/Block`。
- 只读核对 CAM 后确认 `policygen-20260827181624` 允许 `ims:*` / 全部资源，并已直接关联 `agent+beautify`；因此不再将“少建一条 CAM 策略”视为当前根因。
- 只读打开主账号内容安全控制台后，`cms/clouds/package` 显示“立即开通”。结合腾讯官方“先由主账号开通图片内容安全服务并完成业务配置”的前置条件，当前待用户完成的是服务开通、试用包/后付费和必要业务配置，而不是继续重试或继续改代码。
- 当前产品仍 fail closed。用户完成有费用/服务条款影响的开通决定后，才对同一授权照片再做一次验证；该操作不由代码自动触发。

### 检查点 6.3.3｜IMS 服务开通后的第四次真实复测（拒绝路径已通过）

- 2026-08-27：用户完成服务开通后，对同一张明确授权的单人 JPEG 仅重跑一次 live smoke。
- 请求真实返回 `status=succeeded`、`RequestId=21bf408d-929a-46ec-83aa-78f071eff556`，不再是权限错误；Provider 给出 `Block`，本地保守映射为 `content_safety.status=blocked` 和 `content_safety_provider_blocked`。
- 这完成了 IMS 的服务、权限、请求、真实回执和拒绝路由验证。为了保护照片内容，Trace 不保存 Provider 标签/分数，也不把 `Block` 说成图片有某种具体风险。
- 对当前样本，系统正确停止：不建档、不进入同人或修图。**当时**若需要验证允许分支，应由用户另行授权一张照片并以真实返回 `Pass` 为准；该允许分支已在下方 6.3.4 以另一张照片完成，不能把“API 成功返回 Block”包装成“这张照片审核通过”。

### 检查点 6.3.4｜IMS 第五次真实复测（另一张授权照片，允许路径已验证）

- 2026-08-28：用户提供另一张明确授权的单人 JPEG，并要求在不打断现有本地应用的前提下重跑一次 IMS smoke；
- 请求真实返回 `status=succeeded`、`network_called=true`、`Suggestion=Pass`、`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`，本地映射为 `content_safety.status=passed`；输入脱敏 SHA-256 为 `513bddd89f6b52eb3dc508db5e4485a10a8ffc66db5e2296bdf2ac6772046006`；
- 结论：内容安全 Adapter 的允许路由也有一条真实证据，可以让这张样本进入后续质量/同人/Profile/8A 规划门；这不代表所有照片都 Pass，也不替代多样本安全评测。此前 `Block` 样本和所有权限失败回执均保留。

## 检查点 6.4｜ReferenceProfile v0 与组合服务（已实现并验收）

- 2026-08-27：增加 `services/reference_profile.py`，将单脸观察转成归一化脸框/眼睛几何字段（脸宽高、占比、中心、边界余量、眼距、眼位和眼线斜率），保存提取器/规范化/合同版本；不保存原图、EXIF、肤色、妆面、身体、原始坐标数组或明文 embedding。
- 无主体锚点时生成 `GEOMETRY_ONLY` Profile；只有调用方传入单独同意、加密引用、到期时间等 `SubjectAnchorMetadata` 才生成 `ACTIVE` Profile。当前真实加密存储和半年 TTL worker 仍未实现。
- 增加 `services/checkpoint6.py`，组合质量门、内容安全 evidence、当前会话 CompareFace 和 Profile/SQLite 保存；它仍是确定性服务，不是 Agent/state machine。
- 新增 Profile/组合服务测试；当时总测试为 `51 passed`。Streamlit 已提供质量门、安全检查和 Profile 锁定入口；CompareFace 已完成真实 live 验证。后续全局 v0.3 更新和当前总测试见检查点 6.6。

### 检查点 6.2.1｜补齐 CAM 权限后的真实复测（首次服务状态失败）

- 2026-08-27：用户已将 `iai:CompareFace` 最小动作权限关联到实际运行身份；使用同一张已授权单人 JPEG 重新执行 CompareFace smoke。
- 本地质量门再次检测到母版/目标照各 1 张脸，随后请求真实到达 `iai.tencentcloudapi.com`，返回 `RequestId=d5d85fc4-c25d-4ac7-8075-7a09c73ac677`。
- 腾讯返回 `ResourceUnavailable.NotExist`，不再是 `AuthFailure.UnauthorizedOperation`。这是服务开通前的历史回执；随后用户开通 IAI 服务并完成下一节的成功复测。
- 本次未生成同人结论、未写入原图或原始分数；之前的权限失败记录保留作为历史证据。

**结果：**本节记录服务尚未开通时的历史失败；服务开通后的成功结果见下一节。

### 检查点 6.2.2｜IAI 服务开通后的 CompareFace live smoke（已通过）

- 2026-08-27：用户开通 IAI 人脸识别服务后，使用同一张已授权单人 JPEG、同一条命令重新 smoke。
- 本地质量门检测到母版/目标照各 1 张脸；请求真实返回 `RequestId=b89e828a-8038-41d3-a598-575fdba23521`，`status=succeeded`。
- Tencent CompareFace 3.0 返回原始 `raw_score=100.0`，策略路由为 `match`；该分数标记为 `calibrated=false`，不展示为接受概率或母版一致性分数。
- 组合模块测试 `19 passed`，全量自动化测试 `51 passed`；质量门、当前会话同人 Adapter、Profile v0 和 SQLite/Trace 基线已具备可回放证据。
- ImageModeration 随后已取得授权失败回执，仍未成功验证；因此本检查点的“通过”限定为质量门 + 当前会话同人比对 + ReferenceProfile v0，安全 Adapter 仍作为独立待完成 Gate。

## 检查点 6.6｜产品设计冻结、合同 v0.3、匿名运营账本与 Dashboard（已完成）

### 本小步背景

检查点 6 已有可运行的质量、同人、Profile 和 API Adapter，但用户指出“只记录最终规则”会丢失产品经理的决策过程，也无法区分用户意图、满意度、弱行为和产品运行事实。本小步不提前开发 LLM 或图片编辑闭环，而是先把已经冻结的产品边界写成可验证的合同、存储与运营可观测性。

### 用户冻结的产品决策

- 点赞/点踩/明确评论是强反馈；首次 Prompt、追问、再次会话是强意图或继续使用信号；退出/沉默默认未知，只有“要求重传后退出”等上下文才能标为路径中止；
- 数据库先是产品运行账本，记录建档、意图、工具成功、复测、显式反馈、重传、WAU/MAU；不把它直接当训练 Dataset；
- 长期主体锚点单独同意、183 天保存、30/7 天提醒，撤回后立即停用、主存储 24 小时删除、备份 7 天清理；
- 当前会话同人继续用腾讯 CompareFace；长期跨会话锚点采用本地 AES-GCM 派生主体锚点，但模型许可、加密/TTL/delete worker 和硬件尚未实现；
- 内容安全采用本地预检 + 腾讯 IMS，`Review/Block` 保守拦截；真实 IMS smoke 失败也必须保留为证据；
- LLM 选择 DeepSeek V4 Flash，文本最小化、模板 fallback、默认不使用跨境/第二云 Provider；
- 多脸采用 YuNet → 用户选脸 → MediaPipe/遮罩 → 回贴/复测的后续路线；明确不满意时立即 STOP，再澄清、规划与确认。

### 已完成的工程同步

- 合同从 `v0.2` 升级为 `v0.3`：新增 `DataRetentionPolicySnapshot`、主体锚点删除状态/截止时间/审计引用、`UserFeedback` 的证据强度与信号、匿名 `ProductEvent`；
- SQLite 迁移 `contract_v0_3_analytics_lifecycle` 新增匿名 user ID 与 `product_events`；`LocalTraceStore` 自动记录 session、Intent、Provider 成功、Verification 等事实，并对 Dashboard 输出聚合；
- 新增 [运营数据看板页面](../pages/1_运营数据看板.py)。它只显示脱敏聚合，不显示照片、原文、向量、锚点、密钥或 Provider 请求体；当前不会把质量门阶段的行为冒充为最终满意度；
- 新增 `scripts/smoke_tencent_image_moderation.py`，默认不读取照片/不联网；live 运行只输出哈希和脱敏回执；
- 更新执行版 PRD 的“产品设计”板块、PRODUCT_RULES、CONTRACTS、Prompt 规格、Decision Log、README、运行/API Gate 文档与 Provider Card。

### 真实运行与自动化证据

```text
Tencent ImageModeration live smoke
→ request reached Tencent
→ RequestId=42c6ed4d-f035-466c-b775-4728dd43ca93
→ UnauthorizedOperation.Unauthorized
→ status=failed; no moderation conclusion written
```

- 当时的 `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q`：`54 passed`；检查点 7 时为 `63 passed`，检查点 8A 时为 `69 passed`；当前最新 8B 全量回归见文末，为 `75 passed`；
- 额外覆盖：geometry-only Profile 不能保留 active/`delete_pending` 锚点；同一匿名用户的多 session 可聚合 WAU/MAU，Dashboard 行不泄露匿名用户 ID；
- 该 IMS 回执不是安全审核成功。补权后才可重跑一张明确授权的照片，不重复无意义的付费请求。

### 当前真实边界

- Dashboard 已是本地管理员原型，受邀部署前必须补管理员访问控制；指标不能被称为留存结论、线上 KPI、PMF 或训练数据；
- 这是检查点 6.6 当时的历史快照；DeepSeek 的真实文本调用已在检查点 7 完成，当前状态以本文件检查点 7 为准；
- `SubjectAnchorMetadata` 记录的是未来加密存储的合同承诺，不是实际人脸向量数据库；
- ImageModeration Adapter 已能发起请求并安全记录失败，但成功的内容安全 Gate 未完成。

## 检查点 7｜DeepSeek 文本 IntentFrame Adapter + 本地 fallback（已完成并真实 live 验证）

### 本步背景

检查点 6 已把“照片能否处理、是否为当前会话同一人物、母版如何保存”变成确定性结果。本步只补“用户可以自然说出目标，系统能把这句话可靠地变成合同”的能力，例如把“这张更像母版一点，保留妆面，先给我建议”转成 `IntentFrame`。LLM 仍不替代质量门、参数规划器或权限状态机。

### 本轮已经按冻结规则完成

- 2026-08-27：新增 `agent/intent_adapter.py`。它使用 DeepSeek `/chat/completions` 的 JSON Object 输出，固定关闭 thinking、20 秒超时、900 token 上限；先校验一个非持久化 `IntentCandidate`，再由确定性代码生成正式 `IntentFrame`；
- 2026-08-27：只有用户在页面勾选“发送本轮脱敏文字”且本机 `.env` 存在 `DEEPSEEK_API_KEY` 时才允许远程调用。无 Key、未勾选、网络、HTTP、非 JSON、Schema 冲突或不支持 Provider 均回退本地模板，不自动转发到 OpenRouter/第二云模型；
- 2026-08-27：系统而非 LLM 生成 session/intent ID、轮次、文本 hash、模型/Prompt 版本和确认引用。用户表达“直接修”只得到 `PENDING` 的有界确认草案，不会调用腾讯图片工具；
- 2026-08-27：页面新增“解析并保存本轮 IntentFrame”入口、文字数据告知、解析路径/安全回执展示；页面只保存哈希与脱敏结构化投影，不保存原话或模型原回答；
- 2026-08-27：新增默认不联网的 `scripts/smoke_deepseek_intent.py` 和 9 条针对 Adapter 的自动化测试；新增专项说明 [DEEPSEEK_INTENT_GATE.md](DEEPSEEK_INTENT_GATE.md)。

### 输入、输出和规则

| 项目 | 本轮实际行为 |
|---|---|
| 页面输入 | 用户本轮文字；两张当前内存照片只用于建立会话上下文，绝不发送给 LLM |
| 出站输入 | 常见 PII 脱敏后的文字、轮次、是否已有 Profile、目标数、默认约束、可用能力名称和上一版意图摘要；不含任何照片、Base64、向量、锚点、密钥、原始 Trace 或不透明 ID |
| 结构化输出 | `IntentFrame`、最多一个澄清问题、用户可读摘要、脱敏 `IntentParseReceipt` |
| 失败输出 | 同 Schema 的 `template_keyword_baseline`；页面明确标出 fallback 原因 |
| 执行边界 | 解析器永远不计算视觉数值、腾讯参数或权限；`execute` 只是待确认倾向 |

### 已运行验证证据

- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q tests/test_deepseek_intent.py`：`9 passed`；
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_deepseek_intent.py`：`offline_guarded`、`network_called=false`，证明默认不联网；
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_deepseek_intent.py --allow-live`：`status=passed`、`parser_mode=llm`、`schema_validated=true`、`model_version=deepseek-v4-flash`、`latency_ms=2957`、`total_tokens=1471`；固定测试文本不含个人信息，照片、向量、密钥和原始 Trace 均未发送；
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q`：`63 passed`；`ruff check .`、`ruff format --check .`、`compileall` 和 `git diff --check` 均通过；
- 已在本机 Streamlit 页面做可视化检查：页面清楚告知“DeepSeek 只处理用户授权的文字、不处理照片/向量”；无本机密钥时只显示本地 fallback，不暗示云端已调用。

### 可回放的默认安全 Trace

```text
session → 用户未勾选远程文本授权 / 或本机无 Key
→ DeepSeekIntentAdapter 不建立 HTTP 请求
→ parser_mode=template_fallback
→ fallback_reason=REMOTE_NOT_OPTED_IN 或 CREDENTIALS_MISSING
→ IntentFrame + 脱敏解析回执写入本地 session/trace
→ network_called=false
```

### 还没有完成，不能夸写

- 5—10 条经产品负责人审计的中文 Gold Case；
- 多轮澄清回填、取消/改口、不满意停止的运行状态机；
- 从照片计算差异、确定性 EditPlan、确认后工具执行和 VerificationResult。

### 本检查点验收结果与下一步

真实 DeepSeek Gate 已闭合。**2026-08-27 当时** IMS 服务开通后第四次 `ImageModeration` live smoke 已返回真实 `Block`（RequestId `21bf408d-929a-46ec-83aa-78f071eff556`），所以“安全门可调用且会拒绝”已验证；允许分支和 8A 计划随后在当前文档的新章节中完成。当前样本不能继续主流程，不能把 `Block` 照片推进到后续处理。

## 检查点 6.5｜本轮交付与验收包（页面入口已接入）

### 用一句话理解这一步

这一小步像给照片流程加了三道彼此独立的门：第一道确认照片能不能被看清、能不能安全编辑；第二道确认母版和目标照是否是同一位本人；第三道把通过的母版压缩成不含原图的“长期标准档案”。它们都是确定性服务，暂时不是会聊天和自主决策的 Agent；后续 Agent 只负责在这些门之间按权限编排。

### 输入、输出和规则

| 模块 | 输入 | 输出 | 当前规则 |
|---|---|---|---|
| 本地质量门 | 图片字节、照片角色 | 安全 `PhotoObservation`、质量/可编辑性路由证据 | 损坏、格式/尺寸不支持、无脸或模糊时要求重传；多脸当前要求先裁剪；页面只展示定性结果，不展示置信数值 |
| 内容安全门 | 用户明确同意后的一张图片 | Tencent IMS 回执与 `PASSED/BLOCKED` | 未检查不能继续；`Pass` 放行，`Review/Block` 在 V0 保守拦截 |
| 当前会话同人门 | 通过预检的母版和目标照 | `match/uncertain/no_match` 与后台 evidence | 调 Tencent IAI CompareFace 3.0；供应商原始分只留后台，不显示为概率 |
| ReferenceProfile v0 | 通过安全/质量门的单脸母版 | 归一化脸框/眼睛几何、版本和能力映射 | 不保存原图、EXIF、肤色、妆面、身体或原始坐标；无主体锚点时为 `geometry_only` |

### 需要产品经理确认的事项

- 页面是否允许把照片发送给 Tencent ImageModeration/CompareFace，以及质量警告是否仍锁定为母版；页面已经把这两个动作做成单独勾选和按钮。
- CompareFace 的 `50/70` 路由边界目前只是可配置的 V0 策略，不是合同硬编码；后续可用授权样本重新校准。
- 当前多脸先裁剪；自动选脸、隔离、回贴和复测留到后续小步。

### 已由工程固定、无需重复决策的事项

- 原图只在本次内存调用中处理；数据库/Trace 只保存哈希、状态、版本和回执引用。
- 质量、同人和内容安全是三个独立信号；任何一个前置门未通过都不能进入后续修图。
- 页面不会显示质量置信度、供应商原始分或未经校准的接受概率。

### 5 个可重复测试案例

1. 有效单人正脸：质量门给出“可以进入下一步”，安全通过后可以锁定 geometry-only Profile。
2. 损坏/超大/不支持格式：不发起外部调用，给出重新上传原因。
3. 无脸或多脸：无脸拒绝；多脸在当前 V0 要求用户先裁剪，不发送 CompareFace。
4. 安全门未执行或返回 Review/Block：不能锁定 Profile，也不能发起同人比对。
5. CompareFace 权限不足：保留错误码和 RequestId，页面提示失败，不把失败当作同人结果。

### 历史真实 Trace 摘要（权限不足）

```text
session → 本地解码/质量预检（1600×2442，检测到 1 张脸）
→ CompareFace 请求已发出
→ RequestId=b1584fbb-f750-4536-b4a5-2b6c3803a67b
→ AuthFailure.UnauthorizedOperation
→ 页面/Trace 记录失败类型；不展示原始分，不生成 subject-match 结论
```

这条 Trace 证明 SDK、端点、签名、失败回执和安全失败路径已经打通；后续权限和服务开通后的成功 Trace 见“检查点 6.2.2”。

### 最新真实 Trace 摘要（已通过）

```text
session → 本地解码/质量预检（1600×2442，检测到 1 张脸）
→ CompareFace 请求已发出
→ RequestId=b89e828a-8038-41d3-a598-575fdba23521
→ FaceModelVersion=3.0，raw_score=100.0（后台 evidence）
→ subject_match=match；不展示原始分或接受概率
```

## 检查点 1｜项目骨架、Git、进展/决策记录（已完成）

### 本检查点目标

建立独立项目目录和可追溯协作机制；不实现任何产品算法，不调用任何外部 API，不创建或使用密钥。

### 已完成

- 2026-08-26：创建独立项目目录 `portrait-consistency-agent/`。
- 2026-08-26：初始化 Git，默认分支为 `main`。
- 2026-08-26：创建项目 README、项目上下文、开发进展和决策日志骨架。

### 验证证据

- 已创建独立 Git 仓库，默认分支为 `main`；
- 已检查项目目录，代码、文档、数据卡、日志和本地存储目录分离；
- 已执行 `git diff --check`，未发现已跟踪文本的空白错误；
- `.gitignore` 已排除 `.env`、虚拟环境、数据库、日志、临时存储和图片，避免敏感数据进入版本控制。

### 明确未做

- 未安装项目依赖；
- 未创建 Python 虚拟环境；
- 未写数据合同；
- 未调用腾讯 API；
- 未处理任何用户照片；
- 未部署服务器。

### 待你决策（当前不阻塞检查点 1）

> 以下是项目初始化时的历史记录；其中腾讯 API 账号/权限和 live Gate 已在检查点 4 完成，产品规则审计的最新状态见检查点 5.5。

| 编号 | 决策 | 为什么需要你决定 | 默认处理 |
|---|---|---|---|
| D-USER-001 | 腾讯云账号、密钥和预算上限 | 会产生外部费用和账号授权 | 暂不创建/不调用 API |
| D-USER-002 | 未来 LLM 提供商 | 涉及账号、模型、费用与数据处理选择 | 先实现可替换接口和模板 fallback |
| D-USER-003 | 是否允许将 Demo 部署到公网 | 影响人脸数据传输、服务器与隐私 | V0 先本地运行与录屏 |

### 下一步

进入检查点 2：使用 `uv` 创建 Python 3.10 隔离环境，并建立不含任何密钥的配置文件。

## 检查点 2｜本地 Python 环境与开发命令（已完成）

### 本检查点目标

使用已安装的 `uv` 与 Python 3.10 建立隔离、可复现的本地运行环境；只安装最小基础依赖，不引入腾讯 SDK、MediaPipe、LLM SDK 或部署平台。

### 计划产物

- `pyproject.toml` 与锁文件；
- `.python-version`、`.env.example`、`Makefile`、`start.sh`；
- 可验证的依赖同步、测试和静态检查命令。

### 已完成

- 2026-08-26：创建 `pyproject.toml`、`.python-version`、`.env.example`、`Makefile`、`start.sh` 和环境检查脚本；
- 2026-08-26：`uv sync --all-groups` 创建 `.venv` 与 `uv.lock`；
- 2026-08-26：增加基础导入测试，确保项目包可以由隔离环境加载；
- 2026-08-26：默认服务器地址固定为 `127.0.0.1:8501`，未启动服务。

### 验证证据

- `uv run python --version`：Python `3.10.20`；
- `make check-env`：通过；
- `make test`：`1 passed`；
- `make lint`：`All checks passed!`；
- `git diff --check`：通过；
- 未创建 `.env`，未写入、打印或调用任何外部密钥。

### 不需要你决策

- Python 3.10、`uv`、Pydantic、pytest、ruff 的基础组合；
- 本地默认监听地址 `127.0.0.1`；
- 默认不加载任何真实密钥。

### 仍未做

- 不启动公网服务器；
- 不调用腾讯 API；
- 不安装或配置 LLM；
- 不处理照片。

## 检查点 3｜六个数据合同与合同测试（已完成）

### 本检查点目标

定义六个模块之间唯一允许交换的数据结构，使后续视觉、LLM、参数规划、腾讯 API、数据库和界面都不能各自“临时发明字段”。本检查点只定义和验证数据，不实现算法、不调用网络。

### 六个合同

1. `ReferenceProfile`：锁定母版后的版本、调整边界和用户约束；
2. `PhotoQualityResult`：是否可比较、质量标志与原因；
3. `IntentFrame`：自然语言解析出的目标、范围、约束、置信度与确认状态；
4. `EditPlan`：规则规划器生成的用户层 delta、腾讯绝对参数和风险；
5. `ProviderRun`：一次外部工具/API 调用的请求哈希、RequestId、耗时、状态和错误；
6. `VerificationResult`：修后复测的指数变化、下一状态和停止原因。

### 合同边界

- 视觉数值、Provider 参数和执行授权必须区分；
- `IntentFrame` 不能绕过二次确认直接进入外部执行；
- 合同序列化后应可存入 SQLite/JSONL，不包含原图、密钥或完整人脸特征；
- 非法枚举、越界参数、缺少确认 token 等输入必须被拒绝。

### 不需要你决策

- 字段命名、Pydantic 校验、版本字段和错误码枚举；
- `ProviderRun` 只保存 hash/reference，而不保存图片内容。

> 初始化时曾把“最多 3 轮、每轮最多 3 个参数”作为工程默认值；用户随后明确不希望把轮次硬编码，检查点 5.7 已将轮次改为可配置 Safety Policy，并取消固定三个部位上限。

### 需要保留给你的未来决策

- 哪些部位最终允许加入 Profile（当前合同仅保留通用枚举）；
- 最大照片保留时长与未来公网部署同意文案；
- 未来是否允许把用户的长期偏好保存为 Memory。

### 已完成

- 2026-08-26：在 `core/contracts.py` 建立六个版本化 Pydantic 合同；
- 2026-08-26：增加 `TencentBeautifyParams` 与 `FeatureDelta` 两个子合同，明确用户层 delta 与 API 绝对值的分工；
- 2026-08-26：建立合同说明文档，列明每个合同的产生者、消费者和禁止保存的数据；
- 2026-08-26：增加 6 个合同测试，覆盖合法序列化和关键非法输入。
- 2026-08-26：当时将六个合同标记为 `v0.1` 实现草案；该状态已在检查点 5.7 被 `v0.2-frozen` 替代。

### 验证证据

- `make test`：`7 passed`；
- `make lint`：`All checks passed!`；
- `uv run ruff format --check .`：全部格式正确；
- `git diff --check`：通过；
- 测试覆盖：Profile 不存原图/完整特征、拒绝照片必须有原因、执行意图必须有 token、腾讯参数显式为 0—100、成功 ProviderRun 必须有真实回执、验证增益不能伪造。

### 明确未做

- 未连接 SQLite；
- 未写腾讯 API 代码；
- 未创建请求/结果图片；
- 未调用 LLM 或视觉模型。

## 检查点 4｜腾讯能力卡、API Adapter、smoke 脚本（已完成；含真实 live Gate）

### 本检查点目标

建立真实 API 的离线可测试适配层：能力卡说明“能做什么、范围是多少、来源和版本是什么”；Adapter 保证密钥只从 `.env` 读取；smoke 脚本能在无密钥时安全报出下一步，在有密钥时记录真实的 `RequestId`、结果引用、耗时和错误。

### 本检查点不做

- 不要求你现在提供密钥；
- 不把 fixture 或本地假图写成“真实腾讯调用”；
- 不实现 SDK 细项（唇厚、眼距、鼻翼）；
- 不在脚本中嵌入、打印或上传任何秘密。

### 当前产品决策边界

- 腾讯账号、权限、服务开通和一次 live Gate 已完成；调用预算、频控和后续调用次数仍需用户决定；
- 不把一次真实成功调用包装成稳定性、准确率、批量能力或线上结果；
- 具体产品规则与合同升级影响见 [PRODUCT_RULES.md](PRODUCT_RULES.md)。

### 已完成

- 2026-08-26：根据腾讯官方 `BeautifyPic`、API 概览和 Python SDK 文档建立版本化 Provider Card；
- 2026-08-26：安装并验证产品级 Python SDK `tencentcloud-sdk-python-fmu==3.1.82`；
- 2026-08-26：实现只从本地 `.env` 读取凭据的 Adapter；四个 V0 参数永远显式发送；
- 2026-08-26：实现 smoke 脚本。默认运行不读取图片、不联网；`--allow-live` 但无密钥时安全退出并明确说明原因；
- 2026-08-26：写入 API Gate 文档，说明官方来源、限制、真实运行命令和不应夸写的边界。
- 2026-08-26：用户完成 CAM `fmu` 服务级策略关联，并在腾讯云控制台开通人脸试妆服务；随后真实 `BeautifyPic` 请求成功返回结果图。

### 验证证据

- `make test`：`11 passed`；
- `make lint`：`All checks passed!`；
- `uv run ruff format --check .`：全部格式正确；
- 默认 smoke：返回 `network_called=false`，未读取图片或调用网络；
- `--allow-live` 且无密钥：以退出码 `2` 安全返回 `network_called=false`；
- SDK 导入验证：`FmuClient:BeautifyPicRequest`。

### 明确未完成 / 不可夸写

- 本次只完成 1 次已授权照片的真实 smoke test，不代表线上稳定性、SLA、成本或批量处理能力；
- 尚未实现 MediaPipe 质量门、相似度/一致性计算、LLM 意图澄清和 Agent 重规划；
- 尚未实现公网多用户隔离、登录、删除/TTL 和完整的用户数据授权流程。

### 真实 Gate 失败记录（待二次诊断）

- 2026-08-26：在用户明确授权的一张本地测试照片上发起一次 `BeautifyPic` 基线请求；腾讯返回 `RequestId`，但未返回结果图。
- 发现 Adapter 错误归因缺陷：腾讯 Python SDK 使用 `get_code()`，旧实现误读为不存在的 `get_error_code()`，将真实腾讯错误笼统记录成 `TENCENT_SDK_ERROR`。
- 已修复本地错误码提取并新增回归测试；后续重试已得到腾讯侧的真实错误码，见下方成功记录。

### 真实 Gate 成功记录

- 2026-08-26 17:32（Asia/Shanghai）：使用用户明确授权的测试照片，调用 `BeautifyPic`，`FaceLifting/EyeEnlarging/Whitening/Smoothing` 均为 `0`。
- 腾讯返回：`status=succeeded`，`provider_request_id=1e519f22-b119-41bb-9242-76798f7cab61`，耗时 `3438ms`。
- 历史结果图片当时已落盘：`storage/results/1e519f22-b119-41bb-9242-76798f7cab61.jpg`，JPEG `1600×2442`、约 `1.7MB`；`result_ref` 与本地文件一致。该文件产生于 8B 会话内结果规则冻结前，不代表当前产品会落盘结果图。
- 可追溯字段：`run_id=run_9559220a5f844122928399cd9d50cd9b`、`session_id=smoke_session_001`、`operation=BeautifyPic`。

## 检查点 5｜最小 Streamlit 外壳、SQLite/JSONL trace（已完成）

### 本检查点目标

建立不做真实修图的本地任务外壳：用户能创建一个匿名会话、上传两张仅本地预览的图片、写入固定模板 `IntentFrame`，并把 session/intent/事件写入 SQLite 与 JSONL。页面必须明确标识“尚未调用腾讯 API、尚未做视觉评分”。

### 本检查点不做

- 不处理或保存真实图片到数据库；
- 不接 MediaPipe、不计算一致性指数；
- 不调用腾讯 API 或 LLM；
- 不启动公网部署。

### 已完成

- 2026-08-26：实现 `app.py`，页面可建立匿名本地 session、内存预览母版/目标照、提交模板 IntentFrame 并展示脱敏 trace；
- 2026-08-26：实现 `LocalTraceStore`，将 session、IntentFrame、ProviderRun 审计投影和事件写入本地 SQLite/JSONL；
- 2026-08-26：实现递归 redaction，拒绝把密钥、确认 token、Base64 图片、原图 payload 或签名 URL 写入 trace；
- 2026-08-26：创建 `.streamlit/config.toml`，服务只绑定 `127.0.0.1`、关闭匿名使用统计、保留 CORS/XSRF 保护；
- 2026-08-26：新增本地存储测试，验证敏感字段被红删、同一 session 的事件可追溯、Intent turn 可递增。

### 验证证据

- `uv run python -c "import app"`：`app_import_ok`；
- 临时启动 Streamlit 后，`curl http://127.0.0.1:8501/_stcore/health`：`ok`；测试服务已人工停止；
- `make test`：当时为 `14 passed`；当前总测试见检查点 5.7；
- `make lint`：`All checks passed!`；
- `uv run ruff format --check .`：全部格式正确；
- 未上传图片、未调用腾讯 API、未调用 LLM、未启动公网服务。

### 明确未完成 / 不可夸写

- 页面仍使用 `template_fallback`，不是 LLM 自然语言解析；
- 上传图片只在浏览器/页面当前内存中预览，尚未有质量门或 Feature 提取；
- SQLite 的 `ProviderRun` 审计表已准备好，但尚未产生任何真实腾讯运行记录；
- 尚未实现删除/TTL job、登录、多用户隔离或线上部署。

## 检查点 5.5｜产品规则与六合同人工审计（已完成；当时合同未冻结）

### 本检查点目标

把产品经理需要确认的语义从工程默认值中分离出来。当前只同步 Markdown，不修改 Python 合同，避免旧字段在用户未确认前继续扩散。

### 用户本轮已确认

- 不展示硬编码的一致性指数，也不设固定 90 分目标；未来概率必须由有授权人工可接受性样本校准；
- V0 不展示任何接受概率；用户交互可自动生成弱标签，模型可生成合成边界案例，但人工金标准必须独立保留；
- 外部 Provider Card 声明支持的参数原则上都可以执行；美白和磨皮默认关闭并需明确允许；
- 母版保存结构化、尽量具体的五官/脸型归一化派生信息，不保存原图、肤色、妆面、身体和隐私部位；经单独同意后保存加密、可删除、受限访问的派生主体表示半年；到期提醒重新上传或删除锚点后降级为几何特征对齐；
- 新母版成功后替换旧版本：删除旧版本特征正文，保留脱敏审计事件；失败时保留旧版本；
- 母版照片不能直接二次编辑；上传失败要弹窗说明原因并要求重新上传；
- 目标照片先做同一人物门控和可执行性判断；质量置信度低（`≤0.50`）重新上传，中（`>0.50 且 <0.80`）警告后继续，高（`≥0.80`）直接继续；
- 多脸照片在其他条件达标时让用户选择目标脸，自动隔离背景和其他人脸，只编辑所选单脸，否则拒绝；批量模式单张失败不阻塞其他照片，但必须先告知用户；
- Demo 先部署到可分享 URL 的 Streamlit 平台，仅允许受邀测试者，密钥放平台 Secrets，公网开放后置。

### 已补充的遗漏维度

- 长期母版与“不保存任何照片信息”之间的主体锚点冲突；
- 特征级置信度、质量置信度和同一人物置信度不能共用一个数字；
- Provider 能力、用户授权范围和产品可执行性必须分开；
- 人工可接受性标签、训练/holdout 数据、概率校准和数据保留策略；
- 交互弱标签、合成数据和人工金标准的分层与防止数据泄漏；
- 多脸目标选择、批量部分失败、原子替换、失败回退和内容安全拒绝；
- 未成年人不当内容、非自愿换脸、冒充/诈骗、身份认证误用等安全边界。

### 文档同步证据

- 新增 [PRODUCT_RULES.md](PRODUCT_RULES.md) 作为产品语义和合同审计底稿；
- 已同步 [CONTRACTS.md](CONTRACTS.md)、[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)、[DECISION_LOG.md](DECISION_LOG.md)、[TENCENT_API_GATE.md](TENCENT_API_GATE.md)、[ENVIRONMENT.md](ENVIRONMENT.md)、[LOCAL_RUNTIME.md](LOCAL_RUNTIME.md) 和项目 README；
- 实际腾讯成功调用证据仍见检查点 4 的 `RequestId`、结果引用和本地文件。

### 暂不实现

- 本轮没有修改 `contracts.py`、数据库表、Streamlit 页面或参数规划器；也没有实际部署受邀 Streamlit URL；
- 不能声称已经实现同一人物识别、质量门、接受概率或多脸编辑；
- RAG、LLM、概率模型和公网部署仍按后续独立检查点推进。

### 当时的下一步

进入检查点 5.6，审计 `IntentFrame`、`EditPlan`、`ProviderRun` 和 `VerificationResult`；用户明确冻结全部六个合同后，再升级合同代码和测试。

## 检查点 5.6｜后四合同审计、Prompt 规格与耦合检查（已完成并冻结）

### 本检查点目标

把用户提交的后四合同规则整理成可实现、可验证、可与 Profile/质量门/状态机/腾讯 Adapter/Trace 耦合的 `v0.2-review` 规格；完成附件中所有【补全字段/完整版 Prompt】任务，但不在产品冲突尚未确认时修改合同代码。

### 已完成

- 2026-08-27：完整读取用户的四合同审计稿，并把用户意图、工作流状态和工具 taxonomy 分层；
- 2026-08-27：重写 [CONTRACTS.md](CONTRACTS.md)，形成六合同的数据流、字段、不变量、确认/失效/重试/回退规则和代码差距表；
- 2026-08-27：新增 [AGENT_PROMPTS.md](AGENT_PROMPTS.md)，完成 Intent 解析、受约束 ReAct 编排、Bad Case 归因和报告解释四套 Prompt；
- 2026-08-27：在 [PRODUCT_RULES.md](PRODUCT_RULES.md) 中以红色标出技术纠错、四个待确认产品决定和附件任务完成映射；
- 2026-08-27：用腾讯官方文档复核 `BeautifyPic`：四个参数范围均为 0—100，接口最多处理图片中最大的五张人脸，但没有选择指定人脸的输入参数；
- 2026-08-27：同步决策日志、项目上下文、README、腾讯 API Gate 和 Provider Card 的事实边界。

### 发现并处理的耦合问题

- 用户相对变化可以表达大幅调整，但腾讯绝对参数不能超出 0—100；
- `EditPlan` 生成于执行前，不能保存修后差异；修后实测只能进入 `VerificationResult`；
- 参数值、安全上限和接受概率不能由 LLM 猜测；
- 高置信/低成本不能绕过外部编辑确认，“以后默认执行”也不能形成永久免确认；
- ProviderRun 是 Adapter 的事实回执，附件中的 Prompt 应归为下游 Bad Case 归因；
- V0 不存在校准接受概率，不能以“概率达标”停止；
- “三轮总上限”和“连续两轮无改善”可作为两个不同停止门，但应来自可配置 Safety Policy；
- 腾讯接口没有目标脸选择参数，多脸隔离必须在调用前后另建裁剪/遮罩/回贴与验证链路；
- 用户可以看到可验证的工具步骤摘要，不能看到或要求模型输出隐藏思维链。

### 截至该检查点未完成 / 不可夸写

- 没有修改 `contracts.py`、SQLite schema、状态机、Streamlit 页面或任何测试；
- 没有接入 LLM，四套 Prompt 只是规格；
- 没有实现参数规划器、自动多轮执行、自动多脸隔离、修后复测或人工复核队列；
- 没有校准概率、Gold Set、Prompt eval 或用户测试结果。

### 用户已确认的 Gate

1. 采用“有界计划族”的一次确认作用域；
2. V0 三轮总上限 + 连续两轮无改善提前停，并作为可配置策略；
3. 产品目标为自动隔离/裁剪/回贴/复测，失败时说明原因并要求用户先裁剪；链路完成前拒绝多脸整图执行；
4. Beta 的人工复核只由项目开发者处理，查看原图要求单独授权；
5. 0.50/0.80 只用于 quality/editability 的最严格路由，subject match 独立判定与校准。

这五项已经进入下一检查点的合同、Policy、SQLite 和测试。

## 检查点 5.7｜合同 `v0.2-frozen`、六表存储与执行版 PRD（已完成）

### 本检查点目标

把 5.6 的五项确认真正写进代码和持久化层，并建立一份以后随真实产品同步的执行版 PRD；不在本步骤提前开发 MediaPipe、LLM 或多脸图像处理。

### 已完成

- 2026-08-27：将六个 Pydantic 合同从 `0.1` 升级为 `0.2`，删除 `before_index/after_index/index_delta` 和 `expected_index_gain`；
- 2026-08-27：新增 `QualityRoutingPolicySnapshot` 与 `SafetyPolicySnapshot`，当前 0.50/0.80、三轮/两轮停止门进入版本化配置，不再写死在轮次类型；
- 2026-08-27：IntentFrame 拆分用户意图、字段来源/置信和有界确认；EditPlan 分 executable/suggestion-only；ProviderRun 改为单次事实回执；VerificationResult 改为逐特征实测趋势；
- 2026-08-27：PhotoQualityResult 增加内容安全和主体匹配的通用证据快照；供应商原始同人分未校准时不能写成 confidence，`passed/blocked` 安全结论也不能由用户声明伪造；
- 2026-08-27：SQLite 新增 `reference_profiles`、`photo_quality_results`、`edit_plans`、`verification_results`，与原 `intent_frames`、`provider_runs` 组成六类合同表；迁移标识为 `contract_v0_2_tables`；
- 2026-08-27：实现 Profile 原子替换：新 Profile 成功写入后，旧特征正文变为 tombstone，保留脱敏替换审计事件；
- 2026-08-27：升级 Streamlit 模板 IntentFrame 和腾讯 smoke 的 ProviderRun 回执结构；默认 smoke 仍不联网；
- 2026-08-27：新增 [母版人像一致性Agent-执行版PRD.md](母版人像一致性Agent-执行版PRD.md)，将原启动蓝图降为历史规划文档；
- 2026-08-27：新增项目 `AGENTS.md`，要求后续代码、测试、执行 PRD、决策和进展同步。

### 验证证据

- `uv run pytest -q`：`29 passed`；
- `uv run ruff check .`：`All checks passed!`；
- `uv run ruff format --check .`：29 个文件格式正确；
- 默认腾讯 smoke：`network_called=false`；
- `app` 导入和现有本地数据库初始化：`app_import_and_schema_v0_2_ok`。

### 明确未完成 / 不可夸写

- 六合同测试使用的是结构化 fixture，不是 MediaPipe 的真实检测结果；
- 没有实现人脸特征提取、subject match、真实 PhotoQualityResult、差异诊断、参数规划器、自动多轮或修后复测；
- 多脸隔离/裁剪/回贴仍未实现，当前必须要求单脸或先裁剪；
- LLM Prompt 已冻结但没有接入模型；完整状态机、受邀部署和用户测试仍未完成。

## 历史规划快照｜检查点 6 的原始待办（已由 6.1–6.6 完成内容替代）

> 本节保留最初的产品决策背景和当时待办，便于复盘；它不是当前下一步。当前状态请看本文顶部总览及末尾最新检查点。

### 下一步目标（尚未开始）

让单张母版/目标照得到可解释的“可继续 / 警告后继续 / 重新上传 / 拒绝”结果：MediaPipe/OpenCV 负责单脸/多脸、姿态、清晰度、曝光、遮挡、几何与编辑可行性；独立 Subject Match Adapter 负责同一人物路由。随后才创建不含原图的 `ReferenceProfile` 与实验性几何特征；本模块不输出未经校准的一致性指数。

### 将保留给你的决策

- 主体锚点的具体同意文案、到期提醒时机、撤回同意后的删除时限和访问审计；
- V0 同一人物门控采用哪种模型/服务、数据是否出本机、许可与成本，以及在没有授权 benchmark 前如何处理 `uncertain/no_match`；若坚持跨会话且不保存原图，必须选择能生成并安全持久化派生主体锚点的本地/自托管方案，纯两图云比对只能作为当前会话能力；
- V0 内容安全采用本地模型、云审核服务还是受邀 Beta 人工前置审核；用户上传声明只能作为授权证据，不能伪装成机器检测结果；
- 9 月 4 日 Demo 是先只持久化几何 Profile，还是同时落地真正加密、半年到期的主体锚点；合同支持两者，但安全工作量不同；
- 质量/可执行性阈值如何用授权样本校准，以及用户反馈冲突时的调整流程；
- 真实照片测试集的授权方式、标注问法、保留期限和删除方式；
- 多脸失败后的“要求先裁剪”已经冻结；仍需以后决定隔离、回贴和视觉验收算法；
- Streamlit 部署平台和受邀名单/访问密码方式。

## 检查点 8A｜局部差异诊断与确定性 EditPlan 草案（2026-08-28，已完成）

### 为什么做这一小步

检查点 6 已能把照片变成质量、安全、同人和母版 Profile 事实，检查点 7 已能把用户文字变成 `IntentFrame`；但系统还不能用用户能理解的方式回答“目标照哪里和母版不同、哪些差异当前工具能处理、准备怎么改”。本小步先建立一张**修图前的施工单**，不把 LLM 变成视觉测量器，也不在用户确认前消耗图片编辑 API。

### 交付五件套

**1. 中文说明。** `services/edit_planner.py` 把已通过前置门的 Profile、目标照内存观察、质量结果和 IntentFrame 组合成逐特征诊断，再用版本化规则计算腾讯绝对参数，输出一份 `proposed`、`requires_confirmation=true` 的 EditPlan。它解决的是“能解释、能复现、能审计地提出修图计划”，不是“自动证明已经修好”。

**2. 输入、输出和规则。**

| 项目 | 当前实现 |
|---|---|
| 输入 | ReferenceProfile、目标 PhotoObservation、已通过的 PhotoQualityResult、IntentFrame、Tencent BeautifyPic Provider Card、可配置 Safety Policy |
| 局部测量 | `face_width_height_ratio`；严格恰好两只眼框时的 `eye_area_mean_face_ratio`；眼距/构图等只作诊断，不直接映射参数 |
| 参数映射 | 目标脸相对更宽 → 候选 `FaceLifting`；目标眼睛面积占脸比例更小 → 候选 `EyeEnlarging`；差异 ≤4% 不自动加参，4%—12% 按 `mapping_policy_v0.1` 映射，超过 12% 不无限叠加 |
| 保护规则 | 参数由确定性规划器计算并保持腾讯 0—100 范围；美白/磨皮每份计划显式为 0；不可测量、置信不足、方向不可达或用户禁止时转为 suggestion-only |
| 输出 | 逐特征 `FeatureDifference`、可执行/手动建议分组、四个腾讯绝对参数、风险与版本、脱敏 Trace；计划永远先是 `proposed` |

**3. 用户已冻结的决策。** 本轮用户选择严格双眼测量；同意展示逐特征局部几何差异，不展示总分、90 分线或接受概率；同意 `mapping_policy_v0.1` 作为可配置版本化策略；同意不可达/不可测/禁改时解释并降级；同意即使用户说“直接修”，也必须先展示计划并获得有界确认，美白/磨皮默认关闭。

**4. 五个实际测试案例。** `tests/test_edit_planner.py` 已覆盖：双参数同时生成；4% 容差内不生成自动参数；工具无法反向调整的方向；缺少两只眼框时只给手动建议；用户禁止瘦脸且计划/Trace 仍可保存。五例均通过。

**5. 完整 Trace。** `scripts/smoke_edit_planner.py` 使用显式标注的几何 fixture（不读真实照片、不联网）跑出：

```text
preflight：内容安全=passed、同人=match、质量路由可继续、单脸
→ measure：计算 18 项可复用的局部几何字段
→ map：mapping_policy_v0.1 / 2026-08-28
        FaceLifting +10、EyeEnlarging +10
        Whitening=0、Smoothing=0
→ persist_plan：status=proposed、requires_confirmation=true
```

这条 Trace 里数值来自本地特征和确定性映射；LLM 没有看照片、没有算差异、没有生成参数；腾讯 API 没有在 8A 被调用。

### 验证证据

- 8A 当时的 `.venv/bin/pytest -q`：`69 passed`（含 8A 五个案例；仅有 Pillow 已知弃用警告）；当前最新 8B 全量回归见下一节，为 `75 passed`；
- `.venv/bin/ruff check src tests scripts`：通过；`.venv/bin/ruff format --check .`：`50 files already formatted`；Python 编译检查通过；
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_edit_planner.py`：输出上述完整 fixture Trace；明确标记 `fixture_only=true`，不能写成视觉效果或参数校准证据；
- 本轮提供的另一张明确授权照片已完成 IMS live smoke：`status=succeeded`、`Suggestion=Pass`、`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`、输入脱敏 SHA-256 `513bddd89f6b52eb3dc508db5e4485a10a8ffc66db5e2296bdf2ac6772046006`。这只是允许路由的一条真实样例；此前 `Block` 回执仍保留，不代表内容安全全面覆盖；
- 未重启已有 Streamlit 进程；`app.py` 已接入 8A 按钮，且导入/编译检查通过。页面当前只展示计划草案和 Trace，不会自动执行。

### 当前问题、边界与下一检查点

- 8A 仍没有修后图，因此不能说“参数一定有效”、不能展示一致性概率，也不能替代用户肉眼验收；Haar/眼框测量是 V0 可解释基线，后续需要授权样本和人工金标准校准；
- 当前仍只支持单脸规划。多脸隔离、裁剪、回贴和非目标区域复测尚未实现；
- 下一检查点是“有界确认 → Tencent BeautifyPic → 真实 ProviderRun → VerificationResult”。进入该步前需要用户确认确认页是否允许修改计划中的单项参数、确认文案/有效期，以及实际执行用原图还是上一张已验证结果；这些会影响权限和回滚，暂不由代码默认推断；
- 上述“未执行修图”是 8A 当时的历史边界；检查点 8B 已在本文件下一节完成确认后的单次执行 Gate，当前真实边界以 8B 节为准。

## 检查点 8B｜用户确认、单次 BeautifyPic 执行与 ProviderRun（2026-08-28，已完成离线验证）

### 为什么做这一小步

8A 已经有“该怎么改”的不可变计划，但它不能自己发起付费图片 API。8B 的工作不是再猜参数，而是把用户的一个明确确认变成可以被代码逐项核验的短期授权：只有当前照片、当前母版、当前计划和当前安全门仍然一致时，才允许调用腾讯一次；调用后只记录真实回执，绝不把“腾讯返回图片”写成“已经更像母版”。

### 交付五件套

**1. 中文说明。** 新增 `services/execution.py`。它像一个闸门：8A 负责写施工单，用户负责确认是否要施工，8B 负责检查施工单有没有过期或被改过，再把它交给腾讯一次。它不看照片、不计算脸部差异、不让 LLM 决定参数，也不替用户确认。返回图片只交给当前浏览器会话预览/下载；数据库只保留脱敏的“这次调用真实发生了什么”。

**2. 输入、输出和规则。**

| 项目 | 当前实现 |
|---|---|
| 输入 | 8A 的 `proposed` EditPlan、最新 IntentFrame、Profile、PhotoQualityResult、当前内存中的目标图片字节、Tencent Adapter、Execution/Safety Policy |
| 用户动作 | 勾选“仅将当前照片发送给腾讯云 BeautifyPic”并点击确认，或取消；不是 LLM 文本，也不是隐藏自动执行 |
| 确认产物 | 系统生成 `parser_mode=user_structured_input` 的执行 IntentFrame、`confirmed` Plan 新 revision、scope hash 和 10 分钟 ConfirmationScope |
| 放行校验 | 计划状态/作用域 hash/过期时间、当前照片 hash/ID、Profile 版本、质量/安全/同人 Gate、参数范围、一次尝试限制和本地 idempotency key |
| 成功输出 | 一条不可变 `ProviderRun`：参数投影、RequestId、耗时、结果哈希/不透明 `session_memory` 引用；结果字节只给本次浏览器会话，展示区每 30 秒自检过期并清除 |
| 失败/阻断 | 不调用腾讯或只记录一次真实失败回执；显示可读原因。V0 不自动重试，用户再次尝试必须重新确认 |
| 明确不做 | 不落盘结果图、不存 Base64/原图、不生成 VerificationResult、不声称视觉改善、不做多脸或批量 |

**3. 用户已冻结的决策。** 用户明确选择：确认页不提供滑杆改当前计划，改口要重建方案；确认期限为 10 分钟；结果图只在当前浏览器会话暂存并可选下载，不进入 SQLite/JSONL/Trace；每个确认计划只允许一次真实图片编辑调用，任何错误不自动重试。`max_provider_rounds=3` 保留为未来复测循环的 Policy 上限，但本模块的 `max_attempts_per_plan=1` 不会偷偷调用三次。

**4. 六个实际测试案例。** `tests/test_execution.py` 覆盖：

1. 点击确认会产生一份系统结构化执行 IntentFrame 和一份新的 confirmed plan revision；
2. 成功调用只保存脱敏 ProviderRun，结果 bytes 不进入 JSONL，重复点击只会被拦截；
3. 10 分钟确认到期后不调用 Provider；
4. 目标图片 hash 与确认时不同后不调用 Provider；
5. 腾讯 timeout 只记录一条失败/timeout 回执，绝不自动重试；
6. 用户取消时计划标记取消，完全不产生 ProviderRun。

六例均使用 Fake Tencent Client；不会读取真实照片、密钥或网络。

**5. 完整 Trace。** `scripts/smoke_execution_8b.py` 用同一组公开开发 fixture 跑出以下实际离线链路：

```text
fixture_only=true；network_called=false
→ user_confirmation：allowed_features=[face_lifting, eye_enlarging]；expires_in=10min
→ authorization：照片/母版/质量/安全/同人/计划/幂等检查全部通过
→ provider_double：仅调用 1 次
→ ProviderRun：status=succeeded；request_id=fixture-request-8b-001
   FaceLifting=10；EyeEnlarging=10；Whitening=0；Smoothing=0
→ result_ref_kind=session_memory_only
→ verification_started=false
```

这条 Trace 清楚区分“测试替身调用成功”和“腾讯真实返回成功”：它没有联网、没有接触用户照片，也不证明效果。

### 验证证据

- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest tests/test_execution.py -q`：`6 passed`；
- `uv run ruff check`、`uv run ruff format --check` 和 `py_compile` 已覆盖新增执行服务、脚本、测试与页面改动；
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_execution_8b.py`：输出上述 fixture Trace，明确 `network_called=false`；
- Streamlit 在 `127.0.0.1:8502` 临时启动，`/_stcore/health` 返回 `ok`、根页面 HTTP `200` 后已停止该临时验证进程；不影响用户原有的本地页面进程；
- 8B 开发期间**没有**自动发起新的 BeautifyPic 真实图片调用。2026-08-26 的历史 RequestId `1e519f22-b119-41bb-9242-76798f7cab61` 仍只是独立工具 Gate，不是本次 UI 端到端证据。

### 当前问题、边界与下一检查点

- 当前本地 idempotency key 能防止“已写入回执后的重复点击”，但不能在断电、进程崩溃、多进程部署或供应商重复接收请求时提供 exactly-once 保证；这些是受邀部署前的工程 Gate；
- 结果图仅会话内存。浏览器会话结束、服务进程重启或到达 10 分钟内存窗口时，用户只能重新执行/重新上传，不能从数据库找回；
- 8B 成功只等于“腾讯工具返回了图”，8C-1 现在可以在同一会话内做一次本地结构化观察；仍不得把 fixture 或一次测量写成“线上修图一定更像母版”或“用户满意”；
- **历史快照：**当时下一步是 8C-2。该模块现已在本文末尾完成；RAG 仍只预留接口，细则另进独立 Gate。

## 产品决策 Gate｜8C 与 RAG 方向（2026-08-28，历史决策快照；当前 P0-A/P0-B 实现见文末）

> 下面保留的是当时作出 8C 与 RAG 方向判断的过程记录。其后 P0-A/P0-B 已完成本地检索实现；所有“尚未新增依赖/向量表/检索器”的表述只描述当时，不是当前工程状态。

### 本轮背景

8B 能在确认后调用一次 BeautifyPic，但还不能证明结果是否朝用户最终目标改善。如果 8C 永远固定“本地复测一次”，系统会退化成“腾讯能改什么就改什么”，无法围绕目标继续调整。产品负责人同时提出希望学习 RAG，并让 Agent 在工具能力允许的范围内选择更合适的复测方式。

### 已冻结的 8C 产品规则

- 增加 `VERIFICATION_STRATEGY_SELECT`；Agent 在已审核/已授权策略集合内提出复测方案，状态机负责状态和白名单，权限策略负责新的图片出站与成本确认，Adapter 负责真实调用；
- 验证范围按用户最终目标和本轮 `EditPlan` 动态确定。每个 executable 且可可靠测量的目标特征必须复测；未接入或不可测特征标为 `unverifiable/suggestion_only`，不能默认为成功；
- 初次确认覆盖有界计划族，最多三轮。每轮创建新的子 `EditPlan` 和独立 `ProviderRun`，不修改/重试同一计划；只有正确方向上的可验证累积改善才继续；无改善、变差、不可判断、达到上限或用户明确不满意时停止；
- Agent 判断达到当前可验证目标后才向用户展示并收集反馈。点赞/点踩和明确文字为强反馈；追问、新会话、下载为继续使用/行为证据；退出/沉默按上下文记录未知；WAU/MAU继续进入匿名运营账本。

### 本轮 RAG 结论与后续位置

RAG 是“先查审核过的工具说明书再提出方案”，不是向量数据库本身，也不会代替视觉算法或创造未接入的 API。当前 Provider Card 是结构化 P0 基线，不是完整向量 RAG。<span style="color:#C00000"><strong>本轮方向已调整：未来 RAG 也要在 8A 生成 `EditPlan` 前查询工具能力/限制；此外可在质量门、`VERIFICATION_STRATEGY_SELECT` 和失败路由等工具决策点触发。</strong></span> 但只能在真实 Provider Card、Adapter、权限和测试组成的白名单内提供证据。

8C 只预留 RAG 查询/evidence 接口，不提前建设向量数据库。待当前 8C 核心闭环通过后，进入独立 [RAG 决策与开发 Gate](RAG_DECISION_GATE.md)，由产品负责人先冻结知识源、存储、切片、召回、融合、时效、引用、安全和评测，再把检索接回 8A/8C；在此之前不增加向量表或依赖。

### 本轮耦合检查

- 保留 8B 的“同一 EditPlan 只一次 ProviderRun”规则；8C 的下一轮必须是新的子 plan/Run，并通过父 plan/run 和结果 hash 相连，不是偷偷重试；
- CompareFace 只提供同一人物辅助证据，IMS 只提供内容安全证据，不能替代脸型/眼睛几何复测；
- 动态策略的第一批字段已进入 `VerificationResult`/`VerificationStrategyProposal`，合同升级到 Python `v0.4`；计划族续跑已使用其中的血缘字段，外部复测字段仍按后续模块扩展；
- RAG 细则尚未冻结，因此本轮不新增依赖、不新增向量表；仅增加了 RAG evidence 位置，不宣称完整 RAG。

### 本轮文档同步与验证

本轮已再次同步执行版 PRD、`PRODUCT_RULES.md`、`CONTRACTS.md`、`AGENT_PROMPTS.md`、`README.md`、`AGENTS.md`、`DECISION_LOG.md` 和本进展文件；8C-2 增加代码、6 条测试和 fixture smoke。<span style="color:#C00000"><strong>（历史记录，2026-08-29）当时 RAG 尚未实现；之后已完成 P0-A/P0-B/P0-C、Gold evaluator、私有聚合评分和只读 Dashboard，当前状态以本文档后续 2026-08-30 收口章节为准。</strong></span>

### 下一步

8C-2 已完成当前离线工程闭环；外部/混合复测仍需另有出站同意与 Adapter。准备新增工具时，提醒产品负责人开始 RAG 决策 Gate。

## 检查点 8C-1｜修后结果观察与受限策略提议（已完成首个工程切片）

### 1. 中文说明

8B 的真实事实是“腾讯返回了结果图”，8C-1 负责回答“这张结果图能不能被可靠地观察，以及已执行的脸型/眼睛特征是改善、无变化、变差还是无法判断”。它复用 V0 的本地 Pillow/OpenCV 观察器，只在当前进程内处理图片字节；随后由确定性验证器把修前 gap、修后 gap、测量可靠性和轮次策略写成 `VerificationResult`。`VERIFICATION_STRATEGY_SELECT` 先落地成可替换的 baseline：当前可测时提议 `local_geometry`，不可比较时降级 `manual_visual_review`；没有图片再次出站，也没有让 LLM 越权执行工具。

### 2. 输入、输出和规则表

| 项目 | 输入 | 输出/规则 |
|---|---|---|
| 结果观察 | 8B 成功 ProviderRun 的结果字节、目标 photo_id | `ResultObservation`：解码、单脸、归一化特征、质量标记；原图/坐标不落库 |
| 策略提议 | ResultObservation、版本化白名单 | `VerificationStrategyProposal`；记录 selected/allowed/reason/outbound，不授予调用权限 |
| 特征复测 | Profile 特征、EditPlan 修前差异、ResultObservation | `FeatureComparison`：before/after gap、confidence、trend；缺证据即 `unverifiable` |
| 路由 | 各目标趋势、gap tolerance、轮次、反馈 | `VerificationResult`：`CLOSE/REPLAN/STOP/RESHOOT/MANUAL_REVIEW`；没有指数/概率 |
| 数据 | result bytes | 仅内存使用；SQLite/JSONL 只保存脱敏合同和 Trace，`result_bytes_persisted=false` |

### 3. 产品负责人已冻结/无需重新决定的工程默认

- `measurement_tolerance=0.01`、`target_gap_tolerance=0.04`、最低测量可靠性 `0.80`；均属于版本化可配置基线，不是校准概率。
- 首个切片的 allow-list 只启用 `local_geometry`、`manual_visual_review`；`external_subject_match`/`hybrid` 仍是合同候选，待有真实出站 Adapter 和额外同意流程再开放。
- 所有本轮 executable 特征有可靠修后证据且 gap ≤ 0.04 时，记录 `target_evidence_sufficient=true` 并路由 `CLOSE/GOAL_MET`；这仍需用户反馈，不等于满意。
- 变差需要 last-known-good 引用；没有引用则进入开发者复核。无法解码/比较则 `RESHOOT/INPUT_NOT_COMPARABLE`，不继续叠加参数。
- 妆面、肤色、背景等保持项没有自动验证，`preserved_attributes_verified=false` 并在原因码中明确记录。

### 4. 实际测试案例

`tests/test_verification.py` 的 6 条测试覆盖：改善未达目标 → REPLAN；gap 达标 → CLOSE/GOAL_MET；变差有回退 → STOP/RESULT_WORSENED；变差无回退 → MANUAL_REVIEW；不可比较 → RESHOOT；外部策略必须声明图片出站事实并落账脱敏；是否需要新的用户确认取决于已有 scope 是否覆盖当前用途/Provider/照片，不能把同一有效 scope 内的每一轮误报为新授权。`scripts/smoke_verification_8c.py` 输出 4 个 fixture 路由（`improved_replan`、`target_evidence_close`、`worsened_manual_review`、`worsened_stop_with_fallback`），明确 `fixture_only=true`、`network_called=false`。

### 5. 完整 Trace

完整脱敏 Trace 和可读解释见 [`CHECKPOINT_8C_VERIFICATION_GATE.md`](CHECKPOINT_8C_VERIFICATION_GATE.md)。实际顺序为：

```text
observe_result → verification_strategy_select → compare_features
→ route → persist_verification
```

Trace 记录结果哈希、解码/脸数、测量字段、策略白名单/原因、before/after gap、tolerance、趋势、轮次、决定和 `result_bytes_persisted=false`；不记录 Base64、像素、原始坐标或隐藏思维链。

### 验证证据

- **历史快照：**8C-1 当时的 `UV_CACHE_DIR=/tmp/portrait-uv-cache uv run pytest -q` 为 `81 passed, 4 warnings`；8C-2 后的最新全量数字见本文末尾最新检查点。
- `UV_CACHE_DIR=/tmp/portrait-uv-cache uv run ruff check .`：通过；`uv run ruff format --check .`：通过；Python 编译检查通过。
- `UV_CACHE_DIR=/tmp/portrait-uv-cache uv run python scripts/smoke_verification_8c.py`：四种路由和完整 Trace 输出成功，明确未联网。
- 另外对 8B 历史结果文件做了一次**本地只读观察**：`decode_ok=true`、`face_count=1`、18 个归一化特征可提取、无质量标记；这证明观察器能读取真实 JPEG，但不构成新的腾讯调用、8C live receipt 或视觉改善结论。
- Streamlit 已接入 8C 按钮：8B 会话结果存在时可点击“开始修后复测（8C）”，页面只在内存观察并展示结构化证据；本轮没有新发起真实腾讯图片调用。

### 当前问题与下一步

- 本轮尚未把真实 UI 结果跑成新的 Tencent live 8C receipt；历史 BeautifyPic 回执只能证明工具返回图，不能替代本地结果观察证据。
- **历史快照：**当时尚未自动创建后继计划、实现三轮计划族或反馈控件；这些已由 8C-2 实现，当前边界见本文末尾最新检查点。
- 当前策略提议是 deterministic baseline，不是 LLM Agent 动态决策；RAG 只保留 `knowledge_refs` 字段和接口位置，不能写成“已经接入 RAG”。
- 8C-1 通过后，先进入 8C-2 完成计划族续跑与反馈；若要加入新图片工具或真正动态路由，再进入 [RAG 决策与开发 Gate](RAG_DECISION_GATE.md)，冻结语料、存储、切片、召回、融合、时效、权限、引用和评测，再开发。

## 检查点 8C-2｜有界计划族、受限自动续跑与反馈硬停止（2026-08-28，已完成离线验证）

### 为什么做这一小步

8C-1 能回答“这一轮是否改善、是否需要 `REPLAN`”，但还不能安全地把 `REPLAN` 变成下一次行动。如果直接重发上一组腾讯参数，会把重规划变成隐形重试；如果把同一张确认反复使用，又会让用户不知道哪一张图被发送、为什么再次产生费用。8C-2 把“可以继续”收紧为一条可审计链：上一轮真实回执成功并经本地复测确认改善 → 新建一份子计划 → 在首次确认的照片/用途/Provider/预算/轮次 scope 内自动通过 preflight → 发起一次独立腾讯调用 → 自动复测。它不让 LLM 猜参数，也不让页面越过 scope 静默调用腾讯。

### 交付五件套

**1. 中文说明。** 新增 `services/plan_family.py`。它像“第二张施工单的审计员”：先核对上一张施工单、腾讯回执和复测报告是不是同一条链，再把上一轮结果图当作新输入，生成第 2/3 轮小步施工单。它只有规划权；`app.py` 在首次确认的 scope 内写入自动 preflight 后，由 `services/execution.py` 的 Gate 执行一次并自动进入复测，不再要求用户逐轮点击。

**2. 输入、输出和规则。**

| 项目 | 当前实现 |
|---|---|
| 输入 | 当前 confirmed `EditPlan`、上一轮成功 `ProviderRun`、对应 `VerificationResult`、首次确认的 execution IntentFrame、Profile、原始质量门事实、上一轮结果图内存字节 |
| 允许生成子计划 | `REPLAN + improved + cumulative_improvement=true`，未达当前结构化目标证据、结果图 hash 与父回执一致、无结果质量标记/明确拒绝、Profile/确认 scope/期限/轮次都通过 |
| 子计划 | 新 `plan_id`、`parent_plan_id`、iteration+1、上一结果图 hash；只使用仍有可测 gap 且上一轮改善的可执行部位 |
| 参数 | `followup_mapping_v0` 为每次新输入图生成 2—6 的单次强度；绝不把上一轮腾讯值相加，也不让 LLM 填参数 |
| 子轮执行 | 新 `ProviderRun` 记录 `parent_run_id`、父结果 `input_artifact_ref/hash`；首次确认 scope 仍有效时，页面写入 `auto_followup_preflight` 后自动调用并自动进入复测 |
| 用户反馈 | 👍=明确接受；👎=明确拒绝；文字=强反馈但满意度 unknown。三者都关闭当前计划族；文字只保存 SHA-256，不保存原话 |
| 回退 | 修后变差时，若同一会话仍有已知良好结果字节则展示回退预览；没有则如实提示无法预览，不重新调用腾讯 |

**3. 用户已冻结的决策。** 产品负责人确认：最多 3 轮是 Policy 上限；每轮只有正确方向的可验证累积改善才能继续；首次确认已覆盖照片、用途、Provider、预算和轮次时，计划族内可以自动执行，不需要逐轮再次点击；第一次确认文案需告知“上一轮腾讯结果图可能作为下一轮输入”；用户点踩或留文字反馈后，系统立即停止旧计划族、下一步必须重新表达目标，不能把评论直接变成参数。研发发现 8C 复测必须使用 8B 的 confirmed plan 而非 8A proposed 草案后，已把这一血缘约束写入代码和测试。

**4. 五个实际测试案例。** `tests/test_plan_family.py` 已覆盖：

1. 改善但未达目标时生成子计划，子计划有新的父子血缘、当前结果 hash 和小步单次参数；
2. 子轮执行只以父结果图为输入，新的 ProviderRun 写入 `parent_run_id` 与父结果引用/hash；
3. 用户明确点踩会在任何下一次外部调用前阻断；
4. 第三轮之后不能再生成第四轮，确认 scope 与 Safety Policy 都会给出阻断原因；
5. 文字反馈只保留 hash，SQLite/JSONL Trace 不含原话。

五例均使用 Fake Tencent Client 与本地 fixture：不读取用户照片、密钥或网络。

**5. 完整 Trace。** `scripts/smoke_plan_family_8c2.py` 实际输出的脱敏链路为：

```text
fixture_only=true；network_called=false
→ parent ProviderRun：一次 fake Tencent 回执成功
→ verify_result：before_gap=0.12，after_gap=0.05
   trend=improved；target_evidence_sufficient=false；decision=replan
→ plan_family_preflight：父 plan/run/verification、scope、结果 hash、轮次均通过
→ derive_followup_parameters：FaceLifting=2；EyeEnlarging=3（新输入图单次强度）
→ persist_followup_plan：iteration=2；parent_plan_id=...；status=confirmed
→ auto_followup_preflight：scope/hash/round/budget 复核；execution_trigger=auto_bounded_followup
→ child ProviderRun：parent_run_id=...；input_artifact_ref=父结果临时引用
→ auto_followup_verification_preflight → VerificationResult
→ explicit_dislike：route=blocked；reason=explicit_user_dissatisfaction
```

这证明了代码可回放的父子链和阻断逻辑；它不联网、不调用腾讯真实图片 API，也不证明照片视觉效果真实改善。

### 验证证据

- `.venv/bin/pytest -q`：`87 passed, 4 warnings`；其中 `tests/test_plan_family.py` 的 6 条新增测试覆盖子计划血缘、父结果输入、scope 变化 fail-closed、点踩阻断、三轮上限与文字 hash；
- `.venv/bin/ruff check .`、`.venv/bin/ruff format --check .`、`.venv/bin/python -m compileall -q src app.py scripts` 和 `git diff --check` 均通过；
- `scripts/smoke_plan_family_8c2.py` 输出 `fixture_only=true`、`network_called=false`、父子 plan/run hash 血缘和明确点踩阻断；
- Streamlit 健康检查返回 `ok`；页面已接入子计划事实展示、首次 scope 内自动第 N 轮执行与自动复测、点赞/点踩/文字反馈与回退预览。此检查只证明应用可启动，不能代替一张真实用户照片的多轮腾讯回执。

### 当前边界与下一个决策 Gate

- 8C-2 目前是本地几何复测 + 确定性计划族 baseline；`VERIFICATION_STRATEGY_SELECT` 的 LLM/RAG 动态提议、外部/混合复测、批量路由和多脸隔离仍未实现；未来外部/混合策略若已被首次 scope 覆盖可直接受限调用，否则先进入授权 Gate；
- 文字反馈已安全记录，但尚未接入“用户重新授权后由 LLM 澄清不满意点”的下一 IntentFrame 回合；
- 结果图仍只在当前会话内存中，服务重启/超时后不能续跑旧计划族；本地幂等也不是生产级 exactly-once；
- 8C 核心闭环现已完成离线证据 Gate。接回 8A 规划前的工具能力查询、8C 策略/失败路由或准备加入新的修图/验证 Provider 前，都应按已约定进入 [RAG 决策与开发 Gate](RAG_DECISION_GATE.md)，先冻结知识源、向量/混合检索、切片、召回、融合、时效、权限、引用与评测，再开发。

## 产品设计同步｜数据闭环、隐私权限与 RAG 前置方向（2026-08-28，方向记录）

### 本轮完成的产品记录

- 已将短期任务事实、短期反馈/继续使用信号、上下文退出/沉默和长期 Profile 建立率、首次成功修图率、7/30 日回访、WAU/MAU、会话完成率、失败后重传率、明确满意/不满意比例写入执行版 PRD 的待开发数据库部分；真实受邀用户采集和长期聚合仍未开始。
- 已记录 LLM 数据最小化：照片、Base64、人脸向量、主体锚点、密钥和原始 Trace 不发送给 DeepSeek；失败先走本地模板；OpenRouter/跨境默认关闭；ZDR 需由供应商合同或配置核验，不能凭文案认定。
- 已记录分层同意：本次处理、外部 Provider 处理、主体锚点保存 6 个月、公开演示分别授权；本人单人/成年默认范围，多人须全员授权，未成年人拒绝，IMS `Review/Block` 保守拦截，公开展示前再次确认，撤回后按 24 小时主存储/7 天备份清理规则处理。
- 已把真实 DeepSeek 单轮 IntentFrame receipt 原文放入执行版 PRD 的 IntentFrame 区域，作为“听懂文字”而非“看图修图”的可复盘证据。
- 已把 `mapping_policy_v0.1` 的 `≤4%`、`4%—12%`、`>12%` 区间和 `8/15/22` 模式上限写入执行版 PRD；再次强调差异百分比不等于腾讯绝对参数，也不是接受概率。

### 与代码和测试的对齐结论

本轮没有新增运行代码、合同字段或测试；上述内容是已确认产品方向/待开发需求。当前 `product_events` 和本地 Dashboard 仍只代表已观测的运行事件，不能宣称已经收集到真实留存或用户接受率；当前 8A 也仍直接读取 Provider Card，不是完整 RAG。

### 下一步决策 Gate（需要产品负责人先讨论）

RAG 进入独立决策 Gate：产品方向已改为未来在 8A 生成 `EditPlan` 前、以及 8C 策略选择/失败路由时检索工具知识；但知识源、存储、切片、召回、融合、时效、引用、权限、安全、评测、预算和 fallback 仍未冻结。本轮只准备讨论材料，不写代码、不新增依赖，详见 `docs/RAG_DECISION_GATE.md`。

## 检查点 8C-2 同步修订｜前置同意后的受限自动续跑（2026-08-28）

### 本次为什么需要修订

产品负责人进一步确认：用户已经在 8B 看过用途、照片、部位、预算和轮次并完成一次明确同意；后续若只是同一计划族内根据复测证据做小步调整，逐轮展示滑杆并要求点击会增加理解成本，也不能体现 Agent 围绕最终目标持续工作的价值。因此“用户点击”只保留在首次外部处理确认，不能再写成每个子轮的收费前置条件。

### 已同步的实现

- `services/plan_family.py` 的子计划 Trace 现在明确记录 `execution_mode=auto_bounded_followup`、`inherited_confirmation_scope=true` 和 `user_round_confirmation_required=false`；子计划仍是新的不可变 `EditPlan`，不累加上一轮参数。
- `services/execution.py` 将子轮真实调用标记为 `execution_trigger=auto_bounded_followup`；父/子 Run、结果 hash、scope、预算、质量/安全门和幂等检查仍必须通过，失败不自动重试。
- `app.py` 在每个子轮调用前写入 `auto_followup_preflight`，设置会话幂等 sentinel 防止 Streamlit rerun 重复扣费；调用后写入 `auto_followup_completed`，成功结果自动进入下一次 8C 复测，不再出现“执行第 N 轮”按钮。
- 自动复测写入 `auto_followup_verification_preflight/completed`；若继续有可验证改善，最多到版本化三轮上限；若达标、无改善、变差、不可比较、scope 失效或用户反馈停止，则集中展示最终结果和脱敏 Trace。
- 测试新增首轮与子轮 `execution_trigger`、继承 scope 和免逐轮确认断言；原有 8C-2 父子血缘、点踩硬停止、三轮上限和文字 hash 测试继续保留。

### 仍然没有夸写的边界

这次同步不代表已经有新的真实 UI 多轮照片回执，也不代表 RAG、外部/混合复测、多脸隔离、AES-GCM 主体锚点或公网部署已经完成。自动续跑只在首次有效同意的范围内成立；新增 Provider、用途、出境方、预算或照片必须重新授权。

### 本次验收命令

```text
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m compileall -q src app.py scripts
git diff --check
```

## RAG Gate｜治理与 P0 设计决策同步（2026-08-28，历史快照；当前实现见文末 RAG P0-A）

### 本轮完成的产品决策记录

- 已确认执行知识只接受官方资料和项目人工审核内容；Provider Card、权限/失败规则、真实回执和经审计 bad case 可入库，但原图、人脸向量、密钥、未脱敏文本和未审核网页不入库。
- 已确认 P0 本地 SQLite 优先、人工双周复审、启动时加载/版本切换；本地 lifecycle worker 仅产生复审提醒、候选 diff、过期/冲突/Provider smoke 异常告警，不能自动发布知识或改变工具白名单。
- 已确认 RAG query 只含已校验的结构化任务槽位，不含用户原话、照片或向量；关键安全/权限/Provider/参数边界槽位缺失时追问，非关键缺失时走当前 Provider Card baseline；8A 只消费能力/限制/权限/失败 evidence，参数仍由 `mapping_policy` 生成。
- 已确认 RAG Trace、Gold Set、lifecycle/observability worker 和 Dashboard 的目标：可回放 query hash、过滤、召回、融合、重排、knowledge refs、淘汰原因、版本、延迟、成本、fallback 和后续工具路由，并把异常率反查到具体 Trace。
- 已新建 `docs/RAG_GOLD_SET_DRAFT.md`，包含当前三张腾讯 Card 的支持/未接入/多脸/权限语义，以及隔离 fixture 的过期、冲突、缺槽、无结果和提示注入案例；它是人工待审草案，不是训练集或已经跑出的 RAG 指标。

### 一致性审计与未冻结项

审计发现“整篇文档切片 vs 原子规则”“先 SQLite vs 第一版立即混合检索”“固定 20% overlap 是否合理”“8C 仅提议 vs scope 内可执行”“允许云 embedding vs 当前先本地”不能同时写进代码。对“只在 Trace 留引用 vs 用户看来源”，以后一次明确回答已冻结为 P0 紧凑依据卡。现仍在 RAG Gate 中显式保留五项最终决策：双层 `KnowledgeItem/KnowledgeChunk`、P0-A/P0-B、Top-K/低置信、动态上下文/overlap 和 8C 外部/混合执行范围。推荐先本地 SQLite FTS/metadata，再在同一权威库上增本地 embedding/向量/RRF/rerank；P0 的外部/混合复测仅提议、不执行。

### 代码、合同与真实能力边界

本轮没有新增 RAG 运行代码、SQLite RAG schema、embedding、向量索引、reranker、RAG Adapter、RAG Prompt、worker、Dashboard 或外部 API 调用；现有代码仍直接读取 `data/provider_cards/`。`knowledge_refs` 只是既有合同的预留 evidence 字段，当前没有实际检索回执。下一步必须先由产品负责人确认上述五项，再按“SQLite schema/知识导入 → FTS baseline → Gold Set → Trace → local hybrid/rerank → 监控看板”的单模块顺序实现。

## RAG P0-A｜本地权威知识库、可回放检索与安全降级（2026-08-29，已完成本地验收）

> 本节是上方“RAG Gate（未开始工程实现）”历史快照之后的最新状态；实现细节以 [`RAG_P0A_RETRIEVAL_GATE.md`](RAG_P0A_RETRIEVAL_GATE.md) 为准。

### 这一步解决什么问题

此前代码只能直接读取单张 Provider Card，无法判断一条工具事实是否仍有效、为什么被采用、为何被拒绝或能否回放当时的检索。P0-A 将“来源卡”和“可检索规则”拆开：完整来源是 `KnowledgeItem`，其中一条能力、限制或失败边界是 `KnowledgeChunk`。系统先用结构化任务事实剔除不适用、过期或冲突资料，再以本地 SQLite FTS5 在最多 5 条候选中寻找依据，最后输出“有直接证据 / 只能手动建议 / 安全基线降级 / 信息不足”等结构化结论。

### 本轮实际交付

- 新增 `core/rag_contracts.py`：独立的 `KnowledgeItem`、`KnowledgeChunk`、`RagQuery`、`RagRetrievalResult` 合同；不混入六个图片处理合同，也不混入用户运行账本。
- 新增 `storage/knowledge_store.py`：默认 `storage/knowledge.sqlite3`，保存来源、原子规则、FTS5 索引、导入事件和脱敏检索回执；与 `storage/demo.sqlite3` 分离。
- 新增 `services/rag_p0a.py`：把 3 张人工审核的 Tencent Provider Card 拆成 10 条原子事实，执行“metadata 硬过滤 → FTS 候选 → evidence 分类 → 安全路由”。
- 新增 `pages/2_RAG知识库与检索.py` 和 `scripts/smoke_rag_p0a.py`：分别演示紧凑依据卡/Trace，以及默认不联网的真实本地 SQLite/FTS 闭环。
- 新增 `tests/test_rag_p0a.py`：覆盖来源导入幂等、支持能力、未接入能力、多脸/保持项、同人/安全语义、出站拒绝、缺槽、过期、冲突与注入式知识。

### 用户已冻结的规则在代码中的落实

1. `KnowledgeItem + KnowledgeChunk` 双层结构；完整来源可追溯，检索只取原子事实。
2. P0-A 只做 SQLite + metadata + FTS5，最多 5 条候选；不提前接 embedding、向量、RRF 或 reranker。
3. FTS 分数不展示、更不能放行工具；只有 active、无硬冲突、满足 runtime/权限限制的资料才可形成 direct evidence。
4. 不固定 overlap；首批结构化 Card 保留父级 metadata。长文 overlap、P0-B 算法和数值阈值仍待后续 Gate。
5. RAG 可以在未来扩展工具候选，但 P0-A 不新增 Provider、不读图片、不调用外部 API；对 8C 外部/混合复测也只能提出 evidence，不能执行。

### 实际验证与 Trace

- `.venv/bin/pytest -q tests/test_rag_p0a.py`：`9 passed`。
- `.venv/bin/pytest -q`：`96 passed, 4 warnings`；4 条为既有 Pillow 弃用警告。
- `scripts/smoke_rag_p0a.py`：临时 SQLite/FTS 中写入 3 张来源卡/10 条规则；“瘦脸”命中 `FaceLifting` 的 active evidence；“下嘴唇变厚”路由为 `manual_suggestion`；禁止图片出站时为 `baseline_fallback`；缺少关键槽位时为 `query_underspecified`。输出明确 `network_called=false`、`photo_or_raw_user_text_read=false`、`llm_called=false`、`provider_api_called=false`。
- Trace 固定为：`query_contract → metadata_filter → fts_retrieval → evidence_classification → route`，只记录结构化 query、引用、淘汰原因、版本、路由和耗时；不记录照片、原话、密钥、LLM 或 Provider 回执。

### 当前边界与下一决策 Gate

P0-A 不是向量数据库、不是动态 RAG Agent，也不是“自动修图”。它没有接回 `edit_planner.py` 或 `verification.py`，不会创建 `EditPlan`、参数或 `ProviderRun`。P0-B 已在下节完成本地混合检索；下一步必须单独决定：是否正式把 evidence 回接到 8A/8C；人工 Gold Set 的数值门槛；以及 lifecycle/observability worker、RAG Dashboard 和新 Provider 的入库/执行权限。

## RAG P0-B｜本地混合检索、重排与真实本地模型 smoke（2026-08-29，已完成本地验收）

> 本节是上方 P0-A 完成记录后的最新实现状态；完整输入/输出、测试、Trace 和已知问题以 [`RAG_P0B_HYBRID_RETRIEVAL_GATE.md`](RAG_P0B_HYBRID_RETRIEVAL_GATE.md) 为准。

### 为什么要补这一层

P0-A 能以受控关键词检索审核资料，却仍可能漏掉工具文档中“表达不同、含义相同”的能力描述。P0-B 不改变任何权限或执行规则，只在已经通过生命周期、Provider、operation、区域与安全过滤的审核知识中，补上本地语义召回和本地重排：FTS 前 8 + dense 前 8 → RRF 前 10 → reranker 前 10 → 最多 3 条直接依据。模型排序只帮助“找到哪条说明书”，最终是否采纳仍复用 P0-A 的能力、权限、冲突和注入安全规则。

### 本轮实际交付与安全边界

- 新增固定 revision 的本地 `bge-small-zh-v1.5` embedding、`bge-reranker-base` reranker Adapter，以及只用于测试的确定性替身；正常运行 `local_files_only=true`，权重缺失时回退 P0-A 稀疏检索，不转发到任何云端模型。
- 新增 `storage/knowledge_vectors.sqlite3` 作为可重建派生索引，只保存审核 Chunk 的向量、hash 和 manifest；权威知识仍在 `storage/knowledge.sqlite3`，用户照片、原话、人脸向量、锚点、密钥和 Provider 回执都不进入任一 RAG 数据库。
- 新增 P0-B 页面、默认禁止下载的 smoke 和 6 条离线测试；P0-B 仍不创建 `EditPlan`/参数/`ProviderRun`，不调用 DeepSeek、腾讯、新 Provider 或任何图片工具，也尚未回接 8A/8C。

### 实际验证与完整链路

- `.venv/bin/pytest -q tests/test_rag_p0b.py`：`6 passed`；连同现有项目全量为 `102 passed, 4 warnings`（4 条为既有 Pillow 弃用警告）。
- 首次显式 provision 后，默认命令 `.venv/bin/python scripts/smoke_rag_p0b.py` 从本地缓存加载真实固定模型并成功运行；脚本输出 `model_download_permitted=false`、`tool_or_provider_network_called=false`、`photo_or_raw_user_text_read=false`、`llm_called=false`、`provider_api_called=false`。
- 四个真实本地案例分别为：瘦脸 `evidence_found`、唇厚 `manual_suggestion`、禁止图片出站 `baseline_fallback`、关键槽位缺失 `query_underspecified`。首次冷加载案例约 10.5 秒，后续两个检索案例约 0.6—0.7 秒；这只是本机开发证据，不是线上延迟指标。
- 可回放 Trace 为：`query_contract → metadata_filter → sparse_retrieval + dense_index_build/dense_retrieval → rrf_fusion → local_rerank → evidence_classification → route`。其中 rank 只表示资料排序，不是用户人脸相似度、模型正确率或工具强度。

### 当前下一步

P0-B 现在证明“审核工具知识能以两种本地方法找回、排序并在模型缺失时安全降级”，但尚未证明它应该如何改变修图规划或复测。下一项工作不是继续加算法，而是进入**RAG 正式回接 8A/8C 产品决策门**：冻结哪些 stage 可消费 evidence、retriever miss 与当前 Provider Card baseline 的关系、首批人工 Gold Set/holdout 的验收门槛，以及新 Provider/外部复测是否连同 Adapter、权限、预算和测试一起放行。

## RAG P0-C｜受限 evidence 回接 8A / 8C（2026-08-29，已完成本地验收）

> 本节优先于前文“下一步进入 RAG 正式回接 Gate”的历史快照。产品负责人已完成该 Gate 的规则讨论与冻结；细则见 [`RAG_P0C_ADVISORY_INTEGRATION_GATE.md`](RAG_P0C_ADVISORY_INTEGRATION_GATE.md)。

### 为什么做这一模块

P0-A/P0-B 已证明“能从审核工具知识中找资料”，但还没有回答“这些资料怎样安全地参与 Agent 的计划和复测策略”。直接让 RAG 或 LLM 以检索结果放行工具会绕过确认、权限、Provider Card、Adapter 和真实回执。因此本模块只增加可追溯的证据通道，不增加任何图片执行权限。

### 产品负责人冻结的规则

- RAG 只能提议，`execution_authorized=false`；它可在 8A 计划前、8C 策略选择、工具失败降级、新 Provider 评估、参数/权限冲突时被调用。
- 结果必须分成 `direct_evidence`、`reference_information`、`conflict_information`。无冲突时 direct 供已有确定性模块参考；冲突时完整带回来源并阻断，只允许人工复核、手动建议或停止。
- RAG miss、索引故障、缺关键槽、没有 direct evidence 时，立即停止该 RAG 分支并返回“不知道”；写入脱敏 bad case。只有独立已审核、普通 Gate 已通过的 baseline 可原样保留为 `baseline_degraded`。
- 新 Provider 必须经过候选 Card → Adapter/测试替身 → 权限/预算 → live smoke/receipt → RAG Gold 回归 → 产品冻结 → `reviewed_active`；RAG 找到网页或文档不等于可上传图片。
- 首批自动化验收锚点冻结为 RAG-G01（直接 evidence 不等于参数/授权）与 RAG-G09（硬冲突必须阻断）。

### 实际完成内容

- 新增 `services/rag_advisory.py`，将 P0-B 检索结果转为 `RagAdvisoryDecision`；它只接收已校验结构化槽位，不接收照片、原始用户文本、向量、密钥或 Provider 回执正文。
- `core/rag_contracts.py` 增加 advice 路由、bad-case diagnosis、`RagBadCaseRecord` 和严格的 `execution_authorized=false` 合同边界；`KnowledgeEvidence` 附带 feature code，便于已有规划器参考而不猜参数。
- `storage/knowledge_store.py` 新增 advisory run / RAG bad case 脱敏账本；可回放 query hash、候选计数、来源引用、路由和原因，不保存照片或原话。
- `services/edit_planner.py` 和 `services/verification.py` 增加 P0-C 前置检查/来源引用。冲突、未知、只手动建议会 fail closed；direct evidence 只能写入 `knowledge_refs`，参数和策略白名单仍由确定性代码决定。
- `app.py` 在 8A 计划前、8C 策略建议前调用本地 P0-C，并以紧凑依据展示，而不展示原文、裸分或隐藏推理。
- 新增 `tests/test_rag_advisory.py` 与 `scripts/smoke_rag_advisory.py`。

### 真实本地验证

`scripts/smoke_rag_advisory.py` 已运行并输出：

```text
模型下载：关闭
读取照片或原始用户文本：否
调用 LLM：否
调用腾讯 / 其他 Provider：否

G01：advisory_available；FaceLifting 直接来源存在；execution_authorized=false
G09：conflict_blocked；两条 fixture 冲突来源均保留；hard_fact_conflict 入账
未知能力：unknown_stopped；no_active_knowledge 入账
临时知识账本：5 个来源、12 条规则、3 条 advisory run、2 条 bad case
```

这条证据只证明本地 RAG 证据回接、冲突阻断和 miss 路由，不证明修图效果、外部/混合复测或新 Provider 可执行。

### 收尾交叉校验（2026-08-29）

- `.venv/bin/pytest -q`：`106 passed, 4 warnings`；四条均为既有 Pillow 弃用警告。
- `.venv/bin/ruff format --check .`、`.venv/bin/ruff check .`、`.venv/bin/python -m compileall -q app.py src pages scripts` 与 `git diff --check` 均通过。
- `scripts/smoke_rag_p0a.py`、`scripts/smoke_rag_p0b.py`、`scripts/smoke_rag_advisory.py` 均实际运行；P0-C smoke 中 G01 为 `advisory_available` 且 `execution_authorized=false`，G09 为 `conflict_blocked` 并保留两条冲突来源，未知能力为 `unknown_stopped`。三条 smoke 都不读取照片/原话、不会调用 LLM、腾讯或其他 Provider。
- 新启动的本地 Streamlit 进程已实际加载 P0-B 页面并完成一次“瘦脸”本地混合检索：3 张审核来源卡、10 条原子规则、稀疏候选 6、语义候选 6、融合候选 6，最终为 `evidence_found`。这是本地页面可运行证据，不是图片编辑、用户测试或外部 API 证据。端口 8501 上如仍显示旧导入错误，应先停止旧 Streamlit 进程后再按默认 `make run` 重启；不能把旧进程页面当作当前代码状态。

### 当前边界与下一步

RAG 已经能为 8A/8C 留下受限依据，但 Gold Set v2 的范围、阈值和单一人工事实审核者已经冻结并完成一次 public/holdout 聚合运行；仍未有 LLM Judge 实际运行、lifecycle/observability worker、新 Provider 或 external/hybrid 复测 Adapter。RAG 专属 Dashboard 已在下一节完成；它不替代这些准入流程。

## RAG 专属治理 Dashboard｜独立知识账本的可视化审计（2026-08-29，已完成本地验收）

### 1. 中文说明：它解决什么问题

P0-A/P0-B/P0-C 已能留下 SQLite Trace，但产品负责人无法从一张张记录中快速判断“目前有多少审核资料、知识有没有过期、检索通常走哪条路、哪类 bad case 变多”。本模块把这些**已经存在的脱敏事实**做成只读本机管理员页面；它不检索用户照片、不替代 RAG、不评价修图效果，也不让 Dashboard 反过来授权任何工具。

### 2. 输入、输出和规则表

| 环节 | 只读取的输入 | 页面输出 | 硬边界 |
|---|---|---|---|
| 知识目录 | `KnowledgeItem` 的状态、Provider、版本、复审/过期时间、chunk 数 | 审核知识卡/原子规则、生命周期和复审提醒 | 不显示 source body、原始网页或密钥 |
| 检索/建议运行 | 已脱敏 query/advisory/bad-case 账本的 route、stage、计数、时间 | 路由分布、bad-case 分布、最近脱敏记录 | 不显示原始 query、用户原话、照片、向量或隐藏推理 |
| 派生索引 | 本地 dense 索引 manifest 的安全计数 | 索引状态/条目数 | 不下载模型、不触发 LLM、腾讯或图片 API |

### 3. 产品负责人冻结 / 本模块不需要重新决定的事项

- 保留 SQLite/Trace 为权威账本，Dashboard 只是读取其安全聚合；
- 仅供本机管理员查看，不做公网、多人角色或生产鉴权；
- 看板展示“发生过什么”，不展示 Gold 通过率、不把小样本做成用户研究结论；
- RAG 继续 `execution_authorized=false`：页面没有任何执行按钮，不能添加 Provider、参数或出站调用；
- 自动 lifecycle/observability worker、指标告警、Gold 评测聚合仍留在后续产品决策门。

### 4. 实际测试案例

1. 导入 3 张审核 Provider Card 后，snapshot 正确显示 `3` 张知识卡与 `10` 条原子规则；
2. 针对未知唇厚能力触发 `unknown_stopped` 后，页面数据层正确统计 `baseline_fallback`、`unknown_stopped` 与 `no_active_knowledge`；
3. `knowledge_catalog` 只返回 ID、Provider、版本、生命周期和 chunk 数，断言不含 `content` 或 `raw_text`；
4. 浏览器实际打开 RAG 治理页：页面加载、核心指标可见、浏览器控制台没有图表/页面错误；
5. 全量回归确认 Dashboard 没有改变现有 8A/8B/8C 或 P0-C 行为。

### 5. 一条完整 Trace

```text
reviewed Provider Cards
→ seed_reviewed_provider_knowledge
→ RagQuery（未知能力，只有结构化槽位）
→ RagAdvisoryService：unknown_stopped + no_active_knowledge
→ knowledge.sqlite3：query/advisory/bad-case 脱敏事实
→ rag_dashboard_snapshot / knowledge_catalog
→ pages/4_RAG治理看板.py：本机可视化
```

这条 Trace 中没有照片、Base64、用户原话、人脸向量、source body、密钥、LLM 请求或 Provider 图片调用。它证明的是“可观测性页面读取了什么、没有读取什么”，不是 RAG 评测通过或图片处理成功。

### 交叉验证与当前边界

- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q`：`107 passed, 4 warnings`；4 条均为既有 Pillow 弃用警告；
- Ruff format/check、compileall、`scripts/smoke_rag_advisory.py` 与 `git diff --check` 均通过；smoke 仍显示 `execution_authorized=false`、无 LLM/腾讯/图片调用；
- 已同步执行版 PRD、RAG Gate、P0-C Gate、合同/产品规则/Prompt 边界、项目上下文、本地运行说明、README、AGENTS、决策日志与本进展文档；合同字段没有因为 Dashboard 而扩大；
- 下一产品经理决策门：审核 Gold Set v2（逐题、隐藏集保管、人审/Judge、阈值），之后再进入自动 worker、具体参数级 Provider 与 external/hybrid Adapter。

## 2026-08-30 产品决策冻结｜Gold Set v2 与双 Provider 并行准入（开发中）

### 本轮冻结的产品设计

- 评测范围同时覆盖工具能力、权限、隐私、生命周期、冲突和提示注入；Gold Set v2 固定为 34 道开发题、18 道挑战题、20 道隐藏题。
- 产品负责人是唯一人工事实审核者，暂不加入第二位人工评审；盲审 LLM Judge 可以看到本次运行的机器分数/指标摘要，但不能看到 Gold 答案、答案键、开发集标签或实现版本，只辅助检查证据、解释忠实度和路由理由。
- 安全类题要求 100% 正确拦截、0 次错误工具放行；检索/路由门槛冻结为 Recall@5 ≥90%、Precision@3 ≥80%、MRR ≥80%、nDCG@5 ≥85%、路由/证据关系正确率 ≥90%；未来自由生成解释的 Faithfulness ≥95%、人审—Judge 一致率 ≥80%、Hidden—Dev 主要指标差距 ≤10 个百分点。上述门槛不是行业统一标准，实际报告必须附题量和错误清单。
- 隐藏集运行器只能接收无答案输入；答案键已于 2026-08-30 移至产品负责人独立保管位置，正式 holdout 仅回流聚合分数和错误类型。
- 新能力采用参数级人像美化 SDK/API 路线，火山美颜 API V2.0 与腾讯特效 SDK 两条候选路线并行推进。两者当前只建立 Candidate Card、Adapter shell、权限/预算 preflight、离线测试和 live smoke 入口，不自动获得图片出站或执行权限。

### 本轮工程任务（正在并行）

1. RAG 评测运行器：对开发/挑战集计算检索、排序、路由和安全门指标；隐藏集只读无答案运行包；生成逐题人工审核材料与脱敏 Judge 输入。
2. 火山美颜 API V2.0：建立候选能力卡、typed Adapter shell、权限/预算检查、离线替身和 smoke 入口；实际费用、区域、留存、参数和 live 回执仍待核验。
3. 腾讯特效 SDK：建立细粒度参数候选卡、平台/License 边界、typed Adapter shell、权限/预算检查、离线替身和 smoke 入口；静态图片、批量、眉毛/耳朵等能力仍需按目标版本验证。

### 当前不变的安全边界

RAG 只能提议、不能授权；新 Provider 必须经过官方资料/License/隐私/成本 → Card → Adapter → 权限/预算 → live receipt → Gold 回归 → 产品负责人冻结，才可进入 `reviewed_active`。不向 LLM 发送照片、人脸向量或密钥，不因检索命中或 Adapter shell 存在而调用新 Provider。

### 本轮续跑安排

此前创建的续跑提醒已按产品负责人要求于 2026-08-30 取消；当前没有活动中的自动续跑任务。后续仅在产品负责人再次明确要求时创建提醒。

## 2026-08-30｜Gold Set v2 评测器与双 Provider candidate shell 收口

### 本轮完成

1. **Gold Set v2 离线评测器**：增加 `services/rag_gold_eval.py`、`scripts/evaluate_rag_gold_v2.py`、52 题 answerless public 集（34 dev + 18 challenge）、独立 annotations、20 题 holdout 输入包、盲审 Judge 输入合同和人工逐题审核模板。评测器计算 Precision/Recall/Hit@K、MRR、nDCG、路由/证据关系准确率和 hard-safety Gate；冻结门槛由 `project_threshold_gate` 逐项检查，不用平均分抵消安全错误。
2. **答案隔离与盲审边界**：public 运行不读 hidden 答案；holdout 只读取 `case_id/query`，私有答案键由产品负责人在工作区外内存解析，aggregate-only 输出不含 case/Gold/路径。Judge 仅可看到题干、系统输出和从真实预测派生的安全机器摘要，不能看到 Gold、开发标签、实现版本、原图、向量或密钥。当前 live Judge 未实现，fake Judge 只做结构完整性检查。
3. **火山候选 Provider**：增加 `data/provider_cards/volcengine_beauty_api_v2.json`、`services/volc_beauty.py`、离线 smoke 与 6 条测试。所有官方参数、认证、区域、价格、留存、批量限制仍待书面核验；shell 只生成脱敏请求元数据并 fail-closed。
4. **腾讯特效候选 Provider**：增加 `data/provider_cards/tencent_effect_sdk.json`、`services/tencent_effect.py`、离线 smoke 与 8 条测试。Web/PC/Mobile、License、静态图、批量、价格、遥测和图片出站仍待核验；shell 不导入 SDK、不读图片、不联网。

### 当前真实证据

```text
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q
→ 138 passed, 4 warnings（4 条既有 Pillow 弃用警告）
ruff format --check / ruff check / compileall / git diff --check
→ 全部通过
Gold public deterministic baseline
→ 52 题；Precision@3=47.44%，其余当前公开指标=100%；project_threshold_gate=FAIL
Gold holdout evaluator
→ 20 题无答案 prediction/Trace；hidden_answer_key_read=false
Private holdout aggregate scorer
→ Route=25.00%，Recall@5=38.24%，MRR=52.94%，nDCG@5=41.56%；project_threshold_gate=FAIL；hard-safety=MANUAL_REVIEW_REQUIRED
Volc candidate smoke / Tencent Effect candidate smoke
→ 分别 not_run / blocked；network_call=not_attempted；无照片出站
```

HTML、Markdown、JSON 报告已生成于 `reports/`，只含脱敏评测状态，不含答案键。隐藏答案键已移至产品负责人私有的 Documents 保管位置；A3 与 2:40 续跑提醒均已取消。

### 2026-08-30 当前腾讯真实内部 Smoke

- 用户明确授权的一张本地单人照片先通过腾讯 ImageModeration：`RequestId=dc9e3e2b-808c-4bd0-8cd0-0f3429a4f432`，路由为 `passed`；
- 随后 Tencent BeautifyPic 以 `FaceLifting=5`、`EyeEnlarging=5`、美白/磨皮均为 `0` 真实返回：`RequestId=eb9c8393-81c0-40fa-8a4e-b8790e126ea9`，`1924 ms`；
- 结果图没有写入仓库或 `storage/results`，仅存内存并以哈希/生命周期引用留痕；
- 这是一个单样本、受明确授权的内部 Smoke，不得写成“母版一致性已验证”“用户效果已验证”或“批量能力已通过”。

### 当前下一步（需要产品负责人）

public 确定性 predictions、无答案 holdout 和私有 aggregate 比对均已完成；当前基线没有通过。下一步须先决定稀疏 Gold 的 Precision 定义、当前 holdout 的保留/退役与下一份独立验收集、以及私有 `must_not` 是否转换为 canonical event ID；在此之前不按隐藏逐题答案调参。新 Provider 仍需完成官方能力、License、隐私/区域、价格/延迟、真实 receipt、Gold 回归与产品冻结，之后才可能升级为 `reviewed_active`。在此之前 RAG 只提议，候选 Provider 不接收用户照片。

## 2026-08-30｜public/holdout 真实基线与私有聚合评分收口

### 做了什么

1. 已取消所有自动续跑提醒；后续不会因闹钟继续改动项目。
2. 产品负责人隐藏答案键已迁至项目工作区外的本机受限目录；仓库只保留不含答案的 [保管回执](RAG_GOLD_SET_V2_HOLDOUT_CUSTODY.md)。
3. `scripts/run_rag_gold_baseline.py` 真实生成 public 52 题与 answerless holdout 20 题的脱敏 predictions/Trace。该 runner 不读取 annotations 或 private key，不调用 LLM、Provider、网络，不读取图片/人脸向量；全部 advisory 继续 `execution_authorized=false`。
4. `scripts/score_rag_gold_private.py` 增加了私有 Markdown key 的内存解析与 aggregate-only JSON/HTML 输出。它不返回题目、case ID、Gold、原始文本、私有路径、图片或逐题错误；private Markdown 的自然语言 `must_not` 不被臆造为机器事件，因此显式保留 `MANUAL_REVIEW_REQUIRED`。
5. 使用产品负责人明确授权的内部单人照片，仅对既有 Tencent 链路完成一次 IMS `Pass` 和 BeautifyPic 参数级 Smoke；没有把这张照片发给火山或腾讯特效候选路线。

### 实际结果（不含隐藏答案）

| 运行 | 结果 | 正确解读 |
|---|---|---|
| public 52 题 | Route / relation / Recall@5 / MRR / nDCG@5 = 100%；固定分母 Precision@3 = 47.44%；Gate=`FAIL` | 公开开发回归覆盖较好，但固定 K 与稀疏 Gold 的定义有冲突；不是泛化结论 |
| private holdout 20 题 | Route=25.00%；Recall@5=38.24%；MRR=52.94%；nDCG@5=41.56%；Gate=`FAIL` | 当前基线在未见表达/组合上泛化不足，不能写成 RAG 已通过 |
| private hard-safety | `MANUAL_REVIEW_REQUIRED` | 私有 key 的禁止项仍是自然语言，不虚构 machine event ID 来伪造 `PASS` |
| Tencent IMS / BeautifyPic | `Pass` RequestId=`dc9e3e2b-808c-4bd0-8cd0-0f3429a4f432`；BeautifyPic RequestId=`eb9c8393-81c0-40fa-8a4e-b8790e126ea9`，1924 ms | 单样本、现有 Provider 的内部工具回执，不证明一致性效果、用户满意或候选 Provider 可用 |

### 完整 Trace（安全版）

```text
private holdout runtime（无答案）
→ deterministic baseline（只读 query；写脱敏 prediction/Trace）
→ 私有答案键在工作区外、本机内存中解析
→ deterministic evaluator 计算 aggregate metrics
→ 输出 aggregate JSON/HTML（无题目、case ID、Gold、路径）
→ Gate=FAIL / hard-safety=MANUAL_REVIEW_REQUIRED
→ 停止；不按隐藏逐题答案调参
```

### 当前下一道产品决策门

当前实现和证据已经足够明确地暴露三项不能由工程师自行决定的问题：

1. 对单/少 Gold evidence 的题，`Precision@3` 应保留固定 3 为分母、改为按返回条数为分母，还是按 Gold 数量分层报告；
2. 已经使用过的 hidden holdout 应如何保留为诊断，何时退役并如何建立下一份真正独立的验收集；
3. 私有 `must_not` 是否在产品负责人受限环境中转换为 canonical event ID，以支持 hard-safety 自动 Gate，同时不泄漏答案语义。

这些决定冻结前，不会根据隐藏逐题题干补规则、改 Prompt 或改检索权重；新 Provider 仍保持 `candidate` 且 fail-closed。

### 2026-08-30｜本轮最终交叉检验

- 候选 Provider：火山美颜 API V2 smoke=`not_run`，腾讯特效 SDK smoke=`blocked`；两者均 `network_call=not_attempted`、未读照片、未发送图片。
- RAG P0-A/P0-B/P0-C smoke 均可重放：知识账本、混合检索、证据分类、冲突阻断、retriever miss 停止和 `execution_authorized=false` 保持一致。
- 代码质量：`pytest -q` 为 `138 passed, 4 warnings`；`ruff format --check`、`ruff check`、`compileall` 和 `git diff --check` 全部通过。warning 仍为既有 Pillow 弃用提示。
- 文档/合同一致性：已复核执行版 PRD、RAG Gate、Provider 专项、`PRODUCT_RULES.md`、`CONTRACTS.md`、`AGENT_PROMPTS.md`、`DECISION_LOG.md`、本文件、`PROJECT_CONTEXT.md`、`LOCAL_RUNTIME.md`、`README.md` 与 `AGENTS.md`；当前能力仍明确区分已实现、candidate、未实现和待产品决策。
- 自动续跑提醒已全部取消；不会在未冻结 Gate 上继续自动改动项目。

## 2026-08-30｜RAG failure-pattern 分析、自校正候选与双看板收口

### 本轮实现

- 新增 `services/rag_failure_analysis.py` 与 `scripts/analyze_rag_failures.py`：读取公开逐题事实和隐藏聚合事实，输出 `reports/rag_failure_patterns_v1.json/.html`；不读取隐藏答案键、隐藏题干、照片、向量、原始用户文本、LLM、Provider 或网络。
- 新增 `services/rag_correction_candidate.py`：以 `rag-correction-candidate-v0.1` 测试经审核的英文/领域同义词归一化；候选只在临时本地索引中运行，不改变现役 baseline、权限、Provider、参数上限或阈值。
- `pages/4_RAG治理看板.py` 使用显式 report registry 展示公开评测 HTML、隐藏聚合 HTML 与 failure-pattern HTML；新增 `pages/5_RAG优化看板.py` 展示指标分层、隐藏错误类型、失败模式、候选差值与六步 SOP。两页均为本机只读管理员页面。
- 新增 6 条 failure-analysis/报告 allow-list/看板引用测试；本轮收口后全量回归已重新记录为 `144 passed, 4 warnings`。

### 实际结果与解释

公开 52 题：route/evidence/relation/MRR/Recall@5/nDCG@5/hard-safety 均保持原结果，固定分母 Precision@3=47.44%，project Gate=`FAIL`；候选 regression gate=`PASS` 且所有可比指标差值为 0，`active_baseline_changed=false`。公开集 51/52 题 Gold evidence 少于 3 条，固定 Precision@3 的结构性折损已记录为指标口径风险，未擅自改门槛。

隐藏 20 题：仅使用产品负责人私有 aggregate，回流 17/20 错误、route mismatch=15、evidence set mismatch=14、relation mismatch=13；逐题答案不回流，因此报告只作“分布外表达/组合与路由泛化风险”的聚合诊断。hard-safety=`MANUAL_REVIEW_REQUIRED`，因为自然语言 `must_not` 尚未转换成 canonical event ID。

### 完整 Trace

```text
answerless public run
→ evaluator 读取 public annotations（独立步骤）
→ 产品负责人私有 holdout 仅聚合评分
→ failure analyzer 分层识别口径/泛化/安全/执行边界
→ correction candidate 在临时本地 store 回归
→ 比较 candidate 与 active baseline 的指标差值
→ 写脱敏 JSON/HTML
→ page 4 报告集合 + page 5 优化 SOP
→ 产品负责人批准或回滚（本轮未推广）
```

### 当前 Gate

failure analyzer 已可重放、可观测、可回滚，但不是“RAG 通过”。RAG 仍只能提议；候选 Provider 仍 fail-closed；Precision C、Holdout A、Safety ID C 已冻结并实现。下一步是产品负责人审核事件目录、生成 v3 独立 holdout 与 machine-normalized 答案键，以及候选 Provider 正式准入；不得按 v2 hidden 逐题结果继续补规则。

### 本轮最终交叉检验（2026-08-30）

- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q`：`146 passed, 4 warnings`；4 条仍为既有 Pillow 弃用警告。
- `UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run ruff check src tests pages scripts`：通过；`uv run python scripts/analyze_rag_failures.py`：成功生成脱敏 JSON/HTML；`python -m compileall -q app.py src pages scripts` 与 `git diff --check`：通过。
- 页面证据：`http://127.0.0.1:8503/RAG优化看板` 已加载；page 4 的报告集合包含公开评测、隐藏聚合和 failure-pattern 三个 allow-listed HTML。
- 安全边界：failure analyzer/候选只读 public 逐题材料与 private aggregate，不读取 hidden answer key、隐藏题干、照片、向量、原始文本或密钥；候选 `active_baseline_changed=false`，不改变 RAG `execution_authorized=false` 或候选 Provider 状态。
- 当前评测仍为 public project Gate=`FAIL`、private holdout project Gate=`FAIL`；本轮完成的是“失败可定位、候选可回归、报告可视化”，不是通过 RAG 或新 Provider 准入。
- 运行核对时曾触发一次 evaluator 的“未传 predictions → pending”安全默认；随后立即用 answerless public predictions 重新生成正式 `complete` 报告，并核验 `predictions=52`、`missing_predictions=0`。以后查看 public 报告必须显式传入 predictions，避免把 pending 当作质量结果。
- 供应商现场核验：腾讯 Web License 控制台已进入“新建测试版 License”表单，账户当前正式/测试 License 均为 0；需要项目名和精确域名/AppId，尚未提交。火山控制台停在 IAM/API Key 登录页，需账号登录后再核验服务、Key、创点和权限。

### 2026-08-30｜冻结决策后的最终复跑

本轮在 Precision C、Holdout A、Safety ID C 已落地后再次运行 public baseline/evaluator、failure analyzer、P0-A/P0-B/P0-C 及两个候选 Provider 的 fail-closed smoke。public 52/52 predictions 与报告为 `complete`；固定/覆盖式/返回式 Precision@3=`47.44%/100%/100%`，project Gate 仍为 `FAIL`。failure analyzer 的 proposal-only 候选名与版本统一为 `rag-correction-candidate-v0.1`，`active_baseline_changed=false`，私有答案键读取和网络调用均为 `false`。全量回归为 `146 passed, 4 warnings`，Ruff、format、compileall 与 `git diff --check` 通过。

v3 Holdout 模板仍为空，直接运行会按合同拒绝“至少一条运行题”的输入，不会把空模板算成零分；v2 private aggregate 仍保留历史版本，不重新读取答案键。下一道门仍是产品负责人审核事件目录、在工作区外创建/保管 v3 题目与 machine-normalized 答案键，并完成候选 Provider 的正式准入证据。

## 2026-08-30｜三项评测治理决策实现收口

### 本轮目标

产品负责人冻结了 Precision C、Holdout A 和 Safety Event ID C。本轮只实现这些评测治理能力，不改变 RAG 只能提议、候选 Provider fail-closed 或图片执行链。

### 已完成

1. **Precision 双口径。** `services/rag_gold_eval.py` 保留固定 `precision_at_k`，新增 `precision_at_k_effective`、`precision_at_k_returned`、`precision_by_gold_evidence_count`；Markdown/HTML、failure analyzer 和 page 5 看板均可查看。public 52 题重跑结果：固定 Precision@3=`47.44%`、覆盖式=`100%`、返回式=`100%`，project Gate 仍=`FAIL`。
2. **独立 Holdout A。** 新增 `data/evaluation/rag_gold_v3_holdout_runtime.template.json` 与 `docs/RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md`。v2 仅保留历史 aggregate 诊断；v3 题目/答案尚未创建，模板为空且不产生分数。
3. **Canonical Safety Event ID。** 新增 `core/rag_safety_events.py`、公开 `data/evaluation/rag_safety_event_catalog_v0.json`；48 个公开历史标签可确定性映射到 `RAG_EVT_*`，未知标签进入 `MANUAL_REVIEW_REQUIRED`。私有旧 Markdown 仍不自动猜测。
4. **证据链与看板。** private aggregate 输出带评测口径/事件字典版本；failure analyzer 增加双口径差值和治理 policy；RAG 优化看板显示三种 Precision 与 v3 Holdout 生命周期说明。

### 实际验证

```text
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run pytest -q
→ 16 个 RAG evaluator/failure 测试先通过；全量回归最终为 146 passed
uv run ruff check src tests pages scripts
→ 通过
uv run ruff format --check .
→ 通过
uv run python scripts/run_rag_gold_baseline.py --mode public
→ 52 条 answerless predictions，network/LLM/Provider/photo=false
uv run python scripts/evaluate_rag_gold_v2.py --predictions reports/rag_gold_v2_baseline_predictions.json ...
→ complete；双口径指标写入 JSON/Markdown/HTML
uv run python scripts/analyze_rag_failures.py
→ failure JSON/HTML 更新；private answer key read=false
```

### 下一道决策门

需要产品负责人在受限位置审核公开 canonical event 目录，并独立生成/审核 v3 Holdout 题目与 machine-normalized 答案键；同时候选 Provider 仍需 License、隐私/地区、预算、真实 receipt 和 Gold 回归。上述事项完成前，不能写“RAG 已通过”、不能按 v2 hidden 逐题调参，也不能让 RAG 直接授权新工具。

## 2026-08-30｜可部署代码包与火山候选 V0 收口

### 本轮目标

产品负责人希望先拿到可分享的 Streamlit 精确 URL，并确认火山美颜候选是否值得购买/接入。本轮只处理“可安全发布代码”和“供应商准入证据”，不改变 RAG 只能提议、腾讯现有执行链或六个核心合同。

### 已完成

1. **部署入口兼容。** `app.py` 在直接执行时显式加入 `src/`，因此不依赖本机 editable install；`.streamlit/config.toml` 不再把云端进程绑定到 `127.0.0.1`，本机端口仍由 `make run` 提供。
2. **轻量依赖。** `uv.lock` 默认安装 Streamlit/CV/腾讯 SDK 等运行依赖；`torch/transformers` 移到可选 `rag-local` extra。云端未下载本地模型时，P0-B 沿用 P0-A 关键词回退，不改变安全边界。
3. **发布面清理。** `.gitignore` 排除 `.env`、照片/结果图、SQLite/JSONL、模型缓存、隐藏答案和本机报告；只允许审核过的 Provider Card、公开评测材料和部署所需代码进入仓库。新增 [Streamlit 部署说明](STREAMLIT_DEPLOYMENT.md)。
4. **火山准入收口。** 官方资料确认火山美颜 API V2 需要购买支持后付费 API 的创点套餐；公开页面未提供个人免费额度或按次 API 价格。公开 SDK 年度套餐从 6 万元起，但不等同于 V2 API 价格。因此 V0 暂不购买、不配 Key、不发送照片；保留候选壳，未来需重新走完整准入链。

### 当前验证与下一步

本轮已重新运行 `pytest`（146 passed, 4 warnings）、Ruff、format、compileall、`git diff --check`；`uv run python` 可直接导入 `app.py`，本机 Streamlit 8510 端口返回 HTTP 200 后已正常停止。Git tree 已确认不含密钥、照片、账本和隐藏答案，私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent) 已创建并推送 `main`；Streamlit Community Cloud 的“创建 App、选择入口、配置 Secrets、确认 Private/受邀名单”仍需用户在控制台完成，Cloud URL 由控制台生成。

### 2026-08-30｜Cloud URL 与腾讯精准域名现场核验

- 产品负责人已在 Community Cloud 创建 Private App：`https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`。只读 HTTP 探针返回 `303` 到 Streamlit 登录流程，证明应用地址存在且访问控制仍为 Private；未把它写成公网开放或生产服务。
- 腾讯 Web License 表单已打开并复现格式差异：填完整 URL（带 `https://` 或尾部 `/`）时“确定”按钮禁用；填纯主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app` 时按钮可用。主机名 63 字节，低于 128 字节限制。项目名使用 `portrait-consistency-demo`，小程序 Appid 留空；本轮未提交外部 License。
- 当前 v3 Holdout 仍只有 `data/evaluation/rag_gold_v3_holdout_runtime.template.json` 空模板和保管说明；不存在已生成但未公开的题目/答案键文件。canonical safety event 目录为 `data/evaluation/rag_safety_event_catalog_v0.json`，共 48 个稳定事件 ID，状态仍待产品负责人审核。

本轮现场核验没有调用图片 Provider、没有读取密钥、没有上传照片，也没有创建 Tencent License 资源；下一步需产品负责人审核目录、决定 v3 题目/答案键的独立生成方式，并在确认后提交腾讯测试 License。

### 明确边界

GitHub 私有仓库和 Cloud Private App 只是可部署演示入口，不证明生产级多租户、持久化数据库、半年主体锚点删除 SLA、数据驻留合规或公网用户测试已完成。Cloud 容器在美国且磁盘不作为长期存储；在数据出境和受邀名单未确认前，只使用合成/明确授权的测试照片。火山候选仍为 `candidate`/fail-closed，RAG 不得因检索命中而放行它。

## 2026-08-30｜审核确认、v3 Holdout 工作区外草案与腾讯 License 回执

### 已完成

- 产品负责人已审核通过 `data/evaluation/rag_safety_event_catalog_v0.json` 的 48 个公开 canonical Safety Event 映射；目录状态已更新为 `product_owner_approved_2026-08-30`，未知事件仍保守进入 `MANUAL_REVIEW_REQUIRED`。
- 在项目工作区外的受限目录生成 v3 Holdout 审核草案：36 道新题、分离的 canonical 答案候选和逐题审核表。草案不在 Git、不会被 evaluator/app/dashboard 读取，也没有用于调参；产品负责人需要先逐题审核，再决定是否导出正式 answerless runtime。
- 腾讯 Web 测试 License 已在控制台显示为“正常”，绑定精确 Cloud 主机名，当前有效期显示为 2026-08-30 至 2026-09-13。License Key/Token 没有写入仓库、Trace、报告或本进展文档。

### 真实证据链

```text
owner approval of canonical catalog
→ outside-workspace v3 owner-review draft
→ Tencent console License status=normal
→ docs/PRD / RAG Gate / rules / contracts / prompts / decision log sync
```

### 当前阻塞与下一步

当前不是继续按 v2 hidden 逐题修规则，而是产品负责人审核 v3 草案。审核通过后，受限 runner 才能生成只含 `case_id + query` 的正式输入并进行一次盲测；v3 草案不能被写成“RAG 已通过”。候选 Provider 仍需完整 License/隐私/预算/真实 receipt/Gold 准入，RAG 仍只能提议。
