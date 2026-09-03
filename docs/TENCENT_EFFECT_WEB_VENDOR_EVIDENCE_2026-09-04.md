# 腾讯特效 Web 供应商准入证据（2026-09-04）

> 这份文档只回答“腾讯官方资料明确写了什么、项目因此能承诺到哪一步”。它不把官方宣传、一次成功回执或测试 License 写成生产级视觉效果、数据留存或合规承诺。当前准入范围是 `private_demo_beta`，不是公网生产。

## 1. 已核对的官方资料

| 主题 | 官方资料与可核对事实 | 项目采用的边界 | 证据级别 |
|---|---|---|---|
| Web 功能与静态图 | [Web 端功能说明](https://cloud.tencent.com/document/product/616/86944) 与 [图片处理教程](https://cloud.tencent.com/document/product/616/118039) 说明 Web 端 `takePhoto()` 可返回 `ImageData`，再由业务方绘制到 Canvas；静态图片示例在浏览器执行。 | 结果由浏览器组件短暂持有；通过一次性 handoff 进入共同 `VerificationResult`，Python/SQLite 不保存结果图。 | A：官方文档 |
| License / 域名 | [快速上手](https://cloud.tencent.com/document/product/616/71371) 说明 Web License 与网站域名绑定；测试 License 有效 14 天，可续期一次，最长 28 天；Token 用于签名，正式环境应迁移到服务端。 | Streamlit 精确域名只用于受邀私有 Demo；签名服务端生成；不宣称测试 License 支持长期生产。 | A：官方文档 |
| 正式价格 | [Web 端价格总览](https://cloud.tencent.com/document/product/616/86942) 列出精准域名套餐：基础版 5999 元/月、专业版 8999 元/月；高级版 35000 元/月并支持泛域名。一个正式 License 绑定一个 Web domain。 | 价格已知，但没有把购买行为默认为产品授权；正式长期使用前必须重新核验套餐、地域、合同和预算。 | A：官方文档 |
| SDK 版本 | [SDK 下载](https://cloud.tencent.com/document/product/616/65876) 当前列出 Web 端 SDK，并提示使用最新版本；[Web 开始接入](https://cloud.tencent.com/document/product/616/71364) 说明需 License Key、账号 APPID 与 Token 签名。 | Card/Adapter 记录桥接版本、SDK URL 和签名字段；版本升级要重跑回归与准入，不自动沿用旧结论。 | A：官方文档 |
| 个人信息告知与同意 | [腾讯特效 SDK 合规使用指南](https://cloud.tencent.com/document/product/616/102032) 要求披露第三方 SDK、在取得用户同意后再初始化，并按实际采集信息和用途告知；[个人信息保护规则](https://cloud.tencent.com/document/product/616/65678) 将图片/相机画面列为实现功能所需的个人信息类型。 | 产品在发送前单独告知图片会进入腾讯 Web SDK；只接受本人/已获授权成人照片；公开演示另行授权；拒绝授权则停在本地或手动降级。 | A：官方文档 |

## 2. 项目没有从官方资料得到的事实

以下事项在当前公开资料中没有得到足够明确、可直接用于生产承诺的证据，因此不能写成“已确认”：

- 腾讯 Web 静态图处理的生产数据中心、跨境路径、具体留存时长和供应商侧删除 SLA；
- 当前测试 License 是否允许对外公开演示、受邀人数、并发与流量上限；
- 以本项目图片、参数和浏览器环境计算的稳定单图成本、峰值延迟与批量上限；
- Web generic `lift / shave / eye / chin` 对每一种脸型、角度和表情的视觉改善保证。

因此 Card 的 `vendor_image_egress`、`vendor_retention`、`region` 和 `telemetry` 仍使用“项目未建立”口径。`region_approved=true` 只表示**本次负责人批准的私有 Demo 传输范围**，不表示腾讯生产区域已被核验。

## 3. 本次准入采用的范围解释

为了不让“测试可运行”和“正式上线”混在一起，准入命令使用如下解释：

```text
promotion_scope = private_demo_beta
license_active = 当前受邀 Demo 的有效测试/授权 License
exact_domain_bound = 当前 Streamlit 精确域名与 License 绑定一致
region_approved = 负责人仅批准本次私有 Demo 的出站范围
estimated_cost_known = 已知道正式套餐价格；不等于已购买或单图成本已校准
```

在这个范围内，Card 晋级只意味着：**可以在受邀私有 Demo 主流程中尝试该 Web Adapter，并保留共同复测和 Trace**。它不意味着：已完成公网部署、生产合规、长期数据留存审计、批量效果保证或 RAG 自动授权。

## 4. 重新准入触发条件

下列任一变化都要把 Card 退回 `candidate` 或重新评审：

1. 域名、License、APPID、Token、SDK URL 或桥接版本变化；
2. 处理范围从受邀私有 Demo 扩大到公网、商业用户或新的地域；
3. 供应商的价格、隐私政策、数据处理条款或 SDK 版本变化；
4. 结果图不再只保留在浏览器/短时内存，或新增批量、视频、多人脸处理；
5. 多样本共同 `VerificationResult`、异常隔离或回归 Gate 退化。

## 5. 本轮项目结论

官方资料足以支持“Web 静态图 SDK 可以在精确域名的受邀 Demo 中被调用”，也支持把正式套餐价格和同意告知列为可审计事实；它不足以支持“生产地区/留存已确认”或“母版一致性已泛化”。因此后续 promotion 必须写入 `private_demo_beta` scope，页面继续不显示密钥、结果图只在当前会话展示，RAG 仍然只能提出建议。
