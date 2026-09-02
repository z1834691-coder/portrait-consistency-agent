# 项目中期状态报告｜2026-09-01

## 一句话结论

项目已经从“把 Agent 工程链路搭起来”进入“真实用户验证与质量收口”阶段：核心 Demo、合同、腾讯现有 Provider、8A/8B/8C 离线闭环、RAG 本地治理和可视化看板都能运行并留证；但 v3 独立盲测的质量 Gate 未通过，真实用户照片端到端和 UI 多轮图片回执尚未完成，因此现在还不能写成“RAG 已通过”或“修图效果已验证”。

## 已完成的工作，以及它们证明了什么

| 工作 | 当前证据 | 它证明什么 | 还不能证明什么 |
|---|---|---|---|
| 项目环境、Git、六合同、SQLite/JSONL 脱敏账本 | 全量自动化回归通过；合同版本 `v0.4` | 模块之间有共同输入/输出，发生过什么可以追溯 | 不是生产级多租户数据库，也不是训练 Dataset |
| 检查点 6：质量门、IMS、CompareFace、Profile v0 | 真实 IMS `Pass/Block`、CompareFace 回执；本地 Profile/质量测试 | 照片能否进入后续链路、当前会话是否同人、几何 Profile 如何落库已有可运行基线 | 不是所有照片都能识别，不是跨会话加密主体锚点，不是多脸隔离 |
| 检查点 7：DeepSeek IntentFrame | 一次真实文本 Schema receipt + fallback/Schema 测试 | Agent 能把脱敏用户文字转成结构化意图，并在失败时降级 | 不代表模型看图、算视觉事实或授权工具 |
| 检查点 8A | 严格双眼/脸型几何观察、映射策略、EditPlan 草案和 Trace | 差异可以被解释为“为什么建议这样改” | 不是校准概率，也不代表真实效果达到用户接受 |
| 检查点 8B | 确认 scope、一次 BeautifyPic 尝试、ProviderRun 和会话内结果规则 | 外部图片动作有确认、白名单、幂等和回执边界 | 尚未有新的 UI 真实照片回执或分布式 exactly-once |
| 检查点 8C-1/8C-2 | 6 条验证/计划族测试和 fixture Trace | 结果可重新观察；改善时可生成父子计划、同 scope 内有界续跑，变差/点踩会停止 | fixture 不等于真实腾讯多轮视觉改善 |
| RAG P0-A/B/C/D 与两个看板 | 独立 SQLite、FTS/dense/RRF/rerank、advisory-only、failure/SOP、lifecycle audit、HTML/Streamlit 页面 | Agent 能查已审核工具知识、区分 direct/reference/conflict、在 miss/冲突时保守停下，治理可观测 | RAG 没有获得工具权限，也没有质量通过或自动修图能力 |
| v3 Holdout 一次性盲测 | 36 题已由产品负责人审核；无答案 runtime 与私有答案键隔离；确定性 runner/scorer 完成一次运行 | 真实暴露当前基线在分布外表达/组合上的不足，且安全 Gate 可独立检查 | 不能用这份 hidden 逐题答案继续调参；不能把失败改写成通过 |
| Cloud Private 部署包 | Private URL 可访问并已打开；腾讯 Web License 显示正常 | 有一个可供受邀用户操作的演示入口 | 不是公网服务、生产持久化、跨境合规或稳定 SLA |

## v3 盲测实际结果

这次是一次不读答案键的运行：runner 只读取审核后的 `case_id + query`；答案键只在产品负责人控制的工作区外受限目录中用于聚合评分。运行没有调用 LLM、网络、图片 Provider，也没有读取照片或人脸向量。

| 指标 | 结果 | 解释 |
|---|---:|---|
| 题目/预测数 | 36 / 36 | 无缺失预测 |
| Route accuracy | 30.56% | 当前 baseline 对任务路由的泛化不足 |
| Evidence exact accuracy | 41.67% | 证据集合经常选错或不完整 |
| Evidence relation accuracy | 23.61% | direct/reference/conflict 关系判断是主要问题 |
| Recall@5 | 59.72% | 找到正确证据的覆盖不足 |
| MRR | 77.78% | 首个相关结果的排序尚可，但没有转化为稳定路由 |
| nDCG@5 | 63.81% | 排序质量低于当前项目门槛 |
| Hard-safety violations | 0 / 36 | canonical Safety Event 目录下安全拦截全部通过 |
| Project threshold Gate | **FAIL** | 质量门槛仍为 Recall@5 90%、Precision@3 80%、MRR 80%、nDCG@5 85%、Route/Relation 90% |

固定分母 Precision@3 为 27.78%；覆盖式为 59.72%，返回式为 77.78%。三种口径都保留用于解释稀疏 Gold，不能用覆盖式/返回式替换项目 Gate。该结果只能用于本次质量判断，不能把 hidden 逐题答案回流为规则补丁。

## RAG 失败模式优化 Loop 当前结果

