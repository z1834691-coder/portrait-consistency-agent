# 产品规则与六合同审计

> 版本：`v0.13-frozen`｜更新：2026-08-29（RAG P0-C 受限回接 8A / 8C 并同步）
> 这份文档记录已经冻结的产品规则、仍需后续讨论的规则，以及这些规则对六个数据合同的影响。当前整体执行真相源见 [母版人像一致性Agent-执行版PRD.md](母版人像一致性Agent-执行版PRD.md)。

## 0. 本轮审计结论

本轮用户已经确认的核心方向：

- 产品目标是让目标照片的人脸视觉上接近用户的母版，而不是身份搜索、身份认证或审美打分；
- 不在产品界面展示一个硬编码的 0—100“一致性指数”，也不把 90 设为固定目标线；
- 如果未来展示概率，只能展示经过真实样本校准的“人类接受概率”，没有校准证据就不展示概率；
- V0 明确不展示任何接受概率；后续是否展示属于新的产品决策；
- 腾讯 API 能力卡中实际支持的参数原则上都可以执行；美白、磨皮默认关闭，必须由用户明确允许；
- 眼睛、脸型、鼻子、嘴唇等五官和脸型是主要一致性对象；肤色、妆面、身体和隐私部位不进入母版档案；
- 母版每次只有一个生效版本；新母版成功建立后替换旧版本；母版照片本身不提供二次编辑入口；
- 母版保存加密、可删除、受限访问的派生主体表示，保存期为半年；到期后提醒重新上传，或删除主体锚点、降级为只使用归一化几何特征；
- 质量不足时先解释原因并让用户重新上传；批量模式中单张失败不阻塞其他照片，但要在处理前告知用户；
- 多脸照片在满足质量条件时自动隔离背景、只编辑用户选择的单脸；无法安全隔离、回贴或复测时，说明具体原因并要求用户先裁剪为单脸后重新上传；
- 受邀 Streamlit 部署仍是后续方向；具体平台、访问控制、区域、费用上限和是否购置服务器设备尚未决定，当前继续在本机开发；
- `IntentFrame`、`EditPlan`、`ProviderRun`、`VerificationResult` 的耦合纠错及最后五项产品决定已经由用户确认；
- 六合同及其生命周期/反馈语义已升级为 Python `v0.4-frozen`；SQLite 保留六类业务合同表，并新增匿名 `product_events` 运营账本和本地管理员 Dashboard；RAG P0-A/P0-B/P0-C 额外使用独立知识库/合同，不混入用户运行账本；全量测试通过数以本轮实际运行回执为准。
- 用户意图、满意度和行为事件分开保存：首次 Prompt 是强意图，不是满意；点赞/点踩/明确评论是强反馈；退出和沉默默认未知，只有在明确上下文下标记为当前路径中止。
- 当前会话同人门采用腾讯 CompareFace 3.0；`match/uncertain/no_match` 的临时路由独立于质量门。跨会话长期能力采用本地加密派生主体锚点，但真实特征提取模型许可、AES-GCM 存储、TTL/delete worker 仍待开发。
- 内容安全采用本地预检 + 腾讯 IMS `ImageModeration`，`Review/Block` 保守拦截；服务开通后已得到真实 `Block` 回执，随后新授权照片又得到真实 `Pass`，说明 Adapter 的拒绝与允许路由都有证据。被拦截的照片仍不建档、不进入同人或修图；单次供应商结果不等于完整内容安全覆盖。
- LLM 主模型冻结为 DeepSeek V4 Flash；检查点 7 已实现文本 `IntentFrame` Adapter、显式文字授权、Pydantic Schema 校验和本地模板 fallback，并完成一次固定文本的真实 live receipt；不自动转发到第二个云 Provider。
- 检查点 8A 已冻结并实现：在通过质量/内容安全/当前会话同人门后，确定性规划器比较母版与目标的归一化几何，严格双眼测量满足条件时同时规划瘦脸/大眼；生成 `proposed`、必须确认的 `EditPlan`。
- 检查点 8B 已冻结并实现：确认页不提供滑杆改原计划；实质改口必须重新规划并重新确认。一次确认绑定当前照片 hash、Profile 版本、计划参数和允许部位，10 分钟内只允许一次外部调用；结果只在当前浏览器会话内临时展示/由用户下载，不落 SQLite、JSONL、Trace 或结果目录；超时/网络错误也不自动重试。
- <span style="color:#C00000"><strong>检查点 8C-1/8C-2 已实现：</strong>结果图可在内存中重新观察，`VerificationStrategyProposal` 在已审核/已授权策略集合中提出复测方案，`VerificationResult` 按目标特征输出趋势和 STOP/REPLAN/RESHOOT/MANUAL_REVIEW；`REPLAN` 会在证据、首次外部处理同意和计划族 scope 均满足时生成并自动执行子计划，不再逐轮等待参数点击。</span>
- <span style="color:#C00000"><strong>8C 迭代与反馈规则已实现：</strong>初次确认授权有界计划族，最多三轮；每轮使用新的 `EditPlan`、独立 `ProviderRun` 与父子血缘，只有出现方向正确且可验证的累积改善才继续。点赞/点踩和文字评论会留下强反馈事件；点踩或文字评论关闭当前计划族，追问/新会话/下载为继续使用或行为证据，退出/沉默按上下文记录为未知。自动续跑不等于静默执行：每次都会写入策略、scope、hash、轮次、预算和调用结果 Trace。</span>
- <span style="color:#C00000"><strong>RAG P0-A / P0-B / P0-C 已实现的能力与边界：</strong>3 张人工审核 Provider Card 已导入独立 SQLite 知识库并拆成 10 条 `KnowledgeChunk`；每次查询先做生命周期/Provider/operation/region metadata 过滤，再做 FTS5，P0-B 追加本地 dense 召回、RRF 和 rerank，最终仍经过同一证据分类和过期/冲突/缺槽/注入安全降级。P0-C 已在 8A 计划前、8C 策略选择前消费这些证据，分为 direct/reference/conflict 并留下脱敏 Trace/Bad Case；页面只展示来源/版本/简短支持或降级理由。它不读照片/用户原话、不调用 LLM/Tencent/新 Provider、不生成参数或 ProviderRun；`execution_authorized=false`，因此不是 RAG 自动修图。</span>
- <span style="color:#C00000"><strong>RAG 的冻结路由规则：</strong>无冲突时 direct evidence 可以作为已有确定性规划器/策略选择器的输入，reference 只辅助解释；硬冲突必须展示双方来源、阻断执行，用户/LLM 只能选人工复核、手动建议或停止；检索 miss、索引故障、缺关键槽或没有 direct evidence 时，RAG 分支立即返回“当前不知道”，记录脱敏 bad case，不能让 LLM 编造。既有、独立审核且普通 Gate 已通过的 baseline 才可原样保留，不能借 RAG 扩大能力。新 Provider 仍须 Card → Adapter → 权限/预算 → live smoke → Gold 回归 → 产品冻结，RAG 搜到资料不等于可执行。</span>
- <span style="color:#C00000"><strong>数据闭环已确认：</strong>短期记录任务事实、首条 Prompt/追问/再开一轮、下载/重传、点赞/点踩/文字反馈、复测路由和上下文退出；长期聚合 Profile 建立率、首次成功修图率、7/30 日回访、WAU、MAU、会话完成率、失败后重传率和明确满意/不满意比例。它们进入匿名 `product_events` 和 Dashboard，用于迭代，不是训练 Dataset；退出/沉默没有上下文证据时只能是 `unknown`。</span>
- <span style="color:#C00000"><strong>数据出境与权限已确认：</strong>DeepSeek 只收脱敏最小必要文本和结构化上下文，不接收照片、Base64、向量、主体锚点、密钥或原始 Trace；失败先走本地模板，不自动转发第二个云 Provider，OpenRouter/跨境默认关闭。处理本次照片、发送给外部 Provider、保存主体锚点半年、允许公开演示分别取得同意；仅本人单人照片默认放行，未成年人拒绝，多人须确认所有人授权；IMS `Review/Block` 保守拦截。ZDR 必须以供应商当前合同/配置核验，不能仅凭文案假定。</span>

- <span style="color:#C00000"><strong>RAG 状态同步（本条优先于早期“未实现”描述）：</strong>执行知识只来自官方资料和项目人工审核内容，过期/撤回/硬冲突知识不得放行；P0-A/P0-B 已实现本地 SQLite、结构化 query、metadata/FTS、本地 dense/RRF/rerank、完整 Trace、Gold Set 对应的定向安全案例和用户依据卡；P0-C 已把受限 evidence 回接运行链，另有只读本机 RAG Dashboard 显示脱敏知识/路由/bad-case 聚合。8A 的参数仍由确定性 `mapping_policy` 生成，8C 的外部白名单仍由 Policy 管，RAG 不能授权。当前没有自动 RAG worker、新 Provider 或新的自动 external/hybrid 执行。</span>

## 1. 产品结果：不展示指数，但要有可验证的判断机制

### 1.1 用户看到什么

用户不需要看到一个没有统计依据的“相似度 87 分”。V0 的用户结果优先使用：

- `可以继续处理`：输入质量和身份一致性满足执行条件；
- `存在可解释差异`：指出脸型、眼睛、鼻子、嘴唇等哪些维度偏离母版；
- `处理后可以接受 / 仍建议调整 / 无法判断`：依据复测结果和用户确认；
- `需要重新上传`：说明无法稳定执行的具体原因。

“自然”不作为系统自己定义的审美标准，而作为用户约束，例如“尽量少改”“优先像母版”“不要动肤色”。

### 1.2 “经过校准的真实概率”到底怎么得到

不能直接用腾讯 API 的参数值，也不能让 LLM 看一眼图片后猜一个概率。正确的数据链路是：

```text
母版/目标照片
→ 视觉算法提取归一化五官和脸型特征
→ 同一人物门控 + 质量/姿态/遮挡特征
→ 计算母版与目标的特征差异
→ 外部图片工具执行调整
→ 对修前/修后结果再次提取特征
→ 与人工“可接受/不可接受”标注数据比较
→ 训练并校准一个接受概率模型
```

各部分职责必须分开：

| 组件 | 负责什么 | 不允许负责什么 |
|---|---|---|
| 几何与质量 CV | 人脸检测、关键点或几何特征、姿态、清晰度、遮挡 | 不判断是否同一个人，也不决定用户是否喜欢成片 |
| 主体匹配 Adapter | 比较母版与目标是否可能为同一人物，输出独立状态与证据版本 | 不做 1:N 搜索、身份认证，也不把主体匹配分数当母版一致性分数 |
| 差异与规划算法 | 把特征差异转成可执行参数和风险边界 | 不凭感觉创造供应商不支持的参数 |
| 腾讯或其他图片工具 | 实际修改图片 | 不证明修改后一定“像母版” |
| LLM | 理解自然语言、动态澄清、解释差异、选择下一步工具 | 不计算概率、不直接猜参数、不自行授权执行 |
| 人工标注与校准模型 | 学习“人类是否接受”的概率，并在 holdout 数据上校准 | 不把小样本结果包装成普适真理 |

概率的准确含义应是：

> 在声明清楚的照片条件、用户群体和评审标准下，评审者接受“这张照片已与母版足够一致”的概率。

因此必须先建立有授权的 benchmark：每个样本包含母版、目标照、特征差异、修前/修后结果和人工接受标签；训练集与 holdout 集必须分开。用户点击“接受/继续调整”、主动修改参数、重新上传等交互可以由模型自动整理为候选样本或弱标签，但必须标记 `label_source=interaction_generated`，不能冒充独立人工金标准。

数据集至少要区分：

- `human_gold`：用户或独立评审者明确判断“是否达到自己的母版要求”，用于校准和 holdout；
- `interaction_weak`：由用户操作行为自动生成的候选标签，用于扩大训练样本，不能单独证明模型准确；
- `synthetic`：模型根据已确认规则生成的合成特征/参数案例，用于覆盖边界和 bad case，不作为真实用户接受率证据。

没有足够的 `human_gold`、校准曲线和 holdout 结果时，系统只能输出定性判断，不能显示“真实概率”。V0 不显示任何接受概率。

### 1.3 对当前合同的直接影响

原 `v0.1 VerificationResult` 中的 `before_index`、`after_index`、`index_delta` 是旧设计遗留，不再是产品真相。合同 `v0.4` 保存：

- 修前/修后各特征差异；
- 质量和同一人物门控结果；
- 供应商执行是否成功；
- 用户是否接受；
- 只有在校准模型通过评测后，才允许保存可选的 `acceptance_probability` 及其模型版本。

## 2. 外部图片工具的能力策略

### 2.1 当前腾讯 V0

当前真实验证通过的腾讯 `BeautifyPic` 能力包括：

- `FaceLifting`：瘦脸；
- `EyeEnlarging`：大眼；
- `Whitening`：美白；
- `Smoothing`：磨皮。

参数是否可以自动执行，依据当前 Provider Card 是否声明支持，而不是依据合同里的枚举名称。腾讯现有能力卡支持的参数原则上都可执行；但：

