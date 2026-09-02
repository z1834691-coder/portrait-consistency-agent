# 母版人像一致性 Agent｜两张关键帧 × 三套方向执行 Prompt

> 版本：`KEYFRAME-PROMPT-v2.1` · 日期：2026-09-02
>
> 状态：<span style="color:#C00000"><strong>产品语义、Party Rock 原始 token 与苹方已冻结；视觉方向重新开放为 A/B/C 三套候选。每套严格两张主关键帧：E01 入口、E02 Agent 对话。PNG 用于视觉定调，HTML/SVG 用于精确文案与可编辑布局；方向选择后再进入 Streamlit UI Gate。</strong></span>
>
> 设计基线：[前端与交互设计需求文档](前端与交互设计需求文档.md)；产品事实以[执行版 PRD](母版人像一致性Agent-执行版PRD.md)、[PRODUCT_RULES.md](PRODUCT_RULES.md)、[CONTRACTS.md](CONTRACTS.md) 和代码/测试为准。

## 1. 角色与目标

你是一名负责 C 端 Agent 产品的首席产品设计师、交互设计师、视觉设计师和原型导演。请把“上传照片，再用自然语言告诉 Agent 想保留或改变什么”做成一个安静、直接、可信、可验证的工作台。

产品不是传统修图工具、参数面板、工程监控台或营销落地页。用户不学习滑杆，不比较 Plan A/B/C，不点击后台内容安全检查，也不需要打开独立诊断报告。对话是主控制面；照片、差异、计划、结果和必要依据是对话中的可展开事实块。

## 2. 不可改变的产品事实

1. 产品只处理用户自己授权的本人照片，并把一张已确认的母版作为几何参照；不是身份搜索、美颜评分、医美建议或陌生人检索。
2. V0 只制作两条主路由：`/align` 入口、`/align/:session` Agent 对话。`母版`、`记录`是导航分组与上下文入口，不制作独立的业务关键帧或复杂子页面。
3. 桌面保留轻量 App Shell：全局导航、项目/母版上下文、中央工作区、Agent 对话。E01 可以让中央工作区承担入口主任务；E02 让中央工作区承接照片证据，右侧承接连续对话。不得让用户在多个页面重复填写同一目标。
4. 正常主链固定为：上传 → 自然语言目标 → 自动质量/同人/安全/依据检查 → 一条默认建议 → 一次外部图片处理授权 → 结果/复测 → 继续表达或停止。
5. 后台门控自动发生；外部 Provider 图片处理在调用前必须有一次绑定当前照片、母版、部位、范围和有效期的明确授权。任何 scope 变化都重新授权。
6. 只展示可核实的关键事实、关键决策和下一步；不展示隐藏思维链、原始 Trace JSON、原始 Provider 字段、向量、密钥、未经校准的分数或假进度。
7. 结果图仅当前会话内存；Provider 回执成功与结构化复测改善必须分开说。

## 3. 已冻结的视觉系统与本轮候选硬约束

### 3.1 Party Rock 原始 Token

严格使用 Tweakcn `Party Rock` 原始 token，不调色、不改变明暗、饱和度、对比度或色相：

- Light background：`#F2F1E6`
- Light primary：`#A855F7`
- Light secondary：`#C084FC`
- Light destructive：`#FF4D4D`
- Dark background：`#121212`
- Dark primary/accent：`#A855F7`
- Dark destructive：`#800000`

<span style="color:#C00000"><strong>最新视觉候选覆盖：</strong>上一版紫黑暗流已被产品负责人否定，不再作为当前构图。三套候选统一使用“左侧黑色导航书脊 + 中央/右侧米白工作面”；紫色/淡紫通过柔性圆角框、轨迹、标签和焦点建立品牌记忆；荧光绿 `#36FF9B` 只作少量活动节点/进行中信号；黑色线框与文字承担结构。不得在中间/右侧铺黑底，不得使用紫色+黑色暗影渐变、发光网格、玻璃拟态或大面积荧光绿。面积比例在候选选择前不写死。</span>

