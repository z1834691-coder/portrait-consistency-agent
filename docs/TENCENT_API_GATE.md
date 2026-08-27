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
- 成功必须保存 `RequestId`、本地结果引用和耗时；失败必须保存错误码；
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
- 结果图：`storage/results/1e519f22-b119-41bb-9242-76798f7cab61.jpg`；
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

ImageModeration 尚未发起 live 调用；需要先确认 IMS 服务开通、BizType（可留空使用默认策略）和调用预算。

## 后续重复验证规则

1. 继续只在本机 `.env` 中保存凭据，不发送到聊天、截图或 Git；
2. 每次选择一张明确获授权的图片；
3. 在预算和调用次数可控的前提下运行：

   ```bash
   uv run python scripts/smoke_tencent_beautify.py --allow-live --image /绝对路径/authorized.jpg
   uv run python scripts/smoke_tencent_compare_face.py --allow-live \
     --reference /绝对路径/reference.jpg --target /绝对路径/target.jpg
   ```

4. 脚本会输出脱敏的 `ProviderRun`。成功时应含 `RequestId`、`result_ref`、`latency_ms`；失败时应含 `error_code`。结果图片只写入 Git 忽略的 `storage/results/`。

## 产品能力策略

- 当前 Provider Card 声明支持的参数原则上都可执行；腾讯当前能力卡对应瘦脸、大眼、美白、磨皮；
- 美白和磨皮默认关闭，只有用户明确允许肤色/皮肤质感变化时才可打开；
- 眼距、嘴型、唇厚、鼻翼等未来参数可保留在产品合同中，但必须等某个外部 Provider Card 确认能力后再由对应 Adapter 执行；不能把“建议”写成“已经执行”；
- 多脸若要支持用户选择目标脸，需要在调用 API 前后完成安全的目标脸选择、隔离/裁剪、回贴和复测链路；当前 Adapter 尚未实现这部分。在此之前不能直接把多脸整图发送给接口并承诺只修改所选脸；
- 用户层可以表达超出范围的相对愿望，但 Adapter 绝不能发送小于 0 或大于 100 的腾讯绝对参数；截断/拒绝和解释由确定性规划策略负责；
- 实际调用前仍须由状态机检查用户确认范围、Profile 约束、幂等键和可配置轮次上限。
- `ProviderRun v0.2` 已区分 attempt、Provider Card、参数投影、确认作用域、结果生命周期和结构化错误；smoke 脚本已同步该结构并完成不联网 dry run，但没有再次使用人脸照片发起付费 live 调用。上面的真实 RequestId 是升级前成功证据；BeautifyPic 的执行按钮和修后复测仍未接入页面。
