# 本地运行壳与 Trace

## 当前可运行内容

`app.py` 是一个只监听本机的 Streamlit 壳。它可以：

- 创建匿名本地 session；
- 在浏览器内存中预览两张上传图片；
- 保存一条明确标为 `template_fallback` 的 `IntentFrame`；
- 将 session、意图和事件写入 SQLite/JSONL；
- 在页面展示脱敏 trace。

## 当前刻意不做的内容

- 不把图片写入 SQLite、JSONL 或 Git；
- 不调用腾讯 API、LLM、MediaPipe 或其他外部服务；
- 不计算母版一致性、质量门、参数计划或修后复测；
- 不部署公网，不代表用户授权执行修图。

## 数据位置

| 数据 | 默认位置 | Git 状态 |
|---|---|---|
| SQLite session/intent/provider run audit/event | `storage/demo.sqlite3` | 忽略 |
| JSONL trace | `logs/events.jsonl` | 忽略 |
| 未来腾讯结果图 | `storage/results/` | 忽略 |

Trace 会红删密钥、确认 token、Base64 图片、原图 payload 和签名 URL。上传文件名、原始文本和图片内容不写入 trace。

## 启动与验证

```bash
make run
# 或
./start.sh
```

浏览器打开 `http://127.0.0.1:8501`。关闭终端即可停止本地服务；这不等同于删除本地 trace，删除/TTL 将在后续隐私检查点实现。

`.streamlit/config.toml` 将服务绑定到 `127.0.0.1`，关闭匿名使用统计，并保留 CORS/XSRF 保护；它不是公网部署配置。