用户参考图只用于抽象“黑色左书脊、柔性框、紫色高光、荧光绿动感和米白工作纸”的层级关系，不复制品牌、Logo、摄影、文案或页面资产。Getty 的关系/轨迹叙事抽象见 [UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md](UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md)。

### 3.2 字体与形状

- 正式中文界面字体：`PingFang SC`（苹方）；降级 `Noto Sans SC` → `Microsoft YaHei`。
- 英文/数字：`Arial`；不引入第二套中文 UI 字体。
- 标题短、字重克制、正文易读；不使用装饰性手写字体承载授权、错误或状态。
- 低装饰密度；圆角、黑色细边、轻微实体阴影和明确对齐轴服务于层级、状态或照片对比。

## 4. 两张关键帧 × 三套视觉候选

为 A/B/C 每套各生成 E01、E02 两张桌面主基准 `1440×900`，再由同一组 SVG 源导出 `1280×800` 降级帧。三套保持同一 Shell、同一 Party Rock token、同一 PingFang SC、同一任务语义，只改变视觉叙事；不得把内部状态矩阵的每个状态都扩展为独立页面。候选选择前均标记为“候选探索，不冻结”。

| 编号 | 页面 | 画面必须表达 | 精确主文案 | 唯一主要动作 |
|---|---|---|---|---|
| E01 | 入口 `/align` | 一眼知道“先上传母版或直接说目标”；黑色只在最左导航，中央/右侧米白，紫色柔性框/轨迹与少量荧光绿节点建立记忆 | 标题 `建立母版` 或 `开始对齐`；说明 `先上传一张你认可的本人照片。` | `上传母版照片`；已有母版降级为文字入口 `已有母版，开始对齐` |
| E02 | Agent 对话 `/align/:session` | 左侧黑色导航 + 米白工作区；轨迹串起母版/当前/差异/结果；右侧米白对话只展示关键消息、关键事实和一个输入框 | 用户 `把这张向母版靠拢，保留妆面。`；Agent `我会保留妆面，只处理可可靠测量的脸型和眼睛。` | 自然语言输入；若触及外部副作用，后续对话中只出现一次有界授权 |

### E01 入口构图（所有候选共同要求）

- 左侧全局导航使用黑色；项目上下文和中央主卡保持米白，以紫色柔性框、黑色线框和一条对齐轨迹建立层级。
- 轨迹中只放两个不可识别的中性肖像占位、少量紫色节点和一个荧光绿活动节点；不放真实照片或摄影底图。
- 米白行动面只放短标题、上传主按钮、一个自然语言输入框和低优先级文字入口；不放第二个等权 CTA。
- Agent 侧栏只用两条短消息说明边界；不能抢走上传动作，也不能展示工程状态列表。

### E02 Agent 对话构图（所有候选共同要求）

- 中央米白工作区承接当前照片/母版占位和对齐轴；下方或侧边仅保留“当前状态”事实块。不得使用中间大面积黑底或紫黑暗影。
- 右侧米白 Agent 面板显示一条用户消息、一条 Agent 复述、一块可展开的关键事实和一句下一步；底部只有一个自然语言 composer。
- 事实块最多展示“当前照片 / 母版关系 / 安全检查”三行；安全检查写成自动发生的状态，不要求用户点击。
- 不在关键帧中画 Plan A/B/C、独立诊断报告、完整 Trace、工具调用名、Provider 原始字段、分数或“思考中”动画。

## 5. Image 2 视觉稿指令

使用内置 Image 2 为 A/B/C 每套生成两张视觉方向稿（共六张），分别对应 E01、E02。视觉稿用于材质、比例、留白、层级和状态气质评审，不作为精确中文排版源文件；小字允许近似，精确文字以 HTML/SVG 为准。每套只生成这两张，不生成同一方向的额外状态图。

通用提示词骨架：

