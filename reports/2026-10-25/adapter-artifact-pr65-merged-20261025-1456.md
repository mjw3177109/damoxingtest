# GPT-2 小时审计：Adapter Artifact 来源工具合并与训练状态（2026-10-25 14:56 Asia/Shanghai）

## 范围、假设与代码版本
- 仓库：mjw3177109/damoxingtest。仅在有证据的情况下更新结论，不将 CI 成功、Kaggle COMPLETE 或 ZIP 存在等同于训练成功、模型批准或持久回滚。
- [PR #65](https://github.com/mjw3177109/damoxingtest/pull/65) 已从 Draft 转为 Ready 并以 squash 合并，合并 SHA `7005946584f4763156dc3683c50f7ff9a03ca517`。
- 本轮合并仅涉及 `tools/audit_adapter_artifact.py`、`tests/test_audit_adapter_artifact.py` 与先前审计报告；不修改生产训练脚本、训练/验证数据、权重、质量门槛、凭据。
- 假设：先把可复现、只读的候选归档完整性检查工具纳入主分支，再设计持久备份与独立审批机制；此步骤本身不会提高模型语义质量。

## 本小时 Actions、Kaggle 与实际训练
- 截至本轮查询，Actions 累计 84 个 Run。最新 [Static Preflight Run 40168017207](https://github.com/mjw3177109/damoxingtest/actions/runs/40168017207)：`completed/success`，对应 PR #65 head `45919b9d7f5d1d576f2cea39268ed431fd5f8911`；真实日志显示 153/153 单元测试通过、Ruff F821 通过、response-only collator 与 -100 masking 检查通过。**这些是合并前 CI 证据，合并后未发现新的 CI Run。**
- 最新 [Daily Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：`completed/success`，但 `training_status.json` 为 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`，本次 GPU 有效步数 0，没有重新评估。报告日期目录 `reports/2026-10-25/run-40165941479`。
- Daily Artifact ID `12588187512`，未过期，过期日 2026-11-24；最新 Static Preflight 没有 Artifact。Run 12 历史 GPU Artifact ID `12487687305`，此前已下载检查；历史 Run 8 Artifact ID `12415142300`。
- Kaggle 规范 Kernel ID `mjw3177109/damoxingtest-gpt-2-daily-training`；**实时 Kernel 状态、版本更新与剩余 GPU 配额未能独立核实**。本轮未调用 Kaggle 提交接口，也未启动第 13 次训练。
- 历史 `scripts/train_gpt2_lora.py` 的 `DataCollatorForLanguageModeling` NameError 已核实：main 当前该符号引用数为 0，`response_only_collator` 仍作为 Trainer 的 data_collator。避免重复修复和 GPU 浪费。

## 最新产物核查
- 最新 Daily 目录存在 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`。其中 `training.log` 明确记录 `PRE_SUBMIT_SKIPPED_NO_CHANGES`。
- 最新 Daily `metrics.json` 中 `train_loss=null`、`train_steps=0`、`gpu_name=null`，并明确标记历史指标复用。不能把历史数值视为本小时测量。
- 最近一次真实 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，历史训练 3 epochs / 33 有效步，Tesla T4 / 14.56 GiB，Train Loss 3.2464554599、Val Loss 3.1472766399、PPL 23.2725985343；基线 Val Loss 3.3892908096，同轮相对下降 7.141%。
- 历史训练配置：学习率 0.0002，LoRA rank 8，seed 42，max_length 256，训练 85 条，验证 24 条。训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 最新保存的 10 条生成样例仍是历史复用；代表性输出为 64 个句点，另有问号重复，真实有效样例 0/10。质量门槛 `promotion_approved=false`，`human_review_status=pending`。本小时**无新生成**。

## 对照、风险、经验与下一步
- 与上一轮比较：新增 **PR #65 已合并**及可复现只读审计工具进入 main；GPU 步数、Loss、PPL、生成质量、模型晋级均无新增变化。历史 Run 8 与 Run 12 验证集不同，不能据此确定跨轮历史最佳；没有新证据支持晋级。
- 两份历史 ZIP 均包含候选 LoRA 权重，但仓库仍未证实已批准正式模型的持久权重、独立审批清单与端到端恢复验证。ZIP 可读不等于模型可运行、已批准或可长期回滚。
- PR #60（推理输入字段一致性）与 PR #62（eval v2 候选）仍为 Draft；后者存在语义重叠风险。未经验证不合并、不触发 Kaggle GPU。
- 下一步可测量实验：使用隔离环境对候选 ZIP 执行**只读、受限、非执行式**元数据一致性检查（文件清单、哈希、配置字段和预期基座版本），新增合成反例测试；与当前 5 项检查比较覆盖率和误报率。之后单独设计正式模型批准清单、不可变哈希绑定、持久备份与隔离恢复验收。模型语义质量改善须通过独立数据与安全评估另行证明。
- 本轮经验：**候选完整性审计、批准证据、持久回滚与模型质量必须分别验证。** 最小变更可通过 CI 合并，但不能称为模型进化。
- 安全原则：保护用户、维护人类；不记录 Token、密钥或个人隐私；不绕过审批、不并发训练、不无界重试、不覆盖已批准版本。
