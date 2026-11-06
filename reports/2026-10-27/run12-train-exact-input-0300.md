# GPT-2 Run 12｜03 时档训练输入一致性修复审计（2026-10-27 CST）

## 已确认的问题与根因
- 历史训练入口 `scripts/train_gpt2_lora.py` 的 `encode_record` 显式使用 `add_special_tokens=False`，只传递 input_ids/attention_mask/labels，不使用 token_type_ids。
- CPU 诊断公用函数 `tools/run12_token_type_parity.py::make_inputs` 原来的 `train_parity` 模式仅移除了 token_type_ids，却仍调用 Tokenizer 默认 `add_special_tokens=True`。因此后续 `run12_readability_review.py` 和 `run12_direct_answer_generation.py` 虽标记为“训练一致”，实际并非严格一致。
- 这是已核实的实验输入契约问题，不等于已经证明它是模型生成退化的根因；旧实验记录仍然保留，不追溯改写。

## 最小修复、验证与回滚
- 在 `make_inputs` 新增独立 `train_exact` 模式：显式 `add_special_tokens=False`，移除可选的 token_type_ids；保留历史 `original` 和 `train_parity` 的旧行为，避免破坏旧实验重现。
- 两个未来 CPU 诊断入口切换至 `train_exact`；更新报告文字，明确公开报告不包含生成原文。
- 修改文件：`tools/run12_token_type_parity.py`、`tools/run12_readability_review.py`、`tools/run12_direct_answer_generation.py`、`tests/test_run12_token_type_parity.py`。没有修改训练权重、训练数据、训练超参数、模型架构、Kaggle 工作流或晋级门槛。
- 代码提交：`55a76a5aa3afcfce4a1d39b7acc7dff97400acad`、`27ab8bbffcf5ec67ffe88d45add7afc2fb58e4b2`、`94188f2676776cc5c17e86eccf751dc9d0ce3b46`、`3e81f307dad2fe541628a0adc1b9394d5de0c0ce`。
- 新增 4 项离线回归测试：禁自动特殊 Token、保留历史行为、无 token_type_ids 的兼容性、两个消费入口使用新模式。
- GitHub Actions Static Preflight Run `40382958729`，Job `121783728008`：completed/success；日志确认 **Ran 270 tests**、**All checks passed!**，response-only collator / -100 掩码检查通过。
- 回滚：保留原始历史模式和未合并的 Draft PR #70；可回滚上述增量提交。无 GPU 或 CPU 模型生成实验在本时段执行。

## 运行与归档证据
- 最新 main Daily Training Run `40275426137`：completed/success 但 `SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`；main 最新报告目录 `reports/2026-10-26/run-40275426137`。
- 该目录的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均已读取；`train_steps=0`、`train_loss=null`、`gpu_name=null`，本次未训练或重新评估。
- 最新 Daily Artifact `12629319793` 存在且未过期；历史 GPU Artifact `12487687305` 存在且未过期；本次 CI 无模型 Artifact。
- 历史 GPU 训练 Run `39921870784`：Tesla T4、14.56 GiB、3 epochs、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599。训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 本小时无新生成样例；历史正式样例有效 0/10；历史 CPU 字符 bigram F1 候选与基础模型均为 0.004494。不同验证集的历史 Run 8 不能直接横比。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 公开状态不可访问；实时状态、配额和仓库外并发未能独立核实。
- `DataCollatorForLanguageModeling` NameError：最新代码无该名称；`data_collator=response_only_collator` 保留，故未重复修复。

## 经验、质量门槛和下一步
- **经验：** 只移除 token_type_ids 不等于训练/推理输入一致；应同时显式锁定特殊 Token 策略，并为历史对照保留旧模式。此前称作 `train_parity` 的结果不得冒充完整训练一致性证据。
- **晋级判定：** `promotion_approved=false`；尚无新的语义、事实准确性或安全评估；不宣称模型进化，不替换上一批准版本。
- **下一步受控实验：** 在可用的私有 CPU 环境，使用固定 Run 12 Adapter、基础模型、10 条固定提示词，比较历史 `train_parity` 与新 `train_exact` 输入模式；逐题记录纯标点、EOS、截断、重复长度等数值指标，原始文本仅在私有环境审核。先做语义和安全审核，再考虑下一次 GPU 训练。
- **阻塞：** 本时段未运行真实 CPU 推理，尚不能证明本修复提高回答质量；Kaggle 实时状态/配额无法独立核实，故不启动第 13 次 GPU 训练。
