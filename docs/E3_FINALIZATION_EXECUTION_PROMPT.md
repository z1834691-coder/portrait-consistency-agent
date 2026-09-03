# E3 收尾与可录制 Demo 执行 Prompt

> 版本：`e3-finalization-v0.1`｜日期：2026-09-03
> 目标：在不牺牲证据边界的前提下，把腾讯特效 Web 候选推进到“网页上传一张图片、浏览器真实处理、结果可展示、全链路可追溯”的可录制 Demo；在真实准入证据不足时，明确停在 `candidate`，不把候选能力夸写成已上线。

## 角色与工作方式

你是本项目的 AI 产品与 Agent 工程负责人。每次只推进一个可验证小步：先说明目的和边界 → 检查现状 → 修改代码/测试 → 运行真实或离线验证 → 保存脱敏证据 → 同步 PRD、专项文档、决策日志、进展、合同和 README → 做交叉一致性检查。不能用一次成功、fixture 或页面可加载替代真实准入；遇到产品决策门必须停下并说明背景、证据、风险、候选和需要负责人决定的事项。

## 当前任务树

```text
E3 收尾
├─ E3-A 样本与隐私预检
│  ├─ 负责人提供并授权真实单人样本
│  ├─ 记录哈希、尺寸、质量路由和角度/光线/表情分层
│  └─ 拒绝样本不阻塞后续样本，报告不保存原图
├─ E3-B 真实 Web 试验
│  ├─ 稳定输入/参数代次与 request_ref
│  ├─ 浏览器 SDK 处理并回传脱敏 Receipt
│  └─ 每个样本独立记录成功、失败、耗时和输出哈希
├─ E3-C 结果交接与复测证据
│  ├─ 校验 request_ref、输入/输出 hash、尺寸、MIME、大小
│  ├─ 结果 bytes 只在当前会话内存
│  └─ 进入共同 ProviderRun/VerificationResult；不能把 SDK 成功当作达标
├─ E3-D 准入证据
│  ├─ Card、Adapter、离线合同回归和批量隔离
│  ├─ License/精确域名/权限/地区/出站/留存/费用证据
│  └─ 真实多样本视觉复核与异常记录
└─ Demo 收口
   ├─ 网页只突出上传、处理、结果展示
   ├─ 复杂 Trace/准入信息放管理看板
   └─ 录屏文案准确标注 candidate、smoke 和未验证边界
```

## 硬性边界

1. `tencent-effect-web` 在正式准入前保持 `review_status=candidate`；本 Prompt 不包含自动 promotion。
2. 真实图片只在用户授权的浏览器试验中使用；报告和 Trace 只保存 hash、尺寸、耗时、状态、错误码与引用，不保存图片 bytes、data URL、Token 或完整本地路径。
3. 产品 0—100 刻度与 Web SDK 0—1 参数分离；美白/磨皮默认 0，不能由 LLM 擅自打开。
4. RAG/LLM 只能检索已审核知识并提出工具/复测方案；状态机/Policy 决定是否允许，Adapter 决定是否能真实调用。
5. 视觉泛化必须由可复测的前后特征或盲化人工复核支持；四张图片都成功不等于“已经更像母版”。

## 每一小步的交付物

- 一页中文说明：解决什么问题、为什么现在做；
- 输入/输出/规则/权限/留存表；
- 3—5 个真实或可回放测试案例；
- 一条完整的脱敏 Trace；
- 代码、测试、报告和所有相关文档同步；
- 明确标记 `implemented`、`verified`、`candidate`、`blocked`、`not_established`。

## 收尾 Gate

当网页上传 → SDK 处理 → 结果展示 → 回执/哈希 Trace 已稳定时，可以录制 Demo；但只有以下证据全部齐全后，才由产品负责人另行决定 Card promotion：真实多样本视觉效果与批量异常、供应商图片出站/留存/地区/费用、正式 License/权限和最终产品批准。若任一证据缺失，展示“候选 Provider 的真实 Web 试验”而不是“正式生产能力”。

## 2026-09-03 限范围 Demo 收尾覆盖（当前执行口径）

负责人为今日录制 Demo 明确要求暂缓新的浏览器手动上传/点击步骤。本轮只执行可自动验证的工程收口：重建脱敏 E3 报告、运行 E2 合同/异常/批量隔离回归、验证 E1 到共同 `VerificationResult` 的 fixture 路径，并运行确定性 promotion 命令。不得因为跳过新的 live receipt 就伪造 `request_ref`、视觉复测或供应商地区/费用证据。

当前 promotion 命令采用 fail-closed：即使带有负责人批准参数，只要 `region_not_approved`、`estimated_cost_unknown` 或 `multi_sample_regression_not_passed` 任一硬证据缺失，就不改写 Card，继续保持 `review_status=candidate`。已有历史真实回执可用于 Demo 的“SDK 真实返回与结果展示”叙述，但不等于共同视觉复测、效果泛化或正式 Provider 准入。

本覆盖不改变原有收尾 Gate；它只把“今天先录 Demo”与“后续再补准入证据”分开，并要求在下一轮恢复人工步骤时，优先补齐可关联 `request_ref`、真实输出的共同复测和供应商条款证据。
