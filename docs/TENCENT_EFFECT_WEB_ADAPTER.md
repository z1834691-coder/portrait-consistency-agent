# 腾讯特效 Web SDK Adapter｜静态图准入切片

> 当前状态：`candidate / browser-smoke-ready-pending-receipt`（2026-09-02）
> 这不是一个 Python REST API。它是浏览器 JavaScript/WebGL SDK 的受限桥接层。

## 1. 它解决什么问题

现有 `BeautifyPic` 可以由 Python 后端发起一次参数化修图，但它不能证明腾讯特效 SDK 的更丰富 Web 静态图能力。这个切片把腾讯官方 Web 静态图教程中的能力接入一个独立、可回滚的 Streamlit 页面：Python 只负责校验参数、生成短时签名和记录脱敏回执；浏览器负责加载 SDK、处理图片和显示结果。这样可以真实验证“这个新的 Provider 是否能在绑定域名上处理一张图”，又不会把图片、Base64、License Token 或浏览器结果写进数据库。

## 2. 当前主链路

```text
官方示例图 / 用户明确授权的单人图
→ Python 校验 hash、输入来源和产品参数
→ 检查三项 Effect Secrets
→ 服务端生成五分钟签名（Token 不下发）
→ 浏览器加载 Tencent Web SDK
→ SDK 在浏览器中处理图片
→ 浏览器计算结果 hash/尺寸/耗时
→ 只回传 Browser Receipt
→ Python 校验回执并写脱敏 ProviderRun
→ 人工依据准入清单决定 Card 是否升级
```

正式入口是 `pages/6_腾讯特效Web试验.py`；适配器是 `src/portrait_consistency_agent/services/tencent_effect_web.py`；离线合同 smoke 是 `scripts/smoke_tencent_effect_web.py`。

## 3. 输入、输出与规则

| 项目 | 规则 |
|---|---|
| 输入图片 | 默认使用腾讯官方示例 HTTPS URL；用户图仅接受明确授权的单人图片，转为临时 data URL，不落盘 |
| 产品参数 | `face_lifting / face_narrow / eye_enlarging / chin / whitening / smoothing`，产品刻度 0—100 |
| SDK 参数 | 映射到 Web 的 `lift / shave / eye / chin / whiten / dermabrasion`，范围 0—1 |
| 默认外观 | 美白与磨皮显式传 0；只有用户明确同意和调高才可发送非零值 |
| 认证 | `APP_ID + License Key + License Token`；Token 只在 Python 侧生成签名，浏览器不接收 Token |
| 图片大小 | data URL 桥接上限 8MB；示例 URL 必须 HTTPS |
| 结果 | 浏览器显示与下载；Python 只接收状态、hash、尺寸、SDK 版本、耗时和安全错误码 |
| 留存 | `browser_session_only`；ProviderRun 的结果引用带 10 分钟合同生命周期，不保存结果字节 |
| 准入 | Card 仍为 candidate；一次成功回执不自动改变 Card，不自动加入主流程或 RAG 执行白名单 |
| 不可推断 | Web generic 字段不等于移动/PC 的唇厚、鼻翼、眉毛、眼距等细项；单图不等于批量能力 |

## 4. 产品负责人已经确定 / 仍需核对

已确定：这是一条独立的新 Provider；先用官方示例图做最小 Web 静态图 Spike；保持 RAG `advisory-only`、主流程默认 Tencent BeautifyPic、不保存原图和 Token；美白/磨皮默认关闭。

正式把 Card 从 `candidate` 升级前，还要在控制台或供应商材料中核对并留下非敏感事实：精确域名绑定、测试 License 有效期、当前 Web SDK 版本、图片出站/留存/遥测与处理地区、预算/计费、一次真实成功回执，以及产品负责人对这条 Web 路线的批准。代码提供 `evaluate_effect_web_admission()`，只返回缺失证据，不会自动改 Card。

## 5. 测试案例与验收标准

