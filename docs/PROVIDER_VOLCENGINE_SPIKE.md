# 火山美颜 API V2 候选 Provider Spike（官方证据已核验，仍未接入）

> 日期：2026-08-30
> 状态：`candidate / evidence-reviewed / shell-only / not live`
> 本轮只核验公开的火山引擎一手资料；**没有读取或发送用户照片、没有使用密钥、没有真实 API 请求或结果图**。

## 1. 这一步到底确认了什么

火山的「美颜 API V2.0 传统修图接口（APIKey 版）」不是一个模糊的营销候选：官方文档已明确给出它的静态图处理主链路。系统向 `https://kickart.volces.com/openapi/ai_effect/submit` 提交任务，再向 `/openapi/ai_effect/query` 轮询；成功结果是 `result_url`。官方示例使用 `Authorization: Bearer <API_KEY>`，并以 `task_id` 串起提交与查询。[V2 接口文档](https://www.volcengine.com/docs/6705/2477693?lang=zh) / [官方 Python 示例](https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_602eefdc4c2ccc785188fb6b81fb4f25.py)

它也确实适合“静态照片、每张图不同参数”的方向：V2 文档列出脸型、眼睛大小、瘦鼻、白牙等固定参数；产品介绍明确把静态图与批量修图列为场景，并区分“自适应批量修图”和“固定参数微调”。但这不代表它已成为本项目的可执行能力——目前没有本项目账号的 API Key、价格/隐私书面确认、真实 TaskId、结果图或回归结果。

## 2. 已证实能力与不能夸写的边界

| 问题 | 官方证据能支持的结论 | 当前项目仍不能说什么 |
|---|---|---|
| 静态图 | 通过 `payload.resource_list` 传远程图片 URL，提交异步任务 | 不确认文件格式、尺寸上限、目标脸选择或多人图行为 |
| 单次任务 | V2 文档明确“每个任务只支持一张，多传无用” | 不能称“单请求批量处理” |
| 批量 | 产品页描述批量修图场景 | 本项目只能把批量实现为**多张独立单图任务**；并发/队列/最大总量未核验 |
| 脸型 | 已列出流畅脸、下颌线、去双下巴、自然瘦脸、窄脸、小头、颧骨、下巴长短、发际线等参数 | 参数是否在目标账号可用、实际视觉效果、是否只改选中单脸，都尚未 smoke |
| 眼睛 | 已列出 `eye`（眼睛大小，`[-50, 50]`）和 `eye_brighten` | 不支持把它说成已验证的眼距、眼宽、眼高或眼型控制 |
| 鼻子 | 已列出 `nose`（瘦鼻，`[-50, 50]`） | 不支持把它说成鼻翼、鼻高、鼻长等精细能力 |
| 嘴巴 | 已列出 `whiten_teeth`（白牙） | **不能**写成嘴型、嘴巴大小或唇厚可执行 |
| 眉毛、耳朵 | V2 静态 API 文档中未找到相应参数 | 不承诺自动执行 |

这一点会直接影响 RAG：RAG 可以检索并提出“火山 V2 候选”，却不能把“官方有瘦鼻”扩写成“已验证唇厚/鼻翼/眼距”，更不能绕过 Card 和 Adapter 调用它。

## 3. 实际 API 合同：已经知道什么，尚缺什么

```text
单张远程图片 URL
→ POST /openapi/ai_effect/submit
   template_id = 245621002
   payload.resource_list = [一个图片 URL]
   payload.extra.beautyToolConfigKey = beautyCustom_v1
   自定义参数时传 default 参数组
→ 得到 task_id
→ POST /openapi/ai_effect/query
→ 成功后取得 result_url
```

官方示例中的查询间隔为 5 秒、样例超时为 600 秒；这只是客户端轮询范例，**不是**服务 p50/p95 或 SLA。当前 Card 记录了真实键名和参数范围，但仍将全部参数标成 `official_parameter_documented_pending_live_smoke`：文档证据 ≠ 本项目真实效果证据。

认证还存在一个必须显式保留的交叉核验点：V2 API 页面与官方示例采用 Bearer API Key；产品总览中的“开通与鉴权”文字又写到控制台 AK&SK。当前项目只将“对 V2 请求的候选 header”为 `Authorization: Bearer <API_KEY>`，而不推断 API Key 如何购买、发放、与 AK/SK 的关系；获取账号后须让火山技术支持或控制台材料确认。

## 4. 隐私、地区、结果留存与价格：不能用“看起来像”代替证据

1. 图片会出站：请求体给火山服务的是远程图片 URL。因此即使本项目本地不保存原图，照片仍会被该 Provider 的服务取用；需要独立的“火山处理本次图片”同意，不能复用腾讯同意。
2. 服务条款写明：上传内容应有合法权利/授权；处理个人信息或跨境时，客户仍要遵守相关要求并取得必要同意；处理后的媒体任务结果可能被释放或销毁，用户应及时备份。[智能体验服务专用条款](https://www.volcengine.com/docs/6705/1544700?lang=zh)
3. 但这些条款**没有给出 V2 输入图的精确留存时长、物理处理区域、日志字段、是否零数据留存（ZDR）或模型训练退出机制**。所以 Card 必须继续写 `pending_vendor_confirmation`，不能因为条款有“匿名化改善服务”的表述就误称“不会留存/不会训练”。
4. 条款所写的普通许可地域为中国大陆，除非另有书面约定；这不是数据物理区域证明。部署前仍要取得数据处理区域的明确书面答复。
5. 产品页称美颜 API 采用“创点”计费，并建议通过商务/技术支持购买支持后付费 API 的创点套餐；公开资料中没有找到可用于本项目的 V2 单张人民币价格。SDK 年费报价属于另一条产品线，不能拿来估算 API 成本。

## 5. 输入、输出与当前 Gate

| 模块 | 已知输入/输出 | 当前规则 |
|---|---|---|
| Candidate Card | 只保存官方链接、版本、参数表、未核验事实 | `review_status=candidate`，不能被 RAG 或状态机当作可调用工具 |
| Request Contract | 仅 hash、字节数、候选参数、单图任务数 | 不保存/记录 Base64、原图路径、签名 URL 或密钥 |
| Permission/Budget Gate | 显式 `allow_live`、API Key、火山单独同意、出站、区域、预算、Adapter、Schema | 任一缺失即阻断；目前 Card 自身仍永久阻断 |
| Adapter shell | 安全元数据 → blocked receipt | 无网络路径、无 RequestId/TaskId、无结果图、`image_sent=false` |
| Batch orchestration（未来） | 多张照片各自计划、各自单图任务、各自复测 | 不复制同一套参数；并发与队列待成本/限流证据后冻结 |

## 6. 准入顺序（仍然不变）

```text
确认目标账号可获得 V2 API Key / 鉴权关系
→ 取得 V2 的价格、地区、输入/输出留存、日志和模型使用书面材料
→ 产品负责人冻结火山单独同意、单图/计划族预算、轮询超时与并发策略
→ 用明确授权的内部测试照片做一次单图 live smoke
→ 记录 task_id、结果 hash、端到端耗时、错误码（不记录原图/URL/密钥）
→ 结果解码、单脸隔离/回贴与本地几何复测
→ 运行 RAG Gold Set 与隐藏集回归
→ 产品负责人冻结 reviewed_active，才可把 shell 替换为真实 Adapter
```

当前可立刻安全做的是“实现真实 API 的数据合同与 mock/错误分类”；不能做的是把用户照片或 API Key 放进测试脚本，或把未核验的参数/价格写入产品承诺。

## 7. 本轮离线 Trace

```text
读取官方 V2 文档与官方示例
→ 发现：一任务一张远程图片、submit/query 异步链路、task_id/result_url、Bearer API Key 样例
→ 发现：静态图/批量场景存在，但 V2 请求级不支持多图
→ 将可证实字段写入 candidate Card
→ 保留：地区、输入留存、日志、模型使用、价格、并发、真实效果 = pending
→ 执行 shell 的预检：card_not_active / card_not_ready
→ network_called=false；image_sent=false；无真实 Provider receipt
```

## 8. 官方来源与需要账号/商务确认的精确问题

- [美颜 API V2.0 传统修图接口（APIKey 版）](https://www.volcengine.com/docs/6705/2477693?lang=zh)：异步 submit/query、单图任务、template/extra、参数表。
- [V2 官方 Python 示例](https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_602eefdc4c2ccc785188fb6b81fb4f25.py)：`kickart.volces.com`、Bearer API Key、`task_id`、`result_url`、轮询样例。
- [美颜 API 产品介绍](https://www.volcengine.com/docs/6705/2441388)：静态图/批量场景、两种修图模式、创点计费和开通说明。
- [智能体验服务专用条款](https://www.volcengine.com/docs/6705/1544700?lang=zh)：客户授权、服务地域、任务结果释放/销毁及数据安全责任边界。

火山控制台/技术支持需要针对**本项目的 V2 API Key 账号**回答：

1. API Key 的开通、购买与 AK/SK 的关系；测试额度与可用模板是否已开通；
2. V2 输入支持的格式、尺寸、URL 可访问要求、多人图和目标脸选择行为；
3. 当前地区、数据处理区域、输入/输出/日志的精确留存期，是否存在 ZDR 或训练退出选项；
4. 每次单图的创点/人民币价格、免费额度、并发/限流、错误码、幂等与任务超时；
5. 允许本项目“单张与组图”静态照片处理的许可范围，以及白名单/回调/域名要求。

实现位置：`src/portrait_consistency_agent/services/volc_beauty.py`、`data/provider_cards/volcengine_beauty_api_v2.json` 与 `scripts/smoke_volc_beauty.py`。离线测试见 `tests/test_volc_beauty.py`。

## 9. 当前不可用的定位与手动开通

本候选不是接口不存在，而是目标账号的美颜 V2 服务、API Key/创点、区域/留存、价格/限流和本项目 Adapter 还没有形成可核验闭环。当前 smoke 固定为 `not_run` 且不联网；即使拿到 Ark 侧的通用 Key，也不能直接证明 `kickart.volces.com` 的美颜 V2 权限已开通。手动登录火山控制台，在美颜 API V2 页面确认服务/测试额度和 API Key，在 IAM 核对调用权限，再向官方支持确认 Key 类型、数据边界和计费，之后才可用内部授权图做一次单图 smoke。密钥仅放部署 Secrets，不写入本文件、Trace 或聊天。
## 2026-08-30 官方计费与准入复核（部署前收口）

本轮重新核对火山引擎官方《美颜 API 产品介绍》和《美颜 API V2.0 传统修图接口文档》。官方明确：美颜 API 已接入智能创作云/创作 Agent，采用“创点”计费；调用前需要购买支持后付费 API 的创点套餐，API Key（AK/SK）和回调凭证只是鉴权材料，不等于可用额度。官方公开页没有给出本 API 的单次调用价格或个人免费试用额度，创点购买链接要求联系技术支持获取。因此仅有 IAM/智能创作云权限不足以证明可以免费调用。

同一产品线公开的“智能美化特效 SDK 套餐”价格不能直接套用到 V2 API：B1 年包 6 万元，B2/B3/A1 年包 18 万元，A2 28 万元，A3 42 万元，双端更高；这是 SDK 授权报价，不是本项目 V2 API 创点单价。若只为个人 Demo 购买，最低公开 SDK 档位也明显超出当前预算，而且 API 仍需另行确认创点、回调凭证、区域、留存和试用额度。

**当前产品结论：** V0 放弃火山美颜真实接入，保留 candidate Card 和 fail-closed shell，不申请采购、不填密钥、不发送照片；继续使用已有腾讯 BeautifyPic 路径。未来只有在厂商书面给出低成本测试额度、实际 API 价格、License/留存/区域和真实 schema 后，才重新开启“Card → Adapter → 权限/预算 → live receipt → Gold 回归”准入 Gate。

官方依据：

- [美颜 API 产品介绍（创点与购买支持后付费 API）](https://www.volcengine.com/docs/6705/2441388)
- [美颜 API V2.0 传统修图接口文档（APIKey 版）](https://www.volcengine.com/docs/6705/2477693?lang=zh)
- [智能美化特效 SDK 套餐与公开年包价格](https://www.volcengine.com/docs/6705/1544706?lang=zh)
