# 腾讯特效 Web SDK 纳入 Meta-Agent 的执行 Prompt

> 版本：`integration-v0.1`
> 用途：指导 Codex/工程 Agent 把已完成一次真实浏览器 Smoke 的 Tencent Effect Web SDK 纳入“工具知识卡 → 受限 Meta-Agent → 浏览器 Adapter → 回执 → 复测”的可追溯链路。
> 性质：工程执行指令，不是 Provider 准入批准；任何 `candidate → verified` 仍须产品负责人单独审核。

## 1. 背景

当前项目已经有一条可工作的主链：质量/安全/同人门 → IntentFrame → 8A 差异诊断与 EditPlan → 8B 确认 → Tencent BeautifyPic → ProviderRun → 8C 复测。Tencent Effect Web 是另一条浏览器 SDK 路线：图片进入浏览器，SDK 在浏览器处理，Python 只接收脱敏 Browser Receipt。此前结果捕获因错误调整 SDK Canvas 尺寸而失败；现已修复，并取得真实成功回执 `web_receipt_effect_web_4d58ea15a0794370`。

本任务的目标不是“把所有 SDK 参数都宣称可用”，而是把这条 Web 路线接入统一的工具知识、计划、权限、回执和复测控制面，使 Meta-Agent 能够在真实证据范围内提出和执行正确工具路径，同时在证据不足时安全停止。

## 2. 目标

1. 将 `data/provider_cards/tencent_effect_web.json` 作为独立、版本化的 Web 能力卡；不把移动/PC 细项能力移植成 Web 能力。
2. 将 Web Adapter 注册到统一 Tool/Provider Registry，明确其输入、参数映射、输出、状态、留存和失败码。
3. 让 Meta-Agent 在当前状态允许的工具集合内读取工具卡和 RAG advisory，提出 `tencent_effect_web/WebARImage` 候选；它不能自行制造权限、参数、回执或成功事实。
4. 在有效确认 scope、图片同意、预算、域名 License、Card 状态和 Adapter 条件均满足时，调用浏览器组件；否则返回可读的 fail-closed 原因。
5. 将 Browser Receipt 转换成统一 `ProviderRun`，保留输入/输出哈希、耗时、错误码、结果生命周期和父子计划关系，结果图只留浏览器会话。
6. 真实运行后按最终目标选择复测策略；VerificationResult 只能使用实际复测证据，不能把 SDK 成功回执等同于“已经更像母版”。

## 3. 非目标

- 不在本任务中把 Card 自动改成 `verified`。
- 不把 Web generic 的 `lift/shave/eye/chin` 扩写成唇厚、鼻翼、眼距、眉毛或耳朵能力。
- 不把移动/PC SDK 的宣传参数迁移到 Web 静态图路径。
- 不将原图、结果图、License Token 或完整用户文本写入 Python、SQLite、Trace、RAG 或 Git。
- 不让 LLM 计算视觉差异、生成绝对参数、签名、RequestId、ProviderRun 或权限结论。
- 不在 Cloud 页面把单次 Smoke 写成产品 KPI、效果通过或批量能力。

## 4. 受限 Meta-Agent 的职责分工

```text
用户文本/当前合同
  → IntentFrame Adapter：理解目标和约束
  → RAG/Provider Card：检索已审核的工具能力、限制和失败规则
  → Meta-Agent：在当前状态的 allow-list 中提出下一工具和理由
  → 状态机/Policy：校验状态、scope、同意、预算、Card、轮次和幂等
  → Web Adapter：确定性映射参数、生成签名、挂载浏览器组件
  → Browser SDK：真实处理图片
  → Receipt Validator：校验 request_ref、hash、尺寸、状态和错误
  → ProviderRun/Trace：保存事实
  → Verification：复测目标特征并决定 CLOSE/REPLAN/STOP/MANUAL_REVIEW
```

Meta-Agent 只能输出结构化 `ToolProposal`：`tool_id`、`reason_codes`、`evidence_refs`、`required_checks`、`execution_authorized=false`。最终放行权属于状态机和确定性 Policy；Adapter 只报告它真实执行了什么。

## 5. 阶段 Gate（一次只完成一个）

### Gate A：工具卡和 Registry

- Card JSON 通过 schema、版本、来源、参数和生命周期校验；`review_status` 仍为 `candidate`。
- Registry 同时列出 `tencent_beautify_pic`（已审核可执行）和 `tencent_effect_web`（候选/需准入）。
- 任何候选工具默认 `execution_allowed=false`，但可以被 Meta-Agent 读取并提出建议。

### Gate B：计划与权限桥

- 将 Web 候选映射到独立的 Web 请求合同，不复用 REST BeautifyPic 参数合同。
- 校验单人授权、当前图片处理同意、精确域名 License、APPID、签名、预算、结果保留和 scope。
- scope 不覆盖 Web Provider、出站方或用途时，返回授权缺失，不发送图片。

### Gate C：Meta-Agent 受限提议

- 给 Meta-Agent 的上下文只包括结构化合同、审核证据和安全错误；不包括照片、向量、密钥或隐藏思维链。
- RAG 只提供直接证据/参考信息/冲突信息；冲突或检索不到时不能猜测。
- 记录 proposal、采用/拒绝原因和最终状态机决定，不能让 LLM 直接调用组件。

### Gate D：真实执行和回执

