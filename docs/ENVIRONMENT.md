# 本地开发环境

## 已冻结的本地选择

- Python：3.10（由 `uv` 管理）；
- 依赖：`pyproject.toml` + `uv.lock`；当前增加 `numpy`、`opencv-python-headless`（质量/几何基线）、腾讯 IAI/IMS SDK（主体/内容安全 Adapter）。RAG P0-B 的 `torch` + `transformers` 已移为可选 `rag-local` extra：缺少它们或模型权重时会退回 P0-A，不阻塞轻量 Streamlit 部署；8A 规划器仍使用现有 Pydantic/本地标准库，不让 LLM 直接生成视觉数值；
- 本地服务：`make run` 仍显式监听 `127.0.0.1:8501`；部署包可由 Community Cloud 从 `main/app.py` 构建，但默认保持 Private/受邀测试。Cloud 容器在美国且磁盘不保证持久化，真实照片/跨境/长期数据不得在未确认前启用；`.streamlit/config.toml` 关闭本地匿名使用统计，并启用 CORS/XSRF 默认保护；
- 密钥：本机只放在忽略的 `.env`，Cloud 只放在对应 App 的根级 Secrets；本仓库不提供或保存任何真实凭据。Cloud ImageModeration 失败时，页面和脱敏 Trace 只显示 `error_code`/`provider_request_id`，不显示原始 SDK 错误全文；
- 数据：本地运行账本 SQLite/JSONL trace 已启用；RAG 权威知识另用 `storage/knowledge.sqlite3` 保存审核知识、FTS 索引与 P0-C advisory/bad-case 脱敏投影，P0-B 的 `storage/knowledge_vectors.sqlite3` 只保存可由权威知识重建的向量与 hash；本地模型权重位于 Git 忽略的 `storage/model_cache/`。原图不进入任何数据库、向量索引或 trace。

## 初始化

```bash
cd portrait-consistency-agent
uv sync --all-groups
cp .env.example .env
make check-env
```

需要本地语义模型时再执行 `uv sync --all-groups --extra rag-local`；正常页面不下载模型。

复制 `.env.example` 会创建空的本地配置；本地真实腾讯调用时，凭据只填写在本机 `.env`；部署时只填写在平台 Secrets，不发送到聊天、截图或 Git。当前腾讯 `BeautifyPic` live Gate 已成功一次。

DeepSeek 的 Key 也采用同一规则：从你自己的密码管理器**直接粘贴**到项目根目录的 `.env`，只填写 `DEEPSEEK_API_KEY=...`，不需要、也不要把它发送给 Codex。检查点 7 已读取 `LLM_PROVIDER`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`LLM_TIMEOUT_SECONDS` 和 `LLM_MAX_OUTPUT_TOKENS`；2026-08-27 已以固定无个人信息文本完成一次真实 smoke，返回合法 Schema；默认 smoke 仍不联网，以下命令只在密钥轮换或重新部署后才需要：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_deepseek_intent.py --allow-live
```

## 常用命令

```bash
make test
make lint
make format
make check-env
```

`make run` / `./start.sh` 在 Streamlit 壳完成后才运行；默认地址固定为 `127.0.0.1:8501`，不等同于公网部署。Community Cloud 的入口、Secrets、受邀名单和数据出境边界见 [Streamlit 部署说明](STREAMLIT_DEPLOYMENT.md)。

## 不做的事情

- 不把 `.env`、照片、数据库、trace 或输出图片提交到 Git；
- 不自动删除任何本地照片或目录；
- 当前不启动开放公网服务器、不配置自有域名、不接入对象存储；受邀 Streamlit 部署属于后续单独部署 Gate；
- 质量门为本地 OpenCV/Pillow 服务；CompareFace、ImageModeration 和 BeautifyPic 只有显式 `--allow-live` smoke 或首轮页面明确 UI 确认才调用；DeepSeek 文本 Adapter 已接入并通过一次真实 live receipt，缺 Key/失败均回退本地模板。8A 差异诊断/计划草案已在页面接入；8B 已接入确认期限、Gate/hash 校验、一次 BeautifyPic 调用和脱敏 ProviderRun，结果仅会话内存，不自动重试；8C-1/8C-2 已接入会话内修后观察、策略提议、子计划/父子回执血缘、首次 scope 内自动续跑/自动复测与最终反馈硬停止。RAG P0-A/P0-B/P0-C 已实现本地权威知识、FTS、dense、RRF、rerank 与受限 evidence 回接；正常模式只读本地固定模型缓存，缺权重时安全退回 P0-A 稀疏检索，不读照片/原话、不调用 LLM/API。P0-C `execution_authorized=false`，所以不能带来新的图片调用；本机 RAG Dashboard 只读取脱敏账本聚合。external/hybrid 复测、LLM 自由策略、跨会话状态恢复、自动 worker 和新 Provider 均待后续 Gate。IMS 服务开通后已分别得到真实 `Block` 和新授权照片的真实 `Pass`，只证明两条样例路由，不代表完整内容安全覆盖。

RAG P0 的默认不联网验证命令：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_p0a.py
# P0-B 正常运行只读取已缓存的本地模型；不允许下载、不读照片、不调用外部服务
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_p0b.py
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_rag_advisory.py
```

只有开发者首次准备本机模型缓存时，才可以显式执行 `scripts/smoke_rag_p0b.py --allow-model-download`；这一步会下载公开模型权重，不应由页面、受邀测试用户或正常产品任务触发。