- 美白、磨皮默认值为 0；只有用户明确允许肤色/皮肤质感变化时才可打开；
- 默认执行目标是五官和脸型一致，不主动修改全身肤色、背景或整体色调；
- 前端在用户选择美白/磨皮前必须说明：这两项可能影响皮肤质感、肤色和整张照片的观感，不属于默认的人脸五官对齐；用户确认后仍以单次任务为作用范围，不写入长期母版偏好；
- 未来的眼距、嘴型、唇厚、鼻翼等参数可以保留在产品合同中；当某个外部工具能力卡确认支持后，可接入对应 Adapter；当前腾讯 Adapter 不支持的参数不得假装已执行，应转为“手动建议”或等待后续工具；
- 外部工具只负责执行，不负责定义母版、不负责评估人类接受概率。

## 3. 检查点 8A：局部差异诊断与 EditPlan 规则

8A 的目标是把已通过门控的母版和目标照，转换成一份可解释、可审计、等待确认的修图计划；它不执行图片编辑，也不展示总分或接受概率。

### 3.1 可测量字段与方向

- `face_width_height_ratio`：目标照相对母版更宽时，才可候选映射到腾讯 `FaceLifting`；目标照更窄时不伪造反向参数；
- `eye_area_mean_face_ratio`：仅当视觉模块恰好得到两只眼框时才是 `measured`；目标眼睛面积占脸比例更小时，才可候选映射到 `EyeEnlarging`；
- 眼距、脸在画面中的大小/中心/边缘余量可作为诊断事实，但不能直接当作大眼或瘦脸参数；
- 局部差异百分比是归一化几何测量，不是母版相似度、接受概率或质量评分。

### 3.2 规划与降级

`mapping_policy_v0.1` 是版本化的确定性映射：差异 `≤4%` 视为容差内；`4%—12%` 进入规划区；超过 `12%` 不继续无限叠加。差异百分比不等于腾讯滑杆值，规划器先检查方向、可测量性和用户允许范围，再生成用户可读的 `+n` 与腾讯绝对值。调整模式 `preserve_original / balanced / consistency_first` 的自动强度上限暂定为 `8 / 15 / 22`；每份 `EditPlan` 保存策略版本、输入差异、原因码和降级原因。这些数字是可回归的产品基线，不是经过人工金标准校准的概率模型。

以下任一条件成立时，不生成对应可执行参数：特征不可测量、测量置信度低于规划下限、Provider 无法朝目标方向调整、用户禁止该部位、质量/安全/同人门未通过。系统必须解释具体原因，并降级为重拍、手动建议或暂不处理。

### 3.3 计划合同与确认

规划器读取 `ReferenceProfile`、`PhotoQualityResult`、`IntentFrame` 和审核过的 Provider Card；P0-C 现已在规划器前受限消费 P0-A/P0-B 的带版本 evidence。它只提供 direct/reference/conflict 证据，确定性规划器仍输出逐特征 `FeatureDifference` 与不可变 `EditPlan`；冲突、未知或仅手动建议会阻断计划。计划记录用户层 `+n`、Provider 绝对值、原因码、策略版本、风险和直接证据引用；当前 Provider 的参数全部显式发送，美白/磨皮仍默认关闭。首次执行计划状态为 `proposed`，`requires_confirmation=true`，必须取得一次有界外部处理同意；计划族内的后续子计划沿用有效 scope，不再逐轮要求用户点击。

### 3.4 当前实现边界

<span style="color:#C00000"><strong>RAG 同步边界。</strong> 本节前文“RAG 细则未冻结/尚未实现检索器”是历史描述；P0-A/P0-B 已有真实本地检索器、安全 Trace、本地语义召回和重排，P0-C 已把其输出受限接入 `edit_planner.py`。因此可以称“有治理的 RAG evidence 参与规划”，但不能声称 RAG 自动修图、自动新增 Provider 或自由 Agent。</span>

代码位于 `services/edit_planner.py`，页面通过“生成差异诊断与计划草案”展示归一化值、局部差异、是否可进入计划和脱敏 Trace。它不接受图片字节、不让 LLM 计算视觉事实、不调用腾讯编辑 API；修后 `VerificationResult` 由 8C-1 的 `services/verification.py` 负责，重新规划属于 8C-2。

## 3B. 检查点 8B：用户确认、单次执行与事实回执规则

### 3B.1 确认不是可编辑滑杆，也不是 LLM 说“可以”

用户在确认页只能看清“改什么、为什么、会调用哪个工具、结果如何留存”，不能拖动滑杆修改当前方案。若用户自然语言改口，例如“少瘦一点”“别动眼睛”“这次只要参数”，系统必须生成新的 `IntentFrame` 和新的不可变 `EditPlan`；旧计划/确认失效，用户再确认。LLM 可以理解改口、解释方案，但不能生成确认 token、放行工具或私自改变腾讯参数。

### 3B.2 有界确认与一次执行

确认作用域必须同时绑定当前 `photo_sha256`、Profile 版本、可执行部位、Provider 参数、Safety Policy 和过期时间。V0 确认有效期为 10 分钟；过期、更换照片/母版、质量/安全/同人 Gate 改变、计划被 supersede 或重复执行时，不调用腾讯。`max_provider_rounds=3` 是计划族的配置上限；8B 的首个计划仍只允许一次付费图片编辑调用，8C 后续子计划可在首次确认 scope 未变且 preflight 通过时自动调用一次，不能在同一计划内重试。

### 3B.3 结果、失败与隐私

腾讯结果图只存在当前 Streamlit 浏览器会话的内存，用户可主动下载；页面结束、进程重启或最多 10 分钟后不再可取。结果展示区每 30 秒自检一次过期时间并清除会话内 bytes，避免把 TTL 只写在文档里。SQLite、JSONL、Trace 和项目目录只保存脱敏 `ProviderRun` 事实：参数投影、RequestId、耗时、错误分类、哈希和不透明的 `session_memory` 结果引用，绝不保存结果 Base64、原图、密钥或签名 URL。网络/超时/限频/5xx 也不自动重试，系统只解释真实错误；用户愿意再次尝试时必须重新确认，产生新的计划/回执链。

### 3B.4 当前实现与不可夸写边界

`services/execution.py` 在确认按钮之后做确定性 Gate 校验、局部幂等拦截、一次 Tencent Adapter 调用和 ProviderRun 存储；`app.py` 只把结果字节保留在 `st.session_state`。8C-2 对子计划额外核验父 Run、上一轮 VerificationResult、结果 hash、确认 scope 和 iteration，且把上一轮结果图而非原始上传图写为本轮 input artifact。离线 fixture 测试覆盖成功、过期、换图、超时、取消、重复点击、子计划血缘和硬停止；当前仍没有新的 UI 真实照片三轮回执，不能据此宣称腾讯图片一定更像母版。本地幂等键只能阻止已保存回执后的重复点击，不是断电、并发多实例或供应商侧的 exactly-once 承诺。合同落账还会按真实唯一键预检：同一 ID 的投影发生变化时统一 fail-closed 为 `ValueError`，不覆盖旧证据，也不泄漏 SQLite 唯一键异常。

## 3C. 检查点 8C：修后验证、计划族续跑与反馈（8C-1/8C-2 已实现）

### 3C.1 验证不是固定的“本地复测一次”

8C 以用户最终目标和当前 `EditPlan` 为验证范围。每个标记为 `executable` 且有可靠测量的目标特征，都必须有修前/修后证据；暂不支持、不可测或只有手动建议的特征，必须明确标记 `unverifiable/suggestion_only`，不能被默认为完成。CompareFace 只补充同一人物证据，IMS 只补充内容安全证据，二者不能替代五官/脸型几何复测。

### 3C.2 `VERIFICATION_STRATEGY_SELECT` 的职责分工

Agent 根据修后结构化证据和审核知识检索结果，在允许集合中提出 `local_geometry`、`external_subject_match`、`hybrid` 或 `manual_visual_review` 等策略，并说明原因；状态机负责当前状态和工具白名单；权限策略负责首次外部处理同意、出站范围、成本和轮次；Adapter 负责真实调用。若当前 scope 已覆盖所选工具和用途，Agent 可直接触发调用，不再弹出逐次确认；scope 不覆盖时必须停下请求授权。8C 首个切片用 `deterministic_baseline_v0` 提议本地几何或人工复核，已经写入 `VerificationStrategyProposal`；P0-C 现可为提议层提供 direct/reference/conflict evidence，但不能替换白名单、安装/调用未知工具或扩大权限。<span style="color:#C00000"><strong>这里“scope 内可直接调用”仅指已经实现、已验证 Adapter 的当前确定性计划族续跑；RAG 新提出的 external/hybrid 复测在 P0-C 中只能提议/留证，仍以 `RAG_DECISION_GATE.md` 第 21 节为准，当前不能默认放行。</strong></span>RAG 只提供工具能力/限制/失败规则的证据，不直接计算脸部差异或参数。

### 3C.3 三轮计划族与停止

初次确认授权照片、允许部位、预算和最多三轮的有界计划族。8C-2 已把 `REPLAN` 具体化：只有上一轮 `ProviderRun` 成功、`VerificationResult=REPLAN + improved + cumulative_improvement=true`、目标证据尚不足、结果图 hash 与回执一致、没有质量标记/明确不满意，且确认 scope/Profile/期限/轮次仍有效时，才生成并自动执行新的子 `EditPlan`。子计划有新 `plan_id`、`parent_plan_id`、本轮结果图 hash；下一条 `ProviderRun` 有 `parent_run_id` 和上一结果引用，不能重试原计划。腾讯参数是新输入图上的单次 2—6 保守值，不与上一轮数值相加。用户不需要看参数或逐轮点击，但系统必须写入自动续跑原因、策略/同意引用、preflight、真实回执和失败路由 Trace。达到目标、无改善、变差、无法判断、达到三轮上限、同意/范围失效或用户明确不满意时停止。这里的“Agent 判断达到目标”必须由结构化 `VerificationResult` 和版本化停止策略支撑，不能只凭 LLM 文本。

### 3C.4 反馈事件

结果页提供点赞、点踩和可选文字评论：点赞/点踩是强满意度标签，文字评论是强反馈事件但 V0 不自动把原话当作执行命令；只保存文字 hash。当前实现中，点赞、点踩或文字评论均关闭当前计划族，点踩为硬停止；用户想改变方向需回到 IntentFrame 说明新目标并重新确认。追问、新一轮会话和下载记录为继续使用/行为证据，不等于满意；退出和沉默按上下文记录为未知，不能直接判为不满意。长期留存、WAU、MAU继续进入匿名运营账本，只用于产品迭代，不直接成为训练真值或线上 KPI。

### 3C.5 已实现边界与仍未实现项

当前实现的 `measurement_tolerance=0.01`、`target_gap_tolerance=0.04` 和后续单次 `2—6` 强度是可配置、可替换的工程基线，不是校准概率、真实人脸变化百分比或醒图滑杆换算。若结果不可解码，或必验特征没有可靠修后测量，系统走 `RESHOOT/INPUT_NOT_COMPARABLE`；若特征变差且有上一张已知良好结果仍在会话内存，页面展示回退预览而不重调腾讯；没有回退证据则走 `MANUAL_REVIEW`，不编造回滚成功。`preserved_attributes_verified=false` 明确表示妆面、肤色、背景等保持项尚未自动验证。当前选择器记录 `deterministic_baseline_v0`；P0-C 只能提供策略相关 evidence，不能开放 external/hybrid、LLM 自由策略或真实 UI 三轮照片回执。

## 4. `ReferenceProfile`：母版档案规则

### 3.1 已确认的生命周期

```text
上传候选母版
→ 检查内容安全与可执行质量
→ 提取结构化五官/脸型特征
→ 用户确认这是长期母版
→ 原子性写入新的 active profile
→ 成功后删除旧 active profile 的结构化数据
→ 提示“母版档案已建立”
```

规则：

- 同一个用户只有一个生效母版；
- 用户更换母版时，必须完整上传并重新分析，不能在旧档案上拖动参数修改；
- 新母版分析或写入失败时，旧母版不能被删除；
- 新母版成功提交后，旧版本的特征正文删除，但审计日志保留“版本替换事件”、时间、操作结果和脱敏失败原因，不保留旧照片和旧特征全文；
- 母版照片不是后续可编辑素材，不能提供“继续 P 母版”的隐式入口；若用户想改，必须上传新的确定版本。

### 3.2 当前保存的结构化信息

以下信息用于长期一致性处理；保存的是归一化后的派生数据，不保存原图：

