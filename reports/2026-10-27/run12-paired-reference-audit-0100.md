# Run 12 CPU 参考答案对照：逐题数值复核（2026-10-27 01:00 CST）

## 范围与假设
- 假设：两组平均 character-bigram F1 相同可能掩盖逐题差异；只读复核已完成的真实 CPU Artifact，不再加载模型、重复运行 CPU 推理或消耗 Kaggle GPU。
- 原始 GPU 训练：Actions Run `39921870784`，2026-10-23 已结束；基础模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 对照 CPU Run：`40355719971`，2026-10-27 00:05 CST 左右触发，已 completed/success，20 次生成（base 与 Run 12 Adapter 各 10 次）。
- 来源 Artifact：`12665288586`，已下载并实际解析 `reference_overlap.json`；原 ZIP SHA-256 `964ac9f2005ff6e6865cae94fee303161c45eed05dd640dd588ccbab4b6a31da`；JSON SHA-256 `b9aee03b795e0cc8b6f4b1f9260aa1036980e6c794c6a467b4241e45e91a3494`。
- 固定验证集 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练集 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`。
- Adapter SHA-256：`979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 本轮代码提交：`13b4fa4931ae82163ed2296eb03321c5709ffa25`（工具）、`bdd2c0ae7c896c75e420aad23d597255ac885de4`（4 项离线测试）。仅新增工具与测试，原模型、数据、质量门槛及训练流程未修改。

## 实际复核结果
使用 `python tools/paired_reference_diagnostics.py reference_overlap.json` 对 20 条真实数值记录进行成对索引、提示词 SHA、分数范围、长度和停止原因校验；4/4 离线回归测试与 Python 编译检查通过。

| 逐题指标 | 真实结果 |
|---|---:|
| 固定成对提示词 | 10 |
| 候选模型 bigram F1 更高 | 0 |
| 候选模型 bigram F1 更低 | 0 |
| 两者 bigram F1 相同 | **10** |
| 两组输出字符长度不同 | **2** |
| 两组 EOS 停止状态不同 | **1** |
| base 平均 bigram F1 | 0.004494 |
| Run 12 候选平均 bigram F1 | 0.004494 |
| 候选减 base 平均差 | 0.000000 |
| 已完成语义正确性人工审查 | **否** |
| 晋级 | **否** |

逐题第 0 项候选输出 13 字符、base 输出 119 字符，候选 EOS 结束而 base 到长度上限；第 8 项两组长度不同（119 与 127），但两项的 bigram F1 均未改变。不能将词面指标持平解释为输出完全相同，更不能解释为语义质量等价或提升。

## 本小时真实 Actions / Kaggle / 产物
- 巡检时最近完整静态 CI：Run `40356094451` completed/success，**261/261** tests PASS；本轮新增提交触发新 CI，最终状态以其 Actions 页面为准。
- 最近 Daily Training：Run `40275426137` completed/success，但 `SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`；没有本小时 GPU 训练。
- main 最新报告：`reports/2026-10-26/run-40275426137`。其 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已逐项读取；质量门槛 `promotion_approved=false`、人工审核 pending。
- 最新 Daily Artifact `12629319793`（状态证据，非模型权重），历史 GPU Artifact `12487687305`，CPU Artifact `12665288586` 均通过 GitHub Actions 元数据核实，CPU Artifact 本轮实际下载解析。
- Kaggle Kernel 实时状态、剩余 GPU 配额无法独立核实；不声称有新训练。
- 历史 Tesla T4 14.56 GiB，3 epochs、33 步，Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；本小时没有新 Train Loss / Val Loss / PPL。
- 正式训练样例仍为 10/10 纯标点，代表性为重复句点；本小时无新生成样例。此前修复编码后的 CPU 生成 0/10 纯标点，但不代表语义能力已通过。
- 历史 Run 8 使用不同验证集，不能将 Run 12 的 loss 与之直接比较并宣布历史最优晋级。

## 已确认阻塞与处理边界
- `scripts/train_gpt2_lora.py` 当前 PR 代码已核实不存在 `DataCollatorForLanguageModeling` 名称，`data_collator=response_only_collator` 保留，`-100` 掩码静态检查通过；避免重复提交旧修复。
- 新发现：单一平均词面指标无法展示候选生成长度与 EOS 的差异。通过新增只读、可测试的逐题配对诊断工具补足证据；无 GPU 消耗，无模型变更。
- 当前尚缺修复编码后 10 条输出的**隐私受控语义审查**；现有 Artifact 故意不包含原始文本，不能据此臆造直接回答率或安全表现。下一次应在授权的私有 CPU 环境审阅，不向公开 CI、Artifact、报告上传未脱敏输出。
- 只有当语义相关性、准确性、安全性及 EOS 门槛实际达标，且 Kaggle 状态、配额、并发和回滚条件可核实后，才考虑受控下一步训练实验。当前 `promotion_approved=false`，PR #70 继续 Draft。

## 经验与决策
**经验：** 相同的平均 bigram F1 甚至 10/10 逐题 F1 持平，仍可能伴随输出长度、EOS 行为变化。词面代理指标不能替代人工语义审查。本轮仅提升审计粒度，没有证据证明模型进化。保护用户与人类，最小权限，不公开敏感信息，不绕过质量或安全保护。
