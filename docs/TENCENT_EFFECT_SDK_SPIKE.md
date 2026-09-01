# 腾讯特效 SDK 候选 Provider：官方证据核验版

> 复核日期：2026-08-30
> 当前状态：`candidate / Web adapter implemented / browser-smoke-pending`
> 资料范围：仅腾讯官方一手文档；本轮没有使用账号、License、密钥、SDK 包、照片或网络调用。

## 1. 这次核验回答了什么

产品需要的不只是“文档里有几个美颜滑杆”，而是一个能把**静态人像照片**按计划处理、保存回执、控制隐私与成本的真实 Provider。本次核验把“腾讯特效 SDK 看起来能力很多”拆成四个可验证问题：它到底在哪个平台能处理静态图、细项五官能力属于哪个平台/套餐、License 和成本怎么取得、以及图片和隐私是否已有官方边界。

结论是：**腾讯官方资料分别证明了两件事，但还没有证明它们已经在同一条、可供本项目直接调用的静态图片链路上闭合。**

1. Web 美颜特效 SDK 官方教程确实演示了浏览器选择一张图片、调用 `updateInputImage`、应用效果并下载结果图。因此“Web 静态单图处理”有官方文档依据，但本项目尚未做真实 License/SDK/结果图 Smoke。
2. 移动端/PC 端 S 系列的官方能力清单确实列出眼距、眼宽/高、眉毛、鼻翼、嘴型、唇厚、脸型细分等高级美型能力。但本次没有找到官方资料证明这些细项在**Web 静态图片**路径可用，也没有找到当前项目所选 PC/移动包的静态图片或批量处理回执。

因此这条路线目前的正确定位是：**有价值的候选 Provider，而不是已接入的“细项静态修图 API”。**

## 2. 已证实、未证实与不能推断的边界

| 问题 | 官方一手资料能证实什么 | 本项目仍不能声称什么 |
|---|---|---|
| Web 静态图 | 官方教程展示浏览器输入一张图、处理并下载输出图 | 当前项目已建立浏览器桥接 Adapter；不能外推为 Python REST、细项五官或真实 live 已通过 |
| 高级五官 | 移动端/PC S 系列列出眼距/眼宽高/眉毛/鼻部/嘴部/脸型细分 | 任意套餐、任意 SDK 版本、任意静态图场景都支持全部能力 |
| 批量写真 | 未发现本次审核资料中的 batch API、最大张数或批量 SLA | 单图教程可以自然推广为 8—9 张批处理 |
| License | 官方有 Web 测试 License、正式 License、域名/AppId 绑定等流程 | 当前项目已经持有可用 License 或被授权执行 |
| 价格 | 官方 Web 定价页列有基础/专业/高级月费，移动/PC 也有不同套餐 | 当前项目单图成本、预算消耗、优惠或最终费用 |
| 隐私 | 官方 Android/iOS 规则说明人脸坐标、相册图片本地处理不传输不上报；SDK 使用记录可匿名加密上报 | Web 图像的完整出站、留存、遥测、地区或删除 SLA 已被证明 |
| 性能 | 未找到官方 p50/p95、静态图吞吐或批处理延迟承诺 | 能满足 Demo 或线上体验延迟 |

## 3. 平台选择的实际含义

### Web 路线：最接近当前 Demo，但不是 Python API

腾讯的 Web 图片教程是浏览器 JavaScript/WebGL 路线：图片在前端选择并交给 SDK，再从浏览器下载结果。它适合未来把 Streamlit 前端替换或嵌入一个 JavaScript/TypeScript 图片处理组件；**不能把它误当作一个可由当前 Python 后端直接 POST 图片的云端 REST API。**

Web 定价页当前明确列出的全套餐能力是美颜美白、磨皮、瘦脸、削脸、大眼、下巴等。页面没有以同样方式列出眼距、鼻翼、唇厚、眉毛等细项，因此这些能力在 Web 静态图路径必须另行验证。

### 移动端/PC 路线：细项能力更强，但与当前 Demo 架构有距离

