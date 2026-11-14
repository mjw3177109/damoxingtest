# GPT-2 Run 12｜06 时档早停与监督答案长度审计（2026-10-27 CST）

## 结论及证据边界
- **本小时暂无新 GPU 训练或新模型生成结果。** 第 12 次 GPU 训练 Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束；最新 main Daily Run [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137) 为 `SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`。
- 本轮检查真实训练/验证 JSONL（`data/safety_humanity_train_v2.jsonl`、`data/safety_humanity_eval_v1.jsonl`）的**回答字符长度**，并与已完成的固定 CPU 配对实验 Run [40401678864](https://github.com/mjw3177109/damoxingtest/actions/runs/40401678864) 比较。未使用模型输出原文或重新运行 GPU。
- **训练集 85 条**：参考回答长度最小 39、中央値 50、最大 72、均值约 49.81 字符；**验证集 24 条**：最小 42、中位数 53、最大 62、均值约 52.13 字符。这些是 Python/JS 字符串长度，**不是 Token 数**，也不是模型输出语义质量。
- 05 时档固定 CPU 实验（Artifact **12688029323**，原报告 `reports/2026-10-27/run12-train-exact-reference-cpu-0500.md`）中，Run 12 候选模型 **10/10 EOS**，但索引 **2** 仅 **9 字符**（参考 42）、索引 **3** 仅 **5 字符**（参考 53）。因此 **EOS 且短于参考答案四分之一：2/10**；基础模型 EOS 1/10、短答 0/10。它们是**疑似过早结束**，不能仅凭长度断定语义错误。
- 两组参考答案字符 Bigram F1 均 **0.000000**；没有证据支持候选语义提升。自动质量门槛保持 `promotion_approved=false`；人工审核仍待完成。

## 本轮最小增量及验证计划
- 在 `tools/run12_train_exact_reference_cpu.py` 的**纯统计** `summarize()` 中增加 `eos_and_short_count`、`eos_and_short_indices`，把 EOS 和极短回答的**交集**显式标记出来；不会导出原始提示词、回答或 Token ID。
- `tests/test_run12_train_exact_reference_cpu.py` 新增合成数据回归测试，覆盖候选索引 2、3 的 EOS+短答以及基础模型的非 EOS 短答，避免将任意短答都归因于 EOS。
- 此次不改模型、训练脚本、数据、超参数、Kaggle 工作流或晋级门槛。提交后的 CI 测试结果必须另行核验，**不能把提交等同于测试通过**。
- 下一项可测量实验：在**私有本地**固定 10 条提示词及同一 Adapter 下逐题人工审核输出，分别统计直接回答、事实正确、安全合规、是否过早 EOS；优先核查索引 2、3。只公开聚合数字和脱敏证据，绝不公开原始生成文本。
- 若语义审核不合格，再定位训练监督目标、EOS 标签分布和数据覆盖；只有形成单变量假设、验证、GPU 配额及并发状态检查通过，才考虑下一次训练。当前不提交第 13 次 GPU 训练。

## 历史运行和可回滚状态
- Run 12：Tesla T4，单卡记录显存 14.56 GiB；3 epoch、33 optimizer steps；Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；训练/验证数据 SHA-256 分别为 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`、`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。以上为历史数据，**本小时未重新测量**。
- main 最新报告目录 `reports/2026-10-26/run-40275426137` 已核对；`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`quality_gate.json` 均有历史/复用证据，不能视作新训练。Daily Artifact **12629319793**、历史 GPU Artifact **12487687305**、CPU Artifact **12688029323** 均在 GitHub Actions 中存在、未过期。
- 历史 `DataCollatorForLanguageModeling` NameError 在当前 PR 分支源码中已不存在；Trainer 使用 `data_collator=response_only_collator`，保留 `-100` 标签掩码。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 实时状态、配额及仓库外并发**无法独立核实**。PR #70 继续 Draft，保留上一可回滚版本；不自动晋级。
- **经验**：EOS 100% 是停止行为而非成功回答的证明；须把 EOS 与过短输出交叉统计，并用私有语义评估检验。Run 8 与 Run 12 验证集不同，不能以跨轮 Loss 直接判断历史最佳。
