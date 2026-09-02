# Getty × Thread｜Party Rock 视觉 Track 1

> 状态：候选探索，尚未冻结为最终实现
>
> 交付：E01 `/align` 入口、E02 `/align/:session` Agent 对话、三张 Image 2 环境素材、两张带语义图层的 Figma 可导入 SVG、一个可交互评审 HTML。

## 这条 Track 学什么

这条 Track 把用户提供的三栏 Agent 截图抽象成“黑色导航书脊 + 米白任务舞台 + 连续线程”，再把 Getty Tracing Art 的“对象—关系—证据—下一步”叙事压缩成一条真实状态轨迹。它不复制任何品牌、Logo、文案、人物、艺术品图片或网站代码。[Getty Tracing Art](https://www.getty.edu/tracingart)

## 目录

- `visual-review.html`：可在浏览器中打开的评审页。顶部只属于评审工具，可切换 E01/E02、环境素材和动效暂停；产品画面本身没有额外的候选控制。
- `figma-import/e01-entry.svg`：E01 的分层矢量源，图层 ID 为 `nav`、`context`、`stage`、`trajectory`、`art`、`composer`。
- `figma-import/e02-session.svg`：E02 的分层矢量源，图层 ID 为 `nav`、`context`、`stage`、`thread`、`trajectory`、`composer`。
- `assets/*.png`：Image 2 生成的无人物超现实环境素材，供 HTML 作为装饰环境层使用。
- `assets/*.prompt.md`：每张素材的完整生成 prompt、用途、尺寸和限制。

## 视觉与产品边界

- 颜色严格使用 Party Rock 原始 token；字体严格使用苹方，缺字才回退到 Noto Sans SC / Microsoft YaHei。
- 黑色只做最左侧导航和结构线；中央、右侧保持米白。紫色通过局部柔性框、轨迹与焦点形成节奏；荧光绿只做小节点。
- 不展示 Plan A/B/C、KPI、分数、假进度、工具调用、原始 Trace、隐藏思维链或独立诊断报告页。
- 上传、自然语言意图、自动检查、一次有界外部授权、结果和反馈均在同一任务/线程内表达。真实权限、Provider、照片和结果合同仍以项目执行版 PRD 为准。
- SVG 是可导入 Figma 的矢量参考源，不是云端 `.fig` 文件；导入后可继续编辑图层、文字、线条和占位形状。HTML 中的 PNG 只用于材质/氛围，不等同于真实处理结果。

## 打开与检查

```bash
open design/visual-tracks/getty-thread-party-rock/visual-review.html
```

建议在 1440×900、1280×800、1024×768、768×1024、414×896、375×812 逐一查看；同时切换系统 `prefers-reduced-motion`。当前为视觉候选，不代表 Streamlit 已迁移或真实 Provider 效果已验证。

## 资产来源与商用边界

PNG 由本项目使用 Image 2 内置生成工具生成并保存到本目录；没有输入真实人像、品牌资产或 Getty 素材。是否可以用于最终商业发布，仍需在上线前按实际模型/账户条款完成一次版权与许可复核；本 README 不替代法律意见。
