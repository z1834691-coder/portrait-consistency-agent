# 母版人像一致性 Agent｜视觉权威入口

<!-- visual-authority 1 -->

> 状态：视觉候选阶段；Party Rock 与苹方已确认，Getty × Thread Track 1 尚未冻结为最终实现。
> 本文件只做视觉入口和优先级说明；产品关系、状态机、权限、Provider、隐私和结果边界以执行版 PRD 与合同为准。

## 当前视觉世界

- **核心命题：**一张可呼吸的档案纸，承载一个有判断力的 Agent。
- **版式语法：**左侧稳定导航 + 中央任务舞台 + 右侧连续 Agent 线程；自然语言是主控制面。
- **参考抽象：**用户提供的三栏 Agent 截图（导航/任务/线程关系）与 [Getty Tracing Art](https://www.getty.edu/tracingart)（关系轨迹、先路径后细节、编辑式留白、混合媒介）。不复制品牌、Logo、摄影、文案或网站代码。
- **材料气质：**海外产品的克制、博物馆档案的留白、Party Rock 的紫色节奏和少量荧光绿动感；拒绝紫黑暗影、渐变、玻璃拟态、霓虹网格和后台仪表盘。E01/E02 保持纯米白工作面；K00 封面才允许紫色主场与公共领域艺术照片墙。

## 已确认的视觉输入

| 输入 | 决策 |
|---|---|
| 色彩 | Tweakcn Party Rock 原始 token，不改色相、饱和度、明暗度或对比度 |
| 字体 | PingFang SC；缺字回退 Noto Sans SC / Microsoft YaHei |
| 黑色范围 | 仅最左侧导航书脊和必要结构线 |
| 中央/右侧 | 连续米白工作面 |
| 紫色 | 柔性圆角框、标签、轨迹、主动作和局部焦点 |
| 荧光绿 | 少量活动/对齐节点，不做大面积底色 |
| 页面范围 | E01 `/align` 入口、E02 `/align/:session` Agent 对话、K00 封面评审关键帧 |

## 权威文件与优先级

1. 产品和合同事实：`docs/母版人像一致性Agent-执行版PRD.md`、`docs/PRODUCT_RULES.md`、`docs/CONTRACTS.md`。
2. 视觉方向原则：[`docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md`](docs/UI_STYLE_DIRECTION_GETTY_PARTY_ROCK.md)。
3. 视觉稿级细节、尺寸、文案、素材、动效和验收：[`docs/UI_VISUAL_DESIGN_SPEC_DETAILED.md`](docs/UI_VISUAL_DESIGN_SPEC_DETAILED.md)。
4. 当前可交互候选和可编辑源：[`design/visual-tracks/getty-thread-party-rock/README.md`](design/visual-tracks/getty-thread-party-rock/README.md)。

若文件之间出现冲突，产品/合同事实优先；已确认色彩与字体优先于工具自动生成的通用设计系统；视觉候选不得反向改变业务合同。

## 当前候选与未冻结项

- 当前候选：Getty × Thread Track 1，包含 E01/E02（纯米白背景）和 K00 封面（公共领域艺术照片墙）、HTML/CSS 评审页和三张分层 SVG。
- A/B/C 方向包是历史探索，可回溯或借鉴结构；不自动覆盖 Track 1。
- 已移除活动素材：`orbit-paper`、`folded-window`、`ink-garden` 不再被 E01/E02 HTML/SVG 加载，完整文件与 prompt 保留在 `design/visual-tracks/getty-thread-party-rock/archive/ambient-assets-v1/`。
- 尚未冻结：1440×900 三栏最终比例、K00 封面构图是否进入正式品牌、照片墙素材的逐张商用复核、是否映射到 Streamlit。
- SVG 可导入 Figma 后编辑；K00 的 JPG 仅为有来源的艺术档案墙，E01/E02 无栅格素材；任何关键帧都不代表真实照片结果。

## 质量底线

- 首屏 5 秒内理解下一步：一个上传动作 + 一个自然语言入口。
- 只展示关键事实、关键决策和下一步；不展示 Plan A/B/C、分数、假进度、工具日志、完整 Trace 或隐藏思维链。
- E01/E02 不加载图像；K00 只加载 `cover/artwork/SOURCES.md` 记录的公共领域历史艺术作品，来源可追溯；照片墙支持键盘焦点、暂停和 `prefers-reduced-motion` 静态版本。
- 方向确认后才进入 Impeccable Critical/Audit、WCAG 2.2 AA、Frontend 映射和 Streamlit UI Gate。
