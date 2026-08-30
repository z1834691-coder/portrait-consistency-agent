# 检查点 8C｜修后复测、计划族续跑与验证策略选择

> 状态：8C-1/8C-2 已完成离线验证｜版本：`verification-v0.1` / `verification-selector-v0.1` / `plan-family-planner-v0.1`｜日期：2026-08-28

## 这一模块解决什么问题

8B 只能证明“用户确认后，腾讯 BeautifyPic 返回了一张结果图”，还不能证明结果是否朝母版目标改善。8C-1 把结果图重新交给同一套本地质量/几何观察器，按 `EditPlan` 里真正执行的特征逐项比较修前差异和修后差异，再给出“改善、无变化、变差、无法判断”的事实判断。8C-2 再把受限的 `REPLAN` 落成可审计的下一步：只有真实父回执、改善证据、结果图 hash、原确认范围、期限和轮次同时通过，才生成一份新的子计划；在首次外部处理同意已经覆盖照片、用途、Provider、预算和轮次的前提下，系统写入自动 preflight 后直接发起下一次腾讯调用，不再逐轮要求用户点击。若用途、Provider、出境范围、预算或同意状态发生变化，则先停止并重新授权。它不计算总分、不输出接受概率，也不把“腾讯能改什么”自动当成“任务完成”。同时，`VERIFICATION_STRATEGY_SELECT` 先以一个可替换的确定性基线落地：在允许列表里优先提出本地几何复测；无法测量时降级人工复核；未来接入 RAG/LLM 时，只替换“提出建议”的一层，状态、权限和真实工具放行仍由系统控制。

## 输入、输出和规则

| 项目 | 输入 | 输出/规则 |
|---|---|---|
| 结果观察 | 8B 成功 `ProviderRun` 的结果图片字节（只在内存） | 解码状态、单脸数量、可测特征、质量标记、特征提取版本；不保存像素和原始坐标 |
| 策略提议 | 结构化观察事实、版本化策略白名单 | `VerificationStrategyProposal`；当前默认只启用 `local_geometry`、`manual_visual_review`，提议不是权限，也不会调用外部 API |
| 特征比较 | Profile 归一化特征、EditPlan 修前 `normalized_gap`、修后观测值 | 每个目标特征的 `before_gap`、`after_gap`、测量可靠性和趋势；没有可靠证据就 `unverifiable` |
| 总体路由 | 各可执行目标特征趋势、结果可用性、计划轮次和用户显式反馈 | `VerificationResult`：`CLOSE/REPLAN/STOP/RESHOOT/MANUAL_REVIEW` 与原因码；不展示指数或概率 |
| 继续条件 | 当前轮次低于 Safety Policy 上限，且方向正确、可验证、目标尚未达到 | 只提出新一轮方向；下一轮必须使用新的 plan revision/ProviderRun，不能重试原计划 |
| 变差/无法判断 | 任一必验特征变差、结果解码失败或必验特征不可测 | 变差优先停止并要求回退/人工复核；无法判断走重新上传/重拍；不继续叠加参数 |
| 保持项 | 妆面、肤色、背景等尚无可靠自动测量 | `preserved_attributes_verified=false`，明确告知“本轮未自动验证”，不假装保持不变 |

## 本模块不由产品负责人重新决定的工程默认

- `measurement_tolerance=0.01`：修前/修后相对差异变化不超过 1 个百分点，记为“无变化”；这是可替换的工程基线，不是校准概率。
- `target_gap_tolerance=0.04`：所有本轮可执行特征的修后差异都不超过 4%，才产生结构化“目标证据足够”；仍需等待用户反馈，不等于用户满意。
- 最低测量可靠性 `0.80`；策略白名单当前启用本地几何和人工复核，外部/混合策略已写入合同但尚未接入结果图出站 Adapter。
- 8B 的结果字节仍只在 Streamlit 当前会话内存；SQLite/JSONL 只保存脱敏 VerificationResult 和 Trace。

## 5 个实际测试案例

1. **改善但未达到目标**：修前 gap `0.12`，修后 gap `0.05`，得到 `IMPROVED → REPLAN`，下一轮必须新建计划版本。
2. **结构化目标证据足够**：修后 gap `0.03`，得到 `IMPROVED + target_evidence_sufficient=true → CLOSE/GOAL_MET`；没有概率字段，等待用户反馈。
3. **结果变差且有回退引用**：修后 gap `0.20`，得到 `WORSENED → STOP/RESULT_WORSENED`，携带 `last_known_good_artifact_ref`。
4. **结果变差但没有回退证据**：不强行宣称可回滚，得到 `MANUAL_REVIEW`，明确缺少上一张已知良好结果。
5. **结果无法解码/没有可比较的人脸**：得到 `RESHOOT/INPUT_NOT_COMPARABLE`，不产生“达标”结论。

