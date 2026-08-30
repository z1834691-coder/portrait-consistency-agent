# RAG Gold Set v2｜隐藏答案键保管回执

> 状态：**已于 2026-08-30 移出开发工作区。** 本文件不包含 H01—H20 的题干、Gold evidence、Gold route、`must_not` 或任何答案内容。

## 已完成的隔离

- 运行器继续只读取 `data/evaluation/rag_gold_v2_holdout_runtime.json` 中的 `case_id + query`；
- 隐藏答案键已由产品负责人保管在本机 Documents 下、项目仓库之外的受限目录；
- 目录权限设为仅所有者可访问，答案文件权限设为仅所有者读写；
- 本项目仓库、RAG 索引、评测脚本、报告和自动化测试均不再包含或读取该答案键。

## 评测流程

```text
无答案 holdout 运行包
→ 被测系统生成脱敏 predictions
→ 运行器输出结果包（不含答案）
→ 产品负责人使用私有答案键比对
→ 只将聚合指标、错误类型和必要的脱敏案例回流给开发
```

## 审计边界

- 本文件只能证明保管流程，不证明评测已经通过；
- 隐藏答案不进入训练、切片、向量索引、Prompt、Trace 或 LLM Judge 输入；
- 若答案键发生修改、复制或版本升级，必须新建版本并重新记录保管事件；
- 当前知识快照为 `rag-v2-current-tencent3`；新增 Provider 后应新建 Gold Set 版本，不能回写本版答案。

## 2026-08-30 生命周期更新

按 Holdout A 决策，本 v2 包和它的 aggregate 只作为历史泛化诊断，不再用于逐题调参。新的独立验收包使用 [v3 保管说明](RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md) 和 `data/evaluation/rag_gold_v3_holdout_runtime.template.json`；v3 答案键必须在项目工作区外独立生成、确认和保管。
