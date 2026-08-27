# 本地运行壳与 Trace

## 当前可运行内容

`app.py` 是一个只监听本机的 Streamlit 壳。它可以：

- 创建匿名本地 session；
- 在浏览器内存中预览两张上传图片；
- 保存一条明确标为 `template_fallback` 的 `IntentFrame`；
- 将 session、六合同脱敏投影和事件写入 SQLite/JSONL；
- 在页面展示脱敏 trace。

## 当前刻意不做的内容

- 不把图片写入 SQLite、JSONL 或 Git；
- Streamlit 页面已接入检查点 6 的本地质量门，并提供需要用户明确勾选同意后才执行的 Tencent ImageModeration、CompareFace 和 Profile v0 按钮；BeautifyPic 真实调用已成功一次，CompareFace 已在 IAI 服务开通且 CAM 最小权限补齐后真实 smoke 成功一次；ImageModeration 尚未 live 验证；
- 页面当前仍不计算母版一致性总分、不生成 EditPlan、不做修后复测；LLM 意图澄清、完整状态机和批量模式尚未接入。质量门、Profile v0 和 CompareFace 可以在页面和 Python 服务层运行；ImageModeration 仍待真实验证；
- 页面只展示照片格式、尺寸、人脸数量、定性质量状态和失败原因；质量/可编辑性内部置信度、CompareFace 原始分和隐藏思维链不会展示；
- `AGENT_PROMPTS.md` 的职责边界已冻结但尚未接入 LLM；合同与模板 IntentFrame 已升级为 `v0.2`，页面仍没有 ReAct 编排、真实 EditPlan、自动多轮或 VerificationResult；
- 当前本地运行不部署公网；后续受邀 Streamlit URL 只作为小范围测试入口，不等于开放公网，也不代表用户自动授权执行修图。

## 数据位置

| 数据 | 默认位置 | Git 状态 |
|---|---|---|
| SQLite session/六合同脱敏投影/audit event | `storage/demo.sqlite3` | 忽略 |
| JSONL trace | `logs/events.jsonl` | 忽略 |
| 未来腾讯结果图 | `storage/results/` | 忽略 |

Trace 会红删密钥、确认引用、主体锚点、Base64 图片、原图/input artifact payload 和签名 URL。上传文件名、原始文本和图片内容不写入 trace。SQLite 迁移 `contract_v0_2_tables` 已创建六合同表；页面已能写入质量结果、Profile 和安全/同人事件的脱敏投影，完整修图执行链仍未接入。

## 启动与验证

```bash
make run
# 或
./start.sh
```

浏览器打开 `http://127.0.0.1:8501`。关闭终端即可停止本地服务；这不等同于删除本地 trace，删除/TTL 将在后续隐私检查点实现。

`.streamlit/config.toml` 将本地服务绑定到 `127.0.0.1`，关闭匿名使用统计，并保留 CORS/XSRF 保护；受邀 Streamlit 部署仍需额外配置访问控制、Secrets、删除策略和费用上限。
