# 决策日志

> 只记录会影响产品边界、外部费用、数据安全或后续架构的决定。每条决策应保留“背景、选择、原因、影响、可否回滚”。

| ID | 日期 | 决策 | 当前状态 | 影响 | 可回滚方式 |
|---|---|---|---|---|---|
| D-001 | 2026-08-26 | 项目独立放在 `portrait-consistency-agent/`，不修改原蓝图目录 | 已确认 | 代码、文档、日志可独立版本控制 | 移动目录并保留 Git 历史 |
| D-002 | 2026-08-26 | 运行时使用 `uv` 管理的 Python 3.10 | 已确认 | 兼容当前本机运行时与 MediaPipe/Streamlit 基线 | 修改 `.python-version` 后重新同步依赖 |
| D-003 | 2026-08-26 / 08-27 | 受邀 Streamlit URL 是后续部署方向，公网开放后置；平台、访问控制、区域、费用上限和是否购置服务器设备暂不决定 | 方向确认；部署/设备待未来 Gate | 当前继续本机开发和录屏，不假设现有电脑可承载长期本地主体模型或多人服务 | 继续本机运行；未来可选托管或新设备，不默认采购 |
| D-004 | 2026-08-26 | 密钥只读取本机 `.env`，绝不写入 Git、进展文档或 Trace | 已确认 | 后续 API 调用需显式配置 | 删除 `.env` 或轮换云密钥 |
| D-005 | 2026-08-26 | 该仓库使用本地 Git 身份 `Codex Local <codex@local.invalid>` | 已确认 | 仅用于本项目的可追溯提交，不修改全局 Git 身份 | 用户可随时修改本仓库的 `git config --local user.name/user.email` |
| D-006 | 2026-08-26 | 当前 Provider Card 声明支持的图片参数原则上都可执行；V0 腾讯 Adapter 已真实验证 `BeautifyPic` | 已确认；当前合同 v0.4 | 执行能力由外部工具能力卡决定，不把未来参数写死在产品层 | 增加新的 Provider Card/Adapter，并保留版本化能力证据 |
| D-007 | 2026-08-26 | V0 本地 UI 使用 Streamlit + SQLite/JSONL，绑定 `127.0.0.1` | 已确认 | 先获得可运行、可追溯的单用户原型，不保存原图 | 后续可在隐私/部署 Gate 后替换为 FastAPI + 前端 + PostgreSQL |
| D-USER-001 | 2026-08-26 | 腾讯云账号、密钥、`fmu` 服务级权限和服务开通 | 已完成；预算仍待定 | 已完成真实 `BeautifyPic` smoke Gate；后续调用受预算和频控约束 | 轮换密钥、撤销 `fmu` 策略或关闭服务 |
| D-USER-002 | 2026-08-27 | LLM 主模型选择 DeepSeek V4 Flash；失败回退本地模板，不自动把同一文本发给第二个云 Provider | 已确认；Adapter、离线 Gate 和一次真实文本 receipt 已完成 | 决定 IntentFrame 解析与解释路径；固定无个人信息文本已得到合法 Schema 回执，仍不等于复杂多轮/图片任务已验证 | 配置为模板 fallback 或以后通过新决策更换 Provider |
| D-USER-003 | 2026-08-26 / 08-27 | 受邀测试部署将使用平台 Secrets，不把密钥放入仓库；具体平台/密码/名单/成本/区域和服务器设备延后决定 | 部署方向确认；实施待未来 Gate | 需要部署前补访问控制、删除方案和管理员权限；不等同于公网开放 | 删除部署、撤销邀请或回到本地运行 |
| D-PROD-001 | 2026-08-26 | 不展示硬编码一致性指数，不设固定 90 分线；未来概率必须由人工可接受性样本校准 | 合同已升级；算法待实现 | 用户结果改为可解释的接受/调整/无法判断；无校准证据不展示概率 | 可在有 benchmark、holdout 和校准证据后启用概率输出 |
| D-PROD-002 | 2026-08-26 | 以五官和脸型一致为主；美白、磨皮默认关闭，用户明确允许后才执行 | 合同已升级；UI/规划器待实现 | 避免无意改变肤色、全身色调或照片风格 | 修改用户授权范围和 Provider 参数策略 |
| D-PROD-003 | 2026-08-26 | 母版只有一个生效版本；新母版成功后替换旧版本，失败时保留旧版本；母版不可直接二次编辑 | 合同/本地原子替换已实现；视觉/UI 待开发 | Profile 生命周期清晰，避免半成品覆盖可用母版 | 修改版本替换和恢复策略 |
| D-PROD-004 | 2026-08-26 / 08-27 | 母版只保存结构化五官/脸型派生信息，不保存原图、肤色、妆面、身体和隐私部位；主体锚点单独同意、183 天保存、30/7 天提醒，撤回即停用、主存储 24 小时删除、备份 7 天清理 | 合同/Policy v0.4 已实现；真实加密/TTL/delete worker 待实现 | 支持长期同一人物门控；到期提醒重新上传或删除锚点后降级为几何特征 | 撤回同意、删除锚点或改为会话内母版 |
| D-PROD-005 | 2026-08-26 | 质量置信度路由：低（`≤0.50`）重新上传，中（`>0.50 且 <0.80`）警告后继续，高（`≥0.80`）直接继续；只用于 quality/editability 并取最严格路由 | 已确认并进入 Policy v0 | subject match 独立输出 match/uncertain/no_match，不被质量置信覆盖 | 修改版本化 Policy，并用授权 benchmark 回归 |
| D-PROD-006 | 2026-08-26 | 多脸达标时让用户选择目标脸；自动隔离、裁剪、回贴并复测，只编辑所选单脸；无法稳定完成则解释原因并要求用户先裁剪；批量单张失败不阻塞整组但需先告知 | 已确认（待多脸编辑链路实现） | 防止误修错误人脸，支持批量任务部分成功 | 降级为只接受用户预先裁剪的单脸照片 |
| D-PROD-007 | 2026-08-26 / 08-27 | 用户行为分层：首次 Prompt/追问/再次会话是强意图或继续使用信号；点赞、点踩、明确评论是强反馈；退出/沉默默认未知，只有明确“要求重传后退出”等上下文才标路径中止；人工金标准和合成案例分开 | 已确认；事件账本/字段已实现，标注细则待未来概率模块 | 允许产品迭代而不把弱行为误写成满意或训练真值 | 调整标签来源、合成数据用途和 holdout 规则 |
| D-PROD-008 | 2026-08-26 | V0 不显示任何接受概率；未来启用概率必须有人工金标准、holdout 和校准证据 | 已确认 | 防止把未校准的模型输出包装成真实概率 | 在评测 Gate 通过后重新提案 |
| D-PROD-009 | 2026-08-26 | 母版结构化字段先尽量具体，保存归一化五官/脸型字段、特征级置信度、提取版本和 Provider 能力映射 | 合同与 V0 脸框/眼睛几何提取已实现；完整关键点模型待后续 | 提高解释性和可回放性；增加字段维护和隐私审计工作 | 精简字段或升级 Profile Schema |
| D-PROD-010 | 2026-08-26 | 更换母版时删除旧版本特征正文，保留脱敏审计事件；新版本失败时保留旧版本 | 本地原子替换与测试已实现；生产删除任务待开发 | 同时满足隐私删除与操作追溯 | 调整删除范围和审计字段 |
| D-PROD-011 | 2026-08-26 | 美白/磨皮前端说明可能影响肤色、皮肤质感和整张照片观感；默认关闭，只对当前任务生效，不写入母版 | 已确认（待 UI 文案审计） | 管理用户预期，减少无意的全图风格变化 | 修改提示文案和授权作用域 |
| D-PROD-012 | 2026-08-27 | 一次确认授权当前照片/批次、明确允许部位和可配置最多轮次的有界计划族；扩大范围、启用美白/磨皮、换照片/母版或超预算时重新确认 | 已确认并进入合同 v0.4 | 减少每轮重复确认，同时避免永久授权和越权执行 | 将确认策略改回逐轮，旧确认立即失效 |
| D-PROD-013 | 2026-08-27 | V0 当前最多三轮、连续两轮无改善提前停止，但数值属于版本化 Safety Policy，不写死在合同类型 | 已确认并进入 Policy v0 | 保持当前成本/风险边界，同时允许未来无破坏调整 | 发布新 Policy 版本并回归测试 |
| D-PROD-014 | 2026-08-27 | 多脸目标由系统执行选择、隔离、裁剪、回贴和复测；无法稳定完成时解释原因并要求用户先裁剪 | 已确认（工程链路待实现） | 避免腾讯接口同时修改最多五张脸；当前链路未完成前拒绝多脸整图执行 | 降级为只接受单脸输入 |
| D-PROD-015 | 2026-08-27 | Beta 的 MANUAL_REVIEW 只进入项目开发者队列；查看原图需要单独授权，不宣称已有客服团队 | 已确认并进入合同 v0.4 | 保持人工兜底真实、权限可审计 | 关闭人工复核，仅输出重新上传/终止 |
| D-PROD-016 | 2026-08-27 | 0.50/0.80 只用于 quality/editability 最严格路由；subject match 独立判定和后续校准 | 已确认并进入合同 v0.4 | 防止一个总置信度掩盖错人或不可编辑风险 | 发布新的路由 Policy 与主体模型版本 |

