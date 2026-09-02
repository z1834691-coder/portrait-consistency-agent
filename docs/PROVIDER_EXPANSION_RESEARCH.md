# 人像细项修图 Provider 扩展调研（双路线已冻结，候选准入进行中）

> 2026-08-30 状态同步：火山美颜 API V2 与腾讯特效 SDK 的官方证据核验已完成，详细可证实/待证实边界分别见 [火山 Spike](PROVIDER_VOLCENGINE_SPIKE.md) 与 [腾讯特效 Spike](TENCENT_EFFECT_SDK_SPIKE.md)。两者仍为 `candidate`，无图片出站、无真实新 Provider receipt；产品负责人已冻结火山 V0 暂不购买/接入，当前执行链只用 Tencent。本文件的任何历史候选措辞均不得覆盖这两个专项文档的最新边界。

> 调研日期：2026-08-29；实施同步：2026-08-30｜状态：产品负责人已冻结两条并行路线；Candidate Card、Adapter shell、权限/预算 preflight、离线测试和 smoke 已创建，**没有新 Provider 密钥、照片出站或外部调用被创建。**

## 1. 先纠正一个技术前提

你希望补齐的不是“再接一个 API”本身，而是这些真实能力：眼睛、嘴巴、鼻子、眉毛、耳朵、脸型细分，以及未来 8—9 张写真分别对齐母版的批量一致性。这里最重要的是**参数可控、能留工具回执、能验证和能降级**。截至本次官方资料核验，眼距/鼻翼/嘴型/唇厚/脸型细分能在候选 SDK 文档中找到明确参数例子；眉毛和耳朵尚未拿到与当前“静态照片 + 参数级执行”完全匹配的公开能力证据，不能提前承诺为自动执行项。

因此候选不必都叫 SDK：

- 静态图片 API：后端上传图片、带参数返回结果；最贴合今天的 Python/Streamlit Agent Tool；
- Web/客户端 SDK：在浏览器或用户设备内处理像素；细项通常更多、隐私出站更少，但工程和 License 更复杂；
- 生成式图片编辑：看起来“什么都能改”，但不可解释、身份漂移风险高，不适合作为母版一致性主工具。

## 2. 候选方案对比

| 候选 | 已查到的官方能力 | 对当前项目的优点 | 主要代价/不确定性 | 建议优先级 |
|---|---|---|---|---|
| **火山引擎 美颜 API V2.0** | 面向静态图像与批量修图；既有智能预设，也有固定小项参数；官方介绍列出脸型、眼睛、鼻子、嘴巴、画质/批量场景 | 最容易从 Python 后端接成真正的 `ProviderAdapter`；天然适合“同一个母版、每张图不同参数”的批量任务 | 图片需发往火山；创点/商务开通、实际可用参数/地区/报价要拿到书面 Card 后再判断 | **提交后第一优先验证** |
| **腾讯特效 SDK（Web / PC / 移动）** | 当前官方参数页明确列出眼距、鼻翼、鼻梁、嘴型、唇厚、脸型等高级美型；Web 官方有“上传图片→处理→下载”教程 | 与现有腾讯链路更同源；可在客户端/浏览器侧处理，未来有机会减少后端图片出站；细项丰富 | 当前 Web 文档公开示例的能力集合与 PC/移动高级参数表未完全等价；眉毛/耳朵需按目标版本再核验；需测试 License、域名/签名、前端组件改造；免费测试申请/正式 License 可能有企业资质与费用门槛 | **并行做可获得性 Spike** |
| **火山引擎 Effect SDK** | C/移动/PC SDK 可对图像 buffer 处理；图片模式；美型/微整形素材的参数化配置 | 丰富且可控；未来若做原生桌面/移动端，可把处理留在设备侧，适合高级人像编辑 | 当前官方接入须知写明 SDK 不公开直接提供，需联系技术支持；还要处理原生二进制、素材包、License、GPU/设备兼容，工程量显著高 | **长期第二阶段** |
| 通用生成式图片编辑模型 | 可按文字改很多外观 | 短时间 demo 视觉上可能惊艳 | 易重绘身份/妆面/背景，无法保证“眼宽 +x”这种可解释参数，也不适合母版一致性验证 | **不作为主线** |
| 人工自动化醒图/桌面脚本 | 使用用户熟悉的产品 | 表面上接近用户习惯 | 无稳定授权 API、脆弱、不可审计、可能违反产品条款；难以部署 | **不采用** |

