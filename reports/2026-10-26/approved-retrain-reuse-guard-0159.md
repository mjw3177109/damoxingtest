# GPT-2 小时审计：显式重训审批被精确复用覆盖的修复（2026-10-26 01:59 Asia/Shanghai）

## 状态与可核验证据
- 仓库：`mjw3177109/damoxingtest`；仅修改 Draft [PR #70](https://github.com/mjw3177109/damoxingtest/pull/70) 分支，未合并 main，未提交 Kaggle Kernel。
- 本轮代码提交：`5745762b28c5732bd5dfa2af56c9bc505a181d6f`；测试提交：`59b31cda60d77b352cf0075fa4e45b8008c75954`。
- [Static Preflight Run 40218987357](https://github.com/mjw3177109/damoxingtest/actions/runs/40218987357)：completed/success；Job `121246232611`；真实 Job 日志显示新增 `test_cli_explicit_approval_bypasses_even_exact_reuse` 通过，`Ran 192 tests`、`OK`、Ruff F821 `All checks passed!`。该 CI 不执行 GPU 训练。
- 最近 [Daily Training Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：completed/success，但 `training_status.json` 明确 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；无新训练。
- 最近真实 GPU [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：已结束。Kaggle 实时 Kernel 状态、手动提交与剩余配额无法独立核实。
- 最新 main 报告目录：`reports/2026-10-25`；本报告暂仅在 PR 分支的 `reports/2026-10-26`。

## 根因、最小修复与验证边界
- 真实代码缺陷：`tools/pre_submit_reuse_guard.py` 在处理 `--approve-same-data-retrain` 之前始终调用 `find_reusable_run(... force_retrain=False)`。如果历史配置精确匹配，`reuse=true` 优先，用户已明确批准的受控重训仍会被静默跳过；审批参数无法达成其预期语义。
- 最小修复：仅当存在显式审批时跳过精确历史复用查找，进入既有 Kaggle 状态、并发及配额安全检查路径。没有修改训练超参数、模型权重、质量门槛或绕过远端保护。
- 新增回归：模拟存在精确历史匹配时，显式审批不调用复用查找/历史结果复制，写出 `reuse=false`、`blocked=false`，不在本地创建 Kaggle 输出，也不调用远端提交。旧的无审批阻断、数据变化、失败历史等测试仍通过。
- 限制：本轮只验证离线逻辑和 GitHub CI，没有调用 Kaggle CLI、GPU 或远端 Kernel；不能宣称端到端重训安全已获批准。PR #70 保持 Draft，不启动第 13 次训练。

## 历史训练、生成质量与产物核对
- 历史 Run 12：Tesla T4、14.56 GiB、3 epoch、33 有效步，Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`；同轮基线 Val Loss `3.389291`，改善 `7.141%`。训练集 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，验证集 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型固定 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 本小时新增 GPU 步数 0；无新增 Train Loss、Val Loss、PPL、权重或生成样例。最近正式样例含 `................................................................`；有效回答 0/10；`human_review_status=pending`、`promotion_approved=false`。
- 已读取最新 Daily 归档的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`。指标和样例均明确标记为历史复用，不是新训练。
- 最新 Daily Actions Artifact `12588187512` 存在、未过期（截至本轮核实）；本轮静态 CI 不产生新模型 Artifact。
- Run 8 与 Run 12 的验证集不同，不能把同轮 Loss 改善等同于跨轮历史最佳模型提升。候选不晋级，保留可回滚的既有版本。

## 经验与下一步
1. 自动复用和明确重训审批必须有清晰优先级：无审批时默认阻断重复训练；有审批时不能静默复用，但仍必须遵守 Kaggle 远端状态、并发和配额检查。
2. 下一步只读审计 PR #70 的失败路径及工作流事件约束，并完成真实远端状态/配额核实；这些条件不足时继续保持 Draft。
3. 训练质量仍为主要阻塞：独立验证集近重复风险与无效回答问题未解决，不为测试数量增长宣称模型进化。
4. 不提交密钥、隐私、敏感日志；保护用户、维护人类；任何候选晋级需独立质量验证与回滚证据。