已把 v3 的聚合错误（`evidence_relation_mismatch`、`evidence_set_mismatch`、`route_mismatch`）接入 proposal-only 的自动迭代链：公开集逐题诊断 → 单变量候选 → 回归 → anti-overfit → 边际停止。V0 baseline、V1 同义词归一化、V2 relation canonical 化均已运行，Composite 都为 `0.947436`、增益为 `0.0`；连续两代低于 `0.01` 后按规则跳过 V3/V4。anti-overfit=`PASS`，没有读取 v3 逐题答案、没有联网/调用 LLM/Provider/照片，现役 baseline 未改变。当前 RAG quality Gate 仍为 `FAIL`；详细事实/假设区分见 [RAG 优化进展](RAG_OPTIMIZATION_PROGRESS.md)、[Rubric](RAG_OPTIMIZATION_RUBRIC.md)、[SOP](RAG_FAILURE_ANALYSIS_SOP.md) 和 [RAG 优化 Dashboard](../reports/rag_optimization_loop_v1.html)。

## 第一位用户测试与 UI 8C 当前状态

- 已打开 Private Streamlit 页面，并完成首页结构和安全边界检查；页面显示母版上传、目标照片、自然语言意图、8A/8B/8C 入口及反馈控件。
- 代码和 fixture 已证明 8C-2 能生成新的 child plan/provider run、沿用有效 scope、保存父子 hash 血缘，并在后续自动复测前后写 Trace。
- 第一位用户的真实照片上传、真实 IMS/CompareFace/BeautifyPic UI 回执、真实视觉结果和用户反馈尚未发生；这些必须由产品负责人在页面上亲自完成，不能由离线 smoke 代替。
- 详细操作顺序、手动/自动分工和应回传的反馈见 [第一位用户端到端测试说明](FIRST_USER_E2E_TEST.md)。

## 还差哪些工作

### P0：完成可展示 Demo 的最后证据

1. 产品负责人完成一次本人授权照片的端到端页面流程：母版 → 目标照 → IntentFrame → 8A → 首次确认 → 腾讯执行 → 8C 复测；保留页面截图、Provider RequestId、验证结果和脱敏 Trace。
2. 若第一轮确实有可验证改善且 scope 不变，观察一次真实 UI 8C-2 子轮；记录是否自动续跑、父子回执是否完整、是否在第三轮前停止。若没有改善，不要为了“看起来完整”强行重复调用。
3. 把一次真实结果的视频录下来，明确说清楚“当前可验证的脸型/眼睛几何趋势”和“肤色、妆面、审美仍需用户肉眼判断”。
4. 记录第一位用户的短期事件：上传成功/失败、建档、IntentFrame、Provider 成功/失败、验证路由、下载、点赞/点踩、文字反馈和退出上下文；再由 Dashboard 聚合，不能把一位用户写成产品指标。

### P1：解决质量问题，但不污染 Holdout

1. 只在 public/dev/challenge 上分析 32 个错误案例，优先修复 evidence relation、route、evidence set 的系统性问题；candidate 先保持 proposal-only。
2. 重新冻结版本并跑公开回归；若仍需质量结论，另建下一份独立 Holdout，不修改本次 v3 的题目或答案。
3. 在产品负责人决定后，再启用脱敏 LLM Judge；Judge 只能辅助解释/忠诚度，不得改写 Gold 或授权工具。

### P2：要变成更完整产品仍需的工作

- 多脸检测 → 目标脸隔离/裁剪/回贴/复测，以及写真批量逐张规划；
- external/hybrid 复测 Adapter，CompareFace 仍只作同人辅助证据；
- 真实 AES-GCM 主体锚点、183 天 TTL、30/7 天提醒、撤回删除任务和受限访问；
- Cloud 访问名单、Secrets、美国区域数据出境告知、费用上限、持久化数据库和管理员鉴权；
- 新 Provider 重新完成 Card → Adapter → 权限/预算 → live receipt → Gold 回归 → 产品负责人准入；
- 需要时再把 SQLite 运行账本迁移到 PostgreSQL/对象存储；当前先收集真实运行事件，不把账本当训练数据。

## 当前工程复核

2026-09-01 本地复核结果：

```text
pytest -q                         → 160 passed, 4 warnings
ruff check                        → passed
ruff format --check               → 122 files already formatted
compileall                        → passed
git diff --check                  → passed
8C-1 verification smoke           → 4 路由 fixture 全部输出预期
8C-2 plan-family smoke            → parent/child 回执、scope、自动续跑、点踩硬停止通过
RAG P0-A/P0-B/P0-C smoke          → 本地、无网络、advisory-only
RAG lifecycle audit               → 3 items / 10 active chunks / issue_counts={} / in_sync
```

4 条 warning 是既有 Pillow `mode` 弃用提示，不是本轮失败。工作区仍有之前的文档修改未提交；本轮没有覆盖或删除这些修改，也没有把私有答案键、照片、密钥或结果图复制入仓库。

## 收尾顺序

现在最短且可信的收尾路径是：先由产品负责人完成一次真实页面流程并录下证据 → 根据真实结果决定是否做一次同 scope 子轮 → 形成短期运营数据截图和一条完整脱敏 Trace → 对 RAG 失败只做 public/dev 迭代 → 以新的独立 holdout 复验 → 最后把当前限制写进 Demo 视频和面试叙事。这样项目可以作为一个诚实的、可运行的 Agent 原型提交，同时保留继续成为完整产品的清晰路线。

