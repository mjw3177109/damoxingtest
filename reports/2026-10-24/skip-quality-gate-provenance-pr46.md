# 2026-10-24 21:00（北京时间）｜GPT-2 质量门槛证据来源修复（PR #46）

## 状态与可核验证据

- 代码主分支合并 SHA：`e96bcc86bfcec9759c6ed27deae867375b84da76`
- PR：https://github.com/mjw3177109/damoxingtest/pull/46
- 静态预检 Run：https://github.com/mjw3177109/damoxingtest/actions/runs/40096316208 （completed/success）
- 本轮测试：106/106 通过，其中新增 4 项质量门槛回归测试；Python 编译、Ruff F821、response-only collator 与 -100 标签掩码检查通过。
- 本轮没有启动 Kaggle Kernel、GPU 训练、模型生成或新模型晋级；未修改安全规则、训练数据、权重或历史最佳版本。
- 最近真实 GPU 训练 Run：https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784 （已结束，33 步）
- 最近 Daily Run：https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092 （completed/success，但 `SKIPPED_NO_CHANGES`，本轮 0 步）
- 最近 Kaggle 历史记录：Kernel Version 8，Actions 日志记录 `QUEUED → COMPLETE`；**未独立核实当前 Kaggle 实时状态**。

## 问题、根因和最小修复

观察到 Daily Run 40065584092 在 `skipped_no_changes=true`、仅复用历史证据时，`quality_gate.json` 同时记录 `LoRA adapter files missing`，容易被误读为“新训练候选缺失模型文件”。实际上这次运行没有新候选模型，不应要求存在新的 Adapter。旧 `candidate_status=completed` 也没有区分“训练完成”与“复用完成”。

最小修复只改 `.github/workflows/daily-gpt2-training.yml` 的质量门槛报告逻辑：

1. 对 `skipped_no_changes=true` 的复用运行，不再附加误导性的 `LoRA adapter files missing` 原因，保留明确的 `No new training candidate was created; prior evidence was reused.` 拒绝原因。
2. 质量门槛记录 `candidate_status=skipped_no_changes`、`evidence_reused=true`。
3. **真正完成的新训练**若缺少 Adapter，仍按原逻辑拒绝；质量阈值、晋级条件、历史已批准权重均未改变。

## 测试证据与风险边界

新增 `tests/test_quality_gate_provenance.py`，从工作流提取并实际执行内嵌的质量门槛 Python，对四种离线模拟条件验证：复用且无 Adapter、复用但意外有 Adapter、真实训练缺 Adapter、真实训练有 Adapter 且满足既有自动阈值。前两种绝不晋级；第三种拒绝；第四种保留原有晋级路径（仅模拟文件，不是训练或真实模型质量认证）。

CI 通过并合并 PR #46；**下一次真实 Daily 工作流的端到端验收尚未发生**，不能将本轮单测当作生产运行成功。

## 历史模型指标（不是本轮新增）

- 来源：`reports/2026-10-23/run-39921870784/metrics.json`
- GPU：Tesla T4，14.56 GiB；Epoch=3；训练 33 步。
- Train Loss=3.246455；Val Loss=3.147277；PPL=23.272599。
- 训练集 85 条，固定验证集 24 条。
- 质量门槛：0/10 有效生成，`promotion_approved=false`；样例为重复标点，候选不晋级。
- 数据 SHA-256（训练）：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`
- 数据 SHA-256（验证）：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`
- 训练方案 SHA-256：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`
- 与第 8 次历史训练的验证集不同，不能据 Val Loss 直接排名历史最佳。

## 经验、下一步和晋级决定

经验：`Actions success`、`Kaggle COMPLETE`、`training_status=completed`、历史指标存在，均不能替代“本轮有新训练候选”的证据；复用报告应在状态与拒绝原因上明确标识来源，避免误导。

下一步：等待下次自然 Daily 运行验证新字段、未提交重复 Kernel、质量门槛继续拒绝复用证据；随后在隔离 CPU 中继续分析标点/UNK 重复轨迹。只有真实质量门槛、静态检查、测试、训练和样例评估均满足条件才考虑晋级。当前**拒绝晋级、不启动第 13 次 GPU 训练**。

安全：不保存密钥、Token、用户隐私或原始敏感提示词；保护用户、维护人类。
