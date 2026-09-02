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
- 受邀 Streamlit 部署方向已冻结为“私有 GitHub + Community Cloud Private/受邀 Beta”；Cloud Private App 已创建，当前 URL 为 `https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，只读探针返回登录跳转。访问名单、Secrets、费用和真实照片授权仍需单独确认；Cloud 容器在美国且磁盘不保证持久化，不能当作生产服务器或长期数据存储。腾讯 Web License 已按纯主机名提交并在控制台显示“正常”，有效期显示为 2026-08-30 至 2026-09-13。
- 产品数据闭环已确认分层记录短期任务事实、意图/反馈/继续使用信号、上下文退出/沉默和长期 Profile 建立率、首次成功修图率、7/30 日回访、WAU/MAU、会话完成率、失败后重传率、明确满意/不满意比例；`product_events` 仍是运行账本，不是训练 Dataset。**本机运营/RAG Dashboard 页面已经实现**，但真实受邀用户采集、足够时间窗后的长期聚合与任何留存结论仍待开发和验证。
- LLM 数据边界已确认：DeepSeek 仅收脱敏最小必要文本，不收照片、向量、锚点或原始 Trace；失败走本地模板，OpenRouter/跨境默认关闭，ZDR 需供应商证据核验。处理、外部 Provider、半年锚点和公开演示分别授权；多人须全员授权，未成年人拒绝。

四合同审计的五项产品规则已经最终确认并进入合同 `v0.4`：确认必须有界；V0 总计最多三轮、连续两轮无改善提前停止且均由可配置策略控制；产品目标为自动隔离/裁剪/回贴/复测，失败时要求用户先裁剪，链路完成前拒绝多脸整图执行；人工复核只承诺由项目开发者处理；质量/可执行性阈值与主体匹配判定分开。v0.4 另外冻结了匿名事件/反馈分层、183 天主体锚点生命周期、IMS 保守门控、LLM 文本最小化、用户不满意立即停止，以及 8C 的策略提议/目标证据字段。8B 进一步冻结：确认页不改滑杆、实质改口必须重建计划；确认绑定照片 hash/Profile/参数/部位且 10 分钟失效；结果只会话内存展示/下载；每份确认计划只允许一次外部尝试、不自动重试。

## 当前技术冻结

| 层 | 当前选择 | 边界 |
|---|---|---|
| UI | Streamlit（当前承载） | 本机开发 + 已准备 Community Cloud Private/受邀 Beta 部署包；设计已冻结为“对齐首页／Agent 对话子页面 + 母版档案 + 结果记录”三空间信息分组，桌面壳为全局导航、项目/母版上下文、中央对齐工作区、右侧 Agent 对话轻量四区；正式视觉 token 为 Tweakcn Party Rock 原始 Light/Dark、字体为 PingFang SC；当前候选统一为最左侧黑色导航、中央/右侧米白、紫色柔性框/轨迹、荧光绿少量节点和黑色线框结构，上一版紫黑暗流仅作历史；A/B/C 是历史方向包；最新 Getty × Thread Track 1 是当前精细化候选，另提供三张无人物 Image 2 环境素材、分层 SVG 和可交互 HTML，仍待方向选择；[前端与交互设计需求文档](前端与交互设计需求文档.md)、[精细化视觉规范](UI_VISUAL_DESIGN_SPEC_DETAILED.md)、[关键帧 Prompt](FRONTEND_UI_KEYFRAME_PROMPT.md) 与 [风格说明](UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md) 已写成执行/评审规格；候选源见 `design/keyframes/party-rock-pingfang/candidates/` 与 `design/visual-tracks/getty-thread-party-rock/`；Streamlit 视觉迁移待 UI Gate；暂不做公网开放 |
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

Gold Set v2 评测器已经独立于线上 RAG 路径：public 52 题（34 dev + 18 challenge）和独立答案键用于开发/挑战评分，holdout 20 题只向运行器提供 `case_id/query`；隐藏答案键已移出工作区，public deterministic prediction 与一次私有 aggregate holdout 评分已经完成，当前两者的 project Gate 都为 `FAIL`，不能写成通过。私有 Markdown 的自然语言 `must_not` 仍未转换为 canonical event ID，因此 hard-safety 只显示 `MANUAL_REVIEW_REQUIRED`。火山美颜 API V2.0 与腾讯特效移动/PC 细项仍只完成 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 fail-closed smoke；腾讯特效 Web 另有独立的浏览器 Adapter、Streamlit page 6 和 `ProviderRun` 联合合同，但 Card 仍为 candidate、尚无新的 Browser Receipt，不能写成已进入主执行链或细项能力已验证。基于官方计费/准入核验，火山 V0 暂不购买/接入，当前主执行链仍只用已验证的 Tencent BeautifyPic/IMS。

当前交叉校验（历史快照更新）：全量 `pytest 178 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 已在腾讯特效 Web 适配器切片后再次通过；HTML/Markdown/JSON 评测报告在 `reports/`。Precision C、Holdout A、Safety ID C 已冻结并实现；v3 Holdout 已在工作区外完成审核并完成一次性盲测，quality Gate 仍为 `FAIL`。部署包已完成 `src/` 入口兼容、轻量锁文件和敏感材料排除，私有 GitHub 仓库已创建并推送 `main`；Cloud Private App 已创建并返回固定 URL，腾讯 Web License 已显示正常。腾讯特效 Web 的 page 6 已能本机启动，但真实 Browser Receipt 仍待绑定域名的 Cloud 页面与 Secrets 运行；Cloud ImageModeration 当前失败只会回传脱敏 `error_code`/`provider_request_id`，等待产品负责人依据真实回执继续排查。