| 信息组 | 字段 | 用途 |
|---|---|---|
| 生命周期 | `profile_id`、匿名 `subject_id`、`version`、`status`、`created_at`、`updated_at` | 识别当前生效档案和版本替换 |
| 提取版本 | `profile_schema_version`、`extractor_version`、`canonicalization_version` | 让后续结果可复现、可回放 |
| 脸型 | 脸宽/脸高比例、额头/中脸/下巴比例、颧区宽度、下颌宽度、下巴长度/形状摘要 | 规划瘦脸或脸型相关调整 |
| 眼睛 | 左右眼宽高、眼裂比例、眼距、眼睛倾斜、相对脸宽位置 | 规划大眼、眼距等调整 |
| 眉眼区域 | 眉眼相对位置、眉形摘要（如工具支持） | 解释眼神和眉眼结构差异 |
| 鼻子 | 鼻宽/鼻长比例、鼻翼宽度、鼻梁相对位置（如工具支持） | 规划鼻部相关调整 |
| 嘴唇 | 嘴宽、嘴角角度、上/下唇厚度比例、嘴部相对脸部位置 | 规划嘴型和唇部相关调整 |
| 状态与置信度 | 每个特征的 `measured/estimated/unavailable`、特征级置信度、整体可执行性摘要 | 避免把不可测量的特征当成事实 |
| 母版质量 | 单脸结果、姿态摘要、遮挡/清晰度/曝光结果、母版是否通过 | 解释为什么母版可以或不能长期使用 |
| 调整约束 | 允许/禁止调整部位、默认模式、用户明确的“不要动”约束 | 保护用户意图和安全边界 |
| 能力映射 | 每个特征对应的 Provider 能力、能力卡版本、`executable/suggestion_only` | 防止把未来参数误当成当前可执行参数 |
| 隐私与同意 | 主体锚点同意记录引用、半年保留期限、到期提醒/删除状态、受限访问状态 | 支持长期门控和后续公网数据治理 |

明确不保存：

- 原图、原图路径、文件名、EXIF、签名 URL；
- 身体和隐私部位；
- 肤色、妆面、背景和全身色调作为母版特征；
- 原始关键点数组、可直接还原的图像数据；
- 未经明确同意长期保存的完整人脸 embedding；即使同意，也只能以加密、可删除、受限访问的派生主体表示保存。

### 3.3 已冻结的冲突解决：长期母版与“不保存原图”

用户希望长期使用母版，同时要求不保存照片信息，并希望之后确认目标照片与母版是否为同一个人。这三点存在技术冲突：删除原图后，系统仍需要某种可比较的主体锚点。

本轮已选择方案 2：保存加密、可删除、受限访问的派生主体表示，不保存原图，保存期为半年。产品必须在建立 Profile 前单独征求用户同意，并清楚说明这是敏感生物特征数据。

半年到期时：

1. 提醒用户重新上传母版或重新确认主体锚点；
2. 用户重新同意后，生成新的主体锚点并重置半年期限；
3. 用户不重新上传/不同意时，删除旧主体锚点，只保留归一化几何特征，系统降级为“几何一致性参考”，并明确告知同一人物确认能力变弱；
4. 到期删除失败必须进入异常队列并告警，不能静默继续长期保存。

已冻结的用户告知与处理规则是：建立长期锚点前，分别取得“处理当前照片”“保存主体锚点 6 个月”“允许公开演示”的同意；三项不能混在一个勾选项里。到期前 30 天和 7 天提醒；用户撤回后立即撤销访问，主存储在 24 小时内删除、备份在 7 天内清理，保留脱敏删除审计事件。当前合同已能记录这些策略和截止时间；真实 AES-GCM 加密、提醒/删除 worker、访问审计页面尚未实现。

### 3.4 母版上传页面规则

点击上传按钮后，先弹窗说明：

- 仅接受 JPG/PNG（是否支持 HEIC 需另行决定）；
- 单人照片；脸部关键区域完整可见，额头、双眼、鼻子、嘴唇、脸颊和下巴不能被大面积裁掉；
- 正面或接近正面，眼睛与镜头大致平齐；
- 使用普通、自然、非夸张表情；
- 避免墨镜、口罩、手遮脸、头发大面积遮挡和强烈阴影；
- 不使用会改变五官的重度美颜、换脸、滤镜或已有夸张修图；
- 光线均匀、脸部清晰、无严重过曝或欠曝；
- 脸部在画面中具有足够大小，图片不能严重压缩或模糊；
- 不上传色情、裸露、血腥、暴力、仇恨、骚扰、未成年人不当内容或未经同意的他人照片。

“脸部多大”“清晰度多少”这类数值阈值不能凭感觉硬编码，后续由视觉工具能力和 benchmark 校准。V0 页面先给出可理解的示例要求，并在失败时返回可解释原因。

### 3.5 母版失败与成功反馈

失败时不建立 Profile，弹窗明确说明：

- 非人像或未检测到脸；
- 多人且无法选择唯一主体；
- 关键五官被遮挡；
- 角度/表情超出当前可执行范围；
- 清晰度、曝光或完整性不足；
- 内容安全检查未通过；
- 无法确认主体锚点或特征提取失败。

成功写入后显示：

> 已成功建立母版档案。后续照片将以这套五官和脸型标准进行比较；肤色、妆面和身体信息不会作为母版标准保存。

## 4. `PhotoQualityResult`：照片可执行性规则

### 4.1 先做“同一人物门控”，但不是身份识别

目标照片首先要判断是否与当前母版属于同一人物。这个判断只服务于当前用户自己的母版对齐，不做：

- 人脸库搜索；
- 识别陌生人姓名或身份；
- 身份认证、风控或公共人物识别；
- 保存未经同意的第三方生物特征。

当前合同已经把置信信息拆成三个独立维度：

- `subject_match_status/evidence`：同一人物的分类状态，以及供应商原始分、分值范围、模型/阈值版本和回执；原始分未校准时不能写进 `subject_match_confidence`；
- `quality_confidence`：照片质量和姿态是否适合分析；
- `editability_confidence`：当前外部工具是否有足够能力完成调整。

同一人物不匹配时直接拒绝；同一人物不确定时不能静默执行。系统应提示用户确认“这是本人且我有权编辑”，并把一次性确认写入有界 `ConfirmationScope` 后再继续；未确认仍要求重新上传/停止，`no_match` 不受该确认影响。

### 4.1.1 第一位真实用户的 8A 阻塞与 UX 反馈（2026-09-01）

<span style="color:#C00000"><strong>真实回执。</strong> 第一位用户的母版 IMS、Profile 建立和目标照 IMS 均成功；CompareFace 原始分为 `56.231842041015625`，按未校准策略是 `uncertain`。原页面没有提供本人/编辑权确认，所以 8A 以 `subject_match_not_confirmed` 与 `quality_route_not_continuable` 停止。RAG 已返回审核过的 Tencent 能力依据，但保持 `execution_authorized=false`；本次不是 RAG 或修图 API 失败。</span>

<span style="color:#C00000"><strong>已冻结修正。</strong> 新增 `subject_match_uncertain_acknowledged` 一次性确认字段：确认后可在当前会话、当前照片和有界计划族内继续，但不把供应商不确定结果升级成 `match`，不更新主体锚点；`no_match` 仍硬拒绝。确认事件和 scope 必须进入脱敏 Trace。新增字段是向后兼容的可选策略扩展，保留合同 `v0.4`，并由迁移标记/测试追踪。</span>

<span style="color:#C00000"><strong>用户体验反馈。</strong> 用户反馈上传等待明显过长、页面直接显示脱敏 JSON、首屏暴露 A/B/C 检查点和过多按钮、自然语言入口被工程选项挤压、整体视觉偏工程文档而非 C 端产品。它们先作为 P0 UX 发现记录，不能在没有 UI 决策的情况下擅自改权限或流程；下一 Gate 应把检查点合并为后台真实进度、将 JSON/Trace 下沉到开发者/管理员第二层，只保留必要的首次同意和结果反馈，同时先埋点各阶段耗时再决定压缩/并行/缓存。</span>

## 2026-09-01｜Cloud ImageModeration 失败的真实根因与账本幂等修正

<span style="color:#C00000"><strong>产品/工程背景。</strong> 第一位用户在 Cloud 页面看到“ImageModeration request failed”。本机使用同一类已获授权照片完成了真实 IMS 请求并得到 `status=succeeded`/`Pass`（RequestId `c95e1359-9ecb-45ac-aa94-3776fbccc0ad`），所以不能把这条页面提示直接判断为“腾讯密钥无效”或绕过内容安全。Cloud 运行日志进一步显示，Streamlit 每次控件交互重跑脚本时，旧实现会重复写入同一个 `photo_quality_result_id`，SQLite 返回 `UNIQUE constraint failed: photo_quality_results.quality_result_id`；这条数据库异常会中断页面并被用户感知为流程失败。</span>

<span style="color:#C00000"><strong>冻结修正。</strong> `LocalTraceStore` 现在对照片质量、EditPlan 和 VerificationResult 同时按完整业务上下文与真实唯一键预检：同一 ID 携带相同脱敏投影时幂等复用并记录 `*_reused`；同一 ID 携带不同内容时抛出可识别的冲突错误，绝不覆盖旧证据或静默合并。验证完成的产品事件只在首次落账时写入，避免 Streamlit 重跑重复计数。该修正只解决运行账本的可重复提交，不放宽 IMS 的 Pass/Review/Block 门控、不增加重试、不改变 RAG advisory-only 或图片权限。</span>

<span style="color:#C00000"><strong>用户可见结果与边界。</strong> Cloud 拉取新版本后，同一页面重跑不会再因重复质量记录触发底层 SQLite 崩溃；如果腾讯本身仍返回错误，页面继续只显示脱敏 `error_code` 与 `RequestId`，失败仍 fail closed。当前仍需要产品负责人刷新 Cloud、重新执行一次内容安全检查；本机 smoke 的成功不能替代 Cloud 的新回执，也不能写成完整用户端到端通过。</span>

### 4.2 质量维度与阈值策略

需要检查：

- 清晰度/压缩程度；
- 脸部在画面中的大小和完整性；
- 正侧脸角度、俯仰角、旋转角；
- 眼睛、鼻子、嘴唇和脸缘遮挡；
- 表情是否导致五官几何明显变形；
- 过曝、欠曝、逆光、色偏；
- 是否存在重度滤镜、换脸或二次修图；
- 是否有多张脸、重复脸或异常检测结果；
- 外部 Provider 对当前照片尺寸、格式和人脸情况的限制。

质量门不预先硬编码一套“美学阈值”。V0 使用版本化的工程启发式参数把清晰度、曝光、脸框尺寸和眼睛可见性转成 quality/editability 路由置信度；它们不是用户接受概率，后续由授权 benchmark 和人工标注校准。每次拒绝必须记录实际原因。当前基线由 Pillow/OpenCV 实现，完整关键点/姿态模型仍是后续替换项。

<span style="color:#C00000"><strong>页面展示边界：</strong>质量/可编辑性置信度只留在合同、路由和评测证据中；V0 页面不展示任何 0—1 数值，不把它称作接受概率。用户只看到“可以进入下一步 / 存在质量警告，确认后继续 / 需要重新上传”以及可执行的失败原因。</span>

### 4.3 置信度路由

当前采用用户确认的 V0 路由，内部置信度为 0—1：

| 内部置信度 | 路由 | 用户看到的解释 |
|---:|---|---|
| `≤0.50` | 拒绝并要求重新上传 | 当前照片无法稳定识别或修改，说明具体原因 |
| `>0.50 且 <0.80` | 警告后继续 | 可以尝试，但角度/表情/遮挡可能导致偏差 |
| `≥0.80` | 直接进入下一步 | 当前照片满足可执行条件 |

这些数值是质量/可执行性路由阈值，不是“母版一致性分数”，也不能直接解释为概率校准结果。后续仍需用 benchmark 校准边界。

### 4.4 多脸处理

- 单脸：直接进入同一人物门控和质量分析；
- 多脸但其他要求达标：让用户明确选择要处理的脸；系统自动隔离背景和其他人脸，只对被选择的脸建立裁剪/编辑上下文；
- 多脸且无法稳定选择、遮挡严重或无法确认主体：拒绝并说明原因；
- 不允许默认替用户选择第一张脸；
- 当前质量门会识别多脸并阻止进入 CompareFace/单脸 Profile；腾讯 API Adapter 尚未实现“选择某一张脸、隔离其他人脸/背景、回贴和复测”的完整编辑链路，这属于后续实现任务，不能在代码完成前宣称支持。

### 4.5 批量模式

```text
上传母版 + 多张目标照
→ 逐张做同一人物/质量/可执行性检查
→ 先列出失败照片和原因
→ 用户确认是否继续处理可执行照片
→ 每张照片独立规划和执行
→ 最后输出成功、警告、失败三类清单
```

- 单张失败不阻塞其他照片；
- 失败照片先进入重新上传或降级处理队列，不静默跳过；
- 每张照片有自己的差异和参数计划，不能把同一组滑杆值复制到整组照片；
- 批量任务的总体成功不应掩盖单张失败。

## 5. 安全、权限和失败边界

除色情、暴力、血腥和恶搞外，还要明确处理：

- 未成年人不当或性化内容；
- 自残、虐待、极端伤害内容；
- 仇恨、骚扰、羞辱和针对他人的恶意换脸；
- 未经本人同意的第三方照片；
- 冒充他人、诈骗、证件或身份材料伪造；
- 将结果用于身份认证、风控、选美或其他高风险判断；
- 试图绕过内容安全、删除水印或隐藏编辑痕迹。

