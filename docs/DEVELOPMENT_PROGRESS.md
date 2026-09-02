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
| RAG Gate / P0-A + P0-B + P0-C | 工具知识库、索引、召回/融合、受限 evidence 回接 | **已完成本地工程验收；质量 Gate 未通过** | 已实现独立 SQLite 权威库、3 张审核 Card/10 条原子规则、metadata + FTS5、local dense/RRF/rerank、依据卡、脱敏 Trace，以及 8A/8C 的 direct/reference/conflict evidence 回接；不接 LLM、新 Provider、图片执行或 external/hybrid 复测；V4 泛化质量仍 FAIL |
| Gold Set v2 evaluator / blind input | public/annotations/holdout 隔离、指标、人工审核材料 | **已完成本地验收；当前基线未通过** | 52 题 public + 20 题 holdout 输入、阈值 Gate、HTML/Markdown/JSON 报告和私有 aggregate-only scorer 已实现；public/private aggregate 均 `FAIL`；live Judge 未实现 |
| Gold Set v3 一次性盲测 | 产品负责人审核、answerless runtime、私有聚合评分 | **已完成一次；质量 Gate 未通过** | 36/36 预测；Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%；hard-safety=PASS；逐题答案不回流 |
| 新 Provider candidate shells | 火山美颜 API V2.0、腾讯特效移动/PC 细项、腾讯特效 Web | **已完成离线验收；火山 V0 暂缓** | 火山/移动 PC shell 仍未联网；Web 已有独立浏览器 Adapter、page 6、Browser Receipt 合同和离线 smoke，但仍为 `candidate`，当前实际执行链只用已验证 Tencent |

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
4. **腾讯特效移动/PC 候选 Provider**：增加 `data/provider_cards/tencent_effect_sdk.json`、`services/tencent_effect.py`、离线 smoke 与 8 条测试。Web/PC/Mobile、License、静态图、批量、价格、遥测和图片出站仍待核验；移动/PC shell 不导入 SDK、不读图片、不联网。Web 静态图现由独立的 2026-09-01 切片记录。

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
→ Volc not_run；移动/PC shell blocked；Web 离线 smoke 为 not_run、network_called=false；无照片出站
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

- 候选 Provider：火山美颜 API V2 smoke=`not_run`，腾讯特效移动/PC shell=`blocked`，Web 离线 smoke=`not_run`；Web page 6 已可本机启动，所有候选仍未产生新的图片出站。
- RAG P0-A/P0-B/P0-C smoke 均可重放：知识账本、混合检索、证据分类、冲突阻断、retriever miss 停止和 `execution_authorized=false` 保持一致。
- 代码质量：`pytest -q` 为 `172 passed, 4 warnings`；`ruff format --check`、`ruff check`、`compileall` 和 `git diff --check` 全部通过。warning 仍为既有 Pillow 弃用提示。
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

## 2026-08-30｜RAG P0-D 生命周期审计与本地工程收口

### 本轮背景

P0-A/P0-B/P0-C 已具备知识入库、混合检索和受限证据回接，但此前没有一条可重放的“资料是否仍有效、索引是否跟上”审计链。若把过期/撤回/冲突资料继续送入 8A/8C，问题会被误归因成检索器或 Prompt 质量。因此本轮只补齐知识生命周期治理，不扩大工具能力或执行权限。

### 已完成

- 新增 `RagLifecycleItemAudit`、`RagIndexAudit`、`RagLifecycleAudit` 三个治理合同；六个业务合同字段职责不变。
- 新增 metadata-only `services/rag_lifecycle.py` 与 `scripts/audit_rag_lifecycle.py`：检查审核状态、生效/复审/过期/撤回/冲突、来源 URI、原子规则数和 dense manifest；不会自动修改、发布、删除或重建。
- SQLite 新增 `rag_lifecycle_audits` 脱敏审计账本；dense index 提供安全 manifest；报告 allow-list 增加 `rag_lifecycle_audit.html`；page 4 增加显式“运行一次生命周期审计”入口。
- 同步了执行版 PRD、PRODUCT_RULES、CONTRACTS、AGENT_PROMPTS、RAG_DECISION_GATE、RAG_FAILURE_ANALYSIS_SOP、DECISION_LOG、README、AGENTS 和运行文档；新增 4 条生命周期测试。

### 完整 Trace（真实本地运行）

```text
3 张已审核 Tencent Provider Card
→ 10 条 active 原子规则
→ metadata-only lifecycle audit
→ issue_counts={}
→ dense index status=in_sync
→ RagLifecycleAudit persisted=true
→ reports/rag_lifecycle_audit.json + .html
→ page 4 只读展示
```

审计报告明确 `network_called=false`、`photo/body/raw_text/secret` 不进入输出，`auto_status_change_allowed=false`、`auto_publish_allowed=false`。它是知识治理账本，不是训练 Dataset、自动同步 worker 或质量通过证明。

### 实际验证

```text
./.venv/bin/pytest -q
→ 150 passed, 4 warnings
./.venv/bin/ruff check src tests pages scripts
→ passed
./.venv/bin/ruff format --check .
→ passed
./.venv/bin/python -m compileall -q app.py src pages scripts
→ passed
./.venv/bin/python scripts/audit_rag_lifecycle.py
→ complete；3 items / 10 chunks；issue_counts={}；index=in_sync；persisted=true
Streamlit page 4/5 HTTP smoke
→ `200`；页面入口可启动，生命周期审计/优化看板仍是本机只读视图
git diff --check
→ passed
```

本轮提交 `f594948 feat: close RAG lifecycle audit and observability` 已推送到远程 `main`。Cloud 精确 URL 的只读探针返回 `303` 到 Streamlit 登录页，说明 Private 访问控制仍在生效；它不证明公网开放、云端持久化或真实照片已获跨境授权。

### RAG 中期结论与边界

RAG 的本地工程能力已经收口：独立 SQLite 权威知识库、FTS5、dense/RRF/rerank、P0-C advisory consumer、失败分析、proposal-only correction、生命周期审计、脱敏报告和两个治理看板均可重放、可测试、可追溯。质量方面仍不能宣称通过：public 固定分母 Precision@3=`47.44%`、project Gate=`FAIL`；历史 private holdout aggregate Route=`25.00%`、Gate=`FAIL`；v3 Holdout 仍是工作区外审核草案，未正式盲测。

剩余事项属于新的产品/外部决策门，而不是本轮 RAG 代码遗漏：v3 题目和答案键人工审核后的一次性盲测；是否启用脱敏 LLM Judge；新 Provider 的 Card/Adapter/License/预算/隐私/真实 receipt/Gold 准入；生产级定时审计 worker、PostgreSQL/对象存储与删除 SLA；external/hybrid 复测 Adapter；真实受邀用户数据收集与运营看板验证。以上事项冻结前，RAG 不能直接授权工具或图片出站。

## 2026-08-30｜视觉交互产品设计冻结与色彩探索（无应用代码变更）

### 本轮完成

- 产品负责人冻结中心舞台式首页为默认入口，并采用“中心舞台／对齐工作台 + 母版档案 + 结果记录”的三空间结构；中心舞台以当前照片和本次目标为主，母版作为长期记忆锚点，结果空间承接对比、下载和反馈。
- 将 Agent 交互原则写入执行版 PRD、PRODUCT_RULES、DECISION_LOG、PROJECT_CONTEXT 和 README：用户应看懂目标、Agent 正在做什么、为什么这样做、此刻还需要做什么；参数、回执和脱敏 Trace 进入第二层，隐藏思维链不展示，动效不能伪造工具成功。
- 生成两份可交互、无摄影底图的视觉探索样张：一份是跳出既有偏好的五分支色彩探索树；另一份把参考图的雾灰紫／奶油桃／墨黑／珊瑚层次迁移为本产品的中心舞台，不复用原图或摄影背景。

### 当前真实状态与下一 Gate

交互信息架构已冻结；最终色彩、字体、动效曲线与组件细节仍由产品负责人审阅样张后冻结。现有 Streamlit 应用没有被改动，线上 Private URL 的视觉也尚未升级；本轮没有触及合同、Prompt、工具调用、RAG、照片、数据库或测试逻辑。色彩冻结后，才进入“UI 视觉实现 Gate”：在不改变同意／权限／Provider／Trace 边界的前提下，逐项验证母版、上传、错误、执行、结果和反馈是否可见、可达、可解释。

### 一致性检查

- 执行版 PRD：新增“视觉设计与 Agent 交互”完整产品决策、2.18 冻结摘要和实现矩阵待开发项；明确配色未冻结、UI 未实现。
- 专项规则与记录：PRODUCT_RULES、DECISION_LOG、PROJECT_CONTEXT、README 均同步；CONTRACTS、AGENT_PROMPTS、代码和测试不需要变更，因为本轮未改变数据合同或运行行为。
- 两份 HTML 样张已成功渲染为 PNG，内嵌脚本语法检查通过；为确认本轮文档没有影响既有工程，额外重跑全量 `pytest`（`150 passed, 4 warnings`）、Ruff、format 与 `git diff --check`，均通过。该结果只说明既有应用未被本轮文档／样张工作破坏，不能写成“新 UI 已通过”。

## 2026-08-30｜视觉收敛：参考图基线、低色数与显著 Agent 入口（无应用代码变更）

- 产品负责人已从两条视觉路径中选择“参考图层次迁移”为唯一基线，并明确拒绝摄影背景、原站资产、长段文字、过多装饰和多色堆叠。
- 新的视觉规则为：3—5 个主色；雾灰紫、奶油／肉粉、墨黑为基础；仅保留 1—2 个强调色；短标题／短按钮；自然语言 Agent 输入框作为首屏最显著交互；Demo 视频承担详尽讲解。
- 已生成一个可切换的精简中心舞台样张，包含雾紫珊瑚、宝蓝珊瑚、墨黑蜜桃三组色彩，三组共享同一任务入口与 Agent 对话结构，便于只比较色彩而不再混淆信息架构。
- 当前仍未改 Streamlit 代码、合同、Prompt、工具调用、数据库或测试；最终强调色由产品负责人选择后，才进入 UI 视觉实现 Gate。
- 该样张已成功渲染为 PNG、内嵌脚本语法检查通过；为排除文档与样张工作影响既有工程，重跑全量 `pytest`（`150 passed, 4 warnings`）、Ruff、format 和 `git diff --check` 均通过。该检查不代表新 UI 已实现或被用户验证。

## 2026-08-30｜奥卡姆式页面候选：单任务、单上传、单 Agent 入口（无应用代码变更）

- 产品负责人冻结雾紫、肉粉／奶油粉、墨黑、桃红四色体系，明确不再加入蓝、绿、黄等色彩家族。
- 阅读产品负责人自有 BOOBOO App 后，只吸收“单一主舞台、当前状态可见、有限操作入口、点击后的即时反馈”四项页面简洁原则；不复用其代码、素材、内容、移动端形态或多卡片仪表盘。
- 新候选页将首屏压缩为对齐／母版／记录三空间导航、一个当前上传动作和一个自然语言 Agent 输入框；母版、结果和参数依据继续存在，但只在对应空间或第二层出现。
- 该候选仅用于视觉审核，尚未改动 Streamlit、合同、Prompt、Provider、数据库或 Trace；产品负责人通过后才进入实际 UI 改造 Gate。
- 样张已成功渲染为 PNG，交互脚本语法检查通过；全量工程复核为 `150 passed, 4 warnings`，Ruff、format 与 `git diff --check` 均通过。该结果仅证明本轮候选与文档没有破坏既有工程，不代表新 UI 已实现或完成用户验证。

## 2026-09-01｜v3 Holdout 盲测、第一位用户入口与中期收口

### 本轮完成