| D-TECH-017 | 2026-08-27 | 当前会话同人门采用腾讯 IAI `CompareFace` 3.0；原始分只留 evidence，V0 不展示概率；V0 临时 70/50 路由阈值可配置 | 已确认；Adapter 已实现；CAM 最小权限、IAI 服务开通和真实 smoke 均已验证 | 满足当前两张已授权图片的 1:1 门控，不把供应商分数包装成一致性指数 | 后续用授权 benchmark 发布新 Policy |
| D-TECH-018 | 2026-08-27 | 内容安全采用本地格式预检 + 腾讯 IMS `ImageModeration`；`Pass` 放行，`Review/Block` 在 V0 保守拦截；BizType 从环境/Secrets 读取 | 已确认；Adapter 已实现；IMS 服务开通后已获得真实 `Block` 回执 | 在进入同人/编辑前建立可审计安全证据，避免把用户声明当作审核结果；前三次失败的 RequestId 已留档。第四次 `RequestId=21bf408d-929a-46ec-83aa-78f071eff556` 成功返回 `Block`，证明拒绝路径真实可用，但当前照片不应继续处理 | 未来以另一张明确授权且真实返回 `Pass` 的照片验证允许路径；若供应商策略/BizType 改变，先更新 Provider Card/环境配置再测 |
| D-TECH-019 | 2026-08-27 | Profile v0 使用 Pillow + OpenCV Haar 的脸框/眼睛归一化几何；不保存原图；无主体锚点为 geometry-only | 已确认；构建器与组合服务已实现 | 先形成可解释、低依赖的真实 Profile 基线，后续可替换关键点模型 | 发布新 extractor/canonicalization 版本并回归 |
| D-PROD-017 | 2026-08-27 | 数据库先作为产品运行账本，而不是训练 Dataset；记录匿名 session、建档、意图、工具回执、复测、显式反馈、重传和活跃，聚合到本地管理员 Dashboard | 已确认；`product_events`、匿名 ID、Dashboard 和测试已实现 | 形成可追溯漏斗、bad case 归因入口和未来数据飞轮；现阶段不宣称留存/KPI/训练样本 | 在有授权端到端记录后，另行冻结 Dataset 抽取/去标识化/标注方案 |
| D-PROD-018 | 2026-08-27 | 用户明确不满意时立即停止下一次工具调用；LLM 只分类不满意原因，确定性规划器映射解决方式，新的执行需再次确认 | 已确认；Prompt/状态规则已同步，运行状态机待开发 | 防止在授权范围内继续叠加修改、放大不满意 | 仅能在未来另行决定默认继续或改变确认策略 |
| D-PROD-019 | 2026-08-27 | Beta 测试将“处理当前照片”“保存主体锚点”“允许公开演示”拆为独立同意；用户需声明有权处理照片，未成年人/未经授权第三方照片不接受 | 已确认；同意 UI/审计待开发 | 区分产品处理、长期敏感特征与展示用途，避免单一勾选越权 | 撤回某一项后仅停止对应用途；公开演示不再使用新材料 |
| D-TECH-020 | 2026-08-27 | LLM 只接收脱敏最小必要文本与结构化上下文；不发送照片、Base64、人脸向量、密钥或原始 Trace；Demo 默认不启用 OpenRouter/跨境路由 | 已确认；Adapter、页面单轮文字授权、Trace 脱敏、fallback 和一次真实 live receipt 已完成 | 将语言理解与敏感视觉数据隔离，降低 Provider/跨境治理复杂度；本次实际输出可被 Schema 校验，未发送图片数据 | 未来增加云 Provider 或路由时必须新增隐私/成本决策 |
| D-TECH-021 | 2026-08-27 | 多脸实现路线为 YuNet 检测 → 用户选脸 → MediaPipe/轻量遮罩隔离与裁剪 → BeautifyPic → 羽化回贴 → 非目标区域检查 → 目标脸复测；失败降级为用户先裁剪 | 已确认；工程待开发 | 解决 Tencent 不能指定编辑哪张脸的风险，不对外虚称已经支持多脸 | 继续只接受单脸输入，或未来换支持目标脸参数的 Provider |
| D-TECH-022 | 2026-08-27 | DeepSeek 只返回非持久化 `IntentCandidate + 一个澄清问题 + 摘要`；系统补入 ID、版本、文本 hash 和确认作用域，执行倾向一律先进入 `PENDING` | 已实现、9 条 Adapter 测试覆盖，并完成一次真实 Schema receipt | 将语言理解与权限/工具事实分离，防止 Prompt 注入伪造系统字段或一句话绕过编辑确认 | 保留同一 `IntentFrame` 合同，替换 Adapter 或收紧候选 Schema |
| D-PROD-020 | 2026-08-28 | 8A 不再追求总相似度或 90 分线；采用“逐特征局部几何差异 + 严格双眼测量”表达目标照与母版的可解释差异。只有恰好检测到两只眼框且达到规划置信下限，眼睛面积差异才可进入大眼计划；眼距/构图只作诊断 | 已确认并实现 | 用户看到的是“哪里不同、为什么建议、哪些能执行”，避免把未校准的几何距离包装成概率；后续可在人工金标准完成后另行提出概率模型 | 发布新版本测量/展示策略；不改六个合同的职责边界 |
| D-PROD-021 | 2026-08-28 | 检查点 8A 只生成 `proposed`、`requires_confirmation=true` 的修图前计划；即使用户说“直接修”，也不能在本步调用 BeautifyPic；美白/磨皮显式保持 0 | 已确认并实现 | 将诊断、计划、用户确认和外部执行分层，降低误修和越权；下一步可在确认页一次授权有界计划族 | 回滚为仅诊断；或由新的确认策略决定更细的参数编辑权限 |
| D-TECH-023 | 2026-08-28 | 增加确定性 `geometry-edit-planner-v0.1`：目标脸宽高比例更宽才候选 `FaceLifting`，目标眼睛面积比例更小且双眼可测才候选 `EyeEnlarging`；差异 ≤4% 不加参，4%—12% 按版本化 mapping policy 映射，超过 12% 不无限叠加；方向不可达/不可测/禁改转 suggestion-only | 已实现并通过 5 个规划器测试及 fixture Trace | LLM 只做意图理解和解释，数值由可回归规则生成；计划记录策略版本和降级原因，便于坏例归因 | 替换 `mapping_policy` 新版本，保留旧计划和 Trace |
| D-TECH-024 | 2026-08-28 | 对用户另行提供且明确授权的 JPEG 重跑 IMS `ImageModeration`，得到 `Suggestion=Pass`、`RequestId=211483d5-4ee0-41e8-b5d5-156f81557a69`；此前 `Block` 证据继续保留 | 已验证单样本允许路径；不代表全面内容安全覆盖 | 完成一条真实“允许进入后续门”的证据，同时维持 `Review/Block` fail closed | 只保留历史回执；未来换 BizType/供应商前重新跑授权样本 |
| D-PROD-022 | 2026-08-28 | 检查点 8B 确认页不提供数值滑杆直接改当前方案；用户自然语言实质改口必须生成新的 IntentFrame/不可变 EditPlan，并重新确认 | 已确认并实现 | 防止确认页成为绕过规划器、安全参数与审计链的旁路；用户仍可自然表达偏好 | 回退为仅诊断/参数建议，或在未来经新决策加入受控的计划编辑体验 |
| D-PROD-023 | 2026-08-28 | 外部编辑确认绑定当前照片 hash、Profile 版本、允许部位、显式参数和 Policy；有效期为 10 分钟，变化/过期/Gate 失败/重复点击均不调用腾讯 | 已确认并实现 | 明确用户授权边界，降低换图后误修和过期确认越权风险 | 发布新的版本化 `ExecutionPolicy` 并补回归测试 |
| D-PROD-024 | 2026-08-28 | 腾讯结果图仅在当前浏览器会话内临时预览并允许用户主动下载；不写 SQLite、JSONL、Trace 或项目结果目录，最多 10 分钟内存窗口 | 已确认并实现 | 减少结果人像的持久化隐私面；历史 smoke 结果文件只作为规则冻结前的 Gate 证据 | 未来若确需持久化，须另行冻结对象存储、访问控制、TTL、删除证明和用户同意 |
| D-PROD-025 | 2026-08-28 | V0 每份已确认计划只允许一次 BeautifyPic 外部尝试；任何错误均不自动重试，再次尝试必须由用户新确认 | 已确认并实现 | 避免隐形重复扣费和用户不知情的连续编辑；ProviderRun 可保留真实错误供归因 | 未来通过成本/错误率/体验评测后，以新 Policy 决定可恢复错误的显式重试方案 |
| D-TECH-025 | 2026-08-28 | 8B 由确定性执行服务生成 `user_structured_input` 执行意图、confirmed plan revision、scope hash、一次 Adapter 调用与 ProviderRun；本地 idempotency key 阻止已保存回执后的重复点击 | 已实现并通过 6 个离线案例 | 将 LLM、确认、参数规划和 API 真实事实分层；结果 Base64 不进入持久化 Trace | 本地幂等不是多进程/宕机恢复/Provider-side exactly-once；部署前另行设计 |
| D-PROD-026 | 2026-08-28 | 8C 验证范围按用户最终目标和本轮 `EditPlan` 动态确定；每个 executable 且可可靠测量的目标特征必须有修前/修后证据，未接入/不可测特征显式为 `unverifiable/suggestion_only` | 已确认；8C-1/8C-2 已实现本地观察与有界计划族，外部/混合复测待后续 | 不再把“腾讯当前能改什么”误当作任务完成；新增工具接入后可扩展验证范围 | 发布新 Provider Card/Extractor/Verifier 版本并回归 |
| D-TECH-026 | 2026-08-28 | 8C 增加 `VERIFICATION_STRATEGY_SELECT`：Agent 在已审核/已授权策略集合中提议复测方式；状态机负责状态/白名单，权限策略负责出站/成本/确认，Adapter 负责真实调用 | 首个确定性 baseline 已实现；LLM/RAG 动态提议和外部 Adapter 待后续 | 允许 Agent 做策略选择，同时避免自由调用未知 API；RAG 未来提供工具证据 | 若策略提议评测不稳定，可先降级为固定本地策略；不改变 ProviderRun 事实边界 |
| D-PROD-027 | 2026-08-28 | 8C 初次确认覆盖最多三轮有界计划族；每轮新建子 `EditPlan` 和独立 `ProviderRun`，只有正确方向上的可验证累积改善才继续；无改善/变差/不可判断/达标/用户不满意时停止；“Agent 认为达到目标”必须由结构化 VerificationResult 和版本化停止策略支撑 | 已确认；8C-2 已实现离线计划族续跑，外部/混合复测待后续 | 保留成本上限和可回滚证据，避免同一计划隐式重试；允许 Agent 围绕最终目标继续调整，但不把 LLM 主观文本当作停止事实 | 通过新版本 Safety Policy 改轮次或恢复策略；旧 Run 不覆盖 |
| D-PROD-028 | 2026-08-28 | 8C 结果由 Agent 判断达到当前可验证目标后再展示并收集反馈；点赞/点踩和明确文字为强反馈，追问/新会话/下载为行为证据，退出/沉默按上下文记录未知；WAU/MAU进入匿名运营账本 | 已确认；8C-2 已接入反馈 UI/事件，文字只保留 hash | 不用固定按钮或沉默推断满意；支持长期产品迭代 | 调整事件 taxonomy 和看板聚合，不修改视觉合同 |
| D-PROD-029 | 2026-08-28 | RAG 可在质量门、规划、`VERIFICATION_STRATEGY_SELECT` 和失败路由等工具决策点触发；当前只保留 Provider Card 结构化基线，8C 预留查询/evidence 接口；8C 核心闭环通过且准备新增 Provider 时，先单独冻结 RAG 规则再一次性建设向量/混合检索 | 方向已确认；RAG 细则和工程待开发 | 保留学习 RAG 的路线，同时不把未接入工具或未经审核知识带入执行 | 进入 `RAG_DECISION_GATE.md` 重新决定知识源、存储、切片、召回、融合、时效、权限和评测 |
| D-TECH-027 | 2026-08-28 | 8C-1 将策略提议与验证事实分开：新增 `VerificationStrategyProposal`，`VerificationResult` 增加策略、出站/同意、计划族和目标证据字段；合同从 v0.3 升级为 v0.4 | 已实现并通过全量回归 | 可以回放“Agent 建议了什么”和“验证器测到了什么”，避免 LLM 伪造 API 事实 | 外部策略、三轮计划族完成后继续增加真实引用字段并迁移测试 |
| D-TECH-028 | 2026-08-28 | 8C-1 的确定性 baseline 使用 `measurement_tolerance=0.01`、`target_gap_tolerance=0.04`、最低测量可靠性 0.80；首批 allow-list 只启用 local geometry 与 manual review | 已实现；均为版本化可配置 Policy，不是概率或永久合同限制 | 先跑通可解释、低成本、无新增图片出站的复测；为未来 LLM/RAG selector 留替换点 | 有真实 8C receipt 和新增 Provider 后，按 RAG/benchmark Gate 重评策略与阈值 |
| D-TECH-029 | 2026-08-28 | 修后结果复用同一 V0 本地观察器；只比较 EditPlan 中 executable 特征；结果不可比较走 RESHOOT，变差无回退引用走 MANUAL_REVIEW；保持项明确记录未自动验证 | 已实现并通过 6 条 8C-1 服务/落账测试 | 不把腾讯返回图、妆面/肤色或供应商分数误写成“已达标”；失败原因可追踪 | 接入真实外部/混合复测时仍需新的出站同意、Adapter 回执和回归集 |
| D-TECH-030 | 2026-08-28 | 合同 v0.4 的修后验证字段使用现有六表/Trace 投影；初始化增加 `contract_v0_4_verification_observation` 迁移标记并验证 VerificationResult 落账不含结果字节 | 已实现并通过全量回归 | 新字段有可追溯版本边界，数据库仍是产品运行账本而非 Dataset | 若升级生产数据库，需保留迁移历史并重新做脱敏/TTL 评测 |
| D-PROD-030 | 2026-08-28 | `REPLAN` 不是再次无声调用：只有前轮真实成功、结构化改善且未达目标、结果图 hash/原确认范围/期限/轮次均仍匹配时，系统可生成下一轮子计划；**历史版本曾要求每轮页面点击，已由 D-PROD-038 修订为“首次有效 scope 内自动执行并保留 Trace”** | 已被 D-PROD-038 supersede；历史离线链路仍保留 | 在减少重复问卷的同时，不把有界确认误解成隐藏连续扣费；范围改变仍重新确认 | 若真实 Beta 证明自动续跑成本/体验不可接受，再发布新的确认/预算 Policy |
| D-TECH-031 | 2026-08-28 | 8C-2 用已有 v0.4 `parent_plan_id`、`parent_run_id`、`previous_verification_id`、`cumulative_improvement` 字段实现父子血缘；修正 8C 不得用 8A proposed 草案复测，必须使用 8B confirmed plan revision。子计划使用上一结果图 hash，子 Run 使用父回执的 input ref/hash | 已实现并通过 6 条 8C-2 fixture 测试（含 scope 变化 fail-closed） | 每一轮可回放“哪一张图、哪一个确认、哪一次 ProviderRun”产生了下一轮；不新增数据库图像持久化 | 未来如换持久化/分布式执行，保留血缘字段并补迁移与恢复测试 |
| D-TECH-032 | 2026-08-28 | 8C-2 的 `followup_mapping_v0` 只对已改善但仍有剩余 gap 的可执行特征生成 2—6 的新输入图单次参数；不把腾讯 0—100 参数视作跨请求可累加滑杆 | 已实现并通过 fixture Trace | 防止把重规划退化为复用或不断叠加上一轮参数；数值是版本化工程策略，不是视觉概率 | 发布新 mapping Policy 并对授权 benchmark 回归 |
| D-PROD-031 | 2026-08-28 | 结果页的点赞、点踩、文字评论均作为强反馈记录；点踩或文字评论关闭当前计划族，文字仅保留 hash，不能直接当作新的修图命令。用户若要继续，须主动提交新的 IntentFrame 并重新规划/确认 | 已确认并实现当前会话 UI/脱敏事件 | 把满意度事实与用户意图分开，避免自由文本绕过权限，同时给后续 bad case/运营分析留下证据 | 调整反馈 taxonomy 或未来在用户重新授权后引入文本澄清 LLM |
| D-PROD-032 | 2026-08-28 | 将短期任务事实、短期反馈/继续使用信号和长期产品健康指标分层记录；Profile 建立率、首次成功修图率、7/30 日回访、WAU/MAU、会话完成率、失败后重传率和明确满意/不满意比例进入匿名 `product_events`/Dashboard；退出/沉默按上下文记为路径中止或 unknown | 已确认；字段/看板继续补真实受邀端到端采集 | 支持 bad case 归因和产品迭代，避免把新会话/下载/沉默误写成满意或训练真值 | 发布新的事件 taxonomy/聚合 Policy，并保留历史事件语义 |
| D-TECH-033 | 2026-08-28 | LLM 只接收脱敏最小必要文本与结构化上下文；不发送照片、Base64、人脸向量、主体锚点、密钥或原始 Trace；DeepSeek 失败先走本地模板，不自动转发第二云 Provider；OpenRouter/跨境默认关闭；ZDR 必须以供应商合同/配置核验 | 已确认；Adapter 与 Trace 脱敏已实现，ZDR/部署治理待核验 | 降低敏感数据出境与多 Provider 留存面，便于回放 fallback | 新增 Provider 前重新做数据出境、留存、ZDR 和成本 Gate |
| D-PROD-033 | 2026-08-28 | 处理本次照片、外部 Provider 处理、保存主体锚点 6 个月、公开演示分别取得同意；V0 默认本人单人且成年，多人须确认所有人授权，未成年人拒绝；IMS `Review/Block` 保守拦截；公开展示前再次确认，撤回后停止新展示 | 已确认；部分同意 UI、锚点 TTL/delete 和多脸隔离仍待开发 | 把肖像权、敏感生物特征、第三方传输和公开展示分开，避免单一勾选越权 | 关闭某一用途同意即仅停止对应路径，保留脱敏审计 |
| D-PROD-034 | 2026-08-28 | RAG 的产品消费点扩展为：8A 生成 `EditPlan` 前查询工具能力/限制，质量门、`VERIFICATION_STRATEGY_SELECT` 和失败路由按需查询；当前仍仅有 Provider Card 基线，细则和代码未冻结 | 方向已确认；RAG 独立 Gate 待讨论 | 解决“只能按腾讯现有能力修”的瓶颈，同时保持工具白名单、权限和事实边界 | 若召回评测不稳定，暂退回 Provider Card baseline |
| D-TECH-034 | 2026-08-28 | `mapping_policy_v0.1` 的差异阈值、模式上限、参数版本和降级原因必须进入 `EditPlan` Trace；差异百分比不直接等于腾讯绝对强度，`≤4%` 不加参、`4%—12%` 规划、`>12%` 不无限叠加，模式上限 `8/15/22` | 已实现并通过 8A/8C-2 fixture；不是概率校准 | 参数可解释、可回归、可换版本，避免 LLM 凭感觉猜滑杆 | 发布新 mapping Policy 并对授权 benchmark 回归 |
| D-TECH-035 | 2026-08-28 | 将真实 DeepSeek 单轮 IntentFrame receipt 作为执行版 PRD 的证据案例：LLM 只完成“听懂文字”，不能生成用户 ID、确认令牌、参数、ProviderRun 或执行授权 | 已验证；一次真实 live receipt，非图片链路证明 | 面试与后续复盘能区分已验证能力和未实现边界 | 替换 Adapter/Prompt 时保留历史 receipt 与 Schema 版本 |

## 2026-08-27 四合同审计候选的最终处理

> 下列五项已由用户逐项确认，并分别转为 `D-PROD-012`—`D-PROD-016`；表格保留候选到正式决策的追溯关系。

| 候选 ID | 推荐修正 | 当前状态 | 不确认的影响 |
|---|---|---|---|
| P-AUDIT-001 | 一次确认授权“当前照片/批次 + 明确部位 + 最多三轮”的有界计划族；扩大范围或启用美白/磨皮时重新确认 | 已采纳 → D-PROD-012 | 每轮确认会拖慢体验；永久默认执行又会越权 |
| P-AUDIT-002 | 三轮是 V0 可配置 Safety Policy 上限，不写死在合同类型；连续两轮无改善提前停止 | 已采纳 → D-PROD-013 | 与此前“不硬编码三轮”及附件“最多三轮/两轮无改善”冲突 |
| P-AUDIT-003 | 自动选脸/隔离完成前，V0 多脸拒绝或要求先裁剪 | 已扩展采纳 → D-PROD-014 | 腾讯接口没有目标脸选择参数，直接调用可能误修其他人 |
| P-AUDIT-004 | Beta 的 MANUAL_REVIEW 只表示“待项目开发者复核”，查看原图另行授权 | 已采纳 → D-PROD-015 | 若没有真实处理人，用户会被误导为已有客服/运营队列 |
| P-AUDIT-005 | 0.50/0.80 仅用于 quality/editability 并取最严格路由；subject match 单独判定和校准 | 已采纳 → D-PROD-016 | 一个总置信度会掩盖身份不确定或工具不可执行 |

已直接按技术事实纠正、无需另设产品选择的边界：腾讯绝对参数只允许 0—100；参数与安全上限由确定性规划器/策略决定而非 LLM；ProviderRun 由 Adapter 生成；V0 不以接受概率作为停止条件；不向用户展示隐藏思维链，只展示可验证的进度、工具回执和决策摘要。

## 2026-08-28 追加决策｜RAG 扩展边界与 8C 受限自动续跑