腾讯移动端/PC S 系列能力清单列出的候选范围包括：

- 眼部：眼距、眼宽、眼高、眼睛位置、眼角；
- 眉毛：角度、距离、高度、长度、粗细、眉峰；
- 鼻部：瘦鼻、鼻翼、位置、鼻梁、山根；
- 嘴部：嘴型、嘴唇厚度、宽度、位置、微笑唇；
- 脸型：瘦脸、窄脸、V 脸、收下颌、短脸、脸型、下巴、额头、瘦颧骨。

这些是“能进入下一轮实证的候选特征目录”，不是本项目当前的工具白名单。耳朵形状在已审核官方资料里没有找到对应证据，因此保持 `not_promised`。

## 4. License、价格与产品可行性

官方 Web 快速上手说明：测试 License 可用于本地测试，测试期 14 天、可续期一次至最多 28 天、每个账号最多一个；正式上线前需要购买正式版 License，并按域名/小程序 AppId 绑定。正式 Web License 的官方列表价为基础版 5,999 元/月、专业版 8,999 元/月、高级版 35,000 元/月（价格须在实际购买时重新核对）。

移动端/PC 的 License 与 Web 分开：单个 License 只能绑定移动端或 PC，不支持同时绑定；S 系列能力和套餐价格也与 Web 独立。对当前学生 Demo 而言，这意味着腾讯特效 SDK 不是“申请一个 API Key 就能低成本扩展”的路线，必须先以测试 License 和真实单图 Spike 验证价值。

## 5. 隐私、地区和数据边界

腾讯官方个人信息保护规则将开发者定位为数据处理者，要求在集成前告知并取得终端用户同意；合规指南进一步要求获得同意后再初始化 SDK、在用户实际触发功能时调用。对 Android/iOS，规则写明人脸坐标与用户主动选择的相册图片用于美颜时为本地处理、不传输不上报；同时 SDK 使用记录可能匿名加密上报。

这些材料**不能外推为“Web 图片绝不会出站”或“供应商留存为零”**。本次资料中没有得到所选 Web/PC/移动表面的确切数据处理地区、跨境路径、图片保留期、删除 SLA、遥测内容或静态图延迟。因此候选卡仍把这些字段标为 `pending/unknown`，并要求逐项向腾讯控制台、合同/隐私条款或工单核验。

## 6. 本切片的 Card、Adapter 与测试边界

候选 Card：[tencent_effect_sdk.json](../data/provider_cards/tencent_effect_sdk.json)。它新增了“官方已证明什么、只适用于哪个表面、不能推断什么”的证据字段，且保持 `review_status=candidate`。

Adapter：[tencent_effect.py](../src/portrait_consistency_agent/services/tencent_effect.py)。它只允许构造没有图片、Base64、路径或密钥的候选请求信封；`execute()` 永远拒绝，不导入腾讯 SDK、不读照片、不触网。候选参数范围来自旧版 Android 参数表，仅作为候选计划参考，不能转化为当前静态图的执行 key。

离线 Smoke 和单元测试只验证“候选卡能加载、未知能力会被拒绝、缺 License/权限/预算/同意时会阻断、网络调用未尝试”。它们不能证明腾讯 SDK 的视觉效果、静态图支持、价格、隐私或性能。

## 7. 下一步需要产品负责人/控制台配合的精确事项

1. **先选 Spike 表面。**若目标是 9 月 4 日 Demo，优先核验 Web 静态单图；若目标是细项五官，先确认是否接受移动/PC SDK 重构及套餐成本。两条结论不可混用。
2. **在腾讯控制台申请测试 License。**仅保存 License 是否有效、目标域名/AppId、到期日等非敏感事实；不要把 Token/Key 放入仓库、文档或 Trace。
3. **使用明确授权的内部测试图完成一次单图 Spike。**保存脱敏 receipt：SDK 版本、平台、License 状态、参数名、输出 hash、耗时、错误码；不保存原图/Base64。
4. **向腾讯工单/商务获得书面答复。**问题必须逐项问清：目标版本/套餐是否支持静态图；目标细项在该表面的精确 key 与范围；批量上限；Web 图片/遥测是否出站、留存和删除；地区/跨境；测试和正式价格；性能/并发建议。
5. **仅当 Card、真实 Adapter、单图 receipt、隐私/预算证据、Gold 回归和产品负责人冻结全部通过后，才允许从 `candidate` 改为可执行。**