## 2026-08-30 RAG 工程收口快照

本轮新增 metadata-only `RagLifecycleAudit`：它检查 3 张已审核 Tencent Card 的状态/有效期/来源 URI/原子规则数，并核对 dense manifest；当前为 3 items、10 active chunks、`issue_counts={}`、`index_status=in_sync`。审计写入脱敏 SQLite/JSON/HTML，可从 page 4 显式触发；不自动发布、改状态、删除、重建索引、调用 LLM/Provider 或授权图片出站。全量回归当前为 `178 passed, 4 warnings`；RAG project quality Gate 仍为 `FAIL`，不能写成通过。

## 2026-08-30 failure-pattern 实现快照

新增 `rag_failure_analysis-v0.1`、`rag-correction-candidate-v0.1`、报告 allow-list、page 4 报告集合和 page 5 RAG 优化看板。分析器与候选只在公开/聚合材料上运行，禁止读取 hidden answer key、hidden 题干、照片、向量、原始用户文本、LLM 或 Provider；候选公开回归无指标回退但未推广，当前 project Gate 仍 `FAIL`。报告与看板只提供脱敏指标、错误类型、候选差值和六步 SOP，不提供自动应用修正的按钮。两个候选 Provider 仍分别为 `not_run`/`blocked`，没有新的图片出站。

## 2026-08-30 评测治理冻结快照

Precision C 已实现为固定/覆盖式/返回式三种并行口径；Holdout A 已将 v2 降级为历史诊断并创建 v3 answerless 模板，工作区外另有 `OWNER_REVIEW_DRAFT` 题目/答案草案；Safety ID C 已建立并经产品负责人审核 `RAG_EVT_*` 确定性字典，未知标签保持人工复核。public 报告固定 Precision@3=`47.44%`、覆盖式/返回式=`100%`，project Gate 仍 `FAIL`。这些变更只扩展评测和保管可观测性，不改变 RAG advisory、Provider fail-closed 或图片执行权限。

## 2026-09-01 当前状态覆盖

产品负责人已审核 v3 Holdout 36 题，并按 Holdout A 完成一次工作区外私有聚合盲测。runtime 仅含 `case_id + query`，runner 未读答案键、照片、向量、LLM、Provider 或网络；聚合结果为 Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、evidence relation=23.61%，hard-safety=0/36（PASS），project quality Gate=`FAIL`。这份结果用于识别当前 baseline 的泛化问题，不得用于逐题调参。