| 决策 ID | 日期 | 决策 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-036 | 2026-08-28 | RAG 不把产品能力永久限制在腾讯当前四个参数；未来可通过经审核的 Provider Card、真实 Adapter、权限、成本/延迟证据和回归测试扩展能力，但不允许自由调用未知 API。RAG 细则仍进入独立决策 Gate。 | 已确认；方向已同步 | 8A 规划前、8C 策略选择和失败路由都预留工具知识检索位置；当前仍不宣称完整 RAG | RAG Gate 冻结知识源、存储、切片、召回、融合、时效、引用与评测后再开发 |
| D-PROD-037 | 2026-08-28 | CompareFace 只作同一人物辅助证据，IMS 只作内容安全证据，二者都不能替代几何复测。首次外部处理同意若已覆盖当前 Provider/用途/照片/出境范围，8C 可直接触发；scope 变化才重新授权。 | 已确认；代码 Gate 保留 | 减少逐轮授权摩擦，同时维持数据出境和工具白名单边界 | 新增 Provider 或新用途时重做权限评审 |
| D-PROD-038 | 2026-08-28 | 8C 的 `REPLAN` 在首次确认的照片、Profile、允许部位、用途、Provider、预算、有效期和最多三轮范围内，可自动生成、执行并复测子计划；不再逐轮展示参数或要求点击。每个子轮仍是新 plan/Run，必须有方向正确的累积改善和确定性 preflight，失败/边界变化 fail closed。 | 已确认并实现 app/service/测试 | 用户只在首轮承担一次外部授权和最终结果反馈；Trace 记录自动触发、scope/hash、父子血缘、RequestId、耗时、预算和路由 | 受邀 Beta 真实多轮回执后复核成本、体验、停止策略 |
| D-TECH-036 | 2026-08-28 | 为 8C-2 增加 `auto_followup_preflight`、`auto_followup_completed`、`auto_followup_verification_preflight/completed` 事件和 Streamlit sentinel；子轮 `ProviderRun`/计划 Trace 标记 `execution_trigger=auto_bounded_followup`，防止 rerun 重复扣费。 | 已实现并通过全量回归（87 passed, 4 warnings） | 自动执行不等于静默执行；可观测、幂等和失败原因可回放 | 分布式部署前仍需队列、跨进程幂等和持久化结果生命周期设计 |

## 2026-08-28 追加决策｜RAG 治理、P0 方向与评测闭环

| 决策 ID | 日期 | 决策 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-039 | 2026-08-28 | RAG 执行知识只接受官方 API/SDK/License/隐私/成本资料与项目人工审核内容；Provider Card、权限/失败规则和真实回执可入库，原图、人脸向量、密钥、未脱敏文本和未审核网页不得入库。只有官方来源 + 已 smoke 的 Provider Card 才可影响执行；内部 bad case/用户经验先仅用于解释。 | 已确认；未实现入库服务 | 将知识、用户数据和工具放行证据分开，防止 RAG 扩大未授权能力 | 首批 SQLite 知识库导入时逐条人工审核 |
| D-PROD-040 | 2026-08-28 | RAG P0 本地 SQLite 优先，人工双周复审、启动时加载、版本切换；生命周期 worker 只能提醒/生成候选 diff，不能自动发布。RAG query 只含已校验的结构化任务槽位，不含用户原话、照片或向量；8A 只查询能力/限制/权限/失败处理，参数仍由 `mapping_policy` 决定。 | 已确认；P0-A/P0-B 检索已实现，worker 待开发 | 为本地 Demo 保留可迁移的 SQLite + 本地 embedding/向量索引路线，同时不新增数据出境 | 真实用户测试前评估云端迁移、ZDR、留存与费用 |
| D-PROD-041 | 2026-08-28 | RAG Trace 必须记录 query hash、过滤/召回/融合/重排、knowledge refs、淘汰原因、版本、耗时、成本与 fallback；未来新增 lifecycle/observability worker 和 Dashboard。Gold Set 覆盖支持、未接入、过期、冲突、缺槽、无结果、权限和提示注入。 | **当时**已确认；Gold Set 草案已建，worker/dashboard 待开发。后续 Dashboard 已由 D-PROD-052 / D-TECH-040 实现，worker 仍待开发 | 让检索质量、安全路由与 bad case 可反查具体 Trace，避免只汇报平均分 | 人审 Gold Set 后冻结指标目标和告警阈值 |
| D-PROD-042 | 2026-08-28 | 不把互相冲突的 RAG 输入强行冻结：切片单位、P0-A/P0-B 的混合检索时点、Top-K/低置信、动态上下文/overlap、8C 外部/混合候选是否执行仍为显式产品决策门。硬事实冲突必须阻断并进入人工审核；LLM 只能解释，不能裁决。 | P0-A/P0-B 配置已由 D-PROD-044 冻结并实现；正式回接仍待决策 | 防止代码同时实现互相矛盾的“整篇/原子切片”“仅提议/可执行”等规则 | 下一门只讨论 8A/8C 回接、Gold Set/holdout 与外部/混合执行范围 |
| D-PROD-043 | 2026-08-28 | 对“引用只留 Trace”与“用户要看到来源/未采用原因”的二次澄清，以后一轮的明确选择为准：P0 结果页展示来源名称、版本、是否支持/为何降级的紧凑依据卡；后台保存完整 `knowledge_refs` 和淘汰原因；不展示原文全文、相关性分数或完整 Trace。 | 已确认；P0-A/P0-B 页面与检索工程已实现 | 兼顾 C 端可解释性、隐私和用户认知成本，且能在 bad case 时回放证据 | P1 再决定是否可展开受控摘要 |
| D-PROD-044 | 2026-08-29 | 产品负责人确认 RAG P0 的五项推荐：`KnowledgeItem/KnowledgeChunk` 双层结构；P0-A 先 SQLite + metadata + FTS、P0-B 后接本地混合检索；P0-A FTS 前 5、P0-B 的 8+8/RRF10/rerank10/LLM3—5 仅作实验配置且分数不放行；不固定 20% overlap；RAG 对 8C 外部/混合复测仅提议、不执行。 | 已冻结；P0-A 与 P0-B 均已完成本地验收 | 允许先跑通可审计检索与安全降级，不扩大图片出站、Provider 或执行权限 | P0-B 当前实现记录在 D-TECH-038；下一门只讨论 RAG 与 8A/8C 的正式回接 |
| D-TECH-037 | 2026-08-29 | 按 D-PROD-044 实现 RAG P0-A：独立 `rag_contracts.py`、`storage/knowledge.sqlite3`、3 张审核来源卡/10 条原子规则、生命周期/Provider/operation/region metadata 过滤、SQLite FTS5 前 5、来源依据卡和脱敏检索 Trace。 | 已实现并本地验证 | 9 条定向测试与默认不联网 smoke 覆盖支持能力、未接入能力、多脸、保持项、同人/安全语义、出站拒绝、缺槽、过期、冲突和注入式知识；全量测试为 `96 passed, 4 warnings`。 | P0-A 不读照片/原话、不调用 LLM/Tencent/API、不产生参数或 ProviderRun，也尚未接回 8A/8C；P0-B/正式回接另开 Gate。 |
| D-TECH-038 | 2026-08-29 | 按 D-PROD-044 完成 RAG P0-B：复用 P0-A 的 SQLite 权威知识与硬过滤，在独立 `storage/knowledge_vectors.sqlite3` 中保存可重建的向量/hash；本地 `bge-small-zh-v1.5` embedding + FTS 前 8、dense 前 8、RRF 前 10、本地 `bge-reranker-base` 重排前 10，最多采纳 3 条证据。模型固定到本次实际 smoke 的公开 revision，正常运行仅本地缓存；模型不可用时退回 P0-A 稀疏路径。 | 已实现并完成真实本地 smoke | 6 条 P0-B 离线回归覆盖混合路径、语义补召回、索引复用、模型缺失 fallback、缺槽短路、出站/注入拦截；默认禁止下载的真实 smoke 加载固定本地模型，未读照片/原话、未调用 LLM/Tencent/API。 | **当时**排序模型不产生参数、不放行权限、不接入 `EditPlan`/`VerificationResult`；随后 P0-C 已受限回接 8A/8C，Dashboard 已由 D-TECH-040 实现。新工具/Adapter、人工 Gold Set 数值门和 worker 仍是后续 Gate。 |

## 2026-08-29 追加决策｜RAG P0-C 受限 evidence 回接

| 决策 ID | 日期 | 决策 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-045 | 2026-08-29 | RAG 只能提议，不能授权。P0-C 可在 8A 生成计划前、8C 选择复测策略时、工具失败降级、新 Provider 评估、参数/权限冲突时被调用；`RagAdvisoryDecision.execution_authorized=false`。 | 已冻结并实现 | RAG 可提高工具知识覆盖，但状态机、确认 scope、Policy、Provider Card、Adapter 和真实 receipt 仍是执行唯一放行链。 | 新 Provider/external-hybrid Adapter 仍需独立 Gate。 |
| D-PROD-046 | 2026-08-29 | P0-B 结果分 `direct_evidence`、`reference_information`、`conflict_information`：无冲突时 direct 供既有确定性模块参考、reference 仅解释；硬冲突必须完整带回来源并 `CONFLICT_BLOCKED`，用户/LLM 只能选择人工复核、手动建议或停止，不能裁决一条事实执行。 | 已冻结并实现 | 防止“排序模型/聊天模型替代硬事实和权限”；冲突 evidence/bad case 可回放。 | 人工复核流程、运营角色和冲突解决 SLA 待部署阶段定义。 |
| D-PROD-047 | 2026-08-29 | RAG-dependent 新能力/策略出现 miss、索引故障、缺关键槽或无 direct evidence 时立即停止该 RAG 分支并返回“不知道”，不允许 LLM 幻觉；记录知识缺失/空召回/重排无直接证据/索引/缺槽/冲突 bad case。仅已独立审核且普通 Gate 已通过的 baseline 可原样保留为 `baseline_degraded`。 | 已冻结并实现 | 将“RAG 没找到”与“当前已存在的安全 baseline”分开，不因检索失败扩大或关闭既有能力。 | 真实 query 数据后评估缺失类型分布和知识更新节奏。 |
| D-PROD-048 | 2026-08-29 | 新 Provider 采用 Candidate Card → Adapter shell/测试替身 → 权限/预算 → live smoke/receipt → RAG Gold 回归 → 产品负责人冻结 → `reviewed_active` 的准入链；RAG 搜到资料不等于可上传图片。首批验收锚点选 RAG-G01/G09。 | 已冻结；生命周期前半段待后续 Provider 实践 | 新能力扩展可追溯、可回滚；G01 保护“证据不等于参数/执行”，G09 保护“冲突不等于可任选”。 | 人工 Gold Set 的问法、评审人数、holdout 与数值阈值待定。 |
| D-TECH-039 | 2026-08-29 | 实现 `services/rag_advisory.py`、`RagAdvisoryDecision`、`RagBadCaseRecord`、知识账本 advisory/bad-case 表，以及 `EditPlan`/`VerificationStrategyProposal`/`VerificationResult` 的受限 `knowledge_refs`。将 P0-C advice 接入 8A 规划前与 8C 策略建议前。 | 已实现并本地 smoke/回归验证 | 新增 4 条 G01/G09/miss/baseline 定向回归与 `smoke_rag_advisory.py`；全链不读照片/原话，不调用 LLM/Tencent/API，trace 只记录结构化引用/计数/路由。**P0-C 收尾当时**全量为 `106 passed, 4 warnings`，并实际通过 Ruff、compileall、diff check。 | 不能据此宣称视觉效果、external/hybrid 验证、RAG worker 或新 Provider 已完成；Dashboard 已在后续 D-TECH-040 完成，当前全量测试数以 D-TECH-040 的 `107 passed, 4 warnings` 为准。 |

## 2026-08-29 追加决策｜RAG 评测 v2、Provider 扩展、混合复测与可观测性

| 决策 ID | 日期 | 决策 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-049 | 2026-08-29 | RAG 评测范围同时覆盖工具能力、权限、隐私、过期、冲突与提示注入；人工审核是事实权威，盲审 LLM Judge 只能在与人工校准后辅助。已生成 34 开发题、18 挑战题、20 流程型隐藏题的 v2 材料。 | 评测范围已冻结；题干、答案键、人审人数、Judge 与阈值待产品负责人审核 | 防止仅用一个命中率或一个平均分掩盖越权工具调用；检索、融合/路由、最终解释分层评估。 | 审核 v2；将答案键移出开发工作区后才可做真正盲测。 |
| D-PROD-050 | 2026-08-29 | 为补齐眼睛、嘴巴、鼻子、眉毛、耳朵、脸型细分和逐图批量一致性，选择“参数级人像美化 SDK/API”扩展路线；维持单人、本人/成年/授权、同一身份、局部几何、每图独立计划、最多三轮和按 Provider 单独授权。 | 方向已冻结；具体 Provider 未冻结/未接入 | RAG 可以发现候选能力，但只能进入 Candidate Card；静态图片 API 与现有 Python/批量链路耦合更低，SDK 的细项和端侧隐私优势需另验 License/前端代价。 | 优先完成火山美颜 API V2.0 静态/批量 Spike 的准入研究，并并行核验腾讯特效 Web SDK；不因研究资料新增执行能力。 |
| D-PROD-051 | 2026-08-29 | external/hybrid 复测选择“本地几何主证据 + CompareFace 仅同人辅助 guard”。CompareFace 不能证明五官/脸型已接近母版，不能单独关闭任务。 | 产品方向已冻结；Adapter/真实回执未实现 | 避免将身份分数错当成一致性验收；RAG 仅可提议策略，状态机/权限/Adapter 才能放行。 | 新 Adapter 需完成出站、成本、Policy、smoke 和回归 Gate。 |
| D-PROD-052 | 2026-08-29 | 保留 SQLite/Trace 为 RAG 权威账本，并现在实现只读本机 RAG 治理 Dashboard。页面只展示审核知识、生命周期、检索/建议路由、bad case、复审提醒、派生索引状态和最近脱敏记录。 | 已冻结并实现 | 让产品负责人能审计知识与故障分布，同时不开放照片、原话、source body、向量、密钥或执行按钮。 | 自动 worker、指标告警、Gold 聚合和部署级管理员鉴权另开 Gate。 |
| D-TECH-040 | 2026-08-29 | 实现 `LocalKnowledgeStore.rag_dashboard_snapshot` / `knowledge_catalog` 与 `pages/4_RAG治理看板.py`；新增 Dashboard 安全聚合测试。 | 已实现并本地页面验证 | `107 passed, 4 warnings`、Ruff、compileall、RAG advisory smoke、diff check 均通过；页面加载且无控制台页面错误。只读现有知识账本，不改六合同、不读照片/原话、不调 LLM/Tencent/API。 | 不能据此称 RAG Gold 通过、生产监控、自动 worker 或用户测试完成。 |
| D-PROD-053 | 2026-08-30 | 冻结 RAG Gold Set v2：34 道开发题、18 道挑战题、20 道隐藏题；同时覆盖工具能力、权限、隐私、生命周期、冲突和提示注入。安全类题要求 100% 正确拦截、0 次错误工具放行；检索/路由门槛为 Recall@5≥90%、Precision@3≥80%、MRR≥80%、nDCG@5≥85%、路由/证据关系正确率≥90%；未来生成解释的 Faithfulness≥95%、人审—Judge 一致率≥80%、Hidden—Dev 差距≤10 个百分点。 | 已冻结；运行器/盲审正在开发，未用于调参或训练 | 把“平均分不错”与“不能越权”分开，指标可定位检索、路由和解释问题；小样本必须同时报告题量和错误清单 | 产品负责人逐题审核 Gold evidence/route；答案键移出开发者可读工作区后运行真正 hidden 测试 |
| D-PROD-054 | 2026-08-30 | Gold 评审采用产品负责人作为唯一人工事实审核者，暂不增加第二位人工评审；盲审 LLM Judge 可看到本次运行的机器分数/指标摘要，但不可看到 Gold 答案、答案键、开发标签或实现版本，只辅助检查证据充分性、解释忠实度和路由理由 | 已冻结；Judge 接口/运行器正在开发 | 保留产品负责人最终裁决，避免模型自评替代事实审核；分数可帮助 Judge 定位异常但不构成答案标签 | Judge 与人工一致率达门槛前只能做辅助错误发现 |
| D-PROD-055 | 2026-08-30 | 新增能力选择参数级人像美化 SDK/API 路线，并行推进火山美颜 API V2.0 静态/批量候选与腾讯特效 SDK 细粒度参数候选；两者都必须走 Card→Adapter→权限/预算→live smoke/receipt→Gold 回归→产品负责人冻结→`reviewed_active`，RAG 只能提议不能授权 | 已冻结路线；具体能力、License、价格、区域、留存和真实回执待验证 | 可用同一准入标准比较能力上限与工程成本，不因宣传资料或 RAG 命中就向用户发送照片 | 先完成两条 Card/Adapter shell 的离线 Gate，再决定哪条进入真实图片 Spike |

