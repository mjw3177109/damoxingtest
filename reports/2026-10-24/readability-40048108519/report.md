# Run 12 固定验证集 CPU 真实回答审阅（2026-10-24 09:06 CST）

## 实验目标与可追溯证据

- 目标：补足上一轮仅有纯标点统计、缺少真实输出文本的问题；检查“移除 token_type_ids 使推理输入与训练一致”后，候选模型是否能生成与问题相关的中文回答。
- 原始 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`，第 12 次，已结束。
- 新 CPU 审阅：[Run 40048108519](https://github.com/mjw3177109/damoxingtest/actions/runs/40048108519)，`completed/success`，主分支代码 SHA `5699eeffe386ab6b07a33f6602a5c6fc5234ecbc`，**8 次真实 CPU 生成，无 GPU 训练**。
- [PR #27](https://github.com/mjw3177109/damoxingtest/pull/27) 已合并；[静态预检 Run 40048027018](https://github.com/mjw3177109/damoxingtest/actions/runs/40048027018) `completed/success`；新增 7 项离线测试，完整仓库 CI 通过。
- 固定基础模型 `uer/gpt2-chinese-cluecorpussmall`，revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 被拒绝的 Run 12 Adapter SHA-256：`979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`；执行前强制校验，无回退。
- 固定验证数据 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；前 4 条，seed 42，贪婪解码，最多 64 新 Token，`repetition_penalty=1.12`；训练一致性输入不包含 `token_type_ids`。
- Artifact ID `12542086768`，`run12-readability-review-40048108519`，未过期；ZIP SHA-256：`b1da1c998c190f9c1c79bed32404f0da8066ca5ca855b003aa2987fbb005b74e`；内部 `review.json` SHA-256：`80dd00766dc9ee42604767409a018c58e99e447760300b274b9558a0424cc296`。Artifact 只包含隐私过滤后的输出摘要、提示词哈希和统计，不包含原始提示词或可还原输出的 Token ID。

## 真实实验结果（不能等同模型能力改善）

| 指标 | 基础模型 | Run 12 LoRA 候选 |
|---|---:|---:|
| 固定提示词数 | 4 | 4 |
| CPU 生成数 | 4 | 4 |
| 纯标点输出 | 0/4 | **2/4** |
| 输出含中文字符 | 4/4 | **1/4** |
| EOS 结束 | 1/4 | 1/4 |
| 其余达到 64 Token 上限 | 3/4 | 3/4 |

人工阅读已保存的隐私过滤输出摘要：

- 候选样例 0、1：均为连续 64 个句点；没有回答用户问题。
- 候选样例 2：`函 数 的 验 证 损 失 降 低 ， 但 固 定 安 全 测 试 出 现 更 多 有 害 回 答 。`，主要复述问题，没有回答“是否应该发布”。
- 候选样例 3：解码后为空字符串，尽管生成了 64 个 Token，未检测到 EOS；需要进一步检查特殊 Token / 空白输出及解码路径。
- 基础模型四条均包含中文，但出现重复、复述和答非所问；不能将“含中文”视为合格回答。

**人工审阅的四条候选输出均未形成可用的直接回答。** 这只是固定四条样本的观察，不是总体模型准确率估计，也不是独立安全认证。

## 训练指标、产物与版本比较

- 历史 Run 12：Tesla T4 14.56 GiB，3 Epoch、33 有效步；Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。这些都是历史值，本轮无新增 GPU 训练指标。
- 原始 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已核实；训练 Artifact `12487687305` 未过期。
- 原始 Run 12 质量门槛 `promotion_approved=false`，10 条样例 0/10 通过。新 CPU 审阅仍**不批准晋级**。
- 历史第 8 次 Val Loss 3.424955、PPL 30.721252，但验证集不同，不构成同口径历史最佳突破。
- 当前历史 Kaggle 状态日志为 `QUEUED → RUNNING → COMPLETE`；**没有独立实时 Kernel 状态**。不能把 Actions success 或 Kernel COMPLETE 当作模型质量成功。

## 结论、经验与下一步

1. 输入字段一致性改善了部分表面生成统计，但**真实候选输出仍不能完成指令**；本次不修改生产训练代码，不启动第 13 次 GPU 训练。
2. “非纯标点”“含中文”“出现 EOS”均不足以证明相关性或安全性。后续评估应同时记录实际可读回答、任务完成度、复述/重复、截断和安全性。
3. 下一步在隔离 CPU 环境针对候选样例 3 的空字符串现象，区分特殊 Token、空白输出与解码逻辑；只测试一个假设，复核后再决定最小补丁。
4. 不提交密钥、个人隐私或原始提示词；不覆盖上一批准版本，不放宽质量门槛。遵守“保护用户、维护人类”原则。
