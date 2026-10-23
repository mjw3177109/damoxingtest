# GPT-2 训练故障与实验经验库

本文件记录可审计的真实运行结果。没有日志支持的改进不得记为成功；训练样例和指标不得虚构。所有训练始终遵守“保护用户、维护人类”，不记录凭据、Token 或个人隐私。

## 2026-10-23：Trainer 初始化前的 NameError

- 证据：GitHub Actions Run [39906737838](https://github.com/mjw3177109/damoxingtest/actions/runs/39906737838)，第 11 次运行，最终 `completed / failure`；[原始报告](../reports/2026-10-23/run-39906737838/report.md)。
- 代码基线：该次运行 `head_sha=de5f1ffadee73e146cdf7ae16abaa159f4470060`；修复前主分支 `03093013a156d665444d036ac5b7538f8c58c791`。
- 数据版本：训练 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`（85 条）；固定验证 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`（24 条）。
- 真实环境：历史运行日志显示 Kaggle Tesla T4，14.56 GiB；Kernel 第 6 版最终轮询为 COMPLETE，但训练本身 FAILED。
- 根因：`scripts/train_gpt2_lora.py:395` 实例化未导入的 `DataCollatorForLanguageModeling`，产生 `NameError`。该局部变量未被使用；`Trainer` 实际传入 `response_only_collator`。
- 最小修复：删除未使用的初始化行，保留 `response_only_collator` 及 `-100` 回答标签掩码。先在修复分支提交，验证通过后才进入新 GPU 训练。
- 防复发：增加仅 CPU 的 PR 静态预检：Python 编译、Ruff F821 未定义名称检测、Trainer 数据整理器接线和 `-100` 掩码结构检查。
- 第 11 次训练指标：有效训练步数 0；Train Loss、Val Loss、PPL 和 `samples.json` 均未生成。不得用第 8 次历史指标代替本次。
- 晋级：拒绝；不覆盖历史已批准的 Adapter。
- 验证状态：修复分支静态结构已检查；CI 和 Kaggle 运行时验证需以对应真实 Actions 记录为准。**本条不是训练成功声明。**
- 后续实验：修复并完成至少一轮有效训练后，固定训练/验证数据及随机种子，仅改变一个超参数进行对照；以固定验证集 Loss/PPL、样例质量和安全审查共同决定是否晋级。

## 2026-10-23：第 12 次完成训练，但生成质量门槛未通过

- 证据：GitHub Actions Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，`completed / success`；[本次报告](../reports/2026-10-23/run-39921870784/report.md)、[指标](../reports/2026-10-23/run-39921870784/metrics.json)、[样例](../reports/2026-10-23/run-39921870784/samples.json) 与 [质量门槛](../reports/2026-10-23/run-39921870784/quality_gate.json)。
- 训练代码 SHA：`647b909a994441e3affa3f65fc46f9d0acb2c958`；训练方案 SHA-256：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 数据：85 条训练样本，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；24 条固定验证样本，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- Kaggle：历史轮询为 `QUEUED → RUNNING → COMPLETE`；训练日志及元数据确认实际使用 Tesla T4、14.56 GiB 显存，完成 3 epochs、33 个有效训练步；本记录不等于实时 Kaggle 状态查询。
- 实测指标：Train Loss `3.2464554599`；基础验证 Loss `3.3892908096`、PPL `29.6449209212`；微调后验证 Loss `3.1472766399`、PPL `23.2725985343`；本次相对基线验证 Loss 下降 `7.141%`。训练日志记录总流程耗时 `67.25s`，其中 Trainer 内部训练耗时约 `11.6575s`，两者不能混为一谈。
- **生成质量失败**：`samples.json` 有 10 条，9 条输出为重复句点、1 条为重复问号；自动生成质量启发式仅 `0/10` 通过。质量门槛 `promotion_approved=false`，因此 **候选 Adapter 不晋级**。工作流成功只证明训练/报告流程执行成功，不证明模型可用。
- 与第 11 次对比：旧的 `NameError` 已消失；从 0 步、无指标变为 33 步、完整指标及 10 条样例。第 8 次历史运行使用不同数据规模，不能直接当作同口径模型提升证据。
- **未确认根因**：重复标点可能与极小语料、目标模型能力、tokenizer/终止符、贪婪解码、训练超参数等因素有关；仅凭现有日志无法确定哪一个是主因，不应擅自声称已修复。
- **下一次受控实验（先推理、后决定是否重训）**：保留第 12 次 Artifact 内的候选 Adapter 与固定 10 条提示词，锁定模型权重、tokenizer、输入、随机种子，比较原有 greedy 解码与一组受控采样参数（例如 `do_sample=True, top_p=0.9, temperature=0.8, repetition_penalty=1.12, no_repeat_ngram_size=3`）；分别记录原始 token IDs、终止符、重复率、可读回答比例、人工安全审核。若采样仍无法产生有意义的中文回答，先诊断数据与 tokenizer/训练目标，再决定是否设计仅改变一个变量的 GPU 训练实验。**当前未执行该实验，不得报告其结果。**
- 防止浪费 GPU：本次已有完整训练证据，若训练数据与 recipe hash 未变化，使用仓库的重复训练保护；文档更新不应触发 GPU 工作流。