| D-TECH-041 | 2026-08-30 | 按 D-PROD-053/054 实现独立 Gold Set v2 离线评测器：public/annotations/holdout 分离，计算检索/路由/证据/安全指标；冻结阈值逐项 Gate，缺 predictions 显示 `PENDING`，不把空结果当 0 分 | **（当时）**已实现并通过 8 条评测器测试；public 52 题尚未生成 predictions，holdout 20 题仅输入包 | 让产品负责人能复盘每层错误，同时防止平均分掩盖越权；评测器不读照片、不调用 LLM/Provider、不读取 hidden 答案 | 后续已生成 public/holdout predictions 并完成私有 aggregate 评分；当前结果以 D-TECH-046 与后续收口记录为准 |
| D-PROD-056 | 2026-08-30 | 产品负责人确认采用确定性 public 基线后再接 LLM 盲审；隐藏答案键移至产品负责人本机 Documents 的项目工作区之外，并以最小权限保存。运行器只接收无答案 holdout 包，评测后仅回流聚合分数和错误类型。续跑提醒全部取消。 | 已冻结并执行；public predictions/holdout 运行进行中 | 将评测答案与被测系统物理分离，保留可复核但不泄漏答案的流程；避免自动续跑在未决 Gate 中继续改动 | 运行 public baseline 与 holdout；由产品负责人私有比对后决定是否进入 LLM Judge |
| D-TECH-045 | 2026-08-30 | 使用产品负责人明确授权的内部单人照片完成当前腾讯既有链路真实 Smoke：IMS `Pass` 后，BeautifyPic 以瘦脸/大眼各 5、美白/磨皮 0 成功执行；只保存脱敏哈希、RequestId、耗时和内存生命周期引用 | 已真实回执；单样本内部 Smoke | 证明已接入腾讯能力的安全允许路径与一次参数级编辑可工作，同时不将结果图或原图落盘 | 继续以母版/目标两图跑完整 UI 闭环；新 Provider 仍按独立准入 Gate，不因该回执升级 |
| D-TECH-042 | 2026-08-30 | 盲审 Judge 只接收题干、系统输出和从真实预测派生的安全机器摘要；不接收 Gold、开发标签、实现版本、原图、向量、密钥；当前仅提供本地 fake Judge，live adapter 默认禁用 | 已实现输入/输出合同与隔离测试；未进行真实 LLM Judge | 保留产品负责人事实权威，机器只辅助发现结构/忠实度问题，不改变工具权限 | 取得产品负责人审核样本、数据出境/预算/留存同意并实现独立 live adapter 后再评估一致率 |
| D-TECH-043 | 2026-08-30 | 按 D-PROD-055 并行建立火山美颜 API V2.0 与腾讯特效 SDK 的 candidate Card、typed Adapter shell、权限/预算 preflight、离线测试和 smoke；候选始终 fail-closed，未通过完整准入链不得图片出站 | 已实现；Volc smoke=`not_run`、Tencent Effect smoke=`blocked`，均 `network_call=not_attempted` | 先验证系统耦合和安全边界，再决定真实供应商；不因 RAG 命中或宣传资料扩大能力 | 供应商书面能力/License/隐私/区域/价格/延迟、真实 receipt、Gold 回归和产品负责人冻结 |
| D-TECH-044 | 2026-08-30 | 全量文档/代码/测试一致性收口：PRD 矩阵、RAG Gate、Provider 专项、规则/合同/Prompt、进展/决策、README 均记录当前真实状态；生成 answerless HTML/Markdown/JSON 报告，不把 pending 说成通过 | 已完成；`pytest 129 passed, 4 warnings`，Ruff/compileall/diff check 通过 | 下次续跑可从同一事实状态恢复，避免文档把 candidate 或离线 smoke 夸成线上能力 | 每次下一轮变更继续运行同一六项一致性检查 |

## 2026-08-30 追加记录｜RAG failure-pattern、自校正候选与优化看板

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-058 | 2026-08-30 | 产品负责人批准建立数据驱动的 RAG failure-pattern / SOP 闭环：同时看公开逐题事实与隐藏仅聚合错误类型；不读取隐藏答案逐题调参。自校正一次只提出一个可解释候选，先公开安全回归，再由产品负责人批准或回滚。 | 已冻结并实现 | 让“为什么错—改什么—是否回退”可追溯，同时保持 RAG 只能提议、权限和 Provider 准入不被自动改变。 | 下一轮由产品负责人决定是否把某个候选升级为现役规则；指标口径和独立 holdout 仍需单独 Gate。 |
| D-TECH-050 | 2026-08-30 | 实现 `rag_failure_analysis-v0.1`、`rag-correction-candidate-v0.1`、显式 `RagReportArtifact` allow-list、page 4 报告集合和 page 5 RAG 优化看板。候选只做审核过的中英/领域同义词归一化；公开回归无指标回退，`active_baseline_changed=false`，project Gate 仍 `FAIL`。 | 已实现并本地验证 | 输出脱敏 JSON/HTML、指标差值、错误类型、Trace 聚合和六步 SOP；不读照片、向量、原始用户文本、隐藏题干/答案键，不调用 LLM/Provider/网络。 | 真实部署级鉴权、自动 worker、新 Provider、LLM Judge 与 hidden hard-safety canonical event 仍需后续 Gate。 |

| D-TECH-051 | 2026-08-30 | 本轮交叉检验收口：重跑 failure analyzer，刷新 failure-pattern JSON/HTML；page 4 报告集合与 page 5 RAG 优化看板均实际加载；全量 `pytest`、Ruff、compileall、`git diff --check` 全部通过。 | 已完成 | 当前真实状态为 `pytest 144 passed, 4 warnings`；public/private aggregate project Gate 均为 `FAIL`；候选 `rag-correction-candidate-v0.1` 保持 proposal-only，未改变现役 baseline、权限、Provider 或阈值。 | 下一产品门仍是稀疏 Precision 口径、独立 holdout 生命周期、private hard-safety canonical event ID 与候选 Provider 正式准入。 |

| D-TECH-052 | 2026-08-30 | 评测可追溯性修正：核对时触发了“不传 predictions 即生成 pending”安全默认；已用 public answerless predictions 重新写回 `complete` 报告并确认 52/52 predictions。该默认保留，防止空输入被误报为 0 分；正式质量报告必须显式提供 predictions。 | 已完成 | 当前 public 报告为 complete，Route/Recall@5/MRR/nDCG@5 等保持 100%，固定分母 Precision@3=47.44%，project Gate 仍 `FAIL`；未改变知识、权限或 Provider 行为。 | 后续脚本/看板应优先读取正式 baseline 报告，pending 仅作为无输入提示。 |

| D-TECH-053 | 2026-08-30 | 供应商控制台现场证据：腾讯 Web License 页已打开到“新建测试版 License”表单，正式/测试 License 均为 0，表单要求项目名+精确域名/AppId，测试期 14 天、可续 1 次至 28 天；火山控制台已打开到 IAM/API Key 登录页但未登录。 | 已核验入口；未提交/未联网调用候选 Provider | 阻断点从“找不到入口”明确为“腾讯需匹配域名/平台 License，火山需账号/服务/API Key/权限”；不读取密钥、不发送照片、不把候选升级为可执行。 | 产品负责人提交腾讯测试 License 或完成火山登录后，继续 Card→Adapter→权限/预算→live receipt→Gold 回归→冻结。 |

## 2026-08-30 追加记录｜隐藏集私有聚合与候选 Provider 官方证据核验

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-TECH-046 | 2026-08-30 | 按已冻结的隔离流程，确定性 runner 先生成 public 52 题与 answerless holdout 20 题 predictions；产品负责人工作区外的私有 Markdown key 仅在本机内存解析。新增 aggregate-only scorer/HTML：不输出题目、case ID、Gold、私有路径、原始文本或图片；不调用 LLM/Provider/网络。 | 已实现并实际运行 | public：Precision@3=47.44%、Gate=`FAIL`；private holdout：Route=25.00%、Recall@5=38.24%、MRR=52.94%、nDCG@5=41.56%、Gate=`FAIL`。当前不能称 RAG 通过或泛化有效。 | 先冻结稀疏 Gold 的 Precision 定义、下一份独立 holdout 与 private safety key 的机评格式；禁止用本份 hidden 逐题答案调参。 |
| D-PROD-057 | 2026-08-30 | 产品负责人确认隐藏答案键保留在本机 Documents 的项目工作区外受限目录；只回流聚合指标/错误类型。当前 hidden 结果用作泛化诊断，不作为规则补丁的监督信号；所有续跑提醒取消。 | 已冻结并执行 | 保住 holdout 的流程独立性，且把“公开集看起来很好、隐藏集失败”记录为真实产品设计证据，而不是通过调参掩盖。 | 产品负责人决定 holdout 退役/新建策略和安全禁项 canonical event ID 前，不进入 LLM Judge、自动 worker或工具权限扩张。 |
| D-TECH-047 | 2026-08-30 | 并行核验两条 candidate Provider 的官方一手证据。火山 V2 证实异步静态图 submit/task/query/result 链及部分脸型/眼睛/鼻部能力，但未证实唇厚、鼻翼、眼距/眼宽高、眉毛、耳朵与完整隐私/成本/地区；腾讯特效证实 Web 静态图处理和移动/PC S 细项分别存在，但未证实细项可在 Web 单图表面调用。 | 已完成证据 Spike；两者仍 `candidate` | 不能将两个产品表面的能力拼写成一个本项目已接入 API；Card/Adapter 均继续 fail-closed、无图片出站。 | 只有补齐 License、隐私/地区、预算、实际 schema、真实 receipt、Gold 回归和产品负责人冻结后，才考虑 `reviewed_active`。 |
| D-TECH-048 | 2026-08-30 | 对产品负责人明确授权的内部单人照片完成既有 Tencent IMS `Pass` 与 BeautifyPic 单次参数级 Smoke；结果图只在内存，落库仅为脱敏 hash/RequestId/耗时。 | 已实际完成 | 更新已有 Tencent 执行基线的单样本回执，不影响候选 Provider 准入，也不证明母版一致性视觉效果或用户满意。 | 真实母版/目标照片端到端 UI、三轮视觉复测和用户反馈仍是后续独立 Gate。 |

| D-TECH-049 | 2026-08-30 | 本轮最终交叉检验：P0-A/P0-B/P0-C 与两个候选 Provider smoke 可重放；全量 `pytest` 为 `138 passed, 4 warnings`，Ruff、compileall、`git diff --check` 通过；文档、合同、代码、测试和真实回执均保持当前能力边界。 | 已完成 | 确保下一次续跑可从同一事实状态恢复；候选 Provider 继续 fail-closed，RAG 继续只能提议，Gold project Gate 继续为 `FAIL`。 | 下一产品 Gate 由产品负责人决定稀疏 Precision 定义、holdout 生命周期、private `must_not` 的 canonical event ID；冻结前不调隐藏集、不扩大工具权限。 |

## 2026-08-30 追加记录｜Precision、Holdout 与安全事件 ID 冻结

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-059 | 2026-08-30 | 产品负责人冻结 Precision 方案 C：固定分母 Precision 保留用于历史 Gate；新增覆盖式（命中数 / `min(K, Gold 条数)`）与返回式（命中数 / 实际返回条数）并行报告，并按 Gold 证据条数分层。 | 已冻结并实现 | 公开报告同时显示三种口径；不因覆盖式 100% 把固定 Gate 的 `FAIL` 改成 `PASS`。 | 若未来要改发布 Gate，需另开产品决策，不由 evaluator/LLM 自动改写。 |
| D-PROD-060 | 2026-08-30 | 产品负责人冻结 Holdout A：v2 H01–H20 及 aggregate 只作历史泛化诊断；创建 v3 answerless 独立模板，题目/答案由产品负责人在工作区外独立生成和保管，正式验收最多一次。 | 已冻结并实现 | 防止 hidden 逐题答案污染规则；模板为空不代表 v3 完成或通过。 | 待产品负责人生成/审核 v3 题目和 machine-normalized 答案键。 |
| D-PROD-061 | 2026-08-30 | 产品负责人冻结 Safety ID C：使用版本化确定性字典 + 产品负责人确认；已知 legacy label 映射 `RAG_EVT_*`，未知标签不猜并进入 `MANUAL_REVIEW_REQUIRED`。 | 已冻结并实现 | public 可自动复测，私有旧 Markdown 仍人工复核；不放宽 RAG/Provider/图片权限。 | 待产品负责人确认公开目录并在 v3/私有 key 迁移时复核新增事件。 |
| D-TECH-054 | 2026-08-30 | 实现 `rag_gold_eval-v0.2`、`rag-safety-events-v0.1`、v3 holdout template/custody 文档、private aggregate/failure analyzer/page 5 dual-metric 展示；public predictions、evaluation、failure report 已显式重跑。 | 已完成 | 146 项测试基线扩展为双口径和未知事件安全路由；网络/LLM/Provider/照片边界不变。 | 下一门为 owner 审核 canonical catalog、生成 v3、候选 Provider 正式证据。 |

