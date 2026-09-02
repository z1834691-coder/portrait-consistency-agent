# 腾讯特效 Web SDK 全链路接入执行 Prompt

> 版本：`web-full-integration-v0.1`｜日期：2026-09-02
> 用途：把腾讯特效 Web SDK 从独立候选试验接入统一工具卡、Meta-Agent、EditPlan、ProviderRun 和 8C 复测链。
> 这是一份工程执行 Prompt，不是把 Provider Card 自动批准为线上工具的授权。

## 角色与工作方式

你是本项目的 Agent 编排、图像工具集成和质量工程负责人。你要先读取执行版 PRD、产品规则、合同、Agent Prompt、Web Adapter 专项文档、探索树、代码、测试和真实回执，再按小步骤实现。每一步都要先说明目的和边界，写代码，运行测试，保存脱敏 Trace，更新相关文档；不能把历史候选记录覆盖成当前事实。

## 当前问题

项目已有 `质量/安全/同人门 → IntentFrame → 8A EditPlan → 8B → BeautifyPic → 8C VerificationResult` 主链。腾讯特效 Web 是另一种浏览器 SDK：图片在浏览器处理，Python 只接收回执。此前已修复 SDK Canvas 被重复调整导致的运行错误，并取得一次真实成功 Browser Receipt，但它仍是 `candidate`。当前要解决的不是“再调用一次 SDK”，而是让 Web 的参数、权限、回执、结果图和复测可以进入同一个可审计系统，同时保留已验证 BeautifyPic 作为 baseline。

## 目标链路

```text
用户文本/IntentFrame
  → RAG 检索审核过的工具知识（只能提议）
  → Meta-Agent 输出 ToolProposal
  → 状态机与 Policy 校验 scope、同意、Card、预算、轮次、幂等
  → EditPlan 选择 Web 或 Beautify 参数模型
  → 浏览器 SDK 处理图片
  → 校验 request_ref、输入/输出 hash、尺寸、MIME、大小和状态
  → 结果 bytes 只在当前会话内存
  → 共同 VerificationResult/8C 复测
  → 多样本、异常和批量隔离回归
  → 人工准入证据齐全后才可 candidate → verified
```

## 不可突破的边界

1. `tencent_effect_web` Card 仍为 `candidate`；Meta-Agent 可提出它，不能自行授权。候选试验必须显式传入 `allow_candidate_trial`。
2. `EditPlan` 允许 `tencent_beautify_pic` 和 `tencent_effect_web` 两种 Provider，但参数合同不可混用：产品强度为 0—100，Web SDK 参数由 Adapter 确定性转换为 0—1。
3. RAG/LLM 只负责检索、解释和提出工具/复测策略；不生成视觉事实、绝对参数、权限、回执或成功结论。最终放行仍由状态机、Policy 和 Adapter 负责。
4. 浏览器回传只做一次性 handoff。Python 必须验证请求代次、输入 hash、回执输出 hash、尺寸、MIME 和大小，并立即把结果作为内存 bytes 交给既有复测器；data URL、图片 bytes、密钥和完整用户文本不得进入数据库、Trace、RAG 或 Git。
5. SDK 成功不等于母版一致。只有结构化 `VerificationResult` 和实际复测证据才能给出改善、无变化、变差或无法判断。
6. 没有多样本/批量、供应商图片留存/地区/费用和负责人准入证据时，BeautifyPic baseline 继续是唯一正式主流程 Provider。

## 分阶段任务与验收

### B1 合同桥

让 Web 参数、Provider、operation、Card/version 能进入 `EditPlan` 和 `ProviderRun`。覆盖合法/越界/错配参数、历史 BeautifyPic 回归。验收：错误输入 fail-closed，旧测试不回归。

### B2 结果 handoff

浏览器使用独立结果 Canvas，先发送临时结果 data URL，再发送脱敏 Receipt。服务端验证后只保留当前会话 bytes。验收：成功结果能构造共同 `ProviderRun`；请求错位、hash 错位、尺寸/MIME/大小异常、失败回执都被拒绝；Trace 无图片。

### B3 Meta-Agent 纵向回放

Registry → RAG advisory → Meta-Agent → candidate proposal/fallback 的链路可回放。验收：proposal 有 Card、证据和 reason code，但永远 `execution_authorized=false`，不创建 `ProviderRun`。

### E1 共同 VerificationResult

把 Web handoff 结果交给与 BeautifyPic 相同的观察器和 8C 复测器。验收：至少一条 handoff → ProviderRun → VerificationResult 的完整脱敏 Trace；没有总分、概率或未经证据支持的“达标”。

### E2 多样本、异常与批量隔离

覆盖成功、供应商失败、请求/输入/输出 hash 错位、非法 MIME、尺寸不一致、超限和“批量中一张失败”。每张样本单独判定，坏样本不阻塞其他样本，报告不保存结果图。验收只说明合同与隔离可靠，不说明视觉效果已泛化。

当前离线套件已落为 8 个样例：1 个成功、1 个供应商失败、6 个拒绝（请求/输入/输出哈希、尺寸、MIME、大小）。样例顺序特意让拒绝样例之后仍有有效回执，独立验证 `batch_failure_isolation_passed`，不把“坏样例在末尾”误当成批量隔离通过。

### E3 Card promotion

静态图真实回执、多样本和批量回归、精确域名、License、权限、出站/地区/留存、费用/预算、Adapter readiness 和产品负责人批准全部齐全后，才允许人工把 Card 改为 `verified`。代码和 LLM 不得自动 promotion。

## 每步必须输出

- 一页中文说明：解决什么问题；
- 输入、输出、规则、权限和留存表；
- 仍需产品负责人决定的事项；
- 3—5 个实际或可回放案例；
- 一条完整脱敏 Trace；
- 更新执行版 PRD“产品设计”、专项文档、合同、Prompt、`DECISION_LOG.md`、`DEVELOPMENT_PROGRESS.md`、README、代码和测试；
- 清楚标记 `implemented`、`verified`、`candidate`、`blocked`、`not_run`。

## 失败与回滚

先定位合同/请求代次，再定位浏览器生命周期，再核对 APPID、License、签名和域名，最后才改代码。每个修复只针对一个根因并新增一个回归案例。真实 SDK 或供应商证据失败时，追加原始脱敏回执，保持 Web candidate，恢复到 BeautifyPic baseline；不删除历史证据、不放宽校验、不重复无意义调用。