Streamlit Cloud Private 页面已经打开，等待产品负责人亲自完成第一位用户的真实照片流程。8C-1/8C-2 的控制逻辑和 fixture 仍已验证，但尚无新的 UI 真实多轮图片回执或视觉改善证据；详见 `FIRST_USER_E2E_TEST.md` 与 `MIDTERM_STATUS_2026-09-01.md`。

## 2026-09-01 RAG 自动优化 Loop 当前事实

新增 `rag_optimization_loop-v0.1`、Rubric、优化进展文档和 page 5 代际 Dashboard。公开 52 题逐题诊断显示 route/evidence/relation/排序均正确，51 题只有 Gold 稀疏分母代码；V0/V1/V2 Composite 均 `0.947436`，连续两代增益为 0 后按停止规则跳过 V3/V4。v3 仅以 aggregate pattern（relation/set/route）进入报告，逐题答案未读取、未重复正式运行。候选、active baseline、Provider 白名单、权限和 `execution_authorized=false` 均未改变；需要新独立 Holdout v4 才能再次验证泛化。

优化报告同时保存每类 v3 aggregate 的“观察事实 / 可验证假设 / 下一份 Holdout 证据”，并标记 relation/set/route 计数可重叠；这些假设只指导 v4 数据设计，不是隐藏集逐题结论。

## 2026-09-01 当前覆盖｜第一位真实用户 8A 阻塞与修复

第一位用户已在 Cloud Private 页面完成母版/目标照 IMS、Profile 建立和 CompareFace；目标照原始分 `56.231842041015625` 路由为 `uncertain`。旧代码没有把“本人且有权编辑”的一次性确认传给 8A，因此记录 `subject_match_not_confirmed`、`quality_route_not_continuable`，没有 EditPlan、ProviderRun 或 VerificationResult。RAG 已返回 Tencent FaceLifting/EyeEnlarging 直接证据，但仍是 advisory-only，未造成阻塞。

当前代码已增加 `subject_match_uncertain_acknowledged`：确认写入有界 `ConfirmationScope`，规划器和执行器双重校验，确认事件和策略版本留痕；它不改变 `uncertain`、不更新主体锚点，`no_match` 仍硬拒绝。该字段是可选向后兼容策略扩展，并有 `contract_v0_4_subject_uncertain_ack` migration marker。Cloud 重建后用户可继续 8A→8B→8C；未产生真实 ProviderRun/VerificationResult 前，不称首轮完成。

第一位用户反馈：上传慢、首屏展示脱敏 JSON、工程检查点和按钮过多、自然语言入口被 GUI 挤压、整体 UI 偏工程文档。它们已记录为下一 UI Gate 的事实输入；先完成一次真实闭环并增加阶段耗时证据，再冻结 UI 重构，不为减少点击删除必要的隐私或授权门。

## 2026-09-01 失败驱动 RAG Loop v2 当前事实

上一轮优化无增益的根因是候选只处理已生成 `Prediction`，未改变自然语言→`RagQuery` 的输入层。当前新建 `rag_failure_driven_dev_v1`（28 题：16 dev + 12 challenge，annotations=`owner_review_required`），并新增查询编译候选和失败驱动运行器。V0 Composite=`0.355614`；V1=`0.403233`（2 条预测改变）；V2=`0.947619`（22 条预测改变，route/relation/Recall@5=100%）；V3/V4 各 0 条改变，连续两代 `<0.01` 停止。该结果只属于开发集工程事实，public regression/project Gate 仍 `FAIL`，active baseline 未变。

报告、SOP、Rubric、page 5 和合同均记录 `changed_prediction_count`、Trace 安全布尔值和停止原因；无网络、LLM、Provider、照片/向量或 hidden-answer 访问。V3 Holdout 仍不重跑、不读取逐题答案；审核 annotations 后必须新建独立 v4 才能评估泛化。