| D-TECH-055 | 2026-08-30 | 评测治理冻结后的最终复核：重新生成 public answerless predictions/evaluation 与 failure-pattern JSON/HTML；修正分析报告中的候选名称，使 `self_correction.current_candidate` 与 `rag-correction-candidate-v0.1` 版本一致；重跑 P0-A/P0-B/P0-C 与两个候选 Provider fail-closed smoke。 | 已完成 | `pytest 146 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 均通过。public 报告 52/52 complete，固定/覆盖式/返回式 Precision@3=`47.44%/100%/100%`，project Gate=`FAIL`；failure analyzer `private_answer_key_read=false`、`network_called=false`、candidate regression=`PASS` 但未推广。 | v2 hidden 仍只作历史 aggregate；v3 模板仍为空；下一门为产品负责人审核 canonical 目录、生成/保管 v3 答案键，以及候选 Provider 的 License/隐私/预算/真实 receipt/Gold 准入。 |

## 2026-08-30 追加记录｜部署包与火山候选准入收口

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-062 | 2026-08-30 | 为拿到可分享演示 URL，采用私有 GitHub 仓库 + Streamlit Community Cloud Private/受邀 Beta；只发布可部署代码、审核过的 Provider Card、测试和产品文档，不发布 `.env`、照片/结果图、SQLite/JSONL、模型缓存、隐藏答案或本机评测报告。 | 已冻结并实现；私有 GitHub 仓库已创建并推送 `main`；Cloud 控制台仍待用户创建 App | 保持代码可迭代、可回滚和可泛化，同时避免把本机运行账本误当成云端生产存储；URL 由 Streamlit 控制台最终分配，不能预先保证某个 slug | 用户在 Cloud 选择仓库/分支/入口并配置 Secrets 后，再核验 URL、访问名单、区域、费用与真实照片授权；部署前不宣称公网服务 |
| D-PROD-063 | 2026-08-30 | 火山美颜 API V2 暂不进入 V0：官方资料明确要求购买支持后付费 API 的创点套餐；公开资料未给出个人免费试用额度或 API 按次价格，SDK 年度套餐公开价从 6 万元起且不等同 V2 API 价格。V0 只使用已真实验证的腾讯链路；火山仍保留为未来 Candidate Card，不采购、不配置 Key、不发送照片。 | 已冻结；未来重开需书面价格/试用、License、隐私/地区和真实 schema 证据 | 预算和准入风险不阻塞 9 月 4 日 Demo；RAG 不能因命中火山资料而授权调用 | 仅在获得低成本试用或明确采购批准后，重走 Card→Adapter→权限/预算→live receipt→Gold 回归→负责人冻结 |
| D-TECH-056 | 2026-08-30 | 为 Community Cloud root entrypoint 增加 `src/` 兼容引导；移除云端不应继承的本机 bind 配置；将 `torch/transformers` 移为可选 `rag-local` extra，缺失模型时沿用 P0-A 关键词回退；`.gitignore` 明确排除本机照片、账本、报告和 hidden 材料；新增 `docs/STREAMLIT_DEPLOYMENT.md`。 | 已实现；146 tests、Ruff、format、compileall、diff check 和 Streamlit HTTP 200 探针通过；私有仓库已推送 | 同一 `app.py` 可在本机 `make run` 和 Cloud 直接执行；轻量部署不改变 RAG 只能提议和候选 Provider fail-closed 边界 | Cloud App 创建后继续核对启动日志、Secrets、私有访问、资源/费用和数据出境边界 |
| D-TECH-057 | 2026-08-30 | Streamlit Cloud Private App 已由产品负责人创建，URL 为 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`；只读 HTTP 探针返回 Streamlit 登录跳转。腾讯 Web License 测试表单现场验证：完整 URL 会禁用提交，纯主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app` 可用；尚未点击“确定”提交 License。 | 已核验；应用仍 Private，License 未提交 | 解决“128 字节/精准域名”输入误区；不把 Private URL 写成公网服务，不把表单可提交写成 License 已签发 | 产品负责人确认后提交测试 License；若服务端仍拒绝，再评估自有域名/反向代理或 localhost Spike，不购买正式套餐 |

| D-PROD-064 | 2026-08-30 | 产品负责人审核通过 `rag-safety-events-v0.1` 公开 canonical Safety Event 目录；已知 legacy label/`RAG_EVT_*` 确定性映射，未知标签继续 `MANUAL_REVIEW_REQUIRED`。 | 已确认并同步 | 公开评测可使用稳定机器事件 ID；不改变 RAG `execution_authorized=false`、Provider 白名单或图片出站权限 | 新增事件必须版本化、人工审核并跑公开安全回归 |
| D-PROD-065 | 2026-08-30 | 按 Holdout A 在项目工作区外生成 v3 Holdout 产品负责人审核草案：36 道独立重写题目、分离答案键和逐题审核表；状态为 `OWNER_REVIEW_DRAFT`，不被 evaluator/应用读取。 | 已生成；待产品负责人逐题审核 | 保持答案隔离和可回滚；正式 runtime 只能接 `case_id + query`，不能把草案写成 RAG 通过 | 产品负责人审核后再导出正式 answerless runtime；正式评分最多一次，禁止用其逐题调参 |
| D-TECH-058 | 2026-08-30 | 腾讯 Web 测试 License 已在控制台创建并显示“正常”，绑定精确主机名 `portrait-consistency-agent-x7cqcqsucatfbk7mmzch3q.streamlit.app`，有效期显示为 2026-08-30 至 2026-09-13。License Key/Token 不写入仓库、Trace、报告或回复。 | 已有外部控制台回执 | Cloud Web License 资源状态已闭合；不等于公网开放、生产合规或新 Provider 准入 | 到期/续期、访问名单、Secrets 和真实照片跨境授权仍按部署 Gate 另行核验 |

| D-PROD-066 | 2026-08-30 | 为结束 RAG 本地工程并保持可追溯，产品负责人冻结“生命周期审计先于知识更新”：审计只读取审核 Card/Policy 元数据、原子规则计数和派生 manifest；过期/撤回/冲突阻断检索，未生效/候选未发布保持 hold，需复审/缺 URI/零规则进入人工复核；不自动发布、改状态、删除或重建索引。 | 已冻结并实现 | 把知识时效、撤回、冲突和索引落后从检索质量问题中分离出来；RAG 继续 advisory-only，`execution_authorized=false` | 后续若做定时 worker、PostgreSQL/对象存储或知识自动同步，必须另开产品 Gate |
| D-TECH-059 | 2026-08-30 | 实现 `RagLifecycleItemAudit`、`RagIndexAudit`、`RagLifecycleAudit` 合同；SQLite 审计账本；dense manifest 快照；`services/rag_lifecycle.py`、`scripts/audit_rag_lifecycle.py`；page 4 生命周期审计入口；allow-listed HTML 报告；4 条生命周期测试。当前 3 张审核 Tencent Card/10 条 active chunks 审计为 `complete`、无 issue、index=`in_sync`。 | 已实现并本地验证 | 形成可重放的 metadata-only audit、trace、JSON/HTML/dashboard 闭环；不读取照片、原文、向量、答案键、密钥，不联网、不调用 LLM/Provider，不改变 active baseline | 继续用全量 RAG 回归和文档一致性检查；外部/生产 Gate 不由本模块自动推进 |

## 2026-09-01 追加记录｜v3 Holdout 正式盲测与第一位用户入口

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-070 | 2026-09-01 | 产品负责人完成 v3 Holdout 36 题逐题审核，并确认按 Holdout A 只用 answerless `case_id + query` 做一次正式验收；答案键继续在工作区外受限保管，不回流应用、Prompt、检索器或调参。 | 已冻结并执行 | 质量证据与开发资料隔离，避免把 hidden 逐题结果过拟合成规则；后续若需再次验收必须新建独立 Holdout | 继续保留本次 aggregate 作为一次性证据；不得读取逐题答案调参 |
| D-TECH-060 | 2026-09-01 | v3 deterministic runner/scorer 完成一次私有聚合盲测：36/36 predictions，无答案键、照片、向量、LLM、Provider、网络读取；Route=30.56%、Recall@5=59.72%、MRR=77.78%、nDCG@5=63.81%、evidence relation=23.61%，hard-safety=0/36，project quality Gate=`FAIL`。 | 已完成并留证 | 明确暴露当前 baseline 的检索/证据关系/路由泛化问题，同时证明 canonical safety 目录的拦截路径；不能写成 RAG 质量通过 | 只在 public/dev/challenge 上修正；需要再验收时另建 Holdout |
| D-PROD-071 | 2026-09-01 | 第一位用户测试采用“产品负责人亲自操作 Private Streamlit 页面”的证据规则；Codex 只打开页面和提供新手指引，不代上传照片、不代点击外部图片调用。 | 已冻结；页面已打开，真实操作待完成 | 防止把 fixture、页面加载或 Codex 代跑误写成用户效果；真实 UI 8C 多轮回执必须由页面实际产生 | 用户完成后记录脱敏事件、ProviderRun、VerificationResult、反馈和 Dashboard 快照 |

## 2026-08-30 追加记录｜视觉与 Agent 交互结构冻结（历史配色，已由 2026-09-02 覆盖）

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-067 | 2026-08-30 | 产品负责人冻结“中心舞台式首页／对齐工作台 + 母版档案 + 结果记录”的三空间交互结构。新用户只从“建立我的母版”或“我已有母版，开始本次对齐”进入；母版是长期记忆锚点，当前照片与本次意图占中心。Agent 只在澄清、真实进度、边界与结果时发声；参数、依据、Provider 回执和脱敏 Trace 是第二层，隐藏思维链永不展示。结果页承担前后对比、下载、点赞／点踩和继续说明。 | 已冻结；实现待色彩决策后进入 UI Gate | 让 Agent 的智能体现在连续任务旅程而非聊天框或滑杆；视觉动效只能表达真实状态，不改变当前 consent、Provider、RAG advisory、保存和审计边界。 | 产品负责人从两条可视化色彩探索中冻结最终色彩系统；随后逐项验收母版、上传、错误、同意、执行、结果和反馈可见性与可达性，才可改 Streamlit UI。 |
| D-PROD-068 | 2026-08-30 | 产品负责人选择参考图的“雾灰紫情绪场 + 奶油桃中央舞台 + 墨黑导航 + 单一强调色”层次语法为唯一视觉基线，并要求进一步收束为 3—5 个主色、短标题／短按钮、低装饰密度和显著自然语言 Agent 输入框。摄影背景、原站资产、长段说明、彩色堆叠及喧宾夺主的装饰不进入产品 UI。 | 已冻结视觉原则；最终强调色待选 | 将艺术感转为可快速开始的 Agent 工作台，保留 Demo 视觉张力但不牺牲任务清晰度、真实状态与第二层证据可见性。 | 产品负责人从雾紫珊瑚、宝蓝珊瑚、墨黑蜜桃三组中选定最终色彩后，再进入 UI 视觉实现与可达性复核 Gate。 |
| D-PROD-069 | 2026-08-30 | 产品负责人确认主色为雾紫、肉粉／奶油粉、墨黑与桃红，不引入其他颜色家族；并要求参考自有 BOOBOO App 的“单一当前任务 + 有限入口 + 即时状态”简洁性，以奥卡姆剃刀将本产品首屏收束为一个上传动作和一个显著自然语言 Agent 输入框。BOOBOO 的配色、素材、内容和多卡片仪表盘不迁移。 | 色彩与简洁原则已冻结；页面候选待审核 | 降低学习成本，把视觉重心还给 Agent 任务，而不是装饰、文字或仪表盘。 | 产品负责人审核低实体页面样张；通过后才改 Streamlit，并复核同意、错误、工具状态、结果、反馈和第二层证据可见性。 |

| D-TECH-061 | 2026-09-01 | 第一位用户入口只读检查发现侧边栏把 Cloud 页面写成“仅本机服务器”，容易让受邀测试者误解运行环境；将文案改为“运行环境：Private Demo；本机开发端口为 `127.0.0.1:8501`”。 | 已实现并已由 Cloud 重建显示 | 只修正文案，不改变合同、权限、Provider、RAG、Trace 或照片数据流；避免把部署入口误写成 localhost。 | 页面已完成只读核对；真实照片流程仍由产品负责人亲自触发。 |

| D-TECH-062 | 2026-09-01 | 第一位用户在 Cloud 页面触发 ImageModeration 前被 `TENCENT_SECRET_ID/KEY` 缺失门阻断。确认原因是 Cloud App 没有根级 Secrets（本机 `.env` 不会随 GitHub/Cloud 部署）；代码提示已改为同时指向本机 `.env` 与 Cloud App Settings → Secrets。 | 已实现并推送；等待产品负责人手动配置 Cloud Secrets | 配置成对的根级变量并重启 App 后，才允许真实 IMS/CompareFace/BeautifyPic 请求；不改变既有 IAM、授权、Provider 白名单或数据边界。 | 产品负责人配置后重跑一次 IMS 安全检查；若变成 `Unauthorized`，再按腾讯 CAM 策略排查。 |
| D-TECH-063 | 2026-09-01 | 第一位用户配置 Cloud Secrets 后，ImageModeration 进入真实请求但页面只给出泛化失败文案；新增安全错误回执投影，页面与脱敏 Trace 同时保留 `error_code`、`provider_request_id` 和异常类型，不保留腾讯原始错误全文、图片或密钥。 | 已实现并待 Cloud 重建验证 | 让产品负责人可以用真实腾讯错误码定位 IAM/服务/参数/网络问题，同时继续 fail closed；不自动重试、不改变 Pass/Review/Block 路由和图片数据边界。 | 产品负责人刷新 Cloud 后再次执行内容安全检查；根据真实 `error_code` 决定下一项腾讯配置修复。 |

## 2026-09-01 追加记录｜v3 失败模式驱动的 RAG 自动优化闭环

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-072 | 2026-09-01 | 产品负责人要求把 v3 的 `evidence_relation_mismatch`、`evidence_set_mismatch`、`route_mismatch` 转成逐题 public 诊断、SOP、候选迭代、反过拟合和边际效益停止闭环；同时确认同一 v3 不得再跑、逐题答案不回流。 | 已冻结并实现 | 失败分析成为可回放的产品质量机制，而不是事后文字说明；v3 只保留 aggregate，上线权限与 RAG advisory-only 边界不变。 | 新增独立 Holdout v4 后再做正式泛化验收。 |
| D-TECH-064 | 2026-09-01 | 实现 `rag-optimization-loop-v0.1` 与 `RAG_OPTIMIZATION_RUBRIC.md`：V0 baseline、V1 同义词归一化、V2 relation canonical 化已运行；连续两代 Composite 增益均为 0.0（小于 0.01），V3 evidence packing/V4 route guard 按停止规则跳过。 | 已完成并本地验证 | public 52 题逐题诊断已生成；Composite=`0.947436` 仅作比较分，project Gate 仍 `FAIL`；候选不改变 active baseline、Provider、权限、参数或 hidden 数据。 | 有新的人工审核数据时，一次只改一个候选并重新跑 dev/challenge；不得读取 v3 逐题答案。 |
| D-TECH-065 | 2026-09-01 | 新增 `reports/rag_optimization_loop_v1.json/.html`、page 5 代际曲线/逐题诊断/反过拟合展示与报告 allow-list；本轮候选 Trace 均 `network=false`、`provider=false`、`llm=false`、`hidden_answer_key_read=false`，anti-overfit=`PASS`。 | 已完成 | 形成“baseline→诊断→候选→回归→停止→人工批准/回滚”的可观测 Dashboard；不会把公开高分或隐藏安全通过写成 RAG 质量通过。 | 继续保持文档、代码、测试和报告版本同步；新 Holdout v4 才能改变泛化结论。 |

## 2026-09-01 追加记录｜第一位真实用户 8A 阻塞修复与体验反馈

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-073 | 2026-09-01 | 第一位用户真实运行完成母版/目标照 IMS Pass、Profile 建立和 CompareFace；目标照原始分 `56.231842041015625` 路由为 `uncertain`，旧页面因没有本人/编辑权确认入口而在 8A 阻断。用户同时反馈上传等待过长、首屏展示脱敏 JSON、A/B/C 检查点和按钮过多、自然语言入口被 GUI 挤压、整体偏工程文档。 | 已记录；UX 改造待产品 Gate | 将“真实安全阻塞”和“交互摩擦”拆成两类问题；不把一次用户反馈写成普遍 KPI，不为减少点击擅自删除权限门 | 先完成当前真实闭环，再按耗时证据和 UI 需求文档冻结改版范围 |
| D-TECH-066 | 2026-09-01 | 为兑现既有规则“`uncertain` 经本人且有权编辑确认后可在当前会话降级继续”，新增可选 `ConfirmationScope.subject_match_uncertain_acknowledged`、页面一次性确认、规划器/执行器双重校验、事件 Trace 和 `contract_v0_4_subject_uncertain_ack` migration marker；不改 `subject_match_status`，不更新长期锚点，`no_match` 仍硬拒绝。 | 已实现；等待 Cloud 重建 | 8A/8B/8C 获得最小、可追溯的继续路径；RAG 仍 `execution_authorized=false`；新增测试覆盖未确认阻断与确认后有界执行 | Cloud 重建后由产品负责人亲自刷新、勾选并继续；产生真实 ProviderRun/VerificationResult 后再关闭首轮 Gate |
| D-PROD-074 | 2026-09-01 | 第一位用户测试不以 8A 暂停结束；继续条件为：用户确认本人/编辑权、当前照片与 Profile/质量/安全事实未变、计划仍在有效 scope 内。完成真实 8B/8C 后，才记录“端到端完成”；在此之前不得声称视觉改善、用户满意或修图有效。 | 已冻结 | 保留隐私与用户控制，同时避免把工程页面缺少入口误判为产品不可用；下一 UI Gate 只调整呈现与编排，不改变安全/授权/Trace 不变量 | 真实流程完成后查看 ProviderRun、VerificationResult、反馈事件和 Dashboard 快照 |

| D-PROD-075 | 2026-09-01 | 产品负责人确认 v3 的 `evidence_relation_mismatch`、`evidence_set_mismatch`、`route_mismatch` 只能以 aggregate pattern 回流；报告必须把“聚合观察事实、可验证假设、下一份独立 Holdout 需要的逐题证据”分开，并明确三类计数可重叠，不能据此写 case-specific 规则。 | 已冻结并同步 | 让 failure analysis 真正服务于数据集设计，同时避免把未知根因包装成算法结论；RAG 继续 proposal-only。 | 新建 Holdout v4 时补齐 canonical relation、evidence set、route、槽位与冲突标志的逐题字段。 |
| D-TECH-067 | 2026-09-01 | 扩展 `rag_optimization_loop-v0.1` 报告合同：新增 `private_pattern_interpretations` 与 `private_pattern_counts_non_additive`；HTML 和 page 5 同步展示事实/假设/下一证据，重新生成 optimization JSON/HTML。 | 已实现并本地验证 | v3 聚合信息可解释、可审计，但不会泄漏题干/答案键或改变现役检索、权限和 Provider。 | 新 Holdout v4 通过后再验证这些假设；本轮不重跑 v3。 |
| D-TECH-068 | 2026-09-01 | 完成优化 Loop 后的首次最终交叉校验：全量 `pytest 158 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check`、P0-A/P0-B/RAG advisory/lifecycle/8C/8C2 smoke 全部通过。 | 已完成；后续发现账本幂等边界并由 D-TECH-069 修正 | 当前工作区的优化代码、报告、看板、SOP、Rubric 与执行版 PRD 口径一致；4 条 warning 仍为既有 Pillow 弃用提示。 | 以 D-TECH-069 的 160 passed 作为当前最终校验；下一质量证据必须来自新的独立 Holdout v4；真实 UI 8C 仍需产品负责人亲自完成。 |
| D-TECH-069 | 2026-09-01 | 修复 `LocalTraceStore._insert_session_contract` 的幂等冲突边界：除完整上下文外，按真实 SQLite 唯一键预检质量结果 ID、计划 ID+revision、验证 ID；相同投影复用，变化投影统一抛出 `ValueError`，避免泄漏底层 `sqlite3.IntegrityError`。新增 `photo_id` 变化回归测试，并完成全量交叉校验。 | 已实现并验证；当前最终校验为 `pytest 160 passed, 4 warnings` | Streamlit 重放或异常上下文不覆盖既有证据；错误可以被上层稳定识别；不改变任何 Provider/RAG/图片执行权限。Ruff、format、compileall、`git diff --check`、P0-A/P0-B/RAG advisory/lifecycle/8C/8C2 smoke 与优化 Loop 均通过。 | RAG quality Gate 仍为 `FAIL`；下一质量证据必须来自独立 Holdout v4，真实 UI 多轮照片回执仍待产品负责人。 |

## 2026-09-01 追加记录｜Cloud ImageModeration 页面失败的根因与幂等修复

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-TECH-070 | 2026-09-01 | Cloud 页面出现 `Tencent ImageModeration request failed` 后，检查运行日志发现可重复根因是 Streamlit 重跑时重复插入同一 `photo_quality_result_id`，SQLite 报 `UNIQUE constraint failed`；本机同类授权照片的真实 IMS smoke 已返回 `Pass`（RequestId `c95e1359-9ecb-45ac-aa94-3776fbccc0ad`），因此不把页面泛化提示误判为密钥失效。 | 根因已定位；修复已实现并通过本地验证 | `LocalTraceStore` 对质量/计划/验证合同按唯一键和完整上下文做幂等复用；内容变化则 fail closed；不覆盖审计事实、不重复完成事件、不绕过 IMS、不自动重试。 | Cloud 拉取新提交后，产品负责人刷新并重新执行一次 IMS；若仍失败，只回传脱敏 `error_code` + `RequestId`。 |
| D-PROD-076 | 2026-09-01 | 用户可见的安全错误继续只显示腾讯 `error_code`、`RequestId` 和简短错误类型；重复写入修复只改善页面稳定性，不能将任何 Cloud 请求自动视为安全通过。 | 已冻结并同步 | 保留 fail-closed、最小必要错误披露和可回放 Trace；本机 Pass 仅是单样本证据，Cloud 新版本仍需真实回执。 | 后续真实 UI 流程完成后，再记录 ProviderRun/VerificationResult；不以本次修复替代端到端验收。 |

## 2026-09-01 追加记录｜腾讯特效 Web Provider 实施与正式准入 Gate

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-077 | 2026-09-01 | 将腾讯特效 Web SDK 定义为独立新 Provider Spike，不改 Tencent BeautifyPic 主链，不把移动/PC 的唇厚、鼻翼、眉毛、眼距等候选能力迁移成 Web API；产品刻度 0—100 由 Adapter 确定性映射到 Web 0—1，美白/磨皮默认 0。 | 已冻结并实现 | 能在绑定域名上验证 Web 静态图，同时保持 RAG advisory-only、Provider 白名单和主流程 fail-closed | 真实 Browser Receipt、Gold 回归和产品负责人批准后再评估 Card promotion |
| D-TECH-078 | 2026-09-01 | 新增 `tencent-effect-web` Card、`TencentEffectWebAdapter`、`EffectWebRequest/BrowserReceipt/Admission` 合同、Streamlit page 6 和离线 smoke；浏览器只接收 License Key/APP ID/短时签名，Token 留在服务端，图片/结果只在浏览器会话。 | 已实现；离线验证通过 | `ProviderRun` 支持 `tencent_effect_web/WebARImage`；Trace 可保存 hash、尺寸、耗时、错误码和本地 receipt，不保存 Base64/原图 | Cloud Secrets 配齐后运行官方示例图，保存非敏感真实回执 |
| D-PROD-079 | 2026-09-01 | Web Card 默认保持 `candidate`。正式准入必须同时具备有效 License、精确域名、Provider 权限、出站/区域批准、成本/预算、Adapter ready、真实成功 Browser Receipt 和产品负责人批准；准入函数只返回 `promote_after_review`，不自动改 Card 或授予图片出站权限。 | 已冻结 | 防止“License 正常”或一次 smoke 被夸写成正式能力；Web generic 与移动/PC 细项、单图与批量证据分开 | 取得真实 receipt 后人工审核 Card 与 RAG 是否接入 |
| D-TECH-080 | 2026-09-01 | Web Adapter 离线 smoke 与 9 条测试通过；当前没有新的浏览器 live receipt，故不可宣称 Web 图片处理已上线、细项五官/批量已验证或供应商隐私/区域已确认。 | 已验证当前边界 | 所有文档、合同、代码和测试统一为 candidate/browser-smoke-blocked-by-cloud-secrets | 配置三项 Effect Secrets 后再执行 page 6 live smoke；失败保留安全错误，不绕过准入 |

## 2026-09-01 追加记录｜失败驱动 RAG Loop v2：修正层级并取得真实开发集增益

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-081 | 2026-09-01 | 复盘上一轮 V0/V1/V2 Composite 均为 `0.947436` 后，产品负责人确认优化必须遵守“冻结 V0 → 逐题失败归因 → 只改一个根因 → 回归/反过拟合 → 再决定 promotion”的链路；不能把 Trace 名称变化写成增益。 | 已冻结并实现 | 失败分析成为可证伪的产品质量机制；RAG 继续 proposal-only，不改变权限、Provider 或图片执行 | 审核新开发集 annotations 后，新建独立 Holdout v4 验收 |
| D-TECH-082 | 2026-09-01 | 定位到上一轮候选只改 Prediction 后处理、未触达线上 `RagQuery` 输入边界；新增 `rag-query-compiler-candidate-v0.1`，在检索前抽取受审核 QuerySignals，并按安全/生命周期优先级编译。 | 已实现并验证 | 真实修复 route/evidence 上游缺口；候选不读照片、向量、hidden 答案，不联网、不调用 LLM/Provider | 仅在 owner-review dev/challenge 使用；未替换 active baseline |
| D-TECH-083 | 2026-09-01 | 新增 `rag_failure_driven_dev_v1`（16 dev + 12 challenge）与结构化 annotations；V0 failure code 为 route 24、relation 23、set 18、rank 10，稀疏 Gold 分母 28 条单列记录。 | 已生成；待产品负责人审核 | 可针对性分析上游查询投影、动作/提问歧义、安全/生命周期、多意图 union 和评测口径；禁止按 v3 case ID 打补丁 | 产品负责人逐题审核题目和 Gold relation/evidence |
| D-TECH-084 | 2026-09-01 | 失败驱动 Loop 实跑 V0→V4：V0=`0.355614`；V1=`0.403233`（+0.047619，改变 2 条预测）；V2=`0.947619`（+0.544386，改变 22 条预测）；V3/V4 改变 0 条预测，连续两代增益 `<0.01` 后停止。 | 已验证；候选未推广 | 证明上一轮无增益是修错层；V2 开发集 route/relation/Recall@5=100%，但 public regression/project Gate 仍 `FAIL`，anti-overfit=`PASS` | 审核 annotations、建立独立 v4，不能重跑/读取 v3 私有逐题答案 |
| D-TECH-085 | 2026-09-01 | 失败驱动报告、SOP、Rubric、page 5 优化看板、合同/Prompt/PRODUCT_RULES/README/执行版 PRD 已同步；候选 Trace 统一记录无网络、无 LLM/Provider、无 hidden 答案、active baseline 未改变。 | 已同步；全量 QA 待本轮完成 | 形成唯一当前事实，避免把开发集改善误写成产品化通过 | 本轮全量 pytest、Ruff、compileall、diff check 完成后更新最终测试数 |
| D-TECH-086 | 2026-09-01 | 完成本轮最终交叉校验：全量 `pytest 173 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check`、failure-driven Loop、P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 全部通过。 | 已验证 | 代码、合同、测试、报告、看板与文档在当前快照一致；4 条 warning 为既有 Pillow 弃用提示 | RAG project Gate 仍 `FAIL`；待产品负责人审核 28 题 annotations 和新建 Holdout v4 |

| D-TECH-087 | 2026-09-01 | 为避免只看总分，失败驱动报告新增 `final_candidate_diagnostics`，对 28 道公开开发/挑战题保留 V0 与终态逐题状态、错误码、路由和是否发生 Prediction 变化；新增人工复盘文档 `RAG_FAILURE_CASE_REVIEW_V2.md`。 | 已实现并通过测试 | 逐题结论可回放且不泄漏 v3 私有答案；从 V0 到终态 24 条 Prediction 事实变化，V2 相对 V1 为 22 条；RAG 仍 proposal-only，active baseline 未改变 | 产品负责人审核开发集 annotations 后，再创建独立 Holdout v4；v3 不重跑 |

## 2026-09-01 追加记录｜腾讯特效 Web Cloud 重建与 Secrets 阻塞

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-TECH-088 | 2026-09-01 | Streamlit Cloud 拉取最新代码后曾因旧进程缓存报 `load_tencent_effect_web_card` ImportError；执行 Cloud Reboot 后 page 6 正常加载，故将该问题归因为部署进程缓存而不是 Card/Adapter 代码缺失。 | 已定位并修复 | Cloud 构建入口恢复；不等于 Web 图片处理成功，不改变主流程 Provider 白名单 | 后续每次依赖代码更新后观察 Cloud 构建日志与页面首屏 |
| D-TECH-089 | 2026-09-01 | Cloud page 6 在生成短时签名前发现缺少 `TENCENT_EFFECT_APP_ID`、`TENCENT_EFFECT_LICENSE_KEY`、`TENCENT_EFFECT_LICENSE_TOKEN`，本轮没有加载 SDK、图片出站或 Browser Receipt。已有 Tencent REST Secret ID/Key 与 Effect Web 三项配置分开。 | 当前阻塞 | `tencent-effect-web` Card 保持 `candidate`，离线 smoke 不得写成 live；Token 仍只在服务端签名 | 产品负责人在 Cloud Settings → Secrets 配齐后，先运行官方示例图一次，再补隐私/区域/成本/Gold/人工准入证据 |

## 2026-09-02 追加记录｜V3 解冻验证诊断与 RAG 回归守门

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-090 | 2026-09-02 | 产品负责人明确允许读取已审核的 V3 题目与答案，用于逐题失败模式、SOP 和候选优化；原始一次性 answerless 盲测快照保留且不重跑，V3 新用途改为 `validation`，不能再称为独立 Holdout。 | 已冻结并实现 | 可以补齐 H01–H36 的题干、Gold、Prediction、根因和完整 Trace；新的独立泛化证据必须来自 V4 | 生成与 V3 不重叠的 V4 Holdout 后，再决定 promotion |
| D-TECH-091 | 2026-09-02 | 新增 `rag_v3_validation_diagnostics.py`、验证集加载/派生脚本、运行脚本、逐题失败解释、完整 Trace、JSON/HTML 和 page 5 看板区。 | 已实现 | 每代 36 条 Trace 均保留 query hash、投影、检索摘要、证据关系、守门与安全布尔事实；无照片、向量、密钥、网络/LLM/Provider | 全量 pytest、Ruff、compileall、diff check 和诊断 runner 必须一起通过 |
| D-TECH-092 | 2026-09-02 | 失败驱动迭代前移到自然语言→QuerySignals→RagQuery 边界。G0 Route=30.56%、Relation=23.61%、Recall@5=59.72%；G2 在 V3 validation 达到 100%；G3 增加 public regression guard 后 public Route/Relation/Recall 保持 100%，V3 Relation=97.22%；G4/G5 no-op。 | 已验证；候选未推广 | 证明上一轮无增益是修错层，并用回归守门抑制 V3 过拟合；RAG 仍 proposal-only、active baseline 未变 | 新 V4 通过前不得把 G2/G3 写成产品化通过 |
| D-TECH-093 | 2026-09-02 | 固定 Precision 的稀疏 Gold 现象继续单列为评测提示；V3 最终覆盖式/返回式 Precision=100%，固定 Precision 与 project Gate 仍 FAIL。 | 已冻结 | 不通过塞无关证据或修改分母偷抬分；Composite 只用于代际比较 | 后续 Holdout 重新设计 Gold evidence 粒度并保持双口径 |

| D-TECH-094 | 2026-09-02 | V3 validation HTML 增加 H01–H36 的可展开完整 Trace；JSON 保留 G0–G5 全代 Trace。全量交叉校验以本轮实际命令为准，历史 173-test 快照只保留作时间线。 | 已实现并验证 | 产品负责人可逐题复盘“问题→根因→SOP→检索/路由事实”，不需要从代码猜测；Trace 仍脱敏、离线、proposal-only | 本轮 QA 已完成；若新增代码或文档，沿用同一套全量检查 |

| D-TECH-095 | 2026-09-02 | 完成当前快照交叉校验：新增 V3 validation 诊断测试后，全量 `.venv/bin/pytest -q` 为 `178 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 通过，失败驱动 Loop、P0-A/P0-B/advisory/lifecycle/8C/8C2 与 Web 离线 smoke 均保持既定结果。 | 已验证 | 代码、合同、测试、RAG 诊断文档和 Dashboard 口径同步；4 条 warning 仍为 Pillow 弃用提示。Tencent Effect Web 仍因 Cloud 缺三项 Secrets 没有 live Browser Receipt，Card 不升级。 | 产品负责人补齐 Effect Web Secrets 后再跑一次官方示例图；不得把离线 smoke 或 Cloud 重建写成图片处理成功 |