## 2026-08-30 环境状态同步

Gold Set v2 评测器和两个候选 Provider shell 已加入本地环境，但它们默认都不联网：

- `scripts/evaluate_rag_gold_v2.py` 只读 answerless public/holdout 输入和独立 dev/challenge annotations；holdout 模式只接收 `case_id/query`，不加载答案键；报告可输出到 `reports/` 的 JSON/Markdown/HTML。
- `services/volc_beauty.py` 与 `services/tencent_effect.py` 只做候选请求元数据、权限/预算 preflight 和 fail-closed smoke；不导入厂商 SDK、不读取或发送图片、不读取密钥。两条 Card 均保持 `candidate`，不能被 RAG 或 LLM 直接放行。
- 当前环境交叉校验：`pytest 129 passed, 4 warnings`；Ruff、compileall、`git diff --check` 通过。四条 warning 均为既有 Pillow 弃用警告。

## 2026-08-30 评测治理环境同步

评测器已升级为 `rag-gold-eval-v0.2`：可生成固定/覆盖式/返回式 Precision 与 Gold 条数分层；`rag-safety-events-v0.1` 提供确定性事件 ID 和未知标签人工复核；v3 Holdout 仅有 answerless 模板，答案不进入本工作区。public/failure report 已重跑，所有默认评测仍不联网、不读照片/向量/密钥、不调用 LLM/Provider。

## 2026-09-01 当前环境状态覆盖

v3 Holdout 已由产品负责人完成审核，并已在工作区外完成一次正式私有聚合盲测；工作区只保留代码和历史/公开评测材料，答案键、逐题审核材料和盲测聚合仍在所有者受限目录。盲测未读答案键、照片、向量、LLM、Provider 或网络；质量 Gate=`FAIL`、hard-safety=`PASS`。不要依据旧快照中“v3 待审核/模板为空”的描述判断当前状态。

Streamlit Cloud Private 页面已打开作为第一位用户入口。当前尚未由 Codex 代上传真实照片或触发新的腾讯图片调用；Cloud 页面上的真实数据采集必须由产品负责人亲自操作并重新确认美国区域/受邀测试边界。8C 多轮仍是“代码/fixture 已验证、真实 UI 回执待触发”，本地命令和轻量 Cloud 包均不自动下载模型或联网。

## 2026-09-01｜腾讯特效 Web 试验环境

新增 page 6 和 `TencentEffectWebAdapter` 使用 Streamlit Components v2 在浏览器中加载腾讯 Web SDK。它不是 Python REST 调用：图片/输出图只在浏览器会话，Python 仅接收脱敏 Browser Receipt。需要的三项根级配置为：

```text
TENCENT_EFFECT_APP_ID
TENCENT_EFFECT_LICENSE_KEY
TENCENT_EFFECT_LICENSE_TOKEN
```

本机放 `.env`，Cloud 放 App Settings → Secrets；Token 只在 Python 侧生成短时签名，不能出现在页面、Trace、仓库或聊天。`scripts/smoke_tencent_effect_web.py` 是离线 smoke，明确输出 `network_called=false`；真实 smoke 必须在绑定了腾讯测试 License 的 Cloud 域名 page 6 中点击组件按钮后取得浏览器回执。当前 Web Card 仍为 `candidate`，不能因环境变量齐全而自动放行。
## 2026-09-01｜失败驱动 RAG Loop v2 环境回执

失败驱动运行器使用项目 `.venv` 的 Python 环境，在临时 SQLite/FTS/dense 索引中完成 V0→V4；它不联网、不调用 LLM/Provider、不读取照片、向量或 hidden answer。当前报告为 `reports/rag_failure_driven_loop_v1.json/.html`，并在 page 5 只读展示；V2 查询编译候选只属于 proposal，不能替换 active baseline。全量 QA 当前为 `178 passed, 4 warnings`，4 条 warning 仍是 Pillow 弃用提示。

## 2026-09-01｜腾讯特效 Web Cloud 运行状态覆盖

Cloud 已从最新提交完成重建，page 6 可以正常加载；旧进程缓存造成的导入错误已通过 Reboot 消除。
当前 Cloud Settings → Secrets 尚未配置 `TENCENT_EFFECT_APP_ID`、
`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`，所以本轮没有加载 Web SDK、
没有图片出站、没有 Browser Receipt。补齐三项配置后才允许用官方示例图运行一次；Card 在此之前
继续 `candidate`，不能把部署成功写成 Provider live。

## 2026-09-02｜V3 validation 环境回执

产品负责人已将 V3 的后续用途明确为离线 validation。原始一次性 answerless 盲测快照仍在工作区外，派生验证包才包含题干与已审核 Gold；运行器不读取照片、向量、密钥，不联网，不调用 LLM 或图片 Provider。当前生成物是 `reports/rag_v3_validation_diagnostics_v1.json/.html`，每代 36 条完整 Trace，页面由 page 5 只读展示。

最终 G3 的 validation Route=100%、Evidence relation=97.22%、Recall@5=100%；G2 因 public regression 退化不采纳，G4/G5 无增益。全量 QA 需同时包含 validation runner、pytest、Ruff、format、compileall、diff check；该 validation 证据不改变 active baseline 或 `execution_authorized=false`，推广仍需独立 V4 Holdout。
