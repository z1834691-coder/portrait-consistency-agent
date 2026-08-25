# 腾讯 BeautifyPic API Gate

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

## 当前未完成的 live Gate

当前没有你的腾讯云账号、密钥、预算或经授权测试照片，因此**尚未发起真实腾讯请求**。代码、依赖、能力卡和无密钥安全失败路径已经准备好；这不等于 API 已经跑通。

## 以后由你执行的一次真实验证

1. 在自己的本机复制 `.env.example` 为 `.env`；只在其中填写自己的 `TENCENT_SECRET_ID` 与 `TENCENT_SECRET_KEY`，不要发送到聊天、截图或 Git；
2. 选择一张你有权使用的单人 JPG/PNG/BMP 图片；
3. 明确决定预算后运行：

   ```bash
   uv run python scripts/smoke_tencent_beautify.py --allow-live --image /绝对路径/authorized.jpg
   ```

4. 脚本会输出脱敏的 `ProviderRun`。成功时应含 `RequestId`、`result_ref`、`latency_ms`；失败时应含 `error_code`。结果图片只写入 Git 忽略的 `storage/results/`。

## 产品限制

- 产品 V0 后续仍会拒绝多脸输入，即使腾讯 API 可处理多个最大人脸；
- 这条 REST API 不支持唇厚、眼距、嘴型和鼻翼等细项，不能在 V0 假装支持；
- 实际调用前仍须由状态机检查用户确认 token、Profile 约束、幂等键和轮数上限。