## 2026-09-02 追加记录｜Tencent Effect Web 回执 request_ref 错位修复

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-TECH-096 | 2026-09-02 | Cloud page 6 首次收到浏览器回执时出现 `request_ref does not match`。根因是 Streamlit 组件事件触发脚本重跑，而旧页面每次重跑随机生成新的 `request_ref`；后端合同拒绝了旧回执。修复为按输入 hash/引用、参数、来源和 Card 版本生成 fingerprint，并在同一代次复用 request_ref；签名时间可刷新，reset token 不再随时间变化；旧代次回执安全忽略，不写入 ProviderRun。 | 已实现并通过回归 | 解决真实 UI 回执关联错位，不放宽回执合同，不改变 Token/图片留存边界、candidate Card 或 RAG proposal-only；新增 2 条回归测试。 | Cloud 拉取该提交后重跑 page 6；真实 Browser Receipt 仍需 Secrets、域名和 License 证据 |

| D-TECH-097 | 2026-09-02 | 回执关联修复后的本地全量 QA：`.venv/bin/pytest -q` 为 `180 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 通过；Web 专项 11 条回归通过。Cloud 已进入组件执行区，但本轮尚未取得新 Browser Receipt。 | 已验证 | 代码与合同一致；真实 Web Provider 仍是 candidate，不把 Cloud Secrets 已配置或页面可加载写成图片处理成功 | 用户点击当前版本组件后保存脱敏 Browser Receipt，再补 Card/准入证据 |
| D-TECH-098 | 2026-09-02 | Cloud page 6 真实重试已消除 `request_ref` 错位；腾讯 Web SDK 返回失败回执 `web_receipt_effect_web_fa6f0765ad924597`，耗时约 965ms、未生成输出图。浏览器日志出现 SDK 鉴权码 100；当前最可能的配置问题是 `TENCENT_EFFECT_APP_ID` 被填成绑定域名，而不是腾讯账号数字 APPID。 | 已定位；Provider 仍 blocked | 真实请求已到达浏览器 SDK，但不能写成处理成功；Card 继续 `candidate`，不改变主流程权限 | 负责人在 Cloud Secrets 仅修正数字 APPID 后 Reboot，再运行一次官方示例图 |
| D-TECH-099 | 2026-09-02 | 为避免重复失败与黑箱，Web bridge 在失败回执后重新启用按钮；服务端拒绝 URL 形式 APPID；前端把 SDK 已知错误码映射为安全中文提示并在页面显示 `error_code/safe_error`。本地全量 QA：`181 passed, 4 warnings`；Ruff、format、compileall、`git diff --check` 通过。 | 已实现并验证 | 重试可用、错误可观测且不泄漏密钥/原始 SDK 信息；不放宽回执合同，不自动升级 Card | 修正数字 APPID 后只做一次 live smoke；成功仍需完成隐私/区域/成本和负责人准入 |
## 2026-09-02 追加记录｜V4 独立 Holdout 与失败驱动 RAG 优化

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-100 | 2026-09-02 | V3 已被负责人解冻为 validation，不能继续作为独立泛化证据；建立与 V3 不重叠的 48 题 V4 Holdout，覆盖能力、路由、权限、隐私、生命周期、过期/冲突、注入、未就绪 Provider、复测、批量/多脸、缺槽位和参数边界。 | 已冻结并实现 | 运行包只含 `case_id + query`，答案键工作区外保管；正式盲测最多一次 | 新 Holdout 必须在答案键不回流的条件下重新验收 |
| D-TECH-101 | 2026-09-02 | V4 answerless baseline 已完成一次：48/48 predictions；未读答案/annotations、照片/向量、网络、LLM 或 Provider；盲测快照已封存，私有评分仅输出聚合。 | 已验证 | V4 baseline Route=12.50%、Evidence relation=18.75%、Recall@5=57.99%、MRR=81.25%、nDCG@5=63.22%；hard-safety 0/48 PASS，project Gate FAIL | 不得把安全 PASS 写成质量 PASS；不得把盲测答案带回开发代码 |
| D-PROD-102 | 2026-09-02 | RAG 继续 proposal-only；“智能”定义为在审核知识范围内理解任务、区分直接/参考/冲突证据并提出受限建议，不得新增工具、参数、权限或图片出站。 | 已冻结 | 8A/8C 可消费证据建议，但状态机、权限策略和 Adapter 仍是事实放行边界 | 任一 promotion 需新 Holdout、公开回归、安全、权限和真实回执证据 |
| D-TECH-103 | 2026-09-02 | 新增 `rag_v4_query_compiler_candidate.py`、validation diagnostics、私有 scorer、运行脚本、V4 文档和 page 5 看板。G2–G5 解冻验证语义指标达到 100%，fixed Precision@3=51.39%，project Gate 仍 FAIL；`blind_snapshot_match=true`、`active_baseline_changed=false`、`proposal_only=true`。 | 已实现；候选未 promotion | 修正触达自然语言→查询投影真实输入层；G3–G5 无新增预测变化后按 SOP 停止 | 只可在新的未参与诊断 Holdout 上讨论 promotion |
| D-PROD-104 | 2026-09-02 | V4 的 fixed/effective/returned Precision 并行保留。Gold 稀疏时 fixed K=3 会产生统计偏低；不通过改分母抬分，semantic diagnostic 仅作解释和调试，冻结 project Gate 仍权威。 | 已冻结 | 看板和报告必须同时显示统计口径与 Gate，避免将诊断分数写成泛化分数 | 后续若调整 Gold 粒度，先由产品负责人冻结新 Rubric，再建独立 Holdout |
| D-TECH-105 | 2026-09-02 | 完成 V4 后最终一致性校验：全量 `pytest 189 passed, 4 warnings`；V4 专项 `8 passed`；Ruff check/format、compileall、`git diff --check`、V4 diagnostics runner 和既有 RAG/8C smoke 均通过。 | 已验证 | 代码、合同、测试、报告、看板和文档口径同步；4 条 warning 为既有 Pillow 弃用提示；不改变 project Gate=`FAIL`、RAG proposal-only 或 candidate 未 promotion | 若调整 Rubric/Gold 或 promotion，必须重新建未参与诊断的新 Holdout |
| D-TECH-106 | 2026-09-02 | 产品负责人修正 Cloud Secret 后再次明确点击 Tencent Effect Web；稳定请求代次复用 `request_ref`，最新回执 `web_receipt_effect_web_3a3c71bec3f24557`，耗时 628ms，SDK 错误码 100/规范化码 20001001，未生成输出图。 | 已验证；Provider 仍 candidate/blocked | 回执关联和失败可重试链路保持有效；不能把鉴权失败写成 Web 能力成功；候选仍不进入主流程或 RAG 自动放行 | 只在确认 License/Token、数字 APPID/签名、精确域名和 Secret 重载后再做一次官方示例图；不盲目重复调用 |

| D-TECH-107 | 2026-09-02 | 在当前 Cloud 页面完整重新执行官方示例图流程；SDK 等待自身鉴权窗口后返回 `web_receipt_effect_web_3a3c71bec3f24557`，耗时 10360ms，SDK 错误码 100/规范化码 20001001，未生成输出图。稳定 `request_ref` 是同一代次的合同设计，本次为新的明确点击。 | 已验证；Provider 仍 candidate/blocked | 回执关联已通过，但 Web 鉴权仍阻塞；不升级 Card、不进入主流程、不由 RAG 放行 | 先完成 Cloud Secret 重载、License/Token 配对、数字 APPID/签名与精确域名核对，再做一次官方示例图 smoke |

## 2026-09-02 追加记录｜RAG 多轮低成功率反思审计

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-107 | 2026-09-02 | 在继续新增题目或调检索参数前，先对 V3/V4 多轮优化做独立反思审计。审计暂不改变质量门、active baseline 或 RAG proposal-only 边界；当前提出的下一 Gate 是把“自然语言→结构化查询”和“结构化查询→真实知识召回”拆成两条评测轨道，并补齐可检索的 Policy/Rule Card。该 Gate 仍待产品负责人确认，不把审计建议当成已冻结产品规则。 | 待下一 Gate 确认 | 防止把“听懂问题”的失败误写成向量检索失败，也防止在错误层继续加题、调 Top-K 或读取 Holdout 答案；现有 V4 盲测结果保持历史事实 | 产品负责人确认两条轨道、Policy/Rule Card 是否纳入质量评测、以及固定 Precision 与诊断口径的关系后，才进入下一轮开发 |
| D-TECH-108 | 2026-09-02 | 新增 `RAG_LOW_SUCCESS_REFLECTION_AUDIT_PROMPT.md`、`audit_rag_low_success.py`、JSON/HTML 反思报告和专项测试。审计只读公开代码、公开聚合、answerless Trace 与生命周期摘要；当前证据为 V4 48 题中仅 8 题生成结构化检索请求、40 题在检索前结束；知识库为 3 张卡/10 条有效规则；V4 fixed Precision@3 理论上限约 51.39%，公开集约 47.44%。独立审计视角复核后得到相同结论。 | 已实现；全量 QA 待本轮完成 | 形成“事实→推断→根因→最小验证”的可复核材料；不读取隐藏答案、照片、向量或密钥，不调用网络/LLM/Provider，不修改 active baseline | 完成全量测试和文档交叉检查后更新实际测试数；两条评测轨道 Gate 未确认前不新建 Holdout、不 promotion |
| D-TECH-109 | 2026-09-02 | 反思审计专项测试加入后完成最终交叉校验：`.venv/bin/pytest -q`=`193 passed, 4 warnings`；Ruff check、format（188 files）、compileall、`git diff --check` 和 `audit_rag_low_success.py` 均通过；P0-A/P0-B/advisory/lifecycle/8C/8C2 smoke 均 exit 0。 | 已验证 | 代码、合同、测试、报告、SOP 和工作协议在当前快照一致；4 条 warning 为既有 Pillow 弃用提示。工程通过不等于 RAG 质量通过，V4 project Gate 仍 `FAIL`，RAG 仍 proposal-only | 等产品负责人确认两轨评测与 Policy/Rule Card Gate 后，才进入最小公开 smoke；不得用本轮报告直接 promotion |

## 2026-09-02 追加记录｜Party Rock + 苹方视觉决策冻结

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-110 | 2026-09-02 | 产品负责人冻结正式界面采用 Tweakcn `Party Rock` 原始 Light/Dark token，并冻结苹方（`PingFang SC`）为正式 UI 字体；四元黑体及其他字体只保留作后续字标/实验候选。 | 已冻结；UI 实现待 Gate | 关键帧与后续前端实现不再在三套配色或十种字体之间切换；主题原始值保持不变，业务合同、权限、Provider、RAG、结果保留和 Trace 均不受影响。 | 实现前单独核验字体/主题授权；UI Gate 验证桌面关键帧、组件状态、可访问性和响应式降级。 |
| D-PROD-111 | 2026-09-02 | 冻结色彩面积层级：米白（`#F2F1E6`）为最大面积的画布/中央工作区/容器，紫色（`#A855F7`、`#C084FC`）为第二大面积的主操作/激活/选中/结果高光，黑色为侧栏/文字/分隔线等结构色，荧光绿、珊瑚红及其他颜色只作少量语义点缀。面积参考用户示意图的“米白画布 + 黑色侧栏 + 紫色高光”关系，不复制示意图内容。 | 已冻结；UI 实现待 Gate | 视觉评审只验证比例、层级和真实状态，不再做主题颜色改造，也不让点缀色竞争主 CTA；Streamlit 尚未迁移。 | 在 1440×900 与 1280×800 关键帧中复核相对面积和对比层级；通过后再进入 Frontend 原型与 Impeccable Critical/Audit。 |

