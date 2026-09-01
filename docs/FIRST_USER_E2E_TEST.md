# 第一位用户端到端测试说明（Streamlit Private Beta）

> 状态（2026-09-01）：第一位用户已完成母版/目标照安全检查、Profile 建立和当前会话同人检查；在 8A 因 CompareFace `uncertain` 缺少确认入口而暂停。代码已补齐一次性本人/编辑权确认路径，等待 Cloud 重建后继续 8A→8B→8C。第一位用户仍由产品负责人本人完成操作。

## 测试入口与边界

入口：<https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app>

这是 Streamlit Community Cloud 的 Private 应用。打开后若出现登录或邀请提示，先用已获邀账号进入。Cloud 容器位于美国，真实照片上传前必须确认自己接受当前受邀测试范围和数据出境边界；只上传本人、已获授权且不含未成年人或未获授权他人的照片。

## 假设自己什么都不知道，按这个顺序开始

1. 在“候选母版”上传一张单人、正面或接近正面、清晰、眼睛可见的 JPG/PNG。先阅读页面的图片要求和授权提示。
2. 按页面提示完成内容安全检查；通过后锁定母版并建立档案。母版锁定后不能在页面里直接二次编辑，想更换母版要重新上传一张候选图。
3. 在“目标照片”上传另一张本人照片，完成内容安全和当前会话同人检查。若质量、多人或同人证据不足，页面会说明原因，不要反复点击同一个按钮；若显示同人 `uncertain`，且确实是本人并有权编辑，可勾选一次性确认后继续，不能把它理解为系统已证实同人。
4. 在自然语言输入框直接说目标，例如：“把这张照片向我的母版靠拢，保留妆面，能自动调整的就帮我处理。” 不需要先填写固定问卷。
5. 先观察 Agent 的意图理解、差异解释和计划摘要。首次真实修图前，只有页面明确出现授权/确认入口并由你点击，系统才允许调用 Tencent BeautifyPic；不要把参数当成需要自己计算的滑杆。
6. 看到结果图后，点击“开始修后复测（8C）”。系统会在当前会话内观察结果是否可解码、是否仍为单脸，以及已执行的脸型/眼睛特征是否朝母版方向改善。
7. 如果首轮改善但仍有可验证差距，且原来的照片、用途、Provider、预算和轮次范围仍有效，8C-2 会自动生成新的子计划、调用一次并复测；你不需要每轮再次点击参数。范围变化、反馈不满意或风险信号出现时会停止。
8. 最终结果页可以点赞、点踩、下载或在对话框说明问题。文字原文不进入 Trace，只保存不可逆 hash；点踩或明确不满意会关闭当前计划族。

### 如果腾讯内容安全检查失败

如果页面显示 Tencent ImageModeration 调用失败，先不要重复点击。新版页面会显示腾讯 `error_code` 和 `RequestId`，并在当前会话 Trace 中保留同样的脱敏字段；把这两项记录下来即可。`UnauthorizedOperation` 通常指向腾讯账号/服务权限，`InvalidParameter` 或类似参数错误则需要按具体回执排查。无论哪种失败，系统都会停止放行，不会继续锁定母版或发送到修图接口；不要把密钥、原图或完整腾讯错误正文发到聊天中。

### 如果 CompareFace 显示“同人不确定”

这不是系统把你判成了别人，也不是可以忽略的“通过”。在确认这是本人且你有权编辑后，勾选页面的一次性确认，再生成 8A 计划；系统会把确认和策略版本写入脱敏 Trace，但保留 `uncertain` 原事实，不更新长期主体锚点。若显示 `no_match`，仍必须重新检查/上传，确认不能绕过。

## 哪些动作由你完成，哪些由系统完成

| 由第一位用户完成 | Agent/系统自动完成 |
|---|---|
| 登录 Private 应用、选择测试照片、阅读并勾选授权 | JPG/PNG 解码、尺寸/清晰度/曝光/人脸可见性检查 |
| 点击安全检查、同人检查、必要时确认“本人且有权编辑”、锁定母版和首次外部执行确认 | IMS 内容安全、当前会话 CompareFace、Profile 归一化几何提取 |
| 用人话描述希望保留或改变什么 | IntentFrame 解析（DeepSeek 可用时）或本地模板 fallback |
| 结果页点赞、点踩、下载或描述不满意 | RAG 只查已审核工具知识并留下 evidence；不会获得执行权限 |
| 必要时停止测试并把页面显示的问题告诉项目负责人 | 8A 生成计划、8B 单次 ProviderRun、8C 复测、同 scope 内受限续跑和脱敏 Trace |

