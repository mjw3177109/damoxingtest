# GPT-2 质量初筛来源一致性审计｜2026-10-26 10:00 CST

## 假设与真实根因
当前质量初筛虽然检查 GitHub Run 的 `status.txt == COMPLETE`，但原实现没有核对下载的 `metrics.json`、`run_metadata.json` 与当前 checkout 的训练数据、验证数据和训练配方。远端 `COMPLETE` 只表示 Kernel 状态，不能证明产物来自当前代码与数据；这是通过实际工作流代码检查发现的潜在证据归属缺陷，**不是已发生错误晋级的证据**。

## 本轮最小修复
- 在 `.github/workflows/daily-gpt2-training.yml` 的 Candidate quality gate 中读取 `run_metadata.json`，缺失则 fail closed。
- 对当前 checkout 的 `data/safety_humanity_train_v2.jsonl`、`data/safety_humanity_eval_v1.jsonl` 计算 SHA-256，并要求 `metrics.json` 与 `run_metadata.json` 中的对应哈希均匹配。
- 按 `scripts/train_gpt2_lora.py::training_recipe_hash` 的原有约定，对训练脚本、Kaggle notebook 和 requirements 文件计算配方 SHA-256，并与两份产物核对。缺文件直接拒绝。
- 保留旧有跳过训练的来源拒绝、当前 Run COMPLETE 检查、样例门槛、人工复核与 `promotion_approved=false`，不更改训练参数或 GPU 提交流程。

## 证据与验证
- PR: https://github.com/mjw3177109/damoxingtest/pull/70 （Draft，不合并）
- 新增 4 项离线回归：训练数据哈希不匹配、验证数据哈希不匹配、配方哈希不匹配、元数据缺失。四项均拒绝 `automated_precheck_passed`。
- 中间 CI `40256924806` 与 `40256950093` 失败；后一轮发现原有 promotion 测试夹具没有提供新要求的真实结构元数据（2 项失败），随后补齐合法合成数据、配方和元数据。保留失败证据。
- 修复后 CI: https://github.com/mjw3177109/damoxingtest/actions/runs/40257005958，`completed/success`，**210/210** 测试通过；Ruff F821、response-only collator 与 `-100` 标签掩码检查通过。
- 代码提交：`7e721321e3aa9b31e2b9c40b46010257603f9b6e`（测试），`0bdda47eab84048ae27ea2cd7dfbdf36fc6359ed`（门槛），`896c3e021d40a17c25a72b93d73ea18c4f20551e`（测试夹具）。
- **无 Kaggle GPU 提交，无模型参数更新，无新训练指标，无新样例。**

## 历史训练证据（不是本轮指标）
- 最近真实 GPU 训练：Actions Run `39921870784`，2026-10-23，Tesla T4 14.56 GiB，3 epochs，33 steps，Train Loss 3.246455，Val Loss 3.147277，PPL 23.272599。
- 训练集 85 条，验证集 24 条。数据 SHA：train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；eval `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 历史 recipe SHA：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`；当前 PR 不启动重训。
- 10 条历史生成样例均为连续标点，质量初筛 0/10，人工审核 pending，晋级拒绝。
- 最新 Daily Run `40165941479`：`SKIPPED_NO_CHANGES`，复用 Run 12，未提交 Kaggle Kernel；其 Artifact `12588187512` 存在。历史训练 Artifact `12487687305` 存在。

## 边界、对照与下一步
- 本轮验证的是**工作流中真实质量门槛代码的离线回归**，不是 Kaggle 远端端到端验证。远端 Kernel 当前状态、GPU 配额与仓库外手动提交尚未独立核实。
- 当前训练产物**尚未记录 Kaggle clone 的精确 Git commit SHA**。本轮以训练配方哈希加数据哈希约束训练相关来源，不能将其称为完整 Git SHA 或 Kernel version 归属验证；下一轮应在不消耗 GPU 的前提下设计可核实的精确 SHA/Kernel 版本记录与对照。
- 相较上一轮：测试数从 206 到 210；安全门槛新增来源一致性检查。模型 Loss/PPL 与生成质量**没有新变化**，历史最佳跨不同验证集不可直接比较。
- 可测量的后续实验：为 Kaggle clone 的 commit SHA、提交版本与当前 Actions Run SHA 增加独立来源校验，构造不同 SHA 的合成样例，期望 100% 拒绝不一致，且合法匹配样例通过离线初筛。
- PR 继续保持 Draft；禁止无授权 GPU 重训、并发重试或模型自动晋级。保留上一已批准 Adapter 及回滚能力。
- 项目原则：保护用户、维护人类；不写入凭据或个人隐私。