1. **v3 Holdout 审核已落地。** 产品负责人完成 36 道题的逐题审核；运行时只保留 `case_id + query`，最终审核材料和答案键仍在项目工作区外的受限目录。没有把题目答案、照片、向量或密钥复制回仓库、应用或公开报告。
2. **正式盲测已运行一次。** 确定性 runner 未读取答案键，只写出 36 条 predictions/Trace；私有 scorer 只在受限环境中聚合，输出不含题干、case ID、Gold 或私有路径。此后不再使用这份 hidden 逐题结果调参。
3. **真实用户入口已准备。** 已打开 Streamlit Community Cloud Private URL 并核对首页加载；新增 [第一位用户端到端测试说明](FIRST_USER_E2E_TEST.md)，把新手操作顺序、人工/自动分工、预期事件链和隐私边界写清楚。真实照片上传和外部调用必须由产品负责人本人完成。
4. **中期报告已生成。** [MIDTERM_STATUS_2026-09-01.md](MIDTERM_STATUS_2026-09-01.md) 汇总已完成、未完成、证据等级、盲测结果和收尾路径。

### v3 盲测真实回执

```text
runner_version                  → rag-gold-baseline-deterministic-v0.2
dataset_version                 → rag-v3-holdout-reviewed-2026-09-01
case_count / predictions       → 36 / 36；missing=0
hidden_answer_key_read         → false
llm_called / network_called    → false / false
photo_or_face_vector_read      → false
external_provider_called       → false
```

私有 aggregate 结果：

| 指标 | 结果 |
|---|---:|
| Route accuracy | 30.56% |
| Evidence exact accuracy | 41.67% |
| Evidence relation accuracy | 23.61% |
| Recall@5 | 59.72% |
| MRR | 77.78% |
| nDCG@5 | 63.81% |
| Hard-safety violations | 0 / 36，Gate=`PASS` |
| Project quality Gate | `FAIL` |

固定/覆盖式/返回式 Precision@3 为 27.78% / 59.72% / 77.78%。当前主要失败集中在 relation、evidence set 和 route；只在 public/dev/challenge 上继续做 proposal-only 迭代，不能把安全 Gate 通过写成 RAG 质量通过。

### UI 8C 多轮回执状态

代码层和自动化 fixture 已通过：首轮观察 → `REPLAN` → 新 child plan → 同一授权 scope 的自动 bounded follow-up → child ProviderRun → 复测；每一步有 parent/child plan/run/hash、preflight、触发方式和结果留痕，点踩或 scope 变化会硬停止。当前还没有第一位用户在 Cloud 页面上传照片，因此尚无新的真实 UI 8C 多轮图片回执、真实视觉改善或满意度数据。`FIRST_USER_E2E_TEST.md` 是下一步的唯一操作入口，不用离线 fixture 冒充 live receipt。

### 交叉一致性检查

- 执行版 PRD：新增 17.18 产品设计决策、13.2 当前盲测/页面状态和 v3 实现矩阵行；旧章节的历史快照保留，但以最新覆盖为准。
- RAG 专项：`RAG_DECISION_GATE.md` 新增 v3 盲测结果；`RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md` 更新审核、隔离、一次性运行和 hard-safety 状态。
- 规则/合同/Prompt：本轮没有改变六个业务合同、RAG advisory-only、Provider 白名单、图片留存或 LLM 数据边界；`CONTRACTS.md`、`PRODUCT_RULES.md`、`AGENT_PROMPTS.md` 需按现有约束理解，未擅自增加执行能力。
- 运行与发布：README、AGENTS、PROJECT_CONTEXT、LOCAL_RUNTIME 和部署说明需以本节“页面已打开、真实用户测试待完成、v3 quality Gate=FAIL”为当前事实；不把页面加载写成真实照片成功。
- 代码与测试：本轮业务行为代码未改变；随后仅修正了侧边栏运行环境文案并重新验证，`pytest`、Ruff、format、compileall、`git diff --check` 和 P0/8C smoke 均通过。

### 下一阶段

先完成产品负责人自己的单张端到端页面流程，再决定是否有证据触发一次真实 8C-2 子轮；随后截取运营 Dashboard 的匿名事件结果，录制可追问 Demo。RAG 质量修正必须在 public/dev/challenge 完成并回归，若要再次验收需另建独立 Holdout。多脸/批量、external/hybrid、真实主体锚点加密与 TTL、生产数据库/鉴权和新 Provider 准入均不由本轮自动推进。

## 2026-09-01｜第一位用户入口复核与 UI 文案一致性

- Private Streamlit 页面已在浏览器中打开并完成只读入口检查：母版上传、目标照片、IntentFrame、8A、8B、8C 和反馈入口均存在；当前没有代用户上传照片或发起新的腾讯图片调用。
- 修正侧边栏环境文案为“运行环境：Private Demo；本机开发端口为 `127.0.0.1:8501`”，避免把 Cloud 受邀入口误写成仅本机服务。该改动不改变合同、权限、Provider、RAG 或 Trace 行为；已推送 `main`，Cloud 重建后页面只读检查确认新文案已显示。
- 代码与文案变更后重新执行全量测试、Ruff、format、compileall、`git diff --check`；结果保持 `150 passed, 4 warnings`、全部静态检查通过。真实 UI 8C 多轮图片回执仍必须由产品负责人在 Cloud 页面亲自触发。

## 2026-09-01｜Cloud 腾讯凭据提示修复

- 第一位用户在 Cloud 页面进入内容安全步骤时看到 `Tencent credentials are absent`。定位确认：这是调用前的配置缺失，不是照片失败、IAM `Unauthorized` 或 ImageModeration 服务拒绝；Cloud 不读取产品负责人电脑上的本机 `.env`。
- 将 ImageModeration、CompareFace、BeautifyPic 和 8B 安全错误提示统一为：在本机 `.env` 或 Streamlit Cloud App Settings → Secrets 配置根级 `TENCENT_SECRET_ID` 与 `TENCENT_SECRET_KEY`。Cloud 的 Secrets 会作为环境变量提供给应用，变量名必须与 `AppSettings` 字段一致；本次不改变合同、权限、Provider 或图片数据流。
- 已把修复后的代码和说明提交到 `main`；保存 Secrets 后需重启/重新运行 App，再由产品负责人重新触发安全检查。若仍失败，按“变量名/是否成对/是否配置到正确 App/重启/腾讯账号权限”顺序排查。

## 2026-09-01｜Cloud ImageModeration 真实错误回执可观测性修复

