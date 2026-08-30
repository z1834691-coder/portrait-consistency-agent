# 检查点 7｜DeepSeek 文本 IntentFrame Gate

> 状态：代码、页面入口、离线测试、默认不联网 smoke 和一次真实 DeepSeek 云端回执均已完成；检查点 8A 已在下游接入逐特征诊断与待确认计划草案；检查点 8B 已接入确认后单次编辑，8C-1/8C-2 已接入会话内修后观察、`VerificationResult`、自动有界续跑和反馈控件；完整外部/混合复测、生产级恢复和自由动态策略仍未实现。

## 这一模块到底解决什么

用户不必先填固定问卷，可以自然地说“这张更像母版一点，保留妆面，先给我建议”。本模块把这句话变成系统能继续处理的结构化 `IntentFrame`：用户想做什么、希望先给建议还是倾向直接执行、哪些部位可调整、哪些效果要保留，以及还缺哪一个真正影响下一步的问题。

它不是“看图模型”，也不是修图执行器。照片质量、同一人物、具体五官差异、参数数值、用户确认和腾讯 API 回执仍由各自的确定性模块负责。

## 输入、输出与边界

| 项目 | 实际内容 | 为什么这样做 |
|---|---|---|
| 页面短暂持有的输入 | 用户本轮自然语言、当前是否已有母版、目标照片数量和已冻结的默认约束 | 让模型只理解语言，不替视觉系统做事实判断 |
| 可离开本机的输入 | 经常见 PII 脱敏后的本轮文字；不含任何不透明 ID 的最小结构化上下文 | 避免把照片、向量、锚点、密钥或完整运行日志交给 LLM |
| 结构化输出 | `IntentFrame`、最多一个澄清问题、用户可读摘要、解析回执 | 前端和后续状态机都能稳定读取，而不是解析一段自由文字 |
| 永远不由 LLM 生成 | `intent_id`、`session_id`、轮次、文本 hash、模型/Prompt 版本、确认引用、工具回执和任何修图参数 | 防止模型伪造系统事实或越权执行 |
| 失败时输出 | 同一个 `IntentFrame` Schema 的本地关键词模板结果 | 没有密钥、用户不授权、网络、HTTP、JSON 或 Schema 失败时，产品仍可继续说明下一步 |

## 已冻结的产品规则如何落到代码

1. **是否能发给 DeepSeek**：页面必须由用户勾选“仅将本轮脱敏文字发送给 DeepSeek”且本机存在 `DEEPSEEK_API_KEY`。任一条件缺失，Adapter 根本不发网络请求。
2. **模型的职责**：只把用户语言转换成候选意图、一个澄清问题和简短说明；不读图、不看人脸向量、不算五官差异、不决定腾讯参数。
3. **执行倾向不等于执行授权**：用户说“直接帮我修”时，系统仍只生成 `PENDING` 的有界确认草案，不调用任何图片编辑工具。
4. **单一云 Provider**：当前只使用 DeepSeek；失败只回退本地模板，不把同一段文字自动转给 OpenRouter 或第二个云模型。
5. **Trace 可审计但不泄露内容**：保存解析路径、是否联网、模型/Prompt 版本、耗时、可取得 token、Schema 是否通过、fallback 原因和脱敏类别；不保存原话、模型原回答、隐藏思维链或 API Key。

这些规则的完整产品语义见 [PRODUCT_RULES.md](PRODUCT_RULES.md)，字段定义见 [CONTRACTS.md](CONTRACTS.md)，Prompt 规格见 [AGENT_PROMPTS.md](AGENT_PROMPTS.md)。

## 这次真实写进了什么

- `src/portrait_consistency_agent/agent/intent_adapter.py`：直接调用 DeepSeek `/chat/completions` 的文本 Adapter；请求固定 JSON Object、关闭 thinking、20 秒超时、900 token 上限。
- `app.py`：在上传母版和目标照后，提供“解析并保存本轮 IntentFrame”入口；无密钥或未勾选时清楚显示本地 fallback，不暗中联网。
- `scripts/smoke_deepseek_intent.py`：默认安全离线；只有显式传 `--allow-live` 才尝试真实云端调用。
- `tests/test_deepseek_intent.py`：9 条自动化案例，覆盖边界和失败路径。

## 已运行的 5 类验收案例

1. **没有本机密钥**：不发 HTTP 请求，返回 `template_fallback`。
2. **DeepSeek 返回合法 JSON**：先用 Pydantic 校验候选字段，再由系统补全 ID、确认作用域和版本字段。
3. **DeepSeek 返回非 JSON / Schema 不合法 / HTTP 429**：记录安全错误类别，回退到本地模板，不泄露供应商原始错误正文。
4. **用户说“直接修”**：仍停在待确认状态，不会因为一句话直接调腾讯图片 API。
5. **用户在文字中放电话、邮箱或注入式指令**：常见敏感标识先脱敏；模型无法写入系统字段或把自己变成工具调用者。

2026-08-27 本检查点的定向测试为 `9 passed`，当时全量回归为 `63 passed`；检查点 8A 时为 `69 passed`，8B 时为 `75 passed`，8C-1 时为 `81 passed`。8C-2 后的最新全量数字以执行版 PRD/开发进展中的实际命令输出为准。默认 smoke 输出 `offline_guarded` 与 `network_called=false`。同日的显式 live smoke 使用固定、无个人信息的文本，真实返回：`status=passed`、`parser_mode=llm`、`model_version=deepseek-v4-flash`、`schema_validated=true`、`latency_ms=2957`、`prompt_tokens=960`、`completion_tokens=511`、`total_tokens=1471`、`fallback_reason=null`。

## 真实云端 Gate 已闭合

代码和离线测试不能代替真实云端回执。2026-08-27，用户已在**自己的密码管理器和本机文件系统之间**配置 Key，项目已完成一次显式 live smoke；Key 没有进入聊天、截图、Markdown 或 Git。下面的配置方式保留给以后重新部署或轮换密钥时使用：

```text
DEEPSEEK_API_KEY=你的密钥
```

不要把密钥发到聊天、截图、Markdown 或 Git。配置完成后，由本项目运行：

```bash
UV_CACHE_DIR=/private/tmp/portrait_consistency_uv_cache uv run python scripts/smoke_deepseek_intent.py --allow-live
```

真实通过的最低证据是：输出 `parser_mode=llm`、`network_called=true`、`schema_validated=true`，并在本地 SQLite/JSONL 看到同一 session 的脱敏解析回执。本次已经满足该标准；后续若调用失败，脚本仍会保留安全失败类别并自动 fallback。

## 仍未实现，不能夸写

- 多轮澄清后的回填、取消和不满意状态迁移；
- 从照片计算逐特征差异或 EditPlan；
- 用户确认后的腾讯 BeautifyPic 执行；
- 8C-2 的自动重规划、三轮计划族、外部/混合复测和结果反馈；
- 5—10 条由产品负责人审计的中文 Gold Case。

因此，检查点 7 证明的是“受约束的文本意图理解 + 可审计降级”，而不是完整 Agent 已经能自主修图。
