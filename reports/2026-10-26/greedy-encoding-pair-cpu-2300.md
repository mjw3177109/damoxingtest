# GPT-2 Run 12｜23:00 时档：历史默认编码与训练一致编码的 CPU 贪心生成对照

- 检查时间：2026-10-26 23:07–23:13（Asia/Shanghai）。
- 仓库：mjw3177109/damoxingtest。
- 工作分支：fix/reuse-training-config-20261025-22；PR #70 仍为 Draft，未合并。
- 本轮工程提交：工具 a80353f358da5fcac393bb67305ddd6578a4bc83；测试 7efc0655e6a6616133a1517e78961219ba5e65ab；一次性 CPU 工作流 df46eb3ead47bf6c49e4f839c59b0c4d774083da。
- CPU Actions Run：40346746124（completed/success）；Job：121655574487；Artifact：12660989113（run12-encoding-pair-40346746124）。
- 最新静态预检 Run：40346649060（completed/success），255/255 项测试通过；本轮新加 6 项。
- 最近 Daily Run：40275426137（completed/success，但 SKIPPED_NO_CHANGES，未提交 Kaggle）。
- 最近真实 GPU 训练 Run：39921870784（已结束）；Kaggle Kernel 实时状态及剩余配额未独立核实。

## 假设与受控实验

假设：历史默认 Tokenizer 编码额外插入两个特殊 Token，可能导致 Run 12 模型在贪心解码时连续输出标点。仅改变 prompt 编码开关（默认 vs add_special_tokens=False），其余条件固定：同一个拒绝晋级的 Run 12 LoRA Adapter、同一基础模型版本、同一验证集 10 条提示词、CPU、greedy、max_new_tokens=64、repetition_penalty=1.12、EOS/PAD 配置相同。不使用 GPU、不训练、不提交 Kaggle、不修改晋级门槛。

- Base model：uer/gpt2-chinese-cluecorpussmall。
- 固定 base revision：c2c0249d8a2731f269414cc3b22dff021f8e07a3。
- Adapter SHA-256：979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c。
- 验证集 SHA-256：5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f。
- 实验结果文件 SHA-256：4d9d6920e116152a93cafe2a0ff20ffdcc9007374f89183159aaaeeac0400194。
- 20 次真实 CPU 推理已完成；运行日志确认单元测试 6/6 PASS、模型生成、输出来源校验及 Artifact 上传均成功。

## 真实结果

| 指标 | 历史默认编码 | 训练一致编码 |
|---|---:|---:|
| 固定提示词数量 | 10 | 10 |
| 纯标点输出 | 10/10 | **0/10** |
| EOS 结束 | 0/10 | 1/10 |
| 最长相同字符连续长度 | 64 | **2** |
| 平均生成 Token 数 | 64.0 | 58.4 |
| 直接回答率 | 未人工评估 | **未人工评估** |

- 10/10 对提示词的输入 Token ID 序列不同；10/10 对输出 Token ID 序列不同。
- 训练一致编码每条提示词比历史默认编码少 2 个 Token。
- **可确认的结论：本次固定条件下，输入编码切换使纯标点输出从 10/10 降至 0/10，且最长重复字符由 64 降至 2。**
- **不可确认的结论：是否形成语义正确、安全、直接的回答；目前未保存原始文本，尚未完成人工审核，不得宣称模型质量达标或晋级。**
- 本次实验使用已有 Adapter，不是新训练；不存在新的 Train Loss、Val Loss 或 PPL。

## 历史 GPU 训练指标（不是本小时新增）

- GPU：NVIDIA Tesla T4，14.56 GiB；Epoch=3，有效训练步数=33。
- Train Loss=3.246455；Val Loss=3.147277；PPL=23.272599。
- 同轮 base Val Loss=3.389291；相对改善=7.141%。
- 历史 Run 8 与 Run 12 验证集不同，不能据此宣布跨轮历史最佳。

## 文件、质量门槛与安全边界

- 主分支最新日期目录：reports/2026-10-26/run-40275426137。
- 已核实 training.log、metrics.json、samples.json、report.md、run_metadata.json、training_status.json、quality_gate.json。
- Daily Artifact 12629319793、历史 GPU Artifact 12487687305 均存在且未过期；本次 CPU Artifact 12660989113 已实际下载并解析，只有聚合/哈希诊断，没有原始提示词、输出文本或 Token ID。
- 最新 Daily 质量门槛：有效生成 0/10，human_review_status=pending，promotion_approved=false。
- 历史 DataCollatorForLanguageModeling NameError 在当前代码已不存在；Trainer 仍使用 response_only_collator 和 -100 掩码，未重复修复。
- 本次未运行 GPU、未变更模型权重、未合并 PR、未修改或绕过安全保护，保留可回滚历史版本。

## 与上一轮比较、经验及下一步

上一轮仅证实默认编码导致 10/10 Token ID 差异；本轮首次完成同 Adapter、同提示词、同贪心解码设置的真实生成对照，证明重复标点现象与编码开关具有强关联。静态测试由 249 增至 255，CPU Artifact 新增一个。没有新的 GPU Loss/PPL，也没有语义质量通过的证据。

经验：输入编码一致性会显著影响生成行为；但词法异常消失不等于模型已经能回答问题。下一步应在受控 CPU 环境对修复后的输出进行隐私保护的语义/安全人工审核与独立评分，并核对 EOS、重复、指令相关性；若不达标，继续检查数据质量和模型训练目标，不盲目启动第 13 次 GPU 训练。恢复 GPU 训练前必须独立确认 Kaggle 状态、配额、并发保护、可回滚基线及质量门槛。
