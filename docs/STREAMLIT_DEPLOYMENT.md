# Streamlit Community Cloud 部署说明

这份说明只解决“把当前可运行原型部署成受邀测试 URL”这一件事。它不把
Community Cloud 当成生产服务器，也不改变 RAG 只能提议、腾讯调用需要明确授权、
结果图只在会话内存和本地账本不是 Dataset 的产品边界。

## 当前部署包

- GitHub 仓库：[`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)（已创建、默认私有，`main` 已推送）；
- 分支：`main`；入口：根目录 `app.py`；
- 仓库包含可运行代码、审核过的 Provider Card、测试和产品文档；不包含 `.env`、真实照片、
  SQLite/JSONL、生成结果图、模型缓存、隐藏答案键和本机评测报告；
- `uv.lock` 是仓库唯一的 Python 环境声明。CPU BGE/Transformers 放在可选的
  `rag-local` extra；没有模型权重时，P0-B 会明确退回 P0-A 关键词检索，云端不会为打开页面下载大模型；
- `app.py` 启动时显式加入 `src/`，所以 Streamlit 直接执行入口文件时仍能找到项目包。

## 在 Community Cloud 创建应用

1. 打开 <https://share.streamlit.io/>，点击 **Create app**。
2. 选择仓库 `z1834691-coder/portrait-consistency-agent`、分支 `main`、入口文件 `app.py`。
3. 在 **Advanced settings** 选择 Python 3.10（与当前本地开发环境一致）；如果控制台只提供仍受支持的相邻版本，先选择 3.11 并观察构建日志。
4. 第一次部署建议保持 **Private**，只邀请已同意测试的邮箱；不要直接设置成可被全网搜索的 Public。
5. 部署成功后，使用页面生成的 `*.streamlit.app` URL；可在 App settings 中申请一个可用的自定义子域名。最终 URL 以控制台显示为准，不能在代码中预先保证某个 slug 一定可用。

Community Cloud 的构建会读取仓库的 `uv.lock`，并在仓库根目录执行 Streamlit。它的容器磁盘不是可靠的长期数据库：重启、休眠或重新部署可能丢失 `storage/` 和 `logs/`。因此受邀 Beta 阶段只把它当演示与短期测试入口，不在这里承诺半年主体锚点删除、运营长期留存或生产级审计。

## 2026-08-30｜腾讯 Web License 精确域名现场核验

当前 Cloud App 已由产品负责人创建，地址为：
`https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`。
对该地址发起只读 HTTP 探针得到 Streamlit 登录跳转（HTTP 303），说明应用存在且目前是 Private，不代表应用公开可访问。
该 URL 的纯主机名为 63 字节，低于腾讯表单提示的 128 字节上限。

腾讯 Web License 的 `Domain` 输入框要求**精准域名**，不是完整 URL。现场核验结果如下：

- 错误格式：`https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app/`；表单的“确定”按钮保持禁用；
- 正确格式：`portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`；表单按钮立即变为可用；
- 不要填写 `https://`、末尾 `/`、路径、查询参数、通配符或空格；小程序 Appid 留空；
- 当前控制台已预填项目名 `portrait-consistency-demo` 和上述纯主机名，但尚未点击“确定”提交测试 License。

腾讯官方资料说明 Web License 按固定域名绑定，且 Web 端测试 License 申请后有效 14 天、可续期一次至 28 天；Streamlit 官方资料说明 Community Cloud 应用可使用 6–63 字符自定义 `streamlit.app` 子域名。若纯主机名仍在提交阶段被服务端拒绝，问题就不是字节长度，而是供应商对第三方托管子域名/域名归属的服务端限制；此时不要购买正式套餐，先用自有域名反向代理或本机 `localhost` 做单独 License Spike，并重新核验 referer。

官方依据：[腾讯 Web 端 License 计费与精准域名说明](https://cloud.tencent.com/document/product/616/86942)、[腾讯 Web 测试 License 说明](https://cloud.tencent.com/document/product/616/80189)、[腾讯 Web License 常见问题](https://cloud.tencent.com/document/product/1143/45381)、[Streamlit 应用 URL 设置](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings)。

## Secrets 配置

Community Cloud 的根级 Secrets 会以环境变量形式提供给应用。只在 Streamlit 的 **Advanced settings → Secrets** 粘贴你自己的值，不要把真实值发给 Codex，也不要提交 `.streamlit/secrets.toml` 或 `.env`。

无外部调用的 UI/离线演示可以先不填任何 key。要在受邀、明确授权的测试中调用已有腾讯链路，再按需填写：

```toml
APP_ENV = "streamlit_beta"
TENCENT_SECRET_ID = "从密码管理器粘贴"
TENCENT_SECRET_KEY = "从密码管理器粘贴"
TENCENT_REGION = "ap-guangzhou"

# 仅在你明确同意把文字发送到 DeepSeek 时填写；图片、人脸向量和原图不会发送给它。
LLM_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = "从密码管理器粘贴"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
LLM_TIMEOUT_SECONDS = 20
LLM_MAX_OUTPUT_TOKENS = 900
```

不要填写 `VOLC_BEAUTY_CREDENTIAL_REF`：火山美颜仍是候选 Provider，未完成套餐、License、
隐私/区域、真实回执和 Gold 准入，应用不会调用它。

## 隐私与测试边界

Community Cloud 当前由 Streamlit 托管在美国基础设施。把真实照片上传到该 URL 之前，
必须重新确认你的数据出境/受邀测试范围；未确认时使用合成或明确授权的测试照片，且不要配置真实
腾讯/DeepSeek Secrets。受邀用户也要看到“本原型、图片只为本次测试、不要上传他人或未成年人照片”提示。

Streamlit URL 可用不代表以下能力已完成：持久化数据库、AES-GCM 主体锚点、跨会话恢复、多人隔离、
三轮真实视觉复测、生产级鉴权、自动删除 worker 或公网 SLA。

## 代码更新方式

后续修改只在本地项目完成测试后提交到 `main`；Community Cloud 会检测 GitHub 更新并重新构建。每次变更继续遵循项目六项同步检查：执行版 PRD、专项文档、`DECISION_LOG.md`、`DEVELOPMENT_PROGRESS.md`、合同/代码/测试、README 当前能力与不可夸写边界。
