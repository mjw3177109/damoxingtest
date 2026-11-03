# PR #60 质量证据复用审计（2026-10-25 07 时档，Asia/Shanghai）

## 本轮动作与判定
- 独立复核 GitHub Actions 列表、PR #60 差异、142 项 CI 日志、现有 CPU 实验代码、机器可读报告与 Artifact 元数据；**本小时没有新 GPU 训练、没有新模型生成、没有修改生产训练代码**。
- **重要去重发现：PR #60 计划的“移除 token_type_ids 后观察真实回答质量”已在先前 CPU 审阅中以 `train_parity` 输入模式执行过**，无需重复下载权重或重新运行同条件的 CPU 实验。
- 当前证据显示：输入协议修复能改变生成行为，但没有证明语义任务完成率提升。**PR #60 继续保持 Draft，不合并 main，不触发 Kaggle，不晋级模型**。

## 可核实代码路径
1. PR #60 [diff](https://github.com/mjw3177109/damoxingtest/pull/60/files)：新增 `prepare_generation_inputs`，仅从 `tokenizer(prompt, return_tensors="pt")` 的输出删除 `token_type_ids`，再送入原 `generate` 调用；保留 `response_only_collator`。
2. 已合并的 `tools/run12_token_type_parity.py` 中 `make_inputs(tokenizer, prompt, "train_parity")` 执行相同的字段移除操作；`tools/run12_readability_review.py` 在 CPU 真实生成中直接使用该模式。**这验证了输入字段处理的行为对照，不等于 PR #60 生产函数已经完成真实模型端到端测试。**
3. PR #60 HEAD `59246c9bd1415fd98aa19fa91df914d24f0056f6` 的 [Static Preflight Run 40136941594](https://github.com/mjw3177109/damoxingtest/actions/runs/40136941594) 为 `completed/success`；核对 job log：**142/142 tests OK**，Ruff F821 及 response-only 掩码/Trainer wiring 检查通过。该成功是工程验证，**不是模型质量成功**。

## 历史 CPU 真实质量证据（无需重复同条件实验）
- [Token type 对照 Run 40043428043](https://github.com/mjw3177109/damoxingtest/actions/runs/40043428043)，固定 10 条、64 Token、同一被拒绝 Run 12 Adapter：候选纯标点 `10/10 → 7/10`（原始字段→移除 token_type_ids），仍不合格。Artifact ID `12540092198`，未过期。
- [CPU 可读性 Run 40119328101](https://github.com/mjw3177109/damoxingtest/actions/runs/40119328101)，**已使用 train_parity**、固定 4 条、64 Token、`no_repeat_ngram_size=0`：LoRA 候选纯标点 `2/4`、全特殊 Token 空白 `1/4`、初步人工直接回答 `0/4`。Artifact ID `12569273751`，未过期。证据：`reports/2026-10-25/readability-review-40119328101/{report.md,summary.json}`。
- [CPU bigram Run 40123632273](https://github.com/mjw3177109/damoxingtest/actions/runs/40123632273)，同样使用 `train_parity`，仅把 `no_repeat_ngram_size` 改为 2：候选纯标点 `1/4`、直接回答 `0/4`。Artifact ID `12571643988`，未过期。证据：`reports/2026-10-25/readability-bigram-40123632273/{report.md,summary.json}`。
- 这两次四样本审阅与 10 样本实验的样本数、实验目标不完全相同；不可混为单一统计或宣称语义改善。已有四样本实验表明 **train_parity 仍未达到直接回答质量门槛**。

## 训练基线、文件及安全状态
- 最近真实 GPU：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，Tesla T4 / 14.56 GiB，3 Epoch、33 有效步，Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`；固定样例门槛 `0/10`，晋级拒绝。训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，固定验证集 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 最新 Daily：[Run 40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092)，`SKIPPED_NO_CHANGES`，未新增 GPU 参数更新；`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已逐项核实在 `reports/2026-10-24/run-40065584092/`，指标是复用历史而非新测。旧报告的 `LoRA adapter files missing` 为已修复但待下一次 Daily 端到端验收的误报。
- 最近 GitHub Actions 总计 71 次；截至本轮查询，最新 Run 40136941594 已结束成功，未发现新 GPU 训练。Kaggle Kernel Version 8 `COMPLETE` 仅有历史记录，**未取得独立实时 Kernel/配额状态**。
- 第 8 次与第 12 次验证集不一致，不进行不合理的跨版本历史最佳 Loss 排名。保留上一已批准版本与回滚路径。

## 本轮积累的经验及唯一下一步
- **经验：** 计划实验前应先检查现有工具调用链、输入模式和历史真实样例；已有匹配的失败证据时，不再重复耗费 CPU/GPU，也不因 CI 通过而宣称模型进化。
- **下一步：** 不重复 `train_parity` 4 条/64 Token 同条件实验。若要继续 PR #60，需先设计**新增信息量**的 CPU 验证，例如使用未审阅的固定验证样本进行逐条人工语义/安全审阅，并确认生产 helper 与实验输入字段完全等价；否则保留 Draft/考虑关闭。只有通过明确质量门槛、核实 Kaggle 空闲与配额，才考虑合并可能触发 GPU 的训练脚本变更。
- 仅记录公开、无敏感信息的实验索引与汇总；不提交 Token、密钥、个人信息或未经脱敏的生成内容，不修改/绕过任何安全门槛。

**本小时暂无新训练/生成结果；本轮新增的是可审计的历史证据去重与 PR #60 合并风险判定。**