安全检查失败时：

- 不调用外部图片 API；
- 不保存原图到 trace；
- 给出“拒绝/请更换照片”的可理解说明；
- 记录脱敏的风险类别和处理结果，便于 bad case 归因。

## 6. 合同 `v0.4-frozen` 已落实的升级

代码中的 `contracts.py` 已按 [CONTRACTS.md](CONTRACTS.md) 升级为 `v0.4-frozen`：

- `ReferenceProfile`：已加入 Profile 状态、特征级置信度/可用性、能力映射和同一人物锚点元数据；SQLite 已实现新版本成功后旧特征正文 tombstone；
- `PhotoQualityResult`：已加入同一人物门控、质量置信度、可执行性置信度、多脸选择/隔离状态和最严格路由；
- `IntentFrame`：动态澄清，拆分用户意图、状态机和工具名；补充对象范围、保留项、字段来源、逐槽位置信和确认作用域；
- `EditPlan`：已取消部位数量硬上限和 `expected_index_gain`；Provider 绝对参数仍严格为 0—100，不支持项可标为 suggestion-only；
- `ProviderRun`：增加尝试次数、能力卡版本、确认范围、参数投影、重试/超时/成本、错误分类和结果 TTL；
- `VerificationResult`：已移除旧指数，改为逐特征修前/修后实测、总体趋势、策略提议引用、出站/同意事实、计划族引用、显式用户反馈和 STOP/REPLAN/RESHOOT/MANUAL_REVIEW 决策；`target_evidence_sufficient` 只表示结构化差异满足当前策略，不是概率。
- `VerificationStrategyProposal`：记录允许策略集合、选中策略、原因码和是否需要额外出站同意；当前实现是确定性 baseline，不代表已经启用 LLM/RAG 路由。
- 运营账本：新增匿名 `ProductEvent`、匿名用户 ID、强意图/强反馈/弱行为/未知四类证据强度与本地 Dashboard；它不是第七个图片处理合同，也不是训练 Dataset。
- 主体锚点：新增 183 天保留、30/7 天提醒、撤回后 24 小时主存储删除/7 天备份清理的 Policy 快照和 `delete_pending/deleted` 审计字段；实际加密与删除任务仍待实现。

完整 Prompt 已整理在 [AGENT_PROMPTS.md](AGENT_PROMPTS.md)。其中 IntentFrame 的文本解析、检查点 8A 的规划边界、8C-1 的结果解释边界，以及 8C-2 的计划族允许条件已接入。当前仍未接入 LLM/RAG 动态策略、完整多轮澄清和 Bad Case 自动归因；合同字段存在不代表完整 Agent 状态机已经实现。

<span style="color:#C00000"><strong>检查点 6 的实际实现：</strong>新增 `photo_quality.py`（Pillow 安全解码 + OpenCV Haar 人脸/眼睛检测、清晰度/曝光/脸框尺寸指标）、`tencent_subject.py`（IAI `CompareFace` 3.0 当前会话同人 Adapter）、`tencent_safety.py`（IMS `ImageModeration` 安全 Adapter）、`reference_profile.py`（V0 归一化脸框/眼睛几何 Profile 构建）和 `checkpoint6.py`（三者的确定性组合服务）。这些模块只在内存处理原图，SQLite 只保存合同脱敏投影。CompareFace 已完成一次真实同图 smoke，返回原始分 100；该分数不作为 V0 用户分数。IMS 服务开通后的第四次 `ImageModeration` smoke 返回 `Block`（RequestId `21bf408d-929a-46ec-83aa-78f071eff556`），另一张明确授权照片的第五次 smoke 返回 `Pass`（RequestId `211483d5-4ee0-41e8-b5d5-156f81557a69`）。这证明两条样例路由和 Adapter 证据链真实可用；`Block` 样本仍被拦截，`Pass` 样本也不代表完整内容安全覆盖。</strong></span>

<span style="color:#C00000"><strong>检查点 7 的实际实现：</strong>`agent/intent_adapter.py` 只把用户文字和最小化结构化上下文送入 DeepSeek；页面必须先获得“发送本轮脱敏文字”的明确勾选，本机无 Key、未勾选、网络/HTTP/JSON/Schema 失败时均回退到本地 `template_keyword_baseline`。模型不能写入 ID、确认引用、模型版本或工具回执；`action=execute` 只由系统生成待确认作用域，并不执行修图。Trace 只写解析路径、模型/Prompt、耗时、token（可得时）、fallback 原因和脱敏类别，绝不写原话或模型隐藏思维链。9 条离线 Adapter 测试、默认不联网 smoke 和固定无个人信息的真实 smoke 均已通过；当前最新全量回归数字以本轮 8C-2 验证证据为准。</strong></span>

<span style="color:#C00000"><strong>检查点 8A 的实际实现：</strong>新增 `services/edit_planner.py` 与 `scripts/smoke_edit_planner.py`。规划器只读取已通过门控的 Profile/PhotoQualityResult/IntentFrame/Provider Card，不接收图片字节、不调用 LLM 计算视觉数值、不调用 BeautifyPic。它严格使用双眼框计算 `eye_area_mean_face_ratio`，用版本化 `mapping_policy_v0.1` 将可达差异映射为 FaceLifting/EyeEnlarging 的保守绝对值；不可测量、方向不可达、测量置信不足或用户禁改时转为 suggestion-only。计划状态固定为 `proposed` 且需要有界确认，美白/磨皮显式为 0。5 个规划器案例、离线完整 Trace 和页面展示已通过。</strong></span>

<span style="color:#C00000"><strong>检查点 8B 的实际实现：</strong>新增 `services/execution.py` 与 `scripts/smoke_execution_8b.py`。页面只有在用户勾选“将当前照片发送给腾讯云 BeautifyPic”并点击确认后，才生成一份由系统而非 LLM 产生的 `user_structured_input` 执行意图和新的 `confirmed` 计划 revision；执行器逐项检查确认期限、照片 hash、Profile、质量/内容安全/同人 Gate、计划状态和本地幂等键，再且只再调用一次 Adapter。成功/失败均由 Adapter 写入真实 ProviderRun 事实，结果字节仅保存在浏览器会话内存；6 个离线案例和 fixture Trace 已通过。</strong></span>

<span style="color:#C00000"><strong>检查点 8C-1/8C-2 的实际实现：</strong>新增 `services/verification.py`、`services/plan_family.py`、`scripts/smoke_verification_8c.py`、`scripts/smoke_plan_family_8c2.py` 和 `CHECKPOINT_8C_VERIFICATION_GATE.md`。8C 在内存中解码/重新提取腾讯结果图，按当前 EditPlan 的 executable 特征生成逐项 `FeatureComparison`，使用版本化 tolerance 路由到 `CLOSE/REPLAN/STOP/RESHOOT/MANUAL_REVIEW`；当且仅当 `REPLAN + improved + cumulative_improvement` 等证据和原确认范围同时成立，才生成新的不可变子计划。子计划以父 plan/run、上一结果图 hash 和新的单次参数相连；首次外部处理同意的 scope 仍覆盖照片、用途、Provider、预算和轮次时，页面写入自动 preflight 后直接把上一结果图作为下一次腾讯输入，不逐轮要求用户点击；scope 改变则先停止并重新授权。点赞、点踩和文字评论记录强反馈，且关闭当前计划族；文字仅保留 hash。结果图不写数据库；Trace 只写脱敏合同事实和 `result_bytes_persisted=false`。6 条 8C-1 加 6 条 8C-2 服务/落账测试和两条 fixture smoke 已通过。当前仍没有真实 UI 三轮修图回执，不能把 fixture 结果写成线上成功。</strong></span>

## 7. 已冻结边界与以后才需要的决定

| 时间 | 事项 | 当前状态与原因 |
|---|---|---|
| 未来概率模型前 | 人工金标准问法、评审人数和冲突处理 | 暂缓；没有样本与真实端到端结果时，不提前设计看似精确的评审制度 |
| 本地主体锚点开发前 | 许可核验后的特征提取模型、运行硬件/服务器 | 长期锚点已冻结为产品方向；具体模型和设备不能由当前笔记本假设替代 |
| 内容安全多样性验证前 | 继续用更多明确授权样本覆盖 Pass/Review/Block 和误判边界 | 当前已各有一条真实 `Pass` 与 `Block` 回执；单样本不能代表完整安全覆盖，`Review/Block` 仍保守拦截 |
| 受邀部署前 | 平台、受邀名单/密码、区域、费用上限、管理员访问控制和删除实现 | 本机开发继续；不默认采购硬件或开放公网 |
| Dataset 化前 | 事件抽取、去标识化、人工标注、holdout 与训练用途 | 当前数据库仅是产品运行账本，不能直接当训练数据 |
| P0-C 受限回接后 | Gold Set v2 人审/Judge/阈值、自动 worker、新 Provider 与 external/hybrid Adapter | evidence 消费规则与本机只读 RAG Dashboard 已完成；不得自动接入图片执行，见 [RAG_DECISION_GATE.md](RAG_DECISION_GATE.md) 与 [RAG_P0C_ADVISORY_INTEGRATION_GATE.md](RAG_P0C_ADVISORY_INTEGRATION_GATE.md) |

这一轮已没有待产品负责人补答的 V0 基础规则；上表列出的都是未来模块的开工 Gate。实施前仍沿用“先讨论 → 补漏洞/权衡 → 用户冻结 → 再写代码和测试”的协作方式。

## 8. 本项目的模块协作方式

### 8.1 规则不再“想到即落库”

后续四个合同（`IntentFrame`、`EditPlan`、`ProviderRun`、`VerificationResult`）以及任何新增规则，都必须经过四个阶段：

1. 用户先写出自己的初步规则；
2. 我在对话框中补充遗漏维度、风险和可选方案；
3. 用户修改、取舍并回复最终版本；
4. 用户明确说“冻结”后，才把最终规则写入 Markdown、合同代码和测试。

在第 3 步之前，我的补充只能标为“候选建议”，不能被当成产品决定，也不能悄悄进入代码。Markdown 只记录已经确认的规则和仍待讨论的问题；聊天中的候选建议不自动升级为合同。

每个模块严格按以下顺序推进：

```text
先讲清楚模块
→ 列输入/输出/规则
→ 标出由用户决定的地方
→ 用户确认
→ 再写代码
→ 用 3—5 个实际案例运行
→ 展示一条完整 Trace
→ 用户验收：通过 / 修改规则 / 暂不实现
```

每个模块必须交付：

1. 一页中文说明；
2. 输入、输出和规则表；
3. 用户决策清单；
4. 3—5 个实际测试案例；
5. 一条能对应到代码和日志的完整 Trace。

## 9. 四个合同的产品规则归一化

### 9.1 `IntentFrame`

用户直接用自然语言表达目标，Agent 先形成结构化 IntentFrame，再只追问一个真正影响结果的问题。“只看诊断、给参数、直接执行”保留为 action/output 的候选，不成为固定问卷。意图至少要覆盖目标、单张/批量、对象范围、母版来源、输出方式、允许/禁止部位、必须保留的妆面/肤色/表情/背景、调整模式、速度/成本/少改优先级、批量失败策略、确认作用域和用户是否请求保存长期偏好；每个字段记录来源和置信度。

<span style="color:#C00000"><strong>【耦合纠错】review_reference、lock_profile、analyze_consistency、plan_edit、execute_beautify 等不是同一层“用户 intent”：前两者更接近工作流状态，后三者是工具。IntentFrame 只描述用户要什么，状态机决定现在允许做什么，ReAct 层只能在白名单中建议下一工具。</strong></span>

执行、删除、母版更新和长期偏好保存都需要明确确认。高置信与低成本只能减少澄清，不能免除外部编辑确认；“以后默认直接执行”只能预选执行路径，仍不能取消新任务的有界确认。检查点 8B 中，用户真实点击确认后才由系统生成 `parser_mode=user_structured_input` 的执行意图；LLM 不能制造这一权限。用户明确取消时立即取消；改口后，新 IntentFrame 覆盖旧意图，旧未执行计划与确认失效并写入 Trace。

三到五秒首个反馈属于体验目标：UI 可以立即显示真实的“正在解析/检查/规划/调用/复测”状态，不能把动画或流式文字当作工具已经成功，也不能展示隐藏思维链。

### 9.2 `EditPlan`

每张可执行照片生成一张独立、不可变的计划；批量可以并行规划，但不能共用同一组滑杆值。计划分为 Provider 可执行变化和 suggestion-only 手动建议。用户层保存相对变化，腾讯层保存全部显式绝对值；参数由确定性规划器和能力卡计算，LLM 只理解意图、选择工具和解释。

<span style="color:#C00000"><strong>【耦合纠错】腾讯官方参数只能是 0—100，后台不能发送超界值；单次/累计安全上限也不能由 LLM 决定。用户提出更大变化时，规划器应按版本化安全策略截断或拒绝并解释。</strong></span>