1. 产品刻度 `100/15/5` 映射为 Web `1.0/0.15/0.05`，其余字段显式为 0。
2. 未知细项（如 `lips_thickness`）、布尔值、超过 100 或大于 8MB 的输入在出站前被拒绝。
3. 缺少 APP ID/License Key/Token 时只显示配置指引，网络调用不会发生。
4. 浏览器成功回执必须含输出 hash 和输入/输出尺寸；失败回执必须含安全错误码与消息；请求引用或输入 hash 不一致时拒绝入账。
5. 所有证据齐全时，准入函数只返回 `promote_after_review`；它仍不替产品负责人写入 `review_status=verified`。

## 6. 一条完整 Trace（示意字段）

```text
effect_web_request_prepared
  request_ref=effect_web_req_…
  input_source=sample_url
  input_sha256=<64 位哈希>
  product_params={face_lifting:10, eye_enlarging:10}
  sdk_params={lift:0.1, eye:0.1, shave:0, chin:0, whiten:0, dermabrasion:0}
→ effect_web_signature_minted
  app_id=<非密钥账号标识>
  token_exposed_to_browser=false
→ browser_sdk_started
  sdk_url=https://webar-static.tencent-cloud.com/…
→ browser_receipt_received
  status=succeeded | failed
  receipt_id=web_receipt_…
  output_sha256=<成功时才有>
  elapsed_ms=<实际值>
→ provider_run_saved
  provider=tencent_effect_web
  operation=WebARImage
  result_retention=browser_session_only
  card_review_status=candidate
```

回执中的 `receipt_id` 是本地浏览器桥接 ID；Web SDK 不一定提供 Python REST API 那样的 Tencent `RequestId`，不能把二者混称。

## 7. 官方依据

