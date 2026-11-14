# GPT-2 每小时审计：训练复用配置一致性修复候选（2026-10-25 22:00 Asia/Shanghai）

## 本轮真实状态
- 仓库主分支审计起点 SHA：`b4fa3af102f0273943ff6c7ea1ed831dad3517d6`；本轮变更仅在 Draft [PR #70](https://github.com/mjw3177109/damoxingtest/pull/70) 的 `fix/reuse-training-config-20261025-22` 分支，**尚未合并 main**。
- 最新真实 Actions：[Static Preflight Run 40200119053](https://github.com/mjw3177109/damoxingtest/actions/runs/40200119053) completed/success，job `121189332429`；**183/183 单元测试通过**，包括新增 7 项无 GPU 回归测试。Python 编译、Ruff F821、response-only collator/-100 掩码均通过。PR 测试代码 SHA `9cf13113a66862ee0c5b3a61507afd0213e26740`。
- 最近 Daily：[Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) completed/success，但状态为 `PRE_SUBMIT_SKIPPED_NO_CHANGES`；`kaggle_kernel_submitted=false`，没有本小时 GPU 训练、评估或新样例。
- 最近真实 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束。Kaggle Kernel Version 8 COMPLETE 仅为历史状态；**当前 Kernel 运行状态、GPU 配额、并发状态均未能独立核实**。
- 最新报告目录：`reports/2026-10-25`。最新 Daily Artifact `12588187512`、真实 Tokenizer 审计 Artifact `12599861115` 存在且未过期。PR CI 本身无新模型 Artifact。

## 真实缺陷、根因和最小修复
- 根因：`scripts/train_gpt2_lora.py::find_reusable_run` 原先只核对训练集、验证集及配方文件 SHA。**直接 CLI 修改 learning_rate、seed、batch_size、模型或 LoRA 参数后，仍可能复用不匹配的旧训练指标和样例**；指定已有 Adapter 时也可能错误复用从基础模型训练的历史运行。这是证据复用完整性问题，**没有证据表明历史 Daily 发生过该误复用**。
- 本轮在训练复用判断中加入历史 `run_metadata.json` 与训练相关参数的一致性检查，缺失字段拒绝复用，指定 prior Adapter 拒绝 base-model 复用。原先的训练逻辑、超参数、Kaggle 工作流、质量门槛、权重和数据均未修改。
- 新增 `tests/test_training_reuse_config.py` 7 项测试：默认参数匹配、learning_rate 不匹配、model/batch 不匹配、LoRA/seed 不匹配、prior Adapter、缺失元数据、临时仓库端到端复用判定。真实 CI 已通过。
- 变更提交：`3cd889d7ec83d5848278d3e0f6bbe2b8f54d5740`（脚本），`9cf13113a66862ee0c5b3a61507afd0213e26740`（测试）。**Draft 保留待进一步审查；未合并，不触发主分支脚本变更引起的潜在 Kaggle 提交。**

## 训练质量与来源证据
- Run 12 真实历史指标：NVIDIA Tesla T4，14.56 GiB；3 Epoch、33 有效步；Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`；基线 Val Loss `3.389291`，同轮改善 `7.141%`。本小时新增训练步数为 **0**，没有新增 Loss/PPL。
- 数据版本：训练 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 最近 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已逐项读取。指标与样例来自历史 Run 12；样例包含连续句点 `................................................................`，有效生成 **0/10**，`promotion_approved=false`，人工审核 pending。
- 第 8 次和第 12 次验证集不同，且留出集有近重复风险；**不能宣称超过历史最佳**。本轮仅提升复用判断的证据一致性，不是模型质量改善。

## 已知限制、经验与下一步
1. `max_new_tokens` 尚未包含历史训练元数据，不属于本次训练配置一致性修复的覆盖范围；后续可独立设计生成参数证据指纹，不应混入未经测试的改造。
2. 新增检查已通过真实 CI，但尚未经过 Kaggle 端到端验证。合并前须确认预提交 guard 在默认参数下仍安全跳过，且任何异常都不会造成并发重复 GPU 任务。
3. 历史 `DataCollatorForLanguageModeling` NameError 已不在当前代码中，`response_only_collator` 仍连接 Trainer；不重复提交相同修复。
4. 经验：**同一数据 SHA 和同一源码 SHA 并不代表同一训练实验**；训练参数及起始 Adapter 同样属于可复用证据的必要条件。
5. 下一次可测量实验：在无 GPU 隔离测试中，构造相同数据/配方、仅改变单一学习率或起始 Adapter 的两组配置，要求默认配置复用、变更配置拒绝复用；若需要真实训练，先核实 Kaggle 实时状态、配额和回滚，再审批单次受控运行。
6. 本轮没有泄露凭据、没有改动安全保护、没有自动晋级或覆盖任何已批准模型。原则：保护用户、维护人类。