取消固定“三个部位”上限；真实可执行数量仍受 Provider Card 限制。检查点 8B 的确认页不允许直接修改滑杆；实质改口必须生成新 plan revision 并重新确认，旧计划不修改。8C-2 的后续轮不是修改旧计划：它创建新的不可变子 `EditPlan`（新 `plan_id`、`parent_plan_id`、当前结果图 hash、iteration），并只可沿用首次确认已允许的部位、轮次和期限。EditPlan 只保存修前差异、具体参数、预计改善方向、风险和确认要求；修后实测必须进入 VerificationResult。

### 9.3 `ProviderRun`

一次真实 API 尝试产生一条不可变回执，包括关联的计划/照片/attempt、供应商与能力卡版本、脱敏参数投影、确认作用域、幂等键和请求 hash、状态、RequestId、结果引用、各阶段耗时、成本、错误分类、是否可重试以及结果 TTL/删除状态。Base64、密钥、签名 URL、原图和未经脱敏文本不得保存。

<span style="color:#C00000"><strong>【耦合纠错】ProviderRun 不是 LLM 合同，必须由 Adapter 和计时/审计代码生成；附件中的 Prompt 实际是读取 ProviderRun 后的 Bad Case 归因 Prompt。API 成功只证明工具执行，不证明修图有效。</strong></span>

当前 8B **不自动重试任何错误**：超时、限频、网络和 5xx 也只产生一次失败 Run，用户重新确认后才可能发出新的请求。参数、权限、内容安全和图片格式错误同样不得重试。8C-2 若继续，必须产生新的 `ProviderRun`，通过 `parent_run_id`、输入结果图引用/hash 与父回执相连；它是同一已确认计划族内的一次受限自动调用，不是重试。一次真实尝试一条 Run，不能覆盖或伪造第一次证据；以后若要启用恢复策略，必须作为新的版本化产品/成本决策，而不是默默改变行为。

### 9.4 `VerificationResult`

验证器重新提取修前/修后的逐特征差异，记录总体趋势、质量/禁改部位情况、轮次、显式用户反馈和真实下一步。8C 新增 `VERIFICATION_STRATEGY_SELECT`，由 Agent 在审核/授权策略集合内提议复测方式，状态机和权限策略校验后才执行；报告 LLM 只能解释，不能改数值或越权调用。

<span style="color:#C00000"><strong>【耦合纠错】V0 没有校准后的接受概率，因此不能把“真实概率达标”作为当前停止条件。当前只能依据逐特征实测趋势、质量/安全门、轮次策略和用户显式接受做定性判断；沉默、关闭页面或打开新窗口只能作为弱行为信号。</strong></span>

质量不足走重新上传/重拍，不继续加参数；8B 的 API 失败先展示 Provider 的错误分类并停止，不能在同一计划中自动再扣费。8C 可以在已确认的三轮计划族内生成并自动执行后继子计划，但每个计划仍只有一次 ProviderRun；只有可验证的累积改善、上一结果图 hash 一致、范围/期限未变时才允许继续。用户不需要逐轮理解参数或点击；系统必须在每次调用前完成 scope/预算/幂等/安全 preflight，并在调用前后保存自动触发 Trace。用户点踩或提交文字反馈时当前计划族硬停止；文字反馈不直接变成参数，先由下一次 IntentFrame 澄清具体差异。

## 10. 本轮产品决定已冻结

以下决定已由用户在 2026-08-27 至 2026-08-28 明确确认，并进入合同、Policy 或实现边界：

1. <span style="color:#C00000"><strong>确认作用域：</strong>一次确认授权当前照片/批次、明确允许部位和最多三轮的有界计划族；扩大部位、启用美白/磨皮、换母版/照片或超预算时重新确认。</span>
2. <span style="color:#C00000"><strong>轮次与停止：</strong>“三轮”作为 V0 Safety Policy 的可配置总上限，而非合同类型的永久硬编码；连续两轮无改善提前停止。</span>
3. <span style="color:#C00000"><strong>多脸 V0：</strong>产品自行执行选择、隔离、裁剪、回贴和复测；任一步无法稳定完成时说明原因并要求用户先裁剪。该工程链路完成前，当前 Demo 拒绝多脸或要求先裁剪。</span>
4. <span style="color:#C00000"><strong>人工复核：</strong>Beta 只标记为“待项目开发者复核”，查看原图需要单独授权，不宣称已有客服或运营团队。</span>
5. <span style="color:#C00000"><strong>三类判断信号：</strong>0.50/0.80 只用于 quality/editability，并采用最严格路由；subject match 单独输出 match/uncertain/no_match，供应商原始分不是概率，阈值后续用授权样本校准。</span>
6. <span style="color:#C00000"><strong>反馈与数据：</strong>首次 Prompt、再次会话和追问记录为强意图/继续使用信号；点赞、点踩和明确评论是强反馈；退出/沉默默认未知，仅按具体上下文记录路径中止。匿名事件进入运营账本与本地 Dashboard，不直接进入训练 Dataset。</span>
7. <span style="color:#C00000"><strong>隐私生命周期：</strong>主体锚点单独同意，183 天有效，30/7 天提醒；撤回后立即停用，主存储 24 小时内删除、备份 7 天内清理；公开演示授权独立于照片处理与锚点保存。</span>
8. <span style="color:#C00000"><strong>LLM 与数据边界：</strong>DeepSeek V4 Flash 是文本理解主模型，检查点 7 已实现 Schema 校验与模板降级，并通过一次固定文本的真实 live receipt；照片、Base64、人脸向量和密钥不进入 LLM，不自动把同一段文本发送给第二个云 Provider。LLM 文本远程调用仍需本轮勾选和本机密钥；图片/验证 Provider 的首次外部处理同意可在有效计划族内复用，scope 变化时重新授权。</span>
9. <span style="color:#C00000"><strong>多脸与不满意：</strong>YuNet → 用户选脸 → MediaPipe/遮罩裁剪 → 编辑 → 回贴 → 复测；失败要求先裁剪。用户明确不满意立即停止下一次工具调用，先澄清再重新确认。</span>
10. <span style="color:#C00000"><strong>8B 计划编辑：</strong>确认页不提供滑杆直接改当前计划；自然语言改口必须产生新 IntentFrame/新 EditPlan 并重新确认。</span>
11. <span style="color:#C00000"><strong>8B 确认期限：</strong>确认绑定当前照片 hash、Profile/计划/允许部位与参数，10 分钟后失效；变更、过期、Gate 失败或重复点击均不调用腾讯。</span>
12. <span style="color:#C00000"><strong>8B 结果数据：</strong>结果图只在当前浏览器会话内预览，用户可下载；不写 SQLite、JSONL、Trace 或项目目录，最多保留 10 分钟内存窗口。</span>
13. <span style="color:#C00000"><strong>8B 付费失败：</strong>每个确认计划只允许一次外部尝试，不自动重试；同一计划失败后不能静默重试，任何新的尝试必须生成新的子/修订计划并通过相应的 scope Gate。若只是 8C 在首次有效 scope 内的证据驱动后继子计划，则可受限自动调用；scope 变化仍由用户重新授权。</span>
14. <span style="color:#C00000"><strong>8C 策略选择：</strong>加入 `VERIFICATION_STRATEGY_SELECT`；Agent 只在已审核/已授权策略集合内提议复测方式，状态机、权限策略和 Adapter 才能放行。RAG 可在需要工具知识时提供证据，但不能自由搜索或调用未知工具。</span>
15. <span style="color:#C00000"><strong>8C 目标与轮次：</strong>验证范围按用户最终目标和当前 EditPlan 的可执行特征确定；最多三轮是版本化计划族上限。只有 `REPLAN + improved + cumulative_improvement`、当前结果图 hash 与父回执一致且原确认仍有效时，才生成并自动执行新的子 EditPlan；子计划的腾讯参数是新输入图上的 2—6 保守单次强度，不能把上轮参数相加。每轮都有独立 ProviderRun，调用前必须通过确定性 preflight 并留下自动触发 Trace；无改善、变差、无法判断、达标或用户不满意时停止。</span>
16. <span style="color:#C00000"><strong>8C 反馈：</strong>点赞/点踩和明确文字为强反馈；点踩或文字评论关闭当前计划族，文字只记录 hash，不能直接变成修图指令。追问、新会话、下载为继续使用/行为证据；退出/沉默默认未知并结合上下文记录；长期 WAU/MAU 只作为匿名运营事件，不直接当满意度或训练真值。</span>
17. <span style="color:#C00000"><strong>RAG P0-A / P0-B / P0-C + Dashboard：</strong>已实现本地 SQLite/metadata/FTS5 与本地 dense/RRF/rerank 的审核工具知识检索、来源依据卡、脱敏 Trace、8A/8C 的受限 evidence 回接，以及只读本机 RAG 治理 Dashboard；它们只回答/展示“现有工具有什么能力、限制和路由事实”，不读照片、不调 LLM/API、不产生参数或执行。Gold Set v2 评测器与答案隔离材料已实现；下一步是逐题审核/真实 predictions，再讨论自动 worker、新 Provider 正式准入和 external/hybrid Adapter。</span>
18. <span style="color:#C00000"><strong>RAG Gold Set v2 评测：</strong>固定 34 道开发题、18 道挑战题、20 道隐藏题，同时测试工具能力、权限、隐私、生命周期、冲突和提示注入。产品负责人是唯一人工事实审核者，暂不加入第二位人工评审；盲审 LLM Judge 可以看到机器分数/指标摘要，但不能看到 Gold 答案、答案键、开发标签或实现版本。安全类必须 100% 正确拦截、0 次错误工具放行；检索/路由门槛为 Recall@5≥90%、Precision@3≥80%、MRR≥80%、nDCG@5≥85%、路由/证据关系正确率≥90%；未来解释 Faithfulness≥95%、人审—Judge 一致率≥80%、Hidden—Dev 差距≤10 个百分点。隐藏集运行器只接收无答案题目；答案键已移至产品负责人独立保管位置，工作区仅保留不含答案的保管回执。</span>
19. <span style="color:#C00000"><strong>新 Provider 路线：</strong>选择参数级人像美化 SDK/API，并行验证火山美颜 API V2.0 静态/批量路线与腾讯特效 SDK 细粒度路线。两者目前只能建立 Candidate Card、Adapter shell、权限/预算 preflight、离线测试和 live smoke 入口；必须完成官方能力/License/隐私/地区/成本证据、真实 receipt、Gold 回归和产品负责人冻结后，才可进入 `reviewed_active`。RAG 只能提议，不能授权或直接上传照片。</span>
20. <span style="color:#C00000"><strong>视觉／Agent 交互：</strong>冻结“对齐首页／Agent 对话子页面 + 母版档案 + 结果记录”的三空间信息分组，桌面壳固定为“全局导航 + 项目/母版上下文 + 中央对齐工作区 + 右侧 Agent 对话”轻量四区。新用户只看“建立我的母版”或“我已有母版，开始本次对齐”；母版是轻量长期锚点，当前照片与本次意图居中。Agent 只在澄清、真实进度、边界和结果时发声；参数、依据、Provider 回执与脱敏执行记录是第二层，隐藏思维链永不展示。结果页提供前后对比、下载、点赞／点踩与继续说明。动效只能表示真实状态，不能伪造调用完成。视觉基线继续借鉴参考图的层次语法，但不使用摄影或原站资产；正式界面配色为 Tweakcn Party Rock 原始 Light/Dark token，字体为苹方（PingFang SC），紫色与米白共同为最大面积、紫色略强，黑色为结构色、其他颜色仅少量点缀。活跃视觉只制作 E01 入口与 E02 Agent 对话两张主关键帧；页面遵守奥卡姆剃刀：每一层只保留当前任务必要的实体；导航只保留对齐／母版／记录，首屏突出一个上传动作和一个自然语言 Agent 输入框，按钮与文案保持短句。当前冻结设计不改变任何同意、权限、外部调用、保存或审计规则，也不代表线上 UI 已升级。</span>

## 2026-08-30｜Failure Pattern 与 RAG 自校正边界（已实现）

**产品背景。**公开集高分与隐藏集低聚合分数同时出现，说明仅维护一套能通过公开题的规则会掩盖泛化和指标口径问题。产品需要能够回答“为什么错、下一步改什么、改后是否回退”，但不能让系统为了通过评测而读取隐藏答案或扩大工具权限。

**冻结规则。**新增 failure-pattern 分析和本机优化 Dashboard；分析器只消费公开逐题材料与隐藏聚合材料，所有隐藏诊断只保留计数/指标/证据级别。自校正采用 proposal-only：一次只提出一个可解释候选，先跑公开安全回归，再由产品负责人决定升级或回滚；不得自动修改权限、Provider 白名单、参数安全上限、停止策略或 `execution_authorized=false`。

**当前候选。**`rag-correction-candidate-v0.1` 只做经审核的领域/中英同义词归一化，运行在临时本地索引中。候选公开回归没有指标回退（`regression_gate=PASS`），但 project Gate 仍是 `FAIL`，所以候选尚未激活；指标差值和 Trace 聚合落在 `reports/rag_failure_patterns_v1.json/.html`。