```text
Use case: ui-mockup
Asset type: desktop web UI keyframe, 1440x900 visual direction board
Primary request: premium Chinese C-end portrait-consistency Agent workspace, direct and calm like Kimi/Moonshot, one clear task and one natural-language entry, not a marketing landing page and not a photo-editing dashboard.
Composition: compact desktop shell with a narrow solid-black navigation rail only, warm ivory context/workspace/conversation surfaces, a central alignment workspace, and one right-side conversation panel only where the state needs it. Use soft purple/lilac rounded frames and a restrained purple provenance line; add one or two tiny fluorescent acid-green active nodes. No dark center, no purple-black shadow or dark-flow background.
Palette: Party Rock raw colors only — #F2F1E6, #A855F7, #C084FC, #121212/#000000, and a tiny #FF4D4D semantic accent. Do not invent colors or retune tokens.
Material: matte solid surfaces, crisp ink rules, rounded geometry, restrained tactile depth, soft opaque purple blocks and a single ribbon/trajectory on ivory. No gradients, dark-flow field, or glow.
Typography: PingFang SC-like Chinese UI type, short labels, no English marketing slogan.
Content: abstract non-identifiable portrait placeholders, a single alignment axis, concise Chinese copy, one composer, and at most one compact scoped confirmation card.
Constraints: no identifiable people, no real photos, no scores, metrics, fake progress, chain-of-thought, Plan A/B/C, extra business pages, watermarks, or duplicated buttons.
Avoid: blue, yellow, neon green, gradients, glassmorphism, cyberpunk glow, futuristic grids, dense dashboards, generic photo-editor controls.
```

E01 追加：让入口在黑色左导航之外保持米白，通过紫色柔性框/轨迹和少量荧光绿节点形成节奏；只保留 `建立母版`、`上传母版照片`、`告诉我想保留什么…` 等短文字。

E02 追加：让米白工作区承接照片对齐，右侧米白面板承接连续对话，黑色线框与紫色轨迹承接关系，事实块只显示关键状态；不要生成独立报告或复杂工具轨迹。

每张图生成后只允许一次针对性重生成。检查重点：黑色是否只在最左导航/结构出现、中央/右侧是否保持米白、紫色柔性框是否灵动而不沉重、荧光绿是否稀疏、入口是否只有一个主动作、对话是否成为 E02 的主控制面。

## 6. 可编辑交付物

1. `design/keyframes/party-rock-pingfang/candidates/candidate-review.html`：无构建依赖的候选评审页，可切换 A/B/C 与 E01/E02；评审备注可直接输入。
2. `design/keyframes/party-rock-pingfang/index.html`：上一版单一 E01/E02 原型，保留作历史基线，不得覆盖本轮候选约束。
3. `candidates/{a-archive-ribbon,b-soft-index,c-open-provenance}/figma-import/`：每套两张 1440×900 SVG。导航、上下文、米白工作区、轨迹、照片占位、对话、事实块、按钮和文字位于独立 `<g id="…">` 图层；导入 Figma 后取消编组即可继续编辑。
4. `candidates/*/raster/`：六张 Image 2 视觉方向稿；同名 `.prompt.md` 保存完整提示词、尺寸、日期、用途和检查结论。
5. `candidates/*/renders/1280/`、`candidates/*/renders/1440/`：由 SVG 源导出的两种桌面尺寸，不重复调用模型，避免视觉漂移。
6. 原四帧版本移入 `archive/v1-four-state/`，上一版 E01/E02 只作历史审阅，不属于本轮 active 候选方向。

可编辑源验收：设计师无需改业务代码即可修改标题、状态、主 CTA、紫色面积、区域宽度和对话内容；SVG 不嵌入真实用户照片、Base64、密钥、签名 URL、Provider 结果或 Trace。

## 7. 文案与状态纪律

- 页面标题 2—8 个中文字符；每条 Agent 消息最多 2—3 行。
- 每条状态同时说明事实、下一步和是否需要用户动作；没有动作就明确写“这一步不需要你操作”。
- 失败说明是否已发生外部调用；不使用“再试一次”绕过新意图/新授权。
- `结果已返回` 不等于 `已改善`；只有结构化复测允许使用“差异缩小 / 无变化 / 无法判断”。
- 用户点踩、文字不满意、scope 改变或证据不足后，显式停止当前计划族；不出现“继续自动优化”。

## 8. 输出顺序与质量检查

