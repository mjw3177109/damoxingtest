# GPT-2 Run 12｜07 时档 EOS 监督标签真实 CPU 审计（2026-10-27 CST）

## 本轮结果与证据
- 本小时新增 **只读 EOS 标签审计工具** `tools/audit_run12_eos_labels.py`、**5 项离线回归测试**及**一次性 CPU 工作流** `.github/workflows/run12-eos-supervision-cpu.yml`。没有修改训练超参数、模型权重、数据集、晋级门槛或 Kaggle 提交流程。
- 静态 CI Run [40417526845](https://github.com/mjw3177109/damoxingtest/actions/runs/40417526845)：**completed/success，290 项测试通过**；本地独立运行新增 5/5 项测试和 Python 编译也通过。
- 真实 CPU 审计 Run [40417564007](https://github.com/mjw3177109/damoxingtest/actions/runs/40417564007)：**completed/success**；Artifact **12696138797** 已下载、解压并逐项读取 `eos_supervision.json`，SHA-256 `af1a48fad649f0e92f88bfcae614fe32b4af4789528faf97200d1d7e0b0d7aea`。
- 工具提交 `801dbcf36337d51cbd7e1bae963053d0932c7ce6`；测试提交 `4dbe66e7ff19ee9d953a75223ea4dd0f76c36919`；CPU 工作流提交 `b948a648cb5eb31f0535574153cc882b0e7a50b2`。工作流采用只读权限，固定历史 Run 12 Adapter 所保存的 Tokenizer，未加载模型权重执行推理。

## 假设、真实数值及判断
**假设：** 候选模型索引 2、3 的疑似过早 EOS，可能是训练标签遗漏 EOS、被 `max_length=256` 截断，或响应区标签被完全掩码导致。

| 真实 CPU 审计指标 | 训练集 | 验证集 |
|---|---:|---:|
| 固定记录数 | 85 | 24 |
| 末尾 EOS 编码缺失 | 0 | 0 |
| 回答内部出现 EOS | 0 | 0 |
| 记录被截断 | 0 | 0 |
| 没有任何监督 Token | 0 | 0 |
| **末尾 EOS 确实进入监督标签** | **85/85** | **24/24** |
| 提示词 Token 长度（最小/中位/最大） | 14/25/36 | 25/30/40 |
| 回答含 EOS 的 Token 长度（最小/中位/最大） | 40/50/73 | 43/53.5/63 |

训练数据 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。审计使用历史 Adapter 保存的真实 Tokenizer，编码契约与 `scripts/train_gpt2_lora.py` 的 `encode_record` 一致：`add_special_tokens=False`，前缀标签 `-100`，回答末尾追加 EOS。

**结论：** 在 Run 12 固定数据、Tokenizer 与 `max_length=256` 下，**“EOS 监督标签缺失或被截断”假设被本次审计排除**。这并不排除小数据规模、模型学习动态、解码参数、回答质量或其他原因造成过早 EOS；不能声称已经定位最终根因。

## 与上一轮及历史最佳的比较
- 上一轮发现严格输入下候选模型 10/10 EOS、2/10 疑似极短回答，基础模型 1/10 EOS；本轮没有重新生成模型文本，新增的是对 **109 条训练/验证记录** 的实际 Token 监督审计。
- 上一轮 CI 285 项，本轮 CI **290 项**；没有新 GPU 训练，没有新的 Train Loss、Val Loss、PPL 或模型权重。
- 历史真实 GPU Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4 **14.56 GiB**，3 epochs，**33 steps**，Train Loss **3.246455**，Val Loss **3.147277**，PPL **23.272599**，同轮基线 Val Loss **3.389291**。Run 8 与 Run 12 验证集不同，不能声称跨轮历史最佳改善。
- 最新 main Daily Run [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137)：`SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`；`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已核实。Daily Artifact **12629319793**、历史 GPU Artifact **12487687305**、前次 CPU Artifact **12688029323** 及本次 CPU Artifact **12696138797** 均存在、未过期。
- 历史正式生成样例仍含连续句点，修复后严格输入的真实 CPU 对照已消除纯标点输出，但参考答案 Bigram F1 仍未改善；**语义/安全人工审核尚未完成**，`promotion_approved=false`，不得晋级。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 实时状态、GPU 配额及仓库外并发仍未独立核实；**不启动第 13 次 GPU 训练**。

## 本轮经验、失败假设与下一步
- **经验：** 应把“生成 EOS 的比例”和“训练时 EOS 是否确实被监督”分开审计；正常的 EOS 标签不意味着生成答案正确。此次排除了一个明确、可测量的假设，避免在没有证据时盲目修改 EOS 标签或消耗 T4 配额。
- 下一次优先在**私有 CPU 环境**逐题审阅固定 10 条真实输出（尤其索引 2、3），统计直接回答、事实正确、语义相关性、过早结束及安全表现。只公开数值评分，原始文本不得进入公开日志/Artifact。
- 如果审核证实早停且语义质量不合格，再设计**单变量、可回滚**的训练或解码对照实验，必须先通过静态检查、单测、来源校验、Kaggle 配额与并发保护；PR #70 继续 Draft。
- 历史 `DataCollatorForLanguageModeling` NameError 已核实在最新分支源码不存在；`data_collator=response_only_collator` 和 `-100` 掩码保留，不重复修复。所有实验记录均不包含 Token、凭据或用户隐私。
