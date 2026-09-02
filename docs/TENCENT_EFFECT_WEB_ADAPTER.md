# 腾讯特效 Web SDK Adapter｜静态图准入切片

> 当前状态：`candidate / browser-smoke-blocked-by-cloud-secrets`（2026-09-01）
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
