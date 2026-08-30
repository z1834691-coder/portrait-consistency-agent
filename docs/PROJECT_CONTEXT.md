# 项目上下文与不可变边界

## 当前目标

在 2026-09-04 前交付可运行 Demo 和演示视频，证明以下闭环真实存在：母版建立、目标照诊断、受约束编辑计划、用户确认、外部图片编辑 API 调用、修后复测、停止或重规划。

## 产品定义

产品帮助用户建立自己的 `Reference Profile`，并让单张照片或一组照片分别接近该标准。目标是五官和脸型的视觉一致，不定义“美”或“自然”的统一标准。它不做人脸库搜索、陌生人身份识别、身份认证、自动发布或通用生成式重绘。

产品不展示未经校准的 0—100 一致性指数，也不硬编码 90 分目标线。未来如展示概率，只能是基于有授权人工可接受性样本校准的接受概率；在 benchmark、holdout 和校准证据完成前，使用可解释的“可继续/建议调整/无法判断/重新上传”结论。

当前用户规则：

- 腾讯 Provider Card 声明支持的参数原则上都可以执行；美白和磨皮默认关闭，必须得到用户明确允许；
- 肤色、妆面、身体和隐私部位不进入母版档案；
- 母版只有一个生效版本，新母版成功建立后替换旧版本，母版照片不能直接二次编辑；
- 母版除归一化五官/脸型特征外，可在单独同意后保存加密、可删除、受限访问的派生主体表示半年；到期提醒重新上传，或删除主体锚点后降级为几何特征对齐；
- 同一人物门控、质量门和可执行性判断是目标照片进入修图前的前置条件；
- 多脸照片在条件达标时让用户选择目标脸，系统自动隔离背景和其他人脸，只编辑所选单脸；批量模式中的单张失败不阻塞其他照片，但必须先告知用户；
- V0 不显示任何接受概率；用户交互可以生成弱标签，模型可以生成合成边界案例，但人工金标准必须独立保留；
- 受邀 Streamlit 部署方向已冻结为“私有 GitHub + Community Cloud Private/受邀 Beta”；Cloud Private App 已创建，当前 URL 为 `https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，只读探针返回登录跳转。访问名单、Secrets、费用和真实照片授权仍需单独确认；Cloud 容器在美国且磁盘不保证持久化，不能当作生产服务器或长期数据存储。腾讯 Web License 现场表单已核验应填纯主机名，不带协议/路径。
- 产品数据闭环已确认分层记录短期任务事实、意图/反馈/继续使用信号、上下文退出/沉默和长期 Profile 建立率、首次成功修图率、7/30 日回访、WAU/MAU、会话完成率、失败后重传率、明确满意/不满意比例；`product_events` 仍是运行账本，不是训练 Dataset。**本机运营/RAG Dashboard 页面已经实现**，但真实受邀用户采集、足够时间窗后的长期聚合与任何留存结论仍待开发和验证。
- LLM 数据边界已确认：DeepSeek 仅收脱敏最小必要文本，不收照片、向量、锚点或原始 Trace；失败走本地模板，OpenRouter/跨境默认关闭，ZDR 需供应商证据核验。处理、外部 Provider、半年锚点和公开演示分别授权；多人须全员授权，未成年人拒绝。

四合同审计的五项产品规则已经最终确认并进入合同 `v0.4`：确认必须有界；V0 总计最多三轮、连续两轮无改善提前停止且均由可配置策略控制；产品目标为自动隔离/裁剪/回贴/复测，失败时要求用户先裁剪，链路完成前拒绝多脸整图执行；人工复核只承诺由项目开发者处理；质量/可执行性阈值与主体匹配判定分开。v0.4 另外冻结了匿名事件/反馈分层、183 天主体锚点生命周期、IMS 保守门控、LLM 文本最小化、用户不满意立即停止，以及 8C 的策略提议/目标证据字段。8B 进一步冻结：确认页不改滑杆、实质改口必须重建计划；确认绑定照片 hash/Profile/参数/部位且 10 分钟失效；结果只会话内存展示/下载；每份确认计划只允许一次外部尝试、不自动重试。

## 当前技术冻结

| 层 | 当前选择 | 边界 |
|---|---|---|
| UI | Streamlit | 本机开发 + 已准备 Community Cloud Private/受邀 Beta 部署包；暂不做公网开放 |
| 状态/编排 | Python 状态机 + 受限 ReAct 工具提议 | 状态机拥有权限与迁移最终权；不要求 LangGraph，LLM 只能在当前状态白名单内提议下一工具 |
| 数据 | SQLite + JSONL trace + 匿名 `product_events`（本地）；部署后按平台存储方案扩展 | Demo 仍不做多租户；主体锚点需加密、可删除、受限访问、183 天到期；当前只是合同/Policy，真实加密/worker 未实现 |
| 几何与质量视觉 | OpenCV Haar + Pillow V0 基线（可替换 CV Adapter） | 已实现真实图片解码、质量/可编辑性指标和粗粒度脸框/眼睛几何；不承担同一人物判断，后续可替换为关键点模型 |
| 主体匹配 | 腾讯 IAI `CompareFace` 3.0（独立 Subject Match Adapter） | 只做母版与目标的 1:1 同人路由，不做 1:N 搜索或身份认证；内部供应商分数不作为母版一致性分数展示；服务已开通且 CAM 最小权限已验证 |
| 执行 | 腾讯云 BeautifyPic（历史 live Gate 已通过；8B 离线 Gate 已通过） | 仅授权后端调用；参数由 Provider Card 决定；用户确认后校验 scope/hash/期限/Gate 并调用一次；结果仅当前会话内存；无自动重试 |
| 修后验证 | 本地结果观察器 + 8C-1 `VERIFICATION_STRATEGY_SELECT` baseline | 只比较本轮 executable 特征并产出 `VerificationResult`；不计算总分/概率，不再次上传图片；8C-2 在首次 scope 内自动重规划、执行和复测；外部/混合复测仍待后续 Gate |
| LLM | DeepSeek V4 Flash + 本地模板 fallback | 文本 IntentFrame Adapter、Pydantic 校验、单轮明确文字授权、本地降级和一次真实云端 Schema receipt 已实现；只输出候选意图/一个澄清问题/摘要，不猜视觉数值/参数/权限 |
| RAG | P0-A/P0-B：独立 SQLite 权威知识 + metadata 过滤 + FTS5 + 本地 dense/RRF/rerank；P0-C：8A 规划前和 8C 策略前的受限 evidence consumer；本机 RAG 治理 Dashboard | 已导入 3 张审核 Provider Card/10 条原子规则，P0-B 只读固定本地模型缓存并能安全退回 P0-A；P0-C 返回 direct/reference/conflict 和脱敏 bad case，可留来源引用但 `execution_authorized=false`。Dashboard 只显示脱敏聚合；不读照片/原话，不调用 LLM/API，不新增 Provider；自动 worker、external/hybrid 另开 Gate |

## 安全与证据边界

- 原图默认不进入 LLM；只允许本地/临时后端处理；
- Profile 只保存结构化派生特征；用户已确认可在单独同意后保存加密、可删除、受限访问的派生主体锚点 183 天；30/7 天提醒，撤回立即停用，24 小时主存储删除、7 天备份清理；当前合同记录该承诺，真实加密、提醒和删除审计任务待开发；
- LLM 不接收照片、Base64、人脸向量、密钥或原始 Trace；Demo 默认不启用跨境/第二云 Provider 路由；
- 外部图片修改首轮必须明确确认；当前确认绑定照片 hash、Profile、当前参数和允许部位，10 分钟后失效。确认页不能直接改滑杆，实质改口必须重新规划/确认；同一 scope 内的 8C 子轮可受限自动执行，scope 变化必须重新确认；
- 每个工具结果、错误、参数与版本写入 trace；
- UI 可以展示真实状态、工具调用和决策摘要，不展示隐藏思维链；
- 当前项目只能称为可运行原型和方向性 smoke test；腾讯 API 有历史真实 BeautifyPic、CompareFace、IMS Pass/Block 回执，8A 有局部几何规划证据，8B 有确认/一次执行/ProviderRun 的离线证据，8C-1 有本地结果观察与 fixture 路由证据，8C-2 有自动续跑控制和父子血缘离线证据，RAG P0-A/P0-B/P0-C 有本地 SQLite/FTS/混合检索与受限 evidence 回接 Trace 证据，RAG Dashboard 有本机页面与安全聚合测试证据；但尚无新的 UI 真实 8C 图片回执、真实视觉改善、接受概率校准、线上稳定性、A/B 结果或用户增长证据。<span style="color:#C00000"><strong>RAG P0-C 与 Dashboard 已实现受限证据/可观测性，但完整 external/hybrid 复测、自动 RAG worker、新 Provider 和自由动态 Agent 策略仍未实现。</strong></span>
- 没有授权的照片、腾讯密钥、API 响应图片和个人日志不得进入版本控制。

## 当前开发节奏

每个检查点只做一个完整可验证的能力。完成后必须：更新 [母版人像一致性Agent-执行版PRD.md](母版人像一致性Agent-执行版PRD.md) 与 `DEVELOPMENT_PROGRESS.md`、记录需要用户决策的事项、运行验证、保留下一步入口。合同 `v0.4-frozen`、六类业务合同表、匿名运营账本和本地 Dashboard 已完成；检查点 6 已落地 OpenCV/Pillow 质量门、腾讯 CompareFace/ImageModeration 适配器和 Profile v0 构建器，CompareFace 已完成真实 live Gate；IMS 已分别取得一条真实 `Block` 和一条新授权照片的真实 `Pass`，两条路由样例均有证据。检查点 7 已落地 DeepSeek 文本 IntentFrame Adapter、Schema 校验和本地 fallback，并完成一次真实云端 Schema receipt。检查点 8A 已落地严格双眼测量、逐特征诊断、版本化确定性映射、待确认 `EditPlan` 和页面 Trace；检查点 8B 已落地用户确认、10 分钟 scope、一次 Adapter 调用、脱敏 ProviderRun 和会话内结果展示的离线 Gate。<span style="color:#C00000"><strong>8C-1/8C-2 已落地修后观察、`VerificationResult`、受限 `VERIFICATION_STRATEGY_SELECT`、有界三轮子计划/父子回执血缘、用户可见执行与反馈硬停止。RAG P0-A/P0-B/P0-C 也已落地独立 SQLite/FTS、本地 dense/RRF/rerank、依据卡和到 8A/8C 的受限 evidence 回接；RAG Dashboard 已落地为只读本机管理员页面。它们仍不改变工具权限或执行链。真实 external/hybrid 复测、自动 RAG worker、新 Provider 和 LLM 自由策略仍待后续 Gate。</strong></span>

## 2026-08-30 当前实现快照

Gold Set v2 评测器已经独立于线上 RAG 路径：public 52 题（34 dev + 18 challenge）和独立答案键用于开发/挑战评分，holdout 20 题只向运行器提供 `case_id/query`；隐藏答案键已移出工作区，public deterministic prediction 与一次私有 aggregate holdout 评分已经完成，当前两者的 project Gate 都为 `FAIL`，不能写成通过。私有 Markdown 的自然语言 `must_not` 仍未转换为 canonical event ID，因此 hard-safety 只显示 `MANUAL_REVIEW_REQUIRED`。火山美颜 API V2.0 与腾讯特效 SDK 只完成 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 fail-closed smoke；没有导入 SDK、没有真实图片出站、没有密钥或 ProviderRun。基于官方计费/准入核验，火山 V0 暂不购买/接入，当前执行链只用 Tencent。

当前交叉校验：全量 `pytest 146 passed, 4 warnings`；Ruff、compileall、`git diff --check` 已在 failure-pattern/优化看板收口后再次通过；HTML/Markdown/JSON 评测报告在 `reports/`。Precision C、Holdout A、Safety ID C 已冻结并实现；下一步是审核事件目录、生成 v3 独立验收集，并继续完成新 Provider 的书面能力/License/隐私/价格/延迟、真实 receipt、Gold 回归与产品准入。部署包已完成 `src/` 入口兼容、轻量锁文件和敏感材料排除，私有 GitHub 仓库已创建并推送 `main`；Cloud Private App 已创建并返回固定 URL，但腾讯 Web License 测试申请仍未提交。

## 2026-08-30 failure-pattern 实现快照

新增 `rag_failure_analysis-v0.1`、`rag-correction-candidate-v0.1`、报告 allow-list、page 4 报告集合和 page 5 RAG 优化看板。分析器与候选只在公开/聚合材料上运行，禁止读取 hidden answer key、hidden 题干、照片、向量、原始用户文本、LLM 或 Provider；候选公开回归无指标回退但未推广，当前 project Gate 仍 `FAIL`。报告与看板只提供脱敏指标、错误类型、候选差值和六步 SOP，不提供自动应用修正的按钮。两个候选 Provider 仍分别为 `not_run`/`blocked`，没有新的图片出站。

## 2026-08-30 评测治理冻结快照

Precision C 已实现为固定/覆盖式/返回式三种并行口径；Holdout A 已将 v2 降级为历史诊断并创建 v3 answerless 模板；Safety ID C 已建立 `RAG_EVT_*` 确定性字典，未知标签保持人工复核。public 报告固定 Precision@3=`47.44%`、覆盖式/返回式=`100%`，project Gate 仍 `FAIL`。这些变更只扩展评测和保管可观测性，不改变 RAG advisory、Provider fail-closed 或图片执行权限。