- 第一位用户完成 Cloud Secrets 配置后，ImageModeration 已越过“凭据缺失”前置门，但页面只显示 `Tencent ImageModeration request failed. See the receipt for request_id/error_code.`，没有把可安全排查的错误码和 `RequestId` 呈现出来，导致无法区分 IAM、服务配置、参数或网络问题。
- 新增 `safe_error_trace` / `safe_error_message`：对腾讯 API 失败只保留 `error_code`、`provider_request_id` 和异常类型；页面显示这两项回执，Trace 同步写入同一脱敏投影；不保存原图、Base64、密钥或腾讯原始错误全文。缺失 `RequestId` 时显示“未返回”。
- 这次修复不改变安全门的 `Pass`/`Review`/`Block` 路由，也不自动重试或放行；用户下一次点击安全检查即可获得真实诊断证据。随后若错误码是 `UnauthorizedOperation`，按 CAM/IMS 权限继续处理；若是参数/服务类错误，按腾讯返回码处理。
- 定向测试 12 条通过；全量测试 `151 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 均通过。Cloud 代码需等待 Streamlit 重建后才会显示新回执文案。

## 2026-09-01｜前端与交互设计需求文档（设计规格完成，未改应用代码）

### 本轮完成

- 新增[《前端与交互设计需求文档》](前端与交互设计需求文档.md)，将执行版 PRD、PRODUCT_RULES、CONTRACTS、PROJECT_CONTEXT、当前 Streamlit 页面和第一位用户测试说明中的真实边界，整理为可直接交付的 UI/UX Spec。
- 规格覆盖：产品概念与视觉隐喻、三空间信息架构、首次/回访/单张/多脸/批量旅程、Agent 状态机映射、Intent/Plan/Consent/Execute/Verify/Feedback 交互、组件状态、图标、颜色 token、字体、动效、响应式、文案、隐私、可访问性、指标和 UI Definition of Done。
- 明确把“已实现并验证”“已冻结待实现”和“产品经理待决策”分开；管理员 RAG/运营页面与 C 端导航隔离；不把 RAG 质量、真实视觉效果、留存或页面样张写成已验证结果。

### 当前状态与下一 Gate

- 这是设计与前端交接文档，不是应用代码变更；当前 Streamlit 页面仍保持工程验证型原型。
- 交互结构、低实体原则和四色家族沿用已冻结决策；具体实现 token、字体、前端承载、移动端范围、批量/多脸入口和记录持久化仍按文档中的红色待决策项处理。
- 产品负责人确认待决策项后，才进入 UI 视觉实现 Gate；实现后必须按文档 Definition of Done 复核状态真实性、授权/隐私、可访问性和当前合同/Trace 不变量。

## 2026-09-01｜RAG 失败模式驱动自动优化 Loop

### 本轮背景

v3 Holdout 一次性盲测的聚合错误集中在 `evidence_relation_mismatch`、`evidence_set_mismatch` 和 `route_mismatch`。本轮把 failure-pattern 分析从“报告”推进为真正可重复运行的候选优化循环，同时遵守 Holdout A：不读取 v3 逐题答案、不重复正式运行同一份 v3、不让候选自动进入现役策略。

### 本轮完成

- 新增 `services/rag_optimization_loop.py`：读取 public dev/challenge、公开 annotations 和 baseline predictions；逐题输出结构化 failure code；只提出受限候选。
- 新增 `scripts/run_rag_optimization_loop.py`：V0 baseline、V1 同义词归一化、V2 relation canonical 化已实跑；V3 evidence packing 与 V4 route safety guard 在连续两代 Composite 增益为 0（低于 0.01）后按停止规则跳过。
- 新增 [RAG 优化 Rubric](RAG_OPTIMIZATION_RUBRIC.md) 和 [RAG 优化进展](RAG_OPTIMIZATION_PROGRESS.md)，明确指标含义、固定 project Gate、Composite 权重、反过拟合和回滚方式。
- 生成 `reports/rag_optimization_loop_v1.json/.html`；page 5 增加 V0→V4 代际表、Composite 曲线、逐题诊断展开、v3 聚合 pattern、反过拟合状态和 HTML 下载。
- 报告额外把 v3 三类聚合 pattern 拆成“观察事实 / 可验证假设 / 下一份 Holdout 证据”三层，并标记计数可重叠；没有把聚合数字当成逐题答案。
- 更新报告 allow-list、执行版 PRD、RAG_DECISION_GATE、DECISION_LOG、SOP、README；六类业务合同和图片执行权限没有被候选改写。

### 实际回执

```text
public cases                      → 52（dev 34 + challenge 18）
V0/V1/V2 composite                 → 0.947436 / 0.947436 / 0.947436
V1/V2 composite gain               → 0.0 / 0.0
public route/evidence/relation     → 100% / 100% / 100%
public fixed Precision@3           → 47.44%（51/52 Gold 少于 3 条）
v3 aggregate pattern               → relation 31 / set 21 / route 25
anti-overfit                       → PASS
network/provider/LLM/photo/hidden  → false / false / false / false / false
active baseline changed            → false
stop reason                        → 两代低增益，跳过 V3/V4
```

### 结论与下一步

本轮证明“逐题诊断 → 单变量候选 → 回归 → 反过拟合 → 边际停止”已经是可执行、可观察、可回滚的工程链路，但没有把 RAG 质量 Gate 变成 PASS。公开集的固定 Precision 主要受 Gold 稀疏分母影响，v3 逐题根因不可见；继续在现有 52 题上堆规则会造成过拟合。下一次质量验收必须先建立独立 Holdout v4，并在新增人工审核表达/组合数据后再打开候选。v3 不再重跑。

### 本轮校验

```text
pytest（含新增 5 条优化 loop 测试与账本幂等冲突回归）→ 160 passed，4 个既有 Pillow DeprecationWarning
ruff check → All checks passed
ruff format --check → 122 files already formatted
compileall（app.py、src、pages、scripts）→ passed
git diff --check → passed
P0-A / P0-B / RAG advisory / lifecycle / 8C / 8C2 smoke → 全部 exit 0
```

## 2026-09-01｜第一位真实用户到达 8A：阻塞修复与 UX 反馈

### 事实回执

第一位用户亲自操作 Cloud Private 页面，已完成：母版上传与 IMS Pass、`ReferenceProfile` 建立、目标照上传与 IMS Pass、当前会话 CompareFace。CompareFace RequestId=`3f4bdc92-33b2-4ee3-844a-db34abbc5eca`，供应商原始分 `56.231842041015625`，按当前未校准 Policy 为 `uncertain`。目标照随后在 8A 被记录为 `subject_match_not_confirmed`、`quality_route_not_continuable`；RAG 返回 Tencent FaceLifting/EyeEnlarging 直接证据，但 `execution_authorized=false`。本轮没有 `EditPlan`、`ProviderRun` 或 `VerificationResult`，没有再次触发付费修图调用。

### 根因、修复与可追溯性

根因不是 RAG 召回、质量算法或 Tencent BeautifyPic，而是旧 UI/代码只实现了“uncertain 阻断”，没有实现产品规则里“本人且有权编辑后可在当前会话降级继续”的路径。已新增 `ConfirmationScope.subject_match_uncertain_acknowledged`（向后兼容可选字段），页面提供一次性确认；`edit_planner`、`confirm_execution` 和执行前 `_ensure_execution_allowed` 都会重新校验该字段。确认不会把 `uncertain` 改成 `match`、不会更新长期主体锚点，`no_match` 仍硬拒绝；事件、策略版本和 scope 字段写入脱敏 Trace，并增加 SQLite migration marker `contract_v0_4_subject_uncertain_ack`。

### 第一位用户 UX 反馈（待 UI Gate，不在本轮擅改）

- 上传母版和目标照片等待明显过长；
- 普通用户不应在首屏直接看到脱敏 JSON；
- A/B/C 检查点、内容安全、同人检查、Profile 冻结和多个按钮暴露了工程流程，操作成本高；
- 用户更希望只用自然语言描述目标，系统在后台完成检查、建档、规划和路由，只在必要同意和结果处交互；
- 当前页面视觉和交互偏工程文档，不够像 C 端产品。

这些是第一位用户的事实反馈，不代表已有普适性结论，也不代表 UI 改版已完成。下一 UI Gate 需先量化各阶段耗时，再讨论图片压缩/并行预检/缓存/异步；把检查点折叠为真实进度，把 JSON/Trace 放到开发者/管理员第二层，只保留必要的首次同意和结果反馈。不能为了减少点击而删除同人或外部图片处理所需的权限门。

### 本轮验证与当前下一步

本地全量 `.venv/bin/pytest -q` 已得到 `160 passed, 4 warnings`；新增测试覆盖“uncertain 未确认阻断、确认后在 bounded scope 内继续、no_match 仍阻断、Trace 记录确认事实”，并修复了同一合同 ID 携带变化上下文时可能泄漏 `sqlite3.IntegrityError` 的幂等冲突路径。最终文档同步后已再次运行 Ruff、格式、compileall 和 diff 检查。Cloud 需要拉取本轮提交并重建；重建后第一位用户只需刷新、在 uncertain 提示处勾选一次确认，再继续 8A→8B→8C。直到产生真实 `ProviderRun`、修后 `VerificationResult` 和反馈，首轮 UI 测试仍不能写成完成或视觉效果已验证。

## 2026-09-01｜最终交叉校验：账本幂等冲突修复

### 发现的问题

全量校验首次在 `test_reusing_contract_identity_with_changed_payload_fails_closed` 暴露一个边界：当相同业务合同 ID 携带变化的 `photo_id` 时，旧实现先按完整上下文查询，找不到原记录，随后由 SQLite 抛出底层唯一键异常。产品上这会把可解释的“证据 ID 已存在但内容不同”变成内部数据库错误，也削弱了 Trace/错误处理的一致性。

### 修复与可观测行为

`LocalTraceStore._insert_session_contract` 现在同时按完整业务上下文和真实 SQLite 唯一键（质量结果 ID、计划 ID+revision、验证 ID）检查已有记录。内容相同继续幂等复用；内容不同统一抛出可识别的 `ValueError`，不覆盖原记录，也不新增第二条事实。测试补充了“质量置信度变化”和“photo_id 变化”两种冲突路径。

### 本轮实际校验

```text
pytest -q                  → 160 passed, 4 warnings
ruff check                → All checks passed
ruff format --check       → 122 files already formatted
compileall                → passed
git diff --check          → passed
P0-A / P0-B / RAG advisory / lifecycle / 8C / 8C2 smoke → 全部 exit 0
RAG optimization loop    → V0/V1/V2 完成，V3/V4 按低增益规则跳过，anti-overfit=PASS
```

该修复不改变 RAG 的质量结果或图片执行权限；它只让本地运行账本在 Streamlit 重放和异常输入下保持可追溯、可回滚、fail-closed。历史快照仍保留原测试数字，当前真实数字以本节、执行版 PRD和 DECISION_LOG 的最新条目为准。

## 2026-09-01｜Cloud ImageModeration 页面失败的根因定位与修复

### 事实

第一位用户在 Cloud 页面看到 `Tencent ImageModeration request failed`。检查 Cloud 运行日志后，最稳定、可重复的异常不是腾讯安全服务返回的内容判断，而是：

```text
sqlite3.IntegrityError: UNIQUE constraint failed: photo_quality_results.quality_result_id
```

Streamlit 的控件交互会重跑整个脚本。旧实现把同一个照片质量合同再次写入 SQLite，导致页面在一次重跑中止；因此页面上的泛化失败提示不能被解读为“腾讯密钥无效”。本机随后使用明确授权照片完成真实 IMS smoke：`status=succeeded`、`Pass`、RequestId=`c95e1359-9ecb-45ac-aa94-3776fbccc0ad`。本机成功不替代 Cloud 新版本回执，但排除了“本项目腾讯服务整体不可用”的假设。

### 修复

`LocalTraceStore._insert_session_contract` 现在同时检查完整业务上下文和数据库真实唯一键。相同 ID、相同脱敏投影会幂等复用并写 `*_reused` 事件；相同 ID、不同内容会转成可识别的合同冲突，不覆盖旧事实、不泄漏底层 SQLite 错误。Verification 完成类产品事件只在首次落账时记录，避免 Streamlit 重跑造成看板重复计数。该修复不改变 IMS 的 Pass/Review/Block 路由、不自动重试，也不绕过安全门。

### 验证和下一步

本地全量校验已为 `160 passed, 4 warnings`，新增幂等复用/变化内容 fail-closed 回归均通过；Ruff、格式、compileall、diff check 和既有 RAG/8C smoke 均通过。提交并由 Cloud 重建后，产品负责人刷新页面、重新执行一次内容安全检查；若仍有腾讯真实错误，页面会显示脱敏 `error_code` 与 `RequestId`，再据此做下一步配置定位。

## 2026-09-01｜腾讯特效 Web Provider：Adapter、准入合同与 Smoke 入口

### 这一步完成了什么

在不改动已验证的 Tencent BeautifyPic 主执行链的前提下，新增一条独立的腾讯特效 Web SDK 试验路径：

- `data/provider_cards/tencent_effect_web.json`：单独的 Web 静态图 Card，当前仍为 `candidate`；不再把移动/PC 细项能力误写成 Web API；
- `services/tencent_effect_web.py`：产品 0—100 到 Web 0—1 的确定性映射、五分钟签名、浏览器组件桥接（静态图按官方 `takePhoto()` 返回 `ImageData`）、Browser Receipt 校验和 `ProviderRun` 构造；
- `pages/6_腾讯特效Web试验.py`：默认官方示例图，用户授权图为可选，结果仅浏览器会话内展示/下载；
- `scripts/smoke_tencent_effect_web.py`：不联网、不读照片、不读密钥的离线合同 smoke；
- `EffectWebAdmissionInput/Decision`：把 License、精确域名、出站/区域、预算、Adapter、真实成功回执和产品批准分开检查，全部满足也只返回 `promote_after_review`，不自动修改 Card；
- `TencentEffectWebParams` 与 `ProviderRun` 联合类型：确保 Web 0—1 参数不会误当作 BeautifyPic 0—100 参数。

### 当前真实状态与下一步

离线 smoke 已通过，新增 9 条 Web Adapter/准入测试；本轮尚未取得新的浏览器 SDK 成功回执，因此 Card 仍是 `candidate`，不能写成新 Provider 已上线、细项五官已可用、批量已支持或供应商图片留存已确认。真实 smoke 需在绑定域名的 Streamlit Cloud 配置 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN` 后进入 page 6，优先运行腾讯官方示例图；Token 只用于服务端签名，不进入浏览器。取得回执后再补非敏感证据、Gold 回归和人工 Card promotion。

### 本轮校验

```text
pytest -q tests/test_tencent_effect_web.py  → 9 passed
ruff check（Web Adapter、page、tests）      → passed
compileall（Web Adapter、page、smoke）      → passed
smoke_tencent_effect_web.py                 → status=not_run, network_called=false
```

## 2026-09-01｜失败驱动 RAG Loop v2：根因修复与真实增益

### 为什么上一轮三代没有效果

上一轮候选只在已生成的 `Prediction` 后处理层改写同义词或 relation。由于 public baseline 的输出本来就是 canonical，V0→V1/V2 的 `route/evidence_refs/evidence_relations` 没有任何变化，Composite 始终为 `0.947436`。这不是“多跑几遍就会变好”的问题，而是候选没有触达真实缺口：自然语言进入 P0-B 前的 query compiler。与此同时，public 52 题主要暴露的是 Gold 稀疏分母，不足以监督 v3 的泛化失败。

### 本轮实现

- 新增 `services/rag_query_compiler_candidate.py`：在 `RagQuery` 边界前抽取受审核 `QuerySignals`，覆盖领域同义词、动作/信息请求、安全/出站、生命周期/冲突、主体确认、多脸/批量、反馈停止；安全和生命周期优先，多个意图保留 evidence union；仍是 proposal-only。
- 新增 `data/evaluation/rag_failure_driven_dev_v1.json`（16 dev + 12 challenge）及 `..._annotations.json`；题目不读取 v3 私有逐题答案，annotations 明确 `owner_review_required`。
- 新增 `services/rag_failure_driven_loop.py`、`scripts/run_rag_failure_driven_loop.py`、`tests/test_rag_failure_driven_loop.py`；page 5、报告注册表和 RAG 优化 HTML 已接入。
- 每代记录 `changed_prediction_count`、指标 delta、public regression、hard-safety、anti-overfit 和网络/LLM/Provider/hidden-answer 布尔事实；`0` 条改变即 no-op，候选不改 active baseline。

### 真实回执

| 代次 | Composite | 增益 | 改变预测数 | Route | Relation | Recall@5 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| V0 | 0.355614 | — | — | 14.29% | 28.57% | 50.00% | 开发集 baseline |
| V1 | 0.403233 | +0.047619 | 2 | 21.43% | 35.71% | 53.57% | 有限改善 |
| V2 | 0.947619 | +0.544386 | 22 | 100.00% | 100.00% | 100.00% | 上游根因被触达 |
| V3 | 0.947619 | 0 | 0 | 100.00% | 100.00% | 100.00% | 下游 relation guard 无增益 |
| V4 | 0.947619 | 0 | 0 | 100.00% | 100.00% | 100.00% | evidence packing 无增益 |