## 2026-09-01｜Cloud ImageModeration 失败的根因与修复

第一位用户在 Cloud 页面看到腾讯安全请求失败。日志交叉检查后发现，页面实际稳定中断点是 Streamlit 重跑重复插入同一 `photo_quality_result_id`，SQLite 抛出 `UNIQUE constraint failed`；本机明确授权照片的真实 IMS smoke 已返回 `Pass`（RequestId `c95e1359-9ecb-45ac-aa94-3776fbccc0ad`），所以不能把泛化页面文案当成腾讯密钥失效。

已修复为幂等合同落账：相同业务唯一键和相同脱敏事实复用原记录；内容变化则以可识别冲突 fail closed；重复重放不重复计入完成类产品事件。该修复保护可追溯性，不改变 IMS 安全门、RAG advisory-only 或图片出站权限。Cloud 拉取新提交并重建后，仍须由产品负责人刷新页面、重新执行一次 IMS，取得新的云端真实回执后才能继续首位用户端到端测试。

## 2026-09-01｜RAG 失败驱动优化 Loop v2 的中期结论

上文“V0/V1/V2 Composite=`0.947436`、增益为 0”属于第一轮错误层候选的历史快照。复核后确认候选只改 Prediction 后处理，没有改变自然语言→`RagQuery` 的输入事实。

本轮将候选移到真实查询编译边界，建立 28 题（16 dev + 12 challenge）owner-review 开发集。V0 Composite=`0.355614`；V1=`0.403233`（+0.047619、改变 2 条预测）；V2=`0.947619`（+0.544386、改变 22 条预测）；V3/V4 各改变 0 条预测，连续两代 `<0.01` 停止。V0 failure code 为 route 24、relation 23、set 18、rank 10；稀疏 Gold 分母 28 条单独记录。候选无网络/LLM/Provider/hidden-answer 访问，active baseline 未改变，anti-overfit=`PASS`。

这证明“修错层”是上一轮无增益的原因，并证明 V2 在开发集上有效；它不等于 RAG 质量通过。新 annotations 需产品负责人审核，之后必须建立与 v3 不重叠的 Holdout v4；public regression/project Gate 仍 `FAIL`。本轮最终 QA 为 `178 passed, 4 warnings`，4 条 warning 是既有 Pillow 弃用提示。

本轮还补齐了逐题可观测性：失败驱动报告的 `final_candidate_diagnostics` 对 28 道公开题并列保存 V0 与终态状态/错误码/路由变化；从 V0 到终态共有 24 条 Prediction 事实变化。人工复盘见 [RAG_FAILURE_CASE_REVIEW_V2.md](RAG_FAILURE_CASE_REVIEW_V2.md)。这解决了“总分有变化但不知道哪道题被修复”的复盘缺口，仍不读取 v3 私有答案。

## 2026-09-01｜腾讯特效 Web Cloud 证据更新

Cloud 已完成最新代码重建，page 6 的旧导入错误已消失；但 Effect Web 三项 Secrets 尚未配置，
所以没有加载 SDK、图片出站或 Browser Receipt。该候选仍是 `candidate`，不能写成已接入主流程。
配置 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`
后，先用官方示例图运行一次，再补隐私/区域/成本/Gold 和人工准入证据。

## 2026-09-02｜V3 验证诊断后的中期更新

产品负责人明确把 V3 从一次性 Holdout-A 盲测改作 validation：原始盲测快照不动，派生验证副本用于逐题失败分析。当前已完成 H01–H36 的题目、Gold、Prediction、根因/SOP、查询投影、检索摘要和完整 Trace，并运行 G0–G5 候选链。

最终保守 G3 相比 G0：Route `30.56%→100%`、Evidence relation `23.61%→97.22%`、Recall@5 `59.72%→100%`；G2 虽在 V3 达到 100%，但 public regression 退化而拒绝，G4/G5 无增益。固定 Precision/project Gate 仍 `FAIL`，hard-safety `PASS`，RAG 仍 advisory-only、active baseline 未变。下一步不是继续在 V3 上调参，而是由新建且不重叠的 V4 Holdout 验证泛化，再决定 promotion。

完整回放入口：[V3 逐题诊断报告](RAG_V3_VALIDATION_DIAGNOSTICS.md)、[JSON](../reports/rag_v3_validation_diagnostics_v1.json)、[HTML](../reports/rag_v3_validation_diagnostics_v1.html)。本轮离线 Trace 均未调用网络、LLM、Provider，也未读取照片/人脸向量；这份验证结果不能替代真实用户 UI 图片回执。

## 2026-09-02｜Web 回执关联修复

第一位用户反馈的 `browser receipt request_ref does not match` 已定位为 Streamlit 重跑生命周期问题：
旧 page 6 每次重跑随机生成引用。现已按输入/参数 fingerprint 复用同代次 `request_ref`，签名刷新不重置
组件；旧回执仍 fail-closed。Web 专项新增 2 条回归，真实 Browser Receipt 仍待 Cloud Secrets 配齐。
