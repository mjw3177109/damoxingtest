# GPT-2 Run 12 真实监督 UNK 审计与 PR #69 合并记录（2026-10-25 21:00 Asia/Shanghai）

## 审计对象与可追溯证据
- 仓库：`mjw3177109/damoxingtest`。只读诊断改进 [PR #69](https://github.com/mjw3177109/damoxingtest/pull/69) 已合并到 `main`，合并 SHA `5f25f2c13ea73a978d9fde1872e1b737596537ec`，候选 SHA `24cea067258debfc4823a5fd1185c91e23575abf`。
- PR 静态预检 [Actions 40191155629](https://github.com/mjw3177109/damoxingtest/actions/runs/40191155629)：completed/success，176/176 单测通过，Python 编译、Ruff F821、response-only collator 与 -100 标签掩码检查通过。
- 合并触发的真实 CPU Tokenizer 审计 [Actions 40195742573](https://github.com/mjw3177109/damoxingtest/actions/runs/40195742573)：completed/success；4 项离线合成测试通过；固定真实 Tokenizer 运行完成，输出为聚合统计，不含原始问答。
- CPU 审计 Artifact：`12599861115`，名称 `run12-real-tokenizer-contract-40195742573`，已确认存在、未过期；日志包含完整聚合 JSON。
- 来源 GPU 训练 [Actions 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，来源训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`。基础模型 `uer/gpt2-chinese-cluecorpussmall`，固定 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；最大长度 256。
- 训练数据 85 条、SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 24 条、SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。均经脚本 SHA 校验。
- 最近 Daily [Actions 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) 为 completed/success，但 `training_status.json` 记录 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`。最近 Daily Artifact `12588187512` 已核实存在。本轮无 Kaggle 新提交、GPU 训练或模型生成。Kaggle Kernel 实时状态/配额未独立核实。

## 本轮真实 UNK 数据（仅聚合；CPU，无模型前向）
| 数据集 | 前缀 UNK / 总 Token | 完整回答 UNK / 总 Token | 实际监督标签 UNK / 总 Token | 截断 / 零监督 / EOS 缺失 |
|---|---:|---:|---:|---:|
| train 85 条 | 7 / 2162 = **0.3238%** | 1 / 4291 = **0.0233%** | 1 / 4291 = **0.0233%** | 0 / 0 / 0 |
| eval 24 条 | 8 / 732 = **1.0929%** | 2 / 1256 = **0.1592%** | 2 / 1256 = **0.1592%** | 0 / 0 / 0 |

- 两组监督标签均保留末尾 EOS，全部样本未截断。训练集实际监督 UNK 仅 **1 / 4291**，验证集 **2 / 1256**。
- **假设评估：** 监督标签存在少量 UNK 是事实；数量很低，暂不支持「大量监督 UNK 污染直接导致全部样例退化为重复标点」这一主要根因假设。不能因此证明 UNK 与退化完全无关，也不能把生成端的 UNK 与训练标签 UNK 混为一谈。
- 没有修改数据、训练脚本、权重、训练配置、Kaggle 工作流或模型晋级门槛；不因本轮统计自动重训。

## 训练质量、历史对照和晋级
- Run 12 历史实测：NVIDIA Tesla T4、14.56 GiB；3 Epoch、33 有效训练步；Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`，同轮基础模型 Val Loss `3.389291`，改善 `7.141%`。本轮新增 GPU 步数 0；所有上述 Loss/PPL 均为历史数据。
- 最新 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均存在且已读取；历史样例 10 条，自动质量门槛 **0/10**，`promotion_approved=false`，人工审核 pending。代表性输出为连续句点，不具备有效回答能力；本轮没有生成新样例。
- Run 8 和 Run 12 验证集不同；加之 v1 留出集已有近重复风险，**不可宣称 Run 12 超越历史最佳**。本轮没有批准新模型，也没有覆盖或变更回滚候选。
- 历史 `DataCollatorForLanguageModeling` NameError 已在当前 `main` 排除，`response_only_collator` 仍连接 Trainer 并经静态检查验证；无需重复修复。

## 本轮经验、可测量下一步与安全门槛
1. 已把「合成单测验证统计逻辑」升级为「固定真实 Tokenizer + 固定数据哈希的只读 CPU 统计」，这是**审计证据增强**，不是模型质量进化。
2. 由于真实监督 UNK 比例低，不以盲目清除 UNK 或重复训练为下一步。优先做 **一个** 隔离 CPU/合成微型模型的梯度裁剪验证：在固定 batch、随机种子与 `max_grad_norm=1.0` 下，记录 FP32 与当前 AMP 配置各自的裁剪前/后范数、非有限值和参数更新量；判据为裁剪后范数不超过阈值（容许数值误差）、无 NaN/Inf、存在有限参数更新。此实验仅验证训练机制，不声称直接修复生成质量。
3. 若实验揭示可复现训练实现缺陷，再做最小代码修复、静态检查、单测与必要的初始化验证；若无缺陷，则转向独立验证集与回答语义质量，不重复消耗 Kaggle GPU。
4. Kaggle 实时状态、配额、并发状态、独立评估与正式回滚能力未全部核实前，**不启动第 13 次 GPU 训练**。禁止无界重试、泄露凭据、绕过质量门槛或自动晋级。
5. 项目原则：保护用户、维护人类。所有统计和审计记录仅含可复核聚合指标及非敏感标识；保留可回滚历史版本，失败经验与结论边界明确归档。
