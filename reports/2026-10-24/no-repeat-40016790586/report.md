# Run 12 no-repeat-bigram CPU 对照实验（2026-10-24）

## 状态与可审计证据
- 原始 GPU 训练：[Actions Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`；33 步，候选质量门槛未通过。
- 本次 **仅 CPU 推理**：[Actions Run 40016790586](https://github.com/mjw3177109/damoxingtest/actions/runs/40016790586)，`completed/success`，40/40 次生成。Artifact ID `12529420164`，`diagnostics.json` SHA-256 `b7bd05b3fb1007c6633d8bf3bac3ecf973e70c5bed666899a09b67a606b458e6`。
- 代码 PR [#18](https://github.com/mjw3177109/damoxingtest/pull/18) 合并 SHA `a0edcef7355e39c3a2592f917038ac103db188e3`，静态预检 [40016721814](https://github.com/mjw3177109/damoxingtest/actions/runs/40016721814) `success`。新增 5 项离线单测，Python 编译检查通过。
- 固定验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型 commit `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；被拒绝 Adapter 权重 SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。

## 假设、配置与结果
假设：在相同固定提示词、基础模型、Adapter、贪婪解码、`repetition_penalty=1.12`、`max_new_tokens=64`、seed 42 下，**仅**改变 `no_repeat_ngram_size`（0→2）能减少连续重复标点。对基础模型和被拒绝候选各测试 10 条提示词 × 两种设置。历史控制组与 Run `39950178751` 一致性检查通过。

| 模型 / 设置 | 纯标点 | EOS | 达 64 Token 上限 | 最长相同字符连续长度均值 |
|---|---:|---:|---:|---:|
| 基础 / control | 7/10 | 0/10 | 10/10 | 45.4 |
| 基础 / no-repeat-bigram | 0/10 | 0/10 | 10/10 | 2.2 |
| 候选 / control | 10/10 | 0/10 | 10/10 | 64.0 |
| 候选 / no-repeat-bigram | **8/10** | 8/10 | 2/10 | 2.1 |

## 结论与失败教训
- **可确认**：禁止重复二元组改变了重复字符模式，并明显缩短了连续相同字符段。候选模型的纯标点输出仍为 **8/10**；EOS 频率变化不代表回答正确。
- **不可确认**：没有保存/审核新的完整中文回答，不能宣称可读性、准确性、安全性或模型权重得到改善；不得将减少重复等同于模型进化。
- **经验**：机械解码约束可以改善表面重复指标，但可能只让输出变短或换一种无意义形式；未来质量门槛必须独立包含人工可读性、事实与安全检查，并与历史最佳采用同一验证集对比。
- **晋级**：`promotion_approved=false`。本轮无 Kaggle GPU 训练，无新 Train Loss、Val Loss 或 PPL，不修改训练配方、数据、权重和安全机制；保留已批准模型及回滚路径。
- **下一步**：在隔离环境审阅少量实际中文输出，先验证是否有完整、有意义、安全的回答；若仍不合格，再设计固定验证集的单变量训练实验，不盲目扩大 GPU 配额。Kaggle Kernel 实时状态仍需独立查询，本实验不构成其运行证明。

本报告仅保存汇总统计、SHA 与运行证据，不包含原始提示词、模型回答、个人信息或凭据。