| D-TECH-112 | 2026-09-02 | Tencent Effect Web 结果捕获出现浏览器错误：SDK 初始化后旧代码重新设置其输出 Canvas 的 `width/height`，触发 Chromium 的 Canvas transfer resize 限制。修复为 SDK Canvas 固定不变，`takePhoto()` 返回的 `ImageData` 写入新建结果 Canvas；新增回归断言覆盖该边界。Web 专项 `12 passed`，全量 `193 passed, 4 warnings`，静态检查通过。 | 已修复；待 Cloud 重跑 | 解决结果捕获阶段的前端兼容性问题；不改变 License、签名、图片留存、Provider Card 或 RAG 准入状态。 | Cloud 拉取新版本后用官方示例图重跑一次；成功回执仍需完整准入证据。 |

## 2026-09-02 追加记录｜UI/UX Spec v1.0 审计冻结与 Image 2 关键帧

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-113 | 2026-09-02 | 对 `docs/前端与交互设计需求文档.md` 完成一致性审计：以最新手动决策为最高优先级，清除旧英文 slogan、长标题、背景摄影、下方 Agent 对话、前台安全确认、Plan A/B/C、默认 Trace 和弹窗新窗口等冲突；统一为四区桌面工作台、对齐首页 + Agent 对话子页面、自然语言主控制面和短中文文案。 | 已冻结 | Spec 升级为 `UI/UX-SPEC-v1.0`；关键帧与 Frontend 原型必须以该文档为唯一设计基线。重大变更只能通过变更请求重新确认，不得在 Critical/Audit 中静默改写。 | UI Gate 只检查实现还原、状态诚实、可访问性、响应式和真实用户走查；业务合同与权限边界保持不变。 |
| D-TECH-114 | 2026-09-02 | 新增 `docs/FRONTEND_UI_KEYFRAME_PROMPT.md`、`design/keyframes/party-rock-pingfang/index.html`、4 张分层 SVG 和 4 张 Image 2 PNG 视觉方向稿；PNG 已嵌入 `impeccable:prompt` 元数据并保留 prompt sidecar。SVG/HTML 是精确中文排版和可编辑布局源，不声称已生成原生 Figma `.fig` 或 Streamlit 功能。 | 已生成；待 UI Gate | 设计师可直接修改 HTML/CSS 或将 SVG 导入 Figma 后取消编组；PNG 只用于材质/比例参考，不包含真实照片、Provider 结果或敏感数据。 | 浏览器正式视觉回归、WCAG 2.2 AA、Frontend 接入、Critical/Audit 和真实用户证据仍待完成；不得把样张写成线上效果。 |