- 真实执行使用 page 6 的浏览器组件；`takePhoto()` 的 `ImageData` 写入独立结果 Canvas。
- Browser Receipt 必须与 prepared request 的 `request_ref` 和输入 hash 一致；不一致则拒绝入账。
- 成功回执只说明 SDK 返回了结果；失败回执保留安全错误码；每次明确点击有独立 attempt 事实。

### Gate E：复测与产品准入

- 复测按照最终用户目标选择策略；CompareFace 只证明同人辅助证据，不能代替几何一致性复测。
- 只有结构化 VerificationResult、真实回执、多样本回归、隐私/区域/费用证据和产品负责人批准齐全，才讨论 Card promotion。

## 6. 验收清单

### 工程验收

- [ ] `ProviderCard → Tool Registry → Meta-Agent proposal → Policy Gate → Adapter → Browser Receipt → ProviderRun` 可以回放。
- [ ] 成功、鉴权失败、输入图失败、Canvas 捕获失败、request_ref 错位各有测试。
- [ ] RAG miss、冲突、候选 Card、scope 缺失均 fail-closed。
- [ ] 所有失败都产生可读 reason code 和脱敏 Trace；不泄漏 Token、原图或隐藏思维链。
- [ ] 单次调用不会被 Streamlit rerun 重复扣费；同一请求代次的幂等和旧回执隔离可验证。

### 产品验收

- [ ] 页面只让用户完成必要的上传/同意/结果反馈动作，工程检查在后台运行。
- [ ] 用户看到的是“本次处理做了什么、结果是否可用、为什么停止”，不是脱敏 JSON 或内部状态码。
- [ ] 单次真实成功不宣称“全部五官已支持”“已达到母版一致”或“Provider 已正式上线”。
- [ ] 产品负责人可以从 Trace 追溯：为什么选 Web、使用了哪张 Card、哪项 Policy 放行、SDK 返回了什么、为何复测/停止。

## 7. 出现问题时的探索顺序

1. 先检查合同和请求代次是否一致；不先重复调用。
2. 再检查浏览器 Console/安全错误码和 SDK 生命周期；不把前端异常归因于权限。
3. 再核对 APPID、License、签名和精确域名；Token 只从 Secrets 读取。
4. 再核对供应商能力、区域、留存、成本和并发证据；缺证据保持 candidate。
5. 最后才考虑代码变更；每次只改一个原因，补一个回归案例和一条 Trace。

## 8. 输出格式

每个 Gate 完成后必须输出：

1. 中文说明：本 Gate 解决什么问题；
2. 输入/输出/规则与权限表；
3. 用户必须决定的事项与默认安全行为；
4. 3—5 个真实或可回放测试案例；
5. 一条完整脱敏 Trace；
6. 代码、测试、Card、PRD、专项文档、`DECISION_LOG.md`、`DEVELOPMENT_PROGRESS.md` 和 README 的同步结果；
7. 明确区分 `implemented`、`verified`、`candidate`、`blocked`、`not_run`，不夸大能力。

## 9. 本轮执行增量（2026-09-02）

### 已落地的第一条纵向切片

<span style="color:#C00000"><strong>已实现。</strong>新增 `services/tool_registry.py` 与 `services/meta_agent.py`。Registry 读取已审核的 `tencent_beautify_pic` Card 和仍为 `candidate` 的 `tencent_effect_web` Card，生成只读 `ToolDescriptor`；Meta-Agent 以结构化 `ToolProposal` 输出候选工具、Card 版本、所需检查、RAG 证据引用和 baseline 兜底。它不读取图片、不持有密钥、不生成修图数值、不创建 `ProviderRun`，`execution_authorized` 永远为 `false`。</span>

### 当前真实行为

```text
请求功能：face_lifting + eye_enlarging
→ Registry 发现 BeautifyPic（verified）与 Effect Web（candidate）
→ 显式偏好 Web 时提出 WebARImage 候选
→ 检查 candidate_not_admitted
→ 同时给出 BeautifyPic baseline 兜底
→ 不调用浏览器、不发送图片、不创建 ProviderRun
```

离线 smoke `scripts/smoke_meta_agent_tool_routing.py` 已输出完整脱敏 Trace；专项测试覆盖 baseline、Web candidate、RAG 冲突、未知能力和无副作用边界。该切片证明“工具卡 → 受限 Meta-Agent”已经可回放，但不等于 Web Card 已 promotion，也不等于 Web 结果图已经能直接进入现有 Python `VerificationResult`。

### 不能静默绕过的下一道 Gate

当前 `EditPlan` 仍是 BeautifyPic 专用合同，Web Receipt 只含浏览器元数据而不含结果图 bytes。若要把 Web 真正作为主流程执行器并接入现有 8A/8B/8C，需要负责人在以下结果交接方案中明确选择：

* **A：浏览器端复测。** Web 结果不回 Python，由浏览器端返回经过验证的几何事实和 hash；隐私边界最好，但要新增并校准 JS 与 Python 的测量一致性。
* **B：一次性受限回传。** Web 结果 data URL/bytes 只回 Python 做既有复测；复用率高，但会改变当前 `python_receives_image=false`、留存、删除和部署安全边界。
* **C：Web 只做展示/下载。** 主 Agent 继续调用已验证的 BeautifyPic；最安全、最快，但不能称 Web 已完成主流程接入。

在该 Gate 冻结前，本 Prompt 要求继续完成 Card/Registry/Proposal/Trace 和离线回归，但禁止把 candidate 工具自动放入真实图片主链。