本轮最终 QA 为全量 `pytest 178 passed, 4 warnings`；Ruff、format、compileall、`git diff --check`、failure-driven Loop、P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 均通过。4 条 warning 是既有 Pillow 弃用提示；这不改变 RAG quality Gate=`FAIL` 或候选未推广状态。

失败驱动报告现同时提供 `final_candidate_diagnostics`，让 28 道公开题可逐题比较 V0 与终态；产品复盘见 `docs/RAG_FAILURE_CASE_REVIEW_V2.md`。该可观测性补充不读取 v3 私有答案，也不改变 Holdout A。

## 2026-09-01 当前 Cloud 运行异常与修复

第一位用户在 Cloud 页面触发 `Tencent ImageModeration request failed`。运行日志显示页面中断的确定性根因是 Streamlit 交互重跑时重复写入 `photo_quality_results.quality_result_id`，SQLite 抛出唯一键异常；本机真实 IMS smoke 已返回 `Pass`（RequestId `c95e1359-9ecb-45ac-aa94-3776fbccc0ad`），因此当前不能把通用页面提示直接归因为腾讯凭据失效。`LocalTraceStore` 已实现同一合同唯一键/相同脱敏投影的幂等复用，以及变化内容的 fail-closed 冲突；Cloud 重建后需重新触发一次 IMS 以取得新的云端回执。该修复不改变 RAG、Provider、图片权限或安全门。

## 2026-09-01 腾讯特效 Web Cloud 当前状态

