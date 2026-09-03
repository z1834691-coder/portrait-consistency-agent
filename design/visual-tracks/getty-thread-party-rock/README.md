# Getty × Thread｜Party Rock 视觉 Track 1

> 状态：候选探索，尚未冻结为最终实现
>
> 交付：E01 `/align` 入口、E02 `/align/:session` Agent 对话、K00 封面、两张纯米白产品关键帧、一张带公共领域艺术照片墙的封面关键帧、三张带语义图层的 Figma 可导入 SVG、一个可交互评审 HTML。

## 这条 Track 学什么

这条 Track 把用户提供的三栏 Agent 截图抽象成“黑色导航书脊 + 米白任务舞台 + 连续线程”，再把 Getty Tracing Art 的“对象—关系—证据—下一步”叙事压缩成一条真实状态轨迹。它不复制任何品牌、Logo、文案、人物、艺术品图片或网站代码。[Getty Tracing Art](https://www.getty.edu/tracingart)

## 目录

- `visual-review.html`：可在浏览器中打开的评审页。顶部只属于评审工具，可切换 E01/E02/K00 和动效暂停；K00 的照片墙支持鼠标邻近抬升、键盘聚焦和 reduced-motion。
- `figma-import/e01-entry.svg`：E01 的纯米白背景分层矢量源，图层 ID 为 `nav`、`context`、`stage`、`trajectory`、`composer`。
- `figma-import/e02-session.svg`：E02 的纯米白背景分层矢量源，图层 ID 为 `nav`、`context`、`stage`、`thread`、`trajectory`、`composer`。
- `cover/figma-import/k00-cover.svg`：K00 封面的分层矢量源，包含 `cover-background`、`cover-nav`、`cover-hero`、`cover-arc`、`artwork-*`、`cover-cta` 等可编辑图层；图片使用相对链接，可在 Figma 导入后替换。
- `cover/artwork/*.jpg`：从 Wikimedia Commons 下载的 10 张历史艺术作品缩略图，仅供 K00 封面照片墙使用。
- `cover/artwork/SOURCES.md`：每张作品的艺术家、馆藏线索、来源页、下载入口、公共领域判断与地域复核边界。
- `archive/ambient-assets-v1/`：上一轮 `orbit-paper`、`folded-window`、`ink-garden` Image 2 素材及 prompt 的可回滚归档；活动 E01/E02 不再引用。

## 视觉与产品边界

- 颜色严格使用 Party Rock 原始 token；字体严格使用苹方，缺字才回退到 Noto Sans SC / Microsoft YaHei。
- 黑色只做最左侧导航和结构线；中央、右侧保持米白。紫色通过局部柔性框、轨迹与焦点形成节奏；荧光绿只做小节点。
- E01/E02 的背景现在是纯 Party Rock 米白，不加载任何环境图、纹理或紫黑暗流；K00 为封面例外，允许紫色主场、黑色顶部书脊和少量荧光绿，并使用有来源记录的公共领域艺术作品照片墙。
- 不展示 Plan A/B/C、KPI、分数、假进度、工具调用、原始 Trace、隐藏思维链或独立诊断报告页。
- 上传、自然语言意图、自动检查、一次有界外部授权、结果和反馈均在同一任务/线程内表达。真实权限、Provider、照片和结果合同仍以项目执行版 PRD 为准。
- SVG 是可导入 Figma 的矢量参考源，不是云端 `.fig` 文件；导入后可继续编辑图层、文字、线条和占位形状。K00 的 JPG 只用于艺术档案墙，不等同于真实处理结果；E01/E02 不加载栅格素材。

## 打开与检查

```bash
open design/visual-tracks/getty-thread-party-rock/visual-review.html
```

建议在 1440×900、1280×800、1024×768、768×1024、414×896、375×812 逐一查看；同时切换系统 `prefers-reduced-motion`。当前为视觉候选，不代表 Streamlit 已迁移或真实 Provider 效果已验证。

## 资产来源与商用边界

活动 K00 的艺术图片来自 Wikimedia Commons 文件页并在 `cover/artwork/SOURCES.md` 留存来源与下载日期；选取历史作品是为了降低现代超现实主义版权风险，但不等于跨地区商用许可。上线前仍需按目标市场、馆藏条款和具体复制品逐张复核；本 README 不替代法律意见。上一轮 Image 2 素材只保留在 `archive/ambient-assets-v1/`，不再参与活动关键帧。
