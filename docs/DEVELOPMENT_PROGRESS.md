# 开发进展｜母版人像一致性 Agent

> 这份文档是项目的运行记录。每完成一个检查点，必须更新“完成内容、验证证据、未做事项、待决策项和下一步”。

## 总目标

在 2026-09-04 前完成可运行 Demo、可录制演示和可追问证据包；核心闭环为“母版 → 澄清 → 诊断 → 计划 → 确认 → 腾讯 API → 复测 → STOP/REPLAN”。

## 检查点总览

| 检查点 | 内容 | 状态 | 通过标准 |
|---|---|---|---|
| 1 | 项目骨架、Git、进展/决策记录 | 已完成 | 树结构清晰，Git 可追踪，文档说明上下文与待决策项 |
| 2 | 本地 Python 环境与开发命令 | 已完成 | 可创建隔离环境、同步依赖、运行基础检查 |
| 3 | 六个数据合同与合同测试 | 已完成 | 合法数据可序列化，非法数据被拒绝 |
| 4 | 腾讯能力卡、API Adapter、smoke 脚本 | 已实现；live Gate 待权限 | 无密钥时安全失败；有密钥时可保存 RequestId/结果/错误 |
| 5 | 最小 Streamlit 外壳、SQLite/JSONL trace | 下一步 | 从界面创建 session，并能追溯 IntentFrame 与 ProviderRun |
| 6 | MediaPipe 质量门和 Profile v0 | 未开始 | 单张有效/无效输入有可读结果 |
| 7 | LLM 意图澄清与 fallback | 未开始 | IntentFrame 可被解析、校验、回退 |
| 8 | 端到端单张闭环与 smoke cases | 未开始 | Happy Path + 两条失败路径可重复演示 |

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
- `ProviderRun` 只保存 hash/reference，而不保存图片内容；
- V0 默认最多 3 轮、每轮最多 3 个参数。

### 需要保留给你的未来决策

- 哪些部位最终允许加入 Profile（当前合同仅保留通用枚举）；
- 最大照片保留时长与未来公网部署同意文案；
- 未来是否允许把用户的长期偏好保存为 Memory。

### 已完成

- 2026-08-26：在 `core/contracts.py` 建立六个版本化 Pydantic 合同；
- 2026-08-26：增加 `TencentBeautifyParams` 与 `FeatureDelta` 两个子合同，明确用户层 delta 与 API 绝对值的分工；
- 2026-08-26：建立合同说明文档，列明每个合同的产生者、消费者和禁止保存的数据；
- 2026-08-26：增加 6 个合同测试，覆盖合法序列化和关键非法输入。

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

## 检查点 4｜腾讯能力卡、API Adapter、smoke 脚本（离线实现完成；live Gate 待权限）

### 本检查点目标

建立真实 API 的离线可测试适配层：能力卡说明“能做什么、范围是多少、来源和版本是什么”；Adapter 保证密钥只从 `.env` 读取；smoke 脚本能在无密钥时安全报出下一步，在有密钥时记录真实的 `RequestId`、结果引用、耗时和错误。

### 本检查点不做

- 不要求你现在提供密钥；
- 不把 fixture 或本地假图写成“真实腾讯调用”；
- 不实现 SDK 细项（唇厚、眼距、鼻翼）；
- 不在脚本中嵌入、打印或上传任何秘密。

### 将保留给你的决策

- `D-USER-001`：何时提供自己的腾讯云账号/密钥、预算上限和区域；
- 如果你暂时不提供密钥：我会完成 Adapter 的结构、错误边界和 fixture 测试，但进展文档会明确标为“未完成 live API Gate”。

### 已完成

- 2026-08-26：根据腾讯官方 `BeautifyPic`、API 概览和 Python SDK 文档建立版本化 Provider Card；
- 2026-08-26：安装并验证产品级 Python SDK `tencentcloud-sdk-python-fmu==3.1.82`；
- 2026-08-26：实现只从本地 `.env` 读取凭据的 Adapter；四个 V0 参数永远显式发送；
- 2026-08-26：实现 smoke 脚本。默认运行不读取图片、不联网；`--allow-live` 但无密钥时安全退出并明确说明原因；
- 2026-08-26：写入 API Gate 文档，说明官方来源、限制、真实运行命令和不应夸写的边界。

### 验证证据

- `make test`：`11 passed`；
- `make lint`：`All checks passed!`；
- `uv run ruff format --check .`：全部格式正确；
- 默认 smoke：返回 `network_called=false`，未读取图片或调用网络；
- `--allow-live` 且无密钥：以退出码 `2` 安全返回 `network_called=false`；
- SDK 导入验证：`FmuClient:BeautifyPicRequest`。

### 明确未完成 / 不可夸写

- 未提供或使用腾讯账号、SecretId、SecretKey；
- 未上传任何图片到腾讯；
- 未获得真实 `RequestId`、结果图片或真实调用耗时；
- 未完成 live API Gate。

## 当前检查点：5｜最小 Streamlit 外壳、SQLite/JSONL trace

### 本检查点目标

建立不做真实修图的本地任务外壳：用户能创建一个匿名会话、上传两张仅本地预览的图片、写入固定模板 `IntentFrame`，并把 session/intent/事件写入 SQLite 与 JSONL。页面必须明确标识“尚未调用腾讯 API、尚未做视觉评分”。

### 本检查点不做

- 不处理或保存真实图片到数据库；
- 不接 MediaPipe、不计算一致性指数；
- 不调用腾讯 API 或 LLM；
- 不启动公网部署。