## 预期的可追溯事件顺序

```text
session_started
→ reference_uploaded / quality_checked
→ content_safety_checked / subject_match_checked
→ reference_profile_saved
→ target_uploaded / quality_checked
→ subject_match_uncertain_acknowledged（仅当目标照 CompareFace 为 uncertain 且用户确认）
→ intent_frame_saved
→ rag_plan_advisory_completed（只提议）
→ edit_plan_saved
→ user_confirmation_saved
→ provider_run_saved（若用户明确授权并执行）
→ verification_result_saved（点击 8C 复测后）
→ followup_plan/provider_run/verification（若同 scope 内确有累积改善）
→ explicit_feedback_saved（若用户点赞、点踩或提交文字）
```

数据库只保存脱敏合同事实和产品事件；结果图只在当前会话内存中短暂展示，不能从 Dashboard 反向查看照片。

## 请把这几项反馈回给项目负责人

- 哪一步不知道该点什么，页面原话是什么；
- 是否能理解 Agent 正在做什么、为什么停止或继续；
- 结果图是否能看出改善（这是个人视觉反馈，不等于模型准确率）；
- 是否出现重复点击、等待过久、错误提示不清或意外退出；
- 是否下载、点赞/点踩、继续追问或重新上传。

## 第一位用户真实回执（2026-09-01）

<span style="color:#C00000"><strong>已发生的事实。</strong> 母版 IMS 与 Profile 建立成功；目标照 IMS Pass；CompareFace RequestId=`3f4bdc92-33b2-4ee3-844a-db34abbc5eca`，原始分 `56.231842041015625`，路由为 `uncertain`。旧页面没有可审计的确认入口，8A 记录 `subject_match_not_confirmed`、`quality_route_not_continuable`，未生成 EditPlan、未产生 ProviderRun、未调用 BeautifyPic。RAG 已返回 Tencent FaceLifting/EyeEnlarging 直接证据，但 `execution_authorized=false`。</strong></span>

<span style="color:#C00000"><strong>根因与修复。</strong> 根因是 `uncertain` 被正确地阻断，但没有把“用户本人/编辑权确认”传到规划器和执行 scope。现在新增 `subject_match_uncertain_acknowledged`：页面确认 → 事件 Trace → `ConfirmationScope` → 8A/8B/8C 再校验；不改成 `match`，不放宽 `no_match`。本地自动化已覆盖未确认阻断、确认后有限继续和 no_match 硬阻断。</span>

<span style="color:#C00000"><strong>用户体验反馈（事实，不等于改版已完成）。</strong> 上传等待过长；脱敏 JSON 直接露出；A/B/C 检查点、安全/同人/Profile 等按钮过多；自然语言入口被 GUI 选项挤压；整体 UI 偏工程文档、视觉不够 C 端。它们已进入下一 UI Gate，下一步先做耗时埋点和真实闭环，再由产品负责人审核“后台自动检查、第二层 Trace、首屏单一任务入口”的改版。</span>

## 当前验收结论

- 页面入口已在浏览器打开，首页加载成功；
- 8C-1/8C-2 代码路径和 fixture 多轮回执已通过自动化测试；
- 本次第一位用户已产生真实 IMS/CompareFace/Profile 回执，但在 8A 的 `uncertain` 合规确认边界暂停；没有新的 BeautifyPic ProviderRun 或 VerificationResult；
- 因此“真实用户端到端完成”“UI 真实多轮图片回执”“视觉效果有效”仍未成立。Cloud 重建后完成一次确认即可继续，不需要重新设计产品规则。

## 2026-09-01 Cloud 失败回执的二次定位与恢复步骤

第一位用户看到 `Tencent ImageModeration request failed` 后，Cloud 运行日志显示真正中断点是 Streamlit 重跑时重复写入同一 `photo_quality_result_id`，SQLite 抛出 `UNIQUE constraint failed`。这不是一条可被忽略的内容安全失败，也不能把页面通用提示理解成“密钥一定错误”。代码已改为合同幂等落账：同一 ID、相同脱敏事实可复用；事实变化则明确冲突并停止，不覆盖历史记录，不重复完成事件。

Cloud 重新构建后，第一位用户按以下顺序恢复测试：刷新 Private 页面 → 新建或继续当前本地会话 → 重新执行一次内容安全检查 → 观察页面是否进入质量/同人/Profile。若腾讯服务自身仍失败，只需记录页面显示的 `error_code` 和 `RequestId`；不要提交密钥、原图、Base64 或完整错误文本。只有获得新的真实 IMS 结果后，才继续记录后续 `ProviderRun`/`VerificationResult`。
