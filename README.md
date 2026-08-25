# 母版人像一致性 Agent

当前阶段：`Foundation / Checkpoint 1`  
目标：在 2026-09-04 前完成一个真实可运行、可复测、可追溯的 Demo；它不是生产服务，也不承诺统一的“90 分”或修图效果。

产品闭环：

```text
母版确认 → Reference Profile → 目标照/照片组 → 意图澄清
→ 质量门与特征 → 编辑计划 → 用户确认 → 腾讯图片编辑 API
→ 修后复测 → STOP / REPLAN / RESHOOT / MANUAL_REVIEW
```

当前已冻结的工程边界：

- 母版一致性，而非身份识别或审美评分；
- V0 执行器为腾讯云 BeautifyPic；密钥仅保存在本机 `.env`；
- LLM 只解析自然语言意图、补齐约束、解释工具结果；不读原图、不打分、不猜参数、不自行授权执行；
- RAG V0 是可追溯的 Provider Card 检索；向量库和完整文档检索在提交后再做；
- 单进程 Python/Streamlit + SQLite 优先，暂不做生产部署。

开发状态、每一步验证结果和待你决策的事项见：[开发进展](docs/DEVELOPMENT_PROGRESS.md) 与 [决策日志](docs/DECISION_LOG.md)。

## 当前项目树

```text
portrait-consistency-agent/
├── app.py                         # 本机 Streamlit 壳；尚无视觉/API 执行
├── .streamlit/config.toml         # 仅绑定 127.0.0.1，关闭匿名统计
├── data/provider_cards/           # 可追溯 Tencent 能力卡（RAG P0）
├── docs/                          # 蓝图外的开发进展、决定、合同、运行与 API Gate 记录
├── scripts/                       # 环境检查与显式 opt-in 的腾讯 smoke 脚本
├── src/portrait_consistency_agent/
│   ├── core/                      # 合同与本地设置
│   ├── services/                  # Provider Card / 腾讯 API Adapter
│   └── storage/                   # SQLite + JSONL 脱敏 trace
├── storage/                       # 本地 DB / 未来结果图（Git 忽略）
├── logs/                          # 本地 JSONL trace（Git 忽略）
└── tests/                         # 当前 13 个基础/合同/存储/Provider 测试
```

## 本地命令

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
```

应用入口将在最小界面检查点完成后启用；不要把密钥、真实照片或运行日志提交到 Git。
