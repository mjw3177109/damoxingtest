# Run 12 UNK 固定前缀概率审计（2026-10-24 12:03 北京时间）

## 假设与边界

上一轮确认：被拒绝的 Run 12 LoRA 候选在固定验证集第 4 条提示词上连续生成 64 个 UNK 特殊 Token。本轮检验相同提示词、相同强制 UNK 历史下基础模型和候选模型的 UNK logits、概率和排名；不把强制前缀当作自然语言生成。

- 工程：[PR #33](https://github.com/mjw3177109/damoxingtest/pull/33)，主分支 SHA 03679e551f493156a9117d992d24d0cac865a2c5。仅新增 CPU 诊断、6 项单测和隔离工作流。
- 静态预检：[Run 40060684728](https://github.com/mjw3177109/damoxingtest/actions/runs/40060684728) completed/success；72 项仓库单测通过（含新增 6 项），编译、Ruff F821、response_only_collator 与 -100 标签掩码检查通过。
- CPU 实验：[Run 40060717009](https://github.com/mjw3177109/damoxingtest/actions/runs/40060717009) completed/success；40 次真实 CPU 前向计算、20 组严格匹配比较；没有 GPU 训练或模型更新。
- 模型：uer/gpt2-chinese-cluecorpussmall，revision c2c0249d8a2731f269414cc3b22dff021f8e07a3。被拒绝的 Run 12 Adapter SHA-256：979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c。
- 验证集：data/safety_humanity_eval_v1.jsonl，SHA-256 5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f；前 4 条固定提示词。
- 配置：seed 42，CPU；分别强制追加 0、1、2、3、4 个 UNK；两模型输入历史完全相同；只传 input_ids 和 attention_mask，不传 token_type_ids；同时测量原始与 repetition_penalty=1.12 处理后的 UNK logits、概率、排名；不生成新回答。
- Artifact ID 12546769462，名称 run12-unk-fixed-prefix-40060717009。ZIP SHA-256：cc4fb4d2652f1484132c19f65ca3fc61b22f2d6285af51d60cfea51270ac2b20。内部 JSON SHA-256：230717134a2da4b459991a52867ea5311e3a42397e2d779158c332ca18b85d0e。已下载解析并校验。

## 真实结果

| 指标 | 实测 |
|---|---:|
| CPU 前向计算 | 40 |
| 同历史匹配比较 | 20 |
| 候选 UNK 概率高于基础模型 | 5/20 |
| 候选 UNK 概率低于基础模型 | 15/20 |
| 处理后候选－基础 UNK 概率平均差 | -0.026361060 |
| 基础模型 UNK 排名第一 | 14/20 |
| 候选模型 UNK 排名第一 | 15/20 |

**已知空白输出的第 4 条提示词，第一步（尚未强制 UNK）结果：**

| 指标 | 基础模型 | Run 12 候选 |
|---|---:|---:|
| 原始 UNK 概率 | 0.059600318 | 0.200784360 |
| 重复惩罚后 UNK 概率 | 0.032997736 | 0.096584624 |
| 处理后 UNK 排名 | 3 | 1 |

同一提示词强制追加 1、2、3、4 个 UNK 后，两模型 UNK 都排名第一。处理后概率（基础 / 候选）：1 个 0.166062505 / 0.127181060；2 个 0.079617602 / 0.084980496；3 个 0.335420466 / 0.288916553；4 个 0.423456380 / 0.379645130。

**解释：** 在已知空白输出提示词上，候选模型把首步 UNK 从第 3 名推至第 1 名，且概率上升；进入 UNK 历史后，两模型都存在 UNK 自反馈。但 20 组总体比较中候选概率并非普遍更高，不能把全部重复归因于 LoRA，也不能由本实验证明最终根因。

## 训练、质量与历史对照

本小时没有新训练或自然语言回答。生产训练 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束：Tesla T4、14.56 GiB、3 Epoch、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。

历史 training.log、metrics.json、samples.json、report.md、run_metadata.json、training_status.json、quality_gate.json 均在 reports/2026-10-23/run-39921870784/ 核实。训练 Artifact 12487687305 存在且未过期；生成质量 0/10 通过，promotion_approved=false。历史第 8 次 Val Loss 3.424955、PPL 30.721252，但验证集不同，不能直接比较历史最佳。Kaggle 历史日志为 QUEUED → RUNNING → COMPLETE；实时状态未独立核实。

历史 DataCollatorForLanguageModeling NameError 已修复，response_only_collator 仍被 Trainer 使用，不重复提交修复。

## 本轮经验与下一步

1. 区分首步选择 UNK 与 UNK 历史下的自反馈；特定提示词异常不能概括全部输入。
2. 总体平均差不能掩盖第 4 条提示词的严重退化；同时基础模型自身也有 UNK 自反馈。
3. 下一次在隔离 CPU 环境只检验训练与推理提示词模板的一项差异，固定模型、Adapter、验证集和解码参数；记录 UNK 首步排名、重复、EOS 和回答可读性。
4. 根因与质量未通过前，不启动第 13 次 Kaggle GPU 训练，不覆盖上一个已批准版本，不降低安全质量门槛。

**结论：本轮新增可审计诊断证据；没有训练质量改善，继续拒绝晋级。**