## 一条完整 Trace（脱敏示例）

```text
observe_result
  → 收到 8B ProviderRun 的结果字节（只在内存）
  → decode_ok=true，face_count=1，提取 face_width_height_ratio
verification_strategy_select
  → allowed=[local_geometry, manual_visual_review]
  → selected=local_geometry
  → reason=result_decoded, single_face, local_geometry_measurable
compare_features
  → before_gap=0.12，after_gap=0.05，confidence=0.92
  → trend=improved（变化 0.07，大于 tolerance 0.01）
route
  → target_evidence_sufficient=false（修后 gap 仍大于 0.04）
  → decision=replan；no_improvement_streak=0
persist_verification
  → 保存 verification_id、趋势、策略、原因码和 result_artifact_ref
  → result_bytes_persisted=false；未写入 SQLite/JSONL/Trace
```

## 当前已知边界

8C-1 已能对真实 8B 返回图做本地解码和几何复测；本轮还对仓库中保留的历史 BeautifyPic JPEG 做了只读本地观察，结果为可解码、单脸、可提取 18 个归一化特征。8C-2 已实现自动**生成、执行并复测**下一轮子计划、父子回执血缘和结果页点赞/点踩/文字 hash 反馈；当前命令行回归仍使用 `fixture_only=true`，没有新增腾讯图片调用，因此这不构成新的 8C live receipt，也不能证明视觉改善。RAG P0-C 已在 8C 策略前提供受限 evidence advisory（只提议、不授权）；LLM 自由策略、CompareFace/混合复测、批量照片路由和多脸隔离仍待后续 Gate。任何未来策略都必须先通过白名单、权限、预算和真实 Adapter，不能让 LLM 自由调用工具。

## 8C-2：计划族续跑与反馈硬停止

| 项目 | 输入 | 输出/规则 |
|---|---|---|
| 子计划 preflight | 父 `EditPlan`、成功 `ProviderRun`、`VerificationResult`、初始确认、Profile、结果字节 | 只接受 `REPLAN + improved + cumulative_improvement=true`、hash/范围/期限/轮次一致且无质量/拒绝信号；否则只输出阻断原因，不调用腾讯 |
| 子 `EditPlan` | 已复测结果图、仍有 gap 的可执行特征、`followup_mapping_v0` | 新 `plan_id`、`parent_plan_id`、iteration+1、结果图 hash；每个合格特征 2—6 的新输入图单次强度，不累计上轮腾讯参数 |
| 子 `ProviderRun` | 子计划 + 父结果图 | 新 run，写 `parent_run_id`、父结果 `input_artifact_ref/hash`；每个计划一次尝试，首次同意 scope 有效且 preflight 通过后自动调用；不逐轮点击 |
| 显式反馈 | 点赞、点踩或文字 | 写脱敏 `ProductEvent`；点踩/文字关闭当前计划族，文字只保留 hash，不能直接变成新参数 |
| 回退预览 | 变差的复测结果 + 本会话内已知良好图 | 有内存图则显示；无图则如实提示，绝不为了回退重调腾讯 |

### 8C-2 五个实际测试案例

1. 子计划使用新 `plan_id`、`parent_plan_id` 和上一结果图 hash，参数是 2—6 的新输入图单次强度；
2. 子轮执行回执指向父 run，输入不是最初上传图；
3. 明确点踩在任何下一次外部调用前阻断；
4. Safety Policy/确认 scope 的三轮上限阻断第四轮；
5. 文字反馈在 Trace 中只有 SHA-256，不含原话。

### 8C-2 完整 Trace（fixture）

```text
fixture_only=true；network_called=false
parent_run_succeeded
→ verification: before_gap=0.12, after_gap=0.05, improved, replan
→ plan_family_preflight: run/verification/hash/scope/round checks passed
→ followup_plan: iteration=2, parent_plan_id=..., FaceLifting=2, EyeEnlarging=3
→ auto_followup_preflight: scope/hash/round/budget passed; execution_trigger=auto_bounded_followup
→ child_run: parent_run_id=..., input_artifact_ref=parent result reference; one bounded call
→ feedback_dislike: plan family closed, no further provider call
```

这条 Trace 证明代码的控制边界和血缘记录，不证明真实腾讯调用或视觉效果改善。
