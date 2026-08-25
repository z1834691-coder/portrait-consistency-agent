# 本地开发环境

## 已冻结的本地选择

- Python：3.10（由 `uv` 管理）；
- 依赖：`pyproject.toml` + `uv.lock`；
- 服务：默认只监听 `127.0.0.1:8501`，不暴露到公网；
- 密钥：只放在忽略的 `.env`，本仓库不提供或保存任何真实凭据；
- 数据：本地 SQLite 与 JSONL trace 的路径会在后续检查点启用。

## 初始化

```bash
cd portrait-consistency-agent
uv sync --all-groups
cp .env.example .env
make check-env
```

复制 `.env.example` 只会创建空的本地配置；在腾讯 API Gate 前，`TENCENT_SECRET_ID` 和 `TENCENT_SECRET_KEY` 必须仍为空。

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
- 不启动公网服务器、不配置域名、不接入对象存储；
- 不调用任何腾讯、LLM 或其他外部 API。