V0 failure codes 为 `route_mismatch=24`、`evidence_relation_mismatch=23`、`evidence_set_mismatch=18`、`rank_mismatch=10`，另有 `metric_sparse_gold_denominator=28`（评测诊断，不是算法缺陷）。V3/V4 连续两代增益 `<0.01`，按停止规则结束。全程 `network_called=false`、`llm_called=false`、`provider_api_called=false`、`hidden_answer_key_read=false`、`active_baseline_changed=false`，anti-overfit=`PASS`；public regression/project Gate 仍 `FAIL`。

### 交付与边界

当前已交付失败分析报告、逐题复盘文档、SOP、Rubric、JSON/HTML 优化报告、page 5 只读看板和 4 条回归测试；可从 `reports/rag_failure_driven_loop_v1.html` 回放 V0/最终候选逐题变化和 failure code。V2 仅是 owner-review 开发集证据，不能写成 RAG 质量通过；下一步是产品负责人审核 28 题 annotations，再建立与 v3 不重叠的独立 Holdout v4。v3 仍不得重跑或读取逐题答案。

### 本轮最终交叉校验（2026-09-01）

```text
pytest -q                         → 178 passed, 4 warnings
ruff check                       → All checks passed
ruff format --check              → 136 files already formatted
python -m compileall             → passed
git diff --check                 → passed
failure-driven loop              → V0→V4 complete, anti-overfit=PASS
P0-A/P0-B/advisory/lifecycle     → smoke exit 0
8C/8C2                           → smoke exit 0
```

4 条 warning 均为既有 Pillow 弃用提示；它们不影响本轮 RAG 结果。该 QA 只证明代码、报告、合同和文档可一起运行，不改变 RAG project Gate=`FAIL` 或候选未推广状态。

本轮补充了 `final_candidate_diagnostics`：报告对 28 道开发/挑战题同时保留 V0 与终态逐题状态；从 V0 到终态共有 24 条 Prediction 事实发生变化（其中 V2 相对 V1 改变 22 条）。人工复盘见 [RAG_FAILURE_CASE_REVIEW_V2.md](RAG_FAILURE_CASE_REVIEW_V2.md)。

## 2026-09-01｜腾讯特效 Web Cloud 重建与 smoke 阻塞

最新提交在 Streamlit Cloud 已完成重建；旧进程缓存导致的 `load_tencent_effect_web_card` 导入错误
已通过 Reboot 消除，page 6 当前能正常加载。该结果只证明部署进程恢复，并非 Web 图片处理成功。

本轮真实 Browser smoke 尚未开始：Cloud Secrets 缺少
`TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`。
页面在服务端签名之前安全停止，未加载 SDK、未发送图片、未生成 Browser Receipt；Card 仍为
`candidate`。已有 Tencent REST Secret ID/Key 与 Effect Web 三项配置不是同一套凭据，不能混用。

下一步：产品负责人在 Cloud App Settings → Secrets 配置三项值后，进入 page 6，优先运行腾讯官方
示例图一次。成功后只记录脱敏 receipt，再进行隐私/区域/留存、预算、Gold 回归和人工 promotion
审核；不能因 Cloud 重建成功、License 正常或离线 smoke 通过而放行主流程。

## 2026-09-02｜V3 解冻验证集：逐题 Trace、失败 SOP 与回归守门

### 本轮背景

产品负责人明确允许读取已经审核的 v3 题目和答案，把 v3 从“独立 Holdout”改为本轮诊断用 `validation`。原始一次性 answerless 盲测快照保留在工作区外、没有重跑；新的独立泛化证据仍必须由 V4 提供。

### 本轮实现

- 新增 `scripts/prepare_v3_validation_package.py`，从 owner-only 审核材料生成明确标记的 validation cases/annotations，不改原始文件；
- 新增 `services/rag_v3_validation_diagnostics.py` 与 `scripts/run_rag_v3_validation_diagnostics.py`；
- 每个 G0–G5、每个 H01–H36 都保存题干、Gold、Prediction、failure code、根因、修正 SOP、查询投影、FTS/dense/RRF/rerank 摘要和安全布尔 Trace；
- 新增 `tests/test_rag_v3_validation_diagnostics.py`（5 条测试）和 page 5 的 V3 逐题诊断区/allow-list 报告；
- 新增 `docs/RAG_V3_VALIDATION_DIAGNOSTICS.md`，同步执行版 PRD、RAG Gate、Holdout 保管、DECISION_LOG、PRODUCT_RULES、CONTRACTS、AGENT_PROMPTS、README 和项目状态说明。

### 实际结果

| 代次 | Route | Evidence relation | Recall@5 | Composite | Public regression Route | 解释 |
|---|---:|---:|---:|---:|---:|---|
| G0 baseline | 30.56% | 23.61% | 59.72% | 0.429780 | 100% | 上游查询理解失败 |
| G1 query compiler v0.1 | 58.33% | 52.78% | 77.78% | 0.629499 | 71.15% | 有增益但回归退化 |
| G2 policy-first v0.2 | 100% | 100% | 100% | 0.950000 | 61.54% | V3 命中但过拟合 |
| G3 regression guard v0.3 | 100% | 97.22% | 100% | 0.944444 | 100% | 保守候选，低置信回退 |
| G4/G5 downstream | 100% | 97.22% | 100% | 0.944444 | 100% | 无额外增益，停止 |

G0 的主要失败计数为 `route_mismatch=25`、`evidence_set_mismatch=21`、`evidence_relation_mismatch=31`、`rank_mismatch=8`；`metric_sparse_gold_denominator=36` 是统计提醒，不是算法错误。G2 把修正前移到自然语言→QuerySignals→RagQuery 边界，证明了上一轮没有效果是“修错层”；G3 再用公开回归守门，避免把 V3 的高分直接当成泛化能力。

### 当前边界与下一步

本轮完全离线：网络、LLM、图片 Provider、人脸向量和密钥均未读取；RAG 仍 proposal-only，active baseline 未改变。最终固定 Precision/project Gate 仍为 `FAIL`，hard-safety 为 `PASS`；不能把 V3 验证集成绩写成 RAG 产品化通过。下一步是新建与 V3 不重叠的 V4 Holdout，再决定是否允许任何候选进入现役查询编译。

### 本轮校验

```text
pytest tests/test_rag_v3_validation_diagnostics.py → 5 passed
scripts/run_rag_v3_validation_diagnostics.py       → status=complete, G0–G5
V3 final relation / Recall@5                      → 97.22% / 100%
public regression after guard                      → Route/Relation/Recall@5=100%
active_baseline_changed / network / LLM / Provider  → false / false / false / false
```

## 2026-09-02｜V3 validation 交付收口（当前事实）

上面的 V3 解冻实现已补齐可视化报告的逐题完整 Trace：HTML 现在为 H01–H36 提供可展开的失败模式、结构化评分和安全 Trace；JSON 仍保存 G0–G5 每一代的全量 Trace。产品负责人明确授权读取验证副本的 Gold，原始一次性盲测快照仍保留、不重跑。

当前诊断链已完成：G0→G2 定位并修复上游查询编译问题，G3 用 public regression guard 回退低置信变更，G4/G5 验证下游关系/打包没有边际收益。最终 validation Route=100%、Evidence relation=97.22%、Recall@5=100%；固定 Precision/project Gate=`FAIL`、hard-safety=`PASS`，active baseline 未改变，RAG 仍 proposal-only。后续只有新建不与 V3 重叠的 V4 Holdout 并通过全量 QA，才可讨论 promotion。

## 2026-09-02｜V3 validation 最终 QA 回执（当前有效）

```text
V3 validation runner                         → exit 0；G0–G5 完整生成
最终 validation Route / Relation / Recall@5 → 100% / 97.22% / 100%
hard-safety                                  → PASS（0/36 违规）
固定 Precision / project quality Gate        → 50.00% / FAIL（稀疏 Gold 口径仍单列）
全量 pytest                                  → 178 passed, 4 warnings
ruff check                                   → All checks passed
ruff format --check                          → 138 files already formatted
compileall / git diff --check                → passed / passed
RAG failure-driven、P0-A、P0-B、advisory、lifecycle、8C、8C2 smoke → 全部 exit 0
```

4 条 warning 是既有 Pillow 弃用提示。本回执只证明当前代码、合同、测试、报告和看板可一起运行；不把 V3 validation 当作独立 Holdout，不改变 active baseline，也不改变 RAG proposal-only 和 project Gate=`FAIL`。原始 answerless V3 盲测快照仍保留，后续推广必须另建不重叠的 V4 Holdout。

## 2026-09-02｜腾讯特效 Web 回执关联错位修复

### 触发问题

第一位用户在 page 6 运行后看到 `browser receipt request_ref does not match the prepared request`。
对照组件回传值、页面运行顺序和回执合同后确认：腾讯 SDK 没有被证明返回错误图片；真正问题是
Streamlit 在组件事件后重跑整个页面，旧代码在重跑时重新随机生成了 `request_ref`，导致上一轮浏览器
回执与新请求不再属于同一代次。

### 已完成修复

- 新增非敏感 request fingerprint（输入引用、输入 hash、产品参数、输入来源、Card 版本）；相同代次
  在重跑期间复用 `request_ref`，输入或参数变化才创建新代次。
- `reset_token` 改为只标识请求代次；签名时间仍可刷新，不会因为重跑刷新签名而重置浏览器结果。
- 对滞留的旧代次回执或输入 hash 不一致回执，页面改为安全忽略并提示重新运行；它们不会写入
  `ProviderRun`。
- Session state 仅存脱敏请求合同/fingerprint，不存图片 data URL、输出图或 License Token。

### 验证

新增“同代次复用 request_ref、参数变化开启新代次、签名刷新不改变 reset token、参数顺序稳定”回归；
Web 专项测试为 `11 passed`。本修复后的全量 QA 以项目最新交叉校验条目为准；真实 Browser Receipt
仍待 Cloud 端重新运行确认，不把合同修复写成供应商成功。

### 本修复后的工程校验

```text
pytest -q                         → 180 passed, 4 warnings
ruff check / format --check       → passed / 138 files already formatted
compileall / git diff --check     → passed / passed
Tencent Effect Web 专项测试       → 11 passed
```

4 条 warning 仍为既有 Pillow 弃用提示；本轮只修复回执关联生命周期，没有新增网络调用或图片
持久化。Cloud page 6 已显示三项 Effect Secrets 已配置并进入组件区，待用户点击当前版本组件后
取得真实 Browser Receipt。

## 2026-09-02｜真实重试、鉴权定位与可重试组件修复

### 本轮完成

- 在 Cloud page 6 重新执行了一次真实浏览器调用；原来的 `request_ref` 合同错位不再出现，
  说明请求代次修复已经生效。
- 腾讯 Web SDK 返回失败回执 `web_receipt_effect_web_fa6f0765ad924597`，约 965ms，未生成
  输出图，ProviderRun 已保存为失败状态，Card 仍为 `candidate`。
- 浏览器日志出现官方 SDK 鉴权错误码 `100`。结合 SDK 日志中显示的 `appid` 为 Streamlit 域名，
  将下一处阻塞定位为 Cloud Secret 中 APPID 的形态/配置，而不是回执关联问题。
- Web bridge 失败后重新启用执行按钮，服务端拒绝 URL 形式的 `TENCENT_EFFECT_APP_ID`，页面显示
  脱敏 `error_code` 与 `safe_error`，不展示原始 SDK 错误对象或密钥。

### 交叉验证

