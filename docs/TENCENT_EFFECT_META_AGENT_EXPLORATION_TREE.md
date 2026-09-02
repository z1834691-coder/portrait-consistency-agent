# Tencent Effect Web → Meta-Agent 探索树

> 更新时间：2026-09-02
>
> 这是一份工程推进树，不是把候选能力直接写成已上线能力。每个分支都保留独立证据和回滚点。

```text
腾讯特效 Web SDK 纳入母版人像一致性 Agent
│
├─ A. Provider Card / Registry
│  ├─ A1 读取 Web Card、版本和能力字段              ✅ 已实现
│  ├─ A2 与 verified BeautifyPic baseline 并列登记    ✅ 已实现
│  └─ A3 candidate 不自动变成 execution_allowed      ✅ 已测试
│
├─ B. RAG / Meta-Agent 提议
│  ├─ B1 消费 direct/reference/conflict evidence      ✅ 已接入 8A
│  ├─ B2 输出 ToolProposal（工具/Card/检查/原因）     ✅ 已实现
│  ├─ B3 RAG conflict / unknown fail-closed           ✅ 已测试
│  └─ B4 proposal 不创建 ProviderRun/不发网络        ✅ 已测试
│
├─ C. 计划与执行合同桥（下一道产品 Gate）
│  ├─ C1 维持 BeautifyPic 专用 EditPlan               ✅ 当前安全基线
│  ├─ C2 浏览器端返回几何证据                          ⏸ 方案 A，待冻结
│  ├─ C3 Web 结果一次性回传 Python                    ⏸ 方案 B，改变隐私边界
│  └─ C4 Web 只展示/下载，主链继续 BeautifyPic         ⏸ 方案 C，最小风险
│
├─ D. Web Adapter / Browser Receipt
│  ├─ D1 Canvas 生命周期修复                           ✅ 已实现
│  ├─ D2 官方示例图真实浏览器 Smoke                   ✅ 成功一次
│  ├─ D3 Receipt request_ref/hash 合同校验             ✅ 已实现
│  └─ D4 多样本效果、供应商条款/区域/成本准入          ⏳ 待补证据
│
└─ E. 主流程准入
   ├─ E1 结果图接入现有 VerificationResult              ⏳ 依赖 C 选择
   ├─ E2 多样本回归、异常和批量能力                     ⏳ 待开发
   ├─ E3 Card promotion：candidate → verified            ⏳ 需负责人批准
   └─ E4 生产级公网/长期留存                              ⏳ 不属于本步
```

## 当前节点的真实边界

- A、B 已经能在本地无副作用地回放：请求 `face_lifting + eye_enlarging` 且显式偏好 Web 时，系统会指出 Web 候选、列出准入检查，并给出 BeautifyPic baseline fallback。
- D2 的成功 Browser Receipt 只证明一次浏览器 SDK 处理和脱敏回执，不证明五官一致性、批量能力或供应商合规准入。
- C 是唯一会改变图片交接和主流程权限的产品决策门。没有负责人选择 A/B/C，不修改 `EditPlan`、`execute_confirmed_plan` 或现有 Web 图片留存边界。

## 每个分支的回滚点

Registry/Meta-Agent 可整体移除而不影响现有 BeautifyPic 主链；8A 与 page 6 只读取提议和写入脱敏事件，不依赖候选 Web 结果。若后续 Gate 失败，恢复到“BeautifyPic baseline + Web 独立 Spike”即可，不需要迁移六类图片业务合同。

## 2026-09-02 当前覆盖｜B / E1 / E2 已完成，E3 保持准入门

历史树中的 C1—C4 与 E1/E2“待冻结/待开发”状态已被本节覆盖：

```text
Web Card → ToolRegistry → Meta-Agent ToolProposal（candidate/proposal-only）
        → Web EditPlan（独立 0—1 provider snapshot）
        → candidate trial policy
        → Browser Receipt + 一次性 result handoff B
        → 共同 ProviderRun → VerificationResult
        → E2 多样本/异常/批量失败隔离回归
        → E3 candidate → verified（仍待真实证据与负责人批准）
```

- B 已冻结并实现：Web result 只短暂回 Python 内存，data URL/bytes 不落账；request_ref、输入/输出 hash、尺寸、MIME 和大小均由 Adapter 校验。
- E1 已验证：Web handoff 可以进入共同 `ProviderRun → VerificationResult`；无可测人脸时如实返回不可验证/重拍路径。
- E2 已验证：8/8 fixture 样本通过，覆盖输入哈希/大小异常，失败样本不阻塞后续样本；该结果是合同/隔离证据，不是视觉泛化。
- E3 仍是唯一主流程准入门：必须补真实多样本、供应商隐私/区域/留存/费用和产品负责人批准。若失败，回滚到 BeautifyPic baseline + Web 独立 Spike。
