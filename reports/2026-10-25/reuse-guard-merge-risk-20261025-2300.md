# GPT-2 每小时审计：PR #70 合并前的 Kaggle 误提交风险（2026-10-25 23:00 Asia/Shanghai）

## 本轮真实状态和证据
- main 起点 SHA：`b4fa3af102f0273943ff6c7ea1ed831dad3517d6`。PR #70 仍为 **open/draft**，head SHA `07fa06cb247af518fd80c1f3d4204088216b2b54`，尚未合并。链接：https://github.com/mjw3177109/damoxingtest/pull/70
- GitHub Actions 列表（2026-10-25 23 时档读取）共 96 次；最新 Run `40200181212`，GPT-2 Static Preflight，completed/success，PR head `07fa06cb247af518fd80c1f3d4204088216b2b54`。真实 Job `121189516797` 日志记录 **183/183 单元测试通过**，Ruff F821 通过，response-only collator 与 -100 标签掩码检查通过。链接：https://github.com/mjw3177109/damoxingtest/actions/runs/40200181212
- 最近 Daily Run `40165941479` completed/success，但 `training_status.json` 为 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`，**没有执行本小时训练或评估**。链接：https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479
- 最近真实 GPU 训练 Run `39921870784` 已结束，Tesla T4、14.56 GiB、3 epoch、33 有效步、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`。本小时新增 GPU 步数：**0**；无新增 Loss/PPL。链接：https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784
- Kaggle Kernel 实时状态、并发及剩余 GPU 配额**未能独立核实**；不把历史 COMPLETE 等同于当前可提交。
- 最新 main 报告目录：`reports/2026-10-25`；本次报告仅新增文档，**不修改 scripts、kaggle、data 或工作流**。

## 本小时新增发现：PR #70 不能直接合并
1. `scripts/train_gpt2_lora.py::training_recipe_hash()` 对 **整个训练脚本字节内容**计算 SHA-256（另包含 notebook 和 requirements）。
2. PR #70 的 28 行新增配置检查会改变训练脚本字节，即使真实训练逻辑、数据和默认超参数不变，**训练配方哈希也必然变化**。
3. `tools/pre_submit_reuse_guard.py` 依赖 `find_reusable_run()`，后者必须满足 `previous.training_recipe_sha256 == training_recipe_hash()` 才会复用。Run 12 历史哈希为 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`，无法匹配改动后的训练脚本。
4. `.github/workflows/daily-gpt2-training.yml` 在 main 的 `scripts/**` push 和每天定时运行；复用失败时若 Kaggle 凭据就绪，工作流将进入状态查询与可能的 `kaggle kernels push` 路径。已有远端状态检查能阻止部分并发重复提交，**但不能阻止仅因审计逻辑变更而提交不必要的新训练版本**。
5. 因此 PR #70 **保持 Draft，不合并、不触发训练**。这是代码路径静态核查结论，尚未在真实 Kaggle 执行验证；不能写成已经误提交。

## 训练质量、样例和报告文件
- 历史 Run 12 数据：训练 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 最近 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均在 GitHub 仓库中逐项读取核实。历史样例含 `................................................................`，有效生成 0/10，`promotion_approved=false`。
- 最新 Daily Artifact ID `12588187512`（未过期，2026-11-24 到期）；历史 GPU Artifact ID `12487687305`（未过期，2026-11-22 到期）；最新静态 CI Run `40200181212` 无 Artifact。
- Run 8 与 Run 12 使用不同验证集，且留出集存在近重复风险；不能宣布跨轮历史最佳改善或模型晋级。

## 修复/实验计划与经验
- **当前阻塞根因：** 训练复用参数检查修复本身改变了训练配方哈希，可能将纯保护性变更误认为值得重新训练。先保留 PR #70 的现有 183 项已通过测试，避免直接合并消耗 GPU。
- **下一次可测量的无 GPU 实验：** 在隔离临时仓库构造真实历史数据/配方哈希、只修改复用检查函数，运行 `pre_submit_reuse_guard.py`；预期证明当前逻辑无法复用。随后提出最小、可审计且 fail-closed 的分离方案（训练语义变更才允许训练，保护性工具变更不触发 GPU），增加回归测试后再审查合并。
- 历史 `DataCollatorForLanguageModeling` NameError 当前已消除；`response_only_collator` 仍连接 Trainer，不重复修复。
- 经验：**“单测通过”不等于“部署/合并不会触发副作用”**。对接自动 GPU 工作流的修复必须同时验证触发器、配方指纹、预提交跳过和远端运行状态。
- 本轮无训练、无新生成样例、无模型晋级、无凭据暴露，未更改或绕过安全保护。原则：保护用户，维护人类。
