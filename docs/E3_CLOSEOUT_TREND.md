# E3 收尾趋势与推进树

这张树是当前 Tencent Effect Web 候选从“单次浏览器 Smoke”走到“受邀私有 Demo 可用”的可追溯入口。它只记录项目事实，不把候选能力夸写成生产能力。

```text
E3 Tencent Effect Web 收尾
├─ A 证据盘点与样本预检                         ✅ 已完成
│  ├─ 参考图 1 张、目标图 3 张、异常 PNG 1 张       ✅ 5 个样本可回放
│  ├─ 结果/输入哈希与 receipt 合同                 ✅ 离线通过
│  └─ 批量失败隔离                                ✅ 8/8 fixture 通过
├─ B 浏览器结果 → 共同 VerificationResult         ✅ 已实现
│  ├─ 一次性 request_ref / input-output hash 校验   ✅
│  ├─ 结果只在会话内存，账本只留脱敏事实            ✅
│  └─ Web 与 REST 共用 8C 验证器                   ✅ fixture smoke 通过
├─ C 真实多样本视觉证据                           ⏳ 等待当前私有页新回执
│  ├─ 每张目标图取得可关联 request_ref              ⏳
│  ├─ 每张结果图完成共同 VerificationResult         ⏳
│  └─ 至少一张改善，且无目标图恶化                  ⏳
├─ D 供应商与范围证据                             ✅ 私有 Demo 口径已建立
│  ├─ 官方 Web/静态图/License/价格/隐私资料          ✅
│  ├─ 生产地区、留存、正式单图成本                   ⚠️ 公开资料未确认
│  └─ promotion_scope=private_demo_beta              ✅
├─ E Card promotion                               ⏳ C 完成后自动准入评估
│  ├─ 所有准入字段为真                              ⏳
│  ├─ 确定性脚本原子写 Card                          ⏳
│  └─ Registry/Meta-Agent 只在私有 Demo scope 可选   ⏳
└─ F 全量 QA、部署与回滚                            ⏳ E 后重跑
   ├─ pytest / ruff / compileall / diff check        ⏳
   ├─ Cloud 重建后重新打开 E3 page                   ⏳
   └─ 任一证据退化可回退 candidate                   ✅ 设计已具备
```

## 当前趋势判断

| 阶段 | 已有证据 | 还不能推出的结论 |
|---|---|---|
| 工程交接 | Web 回执可以安全进入共同 `ProviderRun → VerificationResult` | 不能推出视觉效果稳定 |
| 单图真实 Smoke | 浏览器曾返回真实结果，且不落盘图片 | 不能推出多样本泛化 |
| 供应商核验 | 官方资料说明静态图、域名、测试 License 与价格 | 不能推出生产区域/留存/单图成本已确认 |
| 晋级 | 只有 C 的真实多样本证据、D 的私有范围解释、全量 QA 全部通过才允许 | `verified` 仅限 `private_demo_beta`，不等于公网生产 |

## 自动推进规则

1. 本地可完成的合同、代码、测试、报告和文档不等待人工；每一步都写入 progress/decision log。
2. 需要用户照片上传或腾讯真实出站时，只在临门一步要求一次传输确认；确认后按样本顺序运行，不重复生成同一请求代次。
3. 某张图片失败不阻塞其他样本，但必须保留失败原因和隔离证据；若所有目标都无法完成共同复测，则保持 `candidate`。
4. Agent/RAG 可以选择或提出策略，但不能制造结果、绕过权限、修改准入状态；promotion 只能由确定性命令在全部 Gate 为真时执行。
5. 晋级后如域名、License、SDK、数据范围或视觉回归变化，立即重新评审；无法确认时自动降级回 `candidate`。

## 证据入口

- E3 页面：`pages/9_腾讯特效Web_E3真实闭环.py`
- E3 预检：`reports/effect_web_e3_preflight_v1.html`
- E3 脱敏清单：`reports/effect_web_e3_live_manifest_v1.json`
- E3 证据报告：`reports/effect_web_e3_evidence_v1.html`
- 供应商资料：[TENCENT_EFFECT_WEB_VENDOR_EVIDENCE_2026-09-04.md](TENCENT_EFFECT_WEB_VENDOR_EVIDENCE_2026-09-04.md)
- 晋级命令：`scripts/promote_effect_web_card.py`
