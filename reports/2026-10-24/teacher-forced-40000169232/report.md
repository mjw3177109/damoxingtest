# 第 12 次 GPT-2｜固定前缀 Teacher Forcing CPU 对照审计

- 复核日期：2026-10-24（北京时间）。
- 来源训练：[Daily GPT-2 T4 Training Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`；第 12 次训练已完成 33 步，但生成质量 0/10，候选模型未晋级。
- 新实验：[CPU Run 40000169232](https://github.com/mjw3177109/damoxingtest/actions/runs/40000169232)，`completed/success`；Artifact ID `12520284753`，名称 `run12-teacher-forced-cpu-40000169232`。
- 实验原始文件 `teacher_forced.json` SHA-256：`3cd7352f059d74de3ff97ba51c46da7981c731cf48bf014025784926e859f5f0`。本目录 `summary.json` 是对该原始文件的审计摘要，不是新的模型指标。
- 代码：PR [#15](https://github.com/mjw3177109/damoxingtest/pull/15)，合并 SHA `1c20ff673dc3a8e243499f1c062779824ae02761`；[静态预检 Run 40000108444](https://github.com/mjw3177109/damoxingtest/actions/runs/40000108444) success，包含新增的 5 项纯 Python 单元测试。

## 假设与控制条件

之前的自由生成对照在模型产生不同 Token 后，输入历史不再一致。此实验将同一固定验证集中的 4 条提示词分别追加连续 Token 119 或 8601，基础模型与被拒绝的第 12 次 Adapter 均看到**完全相同的前缀**；每条前缀审计 8 步，记录处理前后 Token 119 概率和排序。Teacher Forcing 是人为指定后续 Token，不代表模型实际生成的回答。

- 基础模型：`uer/gpt2-chinese-cluecorpussmall`，commit `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 被拒绝的候选 Adapter 权重 SHA-256：`979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 固定验证集 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练数据 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`。
- 使用完整的 `attention_mask` 和 `token_type_ids`，`repetition_penalty=1.12`，与历史 Run `39975111441` 的四条提示词首步结果全部一致。
- 4 提示词 × 2 固定 Token × 8 步 × 2 模型 = **128 次 CPU 前向计算、64 组同前缀配对**；无 GPU 分配、无 Kaggle 重训、无新模型文本输出。

## 真实结果

| 固定后续 Token | 同前缀配对 | 候选 Token 119 概率更高/更低 | 平均概率差（候选－基础） | Token 119 为 top-1：基础/候选 |
|---|---:|---:|---:|---:|
| 119 | 32 | 25 / 7 | +0.012719537 | 30 / 32 |
| 8601 | 32 | 32 / 0 | +0.002685634 | 2 / 4 |

这些差异说明：在锁定输入历史后，候选 Adapter 对 Token 119 的概率仍有可测量影响；在重复 119 的固定前缀中，基础模型也有 30/32 步将其列为 top-1。**不能据此声称 LoRA 是唯一根因，也不能将 Token 概率变化解释为模型回答质量改善。**

## 质量门槛、历史比较与下一步

- 第 12 次训练历史实测：Tesla T4 14.56 GiB，33 步，Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`；本次 CPU 实验没有产生新训练指标。
- 第 8 次历史运行使用不同训练/验证数据规模，不能与第 12 次直接判定谁是同口径历史最佳。
- 第 12 次 `samples.json` 仍为 10/10 重复标点，`quality_gate.json` 中 `promotion_approved=false`。本次不修改权重、不晋级、不覆盖之前已批准版本。
- 下一步优先检查固定前缀下 Token 119 的 raw logits、处理后概率与其他候选 Token 的相对 margin；随后在隔离环境审核少量真实中文回答。只有得到可测量的单变量训练假设并通过预检后，才考虑新一轮 Kaggle GPU 训练。
- 经验：对照必须保持相同 Tokenizer 输入和生成历史，固定前缀可以消除历史分歧混杂，但无法单凭概率统计证明因果根因或实际质量。
- 安全：不记录密钥、Token、隐私或原始回答；坚持保护用户、维护人类。
