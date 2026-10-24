# Run 12 提示词后缀单变量 CPU 审计（2026-10-24 13:01 北京时间）

## 假设、代码与安全边界

- **已核实的生产事实：** scripts/train_gpt2_lora.py 的训练前缀和生成前缀均为「用户：{instruction}\n助手：」；不存在本轮假设中的训练/推理模板不一致。
- **单变量实验：** 在该前缀末尾仅增加一个换行符，与原始前缀对照；不修改模型、数据、Tokenizer、LoRA Adapter、随机种子或解码配置。此实验只检验输入敏感性，不属于已确定的故障修复。
- 代码合并：[PR #35](https://github.com/mjw3177109/damoxingtest/pull/35)，SHA c7f227edae8364823c4a33fdc915548e29170237。
- 静态 CI：[Run 40064496811](https://github.com/mjw3177109/damoxingtest/actions/runs/40064496811) completed/success；仓库 78/78 项离线测试通过，编译、Ruff F821、response_only_collator 和 -100 标签掩码检查通过。
- CPU 实验：[Run 40064518326](https://github.com/mjw3177109/damoxingtest/actions/runs/40064518326) completed/success；16 次真实 CPU 生成和 16 次首步 UNK 概率测量，质量契约检查通过；**无 GPU 训练**。
- 固定模型 uer/gpt2-chinese-cluecorpussmall，revision c2c0249d8a2731f269414cc3b22dff021f8e07a3。
- 固定被拒绝的 Run 12 Adapter 权重 SHA-256：979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c。
- 固定验证集 data/safety_humanity_eval_v1.jsonl SHA-256：5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f；前 4 条提示词。
- 设备 CPU；seed 42；贪婪解码；max_new_tokens=64；repetition_penalty=1.12；仅输入 input_ids、attention_mask。
- Artifact ID 12548288212，ZIP SHA-256 cf94008a0c77fb71550397a7ae0ed1656bbf2ddddd088e2d2427c4e93e3d8f72；内部 prompt_suffix.json SHA-256 1ad142b68e42f5a76629ac807c1a208218d5105788b9831f7e1aa2e3249f27d5。已下载、解包、解析和校验。

## 实测结果

| 模型 / 提示词 | 纯标点 | 包含中文 | EOS | 64 Token 上限 | 空白 | 首步 UNK Top-1 | 首步 UNK 平均概率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 基础模型 / 原始训练一致模板 | 0/4 | 4/4 | 1/4 | 3/4 | 0/4 | 0/4 | 0.024356880 |
| 基础模型 / 末尾增加换行 | 0/4 | 4/4 | 1/4 | 3/4 | 0/4 | 0/4 | 0.024356880 |
| LoRA 候选 / 原始训练一致模板 | 2/4 | 1/4 | 1/4 | 3/4 | 1/4 | 1/4 | 0.036124010 |
| LoRA 候选 / 末尾增加换行 | 2/4 | 1/4 | 1/4 | 3/4 | 1/4 | 1/4 | 0.036124010 |

16 次生成中，两种后缀对应的 4 条基础模型回答和 4 条候选模型回答在已记录的输出及指标上逐条一致；**本次末尾增加换行没有观察到改善**。这可能与该 Tokenizer 对换行的处理有关，但本次 Artifact 未保存逐 Token 输入对照，不能据此断言 Tokenizer 一定忽略换行。

候选模型仍出现连续 64 个句点、仅复述问题的中文片段和空白回答。第 4 条空白回答仍是 64 个 UNK；两种后缀的首步处理后 UNK 概率均为 0.096584620，排名均为第 1。

**质量判定：** 未产生通过人工质量审核的新模型回答；promotion_approved=false。纯标点、空白及回答相关性问题均未解决。

## 训练、报告、历史对照

本轮没有新 GPU 训练；历史 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束，Tesla T4 14.56 GiB、3 Epoch、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599。同轮基线 Val Loss 3.389291，改善 7.141%，但质量门槛 0/10，拒绝晋级。

历史 reports/2026-10-23/run-39921870784/ 下 training.log、metrics.json、samples.json、report.md、run_metadata.json、training_status.json、quality_gate.json 均存在；训练 Artifact 12487687305 未过期。历史第 8 次 Val Loss 3.424955、PPL 30.721252，验证集不同，不能认定本轮超越历史最优。

历史 DataCollatorForLanguageModeling NameError 在当前代码中已不存在，response_only_collator 仍被 Trainer 使用。Kaggle 历史 COMPLETE 不等于实时 Kernel 已核实，也不等于模型质量合格。

## 经验与下一步

1. **先验证是否真的存在模板不一致，再设计修复。** 本次确认生产训练/生成模板本来一致；不能将单变量敏感性实验误称为修复。
2. **无效果也是有效实验结论。** 增加末尾换行在本组条件下未改变输出和 UNK 概率；不应据此启动 GPU 或修改生产代码。
3. 下一次优先在 CPU 进行输入 Token ID 的隐私安全哈希与长度对照，验证换行是否被 Tokenizer 忽略；若相同，则换用预先定义的、真正改变 Token 序列的单变量模板对照，并继续审核回答质量。
4. 保持历史最佳和被拒绝候选隔离；无通过质量与安全门槛的证据，不晋级、不消耗 Kaggle T4、不泄露凭据。

**结论：新增可审计的负结果与工程测试证据；模型没有升级，拒绝晋级。**