## 3. 推荐路线：不是立刻替换腾讯，而是两条受控 Spike

```text
当前 Tencent BeautifyPic（已真实回执）
    │
    ├─ 继续作为 9 月 4 日可演示的“真实执行”基线
    │
    ├─ Spike A：火山 美颜 API V2.0
    │      核对：实际参数表、批量 API、价格、地区、隐私、测试凭证
    │      若通过：候选静态批量 Provider
    │
    └─ Spike B：腾讯特效 Web SDK
           核对：Web 静态图是否确实覆盖目标细项、License/资质、前端集成
           若通过：候选低出站精细编辑 Provider
```

这两个 Spike 只有调研/测试权，不会自动变成产品能力。每一条都必须走同一条准入生命周期：

```text
官方文档与 License/隐私/价格证据
→ candidate Provider Card
→ Adapter shell + fake test
→ 用户同意与预算 Gate
→ 真实 smoke + ProviderRun
→ RAG Gold / hidden holdout 回归
→ 产品负责人冻结
→ reviewed_active
```

## 4. 用户已明确的产品边界，扩展 Provider 也不能破坏

1. **身份不改写。** 只允许同一位成年、本人授权、单人像的局部几何对齐；不做换脸、生成新身份、年龄/性别变化、身体或隐私部位编辑。
2. **母版不是审美模板。** Reference Profile 提供几何目标和允许/禁止部位，不自动把肤色、妆面或照片色彩当作必须复制的标准。
3. **单脸优先。** 多脸隔离、裁剪、回贴、接缝检查和复测未实现前，新的 Provider 不能把“支持多人脸”当作本项目已能只修一个人。
4. **每图独立计划。** 批量写真共享母版目标，但不能复制同一组滑杆；每张照片都要先质量检查、差异分析、生成自己的 EditPlan，再逐张复测。
5. **最多三轮仍然生效。** 新 Provider 不得因为参数更多就绕过初次确认、范围、预算、幂等、安全和计划族上限。
6. **出站按 Provider 单独同意。** 用户同意腾讯不等于同意火山；本地 SDK 也要说明 License/遥测或联网鉴权可能收集什么。
7. **RAG 只能提议。** 检索到一个“可能支持唇厚”的资料，只能提出候选能力；未完成 Card/Adapter/真实回执/回归前，不得处理用户图片。

## 5. 成本、延迟和隐私：现有规则中还缺的数字

现有项目已经冻结了“首轮明确同意、同一计划族最多三轮、外部图片处理需受限 Trace”的行为边界，但**没有为新增 Provider 冻结具体的人民币预算、p95 时延或最大批量并发数**。所以不能说某个候选“已符合之前的成本/时延规则”。

新增 Provider 前还必须由产品负责人决定：

| 要补的数字 | 为什么必须单独定 |
|---|---|
| 单张最高成本、单个计划族最高成本 | 静态 API 常按张/创点收费；批量 9 张会放大成本 |
| 用户可等待的 p50 / p95 时延 | 实时 SDK 和云端批处理的体验不同，不能套用同一阈值 |
| 批量并发/排队策略 | 9 张同时调用可能造成费用尖峰或请求失败 |
| 新 Provider 的数据处理/区域/日志保留证据 | 用户授权文本必须与实际供应商行为相符 |
| 失败时的降级 | 超时/无参数/License 失效时是手动建议、重试还是停止 |

在这些数字未冻结前，候选只能停留在 `candidate`，不进入 `reviewed_active`。

## 6. 当前最适合你的结论

