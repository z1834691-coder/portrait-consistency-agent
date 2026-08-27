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
| 5.7 | 合同 v0.2、六表存储与执行版 PRD | 已完成 | 29 个测试通过；文档、代码和本地 schema 对齐 |
| 6 | 几何/质量 CV + 独立主体匹配门 + Profile v0 | 已完成（CompareFace live 已验证；ImageModeration 单独待验证） | 单张有效/无效输入有可读结果，且不输出未经校准的指数 |
| 7 | LLM 意图澄清与 fallback | 准备中（待产品决策） | IntentFrame 可被解析、校验、回退 |
| 8 | 端到端单张闭环与 smoke cases | 未开始 | Happy Path + 两条失败路径可重复演示 |

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

## 检查点 6.3｜内容安全 Adapter（已实现；尚未 live 验证）

- 2026-08-27：增加 `services/tencent_safety.py`，接腾讯 IMS `ImageModeration` API `2020-12-29`，输入只在本次调用内存中转为 Base64；`BizType` 可由 `.env` 配置。
- `Pass` 映射为 `PASSED`；`Review/Block` 在 V0 都保守映射为 `BLOCKED`，防止未定义人工审核策略时放行高风险图片。
- 新增 `data/provider_cards/tencent_image_moderation.json` 和对应测试；未进行 live 调用，待确认 IMS 开通、BizType 与预算后再做一次显式 smoke。

## 检查点 6.4｜ReferenceProfile v0 与组合服务（已实现并验收）

- 2026-08-27：增加 `services/reference_profile.py`，将单脸观察转成归一化脸框/眼睛几何字段（脸宽高、占比、中心、边界余量、眼距、眼位和眼线斜率），保存提取器/规范化/合同版本；不保存原图、EXIF、肤色、妆面、身体、原始坐标数组或明文 embedding。
- 无主体锚点时生成 `GEOMETRY_ONLY` Profile；只有调用方传入单独同意、加密引用、到期时间等 `SubjectAnchorMetadata` 才生成 `ACTIVE` Profile。当前真实加密存储和半年 TTL worker 仍未实现。
- 增加 `services/checkpoint6.py`，组合质量门、内容安全 evidence、当前会话 CompareFace 和 Profile/SQLite 保存；它仍是确定性服务，不是 Agent/state machine。
- 新增 Profile/组合服务测试；当前总测试为 `51 passed`。Streamlit 已提供质量门、安全检查和 Profile 锁定入口；CompareFace 已完成真实 live 验证；真实 ImageModeration 尚未 live 验证。

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
- ImageModeration 尚未 live 验证，因此本检查点的“通过”限定为用户最初定义的质量门 + 当前会话同人比对 + ReferenceProfile v0；安全 Adapter 仍作为独立待验证项。

## 检查点 7｜LLM 意图澄清与 fallback（准备中，尚未写代码）

### 本步背景

检查点 6 已把“照片能否处理、是否为当前会话同一人物、母版如何保存”变成确定性结果。下一步让用户可以直接用自然语言表达目标，例如“只改脸型，尽量保留表情，先给我建议”，再把文本可靠地转成已校验的 `IntentFrame`；LLM 只负责理解、澄清和解释，不能替代质量门、参数规划器或权限状态机。

### 开工前待确认

- LLM 供应商/模型与本地或云端数据处理边界（当前 `D-USER-002` 仍待决定）；
- 澄清策略：每轮最多问几个问题、缺失信息的优先级，以及用户回答含糊时的 fallback 文案；
- 是否允许把脱敏的意图与用户反馈用于弱标签/合成案例，以及保留期限。

产品规则确认后，先实现 provider-neutral Adapter、结构化输出校验和离线模板 fallback，再接入真实 LLM；不会让 LLM 直接读取原图或调用腾讯 API。

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
- 结果图片已落盘：`storage/results/1e519f22-b119-41bb-9242-76798f7cab61.jpg`，JPEG `1600×2442`、约 `1.7MB`；`result_ref` 与本地文件一致。
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

## 后续检查点：6｜几何/质量 CV、独立主体匹配门与 Reference Profile v0

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