| D-TECH-115 | 2026-09-02 | 修复 Tencent Effect Web `takePhoto()` 结果捕获：旧代码调整 SDK 输出 Canvas 的 `width/height`，触发 Chromium Canvas transfer resize 错误；现改为保持 SDK Canvas 不变，将 `ImageData` 写入独立结果 Canvas 后生成 hash。部署后真实 page 6 回执 `web_receipt_effect_web_4d58ea15a0794370` 成功，耗时 2601ms，输出哈希已保存。 | 已完成技术验证；Card 仍 candidate | Web 静态图 Adapter 已证明一次端到端成功；结果图仍只留浏览器会话，Python 只留脱敏回执，不改变 RAG proposal-only 或主流程 Provider。全量 pytest 196 passed，Web 专项 12 passed。 | 继续补充多图/异常回归、供应商隐私/区域/预算与精确域名准入后，才可人工评审 Card promotion。 |

## 2026-09-02 追加记录｜RAG 反思后的公平评测与过程监督

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-116 | 2026-09-02 | 产品负责人确认：把“自然语言理解”和“真实知识检索”拆成两条评测轨道；同时覆盖工具能力、权限、隐私、生命周期、过期、冲突和提示注入；保留历史 fixed Precision，并增加低于三分之一/达到三分之一/达到三分之二的诊断带，但不替换既定 project Gate。当前知识库不扩张，RAG 继续 proposal-only。 | 已冻结 | 后续指标可以说明到底是没听懂、没召回、关系标错还是 Gold 口径问题；不再用新题或换分母掩盖流程缺口 | 过程门通过后，再由负责人审核两条轨道的 Gold 连接字段；新的独立 Holdout 才能用于泛化/promotion |
| D-PROD-117 | 2026-09-02 | 产品负责人确认：V3/V4 在连接质量答案之前，必须由独立过程监督考官逐题检查“无缺失/重复、无答案/标注/照片/向量/密钥泄露、编译成功或明确降级、每题合法查询、完整检索 Trace、Prediction 只来自 retrieval_result、无 projection/Gold 注入、无网络/LLM/Provider 副作用”。旧快照不完整时不得补写为 PASS。 | 已冻结 | 过程门 PASS 只表示考试流程完整，不等于内容正确；质量评分在过程门失败时保持锁定 | 新版 answerless 运行包封存后再连接 Gold；旧 V4 快照永久保留为历史证据 |
| D-TECH-118 | 2026-09-02 | 实现 `RagFairEvaluationRunner`、`RagProcessSupervisor`、公平评测脚本、专项测试、脱敏 answerless 运行包和 page 5 看板。新版无答案重放：V3 `36/36`、V4 `48/48` 均有完整检索 Trace，分别 `structured=5/8`、`unknown_fallback=31/40`，新运行过程门均 PASS；旧 V4 快照审计 FAIL（`MISSING_REQUIRED_STAGE=432`、`MISSING_GOVERNANCE_FACTS=48`、`PROJECTION_INJECTED_INTO_EVALUATION=48`、`FORBIDDEN_SIDE_EFFECT_OR_LEAK=2`）。 | 已实现并验证 | 新运行可进入独立 Gold 验证，旧快照质量状态仍 `LOCKED_HISTORICAL_PROCESS_AUDIT`；不改 active baseline、不放行工具、不把验证成绩当泛化 | 连接 Gold 只能消费新 answerless 运行包；不得把过程 PASS、旧质量分数或验证分数写成 RAG 产品化 |
| D-TECH-119 | 2026-09-02 | 为避免旧快照的历史缺陷浪费已经完整跑通的新数据，门控拆为“当前新运行过程门”和“历史快照过程门”：新运行过程门 PASS 即可进入独立 Gold 验证；历史快照 FAIL 只锁定历史质量分数，不阻塞新运行，也不得被修写或复用。 | 已实现并验证 | 报告同时展示两种状态；`quality_scoring_gate` 只描述新运行，`historical_quality_scoring_gate` 单独描述旧快照；RAG 仍 proposal-only | 新验证结束后仍需独立 Holdout/公开回归/安全门和负责人批准，才能讨论 promotion |

| D-TECH-120 | 2026-09-02 | 交叉检查发现公平评测的脱敏 Trace 虽已移除顶层案例编号，但嵌套 Prediction 仍带有 `case_id`；已改为序列化前同时移除嵌套编号，仅保留 `case_id_sha256`，并新增回归断言。 | 已修复并验证 | 四份 answerless predictions/Trace 均不含题干、答案字段或任何明文案例编号；过程门字段与 Gold 连接规则不变，RAG 仍 proposal-only | 仅允许下一步按哈希连接 Gold；不得因脱敏修复而重跑或改写旧快照 |

| D-TECH-123 | 2026-09-02 | 为把 Tencent Effect Web 从孤立 page 6 试验接入工具决策面，新增只读 `ToolRegistry` 和受限 `ToolProposal` Meta-Agent 层。Registry 登记 verified BeautifyPic baseline 与 candidate Web Card；Meta-Agent 可提出 Web 候选、记录 Card/证据/检查项并提供 baseline fallback，但 `execution_authorized` 永远为 `false`。 | 已实现并离线验证 | `Provider Card → Registry → Meta-Agent → proposal-only Trace` 可回放；无图片读取、密钥、网络、ProviderRun 或参数副作用。Web Card 仍 candidate，不改变主流程。 | 结果交接 A（浏览器端复测）/B（一次性回 Python）/C（只展示下载）需产品负责人另行冻结后，才可修改 EditPlan/执行器和 Web promotion |

| D-TECH-124 | 2026-09-02 | 本轮 Registry/Meta-Agent 增量完成最终 QA：新增专项 6 条、全量 `pytest`=`205 passed, 4 warnings`；Ruff check/format、compileall、`git diff --check` 和离线 smoke 均通过。 | 已验证 | 仅证明 proposal/Trace 控制面与既有代码一致；不改变 Web Card `candidate`、RAG `proposal-only`、六类业务合同或主流程图片权限。 | 下一步必须先冻结 Web 结果交接 A/B/C，才可继续主流程 Adapter/Verification 改造 |

## 2026-09-02 追加记录｜UI/UX v2 两关键帧视觉覆盖与可编辑资产

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-120 | 2026-09-02 | 产品负责人将活跃视觉交付收敛为两张关键帧：E01「入口」与 E02「Agent 对话」。此前四张 K01—K04 只保留为历史资产，不再作为实现依据；底层上传、自动门控、授权、结果与停止状态仍由同一 Agent 对话空间承载。 | 已冻结；UI 实现待 Gate | 设计评审只需确认入口与对话两种空间，避免把状态机误拆成多页面；不改变合同、权限、Provider、结果保留或 Trace 边界。 | UI Gate 复核两帧的状态诚实、可访问性、响应式和自然语言主控制面；重大语义变化须重新确认。 |
| D-PROD-121 | 2026-09-02 | 产品负责人覆盖旧的“米白最大、紫色第二”描述：Party Rock 原始 token 和苹方保持不变，页面面积改为紫色与米白共同主导、紫色在暗流/对齐舞台/关键操作中略强；黑色负责结构，其他颜色稀疏点缀。 | 已冻结；UI 实现待 Gate | 不改主题色值，只改使用层级；关键帧以紫色暗流与米白行动/对话面形成高级、直接的对比，避免米白铺满造成土感。 | 在 1440×900 与 1280×800 帧中用 QA 带宽复核：紫色约 40—45%、米白 35—40%、黑色 15—20%、其他≤5%。 |
| D-TECH-122 | 2026-09-02 | 用 Image 2 生成 E01/E02 视觉方向稿；建立无依赖 HTML 原型、分层 SVG/Figma 导入源、1280/1440 同源渲染和 prompt sidecar。旧 K01—K04 已安全移入 `design/keyframes/party-rock-pingfang/archive/v1-four-state/`。 | 已生成并静态验证；待 UI Gate | HTML/SVG 提供精确中文、颜色与可编辑图层；PNG 只作材质/比例参考，不声称原生 Figma `.fig`、Streamlit 迁移或真实用户结果。 | 完成浏览器正式视觉回归、WCAG 2.2 AA、Frontend 映射、Impeccable Critical/Audit 后再进入代码实现。 |

## 2026-09-02 追加记录｜Getty × Party Rock 视觉候选重开

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-125 | 2026-09-02 | 产品负责人否定上一版中间工作区的紫黑暗影/暗流，明确最新候选统一为“最左侧黑色导航 + 中央/右侧米白工作面 + 紫色柔性圆角框/编辑式黑框 + 荧光绿少量动感”。Party Rock 原始 token 与苹方不变；业务主链、路由、授权、隐私和结果边界不变。 | 候选硬约束已冻结；具体方向待选择 | 防止视觉实现回到沉重、僵硬的 AI 工具箱；不改变任何合同、Provider、RAG 或存储能力 | 在 A/B/C 方向选择后用 Impeccable Critical/Audit、浏览器和 WCAG Gate 复核；方向选择前不得写成最终视觉规范 |
| D-PROD-126 | 2026-09-02 | 基于 Getty `Tracing Art` 抽象“先路径后数据、关系轨迹、编辑式留白、混合媒介证据和序列节奏”，形成三套候选：A「档案游线」、B「柔性索引」、C「开放谱系」。每套严格两张关键帧：E01 入口 + E02 Agent 对话。 | 候选探索，不冻结 | 让用户能在同一套 Agent 语义下选择不同视觉叙事，而不增加业务页面或状态分叉 | 产品负责人在 `candidate-review.html` 选择单一方向或明确混合方向；选择结果单独记录为下一条冻结决策 |
| D-TECH-127 | 2026-09-02 | 新增三套候选的 6 张 Image 2 PNG、6 张分层 SVG、12 张同源 1280/1440 渲染帧、Prompt sidecar、候选评审 HTML 与 README；源 PNG 的 `impeccable:prompt` 扫描为 `6 raster, 0 missing`。 | 已生成并静态验证；待 UI Gate | PNG 仅是材质/比例方向稿，SVG/HTML 是精确文案与可编辑布局源；不声称原生 Figma `.fig`、Streamlit 已迁移、真实照片结果或 Provider 效果 | 完成浏览器正式回归、WCAG、Critical/Audit、Frontend 映射后再实现；候选未选前不改 Streamlit |
| D-TECH-128 | 2026-09-02 | 按用户指令尝试 `npx skills add nextlevelbuilder/ui-ux-pro-max-skill@ui-ux-pro-max -g -y`；GitHub clone 长时间无可用结果，已安全取消，未把该 skill 写成已安装或已使用。 | 安装未完成 | 本轮使用已加载的 Impeccable Shape/视觉工作流和 Image 2 完成候选；不影响项目代码和业务合同 | 若后续需要该 skill，需重新安装并先验证其文件与说明真实存在 |

| D-TECH-134 | 2026-09-02 | 对 A/B/C 三套候选的 E02 Image 2 源图做一次定向清理重生成，并重新嵌入 `impeccable:prompt`；源图不再包含真实人物/照片、伪造指标、日期/ID、雷达图或密集仪表盘。6 张源 PNG 扫描 `6 raster, 0 missing`；SVG、评审页脚本和禁用 UI 文案静态检查通过。 | 已完成；方向待选择 | 只更新视觉候选材质，不改变产品语义、合同、Provider、权限、结果或 Trace；候选评审仍以 SVG 精确文案和布局为准 | 当前全量测试 `213 passed, 1 failed, 4 warnings`；失败为既有 Tencent Effect Web 回归断言，与本轮设计资产无关。候选选择后再运行 Critical/Audit、浏览器/WCAG/UI Gate |

## 2026-09-02 追加记录｜Web Card 接入统一计划与共同复测（B 冻结）

| 决策 ID | 日期 | 决策 / 事实 | 状态 | 产品/工程影响 | 后续复核 |
|---|---|---|---|---|---|
| D-PROD-129 | 2026-09-02 | 产品负责人选择 B：Web SDK 结果通过一次性受限 handoff 回 Python 当前会话内存，再进入共同 `VerificationResult`；不采用浏览器端另建复测（A），也不把 Web 限制为只展示/下载（C）。 | 已冻结 | 能复用现有 8C 观察器，新增图片交接和大小/哈希校验；结果 data URL/bytes 不得落盘，Web Card 仍 candidate | E1 真实结果复测、E2 多样本/批量隔离、供应商条款/区域/费用及负责人准入完成后，才讨论 promotion |
| D-PROD-130 | 2026-09-02 | E1/E2/E3 采用顺序冻结：E1 先接共同 `ProviderRun → VerificationResult`；E2 再做成功/失败/错位/超限/批量隔离回归；E3 最后在全部准入证据齐全时由负责人批准 candidate→verified。 | 已冻结 | 防止单次 SDK 成功被误写为效果或泛化通过；BeautifyPic 继续是正式主链 baseline | E3 只允许人工变更 Card，代码和 LLM 不得自动 promotion |
| D-TECH-131 | 2026-09-02 | `EditPlan`/`ProviderRun` 增加 Web 联合参数模型与 Provider 校验；新增 `EffectWebBrowserResult` 和 `accept_effect_web_browser_result()`，校验 request_ref、输入/输出 hash、尺寸、MIME、大小及 candidate trial 开关。 | 已实现并验证 | Web 产品强度 0—100 与 SDK 0—1 分离；正常 handoff 可形成共同 ProviderRun，异常 fail-closed，Trace 不含图片 | 真实 Cloud 结果需继续按当前请求代次回放；不能通过修改合同放宽鉴权/准入 |
| D-TECH-132 | 2026-09-02 | 新增 Web E2 回归套件和 page 7 看板。6 个离线样本覆盖成功、Provider 失败、request_ref/输出 hash/尺寸/MIME 错位；`6/6` 通过，坏样本不阻塞后续样本，结果 payload 不持久化。 | 已验证（fixture-only） | 证明合同、异常拒绝和批量隔离；不证明真实视觉效果或供应商泛化 | 增加真实多样本/批量视觉证据后才进入 E3 |

| D-TECH-136 | 2026-09-02 | 交叉复核发现 E2 套件虽然 6/6 正确，但没有覆盖输入哈希错位和结果大小上限，且样例排列不能证明拒绝样例之后仍会继续处理。仅补充这两个异常样例，并把一个有效失败回执放在拒绝样例之后；最终 8/8 通过，`hard_safety_passed=true` 与 `batch_failure_isolation_passed=true` 分开统计。 | 已验证（fixture-only） | 强化 Web 结果交接的完整性和批量故障隔离证据，不放宽 candidate、RAG proposal-only 或任何执行权限；报告仍不保存结果 payload | E3 仍需真实多样本视觉、供应商条款/区域/留存/费用和产品负责人批准 |
| D-TECH-133 | 2026-09-02 | 新增 `docs/TENCENT_EFFECT_WEB_FULL_INTEGRATION_PROMPT.md`，并将当前 B/E1/E2/E3 顺序、回滚和输出要求同步到执行 Prompt、PRD、合同、产品规则、进展与 README。当前全量 QA=`214 passed, 4 warnings`。 | 已完成并验证 | 项目可由下一次会话按同一 Prompt 继续，历史 A/B/C 未决文字保留为时间线并由当前冻结覆盖 | 若 Web Card promotion 或隐私/供应商事实改变，追加新决策记录，不改写本条历史 |

| D-TECH-135 | 2026-09-02 | 补充 Meta-Agent→Web EditPlan provider/Card 绑定回归，并将 E2 的 `hard_safety_passed` 与 `batch_failure_isolation_passed` 拆成两个独立事实；安全拦截不再受坏样本排列位置影响。最新全量 QA=`215 passed, 4 warnings`。 | 已完成并验证 | 提议、计划和回归指标的耦合更紧；不改变 Web Card candidate、RAG proposal-only 或 E3 准入 | 后续真实 Web 多样本/批量和供应商证据仍须独立进入 E3，不能用本条 fixture 回执 promotion |