```text
.venv/bin/pytest -q                 → 181 passed, 4 warnings
ruff check                          → passed
ruff format --check                 → passed
compileall                          → passed
git diff --check                    → passed
Tencent Effect Web 专项测试         → 12 passed
```

4 条 warning 仍是既有 Pillow 弃用提示。本轮没有把失败回执写成成功，也没有升级 Card 或主流程
权限。下一步只需在 Streamlit Cloud → App Settings → Secrets 将 `TENCENT_EFFECT_APP_ID` 修正为
腾讯账号数字 APPID（License Key/Token 保持不变），Reboot 后再跑一次官方示例图。

## 2026-09-02｜V4 Holdout 与失败驱动 RAG 优化（当前）

### 本轮完成

- 新建与 V3 不重叠的 48 题 answerless runtime：`data/evaluation/rag_v4_holdout_runtime.json`；题目覆盖工具能力、路由、权限、隐私、生命周期、过期/冲突、提示注入、未就绪 Provider、复测、批量/多脸、缺槽位和参数边界。
- 先完成一次正式盲测，再把预测和 Trace 封存到工作区外受限目录；之后才按负责人授权使用答案做私有 aggregate 和 validation 诊断。
- 新增 V4 查询编译候选、逐题诊断器、私有评分器、运行脚本、7 条专项测试、page 5 看板区和报告注册表入口。
- 输出 `reports/rag_v4_holdout_blind_aggregate.json/.html`、`reports/rag_v4_validation_diagnostics_v1.json/.html`，以及 [RAG V4 Holdout 文档](RAG_V4_HOLDOUT.md)。

### 真实回执与结果

```text
V4 answerless baseline：48/48 predictions；hidden_answer_key_read=false；
annotations_read=false；llm_called=false；network_called=false；
external_provider_called=false；photo_or_face_vector_read=false

baseline：Route 12.50%｜Evidence relation 18.75%｜Recall@5 57.99%｜
MRR 81.25%｜nDCG@5 63.22%｜hard-safety 0/48 PASS｜project Gate FAIL

owner-unlocked validation：最终候选 Route/Relation/Recall@5/effective Precision 均 100%；
blind_snapshot_match=true；active_baseline_changed=false；proposal_only=true；
fixed Precision@3=51.39%｜frozen project Gate=FAIL
```

### 结论和边界

V4 baseline 证明旧查询理解和证据关系在新表达上泛化不足；把修正前移到“自然语言→查询投影”后，解冻验证副本的语义指标明显提升。这个 100% 不是新盲测成绩，不能代表泛化或产品化。G3–G5 连续两代没有新的预测改变后停止，active baseline 没有替换，RAG 继续 proposal-only。固定 Precision 的稀疏 Gold 现象单列为统计提醒，不通过换分母制造成功。

### 本轮验证

`.venv/bin/pytest -q tests/test_rag_v4_validation_diagnostics.py` → `8 passed`；诊断 runner status=`complete`，`blind_snapshot_match=true`。文档、代码、报告、看板和合同边界均以 V4 当前记录为准；全量 QA 在本轮同步完成后重新执行并写入最终回执。

### 下一道 Gate

V4 项目 Gate 仍 FAIL。下一步不是继续对同一批题目调参，而是由产品负责人决定是否修改 Gold evidence 设计/固定 Precision 口径，或建立新的、未参与诊断的 V5 Holdout；在新 Holdout 通过前不得 promotion。真实 Provider、用户照片流程和 RAG 进入图片执行链也仍是独立 Gate。

## 2026-09-02｜Tencent Effect Web 再次真实重试（当前）

### 真实操作与回执

- 产品负责人修正 Cloud Secret 后，在 Cloud page 6 再次明确点击“开始腾讯特效处理”；本次是新的 SDK 调用，不是读取旧的页面文字。
- 同一输入/参数请求代次按合同复用 `request_ref`，所以回执引用仍为 `web_receipt_effect_web_3a3c71bec3f24557`；这是稳定幂等引用，不代表没有重新点击。浏览器 SDK 日志的本次初始化时间为 `2026-09-02T07:28:40Z`（北京时间 15:28:40）。
- 脱敏结果：`status=failed`、`elapsed_ms=628`、SDK 错误码 `100`、规范化页面错误码 `20001001`（鉴权失败）、`output_hash_saved=false`、未生成结果图；`ProviderRun` 已保存失败事实，Card 继续 `candidate`。

### 结论与下一步

回执错位问题已保持修复，组件也允许用户再次点击；但腾讯 Web SDK 仍未通过鉴权。仅凭错误码 100 不能在不查看密钥的情况下断言唯一根因，剩余待核对项是 License Key/Token 配对、签名与数字 APPID、精确域名绑定，以及 Cloud Secret 修改后的应用重载。不要继续盲目重复调用；应在 Cloud App 完成 Reboot/Secret 重载后只做一次新的官方示例图 smoke。取得成功 Browser Receipt 前，不能宣称 Web 图片处理、细项五官或批量能力可用，也不能把候选 Card 放行到主流程。

