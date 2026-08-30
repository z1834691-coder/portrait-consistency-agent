# 腾讯 API Gate（BeautifyPic / CompareFace / ImageModeration）

## 检查点 6 新增的两条 Provider 能力

- `CompareFace`：腾讯 IAI，API `2018-03-01`，端点 `iai.tencentcloudapi.com`，模型固定请求 `3.0`；只用于当前会话两张已授权图片的同人路由，保存原始分和 RequestId，不展示为概率。
- `ImageModeration`：腾讯 IMS，API `2020-12-29`，端点 `ims.tencentcloudapi.com`；`Pass` 才能通过内容安全门，`Review/Block` 在 V0 都保守拦截。`BizType` 可在本地 `.env` 配置，不写进代码。
- 两者的输入都只在本次调用内存中转为 Base64；Trace 只保留哈希/状态/版本/回执引用，不保存 Base64 或原图。

官方来源：[CompareFace](https://cloud.tencent.com/document/api/867/32802)、[CompareFace 分数说明](https://cloud.tencent.com/document/api/867/114852)、[ImageModeration](https://cloud.tencent.com/document/product/1125/53273)。

## 已实现的边界

- 使用腾讯云官方 Python SDK 的 FMU 产品包；
- 接口：`BeautifyPic`，API 版本 `2019-12-13`，默认端点 `fmu.tencentcloudapi.com`；
- V0 只用 `Image` Base64 输入、`base64` 输出；四个参数永远显式发送：`FaceLifting`、`EyeEnlarging`、`Whitening`、`Smoothing`；
- 不把腾讯的非零默认值误认为“未调整”；V0 从四个 `0` 值开始；
- 成功必须保存 `RequestId`、不透明结果引用/哈希和耗时；失败必须保存错误码；当前产品结果字节不落盘；
- 默认脚本不读图片、不联网。只有 `--allow-live` 和本地密钥同时存在时才可发起请求。

## 官方来源

- [BeautifyPic 人脸美颜 API](https://cloud.tencent.com/document/product/1172/40715)：端点、版本、输入/输出、四个参数范围/默认值、`RequestId`；
- [人脸试妆 API 概览](https://cloud.tencent.com/document/product/1172/40697)：默认 20 QPS 限频；
- [腾讯云 Python SDK](https://cloud.tencent.com/document/sdk/python)：SDK 安装与凭据安全要求。

2026-08-27 复核：官方 `BeautifyPic` 文档仍规定四个强度参数范围均为 `[0,100]`，Base64 编码后不超过 5M、单边不超过 4000，支持 PNG/JPG/JPEG/BMP；短边小于 64 或脸部小于建议的 34×34 会进入已知错误；接口可处理一张图中最大的五张人脸，但没有“选择指定人脸”的输入参数。

## 当前 live Gate 状态

真实 live Gate 已完成一次成功验证：

- 测试照片：用户明确授权的本地单人照片；
- 参数：`FaceLifting/EyeEnlarging/Whitening/Smoothing` 均显式传 `0`；
- `status=succeeded`；
- `RequestId=1e519f22-b119-41bb-9242-76798f7cab61`；
- `latency_ms=3438`；
- 历史结果图：`storage/results/1e519f22-b119-41bb-9242-76798f7cab61.jpg`；该文件产生于 8B 会话内结果规则冻结前，仅保留为历史 Gate 证据；
- 运行记录：`run_id=run_9559220a5f844122928399cd9d50cd9b`。

这证明了凭据、`fmu` 服务级权限、服务开通、SDK 签名和单次图片处理链路可以工作；不代表批量能力、稳定性、成本、相似度判断或用户可接受性已经验证。

### CompareFace live Gate（2026-08-27，历史记录｜权限补齐前）

- 使用用户先前明确提供的单人本地照片做同图对同图 smoke；本地 OpenCV 质量门检测到 1 张脸后才发起请求。
- 请求已到达腾讯并返回 `RequestId=b1584fbb-f750-4536-b4a5-2b6c3803a67b`，但返回 `AuthFailure.UnauthorizedOperation`。
- 结论：SDK、端点、签名和错误回执路径已验证；当前 CAM 身份还缺少 `iai:CompareFace` 权限，未获得成功分数，不能写成同人能力已上线。
- 待处理：在腾讯 CAM 给实际运行身份补充最小 `iai:CompareFace` 调用权限；补权后只需重跑同一 smoke，不改变产品规则。

### CompareFace 第二次 live Gate（2026-08-27，历史记录｜服务开通前）

- 使用同一张用户明确授权的单人 JPEG 复测；本地质量门检测到母版/目标照各 1 张脸后发起请求。
- 请求返回 `RequestId=d5d85fc4-c25d-4ac7-8075-7a09c73ac677`，错误码为 `ResourceUnavailable.NotExist`。
- 该错误表示 IAI 人脸识别服务尚未在控制台开通（不是 CAM `iai:CompareFace` 权限错误）。成功复测前，不生成 `subject_match` 结论，也不把检查点 6 标记为通过。
- 结果：本节记录服务尚未开通时的历史失败；服务开通后的成功结果见下一节。

### CompareFace 第三次 live Gate（2026-08-27，IAI 服务已开通，已通过）

- 使用同一张用户明确授权的单人 JPEG；本地质量门检测到母版/目标照各 1 张脸。
- 请求返回 `status=succeeded`，`RequestId=b89e828a-8038-41d3-a598-575fdba23521`，`FaceModelVersion=3.0`，`raw_score=100.0`。
- 策略路由为 `match`；`calibrated=false`，原始分只进入后台 evidence，不作为 V0 用户可见概率或一致性分数。
- 此次 smoke 证明 IAI 服务开通、CAM 最小权限、SDK 签名、端点、请求参数、响应解析和路由证据链均可工作。

### ImageModeration 第一次 live Gate（2026-08-27，权限失败回执）

- 使用用户明确授权的单人本地照片，运行新增的 `smoke_tencent_image_moderation.py --allow-live`；脚本不输出文件名、Base64、标签详情、密钥或原图；
- 请求返回 `RequestId=42c6ed4d-f035-466c-b775-4728dd43ca93`，错误码 `UnauthorizedOperation.Unauthorized`，`status=failed`；
- 结论：请求已经到达腾讯，签名、端点和错误回执通路存在；但实际运行身份或 IMS 服务尚未获得成功审核所需授权，**没有得到 `Pass/Review/Block`，不能称内容安全已验证或图片已审核通过**；
- 下一步：用户在腾讯控制台补齐实际运行身份的 IMS `ImageModeration` 调用权限/服务开通后，再对一张明确授权照片重跑一次；成功前，Demo 不能依赖 IMS 放行进入完整执行路径。

### ImageModeration 第二次 live Gate（2026-08-27，用户称 IMS 已关联后仍权限失败）

- 用户确认 IMS 已关联后，使用同一张明确授权的单人 JPEG 再运行一次 `smoke_tencent_image_moderation.py --allow-live`；脚本仍不输出文件名、Base64、标签详情、密钥或原图；
- 请求真实到达腾讯，返回新的 `RequestId=9385fe01-f182-4d74-9a52-3e6eb8be824a`，错误码仍为 `UnauthorizedOperation.Unauthorized`，`status=failed`；
- 因为这是一条新的服务端回执，它排除了“旧回执没有重跑”的可能，但不能证明 IAM 已生效。腾讯官方 IMS 权限文档将这一类错误对应为当前 SecretId 所属主体缺少 `ims:ImageModeration` 对资源 `*` 的允许权限；本项目客户端没有保存腾讯完整错误正文，因此将其作为**待核对的高置信根因**，而不是伪造一条更细的腾讯错误；
- 下一步不是再盲目重试：在 CAM 的“策略生成器”中选服务 `ims` / 操作 `ImageModeration` / 资源“全部资源”，并将策略关联到**本机 `.env` 里当前 SecretId 所属的子用户或角色**，而不是只关联到登录控制台的账户。临时 Demo 可采用官方文档提到的 `QcloudIMSFullAccess` 验证身份归属；更小权限的正式做法是只允许这一项操作。确认后只再 smoke 一次；
- 在得到 `Pass`、`Review` 或 `Block` 之前，内容安全 Gate 仍为失败，系统必须 fail closed，不能把用户照片送入完整编辑路径。

### ImageModeration 第三次 live Gate（2026-08-27，CAM/密钥身份已核对后仍未通过）

- 用户确认本机 `.env` 的 `TENCENT_SECRET_ID` 与 CAM 子用户 `agent+beautify` 的 API 密钥相同；随后使用同一张明确授权的单人 JPEG 仅再运行一次 `smoke_tencent_image_moderation.py --allow-live`。
- 请求真实到达腾讯，返回新的 `RequestId=365e169e-427e-4550-8f60-316ab3dc94d5`，错误码仍为 `UnauthorizedOperation.Unauthorized`，未产生 `Pass/Review/Block`。
- 在不修改云账号的前提下，已在 CAM 控制台只读核对：自定义策略 `policygen-20260827181624` 当前版本允许 `ims:*`、资源为 `*`，并直接关联到 `agent+beautify`。这排除了“未创建该策略、未关联该子用户、或使用了不同 SecretId”这三个此前高优先级假设。
- 随后只读打开主账号的内容安全控制台 `cms/clouds/package`，页面显示“立即开通”。腾讯官方接入文档要求先由主账号开通图片内容安全服务并完成业务配置；因此当前更高优先级阻塞是**IMS 服务尚未完成开通/可用套餐或后付费配置**，而不是继续新建 CAM 策略。
- 下一步需要用户在该“立即开通”页面自行确认服务条款、试用包或后付费等可能产生费用的选择；完成后再由本项目对同一明确授权照片只重测一次。若仍失败，再使用 CAM 模拟策略和该次 RequestId 向腾讯支持定位，不盲目重复上传。
- 在得到 `Pass`、`Review` 或 `Block` 前，内容安全 Gate 仍保持 fail closed，不能将图片安全地送入完整编辑路径。

### ImageModeration 第四次 live Gate（2026-08-27，IMS 服务开通后，已得到真实结果）

- 用户完成 IMS 服务开通后，对同一张明确授权的单人 JPEG 仅重跑一次 `smoke_tencent_image_moderation.py --allow-live`。
- 请求返回 `status=succeeded`、`network_called=true`、`RequestId=21bf408d-929a-46ec-83aa-78f071eff556`、API 版本 `2020-12-29`，说明真实服务、SDK 签名、CAM 权限、服务开通与响应解析链路都已闭合。
- 腾讯返回的是 `Block`；本项目将其保守映射为 `content_safety.status=blocked`、`reason_code=content_safety_provider_blocked`。为避免将用户照片的敏感标签落入 Trace，脚本不打印 Provider 的具体标签或分数。
- 这证明的是“内容安全门能真实给出并执行一条拒绝决定”，**不**证明该照片安全，也不证明产品 Happy Path 已通过。该照片不得进入 Profile、同人或修图；若要验证允许路径，需要未来用另一张明确授权的、服务实际返回 `Pass` 的照片单独测试。
- 至此，IMS 的“服务可调用 + 拒绝路径”Gate 已通过；无需再修改 CAM 策略或重复当前这张被拦截的照片。

### ImageModeration 第五次 live Gate（2026-08-28，用户提供的另一张授权照片，允许路径已验证）

- 用户明确授权使用另一张单人 JPEG，并要求在不打断本地应用的情况下完成一次真实 IMS smoke；本次只读图片用于内存 Base64 请求，不把文件名、原图或标签详情写入 Trace；
- 请求返回 `status=succeeded`、`network_called=true`、`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`、API 版本 `2020-12-29`，Provider `Suggestion=Pass`；本地映射为 `content_safety.status=passed`；
- 本次样本脱敏 SHA-256 为 `513bddd89f6b52eb3dc508db5e4485a10a8ffc66db5e2296bdf2ac6772046006`，仅用于回放时确认输入一致，不代表照片内容或用户身份；
- 这条回执闭合了“真实允许结果 → 可以进入后续质量/同人/Profile/规划门”的单样本证据，但不证明所有照片都会 Pass，也不替代多样本内容安全评测。此前真实 `Block` 记录继续保留，V0 仍对 `Review/Block` fail closed。

### 2026-08-30｜授权测试照片的当前真实内部 Smoke

- 产品负责人明确授权使用一张本地单人照片，仅用于内部腾讯 Gate 与 BeautifyPic Smoke；图片全程仅在本机进程与腾讯本次请求内存中存在，不写入项目仓库、Trace 正文或结果目录。
- ImageModeration 返回 `status=succeeded`、`content_safety.status=passed`、`RequestId=dc9e3e2b-808c-4bd0-8cd0-0f3429a4f432`；输入只记录脱敏 SHA-256 `513bddd89f6b52eb3dc508db5e4485a10a8ffc66db5e2296bdf2ac6772046006`。
- 随后 BeautifyPic 以显式参数 `FaceLifting=5`、`EyeEnlarging=5`、`Whitening=0`、`Smoothing=0` 成功返回，`RequestId=eb9c8393-81c0-40fa-8a4e-b8790e126ea9`，端到端网络耗时 `1924 ms`；结果图仅内存解码，Trace 只记录结果哈希和内存生命周期引用。
- 这证明当前腾讯既有能力的“授权照片 → 内容安全 Pass → 单次参数级编辑 → 脱敏 ProviderRun”路径在一个内部样本上可用；不证明母版一致性提升、视觉自然度、批量稳定性、用户满意度或新 Provider 能力。

## 后续重复验证规则

1. 继续只在本机 `.env` 中保存凭据，不发送到聊天、截图或 Git；
2. 每次选择一张明确获授权的图片；
3. 在预算和调用次数可控的前提下运行：

   ```bash
   uv run python scripts/smoke_tencent_beautify.py --allow-live --image /绝对路径/authorized.jpg
   uv run python scripts/smoke_tencent_compare_face.py --allow-live \
     --reference /绝对路径/reference.jpg --target /绝对路径/target.jpg
   uv run python scripts/smoke_tencent_image_moderation.py --allow-live \
     --image /绝对路径/authorized.jpg
   ```

4. 脚本会输出脱敏的 `ProviderRun`。成功时应含 `RequestId`、`result_ref`、`latency_ms`；失败时应含 `error_code`。当前脚本在内存中解码结果，只输出 `session_memory` 生命周期投影，不再把结果图片写入 `storage/results/`。

## 产品能力策略

- 当前 Provider Card 声明支持的参数原则上都可执行；腾讯当前能力卡对应瘦脸、大眼、美白、磨皮；
- 美白和磨皮默认关闭，只有用户明确允许肤色/皮肤质感变化时才可打开；
- 眼距、嘴型、唇厚、鼻翼等未来参数可保留在产品合同中，但必须等某个外部 Provider Card 确认能力后再由对应 Adapter 执行；不能把“建议”写成“已经执行”；
- 多脸若要支持用户选择目标脸，需要在调用 API 前后完成安全的目标脸选择、隔离/裁剪、回贴和复测链路；当前 Adapter 尚未实现这部分。在此之前不能直接把多脸整图发送给接口并承诺只修改所选脸；
- 用户层可以表达超出范围的相对愿望，但 Adapter 绝不能发送小于 0 或大于 100 的腾讯绝对参数；截断/拒绝和解释由确定性规划策略负责；
- 实际调用前由检查点 8B 执行 Gate 检查用户确认范围、Profile 约束、照片 hash、Gate、幂等键和可配置轮次上限；首轮页面仅在用户勾选/点击后才能发请求。8C-2 的子轮若仍在同一首次确认 scope 内，则先写入 `auto_followup_preflight` 后自动发请求；scope、用途、Provider、出境方、预算或同意状态变化时 fail closed 并重新授权。
- 合同 `v0.4` 已区分 attempt、Provider Card、参数投影、确认作用域、结果生命周期和结构化错误，并新增 8C 策略提议/目标证据字段；8B 确认后执行按钮、一次调用和 ProviderRun 已接入页面并通过离线 fixture Trace，8C-1 已接入会话内本地修后观察与 `VerificationResult`。当前没有新的 UI 8C live receipt，外部/混合复测仍未接入；ImageModeration 已有一条真实 Pass 和一条真实 Block，但这仍只是单样本路由证据，不等于完整审核覆盖。
