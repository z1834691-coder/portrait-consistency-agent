# Party Rock + 苹方｜E01/E02 可编辑关键帧包

> <span style="color:#C00000"><strong>最新状态（2026-09-02）：</strong>本目录根部的 E01/E02 是上一版单一视觉基线，保留用于历史回溯；本轮实际评审请打开 [`candidates/candidate-review.html`](candidates/candidate-review.html)。候选方向统一改为左侧黑色导航、中央/右侧米白、紫色柔性框/轨迹和荧光绿少量节点，上一版紫黑暗流不再作为当前构图。</span>

本包包含上一版 UI/UX Spec 的两张主关键帧交付物：E01「入口」和 E02「Agent 对话」。它用于历史回溯；本轮新的视觉候选位于 `candidates/`，用于视觉定调、产品评审、Frontend 原型和 Figma 微调。所有资产都不是 Streamlit 已实现界面，也不包含真实用户照片、Provider 结果或生产数据。

## 文件结构

```text
party-rock-pingfang/
├── index.html                              # 无依赖浏览器原型，顶部切换 E01/E02
├── figma-import/
│   ├── e01-entry.svg                       # E01 分层、可导入 Figma 的 SVG 源
│   └── e02-agent.svg                       # E02 分层、可导入 Figma 的 SVG 源
├── raster/
│   ├── e01-entry.png                       # Image 2 E01 视觉方向稿
│   ├── e01-entry.prompt.md                 # E01 完整生成提示词与检查记录
│   ├── e02-agent.png                       # Image 2 E02 视觉方向稿
│   └── e02-agent.prompt.md                 # E02 完整生成提示词与检查记录
├── renders/
│   ├── 1280/e01-entry.png, e02-agent.png   # 由同源 SVG 导出的降级帧
│   └── 1440/e01-entry.png, e02-agent.png   # 由同源 SVG 导出的桌面主帧
└── archive/v1-four-state/                  # 旧 K01—K04 四状态资产，仅作历史审阅
```

## 使用方式

1. 先打开 `candidates/candidate-review.html`，切换 A/B/C 和 E01/E02，记录希望保留的方向；根部 `index.html` 仅用于查看上一版基线。
2. 在 Figma 选择 Import，将 `figma-import/` 中的 SVG 拖入画布。每帧的暗流、导航、上下文、舞台、对齐轴、照片占位、对话、事实块、按钮和文字位于独立的语义 `<g id="…">` 图层；导入后取消编组即可继续编辑。此包不声称生成原生 `.fig` 或云端 Figma 文件。
3. PNG 是 Image 2 生成的材质、比例和气质参考，不是精确中文排版源；精确文案、颜色和布局以 HTML/SVG 为准。PNG 已嵌入 `impeccable:prompt` 元数据，并保留同名 sidecar。

## 本轮候选

详见 [`candidates/README.md`](candidates/README.md) 与 [`UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`](../../../../docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md)。A「档案游线」、B「柔性索引」、C「开放谱系」每套各两张 Image 2 PNG、两张分层 SVG 以及 1280/1440 渲染；方向选择前均不冻结。

## 历史设计基线（根部资产）

- 主题固定为 Tweakcn `Party Rock` 原始 Light/Dark token：米白 `#F2F1E6`、紫色 `#A855F7` / `#C084FC`、黑色 `#121212` / `#000000`、珊瑚 `#FF4D4D`。不调色，不改变明暗、饱和度、对比度或色相。
- 旧版面积层级和紫色暗流仅作历史记录；最新候选约束见 `candidates/README.md`：左侧黑色导航，中央/右侧米白，紫色柔性框/轨迹，荧光绿少量动态点，禁止紫黑暗影背景。
- 正式中文界面字体固定为苹方 `PingFang SC`，降级为 `Noto Sans SC` → `Microsoft YaHei`；英文和数字使用 `Arial`。
- 桌面壳保留四个轻量区域：全局导航、项目/母版上下文、中央对齐工作区、右侧 Agent 对话。每套候选只有 E01 入口和 E02 Agent 对话；上传、自动检查、澄清、一次授权、结果与停止由 E02 同一对话空间中的消息/事实块承载，不新增报告页、参数页或多计划页面。
- Agent 以自然语言作为主控制面，只显示可核实的关键事实、关键决策和下一步；不展示隐藏思维链、原始 Trace、Provider 字段、未经校准的分数、假进度或 Plan A/B/C。

## 检查边界

根部历史包已完成 SVG XML 解析、SVG 1280/1440 导出、HTML 脚本语法和静态检查；本轮候选包另行记录六张 Image 2 PNG、六张 SVG-derived renders 和候选评审页检查。Impeccable detector 若因本地 parser 依赖缺失而降级，会在最终报告中明确标注，不能替代浏览器视觉回归。

仍待后续 UI Gate 的事项：浏览器正式视觉回归、WCAG 2.2 AA、键盘/屏幕阅读器、响应式与 reduced-motion 检查、Streamlit 组件映射、真实用户照片链路、真实 Provider 效果和生产级 Figma 云文件。旧 K01—K04 位于 `archive/v1-four-state/`，不得作为当前实现依据。
