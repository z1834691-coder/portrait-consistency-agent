# `/align` · E01 入口页面覆盖

本页覆盖 `MASTER.md` 的通用 AI-Native 建议，优先级低于项目已冻结的 Party Rock 与苹方决定，但高于通用模板中的紫色/粉色主题、Space Grotesk、DM Sans、Hero + Testimonials 模式。

## 页面任务

五秒内让用户理解：这里是一个人像一致性任务；下一步只有上传母版照片，之后可以直接对 Agent 说目标。页面只保留一个上传动作和一个自然语言 composer，不展示 dashboard、指标、计划列表或营销 slogan。

## 壳与比例

- 1440×900：`236px` 黑色全局导航 + 中央米白工作区 + `352px` 米白 Agent 线程。
- 中央工作区是唯一主舞台；右线程只承担连续旁白，不是独立报告。
- 黑色只出现于最左侧导航和必要结构线；中央/右侧始终为 `#F2F1E6`。
- 评审稿中的顶部候选切换属于设计工具，不进入产品壳。

## Token 覆盖

```css
--ivory: #F2F1E6;
--purple: #A855F7;
--lilac: #C084FC;
--ink: #121212;
--black: #000000;
--acid: #36FF9B;
--coral: #FF4D4D;
--font-ui: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
```

禁止使用 Master 中的 `#7C3AED`、`#EC4899`、`#FAF5FF`、Space Grotesk 或 DM Sans 作为产品 token；它们只是检索脚本的通用候选。

## 首屏顺序

1. 导航：`对齐` 当前项、`母版`、`记录`，底部 `设置`、`帮助`。
2. 上下文：`人像一致性项目 / 入口`、`等待母版`。
3. 短标题：`建立母版`。
4. 上传框：`上传母版照片` → `选择照片`。
5. 关系预览：`上传` → `同一条 Agent 线程`。
6. composer：`直接告诉我想保留什么……`。

环境图是装饰层，首屏只 eager-load 一张，并且永远不覆盖上传框和 composer。所有文案使用苹方，正文至少 16px，按钮触摸区至少 44px。

## 动效与无障碍

- 只允许 `transform/opacity`；环境素材约 22 秒低幅呼吸，进入序列 320ms。
- 提供可见 `暂停动效`，`prefers-reduced-motion: reduce` 时默认静止。
- 任何图标均为同一套线性 SVG；不得使用 emoji；独立图标按钮必须有 `aria-label`。
- 主标题、上传动作和 composer 有可见 focus；状态通过文字 + 节点同时表达。
