# GPT-2 每小时审计：真实 Adapter Artifact 可恢复性与批准证据（2026-10-25 14 时档，Asia/Shanghai）

## 目标、范围与假设
- 目标：区分「GitHub Artifact 内有完整候选 LoRA 权重」与「存在独立批准、可长期回滚的正式模型」，避免错误宣称已完成正式版本保护。
- 基线 main SHA：`40a597016b272e820525349add7fb4f972e71934`；新增只读检查工具 `tools/audit_adapter_artifact.py` 和 5 项合成测试 `tests/test_audit_adapter_artifact.py`。
- 只读取两个历史 GitHub Actions ZIP Artifact，检查 ZIP 完整性、单一 Adapter 权重、同目录配置、权重大小和 SHA-256；不解压执行、不加载模型、不使用 GPU/Kaggle 凭据、不写正式 checkpoint。
- 代码审计仅证明归档可读取，**不等于**独立审批、安全评估、权重运行时可加载或持久回滚。

## 本小时真实 Actions 与训练结果
- [Daily Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：2026-10-25T05:33:02Z 开始，`completed/success`；[报告](../run-40165941479/report.md) 的最终状态 `SKIPPED_NO_CHANGES`。
- `training_status.json`：`skipped_no_changes=true`、`kaggle_kernel_submitted=false`。本轮未训练、未评估、未更新 GPU 参数。新 Artifact ID `12588187512`（存在、未过期），只是本轮跳过状态与历史证据的归档。
- [第 12 次真实 GPU 训练 Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4，14.56 GiB，3 epochs、33 steps，Train Loss 3.2464554599、Val Loss 3.1472766399、PPL 23.2725985343；基线 Val Loss 3.3892908096。同轮 Val Loss 相对下降 7.141%，但固定生成质量 0/10，`promotion_approved=false`。
- 历史训练数据：85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证集 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 历史样例：`................................................................`（无实际回答）；本小时无新样例、Loss、PPL。
- 最新运行 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均存在；本轮质量门槛仍拒绝晋级。Kaggle Kernel 实时状态与剩余配额未能独立核实。

## 实际下载并检查的 Artifact
| 训练来源 | Artifact ID | ZIP 检查 | adapter_model.safetensors 大小 | SHA-256 | 结论 |
|---|---|---|---:|---|---|
| Run 39748259656（历史第 8 次） | `12415142300` | 通过 | 3,253,104 bytes | `193662ceb27b530e400e97a234492999acc9c395e9d7eddcec470b8266cade1a` | 候选权重可读取；未核实正式批准 |
| Run 39921870784（第 12 次） | `12487687305` | 通过 | 3,253,104 bytes | `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c` | 候选权重可读取；质量门槛失败，不得晋级 |

- 两个 ZIP 都含 `adapter_config.json` 与 `adapter_model.safetensors`，但均未发现 `checkpoints/adapter_latest` 或 `checkpoints/adapter_version.json`。
- GitHub main 完整树（`truncated=false`）中也没有 `checkpoints/`、`adapter_version.json` 或批准版本元数据。
- 由此只能确认**两个历史候选 Artifact 当前可恢复**，不能证明存在已批准正式模型的独立备份。GitHub Actions Artifact 有保留期，不是持久版本仓库。
- Run 8 的验证集 5 条、训练集 30 条；Run 12 的验证集 24 条、训练集 85 条，指标不能直接做跨轮历史最佳排名。
- 历史 NameError：main `scripts/train_gpt2_lora.py` 中无 `DataCollatorForLanguageModeling` 引用，`response_only_collator` 仍由 Trainer 使用；不重复提交修复。

## 测试与可复现方法
- 本地执行 `python -m py_compile tools/audit_adapter_artifact.py tests/test_audit_adapter_artifact.py`：通过。
- 本地执行 `python -m unittest discover -s tests -v`（在仅包含本次两个新增文件的隔离目录）：**5/5 通过**；仓库完整测试总数以 PR CI 为准，不能提前声称 153/153。
- 两份真实 ZIP 均执行 `python tools/audit_adapter_artifact.py <artifact.zip> --run-id <id>`，返回 `candidate_recoverable=true`、`approval_verified=false`，上述 SHA-256 与大小由实际 ZIP 字节计算。
- 合成测试覆盖：完整候选仍不批准、缺配置、多个候选歧义、路径穿越、空权重。工具从不执行或解压归档内容。

## 风险、经验与下一步
1. 现有 PR #60（推理输入协议）与 PR #62（eval v2）均为 Draft；不合并，不触发 GPU。
2. 已知阻塞：**没有独立批准清单、正式权重持久备份与已验证的回滚恢复流程**。不得把 Run 8 或 Run 12 候选直接当作正式已批准版本。
3. 下一阶段需设计明确的人工批准元数据、内容哈希绑定、持久归档和隔离恢复验证；先在合成环境验证，之后由独立审查者决定是否批准，不绕过现有保护。
4. 第 13 次 GPU 训练继续暂停；Kaggle 实时状态与配额未知，不重复提交。
5. 本轮经验：**Artifact 存在 ≠ 模型已批准 ≠ 可长期回滚**。必须分别验证 ZIP 完整性、权重可读取、独立审核和长期保存。
6. 所有检查均为只读，报告只保存公开 SHA、Run/Artifact ID、训练指标与非敏感路径，不含凭据或个人隐私。
