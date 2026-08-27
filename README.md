# 母版人像一致性 Agent

当前阶段：`Contract v0.2 frozen / Checkpoint 6 quality + CompareFace + Profile validated / Checkpoint 7 next`
目标：在 2026-09-04 前完成一个真实可运行、可复测、可追溯的 Demo；它不展示未经校准的一致性指数，也不承诺统一的“90 分”或普适修图效果。

产品闭环：

```text
母版确认 → Reference Profile → 同一人物/质量门 → 目标照/照片组
→ 意图澄清 → 特征差异与编辑计划 → 用户确认 → 腾讯图片编辑 API
→ 修后复测 → 可接受/继续调整/重新上传/人工复核
```

当前已确认的工程边界：

- 母版一致性，而非身份识别或审美评分；
- V0 执行器为腾讯云 BeautifyPic，真实 live Gate 已成功一次；本地密钥放 `.env`，部署密钥放平台 Secrets；
- Provider Card 声明支持的参数原则上都可执行，但美白和磨皮默认关闭，需用户明确允许；
- 编排采用“Python 状态机控制权限与迁移 + 受限 ReAct 提议下一工具”；LLM 不读原图、不计算接受概率、不猜参数、不自行授权执行，也不向用户展示隐藏思维链；
- 母版保存归一化五官/脸型派生特征；经单独同意后，保存加密、可删除、受限访问的派生主体表示半年，过期后提醒重新上传或降级为几何特征对齐；
- Demo 先部署为受邀测试者可访问的 Streamlit 分享 URL，部署密钥放平台 Secrets，暂不开放公网；
- RAG V0 先以可追溯的 Provider Card 读取基线存在；向量库和完整文档检索在提交后再做；
- 单进程 Python/Streamlit + SQLite 优先，暂不做生产部署。
- 一次确认覆盖当前照片/批次、允许部位和当前可配置轮次的有界计划族；当前 Safety Policy 为最多 3 轮、连续 2 轮无改善提前停；
- 0.50/0.80 只用于 quality/editability 的最严格路由；subject match 独立判定；
- 多脸完整目标是选择、隔离、裁剪、回贴和复测，失败时要求用户先裁剪；当前 OpenCV 质量门会拒绝多脸进入 CompareFace，隔离回贴仍未实现。
- 检查点 6 已增加 Pillow/OpenCV 质量门、Tencent IAI CompareFace（当前会话同人）和 Tencent IMS ImageModeration Adapter，以及 Profile v0 的归一化脸框/眼睛几何构建器；CompareFace CAM 最小权限与 IAI 服务均已开通，真实 smoke 已成功返回原始分 100（不作为用户分数）。

当前产品与实际实现的共同真相源见：[执行版 PRD](docs/母版人像一致性Agent-执行版PRD.md)。六个合同的产品语义见 [PRODUCT_RULES.md](docs/PRODUCT_RULES.md)，字段与耦合规格见 [CONTRACTS.md](docs/CONTRACTS.md)，Prompt 见 [AGENT_PROMPTS.md](docs/AGENT_PROMPTS.md)。Python 合同、可配置 Policy 与 SQLite 六表已经同步为 `v0.2-frozen`；Prompt 尚未接入 LLM。

开发状态、每一步验证结果和待你决策的事项见：[开发进展](docs/DEVELOPMENT_PROGRESS.md) 与 [决策日志](docs/DECISION_LOG.md)。

## 当前项目树

```text
portrait-consistency-agent/
├── app.py                         # 本机 Streamlit 壳；已接质量门/安全/同人/Profile 入口
├── .streamlit/config.toml         # 仅绑定 127.0.0.1，关闭匿名统计
├── data/provider_cards/           # 可追溯 Tencent 能力卡（RAG P0）
├── docs/                          # 产品规则、六合同、Prompt、进展、决策与 API Gate 记录
├── scripts/                       # 环境检查与显式 opt-in 的腾讯 smoke 脚本
├── src/portrait_consistency_agent/
│   ├── core/                      # v0.2 合同、可配置 Policy 与本地设置
│   ├── services/                  # 质量门 / Profile v0 / Provider Card / 腾讯 API Adapter
│   └── storage/                   # SQLite + JSONL 脱敏 trace
├── storage/                       # 本地 DB / 未来结果图（Git 忽略）
├── logs/                          # 本地 JSONL trace（Git 忽略）
└── tests/                         # 当前 51 个基础/合同/质量门/Profile/Provider 测试
```

## 本地命令

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
```

Streamlit 页面已串入检查点 6 的本地质量门、显式同意后的安全/同人调用按钮和 Profile v0 建档；当前仍未接入 LLM、完整状态机、EditPlan、Beautify 执行和修后复测。项目已完成合同、六表存储、脱敏 Trace、Provider Cards、腾讯 Adapter、质量门/Profile v0；CompareFace 已完成一次真实同图 smoke（返回原始分 100，未作为用户分数展示）。ImageModeration 尚未 live 验证。不要把密钥、真实照片或运行日志提交到 Git。
