# GPT-2 每小时工程审计｜ZIP 解压资源上限（2026-10-25 18:00 Asia/Shanghai）

## 假设、真实根因与受控修复
- 修复前 main SHA：`4fd4c4311d74f45dc9a6934e40d518da2687fd23`。
- 真实代码缺口：`tools/audit_adapter_artifact.py` 在执行 `ZipFile.testzip()` 全量完整性扫描前，没有限制成员数量或声明的解压后总大小；异常高压缩比或大量成员可能造成过量 CPU/内存/IO 消耗。这是**审计工具的资源风险**，不是已发生的 GPU 训练故障，未声称观察到实际攻击。
- 最小修复：先读取 ZIP central directory 中的元数据并检查 **成员数 <= 512、单成员解压大小 <= 128 MiB、总解压大小 <= 256 MiB**；不满足时在 `testzip()` 前拒绝。未修改模型、数据、训练方案、晋级门槛、凭据或正式 Adapter。
- 新增 `tests/test_zip_preflight_bounds.py` 4 项离线合成测试：成员数量、单成员大小、累计大小均必须在完整性扫描前拒绝，普通小 ZIP 仍按原逻辑处理。

## 真实代码、CI 与 PR 证据
- 修复提交：`140180b168afe9ade8588a82ac1ff88482383ab4`；测试提交：`5407f34e351690ed433baa85850885a87e15e4b4`。
- PR [#68](https://github.com/mjw3177109/damoxingtest/pull/68) 已通过检查并以 squash 合并到 main，合并 SHA `2c0852466e7ba1748b153ef8228cc135eefbbce7`。
- [Static Preflight Run 40182926751](https://github.com/mjw3177109/damoxingtest/actions/runs/40182926751) completed/success，Job `121137619849` 日志明确显示 **172/172 单测通过**、Ruff F821 通过、response-only collator 和 -100 masking 检查通过。
- CI 属于合并前 PR 代码验证，合并后主分支未单独执行完整测试；不能把 PR CI 说成合并后复测。
- 新增检查在合成 ZIP 上经过 CI 验证；**没有**在本轮重新下载 Run 8/12 真实 ZIP 并执行新版工具，因此不声称真实历史 Artifact 已经重新通过该新增门槛。

## Actions、Kaggle 与模型证据
- 截至本次巡检，最新 Daily [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) 为 completed/success，但 `training_status.json` 为 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`，本小时无 GPU 训练。
- 最新 Daily Artifact `12588187512` 存在、未过期（到期 2026-11-24 UTC）；历史 Run 8 Artifact `12415142300`、Run 12 Artifact `12487687305` 在此前巡检已通过 ZIP、配置和 safetensors 结构检查，本轮未重复下载。
- 最近真实 GPU 训练 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4 / 14.56 GiB、3 epochs、33 steps、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`，同轮基线 Val Loss `3.389291`。本小时新训练步数 0，以上均是历史指标。
- 训练配置：学习率 `0.0002`、LoRA rank `8`、seed `42`、max_length `256`；训练数据 85 条（SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`）、固定验证 24 条（SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`）；配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- `reports/2026-10-25/run-40165941479` 中的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`quality_gate.json`、`training_status.json` 已核实存在。最新样例为历史复用的连续句点/问号，质量初筛 0/10，`promotion_approved=false`，人工审核 pending。
- Kaggle Kernel 实时状态及剩余 GPU 配额**未能独立核实**；不得将 Actions success 或历史 Kernel COMPLETE 等同训练成功。
- `scripts/train_gpt2_lora.py` 当前没有 `DataCollatorForLanguageModeling` 的旧引用，`response_only_collator` 仍保留；不重复提交旧 NameError 修复。

## 对照、经验与下一步
- 上轮 168 项测试，本轮 **172 项**；工程新增 ZIP 资源约束与 4 项回归测试；训练指标、模型质量与晋级**无新增**。Run 8 与 Run 12 验证集不同，无法同口径确认历史最佳。
- 经验：ZIP 完整性扫描本身也需要资源预算，必须先审查声明的解压规模，再做 CRC、配置与 safetensors 校验；通过文件结构验证不等于真实 PEFT 加载成功或安全审核通过。
- 后续受控实验：在隔离 CPU 环境对历史 Run 8/12 Adapter 做真实 PEFT 加载、Tokenizer/基础模型兼容性检查和一条非敏感推理；记录模型/数据 SHA、耗时、成功率及生成质量，与 Run 12 及可核实历史版本同口径比较。PR #60 与 #62 继续保留 Draft，独立验证集与回滚链路未完成。
- 晋级决定：**拒绝**。未核实 Kaggle 配额、并发状态、正式批准权重与独立评估前不启动第 13 次训练；不泄露凭据、隐私，不绕过安全保护。
