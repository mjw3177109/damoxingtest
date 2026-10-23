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