- [腾讯 Web 静态图片处理教程](https://cloud.tencent.com/document/product/616/118039)
- [腾讯 Web 快速上手与测试 License](https://intl.cloud.tencent.com/ind/document/product/1143/53939)
- [腾讯 Web 签名说明](https://cloud.tencent.com/document/product/616/71370)

## 8. 2026-09-01｜Cloud 运行回执与当前阻塞

Cloud 在拉取最新提交后曾因旧进程缓存报 `load_tencent_effect_web_card` ImportError；执行一次
Cloud Reboot 后，page 6 已正常加载，官方示例图入口、参数控件和 Card candidate 状态均可见。
这次重建修复的是部署进程状态，不是一次图片处理成功回执。

本轮浏览器 smoke 尚未真正开始：Cloud Secrets 中缺少
`TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`。
页面因此在服务端签名之前安全停止，未加载 SDK、未发送图片、未生成 Browser Receipt，Card
继续保持 `candidate`。已有 Tencent REST `TENCENT_SECRET_ID/KEY` 不能替代 Effect Web 的
三项 License 配置；Token 仍只用于服务端签名。

官方证据只确认 Web 测试 License 有申请/有效期规则，并不等于本项目已取得图片处理成功：

- [Web 测试 License 说明](https://cloud.tencent.com/document/product/616/80189)
- [Web 价格与域名绑定规则](https://cloud.tencent.com/document/product/616/86942)

用户补齐三项 Secrets 后，下一步只运行一次腾讯官方示例图；若收到回执，保存脱敏的
`receipt_id/input_sha256/output_sha256/elapsed_ms/sdk_version/status`，再分别完成隐私、区域、
成本、Gold 回归和产品负责人 promotion 审核。任何单次成功都不会自动改变 Card 或主流程权限。

## 9. 2026-09-02｜Browser Receipt 引用错位修复

### 现象与根因

真实页面曾显示 `browser receipt request_ref does not match the prepared request`。这不是腾讯 SDK
返回了错误的图片结果，而是 Streamlit 的正常重跑机制造成的：组件回传 Browser Receipt 时，整个
Python 页面会再次执行；旧页面每次重跑都随机生成新的 `request_ref`，于是上一轮浏览器回执被拿去
匹配下一轮新请求，合同正确地拒绝了它。

### 修复后的行为

- 页面按“输入图片引用 + 输入 hash + 参数 + 输入来源 + Card 版本”计算非敏感 fingerprint；同一代
  输入/参数在 Streamlit 重跑时复用同一个 `request_ref`；输入或参数变化才开启新的请求代次。
- `reset_token` 现在标识请求代次，而不是签名时间。页面重跑只刷新五分钟签名，不会把仍在等待回执的
  浏览器组件误重置。
- 旧回执若仍滞留在组件状态中，会被后端按 request/hash 合同安全忽略并提示重新点击当前请求；它不会
  写入 `ProviderRun`，也不会覆盖有效结果。
- Session state 只保存脱敏的请求合同和 fingerprint，不保存 data URL、License Token、输入/输出图。

### 交叉验证

新增测试覆盖：同一代重跑复用 request reference、参数改变时开启新代次、签名刷新不改变 reset token、
参数顺序变化仍得到相同 fingerprint。真实 Browser Receipt 仍须在 Cloud Secrets 配齐后取得；本修复
解决的是回执关联一致性，不等于 Web Provider 已通过准入。

## 10. 2026-09-02｜真实重试回执与当前鉴权阻塞

本轮已在 Cloud page 6 执行一次真实浏览器重试。此前的
`browser receipt request_ref does not match the prepared request` 已不再出现，说明同一代次
`request_ref` 修复生效；请求确实进入了腾讯 Web SDK，但没有生成结果图。

脱敏回执如下：

```text
status=failed
receipt_id=web_receipt_effect_web_fa6f0765ad924597
error_code=SDK_RUNTIME_ERROR（SDK 事件映射前的历史回执）
elapsed_ms=965
output_hash_saved=false
card_review_status=candidate
```

浏览器开发日志同时记录到腾讯 SDK 鉴权错误码 `100`。官方错误码中，`100` 表示鉴权缺少必要
参数。日志里的 SDK `appid` 值呈现为当前 Streamlit 域名，而 `TENCENT_EFFECT_APP_ID` 必须是
腾讯账号的数字 APPID；绑定域名只用于 License 域名校验，不能填入 APPID。当前代码已在服务端
签名前拒绝 `http(s)` 形式的 APPID，并将已知 SDK 错误映射为不泄漏原始 SDK 信息的安全提示。

因此本次重试的结论是：回执关联问题已修复，但 Provider 仍未通过真实图片处理准入。请在
Streamlit Cloud → App Settings → Secrets 中只把 `TENCENT_EFFECT_APP_ID` 改为腾讯账号数字 APPID，
保留现有 License Key/Token，不要在聊天中发送任何密钥；修改后 Reboot/刷新，再用官方示例图运行
一次。成功前 Card 必须继续保持 `candidate`，不得写入主流程。

## 11. 2026-09-02｜再次真实重试：鉴权阻塞仍在

产品负责人修正 Secret 后，本轮在 Cloud page 6 再次明确点击组件执行。请求确实重新进入腾讯 Web
SDK；由于输入、参数和 Card 版本没有变化，合同按同一请求代次复用 `request_ref`，因此回执引用仍为
`web_receipt_effect_web_3a3c71bec3f24557`。这不是自动重试，也不是读取旧的成功结果；本次点击的 SDK
初始化时间为 `2026-09-02T07:28:40Z`，耗时 `628ms`。

本次脱敏 Browser Receipt：

```text
status=failed
provider_request_id=web_receipt_effect_web_3a3c71bec3f24557
sdk_error_code=100
normalized_error_code=20001001
safe_error=SDK 鉴权失败，请检查 License 和签名
output_hash_saved=false
```

这说明前一处 `request_ref` 错位已经没有复现，但 Web SDK 仍未通过鉴权。官方错误码只能确认
“鉴权失败”，不能仅凭页面信息断言唯一原因；应按 License Key/Token 是否成对、签名使用的数字
腾讯 APPID、精确绑定域名和 Cloud Secret 是否已重载逐项核对。Card 继续 `candidate`，不产生主流程
执行权限；在 Cloud Reboot/Secret 重载后只做一次新的官方示例图 smoke，避免无意义的重复调用。

## 12. 2026-09-02｜完整流程重试回执更新

在当前 Cloud 页面从头执行一次官方示例图流程后，SDK 等待自身鉴权窗口并返回最终失败回执：

```text
status=failed
provider_request_id=web_receipt_effect_web_3a3c71bec3f24557
elapsed_ms=10360
sdk_error_code=100
normalized_error_code=20001001
output_hash_saved=false
```

稳定 `request_ref` 仍表示同一输入/参数代次；这次是新的用户点击，不是系统自动重试。回执关联链路
正常，但鉴权阻塞仍未解决，Card 继续 `candidate`，不进入主流程。

## 13. 2026-09-02｜Canvas 生命周期错误修复

最新一次前端运行暴露浏览器错误：`Failed to set the 'width' property on 'HTMLCanvasElement': Cannot resize canvas after call to transfer...`。根因是腾讯 SDK 初始化后接管了输出 Canvas，而旧代码在 `takePhoto()` 返回后再次修改同一 Canvas 的宽高。适配器现已将 SDK 输出 Canvas 与结果 Canvas 分离：SDK Canvas 初始化后保持不变；`ImageData` 复制到新建的浏览器自有 Canvas，再生成预览、下载链接和输出 hash。这样不改变 License、签名、图片留存或 Provider 准入边界，只修复结果捕获阶段的浏览器兼容性问题。

## 11. 2026-09-02｜第二次明确重试回执

负责人在修正 Cloud Secret 后再次明确点击执行。同一输入/参数仍属于同一个请求代次，因此按合同复用
`request_ref`；这次是新的 SDK 点击，不是自动重试或重复写入。最新脱敏回执为：

```text
status=failed
receipt_id=web_receipt_effect_web_3a3c71bec3f24557
elapsed_ms=628
sdk_error_code=100
normalized_error_code=20001001
output_hash_saved=false
```

前一次回执 `web_receipt_effect_web_fa6f0765ad924597` 继续保留为历史失败证据。两次都到达 SDK 鉴权阶段，
均未生成图片；当前尚不能在没有控制台凭据核对的情况下断言唯一根因。候选核对项仍为 License Key/Token
配对、签名/数字 APPID、精确域名绑定和 Cloud Secret 重载。Card 继续 `candidate`，不能接入主流程或被
RAG 自动放行；不要继续盲目重复调用。

## 14. 2026-09-02｜Canvas 修复后的真实浏览器成功回执

已将 GitHub 最新代码部署到 Streamlit Cloud，并在 page 6 使用官方示例图完成一次真实的腾讯特效 Web 浏览器调用。执行链为：Streamlit Cloud 拉取修复 → 浏览器加载 SDK → `takePhoto()` 返回 `ImageData` → 写入独立结果 Canvas → 生成结果哈希 → 返回脱敏 Browser Receipt。真实回执为：

```text
status=succeeded
receipt_id=web_receipt_effect_web_4d58ea15a0794370
elapsed_ms=2601
output_hash_saved=true
result_retention=browser_session_only
```

根因是旧实现修改了 SDK 持有的输出 Canvas 尺寸；现在 SDK Canvas 保持不可变，结果写入独立 Canvas 后再取哈希。该事实证明 Web 静态图 Adapter 已完成一次端到端成功运行，但不自动把 Card 从 `candidate` 升级为 `verified`：精确域名、供应商留存/区域、预算、更多图片回归和产品负责人准入仍需单独核验。

## 15. 2026-09-02｜Tool Registry / Meta-Agent 接入层

`services/tool_registry.py` 将本 Card 投影为只读 `ToolDescriptor`，并与 verified 的 BeautifyPic baseline 同时登记；`services/meta_agent.py` 输出 `ToolProposal`，允许在 8A 计划前、8C 策略选择或失败路由时解释 Web 候选及其准入检查。对于当前 `review_status=candidate`，提议路由固定为 `candidate_proposal_only`，可以记录 `tencent_beautify_pic` fallback，但不得调用浏览器或创建 `ProviderRun`。

这一层不改变本 Adapter 的输入/输出边界：图片和 License Key 仍只在浏览器组件使用，Python 只接收脱敏 Browser Receipt；Web Receipt 仍不含结果图 bytes。因此它完成的是“工具卡 → 受限 Meta-Agent → 阻断/兜底 Trace”的控制面接入，不是 Web 主流程 promotion。结果交接 A/B/C 决策冻结后，才可继续修改 `EditPlan`、执行器和 8C 复测。

## 16. 2026-09-02｜B 方案：结果图一次性回传并进入共同复测（当前覆盖）

上一段“Web Receipt 不含结果图 bytes、A/B/C 待决”是历史状态。本轮产品负责人已选择 B，适配器增加了受限 handoff：浏览器先通过独立结果 Canvas 生成结果 data URL，再发出临时 `result` 触发器和脱敏 `completed` Receipt；Python 只在当前请求中校验后取得 bytes。

服务端校验顺序固定为：

```text
prepared request
→ request_ref 一致
→ 输入 hash 一致
→ Receipt 状态/输出 hash/尺寸合法
→ result data URL 的 MIME（PNG/JPEG/WebP）和 8MB 编码/6MB 解码上限
→ data URL 解码后重新计算输出 hash
→ 只将 bytes 交给共同 VerificationResult
```

`EffectWebBrowserResult` 不是 `ProviderRun` 的持久化字段。`accept_effect_web_browser_result()` 只有在显式候选试验开关、执行 scope、质量/同意/幂等检查都通过时，才把真实 Receipt 转成共同 `ProviderRun`；失败或错位一律 fail-closed。Trace 只留 request/receipt/hash/尺寸/状态和原因码，不留 data URL、图片、Token 或隐藏推理。

E1 已由 `tests/test_execution.py` 和 `scripts/smoke_effect_web_b_handoff.py` 验证 handoff → Web ProviderRun → 共同 `verify_result`；E2 由 `scripts/run_effect_web_regression.py` 覆盖 8 个成功/失败/异常案例，报告见 `reports/tencent_effect_web_regression_v1.json/.html`。结果为 `8/8`，但均为 fixture/合同证据，不是视觉泛化或 Provider promotion。Web Card 继续 `candidate`。

## 17. 2026-09-03｜E3 四张真实 JPEG 回执与证据汇总

负责人批准 E3 并提供四张真实 JPEG。它们先经过 `run_effect_web_e3_preflight.py` 的内存预检，再在已部署的精确域名 page 6 上逐张执行 Web SDK。脱敏回执如下：

| 样本 | Receipt | 状态 | 耗时 | 输出哈希 | 复测 |
|---|---|---:|---:|---|---|
| `e3_reference_001` | `web_receipt_effect_web_c83e83d54d8e4b1d` | succeeded | 2302 ms | `c05054c8…adff171` | metadata-only |
| `e3_target_001` | `web_receipt_effect_web_0710c27460e34a32` | succeeded | 1397 ms | `b00005f2…28832811` | metadata-only |
| `e3_target_002` | `web_receipt_effect_web_9563c0fb46aa4f3f` | succeeded | 1583 ms | `0ae08586…304b49a7` | metadata-only |
| `e3_target_003` | `web_receipt_effect_web_0046d91ec02a4e08` | succeeded | 1340 ms | `acd09781…3f4cccdf5` | metadata-only |

当前 E3 证据为：4/4 真实回执成功；4/4 输入哈希与预检样本绑定；4/4 结果交接标记；离线 E2 合同回归和批量失败隔离通过。完整脱敏报告见 `reports/effect_web_e3_evidence_v1.json/.html`，看板入口为 page 8。手工 manifest 尚未抄录四条完整 `request_ref`，所以报告保留该缺口，不把 receipt ID 猜成 request_ref。

这组结果证明“真实浏览器 SDK 能处理这些输入并产生可追溯结果”，不证明“结果已经更像母版”或“Web 已可作为正式主流程 Provider”。共同 Python `VerificationResult` 的真实图像几何复测、供应商图片出站/地区/留存/费用证据、批量视觉效果和产品负责人最终 promotion 仍是独立 Gate；Card 继续 `candidate`，RAG 继续 `proposal-only`。

### 17.1 2026-09-03｜E3 同步后复核

预检、证据汇总、Web E2 回归和 B handoff smoke 已重新执行：5 个样本为 2 eligible、2 warning、1 rejected；4 条真实 Browser Receipt 全部成功，输入哈希全部绑定，handoff 标记 4/4；E2 合同回归 8/8。完整工程 QA 为 `226 passed, 4 warnings`。手工 manifest 仍缺完整 `request_ref`，所以报告保留该缺口；视觉复测、供应商地区/费用/留存和 Card promotion 不得由这些结果自动推断。
