# GPT-2 Run 12｜04 时档严格训练输入 CPU 对照审计（2026-10-27 CST）

## 结论与证据边界

- **已完成一次真实 CPU 对照实验**，不是 GPU 训练或模型晋级：GitHub Actions Run [40392088089](https://github.com/mjw3177109/damoxingtest/actions/runs/40392088089) completed/success；20 次生成（同一被拒绝的 Run 12 Adapter，10 条固定提示词 × 2 种编码）。
- 对照仅改变输入编码：历史 `train_parity` 仅去掉 `token_type_ids`，而 `train_exact` 额外显式设置 `add_special_tokens=False`。其他模型权重、提示词、解码参数一致。
- **真实结果：** `train_parity` 纯标点 7/10、EOS 1/10、触达生成长度上限 9/10、最长同字符连续 64、平均生成 Token 60.3；`train_exact` 纯标点 0/10、EOS 10/10、触达上限 0/10、最长连续 1、平均生成 Token 19.0。输入 Token ID 不同 10/10，输出 Token ID 不同 10/10。
- 这证明在当前固定条件下，严格训练输入契约显著改变生成行为；**不证明语义正确率、事实准确性或安全性提升**。直接回答率和人工审核仍未评估，模型不晋级。

## 可复现来源

- GPU 权重来源：历史 Run `39921870784`，Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 基础模型：`uer/gpt2-chinese-cluecorpussmall`；revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 固定验证集：`data/safety_humanity_eval_v1.jsonl`；SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；10 条提示词。
- 历史训练集：`data/safety_humanity_train_v2.jsonl`；SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`。
- 本轮代码：`tools/run12_train_exact_pair_cpu.py`（提交 `293816c885251c81316146026c72c23aff514311`）；`tests/test_run12_train_exact_pair_cpu.py`（提交 `ff9706f39ec0471169aa87b3f39222b643e12fe4`）；一次性工作流 `.github/workflows/run12-train-exact-pair-cpu.yml`（提交 `d919c483b8309ad9cbfaac28f07843897dbb2cce`）。
- 实验 Artifact ID `12684631964`，名称 `run12-train-exact-pair-40392088089`，已实际下载、解压、解析；内部 `train_exact_pair.json` SHA-256 `7aa832c5000f39a62aae92739bc1d00d76b4c6bf01b61761cffcbe804ca34f5d`。
- Artifact 仅含数值诊断、提示词哈希、Token ID 哈希，不包含原始提示词、模型回答、Token ID 序列或凭据。

## 代码验证与安全

- 在提交 CPU 工作流前先通过静态预检；最新完整代码静态 CI Run [40392096770](https://github.com/mjw3177109/damoxingtest/actions/runs/40392096770)：completed/success，**278/278 tests PASS**，Ruff F821 通过，`response_only_collator` 和 `-100` 标签掩码检查通过。
- CPU 工作流内的 8 项离线测试、Adapter 来源校验、CPU 推理、隐私字段白名单、无晋级断言与 Artifact 上传全部成功。
- 历史 `DataCollatorForLanguageModeling` NameError 已在最新源码核实不存在；保留 `data_collator=response_only_collator`，没有重复修复。
- 本次未修改训练参数、数据集、模型权重、Kaggle 工作流或安全门槛；未使用 GPU；未合并 Draft PR #70。回滚可撤销以上三个独立提交，保留历史已批准模型。

## Daily / Kaggle / 历史指标

- 当前 main 最新 Daily Training Run [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137)：completed/success，但 `SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`；**没有执行新 GPU 训练或新评估**。
- main 最新报告目录 `reports/2026-10-26/run-40275426137`：`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均已读取。最新 Daily Artifact `12629319793`、历史 GPU Artifact `12487687305` 均存在且未过期。
- 历史真实 GPU Run `39921870784`：Tesla T4、14.56 GiB、3 Epoch、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；这些**不是本小时新指标**。
- 历史正式样例有效 0/10；最新 CPU 对照未保存原文，因此无可公开的新文本样例。最新正式质量门槛 `promotion_approved=false`、人工审核 pending。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 的公开页面不可访问，实时 Kernel 状态、GPU 剩余配额及仓库外并发无法独立核实；不启动第 13 次 GPU 训练。

## 与上一轮及历史最佳比较、经验、下一步

- 上轮 CI 270 项，本轮 **278 项**（新增 8 项）；上轮仅修复 `train_exact` 输入契约，本轮已获得 20 次真实 CPU 对照及可审计 Artifact。
- 在同一 Run 12 Adapter 的当前对照中，纯标点输出由 7/10 降至 0/10，EOS 结束由 1/10 升至 10/10；但没有语义质量证据，不能据此宣布新版本进化。
- Run 8 与 Run 12 验证集不同，不能以 Loss/PPL 直接横向判断历史最优；本轮不改变历史最佳或晋级状态。
- **经验：** 仅删除 `token_type_ids` 不构成训练输入一致性；显式特殊 Token 策略可能实质改变生成终止和退化行为。EOS 结束率提升并不等于回答正确，应检查是否过早终止。
- **下一步：** 在受控私有 CPU 环境，对 `train_exact` 的真实生成进行逐题语义、事实、拒绝与安全审核；公开报告仅保存聚合数值和脱敏证据。若质量仍不足，检查监督目标与数据覆盖，先形成可测量的单变量训练实验，再在确认 Kaggle 配额、并发、回滚与门槛后考虑 GPU。
