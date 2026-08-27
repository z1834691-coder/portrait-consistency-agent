# 本地开发环境

## 已冻结的本地选择

- Python：3.10（由 `uv` 管理）；
- 依赖：`pyproject.toml` + `uv.lock`；当前增加 `numpy`、`opencv-python-headless`（质量/几何基线）和腾讯 IAI/IMS SDK（主体/内容安全 Adapter）；
- 本地服务：默认只监听 `127.0.0.1:8501`；Demo 后续计划部署到可分享 URL 的 Streamlit 平台，但只允许受邀测试者，不直接开放公网；`.streamlit/config.toml` 关闭匿名使用统计，并启用 CORS/XSRF 默认保护；
- 密钥：只放在忽略的 `.env`，本仓库不提供或保存任何真实凭据；
- 数据：本地 SQLite 与 JSONL trace 已启用；原图不进入数据库或 trace。

## 初始化

```bash
cd portrait-consistency-agent
uv sync --all-groups
cp .env.example .env
make check-env
```

复制 `.env.example` 会创建空的本地配置；本地真实腾讯调用时，凭据只填写在本机 `.env`；部署时只填写在平台 Secrets，不发送到聊天、截图或 Git。当前腾讯 `BeautifyPic` live Gate 已成功一次。

## 常用命令

```bash
make test
make lint
make format
make check-env
```

`make run` / `./start.sh` 在 Streamlit 壳完成后才运行；默认地址固定为 `127.0.0.1:8501`，不等同于公网部署。

## 不做的事情

- 不把 `.env`、照片、数据库、trace 或输出图片提交到 Git；
- 不自动删除任何本地照片或目录；
- 当前不启动开放公网服务器、不配置自有域名、不接入对象存储；受邀 Streamlit 部署属于后续单独部署 Gate；
- 质量门为本地 OpenCV/Pillow 服务；CompareFace、ImageModeration 和 BeautifyPic 只有显式 `--allow-live` smoke/后续 UI 确认才调用；LLM、状态机和公网服务尚未接入。