- **9 月 4 日前：** 不替换已经有真实回执的 Tencent BeautifyPic；用现有“诊断→计划→执行→复测/重规划”证明 Agent 闭环。
- **提交后第一个技术探索：** 优先验证火山美颜 API V2.0，因为它公开定位就是静态图片/批量修图，最容易与你的 Python Agent、单图不同参数和批量路线耦合。
- **同时评估：** 腾讯特效 Web SDK 的细项和 License 可获得性；若免费测试/域名/能力范围可行，它可能是低出站且细项丰富的方向。
- **不做：** 用通用生成式模型或自动化醒图来假装“参数级一致性编辑”。它们不利于可解释、可验证和面试复盘。

## 7. 来源（均为官方资料）

- [腾讯特效 SDK：移动端/PC 端美颜参数表](https://cloud.tencent.com/document/product/616/103616)：当前参数表列出眼距、鼻翼、鼻梁、嘴型、嘴唇厚度与脸型等细项；
- [腾讯特效 SDK：处理静态图片教程](https://cloud.tencent.com/document/product/616/118039)：说明 Web 端可对上传图片处理并下载结果；
- [腾讯特效 SDK：测试 License](https://cloud.tencent.com/document/product/616/80189)：测试 License 的申请与有效期条件；
- [火山引擎：美颜 API 产品介绍](https://www.volcengine.com/docs/6705/2441388)：静态图像/批量修图、预设与固定参数两种模式；
- [火山引擎：Effect SDK C 接口接入](https://www.volcengine.com/docs/6705/101966)：图像 buffer、素材节点和参数强度配置；
- [火山引擎：Effect SDK 隐私说明](https://www.volcengine.com/docs/6705/1162076)：SDK 初始化、图像输入与隐私政策要求。

## 8. 下一 Gate 与当前实现状态

产品负责人已选择**两者并行**，并冻结“先候选、后准入”的路线。当前已落地：

1. `data/provider_cards/volcengine_beauty_api_v2.json` + `services/volc_beauty.py`：候选 Card、typed request/preflight/blocked receipt、离线测试和 smoke；当前 `status=not_run`，未接真实 API。
2. `data/provider_cards/tencent_effect_sdk.json` + `services/tencent_effect.py`：Web/PC/Mobile 候选能力、License/静态图/批量/权限边界、typed gate、离线测试和 smoke；移动/PC shell 当前 `status=blocked`，未导入 SDK。Web 静态图另由 `tencent_effect_web.json`、`services/tencent_effect_web.py` 和 page 6 独立承载，仍需 Browser Receipt 才能准入。
3. 两条路线均必须完成官方能力/License/隐私/地区/价格/延迟证据、真实 receipt、RAG Gold/hidden 回归和产品负责人冻结，才可由 `candidate` 升级 `reviewed_active`；RAG/LLM 只能提出候选，不能直接上传照片。

尚未冻结的实现参数仍包括：供应商书面报价与单计划预算、p50/p95 可接受时延、批量并发/排队、出站与留存文案、细项能力优先级和真实图片验收集。这些未完成前，不能把候选 Provider 写进用户可执行能力。

没有上述书面证据和准入 Gate，本项目不会接触新 Provider 的密钥或用户照片。

## 9. 2026-08-30｜两个候选为什么当前不可用，以及手动开通路径

### 火山美颜 API V2.0：不是“没有接口”，而是目标账号和准入证据未闭合

官方 V2 文档能证明异步 `submit → task_id → query → result_url` 的接口形状和 Bearer API Key 示例，但这不等于当前账号已经开通美颜 V2、拥有可用模板/创点、确认了请求字段、数据区域和费用。当前 shell 还要求 `allow_live`、目标账号凭据、单独的火山图片出站同意、区域/预算、已验证 schema、Adapter 和 Card 全部通过；其中 Candidate Card 仍是 `candidate`，所以即使表面参数“全绿”也会 fail-closed。当前 smoke 的事实是 `not_run`、`network_called=false`、`image_sent=false`。

手动处理顺序：登录火山控制台 → 在 API V2/美颜 API 页面确认服务开通、测试额度/创点和 API Key → 在 IAM 核对当前用户或服务账号的美颜 V2 调用权限 → 向官方支持确认 API Key 与 AK/SK 的关系、地区、输入/输出留存、价格/并发/错误码 → 只用明确授权的内部测试图做一次单图 smoke。不要把 Ark 的通用 API Key 当成美颜 V2 已授权的证明；密钥只放部署 Secrets，不发到对话框。官方入口可见 [V2 APIKey 文档](https://www.volcengine.com/docs/6705/2477693?lang=zh)、[产品开通与计费说明](https://www.volcengine.com/docs/6705/2441388?lang=zh) 和 [访问密钥/IAM 说明](https://www.volcengine.com/docs/6392/75626?lang=zh)。

### 腾讯特效 SDK：阻断点是 License/运行表面，不是 CAM API 权限

腾讯特效是 Web/PC/移动端 SDK 路线。官方 Web 教程证明浏览器可以处理一张静态图，但当前项目是 Python + Streamlit；没有 Web License、域名/AppId 绑定和前端 SDK 集成，就不能从后端直接 POST 出一条 REST 图片请求。移动/PC 资料列出的眼距、眼宽高、眉毛、鼻翼、唇厚等细项也不能外推为 Web 静态图或当前套餐可用。移动/PC shell 仍因 `card_candidate_not_admitted` 等门未闭合而 `blocked`；Web 现已具备独立桥接 Adapter，但真实 Browser Receipt、隐私/地区/预算和人工 promotion 仍待完成，不能把其离线入口写成 live。

手动处理顺序：登录腾讯云 → 打开 Vcube/腾讯特效控制台 → 选择目标表面（Demo 优先 Web 静态图；若追求细项则接受 PC/移动 SDK 重构）→ 申请 Web 测试 License（官方快速上手写明测试期 14 天、可续一次至最多 28 天）或确认对应 PC/移动 License → 绑定域名/AppId → 下载与表面匹配的 SDK/示例 → 先用内部授权图验证参数、输出和浏览器端处理 → 再补隐私/遥测/区域/价格证据。Web License 的申请和测试规则见 [腾讯 Web License 快速上手](https://cloud.tencent.com/document/product/616/80189)，Web 静态图教程见 [静态图片处理](https://cloud.tencent.com/document/product/616/118039)，细项能力见 [移动端/PC 能力资料](https://cloud.tencent.com/document/product/616/103616)。

**当前可直接使用的工具仍只有 Tencent BeautifyPic REST 与 IMS ImageModeration/CompareFace 已验证路径。**这两个候选的账号登录或 License 开通，不会自动把它们升级为 `reviewed_active`；开通后必须回到 Card、Adapter、权限/预算、真实 receipt、Gold 回归和产品负责人冻结的准入链。

### 控制台现场状态（2026-08-30）

腾讯 Web License 管理页的“正式/测试 License 均为 0”是提交前历史快照。产品负责人已提交 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app` 精确主机名的测试 License，当前控制台显示“正常”，有效期为 2026-08-30 至 2026-09-13；这只解决 Web License 资源绑定，不等于腾讯特效 SDK 细项能力或静态图 Adapter 已通过。火山候选仍按本文件的套餐/权限/真实 receipt Gate 保持 fail-closed。

## 2026-09-01｜Tencent Effect Web Cloud 证据更新

最新代码在 Cloud 重建后已能加载 page 6；旧进程缓存导致的导入错误已排除。真实 Web smoke
仍未运行，原因是 Cloud Secrets 尚缺 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、
`TENCENT_EFFECT_LICENSE_TOKEN`。因此当前只能确认“部署入口可加载”，不能确认静态图处理、细项
参数效果、性能或供应商图片留存。补齐配置后先用官方示例图做单次 smoke；Card、Adapter、
隐私/区域、成本、真实 receipt、Gold 回归和负责人批准仍需全部闭合，才可从 `candidate` 进入
`reviewed_active`。
