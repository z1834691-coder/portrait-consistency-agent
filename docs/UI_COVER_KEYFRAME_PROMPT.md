# 母版人像一致性 Agent｜K00 封面关键帧执行 Prompt

> 版本：`K00-COVER-PROMPT-v1.0`  
> 日期：2026-09-03  
> 状态：视觉候选执行稿；K00 是否成为正式品牌入口，仍需产品负责人单独确认。  
> 适用范围：只负责 K00 封面关键帧及其可编辑视觉资产；不改变 E01 `/align`、E02 `/align/:session`、产品合同、Provider、授权、隐私、Trace 或 Streamlit 行为。

## 1. 角色与交付目标

你是负责 Agent 产品的高级 UI/UX、视觉系统和动效设计师。请为“母版人像一致性 Agent”制作一张有强视觉抓力的 K00 封面关键帧，并把它做成可以直接在浏览器评审、可以导入 Figma 继续编辑的设计资产。

K00 的任务不是展示业务数据，也不是展示真实用户照片或处理结果，而是作为产品的入口封面，先建立“艺术档案 + 可解释对齐 + 自然语言 Agent”的气质，再让用户进入 E01。它必须与现有 E01 入口和 E02 Agent 对话保持同一套 Party Rock × 苹方视觉语言，但封面可以比工作台更大胆地使用紫色、黑色和少量荧光绿。

必须同时交付：

1. `design/visual-tracks/getty-thread-party-rock/cover/figma-import/k00-cover.svg`：1440×900、语义图层、可导入 Figma、无 base64、图片使用相对本地链接；
2. `design/visual-tracks/getty-thread-party-rock/visual-review.html` 中可切换的 K00 浏览器预览；
3. `design/visual-tracks/getty-thread-party-rock/cover/artwork/` 中的本地艺术缩略图、`SOURCES.md` 来源/许可记录和 `PROVENANCE_PROMPT.md`；
4. 一份桌面与移动端交互验收记录，说明照片墙邻近反馈、键盘焦点、触控替代、暂停动效和 reduced-motion 行为；
5. 一份清晰的“候选资产边界”说明：SVG/HTML/PNG 是设计评审源，不是原生 `.fig`、上线首页、真实 Provider 结果或已迁移的 Streamlit UI。

## 2. 已确认输入（不得自行改写）

### 2.1 参考输入