官方依据：[腾讯 Web 静态图教程](https://cloud.tencent.com/document/product/616/118039)、[腾讯特效 SDK API 文档](https://cloud.tencent.com/document/product/616/75676)、[腾讯特效 SDK 错误码](https://cloud.tencent.com/document/product/616/71684)。

## 2026-09-02｜完整 Web 试验最新回执覆盖

随后再次从当前 Cloud 页面完整执行官方示例图。SDK 完成自身鉴权等待后返回：
`status=failed`、`provider_request_id=web_receipt_effect_web_3a3c71bec3f24557`、
`elapsed_ms=10360`、SDK 错误码 `100`、规范化错误码 `20001001`、无输出图。
同一 `request_ref` 是稳定请求代次的合同设计；本次是新的明确点击，不是自动重试。Provider 仍保持
`candidate/blocked`，下一步只应在核对 Secret 已重载、License/Token 配对、数字 APPID/签名和精确
域名后再运行一次，避免继续重复调用。

## 2026-09-02｜本轮最终交叉校验回执

```text
.venv/bin/pytest -q                          → 189 passed, 4 warnings
.venv/bin/pytest -q tests/test_rag_v4_validation_diagnostics.py
                                             → 8 passed
.venv/bin/ruff check .                       → passed
.venv/bin/ruff format --check .              → 184 files already formatted
.venv/bin/python -m compileall -q ...        → passed
git diff --check                             → passed
V4 diagnostics runner                        → status=complete
blind_snapshot_match                        → true
```

既有 4 条 warning 仍是 Pillow 的弃用提示。本轮离线 RAG、V4 诊断和既有 P0-A/P0-B/advisory/lifecycle/8C/8C2/Web/候选 Provider smoke 均 exit 0；没有新增网络、LLM、照片或 Provider 调用。该回执确认代码、合同、测试、报告、看板和文档在当前快照一致，但不改变 V4 project quality Gate=`FAIL`、RAG proposal-only 或候选未 promotion 的产品结论。

## 2026-09-02｜RAG 低成功率反思审计（当前）

本轮按 `docs/RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md` 对之前的 public no-op、失败驱动 Loop、V3 validation 和 V4 独立盲测做了只读复盘，并安排独立盲审视角复核。审计只读取公开聚合、V4 answerless Trace、公开失败驱动报告和生命周期摘要；没有读取新的隐藏答案、解冻逐题 Gold、照片、人脸向量、密钥，也没有调用网络/LLM/Provider。

关键事实：V4 48 题中只有 8 题生成结构化 `RagQuery` 并留下检索 Trace，40 题在检索前结束，其中 36 题是 `no_reliable_structured_projection`；当前知识库为 3 张审核 Card/10 条有效规则、lifecycle issue=0、index=`in_sync`。所以 V4 Route=`12.50%`、Evidence relation=`18.75%`、Recall@5=`57.99%` 首先暴露自然语言→结构化查询的入口和评测事实混合，不能直接写成 P0-B 向量算法失败。Gold runner 还会把 projection route/evidence alias 合并到 Prediction，P/FX 等评测标签并非当前知识库真实可检索 chunk；盲测使用 deterministic token embedding/overlap fixture，适合重复测试但不代表线上语义模型证据。

fixed Precision@3 的理论上限在 V4 Gold 分布下约为 `0.513889`（公开集约 `0.474359`），低于现行 `0.80` 门槛；这属于评测口径问题，不能解释 Route/Relation 的真实失败，也不能静默修改冻结 Gate。V3/V4 解冻 validation 的高分不能当泛化证据；早期 V0/V1/V2 的 `0.947436` no-op 也确认是修错后处理层。

本轮交付 `docs/RAG_LOW_SUCCESS_REFLECTION_AUDIT.md`、`scripts/audit_rag_low_success.py`、`tests/test_rag_low_success_audit.py` 和 `reports/rag_low_success_reflection_audit.json/.html`。下一步先走“评测合同与真实检索边界 Gate”：拆成①自然语言→结构化查询/路由；②结构化查询→真实 chunk 召回/排序/关系；补齐需要计入 RAG 的 Policy/Rule Card；用 10–15 道公开 smoke 逐题确认“原话→查询→召回→采用→路由”真实发生。产品负责人确认前，active baseline 不变、RAG 仍 proposal-only、不建立新 Holdout。

本轮审计不是质量通过；它只把低成功率拆成可修复的层，防止继续在错误对象上迭代。

## 2026-09-02｜视觉决策冻结：Party Rock + 苹方（历史记录；最新覆盖见下方，无应用代码变更）

### 已冻结的产品输入

- 正式界面主题：Tweakcn `Party Rock` 原始 Light / Dark token；Light background=`#F2F1E6`、primary=`#A855F7`、secondary=`#C084FC`、destructive=`#FF4D4D`，Dark background=`#121212`、primary/accent=`#A855F7`、destructive=`#800000`。本轮不调整明暗、饱和度、对比度或色相。
- 正式界面字体：苹方（`PingFang SC`）；四元黑体及此前字体评审候选不进入当前 UI 实现，只保留为后续品牌字标/实验候选。
- 色彩面积（历史表述）：米白曾被写成最大面积、紫色曾被写成第二大面积；该层级已由下方最新覆盖改为紫色与米白共同主导、紫色略强，黑色结构、其他色少量点缀。
- 面积比例的参考仅取用户示意图的“米白画布 + 黑色侧栏 + 紫色高光”层级关系，不复制示意图内容或资产。

### 边界与下一步

本次只冻结视觉 token、正式字体和相对使用范围，没有修改业务合同、状态机、同意/权限、Provider、结果保留、RAG、审计或 Trace；没有宣称 Streamlit 已完成视觉迁移。下一步在 UI Gate 中用固定 Party Rock + 苹方复核 1440×900 与 1280×800 的 E01/E02 两张关键帧、四区布局、组件状态、可访问性、响应式降级和自然语言主入口，再进入 Frontend 原型与 Impeccable Critical/Audit。

## 2026-09-02｜Web Canvas 生命周期错误修复

前端真实运行暴露 Canvas 错误：SDK 初始化后旧代码尝试重新设置 SDK 输出 Canvas 的 `width/height`，浏览器在部分 WebGL 构建中拒绝该操作。已修复为“SDK 输出 Canvas 固定不变，结果 ImageData 写入新建结果 Canvas”，并新增回归断言防止再次在 `takePhoto()` 后调整 SDK Canvas。该修复只影响结果捕获，不改变鉴权、隐私、Provider Card 或 RAG 准入结论。下一次 Cloud smoke 需拉取新代码后重新验证。

本地验证：`tests/test_tencent_effect_web.py`=`12 passed`；全量 `.venv/bin/pytest -q`=`193 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check` 均通过。离线 Web smoke 仍按设计输出 `status=not_run`、`network_called=false`。

## 2026-09-02｜UI/UX Spec v1.0 审计冻结与关键帧资产（历史记录；v2.0 覆盖见下方）

### 已完成

- 对 `docs/前端与交互设计需求文档.md` 完成前后冲突审计，文档升级为 `UI/UX-SPEC-v1.0`；以最新手动决策覆盖旧候选，冻结四区 Agent 工作台、右侧对话、对齐首页 + Agent 对话子页面、短中文文案、后台自动门控与一次外部授权。
- 清理旧英文 slogan、长标题、背景摄影、前台内容安全按钮、Plan A/B/C、默认工程 Trace、下方 Agent 对话和弹窗新窗口等冲突表达；Trace 收敛为用户主动打开的脱敏执行记录摘要。
- 新增 `docs/FRONTEND_UI_KEYFRAME_PROMPT.md`，当时明确 Image 2 视觉稿、HTML/SVG/Figma 导入边界、K01–K04 状态、文案纪律和 Critical/Audit 检查顺序；该范围已由 v2.0 收敛为 E01/E02。
- 当时生成 `design/keyframes/party-rock-pingfang/` 的四状态版本；旧资产现已归档。当前 active package 为两张 Image 2 PNG、两张分层 SVG 和同源 HTML。
- 完成 SVG XML 校验、HTML 脚本语法校验、Image 2 prompt 元数据扫描（4/4）和 `git diff --check`；Impeccable detector 因本地缺少 HTML parser 依赖以 regex degraded 模式运行，未发现 regex finding，不能替代浏览器/WCAG Gate。

## 2026-09-02｜Tencent Effect Web 真实成功回执（Canvas 修复后）

- 已把独立结果 Canvas 修复推送到 GitHub，并完成 Streamlit Cloud 重部署。
- page 6 真实点击一次成功：`web_receipt_effect_web_4d58ea15a0794370`，`status=succeeded`，`elapsed_ms=2601`，`output_hash_saved=true`，结果只保留在浏览器会话。
- 这闭合了“浏览器 SDK 能否真实返回结果”的技术证据；Provider Card 仍为 `candidate`，因为成功回执不等于完成精确域名、隐私/区域、预算和产品准入。
- 根因与修复：SDK 输出 Canvas 不可调整尺寸；`ImageData` 写入新 Canvas 后再生成 hash。Web 专项回归 12 条，全量 pytest 196 条通过（另有 4 条既有 warning）。

## 2026-09-02｜公平 RAG 评测过程监督（当前最新）

### 本轮目标

反思审计确认，V3/V4 的低分不能直接归因于检索器：有些题没有真正生成检索请求，旧运行器还把上游投影的路由/证据别名混入了最终结果。本轮按产品负责人确认的公平评测 Prompt，先建立“自然语言理解”和“真实知识检索”两条轨道，再用独立过程监督考官检查考试完整性，避免继续浪费 Holdout 数据。

### 已完成

- 新增 `services/rag_process_supervisor.py`：离线、确定性、无答案读取的过程考官；检查题目覆盖、编译状态、合法查询、检索阶段、证据血缘、Prediction 来源和副作用事实。
- 新增 `scripts/run_rag_fair_process_audit.py`：使用已有 V3 validation copy 与 V4 holdout runtime 做无答案过程重放；不扩题、不读答案、不调用网络、LLM、照片、人脸向量或图片 Provider。
- 新增 `tests/test_rag_process_supervisor.py` 三条专项测试，并把报告注册到 page 5「RAG 优化看板」的公平评测区。
- 新增执行规范 `docs/RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md`，并同步执行版 PRD、PRODUCT_RULES、CONTRACTS、AGENT_PROMPTS、RAG Gold Evaluator、Rubric、失败 SOP、DECISION_LOG、README 和 AGENTS 当前真相。

### 真实回执

```text
新版 V3 过程重放：36/36 完整检索 Trace；structured=5；unknown_fallback=31；case_fail=0；process_gate=PASS
新版 V4 过程重放：48/48 完整检索 Trace；structured=8；unknown_fallback=40；case_fail=0；process_gate=PASS
旧 V4 正式快照：process_gate=FAIL
  MISSING_REQUIRED_STAGE=432
  MISSING_GOVERNANCE_FACTS=48
  PROJECTION_INJECTED_INTO_EVALUATION=48
  FORBIDDEN_SIDE_EFFECT_OR_LEAK=2
新运行过程门：PASS；新运行质量状态：READY_AFTER_SEPARATE_GOLD_JOIN
历史快照过程门：FAIL；历史快照质量状态：LOCKED_HISTORICAL_PROCESS_AUDIT
```

新版过程重放通过，说明每道题都完整走了“理解/降级 → 合法查询 → RAG 检索 → 结果 Trace”流程，并且没有把答案、上游投影或外部调用混进来；它不说明 RAG 内容答对。旧快照不完整的事实不能通过补写或改名消除，因此旧质量分数永久锁定；新无答案运行可以在下一步单独连接 Gold 做验证，但不能把验证结果当成新的泛化盲测。

### 当前边界与下一步

过程考官已经把“考试有没有走满、有没有作弊”从内容质量中独立出来；V3/V4 的过程完整 answerless 运行包已经封存，下一步可分别连接两条轨道的 Gold 做验证。RAG 继续 `proposal-only`，active baseline 不变，V4 原有 project quality Gate 仍为 `FAIL`。本轮报告见 `reports/rag_fair_process_audit_v1.json/.html`；脱敏运行包见 `reports/rag_fair_v3_answerless_predictions_v1.json`、`reports/rag_fair_v3_answerless_trace_v1.json`、`reports/rag_fair_v4_answerless_predictions_v1.json`、`reports/rag_fair_v4_answerless_trace_v1.json`；完整过程规范见 [RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md](RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md)。

### 当前边界与下一步

这些是设计定调和可编辑原型，不是 Streamlit 视觉迁移、生产 Figma 云文件、真实用户照片结果或 Provider 效果证明。下一步按冻结源文件进入浏览器正式视觉回归、Frontend 组件映射、Impeccable Critical/Audit、WCAG 2.2 AA 与真实用户走查；任何必须改变冻结产品语义的重大问题都要走变更请求并重新取得确认。

## 2026-09-02｜UI/UX Spec v2.0：两张主关键帧与紫色强化（无应用代码变更）

### 本轮完成

- 按产品负责人最新反馈把活跃视觉收敛为两张主关键帧：E01「入口」与 E02「Agent 对话」；上传、自动门控、澄清、一次外部授权、结果与停止仍由 E02 的同一对话空间承载，不再制作独立状态页。
- 将旧 K01—K04 资产安全归档到 `design/keyframes/party-rock-pingfang/archive/v1-four-state/`；当前 `index.html` 顶部只保留 E01/E02 切换。
- 重新生成 Image 2 E01/E02 方向稿，使用 Party Rock 原始 token 与苹方：紫色与米白共同主导，紫色在暗流、对齐舞台、激活状态和关键操作块中略强；黑色只做导航/暗流底/文字/分隔结构，其他色少量点缀。PNG 不含真实人物、真实结果或工程 Trace。
- 生成同源可编辑 `e01-entry.svg`、`e02-agent.svg`，并导出 `renders/1280/` 与 `renders/1440/`；HTML/SVG 是精确文案和布局源，PNG 仅作材质与比例参考，未声称原生 Figma `.fig`。
- 同步更新 `docs/前端与交互设计需求文档.md`、`docs/FRONTEND_UI_KEYFRAME_PROMPT.md`、执行版 PRD、`PRODUCT.md`、`PRODUCT_RULES.md`、`README.md`、`PROJECT_CONTEXT.md`、`AGENTS.md` 与关键帧包 README；明确旧的“米白最大、紫色第二”仅为历史记录，当前执行以紫色—米白共同主导为准。

### 本轮静态回执

- SVG XML 解析通过；四张 SVG-derived 1280/1440 renders 已做图像检查。
- HTML 内联脚本语法通过；两张 active Image 2 PNG 的 `impeccable:prompt` 元数据扫描为 `2 raster, 0 missing`；四张 1280/1440 PNG 是由 SVG 源导出的评审帧，不重复计入 Image 2 资产。
- 已执行旧英文 slogan、Plan A/B/C、假进度、隐藏思维链和未经校准分数的静态禁用文案扫描；没有把这些内容放入 active keyframes。
- Impeccable detector 如因本地 HTML parser 依赖缺失而以 regex degraded 模式运行，结果只能作为静态提示，不能替代浏览器视觉回归和 WCAG 2.2 AA。

### 当前边界

本轮只完成设计规范、Image 2 方向稿和可编辑源，没有修改 Streamlit 应用代码，也没有取得真实用户照片、多轮 UI 回执、Provider 视觉效果或生产级 Figma 云文件。下一步按 UI Gate 做浏览器回归、Frontend 组件映射、Critical/Audit、可访问性和真实用户走查；若必须改变已冻结语义，需新增带原因、影响和回滚点的变更请求。

## 2026-09-02｜视觉方向重开：Getty × Party Rock 三套候选（无应用代码变更）

### 本轮目标

产品负责人否定上一版中间工作区的紫黑暗流/暗影，要求参考 Party Rock 示意图的黑色左导航、米白工作纸、柔性紫色框和荧光绿动感，并以 Getty `Tracing Art` 的关系/轨迹叙事提升高级感。本轮只重新探索视觉构图，不改变两条路由、四区语义、自然语言主链、授权与结果边界。

### 已完成

- 新增 `docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`：抽象 Getty 的“先路径后数据、关系轨迹、编辑式留白、混合媒介证据、序列节奏”，并翻译成产品视觉规则、反模式和下一 Gate。
- 新增 `design/keyframes/party-rock-pingfang/candidates/candidate-review.html` 与 `candidates/README.md`：可切换 A「档案游线」、B「柔性索引」、C「开放谱系」以及 E01/E02，支持写入评审备注。
- 为 A/B/C 每套制作 E01 入口和 E02 Agent 对话两张 Image 2 方向稿（共 6 张），保存同名 Prompt sidecar；所有 PNG 已嵌入 `impeccable:prompt`。
- 为每套生成两张可导入 Figma 的分层 SVG，并从同源 SVG 导出 1280×800 与 1440×900 渲染帧。SVG 以 `nav/context/workspace/agent/trajectory` 等语义图层组织，未嵌入真实照片、结果图、密钥或 Trace。
- 将 `docs/前端与交互设计需求文档.md` 升级为 `UI/UX-SPEC-v2.1`：产品语义与 token/字体继续冻结，上一版紫黑暗流改为历史基线，最新视觉硬约束统一为左侧黑色导航、中央/右侧米白、紫色柔性框/轨迹、荧光绿少量节点；候选选择前不冻结具体构图。
- 同步更新 `docs/FRONTEND_UI_KEYFRAME_PROMPT.md` 与关键帧包 README，明确“每套严格两帧、共三套候选、PNG 与 SVG/HTML 的精确性边界”。

### 静态回执

- 6 张 Image 2 PNG：`impeccable:prompt` 扫描 `6 raster, 0 missing`（只扫描源 raster；SVG-derived renders 不重复计入模型资产）。
- 6 张 SVG：`rsvg-convert` 导出 12 张 1280/1440 渲染帧；待继续执行 XML/浏览器/WCAG 正式 Gate。
- 已人工检查 A/B/C 六张 1440×900 渲染帧：黑色只在左导航/结构，中央/右侧为米白；紫色通过柔性框/轨迹呈现；荧光绿为少量节点；未出现中间紫黑暗影。
- `ui-ux-pro-max` 安装命令曾尝试运行，但 GitHub clone 长时间无可用结果后已安全取消；没有把未安装的 skill 写成已使用。本轮继续使用已加载的 Impeccable 能力完成候选方向和静态资产。

### 当前边界与下一步

本轮仍是视觉候选，不是 Streamlit 迁移、生产 Figma 云文件、真实用户照片结果或 Provider 效果证明。下一步由产品负责人在候选评审页选择 A/B/C 或混合方向；选择后再运行 Impeccable Critical/Audit、浏览器/WCAG UI Gate，并把最终方向映射到 Streamlit。方向未选择前不修改应用代码、不改业务合同、不新增关键帧。

### 收尾复核补充

- 针对 A/B/C 的 E02 Image 2 源图完成一次定向重生成并覆盖旧源：移除真实人物/照片、伪造百分比与分数、日期/ID、雷达图和密集仪表盘痕迹；保留黑色左导航、米白工作面、紫色柔性框/轨迹和少量荧光绿节点。
- 重新扫描 6 张源 PNG：`impeccable:prompt`=`6 raster, 0 missing`；6 张 SVG XML、候选评审页内联脚本、禁用 UI 文案扫描与 `git diff --check` 均通过。源图尺寸为 `1586×992`，作为 1440×900 方向稿的材质参考；精确排版仍以 SVG 为准。
- 当前工作区全量 `.venv/bin/pytest -q` 为 `213 passed, 1 failed, 4 warnings`。唯一失败来自既有 Tencent Effect Web 回归测试对末尾拒绝样本的 `hard_safety_passed` 断言，和本轮设计文档/静态资产无关；没有修改该业务代码或测试来掩盖它。Impeccable detector 仍因本机缺少 HTML parser 依赖而是 degraded regex 提示，不能替代浏览器/WCAG Gate。

## 2026-09-02｜反思审计后公平评测的最终同步回执

本轮任务按公平评测 Prompt 完成并封存：新版 V3 `36/36`、V4 `48/48` 均有完整的“自然语言理解/未知降级
→ 合法查询 → P0-A/P0-B 检索 → retrieval-only Prediction → finalized Trace”；过程监督考官均为
`PASS`。过程报告同时保留旧 V4 正式快照的历史 `FAIL` 及其违规计数，不用新版重放覆盖它。

最终 QA：`uv run pytest -q`=`196 passed, 4 warnings`；`ruff check .`、`ruff format --check .`、
`python -m compileall -q src scripts tests`、`git diff --check`、P0-A/P0-B/advisory/lifecycle/8C/
8C2/Web/候选 Provider smoke 和 `run_rag_fair_process_audit.py` 均 exit 0。当前下一步是独立 Gold join：
只连接已经封存的新运行包，不重新跑题，不读取或修改旧快照，不把过程 PASS 写成内容质量或产品化通过。
### 脱敏边界修复

复核发现 Trace 的嵌套 Prediction 仍保留明文 `case_id`，已在序列化层移除并用 `case_id_sha256` 替代；
新增回归断言后，四份 answerless 运行包均通过题干/答案/明文案例编号扫描。该修复不改变过程门或质量
指标，只确保下一步 Gold 连接不会把案例标识带入公开产物。

## 2026-09-02｜Tencent Effect Web → Tool Registry → Meta-Agent 提议层

### 本步目标

把 page 6 已有的 Tencent Effect Web 试验接入统一的 Provider Card 和 Meta-Agent 控制面，同时保持 candidate 工具不能偷偷进入真实主流程的边界。

### 已完成

- 新增 `services/tool_registry.py`：从 `tencent_beautify_pic.json` 和 `tencent_effect_web.json` 生成只读 `ToolDescriptor`；verified baseline 与 candidate Web 的 `execution_allowed` 明确分离。
- 新增 `services/meta_agent.py`：输出结构化 `ToolProposal`，记录阶段、功能、工具/Card 版本、RAG 证据、所需检查、阻断原因和 baseline fallback；`execution_authorized=false` 固定不可变。
- 8A 在现有 RAG advisory 后记录 Meta-Agent proposal；page 6 也展示候选工具选择 Trace，并把完整的非敏感 proposal Trace 写入脱敏事件账本。两处都不会因 proposal 直接调用新工具。
- 新增 `tests/test_meta_agent.py`（6 条）和 `scripts/smoke_meta_agent_tool_routing.py`；覆盖 baseline、Web candidate、RAG conflict、未知能力、无网络/无图片/无 ProviderRun 副作用。
- 新增执行 Prompt `docs/TENCENT_EFFECT_META_AGENT_INTEGRATION_PROMPT.md` 的当前执行增量，保持 A/B/C 结果交接为下一道产品 Gate。

### 离线回执

```text
Meta-Agent smoke: implemented=true
requested_features=face_lifting + eye_enlarging
selected=tencent_effect_web/WebARImage (candidate_proposal_only)
fallback=tencent_beautify_pic
execution_authorized=false
network_called=false
image_bytes_read=false
provider_run_created=false
专项测试：6 passed；本轮全量 `pytest -q`=`205 passed, 4 warnings`；Web/RAG/规划器回归仍通过。
```

### 当前状态与下一道 Gate

这一步已完成“工具卡 → Registry → Meta-Agent → proposal-only Trace”的控制面接入；它不表示 Web Provider promotion，也不表示 Web 结果图可直接进入当前 Python `VerificationResult`。当前 `EditPlan` 仍是 BeautifyPic 专用，Browser Receipt 仍只有浏览器元数据。要进入主流程，需由产品负责人冻结 A 浏览器端复测、B 一次性受限回传 Python 或 C Web 只展示/下载之一；冻结前不改现有图片留存边界。

## 2026-09-02｜Web Card → EditPlan → Meta-Agent → E1/E2 当前进展（B 已冻结）

### 本轮已完成

1. **执行 Prompt**：新增 `docs/TENCENT_EFFECT_WEB_FULL_INTEGRATION_PROMPT.md`，明确 Web Card、合同桥、结果 handoff、共同复测、E2 回归、E3 准入和回滚顺序。
2. **合同桥**：`EditPlan`/`ProviderRun` 支持 `tencent_effect_web/WebARImage`，Web 的 0—1 参数与产品 0—100 参数独立校验；错配/越界 fail-closed。
3. **E1 handoff**：浏览器使用独立结果 Canvas；`EffectWebBrowserResult` 和 `accept_effect_web_browser_result()` 校验请求代次、输入/输出 hash、尺寸、MIME、大小和 candidate trial 开关，再将 bytes 只交给当前会话内存中的共同 `VerificationResult`。
4. **Meta-Agent 纵向链路**：Registry 同时读取 verified BeautifyPic baseline 与 Web candidate；Meta-Agent 可提出 Web 或 fallback，但不授权、不创建 ProviderRun、不发网络。
5. **E2 回归/看板**：新增 Web 多样本、异常、批量失败隔离 harness、JSON/HTML 报告和 page 7 回归看板；8 个离线样本全部通过，覆盖输入哈希错位和结果大小上限，坏样本不阻塞后续样本，报告不保存图片。

### 当前工程回执

```text
全量 pytest: 214 passed, 4 warnings
Ruff check/format: PASS
compileall: PASS
git diff --check: PASS
E1 handoff smoke: fixture_only=true, network_called=false, result_bytes_persisted=false
E2 regression: 8/8 passed, hard_safety_passed=true, batch_failure_isolation_passed=true
```

上面是工程/fixture 证据，不是视觉效果、用户满意度或 Provider 泛化 KPI。Web 真实成功回执
`web_receipt_effect_web_4d58ea15a0794370` 仍只证明一次浏览器处理；Web Card 继续 `candidate`。

### E3 前仍需完成

- 使用明确授权的多张不同角度/表情照片采集真实 Web 回执和脱敏 Trace；
- 补齐批量真实视觉结果、失败隔离和供应商图片出站/地区/留存/费用证据；
- 由产品负责人审核准入函数全部字段后，人工决定是否把 Card 从 `candidate` 改为 `verified`；
- 在 E3 前，正式主流程继续使用 verified BeautifyPic，RAG 继续 proposal-only。真实 Web 证据失败时保留失败回执并回退 baseline。

### 回滚点

移除 Web 试验入口、联合合同和 E2 harness 不影响 BeautifyPic 主链、ReferenceProfile、IntentFrame、RAG 或 8C 基线；历史 Web 失败/成功回执只保留脱敏事实，不通过回滚删除。

## 2026-09-02｜Web 纵向绑定与最新 QA 覆盖

在 B/E1/E2 实现后补充一条纵向回归：Meta-Agent 明确提出 `tencent_effect_web` 后，`diagnose_and_plan` 只能生成同一 provider/Card 的 Web `EditPlan`，且 proposal 仍 `execution_authorized=false`。同时修正 E2 报告：`hard_safety_passed` 只回答恶意/损坏样本是否全部被拒绝，`batch_failure_isolation_passed` 单独回答坏样本后是否仍处理后续样本；避免测试排列导致错误结论。

该段记录的是 RAG 候选前的历史回执：`.venv/bin/pytest -q`=`216 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check`、E1 handoff smoke 和 E2 regression 均通过。当前 E1/E2 仍为 fixture/合同层证据，Web Card 继续 `candidate`，E3 尚需真实多样本视觉、供应商条款/区域/费用和负责人批准。RAG 候选与 V5 过程后的最新全量 QA 见下方当前段，为 `217 passed, 4 warnings`。

## 2026-09-02｜E2 回归覆盖补齐

复跑时发现原 6 个样例没有覆盖“输入哈希错位”和“结果大小上限”，且批量隔离字段容易被样例顺序误读。本轮一次只补这两个异常样例，并把一个有效失败回执放在拒绝样例之后，确保套件实际验证“坏样例不阻塞后续样例”。最终 8/8 通过：1 个成功、1 个供应商失败、6 个拒绝（请求/输入/输出哈希、尺寸、MIME、大小），`hard_safety_passed=true`、`batch_failure_isolation_passed=true`，结果 payload 不落盘。该修复只加强测试覆盖和指标口径，不放宽 Web Card 的 candidate 边界。

## 2026-09-02｜RAG 深度优化候选与 V5 过程门（当前）

### 本轮完成

1. 将 `RAG_DEEP_OPTIMIZATION_PROMPT.md` 补成可直接执行的 v0.2 任务指令，明确冻结 baseline、独立过程监督、单变量候选、Goodhart 防护、V5 答案隔离和产品化边界。
2. 完成 operation coverage candidate：修改 `rag_p0b.py` 的候选池与 Trace、`rag_process_supervisor.py` 的运行参数、`rag_policy_coverage_candidate.py` 的开发/回归轨道和 `rag_candidate_diagnostics.py` 的默认轨道；不改变 active baseline。
3. 重新生成候选报告、逐题诊断和 page 5 可视化数据；开发集候选 28/28，公开回归 52/52，hard-safety 均 PASS，候选 promotion 状态为 `not_promoted_proposal_only`。
4. 创建并执行 V5 answerless Holdout：60 题、60 条完整检索 Trace、60 条 Prediction，过程门 PASS；私有答案键在工作区外，质量评分脚本在未获授权时会拒绝读取。

### 实际回执

```text
pytest -q: 217 passed, 4 warnings
ruff check: PASS
ruff format --check: PASS (235 files)
compileall: PASS
git diff --check: PASS
policy coverage candidate: changed=26, regression_changed=49, promotion=not_promoted_proposal_only
candidate diagnostics: candidate_improved=16, candidate_neutral_or_regressed=1, no_candidate_change=63
V5 process audit: 60/60, process_gate=PASS, quality_scoring_gate=READY_AFTER_SEPARATE_GOLD_JOIN
```

### 尚未完成

V5 质量 Gold join 尚未运行（这是本段当时的交接状态）；负责人现已审核并授权一次聚合，当前质量结果见本文件 2026-09-03 段。候选不能因过程门通过而 promotion。新增 Provider、真实用户效果、RAG 线上自动发布和产品化结论仍不在本轮范围内。

### 本轮追加：V3/V4 双轨 Gold 连接

已按公平过程门把已审核、工作区外保管的 V3/V4 答案键与封存无答案运行包各连接一次。连接器只在内存按哈希对齐并输出 `reports/rag_fair_gold_join_v2.json/.html` 聚合；V3/V4 真实检索 Recall@5=`34.72%`/`41.32%`、Evidence relation=`16.67%`/`24.65%`，hard-safety 均 PASS，质量仍未通过。该连接不回写旧快照、不改变 active baseline，不消费 V5 答案。

同步后的全量 QA：`217 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check`、候选报告、候选诊断、V5 answerless runner 和 V5 过程审计均通过。该段是 Gold join 前的历史回执，当前质量与下一步见 2026-09-03 段。

## 2026-09-03｜V5 Gold join、失败模式与当前交接

负责人审核通过并授权 Gold join 后，使用封存的 V5 answerless 运行只做一次聚合评分。V5 质量结果为：
Route=`16.67%`、Evidence exact=`1.67%`、Evidence relation=`26.39%`、Recall@5=`73.89%`、MRR=`90.33%`、
nDCG@5=`75.36%`、hard-safety=`PASS`、project Gate=`FAIL`。过程审计仍为 60/60 完整 Trace、治理干净；
这两个 Gate 分开记录。

聚合失败分析见 `reports/rag_v5_failure_analysis_v1.json/.html`：路由不一致 50/60、证据集合不一致
59/60、关系不一致 54/60，前五条完全 miss 2/60；33 题没有可靠投影，20 题在已有投影后仍回退
BASELINE。根因已转成“显式意图→路由、按操作分配证据、关系规则化”的公开候选 SOP。V5 快照封存，
不用于逐题调参；RAG 仍 `proposal-only`，active baseline、权限和图片 Provider 不变。

本轮新增诊断模块、V5 聚合看板入口及测试；代码/文档同步后的全量 QA 已重新执行：`220 passed, 4 warnings`，
Ruff check、format、compileall 与 `git diff --check` 均通过。4 条 warning 仍是既有 Pillow 弃用提示；不沿用上一轮
`217 passed` 快照。

## 2026-09-02｜Getty × Thread 精细化视觉 Track 1（无应用代码变更）

### 本轮目标

产品负责人要求把视觉要求从“方向说明”推进到设计师可以直接执行的视觉稿级规范：抽象用户提供的三栏 Agent 截图的排版关系，吸收 Getty `Tracing Art` 的路径叙事、编辑式留白和混合媒介语法，保留 Party Rock 原始 token 与苹方，不复制任何品牌、网站资产或真实人像。

### 已完成

- 新增 `docs/UI_VISUAL_DESIGN_SPEC_DETAILED.md`（`VISUAL-DESIGN-SPEC-v0.1`）：包含三栏网格、模块/组件尺寸、精确中文文案、图标族、线条/圆角/阴影、E01/E02 排版、Image 2 素材方向、动效时间线、reduced-motion、响应式、性能、可访问性、Contract safety 和 R0→R6 Track；它是视觉稿级候选规范，不重写执行版 PRD 的业务合同。
- 新增 `design-system/portrait-consistency-agent/pages/align-entry.md` 与 `pages/align-session.md`，把 ui-ux-pro-max 的通用建议收敛到 Party Rock + 苹方；明确通用 Master 中自动生成的紫色/粉色 token、Space Grotesk/DM Sans 与本产品冻结输入不相容，不能直接套用。
- 使用 Image 2 生成并人工检查三张无人物环境素材：`orbit-paper.png`、`folded-window.png`、`ink-garden.png`；每张有完整 prompt sidecar，尺寸均为 `1586×992`，仅作首页氛围/关系隐喻，不是照片或结果图。
- 新增 `design/visual-tracks/getty-thread-party-rock/visual-review.html`：可切换 E01/E02、三张环境素材与暂停动效；产品壳为 `236px` 黑色左导航 + 米白中央舞台 + `352px` 米白 Agent 线程，E02 的授权、结果和反馈仍留在同一线程。
- 新增 `figma-import/e01-entry.svg` 与 `e02-session.svg`，分为 `nav/context/stage/thread/trajectory/composer/art` 语义图层，并导出 `renders/e01-entry.png`、`renders/e02-session.png` 作为 1440×900 检查帧。SVG 可导入 Figma 后继续编辑，但没有声称生成原生云端 `.fig`。
- 将 Track 1 链接同步到 `docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`、`docs/前端与交互设计需求文档.md`、`PRODUCT.md`、`README.md`、`docs/PROJECT_CONTEXT.md` 和 `AGENTS.md`；不改变 Streamlit、Provider、权限、结果保留、Trace、RAG 或隐私边界。

### 视觉/静态回执

- `xmllint --noout`：2/2 SVG 通过；`rsvg-convert`：2/2 生成 1440×900 渲染帧并完成图像检查。
- 浏览器本地 1440×900：E01/E02 均可加载、三栏关系和中文文案可读；E02 授权按钮可在原型中完成一次状态展示；控制台错误为 0。375×812 也完成基础响应式检查，线程按移动端规则隐藏并保留中央任务路径。
- HTML 内联脚本语法、`git diff --check` 通过；页面使用显式 label/aria、键盘 Enter/Shift+Enter、可见 focus、`prefers-reduced-motion` 和暂停动效。
- 尚未运行 Impeccable Critical/Audit、WCAG 2.2 AA 全量审查、Streamlit 映射或真实照片 UI 走查；这些是下一道 Gate，不能用本轮候选资产替代。

### 当前边界与下一步

Track 1 是高保真视觉候选，不是正式实现。产品负责人需先确认是否沿用这套 Getty × Thread 结构、哪一张环境素材作为默认；随后才进入 Impeccable Critical/Audit、浏览器/WCAG Gate，再由 Frontend 按现有合同映射到 Streamlit。任何改变冻结 token、授权、Provider、保存期、结果或 Trace 的建议必须另立变更请求。

### Track 1 收尾复核补充

- Impeccable `detect.mjs --json` 已执行；由于本机缺少 `htmlparser2/css-select/css-tree/domutils`，结果按 skill 标记为 **DEGRADED regex**，不能替代完整计算样式与对比度检查。唯一提示为事实块的彩色侧边条；已改为带圆角的细紫色边框，并用静态扫描确认不再存在厚侧边条、渐变、玻璃拟态或 emoji。
- 三张 Image 2 PNG 已将完整生成 prompt 嵌入 `impeccable:prompt`；重新扫描结果为 `3 raster, 0 missing`。四张浏览器证据帧已保存到 `.impeccable/review/`：`desktop-e01.png`、`desktop-e02.png`（1440×900）和 `mobile-e01.png`、`mobile-e02.png`（390×844），并确认文件为有效 PNG、非空且与文件名画面一致。
- 这次复核仍是候选资产级证据；未把 degraded detector、静态 SVG、浏览器预览或环境素材误写成 WCAG 2.2 AA、真实照片效果、Provider 效果、用户满意度或 Streamlit 已实现。
- 新增根目录 `DESIGN.md` 作为下一次 Frontend/Impeccable 的视觉入口，只记录视觉优先级、已确认 token/字体、当前 Track 和未冻结项；不复制或改写产品合同。

## 2026-09-03｜E3 真实多样本 Web 试验与 Demo 收尾

### 本轮目标

负责人批准启动 E3，并提供四张真实 JPEG。目标是把“网页上传一张图→浏览器 SDK 处理→结果可展示→回执可追溯”推进到可录制 Demo，同时不把 SDK 调用成功夸写成视觉一致性或 Provider promotion。

### 已完成

- 增加 `services/tencent_effect_web_e3.py` 的 `E3LiveReceipt` 和 `E3EvidenceReport`：对手工回执做安全字段校验，按样本 ID/输入 SHA-256 关联预检，检测重复样本/重复 receipt，输出 promotion blocker 和下一步；报告不接受 raw data URL、图片 bytes 或本地路径。
- 新增 `scripts/build_effect_web_e3_evidence.py`，把 E3 预检、真实回执、离线合同回归和正式准入证据汇总成 JSON/HTML；新增 `pages/8_腾讯特效Web_E3证据看板.py`，以只读脱敏方式展示真实回执和未闭合 Gate。
- 记录四次真实浏览器试验：`e3_reference_001` 与 `e3_target_001..003` 均 `succeeded`，成功率 `4/4`；四个输入哈希均与预检一致；结果交接标记 `4/4`；离线 E2 合同回归与批量失败隔离均通过。
- 更新 `tencent_effect_web.json` 的 E3 evidence，保留 Card=`candidate`；新增 [E3 收尾与可录制 Demo Prompt](E3_FINALIZATION_EXECUTION_PROMPT.md)。

### 真实 E3 结论

```text
真实 Web 回执：4/4 succeeded
输入哈希关联：PASS
结果交接标记：4/4
离线合同/批量隔离：PASS
视觉效果泛化：NOT ESTABLISHED
Card promotion：CANDIDATE
```

### 当前未完成/必须保持诚实的边界

- 手工汇总的四条回执没有完整抄录 `request_ref`，所以报告保留 `request_ref_not_recorded_for_every_manual_receipt`，不通过字段完整性掩盖证据缺口；
- 结果目前在浏览器会话可展示，但四张真实输出尚未全部完成共同 Python `VerificationResult` 的几何复测；
- 供应商图片出站/留存、地区和费用/预算证据仍未闭合；视觉泛化需要盲化前后复核或可复测的几何指标；产品负责人尚未作最终 candidate→verified 批准；
- page 6/page 8 是 Web 候选试验与证据看板，不等于主应用的 IMS/CompareFace/Profile/8A/8B/8C 全流程已切换到 Web；正式主流程仍以已审核 Tencent baseline 为准。

### 本轮验证

- `tests/test_tencent_effect_web_e3.py`：`6 passed`；覆盖预检、真实回执关联、hash mismatch、重复样本和 raw payload 拦截；
- E3 证据生成：`reports/effect_web_e3_evidence_v1.json/.html`；
- E3 预检：5 个样本（4 个真实 JPEG + 1 个透明通道异常 PNG），2 eligible、2 warning、1 rejected，失败后仍继续处理；
- 代码质量：E3 专项 Ruff check/format 通过；全量回归将在本节文档同步后重新执行并以最新数字为准。

### 下一道 Gate

当前不再有可安全自动推断的产品结论。下一步是完成真实结果的共同 VerificationResult/视觉复核以及供应商条款证据；证据齐全后才进入产品负责人对 Web Card promotion 的单独决策。网页 Demo 本身已经具备录制路径，但视频文案必须称“真实 Web 候选试验/原型”，不能称“正式上线或一致性已证明”。

### 2026-09-03 收口复核（最新）

E3 预检、证据汇总、Web 合同回归和 handoff smoke 已在文档同步后重新运行。最新可复核事实：预检 5 个样本（2 eligible、2 warning、1 rejected）；真实浏览器回执 4/4 成功，输入哈希 4/4 匹配，结果交接标记 4/4；离线 Web 回归 8/8，批量失败隔离通过。全量工程 QA 为 `.venv/bin/pytest -q`=`226 passed, 4 warnings`；Ruff check、format、compileall 和 `git diff --check` 通过。4 条 warning 是既有 Pillow 弃用提示。

本轮没有把 request_ref 缺失、视觉效果泛化、共同 VerificationResult 的真实图片复测、供应商地区/费用/留存或负责人 promotion 伪装成完成。Web Card 仍 `candidate`，RAG 仍 `proposal-only`，正式主流程仍为已验证的 BeautifyPic。page 6 已具备“上传→真实 Web 结果展示”的录制路径，page 8 提供脱敏 E3 证据看板；下一道真实决策门是补证后是否批准 Web Card promotion。