**可观测与回滚。**`pages/4_RAG治理看板.py` 的报告集合展示公开评测、隐藏聚合和失败分析 HTML；`pages/5_RAG优化看板.py` 展示分层指标、错误类型、SOP 和候选差值。两页只读、使用显式 allow-list，不读取答案键、照片、向量、原始用户文本或密钥。删除候选文件即可回到现役 deterministic baseline；没有产品负责人批准，系统不会自动发布候选。

## 11. 附件中【具体任务】完成情况

| 任务 | 完成状态 | 落点 |
|---|---|---|
| 补全 IntentFrame 所需信息 | <span style="color:#C00000"><strong>已完成</strong></span> | 本文 9.1；[CONTRACTS.md](CONTRACTS.md) 6.2 |
| IntentFrame 完整 System Prompt | <span style="color:#C00000"><strong>已完成</strong></span> | [AGENT_PROMPTS.md](AGENT_PROMPTS.md) 1 |
| EditPlan 完整 System Prompt | <span style="color:#C00000"><strong>已完成并纠正为“受约束编排 Prompt”</strong></span> | [AGENT_PROMPTS.md](AGENT_PROMPTS.md) 2 |
| 补全 ProviderRun 回执信息 | <span style="color:#C00000"><strong>已完成</strong></span> | 本文 9.3；[CONTRACTS.md](CONTRACTS.md) 8.1 |
| ProviderRun 完整 System Prompt | <span style="color:#C00000"><strong>已完成并定位为下游 Bad Case Prompt</strong></span> | [AGENT_PROMPTS.md](AGENT_PROMPTS.md) 3 |
| VerificationResult 完整 System Prompt | <span style="color:#C00000"><strong>已完成</strong></span> | [AGENT_PROMPTS.md](AGENT_PROMPTS.md) 4 |

合同、Policy、六类业务合同表、匿名运营事件账本、8B 单次执行 Gate、8C-1 修后观察/VerificationResult、8C-2 有界计划族/反馈硬停止，以及独立 RAG P0-A/P0-B 检索、P0-C 受限回接与只读 RAG Dashboard 已落实；DeepSeek 的文本 IntentFrame Adapter 已完成一次真实 Schema receipt；长期锚点加密/删除、多脸链路、external/hybrid 复测、自动 RAG worker/新 Provider、完整 Agent loop 和线上评测仍未完成。

## 2026-08-30 实施状态同步

Gold Set v2 离线评测器、public/annotations/holdout 三包隔离、盲审输入合同和答案不泄漏 HTML/Markdown/JSON 报告已落地；public deterministic baseline 已生成并评分，固定分母 Precision@3=47.44%，project Gate=`FAIL`；answerless holdout 20 题也已运行，产品负责人在工作区外私有目录完成一次仅聚合比对，Route=25.00%、Recall@5=38.24%、MRR=52.94%、nDCG@5=41.56%，project Gate=`FAIL`。私有 Markdown 的自然语言 `must_not` 尚未规范成 canonical event ID，因此 hard-safety 明确为 `MANUAL_REVIEW_REQUIRED`，不伪报通过；隐藏逐题答案不回流规则、Prompt 或调参。

火山美颜 API V2.0 与腾讯特效移动/PC 细项仍是 candidate Card + fail-closed Adapter shell、权限/预算检查、离线测试和 smoke；腾讯特效 Web 已另建浏览器 Adapter、page 6 和 `ProviderRun` 联合合同，但 Card 仍为 candidate，尚未取得新的 Browser Receipt。所有新 Provider 都必须完成供应商书面能力、License/隐私/区域、价格/延迟、真实 receipt、Gold 回归和产品负责人冻结后才可进入 `reviewed_active`；本轮产品规则未改变“RAG 只能提议、不能授权”的边界。failure-pattern analyzer 与优化看板只做脱敏诊断和 proposal-only 候选，不改变上述边界。该处的历史快照为 `pytest 172 passed, 4 warnings`；当前全量同步校验为 `178 passed, 4 warnings`，Ruff、format、compileall、`git diff --check` 均通过。

## 2026-08-30 评测治理冻结（Precision C / Holdout A / Safety ID C）

<span style="color:#C00000"><strong>Precision C。</strong> 评测同时输出固定分母 `precision_at_k`、覆盖式 `precision_at_k_effective` 和返回式 `precision_at_k_returned`，并按 Gold 证据条数分层。固定分母保留历史可比性并继续作为当前项目 Gate；其余两项只用于解释稀疏 Gold 和返回噪声，不自动放宽门槛。</span>

<span style="color:#C00000"><strong>Holdout A。</strong> v2 隐藏集及私有 aggregate 只用于历史泛化诊断；新建 v3 answerless runtime 模板和工作区外答案保管流程。v3 题目/答案必须独立生成、正式验收最多一次，不允许用 v2 逐题答案补规则。</span>

<span style="color:#C00000"><strong>Safety ID C。</strong> 已知 hard-safety 标签通过版本化确定性字典映射到 `RAG_EVT_*`；未知标签不模糊猜测，直接要求人工复核。字典只影响评测可观测性，不授权 RAG、LLM 或 Provider 执行。</span>

实现落点：`core/rag_safety_events.py`、`data/evaluation/rag_safety_event_catalog_v0.json`、`data/evaluation/rag_gold_v3_holdout_runtime.template.json`、`RAG_GOLD_SET_V3_HOLDOUT_CUSTODY.md`、Gold evaluator/private aggregate/failure analyzer/page 5 看板及对应测试。当前 public 固定 Precision@3=47.44%、覆盖式/返回式=100%、project Gate 仍 `FAIL`；新 v3 仍为空模板，不能写成 RAG 通过。

## 19. 2026-08-30 当前部署与 Provider 规则收口

