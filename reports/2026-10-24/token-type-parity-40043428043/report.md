# Run 12 token_type_ids 训练/推理输入一致性审计（2026-10-24 08:10 CST）

## 证据与假设

- 原始 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，代码 SHA 647b909a994441e3affa3f65fc46f9d0acb2c958；Tesla T4 14.56 GiB，3 Epoch、33 有效步，已结束。
- 新 CPU 对照：[Run 40043428043](https://github.com/mjw3177109/damoxingtest/actions/runs/40043428043)，completed/success，40 次真实生成；[PR #25](https://github.com/mjw3177109/damoxingtest/pull/25) 已合并，主分支 SHA b11dc3416b2bc1134693da42483f8a5ddf868e62；静态预检 [Run 40043374029](https://github.com/mjw3177109/damoxingtest/actions/runs/40043374029) 成功，新增 6 项离线测试。
- 新 Artifact ID 12540092198，未过期；ZIP digest sha256:6ab66c9b4087653a0fff361ea4bef37c0581a4fdce772493d4369bcec1fbc407；已下载并复核 diagnostics.json，原始 JSON SHA-256 为 6e7592a4f84a9c3aa08eb4ebb59a7f947afd116ffebc38115c7abefb5f9eb56d。
- 固定基础模型 uer/gpt2-chinese-cluecorpussmall，revision c2c0249d8a2731f269414cc3b22dff021f8e07a3；拒绝晋级的 Run 12 Adapter SHA-256 979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c，实验前校验。
- 固定验证集 SHA-256 5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f；前 10 条提示词，seed 42，贪婪解码、64 新 Token、repetition_penalty=1.12。
- 假设：训练 response_only_collator 只提供 input_ids、attention_mask、labels，而推理 BertTokenizerFast 额外返回 token_type_ids 并通过 generate 传入 GPT-2。只在推理端移除该字段，其余不变。

## 真实结果

| 指标 | 基础模型：原始→训练输入一致 | LoRA 候选：原始→训练输入一致 |
|---|---|---|
| 纯标点输出 | 7/10 → **3/10** | 10/10 → **7/10** |
| EOS 结束 | 0/10 → 1/10 | 0/10 → 1/10 |
| 达 64 Token 上限 | 10/10 → 9/10 | 10/10 → 9/10 |
| 最长连续相同字符均值 | 45.4 → **20.1** | 64.0 → **45.0** |
| 首个生成 Token 改变 | 7/10 | 3/10 |

原始控制组 7/10、10/10 与历史 [Run 39950178751](https://github.com/mjw3177109/damoxingtest/actions/runs/39950178751) 一致。此实验说明额外 token_type_ids **确实影响**本组生成行为，但候选移除后仍有 7/10 纯标点，不能宣称根因唯一、模型修复成功或回答质量提升。未保存原始输出文本，未人工审阅中文回答。

## 历史指标、产物和判定

- Run 12 历史 Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599，同轮基线 Val Loss 3.389291，下降 7.141%；均不是本轮新增训练指标。
- 源训练的 training.log、metrics.json、samples.json、report.md、run_metadata.json、training_status.json、quality_gate.json 已核实；训练 Artifact ID 12487687305 未过期。
- 源训练样例 10/10 重复标点，quality_gate 的 promotion_approved=false。候选继续拒绝晋级。历史第 8 次验证集不同，不可直接称为历史最佳突破。
- Kaggle Kernel 仅有历史 COMPLETE 证据，**未获得实时 Kernel 状态**。当前没有新 Kaggle GPU 训练。
- 当前训练脚本中 DataCollatorForLanguageModeling NameError 已消除，response_only_collator 保留，不重复修复。

## 本轮经验与下一步

1. 训练与推理的输入字段应一致。不能将 token_type_ids 造成的变化误归因于 LoRA 权重。
2. 下一轮先在隔离 CPU 环境审阅少量实际生成文本的可读性、相关性、EOS 和安全性；随后考虑仅移除推理端 token_type_ids 的最小补丁和回归测试。
3. 直接修改生产训练脚本会触发 GitHub 的 GPU 工作流；在验证质量门槛前不直接合并该修改。不盲目重训、不覆盖历史已批准模型。
4. 本轮只新增诊断工具、测试、CPU 工作流和报告。保护用户、维护人类；不提交凭据、私人数据或原始提示词。
