# 2026-10-26 03:00 CST｜同数据重训阻断报告准确性审计

## 问题假设与真实根因
在 PR #70 的安全保护逻辑中，`tools/pre_submit_reuse_guard.py` 会对相同训练/验证数据但精确配方不匹配的历史训练返回 `BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL`。审查 `scripts/finalize_report.py` 发现：该状态虽会原样写入 `final_status.txt`，但此前报告的「下一步」统一归入凭据、GPU、网络或训练脚本故障，容易误导操作者进行无必要重试。属于报告语义缺陷，不是新的 GPU 故障。

## 本次最小变更（仅 PR #70 分支）
- `scripts/finalize_report.py`：单独解释审批阻断、未提交 Kaggle/未执行 GPU；下一步要求核实历史训练、仅经 `workflow_dispatch` + `approve_same_data_retrain` 明确审批，保留远端状态、并发与配额检查；避免将阻断误称为运行环境故障。
- `tests/test_blocked_retrain_report.py`：新增 1 项临时目录端到端离线回归，模拟阻断状态并执行报告生成，核查最终状态、审批说明、无新指标/样例以及不误报 GPU 故障。
- 变更前 PR head: `6c7edfdce869c5a91fd40efc4760e0bbed2bff9b`；本次代码/测试验证 head: `0313716370a203262fe788f1425cf09bd9e3e361`。
- 无训练参数、数据、模型、质量门槛或安全保护改动；PR 仍为 Draft，未启动 Kaggle。

## 实际验证证据
- GitHub Actions Static Preflight: Run `40223975187`，Job `121261343549`，`completed/success`。
- 真实 CI Job 日志：`test_blocked_same_data_report_explains_approval_without_gpu_claim ... ok`；`Ran 193 tests in 0.368s`；`OK`；`All checks passed!`。
- 这是 GitHub Runner 上的离线模拟/静态验收，不是 Kaggle 端到端训练验证。

## 训练和历史对照（无本小时新训练）
- 最新 Daily: `40165941479`，`completed/success` 但实际 `SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`，Artifact `12588187512` 存在且未过期。
- 最近实际 GPU 训练: `39921870784`，`reports/2026-10-23/run-39921870784`；Tesla T4，14.56 GiB，3 epochs，33 steps，Train Loss 3.246455，Val Loss 3.147277，PPL 23.272599；训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 历史固定生成样例 10 条，有效 0/10，仍存在连续标点输出；`promotion_approved=false`。Run 8 和 Run 12 验证集不同，不宣称跨轮历史最优改进。
- 本次 GPU、训练阶段、训练步数、Loss、PPL 和新样例：均无新结果。Kaggle 实时 Kernel 状态及剩余配额未能独立核实，不能将 Actions success 或 Kernel COMPLETE 视作训练成功。

## 质量门槛、回滚和下一步
- 仍拒绝候选晋级，保留历史已批准版本；不覆盖模型权重。
- PR #70 继续 Draft。下一步核实工作流事件/审批约束、Kaggle 远端 Kernel 状态和配额，再决定是否合并；不可自动重训。
- 历史 `DataCollatorForLanguageModeling` NameError 已核实不在最新训练路径中，`response_only_collator` 仍由 Trainer 使用；不重复提交。
- 本轮经验：**审批性阻断是预期安全决策，不能在报告中写成凭据或 GPU 故障；报告语义必须与工作流状态一致。**

## 安全与审计
不包含 Token、密钥或个人隐私；不修改安全保护。代码 SHA、Run/Job ID、数据版本、测试证据及是否晋级均可审计。