<span style="color:#C00000"><strong>部署规则。</strong> 为获得短期可分享演示 URL，代码包已推送到私有 GitHub 仓库 [`z1834691-coder/portrait-consistency-agent`](https://github.com/z1834691-coder/portrait-consistency-agent)，并已由产品负责人创建 Streamlit Community Cloud Private 应用：`https://portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`。只读探针返回 Streamlit 登录跳转，说明应用存在且仍为 Private；这不等于公网开放、真实照片授权或持久化服务。腾讯 Web License 表单现场验证要求填纯主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，不能带协议、路径、通配符或尾部斜杠；当前仅预填、未提交测试 License。仓库不包含 `.env`、照片/结果图、本机 SQLite/JSONL、模型缓存、隐藏答案和报告。</span>

<span style="color:#C00000"><strong>火山候选规则。</strong> 火山美颜 API V2 已核对到官方“创点/购买支持后付费 API 套餐”的准入说明；公开资料未给出个人免费额度或按次 API 价格，公开 SDK 年包从 6 万元起且不是 V2 API 的报价。因此 V0 暂不购买、不配置 Key、不发送照片；保留 Card/Adapter shell 供未来候选评估。只有取得书面试用/价格、License、隐私/地区、真实 schema、live receipt 和 Gold 回归后，才可另行申请进入 `reviewed_active`。腾讯 BeautifyPic 是当前唯一继续使用的已验证图片执行 Provider。</span>

<span style="color:#C00000"><strong>验证结果。</strong> 本轮重新跑通 `pytest 146 passed, 4 warnings`、Ruff、format、compileall、`git diff --check` 和 Streamlit HTTP 200 启动探针；这些证据证明部署包可构建和本地入口可启动，不等于 Cloud App 已部署、真实照片已获跨境授权或生产服务已具备。</span>

## 2026-08-30 当前同步：安全事件目录、v3 Holdout 与测试 License

<span style="color:#C00000"><strong>安全事件目录。</strong> 产品负责人已审核通过公开 `rag-safety-events-v0.1` 目录。已知 legacy label 与 `RAG_EVT_*` canonical ID 继续确定性映射；未知或争议事件仍必须进入 `MANUAL_REVIEW_REQUIRED`。这次审核只确认词表，不改变 RAG 只能提议、Provider fail-closed 或图片权限。</span>

<span style="color:#C00000"><strong>Holdout。</strong> 按 Holdout A 在项目工作区外生成了 36 道 v3 题目、分离答案草案和逐题审核表，状态为 `OWNER_REVIEW_DRAFT`。题目和答案不被应用/evaluator 读取；产品负责人审核完成后，正式 runtime 只允许导入 `case_id + query`，正式评分最多一次，不能用 v2/v3 hidden 逐题答案补规则。</span>

<span style="color:#C00000"><strong>Tencent Web License。</strong> 测试 License 已通过控制台提交并显示“正常”，绑定精确主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，有效期显示为 2026-08-30 至 2026-09-13。密钥和 Token 只由产品负责人在密码管理器/部署 Secrets 中保管，不得写入仓库、Trace、报告或聊天。</span>

## 20. 2026-08-30｜RAG 知识生命周期审计规则

**背景与问题。**P0-A/P0-B 已能检索已审核 Provider Card，但“实时”不能被理解成自动抓网页或自动修改知识库；如果资料过期、撤回、冲突或 dense 索引落后，继续检索会把旧事实带入 8A/8C。为了兼顾可用性、成本和可追溯性，先把生命周期治理做成一个可显式触发的审计模块。

**调研与判断。**知识库的权威来源是审核过的结构化 Card/Policy，dense/FTS 索引都是可重建派生物；因此需要同时检查来源元数据和索引计数，而不是让 LLM 猜资料是否仍有效。审计只读元数据、原子规则数和 manifest，不读取照片、向量、原文正文、用户文本或密钥。

**冻结决策。**生命周期审计只生成 `RagLifecycleAudit` 与脱敏 Trace：过期/撤回/冲突条目阻断检索，未生效/候选条目保持 hold，到期复审/缺 URI/零规则进入人工复核，健康条目保持 active；`auto_status_change_allowed=false`、`auto_publish_allowed=false`。知识更新必须由产品负责人人工审核后改 Card/Policy、重建派生索引并重跑回归。RAG 仍只能提议，不能授权 Provider 或图片出站。

**效果与边界。**当前 3 张审核 Tencent Card、10 条有效原子规则的审计结果为 `complete`、无生命周期问题、dense manifest=`in_sync`；审计记录可落 SQLite 并在治理看板查看。该结果证明知识账本与索引在本次快照一致，不证明 RAG 质量 Gate 通过，也不构成自动实时同步、生产合规或新 Provider 准入。

## 2026-09-01 当前评测与真实用户边界

产品负责人已完成 v3 Holdout 36 题的逐题审核，并按 Holdout A 完成一次工作区外私有聚合盲测。运行器只接收无答案 `case_id + query`；答案键不回流仓库、应用、Prompt 或检索规则。盲测未调用 LLM、网络、照片或 Provider，结果为 Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、evidence relation=23.61%，hard-safety 0/36 违规（PASS），project quality Gate=`FAIL`。

这次失败是质量信号，不是执行授权信号：RAG 仍然只能提议，不能新增参数、Provider、权限或图片出站；后续只能在 public/dev/challenge 上修正并回归，需要再次验收时必须另建独立 Holdout。Streamlit Private 页面已打开，但真实照片端到端、UI 多轮图片回执和用户反馈必须由产品负责人亲自完成；Codex 不代上传、不代点击外部图片调用。

## 2026-09-01｜失败模式驱动的 RAG 自动优化规则

<span style="color:#C00000"><strong>背景与判断。</strong> v3 一次性盲测暴露 relation、evidence set 和 route 三类聚合问题。产品负责人要求把失败模式真正转成逐题分析、候选修正和可观察回归，但不能读取 v3 逐题答案。复核 public v2 后确认：52 题的 route/evidence/relation/排序指标均为 100%，唯一公开结构性异常是 51 题 Gold 少于 3 条导致固定 Precision@3=`47.44%`；因此不能用 public 结果伪造算法增益或用 v3 聚合数字写 case 特例。</span>

<span style="color:#C00000"><strong>冻结规则。</strong> 自校正 loop 只读取 public dev/challenge 和公开 annotations；v3 只允许 aggregate context；同一 v3 不得再次正式评分。每一代只改一个可解释变量，先跑安全硬门和质量 Rubric，再由产品负责人决定推广或回滚。Composite（Route 20%、Evidence exact 15%、Evidence relation 20%、Recall@5 15%、MRR 10%、nDCG@5 10%、固定 Precision@3 10%）只用于 Dashboard 趋势，不替代固定 project Gate。连续两代增益 `<0.01` 且未跨过质量门，停止剩余候选；候选不能自动改权限、Provider 白名单、参数上限或 `execution_authorized=false`。</span>

<span style="color:#C00000"><strong>实际状态。</strong> `rag_optimization_loop-v0.1` 已运行 V0 baseline、V1 同义词归一化和 V2 relation canonical 化；Composite 均为 `0.947436`、增益均为 `0.0`，anti-overfit=`PASS`，V3/V4 按停止规则跳过。报告只保留 public case ID、split、标签、题干 SHA-256 和错误代码；page 5 增加逐题表、代际曲线、v3 aggregate pattern、停止原因和 HTML 下载。该规则形成可回放的优化机制，但不把当前 RAG 写成已通过。</span>

## 2026-09-01｜腾讯特效 Web Provider：实际准入实现边界

<span style="color:#C00000"><strong>背景与判断。</strong>现有 Tencent BeautifyPic 是后端 REST 执行路径。为了验证另一个更接近腾讯特效产品能力的静态图片路线，本轮新增 Web SDK Adapter，但官方接口运行在浏览器 JavaScript/WebGL 中，不能把移动/PC 细项宣传直接当成 Python API。产品因此把它做成独立的 Web Card、浏览器桥接、Browser Receipt 和人工准入清单，先验证真实运行面，再决定是否进入主流程。</span>

<span style="color:#C00000"><strong>规则已落地。</strong>产品参数 0—100 由确定性 Adapter 映射为 Web 0—1；美白/磨皮默认 0；浏览器只接收 License Key、APP ID 与短时签名，License Token 只在服务端用于签名；输入/输出图片只在浏览器当前会话，Python/SQLite/Trace 只保存 hash、尺寸、耗时、状态和安全错误码。RAG 和 LLM 不能因为命中该 Card 自动授权。</span>

<span style="color:#C00000"><strong>准入规则。</strong>`data/provider_cards/tencent_effect_web.json` 当前为 `candidate`。`evaluate_effect_web_admission()` 会逐项检查有效 License、精确域名、Provider 权限、出站/区域批准、成本、Adapter、真实成功 Browser Receipt 和产品负责人批准；所有证据齐全时只返回 `promote_after_review`，不自动修改 Card。Web generic 的 `lift/shave/eye/chin` 不等于唇厚、鼻翼、眉毛、眼距等移动/PC 细项，单图成功也不代表批量能力。</span>

<span style="color:#C00000"><strong>当前状态。</strong>已新增 page 6 的官方示例图入口、离线 smoke、`ProviderRun` 的 `tencent_effect_web/WebARImage` 联合合同与 8 条 Adapter 测试；本地尚无新的浏览器成功 receipt，因此不得写成 Web Provider 已正式接入或主流程可用。真实 smoke 需要在绑定域名和 Cloud Secrets 配齐后由浏览器运行，完成后再把非敏感回执补入 Card 和准入记录。</span>

## 2026-09-01｜失败驱动优化：为什么上一轮没有增益，以及本轮如何修正

<span style="color:#C00000"><strong>背景与问题。</strong>上一轮连续三代的 Composite 都是 `0.947436`，表面上像“优化无效”。复核代码、输入合同和 Trace 后发现，V1/V2 只对已经生成的 `Prediction` 做同义词/关系后处理；而 public baseline 的 route、evidence 和 relation 本来就已是规范值，实际 `changed_prediction_count=0`。真正未覆盖的是用户自然语言进入 P0-B 前的查询编译层。另一个问题是 public 52 题过于容易，51 题只有 Gold 稀疏分母提示，不能作为 v3 泛化失败的监督。</span>

<span style="color:#C00000"><strong>调研与判断。</strong>我将线上 P0-A/P0-B 的 `RagQuery` 合同与旧 Gold runner 的 raw-text phrase projector 对照，并读取公开 annotations、failure reports 和 v3 aggregate（不读 v3 逐题答案）。由此把 failure 分成五层：查询理解/策略编译、检索召回、证据关系、路由、安全；只有能证明候选改变了对应层，才把指标变化归因给它。v3 的 relation/set/route 计数只作为聚合假设，不能写 case-specific 规则。</span>

<span style="color:#C00000"><strong>产品决策与处理。</strong>RAG 自校正仍是 proposal-only；新建 28 题（16 dev + 12 challenge）开发集和待审核 annotations。V0 保留旧窄短语 baseline，V1 只做已审核同义词归一化，V2 把 `QuerySignals` 放到真实查询边界，先处理动作、能力、隐私、生命周期、冲突和多意图 union，再交给检索；V3 relation guard、V4 evidence packing 用来验证下游是否还有边际收益。每代都必须记录实际改变的预测数、dev/challenge、public regression、hard-safety、anti-overfit 和回滚方式；连续两代增益 `<0.01` 且未过质量门便停止。</span>

<span style="color:#C00000"><strong>真实结果与效果。</strong>V0 Composite=`0.355614`；V1=`0.403233`（+0.047619，改变 2 条预测）；V2=`0.947619`（+0.544386，改变 22 条预测，开发集 route/relation/Recall@5=100%）；V3/V4 各改变 0 条预测并停止。候选没有联网、没有调用 LLM/Provider、没有读 hidden 答案，active baseline 未改变，anti-overfit=`PASS`。这证明“修错层”是上一轮无增益的原因，也证明当前开发集上的上游修正有效；但 public regression/project Gate 仍 `FAIL`，RAG 不能写成产品化通过，必须由产品负责人审核 annotations 并新建独立 Holdout v4。</span>

## 2026-09-01｜失败驱动 Loop v2 后的工程一致性校验

本轮全量 `.venv/bin/pytest -q` 为 `178 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 以及失败驱动 Loop、P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 均通过。4 条 warning 是既有 Pillow 弃用提示。代码、合同、测试、报告和看板使用同一版 `rag-failure-driven-loop-v0.1` 事实；该校验不改变 RAG advisory-only、project Gate=`FAIL` 或候选未推广边界。

<span style="color:#C00000"><strong>2026-09-01 逐题复盘补充。</strong> 失败驱动报告新增 `final_candidate_diagnostics`，将 28 道公开开发/挑战题的 V0 与终态逐题状态、错误码、路由变化放在同一份脱敏报告中；人工复盘见 `docs/RAG_FAILURE_CASE_REVIEW_V2.md`。这解决了“只看到总分、不知道哪道题变好”的可观测性缺口，但不读取 v3 私有答案、不改变 active baseline，也不把开发集增益写成产品化通过。</span>

## 2026-09-01｜腾讯特效 Web Cloud 状态补充

腾讯特效 Web 继续是独立候选 Provider，不替换已验证的 Tencent BeautifyPic。Cloud 已完成最新代码重建并解决旧进程 ImportError；但 page 6 在服务端签名前发现缺少 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`，所以本轮没有加载 SDK、处理图片或产生 Browser Receipt。Card 继续保持 `candidate`，不能对用户承诺 Web 细项、批量或视觉改善。

即使后续官方示例图 smoke 成功，也必须补齐精确域名/License、图片出站与地区/留存、预算、真实回执、Gold 回归和产品负责人 promotion；RAG/LLM 不能因检索命中或一次成功自动放行。Effect Token 只用于服务端签名，不得进入页面、Trace、仓库或聊天。

## 2026-09-02｜V3 解冻验证：产品规则当前覆盖

产品负责人明确授权后，V3 由“一次性 Holdout-A 盲测”派生出独立 `validation` 副本，用于逐题失败分析和候选优化；原始 answerless 盲测快照保留、不重跑。验证副本允许使用 H01–H36 的题干和人工 Gold，但不进入在线 RAG、Prompt、Provider 或现役 baseline。

当前规则是：RAG 仍 proposal-only；候选只能改变自然语言→`RagQuery` 的查询编译或离线证据整理，不能生成参数、ProviderRun、权限或图片出站。G0–G5 每代记录逐题结论、失败码、SOP、完整安全 Trace、`changed_prediction_count` 和 public regression；G2 的 100% validation 结果因 public regression 退化而不采纳，G3 的保守守门候选才保留。最终 validation Route=100%、Evidence relation=97.22%、Recall@5=100%；G4/G5 无新增增益。固定 Precision/project Gate 仍 `FAIL`、hard-safety `PASS`，不得写成 RAG 产品化通过；推广前必须新建不与 V3 重叠的 V4 Holdout。

## 2026-09-02｜Web 回执关联规则补充

Streamlit 重跑不能导致同一浏览器请求换用新的 `request_ref`。page 6 以输入 hash/引用、参数、来源和 Card 版本形成非敏感 fingerprint，同一代次复用引用，参数或输入变化才开新代次；签名时间可刷新但不触发组件重置。旧代次或 hash 不一致回执安全忽略，不进入 `ProviderRun`。该规则只修复交互生命周期，不放宽 Web Card、图片出站或 RAG 权限。
## 2026-09-02｜Tencent Effect Web 真实重试边界

<span style="color:#C00000"><strong>本轮产品事实。</strong>真实重试已不再出现 `request_ref` 错位，说明同代次回执关联修复生效；但腾讯 Web SDK 返回鉴权错误码 100，未生成图片结果。当前 Card 继续为 `candidate`，不能因为页面可加载、License 存在或失败回执已保存，就宣称 Web 图片能力可用。</span>

<span style="color:#C00000"><strong>安全与可重试规则。</strong>失败后组件必须重新启用执行按钮；服务端拒绝 URL 形式的 `TENCENT_EFFECT_APP_ID`，因为 APPID 必须是腾讯账号数字 APPID，绑定域名只用于 License 域名校验。页面仅显示脱敏错误码和安全解释；原始 SDK 错误对象、Token、图片和密钥不得进入 Trace。修正 Secret 后只运行一次官方示例图，成功回执仍需完成隐私、区域、成本和负责人准入。</span>

## 2026-09-02｜Web 结果 Canvas 修复

<span style="color:#C00000"><strong>实现规则。</strong>腾讯 Web SDK 初始化后拥有其输出 Canvas，产品代码不得在 `takePhoto()` 返回后再次调整该 Canvas 的宽高。结果 ImageData 必须复制到新建的浏览器结果 Canvas，再用于预览、下载和 hash；若结果 Canvas 创建或写入失败，按失败回执处理，不宣称生成成功。该修复不放宽任何鉴权、同意、隐私或 Provider 准入规则。</span>
## 2026-09-02｜V4 Holdout 与 RAG 优化当前规则

V3 被负责人解冻后只作 validation；本轮建立与 V3 不重叠的 48 题 V4 独立 Holdout。V4 先以 answerless 运行一次并封存，再允许负责人授权逐题诊断。正式 blind baseline 的 Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、MRR=81.25%、nDCG@5=63.22%，hard-safety=0/48 PASS，project quality Gate=FAIL。答案键没有进入在线 RAG 或 active baseline。

产品规则继续定义为：RAG 只能在已审核知识范围内理解任务、召回资料、区分直接/参考/冲突证据并提出建议；它不能自由新增 Provider、参数、权限、图片出站或真实 ProviderRun。8A 计划前、8C 复测策略、Provider 失败降级、新 Provider 准入和冲突检查可以消费 RAG 建议，但事实放行仍由确定性状态机、权限策略和 Adapter 完成。

负责人授权后的 V4 validation 候选将语义诊断指标提升到 100%，但这不是泛化成绩；fixed Precision@3=51.39%，冻结项目 Gate 仍 FAIL，active baseline 未改变。G3–G5 连续无新增预测变化后停止，说明继续在下游打补丁已达到边际效益递减。完整题集、逐题 Trace、失败模式和命令见 [RAG_V4_HOLDOUT.md](RAG_V4_HOLDOUT.md)。

所有后续优化必须同时保留 fixed/effective/returned Precision，报告 hard-safety、route、evidence 集合/关系、Recall@5、MRR、nDCG、public regression、anti-overfit 和 `changed_prediction_count`。不能用解冻 validation 高分、稀疏 Gold 换分母或单次安全 PASS 宣称 RAG 已产品化。

## 2026-09-02｜Tencent Effect Web 最新失败边界

负责人再次明确点击 Web Provider 后，最新回执为 `web_receipt_effect_web_3a3c71bec3f24557`，SDK 错误码 100、规范化页面码 20001001，耗时 628ms，未生成结果图。稳定 `request_ref` 复用只表示同一请求代次，不能被解释为没有发生新的点击。失败事实已保留，Card 继续 `candidate`，不能进入主流程；下一次只在核对 License/Token、数字 APPID/签名、精确域名和 Secret 重载后运行一次官方示例图。

## 2026-09-02｜Tencent Effect Web 完整重试最新事实

随后从当前 Cloud 页面完整执行官方示例图流程，SDK 等待自身鉴权窗口后返回最终失败回执：
`web_receipt_effect_web_3a3c71bec3f24557`、耗时 `10360ms`、SDK 错误码 `100`、规范化码
`20001001`，未生成结果图。稳定 `request_ref` 仍是同一输入/参数代次的幂等引用，本次为新的明确
点击；失败事实可追溯，但不证明 Web Provider 可用。Card 继续 `candidate`，必须在核对
License/Token 配对、数字 APPID/签名、精确域名和 Cloud Secret 重载后才可进行下一次 smoke。

## 2026-09-02｜视觉决策冻结：Party Rock + 苹方

<span style="color:#C00000"><strong>产品负责人已冻结正式视觉输入。</strong>正式界面采用 [Tweakcn Party Rock](https://tweakcn.com/themes/cmlqxbfu8000004joajt9gs64) 的原始 Light / Dark token，不对明暗、饱和度、对比度或色相做二次改造；正式界面字体采用苹方（`PingFang SC`）。四元黑体与此前评审的其他中文字体只保留为后续品牌字标或实验候选，不进入本轮 UI 实现。</span>

<span style="color:#C00000"><strong>历史面积表述（已被下方最新覆盖替代）。</strong>早期曾将米白（Light background `#F2F1E6`）写成最大面积、紫色（primary `#A855F7`、secondary/accent `#C084FC`）写成第二大面积；该描述只保留为决策时间线，不再作为实现依据。当前执行以“紫色与米白共同主导、紫色略强；黑色结构；其他颜色少量点缀”为准，Party Rock 原始 token 不变。</span>

<span style="color:#C00000"><strong>实现边界。</strong>这条冻结只约束视觉 token、字体和相对使用范围，不改变任何同意、权限、Provider、结果保留、RAG、审计或 Trace 规则。Streamlit 当前尚未完成视觉迁移；四区布局比例、组件状态、可访问性、响应式降级和关键帧仍需 UI Gate。不得把本条冻结写成已上线 UI，也不得把主题 token 的选定写成字体或主题授权已完成。</span>

## 2026-09-02｜视觉冻结最新覆盖：紫色—米白共同主导与两张关键帧

<span style="color:#C00000"><strong>产品负责人最新反馈。</strong>原“米白最大、紫色第二”的面积描述只作为历史记录保留，当前执行以紫色与米白共同承担最大面积、紫色在入口暗流与关键操作块中略强为准。Party Rock 原始 token、苹方、黑色结构色和少量语义点缀边界不变；不调整主题的明暗、饱和度、对比度或色相。</span>

<span style="color:#C00000"><strong>关键帧范围。</strong>活跃视觉交付只保留 E01 入口和 E02 Agent 对话两张主关键帧。上传、自动检查、澄清、一次外部授权、结果/复测和停止仍由同一对话空间中的消息、事实块、授权 Sheet 和结果块承载，不新增独立状态页面、报告页或参数页。旧 K01—K04 仅作为历史资产归档，不属于当前实现依据。</span>

## 2026-09-02｜视觉候选最新覆盖：左侧黑导航与米白工作面

<span style="color:#C00000"><strong>产品负责人最新反馈。</strong>上一版中间工作区的紫色与黑色暗影/暗流造成沉重和僵硬的 AI 工具箱观感，现明确不再作为当前构图。Party Rock 原始 token 与苹方不变；所有视觉候选统一为最左侧黑色导航、中央/右侧米白工作面，紫色/淡紫柔性圆角框和关系轨迹，荧光绿少量活动节点，黑色线框/文字结构。不得在中间或右侧铺黑底、使用紫黑暗影渐变、发光网格或大面积荧光绿。</span>

<span style="color:#C00000"><strong>候选交付。</strong>基于 Getty `Tracing Art` 的关系轨迹与编辑式留白抽象，新增 A「档案游线」、B「柔性索引」、C「开放谱系」三套视觉候选；每套严格两张关键帧：E01 入口和 E02 Agent 对话。三套只改变视觉叙事，不改变自然语言主链、后台自动门控、外部一次授权、结果保留或 Trace 可见性边界。产品负责人选择前，任何候选都不是最终 UI 规范。</span>

<span style="color:#C00000"><strong>交付入口。</strong>候选评审页为 `design/keyframes/party-rock-pingfang/candidates/candidate-review.html`；风格原则为 `docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`；PNG 只作 Image 2 材质/比例方向稿，分层 SVG 才是可编辑/Figma 导入源。候选选择后才运行 Critical/Audit、WCAG/UI Gate 和 Streamlit 映射。</span>

## 2026-09-02｜Tencent Effect Web 真实成功后的产品边界

<span style="color:#C00000"><strong>最新事实。</strong>Canvas 生命周期修复后，Cloud page 6 已完成一次真实 Web SDK 静态图处理：回执 `web_receipt_effect_web_4d58ea15a0794370`，耗时 2601ms，`status=succeeded`，结果哈希已保存，结果图仅保留在当前浏览器会话。</span>

<span style="color:#C00000"><strong>产品含义。</strong>这证明“浏览器 SDK → 图片处理 → 脱敏回执”技术链路可运行，解决了此前的 Canvas resize 错误；但它不是经过多样本效果评测，也不是供应商隐私、区域、费用和精确域名准入的结论。Provider Card 继续保持 `candidate`，RAG 不能据此授权主流程。</span>

## 2026-09-02｜公平 RAG 评测与过程监督（当前冻结规则）

<span style="color:#C00000"><strong>产品负责人已确认。</strong>反思审计显示，V3/V4 的低分同时混入了“有没有听懂用户问题”和“有没有从真实知识库找到证据”两类问题。因此评测正式拆成两条轨道：自然语言理解轨道只看能否形成结构化查询及其状态；真实检索轨道只看经过合同校验的查询是否召回、排序并正确标记真实知识块。两条轨道不得用同一组预先写好的路由或证据标签代替。</span>

<span style="color:#C00000"><strong>过程先于分数。</strong>V3/V4 每一道题都必须先经过独立的确定性过程监督考官：检查题目无缺失/重复、答案和标注未读取、原题只在内存中使用、编译成功或明确降级、无论是否理解都生成合法查询、每题都有完整检索 Trace、最终结果只来自实际检索回执、没有 projection/Gold 注入，也没有网络/LLM/图片 Provider 副作用。过程门通过只说明“考试流程完整且可审计”，不说明答案正确。</span>

<span style="color:#C00000"><strong>历史快照不可修写。</strong>旧 V4 正式快照已经发现缺少检索阶段、缺少治理事实并含有上游 projection 注入；它仍保留为历史证据，不能补写 Trace、改名或重新解释为通过。新版无答案重放只能证明评测器和运行流程已修复；只有新的过程完整 answerless 运行通过后，才允许单独连接 Gold 计算质量。</span>

<span style="color:#C00000"><strong>指标边界。</strong>历史 fixed Precision 继续保留；同时增加诊断带：低于三分之一为弱，达到三分之一为已有一定效果，达到三分之二为较强。诊断带只用于定位和迭代，不能替换既定 project quality Gate，也不能用稀疏 Gold、换分母或补无关证据抬分。当前知识库规模先不扩张，RAG 仍 `proposal-only`，active baseline 不因过程门通过而改变。</span>

### 当前回执与下一步

- 新版 V3 无答案过程重放：`36/36` 题完整检索 Trace，`process_gate=PASS`；其中 5 题结构化理解，31 题明确标记为未知后继续检索。
- 新版 V4 无答案过程重放：`48/48` 题完整检索 Trace，`process_gate=PASS`；其中 8 题结构化理解，40 题明确标记为未知后继续检索。
- 旧 V4 正式快照审计：`historical_snapshot_process_gate=FAIL`，问题计数为 `MISSING_REQUIRED_STAGE=432`、`MISSING_GOVERNANCE_FACTS=48`、`PROJECTION_INJECTED_INTO_EVALUATION=48`、`FORBIDDEN_SIDE_EFFECT_OR_LEAK=2`。
- 新无答案重放的当前过程门为 `PASS`，质量状态为 `READY_AFTER_SEPARATE_GOLD_JOIN`；旧快照质量状态仍为 `LOCKED_HISTORICAL_PROCESS_AUDIT`。新验证可以继续，但不能把旧分数修写、复用或把新验证成绩写成 RAG 产品化。

可复核入口：[RAG 公平评测过程监督 Prompt](RAG_FAIR_EVALUATION_SUPERVISOR_PROMPT.md)、`reports/rag_fair_process_audit_v1.json/.html`。过程监督考官只负责完整性和证据血缘，不负责判断答案是否正确，也不能授权图片工具或外部 Provider。

### 当前工程回执覆盖（2026-09-02）

当前全量 `.venv/bin/pytest -q`=`196 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check`、
全部离线 smoke 和公平过程审计均通过。4 条 warning 是既有 Pillow 弃用提示。过程门 PASS 只说明新版
V3/V4 考试无漏题、无答案/标签注入且每题有完整检索 Trace；RAG 内容质量尚未评分，project Gate 仍
`FAIL`，`proposal-only` 和 active baseline 不变。

## 2026-09-02｜Tencent Effect Web 纳入 Meta-Agent 的当前产品规则

<span style="color:#C00000"><strong>工具目录规则。</strong>新增只读 Tool Registry，把已审核的 `tencent_beautify_pic` 与仍为 `candidate` 的 `tencent_effect_web` 同时登记。Registry 的 `execution_allowed` 不是用户授权，也不能替代确认范围、预算、内容安全、同人门和 Adapter 准入；候选工具只允许被看见、解释和提出建议。</span>

<span style="color:#C00000"><strong>Meta-Agent 规则。</strong>Meta-Agent 当前输出结构化 `ToolProposal`：阶段、请求功能、工具及 Card 版本、所需检查、RAG 证据引用、阻断原因和已审核 baseline fallback。`execution_authorized` 固定为 `false`；它不读照片/向量、不生成腾讯绝对参数、不生成签名、不创建 `ProviderRun`，RAG conflict/miss 不能变成猜测。</span>

<span style="color:#C00000"><strong>Web 与 REST 的合同隔离。</strong>Web 使用独立的浏览器参数和 `EffectWebBrowserReceipt`；本轮不把 `lift/shave/eye/chin` 塞入 BeautifyPic 的 `FaceLifting/EyeEnlarging` 字段，也不把一次浏览器成功回执解释为母版一致性达标。当前 Web Card 仍为 `candidate`，不进入真实主流程执行。</span>

<span style="color:#C00000"><strong>真实调用边界。</strong>page 6 的一次成功 Browser Receipt 仍可作为独立候选证据；Meta-Agent 集成 smoke 只验证“Card → Proposal → 阻断/兜底”且 `network_called=false`。要让 Web 结果进入 8A/8B/8C，必须先冻结结果交接 A（浏览器端复测）、B（一次性受限回 Python）或 C（只展示/下载）中的一个方案，不能在代码里暗自改变图片留存边界。</span>

## 2026-09-02｜Tencent Effect Web B 结果交接与 E1/E2/E3 当前规则（覆盖上一段 A/B/C 待决状态）

<span style="color:#C00000"><strong>产品负责人已冻结 B。</strong>浏览器 Web SDK 的结果图通过一次性 `result` 触发器回 Python；服务端必须校验当前 `request_ref`、输入 hash、Receipt 输出 hash、宽高、PNG/JPEG/WebP MIME 和大小上限。通过后只在当前 Streamlit 会话内存保留 bytes，立即交给共同 8C `VerificationResult`；data URL、图片 bytes、License Token 不进入 SQLite、JSONL、Trace、RAG 或 Git。</span>

<span style="color:#C00000"><strong>工具和 Agent 边界。</strong>Web Card 仍为 `candidate`。Meta-Agent 可以在 Registry 白名单内提出 Web，并给出已审核 BeautifyPic fallback，但 `execution_authorized=false` 固定不变。只有显式候选试验入口允许接收 Web 结果；状态机/Policy 仍负责同意、scope、预算、轮次、幂等和 fail-closed。SDK 返回成功不是母版一致或用户满意的证据。</span>

<span style="color:#C00000"><strong>E1/E2/E3。</strong>E1 将 Web 结果接入共同 `ProviderRun → VerificationResult`，无总分/概率；E2 要求成功、失败、请求/哈希/尺寸/MIME/大小异常和批量失败隔离均有回归，坏样本不能阻塞其他样本；E3 只有在真实更广样本、批量视觉、供应商隐私/区域/留存/费用、License/权限和产品负责人批准全部齐全后，才允许人工把 Card 改为 `verified`。在 E3 前 BeautifyPic 是唯一正式主流程 Provider。</span>

### 本轮实现状态

| 规则 | 状态 | 当前事实 |
|---|---|---|
| Web 参数进入 EditPlan | implemented/verified | Web `0—1` 参数与 BeautifyPic `0—100` 参数分离校验 |
| Web 结果 handoff | implemented/verified | request/hash/尺寸/MIME/大小校验；只返回当前会话 bytes |
| 共同 VerificationResult | implemented/verified（E1） | fixture 证明 handoff → ProviderRun → 复测；真实视觉效果仍需样本 |
| 多样本/异常/批量隔离 | implemented/verified（E2 合同层） | 离线 8 案例 `8/8`；覆盖输入哈希与大小上限；不是视觉泛化结论 |
| Web Card promotion | candidate | 缺真实准入证据和负责人批准 |

本轮全量回归为 `214 passed, 4 warnings`；Web E2 报告为 `reports/tencent_effect_web_regression_v1.json/.html`。

## 2026-09-02｜Web 纵向绑定测试与 E2 指标口径修正

新增一条 Meta-Agent proposal→Web `EditPlan` provider/Card 绑定测试，确保提议层和计划层不会静默选用不同工具；同时将 E2 的 `hard_safety_passed` 与 `batch_failure_isolation_passed` 分开计算：坏样本必须被拦截，是否有后续样本证明批量继续是独立字段。随后补齐输入哈希错位与结果大小上限样例。最新全量 QA=`216 passed, 4 warnings`，Web E2 为 8/8；Web Card 继续 `candidate`，不改变正式主流程或 E3 准入规则。