Cloud 已从最新提交成功重建，page 6 能加载，旧进程缓存造成的 Web Card 导入错误已通过 Reboot
消除；但 Effect Web 三项 Secrets（`TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、
`TENCENT_EFFECT_LICENSE_TOKEN`）尚未配置，真实 Browser smoke 仍为 `not_run`。本轮没有加载 SDK、
没有图片出站、没有 Browser Receipt；候选 Card 继续 fail-closed。配置后只运行官方示例图一次，
并在隐私/区域/成本/Gold/负责人准入证据齐全后再讨论 promotion。

## 2026-09-02 当前事实覆盖｜V3 validation 与 RAG 优化

产品负责人已明确授权把已审核 V3 题目/答案用于 validation 诊断。原始一次性 answerless Holdout-A 快照仍保留、不重跑；验证副本 `rag_v3_validation_cases_v1.json` / `..._annotations_v1.json` 只供离线诊断。`rag_v3_validation_diagnostics_v1.json/.html` 为 H01–H36 的 G0–G5 逐题结论、根因、SOP、查询投影、检索摘要和完整安全 Trace。

最终 G3 保守候选的 validation Route=100%、Evidence relation=97.22%、Recall@5=100%；G2 的 100% 因 public regression 退化而拒绝，G4/G5 0 改变。固定 Precision/project Gate 仍 `FAIL`，hard-safety `PASS`，active baseline 与执行权限未改变。后续 promotion 仍必须使用不与 V3 重叠的独立 V4 Holdout；RAG 继续 advisory-only。

2026-09-02 Web 试验修复：Cloud 首次回执的 `request_ref` 错位来自 Streamlit 重跑时随机重建请求，
不是腾讯回执被放行或图片结果被篡改。page 6 已改为 fingerprint + 同代次 request 复用，签名刷新与
组件 reset 解耦；旧回执不入账。Web Card 仍为 `candidate`，当前没有新的真实 Browser Receipt。

## 2026-09-02 当前事实覆盖｜V4 Holdout 与最终 QA

V4 已建立为与 V3 不重叠的 48 题独立 Holdout。answerless baseline 先运行一次并封存，再由产品负责人授权离线 validation 诊断。正式 blind 结果为 Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、MRR=81.25%、nDCG@5=63.22%，hard-safety=0/48（PASS），project quality Gate=FAIL。解冻候选语义诊断指标达到 100%，但不代表泛化，`active_baseline_changed=false`、`proposal_only=true`。

V4 的具体题目、盲测聚合、逐题 Trace、失败模式、SOP 和验证命令见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。fixed/effective/returned Precision 并列保留，Gold 稀疏不能成为换分母抬分的理由；在新的未参与诊断 Holdout 通过前，RAG 不得 promotion 或称产品化。

本轮最终工程回执：全量 pytest=`189 passed, 4 warnings`；V4 专项=`8 passed`；Ruff check/format、compileall、`git diff --check`、V4 diagnostics runner 及既有 RAG/8C smoke 均通过。腾讯特效 Web 最新明确重试仍是 SDK 100/规范化码 20001001、无输出图，Card 继续 `candidate`。4 条 warning 为既有 Pillow 弃用提示。

## 2026-09-02 当前事实覆盖｜公平评测过程门

上述 189 条是历史快照；当前全量工程校验为 `196 passed, 4 warnings`，代码静态检查、编译和全部离线
smoke 均通过。新版 V3 `36/36`、V4 `48/48` 的无答案过程重放均完成检索 Trace，过程门 `PASS`，
并封存了不含原题/答案的脱敏运行包；旧 V4 正式快照仍是历史 `FAIL`，不能补写或复用。当前质量评分
状态是 `READY_AFTER_SEPARATE_GOLD_JOIN`，但 RAG project Gate 仍 `FAIL`、`proposal-only`，下一步只能
按哈希把 Gold 单独连接到新运行包。

## 2026-09-02 当前事实覆盖｜Tencent Web 工具编排

新增 `ToolRegistry` 与 `MetaAgentToolSelector`，将已审核的 BeautifyPic baseline 和 candidate Web Card 纳入统一只读目录。Meta-Agent 输出 `ToolProposal`，可解释候选工具、准入检查、RAG 证据和 baseline fallback；proposal 永远不授权执行，不读图片、不持有密钥、不创建 ProviderRun、不调用网络。8A 和 page 6 已接入该提议/Trace 展示，真实 Web 结果仍仅作为独立候选 Browser Receipt。因为 `EditPlan` 仍是 BeautifyPic 专用且 Browser Receipt 不含结果图 bytes，Web 主流程接入等待 A/B/C 结果交接决策，Card 继续 `candidate`。

## 2026-09-02 当前事实覆盖｜Web B handoff 与 E1/E2

上一段关于“BeautifyPic 专用 EditPlan、Browser Receipt 无结果图和 A/B/C 待决”的文字是历史状态。产品负责人已冻结 B：`EditPlan`/`ProviderRun` 采用 Web 专用参数模型，浏览器通过独立 `result` 触发器将一次性结果 data URL 回传；服务端校验 request_ref、输入/输出 hash、尺寸、MIME 和大小后，只在内存中交给共同 `VerificationResult`。RAG/Meta-Agent 仍只提议，Web candidate 不能自行获得执行权限。

E1 已由 `accept_effect_web_browser_result()` 与共同 `verify_result()` 的 fixture 链路验证；E2 已由 8 个成功、失败、请求/输入/输出哈希错位、MIME/尺寸/大小异常和批量隔离样本验证，坏样本不阻塞后续样本，结果 payload 不持久化。新增的纵向 smoke/test 还验证 Meta-Agent 的 Web proposal 与 Web EditPlan provider/Card 绑定。E3 仍等待真实多样本视觉、供应商数据/费用证据和负责人批准；在 E3 前 BeautifyPic 继续是唯一正式主流程 Provider。

该段为 Web E2 变更时的历史工程 QA：`216 passed, 4 warnings`；Ruff、format、compileall 和 `git diff --check` 均通过。它只证明代码/合同/fixture 一致，不改变 Web Card `candidate`、RAG `proposal-only` 或 E3 准入要求；RAG 候选与 V5 过程后的最新 QA 为 `217 passed, 4 warnings`，见本文件当前事实覆盖段。

## 2026-09-02 当前事实覆盖｜RAG 深度优化与 V5

当前 RAG 深度优化已从“只看总分”改为“真实检索层候选 + 过程监督 + 独立 Holdout”。operation coverage candidate 在开发集 28 题、公开回归 52 题上留下了完整候选 Trace，分别改变 26、49 条 Prediction 事实；公开检索 Evidence relation/Recall@5 为 100%，MRR 93.27%、nDCG@5 95.30%，hard-safety PASS。候选仍是 proposal-only，active baseline 未改变。

新建的 V5 独立 Holdout 有 60 题，运行时只读取 answerless 题目。该段记录 Gold join 前的过程审计：输入/Trace/Prediction/retrieval 均 60/60、`process_gate=PASS`、`quality_scoring_gate=READY_AFTER_SEPARATE_GOLD_JOIN`；没有读取答案/标注、照片/向量或密钥，也没有调用 LLM、网络或 Provider。负责人现已授权完成一次质量 Gold join，当前质量见本文件末尾，不能称 RAG 产品化。

本轮真实代码/报告入口：`reports/rag_policy_coverage_candidate_v2.json/.html`、`reports/rag_candidate_diagnostics_v1.json/.html`、`reports/rag_v5_holdout_process_audit.json/.html`；Dashboard 为 `pages/5_RAG优化看板.py`。该段记录 Gold join 前状态；负责人现已授权并完成一次聚合，当前项目状态和质量见本文件末尾，不是“RAG 已通过”。

已完成一次 V3/V4 公平 Gold 连接：只在内存将工作区外答案键与已封存无答案运行对齐，输出 `reports/rag_fair_gold_join_v2.json/.html` 的双轨聚合，不输出题目、答案或 case 级结果。V3/V4 真实检索 Recall@5 分别为 `34.72%`、`41.32%`，Evidence relation 分别为 `16.67%`、`24.65%`；两者仍未达到质量门。该段 `217 passed, 4 warnings` 与“V5 质量连接仍需授权”属于 Gold join 前历史快照；V5 当前事实与最新 QA 见下一段。
### 2026-09-03 当前事实覆盖｜V5 Gold join

V5 答案已由负责人审核并授权一次聚合连接。质量结果：Route=`16.67%`、Evidence exact=`1.67%`、
Evidence relation=`26.39%`、Recall@5=`73.89%`、MRR=`90.33%`、nDCG@5=`75.36%`、hard-safety=`PASS`、
project Gate=`FAIL`。这不是产品化通过。新增 `reports/rag_v5_failure_analysis_v1.html` 只展示聚合失败
模式；V5 题集已封存，不用来逐题调参。下一候选先回到公开开发/回归集，必要时新建 V6。

本轮代码、合同、测试、报告和文档同步后的全量 QA 为 `220 passed, 4 warnings`；Ruff check、format、compileall
与 `git diff --check` 均通过。4 条 warning 为既有 Pillow 弃用提示。

## 2026-09-03 当前事实｜E3 真实 Web 候选试验

负责人已批准 E3，并提供四张真实 JPEG。它们先经过内存预检（输入哈希、尺寸、人脸数、质量/可编辑性路由和分层标签），再在部署后的精确域名 page 6 逐张执行 Tencent Effect Web。当前真实结果为 4/4 `succeeded`，输入哈希 4/4 绑定预检，结果交接标记 4/4；透明通道 PNG 作为异常样本被拒绝。脱敏汇总为 `reports/effect_web_e3_evidence_v1.json/.html`，只读展示页为 `pages/8_腾讯特效Web_E3证据看板.py`。

E3 的工程事实不等于视觉准入：手工 manifest 尚未记录四条完整 `request_ref`，共同 `VerificationResult` 的真实图像几何复测、视觉泛化、供应商地区/留存/费用与负责人 promotion 仍未完成。`tencent_effect_web` Card 保持 `candidate`；正式主流程仍走已验证的 Tencent BeautifyPic，RAG/Meta-Agent 继续 `proposal-only`。结果图 bytes、data URL、密钥和本地路径不写入数据库、Trace、RAG 或 Git。
