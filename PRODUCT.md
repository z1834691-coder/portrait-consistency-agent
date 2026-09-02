# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

主要用户是希望把自己授权的多张人像照片向一张已确认的本人母版靠拢的 C 端用户。用户不需要学习修图参数，而是上传照片并用自然语言表达目标。

## Product Purpose

产品通过母版、当前照片和 Agent 对话，把用户的自然语言目标转换为可验证的诊断、受约束计划和结果。成功意味着用户能清楚知道当前任务、Agent 正在做什么、是否需要一次授权，以及结果是否有真实复测依据。

## Positioning

它是一个 language UI 优先的人像一致性 Agent：聊天承接目标与反馈，工作区承接照片和可验证结果；正常链路不要求用户选择多个方案或逐项操作后台检查。

## Operating Context

桌面网页优先，参考 Kimi 与 Moonshot 的简洁导航和自然语言入口。V0 以一个主页面和一个 Agent 对话子页面为核心；复杂证据、执行记录和治理信息进入第二层或管理员空间。

## Capabilities and Constraints

现有产品合同、状态机、隐私/授权边界、Provider 与复测事实保持不变。质量、同人、内容安全和依据查询可在满足既有同意边界后自动运行；外部图片处理仍需一次绑定范围的明确授权。结果图暂不承诺跨会话持久化。Party Rock、PingFang SC、左侧黑色导航、中央/右侧米白工作面、紫色柔性框/轨迹、荧光绿少量动态点以及轻量四区工作台语义已经冻结为视觉候选硬约束；历史 A/B/C 构图与最新 Getty × Thread Track 1 的具体组件、可访问性和 Streamlit 迁移仍需 UI Gate。

## Brand Commitments

采用简洁、直接、中文优先、低装饰密度的 Agent 工作台；视觉参考用户提供的 Kimi、Moonshot 与 Party Rock 截图，并吸收 Getty `Tracing Art` 的关系轨迹/编辑叙事语法。正式界面视觉使用 [Tweakcn Party Rock](https://tweakcn.com/themes/cmlqxbfu8000004joajt9gs64) 原始 Light/Dark token，正式界面字体为苹方（PingFang SC）；当前候选统一为左侧黑色导航、中央/右侧米白、紫色/淡紫柔性框与轨迹、荧光绿少量活动节点、黑色线框与文字结构。禁止紫黑暗影背景、暗流、渐变、发光网格或密集卡片。四元黑体及其他字体仅保留为后续品牌字标或实验候选，不进入当前 UI 实现；A/B/C 三套方向在负责人选择前不冻结。

## Evidence on Hand

产品执行版 PRD、专家合同/规则文档、现有代码与测试、用户提供的 Kimi/Moonshot/Party Rock 截图，以及三条 Tweakcn 主题链接。产品负责人已明确选择 Party Rock 与苹方；A「档案游线」、B「柔性索引」、C「开放谱系」每套各两张 Image 2 方向稿、HTML 评审页和 SVG/Figma 导入源已作为历史探索保留，旧 K01—K04 与上一版单一 E01/E02 仅作历史回溯。最新的 Getty × Thread 精细化视觉 Track 1（E01/E02、三张无人物 Image 2 环境素材、分层 SVG、可交互 HTML）是当前候选评审对象，仍未冻结；Streamlit 尚未完成视觉迁移。主题原始 token 与生成素材的正式可商用授权仍需在实现前单独核验。

## Product Principles

- 自然语言是主要入口，GUI 只承载必要的选择与授权。
- Agent 自动完成可安全完成的步骤，但不绕过副作用授权。
- 用户看到关键事实、决策和下一步，不被迫阅读隐藏思维链或工程 Trace。
- 结果、Provider 回执和复测改善必须分开表达。

## Accessibility & Inclusion

桌面优先但保留基础响应式降级；关键状态不能只靠颜色或动效表达，支持键盘焦点、屏幕阅读器标签和 reduced motion。