- 排版与壳的参考：用户提供的三栏 Agent 产品截图。只抽象左侧稳定导航、中央任务区、右侧连续线程、轻顶部 chrome、留白、黑色结构和自然语言入口；不要复制 Logo、品牌、频道、头像、真实文案或截图内容。
- 封面节奏参考：用户提供的红色独立设计作品截图。只抽象“顶部细导航 + 左侧短标题 + 中央进入动作 + 下半部半弧照片墙”的版式节奏、错位、重叠和滚动/靠近时的回应；不要复制红色、Logo、素材、文案、品牌或页面代码。
- 艺术感参考：Getty [Tracing Art](https://www.getty.edu/tracingart)。只抽象“先呈现路径、再展开细节”“关系线/节点”“章节化节奏”“编辑式留白”和“图像必须有材料职责”；不要复制 Getty 的图片、Logo、网页动画、人物或内容顺序。

### 2.2 颜色与字体

严格使用已经冻结的 Tweakcn Party Rock 原始 token，不调色、不改明暗度、不改饱和度、不添加新的品牌色：

| Token | 值 | K00 职责 |
|---|---|---|
| ivory | `#F2F1E6` | 标题纸片、照片卡内面、文字留白和少量底部空间 |
| purple | `#A855F7` | K00 主场、主标题承载面、进入动作的视觉节奏 |
| lilac | `#C084FC` | 柔性标签、边缘关系线和局部层次 |
| ink | `#121212` | 文字、细线、卡片轮廓、图标 |
| black | `#000000` | 顶部细导航、标题框、照片卡文字带和结构锚点 |
| acid | `#36FF9B` | 进入节点、活动点和极少量动感提示；不能铺满画面 |
| coral | `#FF4D4D` | 只作为错误/停止语义备用色，正常封面不主动使用 |

封面允许紫色成为最大面积，黑色作为顶部书脊和少量框线，米白只做标题纸片、卡片和呼吸空间；荧光绿必须稀疏。严禁紫黑暗影背景、暗流渐变、霓虹网格、玻璃拟态、发光、金属 3D、复杂花纹、大面积荧光绿、脏旧滤镜和厚重模糊阴影。

正式字体只用：

```css
font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
```

中文优先；英文只保留必要的产品标识、艺术家姓氏或开发标识，不写无业务作用的英文 slogan。标题应短、厚、直接，可以通过“黑色框 + 米白纸片 + 紫色留白”的排版关系制造张力，不靠难以阅读的装饰字体。

## 3. K00 内容与文案

封面只承担“进入产品”的任务，文案必须短而可读：

| 区域 | 精确文案 | 规则 |
|---|---|---|
| 产品短名 | `对齐` | 顶部左侧，不加营销口号 |
| 产品识别 | `人像一致性 AGENT` | 小号辅助标识，可保留 `AGENT` 作为产品类别 |
| 主标题第一行 | `从一张母版` | 放在米白纸片或黑框内 |
| 主标题第二行 | `开始对齐` | 放在紫色主场上，形成最大阅读焦点 |
| 解释 | `让每一张照片，都回到同一个可解释的标准。` | 只出现一次，控制在一行或两行 |
| 主动作 | `开始对齐` | 全屏只保留一个默认入口动作 |
| 辅助说明 | `上传照片，说出想保留的部分；检查、决策与结果留在同一条线程。` | 小号说明，不得像产品说明书 |
| 底部来源提示 | `艺术作品来源见 SOURCES.md` | 只放在设计资产/评审页，不塞进用户对话 Trace |

不要出现：`今天想把哪一张对齐到你的标准`、大段英文宣言、Plan A/B/C、诊断报告、分数、百分比、工具调用、内容安全按钮、假进度和“变美”承诺。

## 4. 1440×900 构图规格

整体采用编辑式、开口向上的半弧构图，画面要大气而有节奏，不要堆成传统 dashboard：

```text
┌────────────────────────────────────────────────────────────────────┐
│ 黑色顶部细导航：对齐 · 入口 / 对话 / 记录                         │
│                                                                    │
│ 人像一致性 AGENT        从一张母版       [进入/播放]               │
│                         开始对齐                                  │
│                                                                    │
│       ┌艺术卡┐ ┌艺术卡┐ ┌艺术卡┐ ... ┌艺术卡┐                    │
│          ╲       ╲        半弧照片墙       ╱       ╱              │
│   紫色主场，保留米白纸片、黑色线框与少量荧光绿节点               │
└────────────────────────────────────────────────────────────────────┘
```

推荐基准：

- 画布 `1440×900`；安全边距上下 `24px`、左右 `32–92px`；
- 顶部黑色导航 `72px`，只放短名、必要的入口位置和三项极简路由提示；
- 左侧标题起点约 `x=92, y=140`；第一行标题纸片宽约 `350–390px`，第二行大标题宽约 `400–520px`；
- 中央进入/播放节点位于画面上半部中央附近，圆形或柔和几何形，直径约 `72–84px`；只表达“进入”，不伪装成播放产品视频；
- 照片墙从 `y≈440` 开始，向两侧延伸至下半部；十张卡片形成开口向上的半弧，中央卡片略高，两侧逐渐下降；
- 每张卡片桌面约 `132×188px`，黑色细边 `2px`，圆角 `6px`，轻实体偏移阴影；旋转角度约从 `-18°` 到 `+19°`，重叠必须可辨认；
- 卡片标题带使用黑色实体底 + 米白字，字号不小于 `9px`（仅艺术家/作品短名）；不要把卡片做成密集信息卡；
- 底部只保留来源提示和 `K00 / COVER KEYFRAME` 等设计标记，不能侵入主动作。

## 5. 艺术照片墙素材规则

### 5.1 只能使用已登记的本地来源

不要自己生成名画，不要在线热链，不要把艺术图片上传给模型，不要使用真实用户照片或任何人像一致性结果。只使用本目录已经下载并登记的历史作品：

- `vermeer-pearl.jpg`：Johannes Vermeer，《戴珍珠耳环的少女》；
- `botticelli-primavera.jpg`：Sandro Botticelli，《春》；
- `bosch-garden.jpg`：Hieronymus Bosch，《人间乐园》；
- `arcimboldo-vertumnus.jpg`：Giuseppe Arcimboldo，《Vertumnus》；
- `leonardo-mona-lisa.jpg`：Leonardo da Vinci，《蒙娜丽莎》；
- `gainsborough-blue-boy.jpg`：Thomas Gainsborough，《蓝衣少年》；
- `rembrandt-self-portrait.jpg`：Rembrandt，《六十三岁的自画像》；
- `durer-self-portrait.jpg`：Albrecht Dürer，《1500 年自画像》；
- `goya-sleep-of-reason.jpg`：Francisco José de Goya，《理性沉睡生怪物》；
- `botticelli-venus.jpg`：Sandro Botticelli，《维纳斯的诞生》。

每张作品的 Commons 文件页、原图入口、下载日期、尺寸和授权复核提醒必须写入 [`cover/artwork/SOURCES.md`](../design/visual-tracks/getty-thread-party-rock/cover/artwork/SOURCES.md)。Commons 的 Public Domain/PD-Art 标记只是来源记录，不是跨地区商业上线的法律意见；正式上线前仍需按目标市场、馆藏摄影复制品和品牌用途逐张复核。现代仍受保护的 Dalí、Magritte 等作品不进入本轮。

### 5.2 图片职责与裁切

- 图片只提供“艺术档案墙”的文化质感，不证明人像身份、质量、相似度、审美或 Provider 效果；
- HTML 每个 `<img>` 必须有准确的中文 `alt`、固定 `width/height`、`object-fit: cover` 和 `decoding="async"`；首屏中央两张可 `loading="eager"`，其余 `loading="lazy"`；
- SVG 使用语义化 `artwork-*` 图层和相对路径，不内嵌 base64；设计师在 Figma 中应能单独替换每张图片；
- 保留来源和替换规则，但不要把馆藏 URL、版权字段、图片 hash 或路径写入 C 端 Agent Trace；
- 在生产候选阶段可转 WebP/AVIF，但必须保留可追溯的 JPG/PNG 回退，不扩大源图尺寸，不直接加载原始馆藏大图。

## 6. 交互与动效

K00 不增加新的业务子页面；它只是入口封面，点击主动作后进入 E01 `/align`。

### 6.1 照片墙邻近反馈

当鼠标/触控板指针进入照片墙：

1. 计算每张卡片中心到指针的距离；
2. 只有最近的一张卡片向上移动约 `24px`，其余卡片保持原位；
3. 卡片保持原有旋转，不能缩放成弹窗、不能跳出画布、不能遮挡标题或进入动作；
4. 指针离开照片墙，所有卡片回到原位；
5. 键盘 `Tab` 聚焦时使用同样的抬升和清晰焦点环；`Enter/Space` 激活该卡片的静态标签/选中反馈，不打开新的报告页；
6. 触控设备没有 hover 时，点击或聚焦提供等价的静态选中反馈；
7. `prefers-reduced-motion: reduce` 或用户点击“暂停动效”时，卡片不抬升、不循环、不自动轮播，但焦点环、标签和可操作性仍然保留。

动效只改 `transform` / `opacity`，时长约 `240ms`，曲线 `cubic-bezier(.22,.8,.24,1)`；不要动画化 `top/left/width/height`，不要使用持续视差、闪烁、旋转或 loading 假象。

### 6.2 入口动作

- `开始对齐` 按钮和中央进入节点使用同一 `data-cover-enter` 行为；
- 点击后切换到 E01，并把焦点移动到 E01 主标题或上传控件；
- 按钮具有明确中文可访问名称、`focus-visible` 外环和至少 `44×44px` 触控区域；
- 动效暂停不影响点击，键盘和触控不依赖 hover；
- 浏览器返回、Esc 和移动端返回路径必须能回到封面或关闭封面，不产生重复 Provider 调用。

## 7. 可访问性、响应式与性能

### 7.1 可访问性

- 主标题、主动作、照片墙和来源提示拥有语义标题/label；
- 颜色不是唯一状态通道；荧光绿同时配合文字或图标，不把绿色当作“成功分数”；
- 所有卡片均可按 Tab 访问，焦点环使用 coral/ink 与背景形成清晰边界；
- 图片 alt 说明艺术家与作品名，不描述“真实用户”或身份；
- 屏幕阅读器不会把装饰路径读成业务事实；纯装饰线使用 `aria-hidden="true"`；
- 文字在 1440、1280、1024、768、414、375 宽度下不被裁切，不依赖浏览器缩放禁用；
- reduced motion、键盘、触控和无 hover 的静态等价路径必须可用。

### 7.2 响应式降级

- `≤1024px`：顶部导航和标题保持顺序，照片墙缩短弧宽，卡片变为纵向可滚动但不产生页面级横向滚动；
- `≤600px`：标题字号收敛，中央进入节点保持在可触达区域，照片卡片约 `76×112px`，半弧仍可辨认；
- 移动端不显示复杂来源表格；来源通过评审页链接保留；
- 不能为适配移动端把主动作藏入菜单或只留图像没有文字。

### 7.3 性能

- 图片预留宽高或 `aspect-ratio`，目标 CLS `<0.1`；
- 首屏最多两张 eager，其余 lazy；长边约 `900px`，不要加载原始大图；
- 邻近计算使用 `requestAnimationFrame`，缓存卡片中心，页面不可见时停止监听；
- 动画每帧只使用 transform/opacity，避免读取布局和写入布局交错；
- 图片和 prompt provenance 必须可扫描，任何缺失来源的 raster 不进入活动 K00。

## 8. 可编辑文件结构

`k00-cover.svg` 必须至少包含下列可独立选择的语义图层：

```text
cover-background
cover-nav
cover-hero
cover-side-note
cover-enter-marker
cover-arc
  artwork-vermeer-pearl
  artwork-botticelli-primavera
  artwork-bosch-garden
  artwork-arcimboldo-vertumnus
  artwork-leonardo-mona-lisa
  artwork-gainsborough-blue-boy
  artwork-rembrandt-self-portrait
  artwork-durer-self-portrait
  artwork-goya-sleep-of-reason
  artwork-botticelli-venus
cover-footer
```

Figma 导入说明：SVG 使用相对图片链接，导入时若 Figma 需要重新定位图片，按 `SOURCES.md` 和文件名逐张替换；不要把“可导入 SVG”写成已经生成原生 Figma 云文件。HTML 预览是交互验收源，SVG 是可编辑结构源，PNG 只做静态截图证据。

## 9. 反模式清单（发现一项即退回）

- E01/E02 出现任何环境图、纹理、暗流、紫黑背景或新插画；
- K00 出现现代受保护艺术家的未经许可图片、在线热链、AI 生成名画、真实用户脸或结果图；
- 中央/右侧变成黑底，紫色被做成黑色发光阴影，或荧光绿形成大面积背景；
- 出现第二个同权重主 CTA、Plan A/B/C、独立诊断页、工具日志、分数、百分比、假 loading 或营销 slogan；
- 关键动作只能 hover 发现，键盘无焦点或移动端没有替代；
- 卡片重叠导致作品、标题、按钮、来源提示无法阅读；
- SVG 只有一张扁平截图、无语义图层、内嵌 base64 或丢失相对图片链接；
- 将样张、回执或 K00 视觉资产描述为“已上线”“已证明一致性”“Provider 已通过”或“原生 Figma 文件”。

## 10. 完成验收清单

执行完成后，逐项输出结果，不要只说“已完成”：

- [ ] K00 1440×900 结构与文案通过 5 秒首屏理解检查；
- [ ] 紫色主场、黑色顶部书脊、米白纸片/卡片、少量荧光绿的面积层级符合要求；
- [ ] E01/E02 仍为纯米白中央/右侧，活动文件不加载 `orbit-paper`、`folded-window`、`ink-garden`；
- [ ] 十张本地艺术图逐张有来源、日期、尺寸、alt 和地域复核备注；
- [ ] HTML 可切换 K00，照片墙最近卡片 hover/focus 抬升，点击入口回到 E01；
- [ ] reduced-motion、暂停动效、键盘 Tab/Enter、触控静态反馈均可用；
- [ ] 375/414/768/1024/1280/1440 宽度无页面级横向滚动、标题裁切或焦点遮挡；
- [ ] SVG 通过 XML 校验并可渲染；所有图层可在 Figma 中继续编辑；
- [ ] provenance 扫描无缺失，HTML/SVG 不含 base64 或旧环境素材引用；
- [ ] 最终报告列出文件路径、截图路径、测试命令、已知限制和未冻结项；
- [ ] 明确声明：K00 是视觉候选，不改变产品合同、Provider 权限、隐私、结果保留、Trace 或 Streamlit 实现。

## 11. 当前执行结果记录模板

```text
交付：
- K00 HTML：
- K00 Figma-import SVG：
- 艺术来源清单：
- 桌面截图：
- 移动截图：

验收：
- XML / SVG：PASS | FAIL
- provenance：PASS | FAIL
- K00 hover/focus/click：PASS | FAIL
- reduced-motion / pause：PASS | FAIL
- E01/E02 无栅格素材：PASS | FAIL
- 响应式：PASS | FAIL

边界：
- K00 是否进入正式品牌入口：未冻结
- 艺术品商业上线许可：逐张待法务复核
- Streamlit / Provider / 真实用户效果：本 Prompt 不涉及
```
