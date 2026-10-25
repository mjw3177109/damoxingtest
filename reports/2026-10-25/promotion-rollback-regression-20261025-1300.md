# GPT-2 每小时审计：已批准 Adapter 不覆盖回归（2026-10-25 13 时档，Asia/Shanghai）

## 本轮假设与范围
- 假设：PR #63 已将自动质量初筛与正式晋级分离，但现有合成测试只验证「不存在批准目录」的情况，未覆盖「已有批准 Adapter 与版本文件」的不可覆盖不变量。
- 本轮只扩充 `tests/test_promotion_review_gate.py` 的回归场景并同步更正 README 的旧晋级描述；不修改训练代码、工作流、数据、模型权重、密钥或 Kaggle 配置。
- 基线 main SHA：`58811fb764a52a8c8dc8c3ae5b3ff04f81d5e982`。本轮测试提交 `4ad1b9ad1e898ef33124f0d729961a9b47a446e0`，文档提交 `2fd4f11821437cd408f0c363c9c52c1d066d5dfc`。

## 真实验证证据
- [PR #64](https://github.com/mjw3177109/damoxingtest/pull/64) 在隔离分支运行，无 GPU 训练。
- [Static Preflight Run 40163938477](https://github.com/mjw3177109/damoxingtest/actions/runs/40163938477)：`completed/success`，测试代码 SHA `2fd4f11821437cd408f0c363c9c52c1d066d5dfc`。
- CI Job 日志明确：`Ran 148 tests`、`OK`、`All checks passed!`、`PASS: response-only collator and -100 masking retained`。
- 新增两项实际执行 gate Python 代码的合成测试：已有已批准 Adapter 时，分别让候选通过和不通过自动初筛，验证 Adapter 字节 `approved-model-v1` 和 `adapter_version.json` 完全不变。
- 这验证的是隔离合成样本下的保护不变量，**不等于**已验证生产环境真实回滚、独立人工审核或模型质量。

## Actions、Kaggle 与训练证据
- 最新真实 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，历史 `training_status.json` 为 `completed`；Tesla T4，14.56 GiB，3 epoch，33 step；Train Loss 3.2464554599，Val Loss 3.1472766399，PPL 23.2725985343，同轮基线 Val Loss 3.3892908096。
- 最新 Daily：[Run 40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092)，`completed/success` 但 `skipped_no_changes=true`，`training.log` 明确无 GPU 更新，仅复用历史证据。
- 训练集 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证集 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 真实历史生成样例：`................................................................`，正式质量门槛 0/10、`promotion_approved=false`。本轮无新样例、Loss、PPL 或模型权重；不晋级。
- GitHub Artifacts：GPU Run 的 ID `12487687305`、Daily Run 的 ID `12549545432` 均通过本轮 Actions Artifact API 核实存在且未过期；本轮 Static Preflight Run 无 Artifact。
- 历史 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 在两轮日期目录中均存在；本轮重新读取了其中的训练指标、状态、质量门槛与生成样例。
- Kaggle Kernel 实时状态及配额无法独立核实；历史 Version 8 COMPLETE 不代表当前空闲或可再次训练。

## 结论、对照与下一步
- 相比上一轮 146 项测试，本轮新增两项保护回归并达到 148 项通过；GPU 训练和语义质量无新增结果。跨 Run 8 / Run 12 的验证集不同，不能宣称跨轮历史最佳。
- 旧 `DataCollatorForLanguageModeling` NameError：重新读取 main 的 `scripts/train_gpt2_lora.py`，无该符号引用，`response_only_collator` 仍由 Trainer 使用。
- PR #60 与 PR #62 仍 Draft；后者仍存在语义重叠风险。保持第 13 次 GPU 训练暂停，不重复提交失败代码。
- 下一步优先核实已批准 Adapter 的真实可回滚版本是否存在，设计独立审批/签名的可审计操作流程；再解决独立评估集和模型生成语义失败。
- 经验：回归测试不能只验证「新候选未晋级」，还要验证「旧批准版本的权重和元数据保持不变」；CI success 仅代表工程测试通过，不代表训练成功或模型能力提升。

本报告仅含公开仓库路径、测试证据、SHA、Run/Artifact ID 与非敏感指标，不包含任何 Token、密钥或个人隐私。
