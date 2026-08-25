# 六个数据合同

## 目的

合同是各模块之间的“统一表格”。视觉工具、LLM、规划器、数据库、腾讯 API 适配器和界面只能读写明确的字段，因此任何一步都能回放、测试和定位错误。

| 合同 | 产生者 | 消费者 | 绝不包含 |
|---|---|---|---|
| `ReferenceProfile` | 母版确认模块 | 诊断、规划、会话 | 原图、完整人脸向量 |
| `PhotoQualityResult` | 质量门 | 路由、报告 | 原图、关键点数组 |
| `IntentFrame` | LLM/模板澄清层 | 状态机、规划器 | 执行后的假回执、原图 |
| `EditPlan` | 确定性规划器 | 用户确认、API 适配器 | 密钥、未受支持参数 |
| `ProviderRun` | 腾讯 API 适配器 | 验证器、trace、bad case | Base64 图片、SecretId/SecretKey |
| `VerificationResult` | 确定性复测器 | 状态机、报告、评测 | 未经计算的“应该变好” |

## 核心规则

1. `IntentFrame.action=execute` 必须具有确认状态和确认 token；确认前不能产生外部写操作。
2. `TencentBeautifyParams` 的四个值始终显式存在、范围为 0—100，避免误用腾讯的非零默认值。
3. `EditPlan.user_deltas` 是用户可理解的相对变化；`provider_absolute_params` 是发给 API 的最终绝对值，两者不能混用。
4. `ProviderRun` 成功时必须记录腾讯 `RequestId`、结果引用和耗时；失败/超时时必须有错误码。
5. `VerificationResult.index_delta` 必须等于修后指数减修前指数，不能由 LLM 填写。
6. 所有模型禁止额外字段；新增字段必须升级合同版本、写入决策日志并补测试。

## 当前未由合同解决的事情

- 特征如何计算、指数权重如何校准；
- 腾讯凭据、预算和真实 API 调用；
- 具体 LLM 提供商、Prompt 与上下文记忆；
- 数据库表、删除任务和部署。

这些会在后续检查点以独立实现和独立测试完成，不能借合同完成就声称已经跑通。
