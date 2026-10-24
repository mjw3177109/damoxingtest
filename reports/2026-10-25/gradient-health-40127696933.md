# Run 12 梯度范数健康度只读审计（2026-10-25 03:59 北京时间）

## 范围与证据
- 本轮仅分析仓库中已经保存的历史 `training.log`，不加载模型、不执行前向/反向、不访问 Kaggle 凭据、不启动 GPU 训练、不更改训练参数或晋级门槛。
- 历史训练来源：[GitHub Actions Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`，日志 blob SHA `c562543cbe47b85cd9c534d7b7f70610d8812c12`。
- 新增离线工具和测试：[PR #58](https://github.com/mjw3177109/damoxingtest/pull/58)，squash merge SHA `73baa825470ff8c04da55f0ed714c50ac09f6602`。静态预检 [Run 40127696933](https://github.com/mjw3177109/damoxingtest/actions/runs/40127696933) `completed/success`，**138/138** unittest 通过；Python 编译、Ruff F821、response-only collator/-100 标签掩码检查均通过。
- 固定训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`（85 条）；固定验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`（24 条）。
- 新增文件仅为 `tools/audit_gradient_health.py`、`tests/test_gradient_health.py` 及本报告；没有修改 `scripts/train_gpt2_lora.py`、notebook、数据、Adapter、质量门槛、安全规则或 Secrets。

## 历史真实日志的新增诊断
从 Run 39921870784 已归档日志中提取 7 条 `Trainer metrics at step` 的 `grad_norm`，对应步骤 1、5、10、15、20、25、30。依次为：

| Step | grad_norm |
|---:|---:|
| 1 | 39550.09375 |
| 5 | 41631.30078125 |
| 10 | 61934.7109375 |
| 15 | 67372.71875 |
| 20 | 68622.515625 |
| 25 | 70956.7890625 |
| 30 | 72079.8203125 |

- 最小值 `39550.09375`，中位数 `67372.71875`，最大值 `72079.8203125`，7/7 条日志值大于训练配置 `max_grad_norm=1.0`。
- **重要解释边界：** Trainer 记录的 `grad_norm` 可能是裁剪前的范数，超过 `max_grad_norm` **不代表裁剪失败**，也不能证明数值不稳定是生成重复标点/UNK 的根因。当前尚无相同批次下的 FP32/AMP、裁剪前后梯度或参数更新对照证据。
- 本轮新增的是可复核的梯度健康诊断信号，而非新的训练指标或模型改善。未来日志出现 `nan/inf` 时，新工具会记录对应步骤并拒绝把非有限数当成正常范数。

## 训练状态、质量与历史对照
- 最近一次真实 GPU 训练仍为 Run 39921870784，Tesla T4 / 14.56 GiB、3 Epoch、33 步、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`，以上均为**历史实测**，非本轮新增。
- 最近 Daily [Run 40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092) 为 `SKIPPED_NO_CHANGES`，没有提交新的 Kaggle 训练。Run 12 固定 10 条生成样例的质量门槛为 0/10，`promotion_approved=false`。
- 上一轮 CPU [Run 40123632273](https://github.com/mjw3177109/damoxingtest/actions/runs/40123632273) 语义直接回答率仍为 0/4；本轮没有生成新文本、Loss/PPL 或 GPU 步数，不能宣称模型改善。
- 第 8 次与第 12 次验证集不同，无法有效进行同口径历史最优排名；已批准版本保持不变。
- Kaggle Kernel Version 8 的 COMPLETE 仅来自历史记录；本轮没有独立实时 Kaggle API 证据。GitHub Actions 成功不等于新训练成功。

## 经验、下一步及安全约束
1. 训练数值诊断要区分**日志记录时点**与**实际梯度裁剪执行**，不能因为 `grad_norm > max_grad_norm` 就判定裁剪失效。
2. 下一次只做一个可测量的 CPU/隔离实验：核实当前 Transformers/Accelerate 版本中 Trainer 的梯度范数记录位置，使用合成微型模型与相同参数分别记录裁剪前/后的范数、是否非有限，以及一次参数更新是否发生；若确认训练实现缺陷，再设计最小修复及回归测试。不得直接修改训练架构或消耗 Kaggle 配额。
3. 继续优先维护用户隐私和人类安全，不提交凭据、密钥、个人数据，不绕过质量门槛；保留历史最佳和回滚路径。