1. 读取冻结版 Spec、执行版 PRD、合同和规则；记录采用的冻结决策与不可展示字段。
2. 为 A/B/C 每套生成 E01/E02 Image 2 视觉方向稿（共六张）并保存 sidecar；检查图片不是空白、不是错误状态、没有真实人物或多余 slogan。
3. 生成同尺寸、同文案、同状态的 HTML/SVG 源；用 SVG 源导出 1280×800 与 1440×900。
4. 检查浏览器两个状态、SVG XML、图层 ID、文字节点、viewBox、PNG 元数据和文件树；运行 Impeccable detector 并诚实记录是否为降级扫描。
5. 执行文案扫描：不得出现旧英文 slogan、Plan A/B/C、`相似度 90%`、`一键变美`、隐藏思维链或假进度。
6. 执行视觉扫描：仅使用 Party Rock 原始 token；黑色只在左导航/结构，中央/右侧米白，紫色/淡紫柔性框与轨迹，荧光绿稀疏；无紫黑暗影、暗流、渐变或发光；E02 对话是主控制面。
7. 执行交互扫描：每套只有 E01/E02 两张主关键帧；每个状态只有一个默认 CTA；后台检查无前台确认按钮；外部处理只有一次有界授权；不声称 Streamlit、Figma 原生 `.fig` 或真实用户结果已实现。

最终报告必须同时列出：生成的文件、PNG 与 HTML/SVG 的边界、浏览器/图像/SVG/元数据检查结果、历史资产归档位置，以及仍明确标记为“尚未实现/尚未真实验证”的部分。

## 2026-09-03｜E3 Demo 与证据页的当前边界

page 6 是腾讯特效 Web 的独立候选试验入口，当前可支持“上传一张明确授权的图片→浏览器 SDK 处理→页面展示结果”；page 8 是只读 E3 脱敏证据看板。UI 设计不得把 page 8 的 receipt、hash、准入 blocker 或 Trace 原样塞进 C 端首屏；它们属于管理/审计层。页面文案必须区分“结果已返回”与“视觉差异已复测”，不得显示未经证据支持的分数、概率或泛化结论。

E3 当前有 4/4 真实 Web 回执成功，但视觉效果、共同 `VerificationResult`、供应商条款和 Card promotion 未闭合；Web Card 继续 `candidate`，正式主流程仍使用 BeautifyPic。后续 UI 映射只能消费这些真实状态，不得用候选样张替换真实结果或隐藏失败/未知状态。

## 9. Getty × Thread Track 1（2026-09-02 最新视觉稿级覆盖）

在以上产品语义与 Party Rock/苹方硬约束之上，新的执行入口是 [UI_VISUAL_DESIGN_SPEC_DETAILED.md](UI_VISUAL_DESIGN_SPEC_DETAILED.md)。它把用户提供的三栏 Agent 截图抽象为黑色稳定导航、中央任务舞台和右侧连续线程，并把 Getty `Tracing Art` 的路径叙事压缩成真实的“母版 → 当前照片 → 检查 → 结果”轨迹；不复制品牌、网站资产、摄影、Logo 或历史内容。

Track 1 只交付两个产品画面：E01 `/align`（`建立母版`、一个上传动作、一个自然语言 composer）与 E02 `/align/:session`（母版/当前照片占位、关键事实轨迹、短 Agent 消息、一次有界授权和同线程结果）。三张 Image 2 环境素材 `orbit-paper`、`folded-window`、`ink-garden` 仅作无人物氛围层，禁止遮挡标题、上传和 composer；素材来源、prompt、尺寸与商用复核边界写在 `design/visual-tracks/getty-thread-party-rock/assets/*.prompt.md`。

评审/交付入口为 [`design/visual-tracks/getty-thread-party-rock/visual-review.html`](../design/visual-tracks/getty-thread-party-rock/visual-review.html)，可切换 E01/E02、三张素材和暂停动效；分层矢量源为同目录 `figma-import/e01-entry.svg` 与 `e02-session.svg`。SVG 可导入 Figma 后继续编辑，但它们与 HTML/PNG 都是候选视觉资产，不是原生 `.fig`、Streamlit 迁移或真实用户结果。候选方向仍需产品负责人选择，之后才进入 Impeccable Critical/Audit、WCAG 2.2 AA 与 Frontend UI Gate。
