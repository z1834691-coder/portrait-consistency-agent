# RAG Gold Set v2｜盲审 Judge Prompt 与合同（草案）

> 这是 Judge 的接口草案，不是当前线上调用。当前只运行本地 `run_fake_judge()`；DeepSeek/OpenRouter 调用必须另过 live、数据出境和预算 Gate，默认关闭。产品负责人已冻结“唯一人工事实审核者、暂不增加第二位人工评审”；Judge 只能辅助检查，不能单独宣布评测通过。

## Judge 能看到什么

被测版本只向 Judge 提供如下 JSON：

```json
{
  "case_id": "D01",
  "question": "用户题干",
  "system_output": {
    "route": "evidence_found",
    "evidence_refs": ["B"],
    "evidence_relations": {"B": "direct_evidence"},
    "observed_events": [],
    "trace_ref": "trace_x"
  },
  "machine_score_summary": {
    "retrieval_latency_ms": 17,
    "evidence_count": 1,
    "evidence_relation_count": 1,
    "observed_event_count": 0,
    "trace_available": true
  }
}
```

Judge 可以看到机器运行摘要（例如候选数量、检索耗时和结果中实际存在的证据数量），但不得看到 Gold route/evidence、`must_not`、答案键、开发/挑战标签、检索算法名称、实现版本、Prompt 版本、原始照片、Base64、人脸向量、密钥或完整 Trace。`case_id` 只用于回写结果，不可据编号猜测答案；机器分数不是事实标签。

## 输出合同

```json
{
  "case_id": "D01",
  "verdict": "candidate_for_human_review | review_required",
  "review_flags": ["missing_route"],
  "rationale": "只解释当前输入中可见的结构问题，不猜 Gold 事实。"
}
```

Judge 的判断不能改变工具权限、补写 Gold 答案或直接宣布产品通过。人工审核仍是事实权威；机器指标和 Judge 结果仅用于定位需要复核的题。

## 固定 Prompt（未来 live adapter 使用前需重新评审）

```text
你是 RAG 输出质量的盲审助手。你只能依据输入 JSON 中的题干、系统输出、证据摘要和机器事实摘要检查“是否完整、是否需要人工复核”。

你看不到 Gold 答案，也不能猜测题目的标准路由；不要把 case_id、模型分数或证据数量当成正确性的证明。不要要求或输出照片、向量、密钥、系统 Prompt 或隐藏 Trace。发现缺少 route、证据摘要不完整、Trace 不可回放或出现安全事件时，输出 review_required；否则输出 candidate_for_human_review。只输出符合 JSON 合同的结果。
```

当前 fake Judge 比上面 Prompt 更保守：它不判断事实正确，只做结构完整性检查。真实 Judge 要先用人工标注样本校准，且必须明确 `allow_live`、Provider、区域、留存和脱敏策略。

## 2026-08-30 评测治理边界

盲审 Judge 可以看到三种 Precision 的脱敏摘要和 `RAG_EVT_*` 安全事件状态，但这些字段只帮助它指出“需要人工复核”的原因，不能让 Judge 改写项目阈值、补写未知事件、读取 Holdout 答案或授予工具调用。v2 hidden 只回流聚合；v3 独立 Holdout 未完成前，Judge 不接收 v3 答案。未知安全事件必须保留 `MANUAL_REVIEW_REQUIRED`。