## 8. 官方资料

- [Web 静态图片处理教程](https://cloud.tencent.com/document/product/616/118039)
- [Web 快速上手与测试 License](https://cloud.tencent.com/document/product/616/71371)
- [Web 端与小程序定价/绑定](https://cloud.tencent.com/document/product/616/86942)
- [移动端/PC 端能力与定价](https://cloud.tencent.com/document/product/616/36807)
- [旧版 Android 参数表（仅候选映射参考）](https://cloud.tencent.com/document/product/616/78792)
- [购买与 License 绑定流程](https://cloud.tencent.com/document/product/616/11235)
- [个人信息保护规则](https://cloud.tencent.com/document/product/616/65678)
- [合规使用指南](https://cloud.tencent.com/document/product/616/102032)

## 9. 当前不可用的定位与手动开通

此前 `blocked` 的原因是缺少 Web 的运行集成和真实 receipt；这并非已有 Tencent BeautifyPic/CAM 权限失效。现在已新增独立的浏览器桥接 Adapter、Web Card、Streamlit page 6 和离线 smoke。Web 教程仍是浏览器 JavaScript/WebGL 路线，不能当作 Python + Streamlit 后端 REST API。测试 License 规则见[官方快速上手](https://cloud.tencent.com/document/product/616/80189)。即使浏览器 smoke 成功，仍需回到 Card→Adapter→权限/预算→隐私/区域→真实 receipt→Gold 回归→产品负责人冻结，不能仅凭 License 把 Candidate 自动升级为主流程可执行 Provider。

## 10. 2026-08-30 控制台现场证据（历史快照，已由下方状态更新）

已在腾讯云视立方控制台打开 `Web 端 License` 管理页并进入“新建测试版 License”表单。以下保留提交前的历史状态：测试表单要求填写 `Project Name`，并至少绑定精确 `Domain` 或小程序 `AppId`，测试有效期 14 天、可续期 1 次、总计 28 天。产品负责人随后已提交精准域名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，当前控制台显示测试 License“正常”（2026-08-30 至 2026-09-13）；但 SDK 细项能力、真实静态图 receipt 和可执行 Adapter 仍未通过准入。

这条现场证据把后续工作缩小为：下载/接入对应 Web SDK，做单图 smoke，核验细项参数是否真的在 Web 表面可用，并补齐隐私/预算/Gold 回归；不能把“表单提交成功”当成图片能力通过。

## 11. 2026-09-01｜Web Adapter 实施状态（当前快照）

已实现 `src/portrait_consistency_agent/services/tencent_effect_web.py`：产品 0—100 参数映射为 Web 0—1 参数，服务端按官方公式生成短时签名，浏览器组件加载 UMD SDK，静态图按官方 `takePhoto()` 获取 `ImageData`，并只返回 hash/尺寸/耗时/安全错误码。`ProviderRun` 已增加 `tencent_effect_web/WebARImage` 的联合合同；`data/provider_cards/tencent_effect_web.json` 是单独的 Web Card，仍保持 `candidate`。`pages/6_腾讯特效Web试验.py` 提供官方示例图优先的实际入口，`scripts/smoke_tencent_effect_web.py` 只做离线合同 smoke。

当前尚未取得新的浏览器成功回执，因此不能声称 Web 图片处理已经 live、细项五官已可用、批量已支持或隐私/区域已确认。正式准入由 `evaluate_effect_web_admission()` 按 License、精确域名、出站/区域、预算、Adapter、成功 receipt 和产品批准逐项返回；它不自动改 Card。三项运行配置名为 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`，只放本机 `.env` 或 Streamlit Cloud Secrets，Token 不下发给浏览器。
