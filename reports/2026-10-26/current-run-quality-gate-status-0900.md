# GPT-2 T4｜当前运行质量门槛状态一致性修复（2026-10-26 09:00 Asia/Shanghai）

## 假设、根因与影响范围
- 发现并复现一项工程证据完整性缺陷：`.github/workflows/daily-gpt2-training.yml` 的 Candidate quality gate 只看下载目录中的 `training_status.json`、`metrics.json`、`samples.json` 和 Adapter 等文件，没有要求**本次 GitHub Run 的 `status.txt` 必须为 `COMPLETE`**。
- 当当前 Run 为 `KAGGLE_OUTPUT_UNAVAILABLE`、`BLOCKED_EXISTING_KERNEL_ACTIVE` 或状态文件缺失，但目录中残留看似完整的历史/部分文件时，旧逻辑仍可能把 `automated_precheck_passed` 记为 `true`。这是报告/初筛的证据归属风险；自动模型晋级本来已禁用，**没有发现历史真实误晋级或误训练证据**。
- 修复仅影响质量初筛及测试，不改训练超参数、数据、Kernel 提交逻辑、权重、自动晋级禁令或已批准模型。

## 最小修复与真实验证
- 在质量门槛读取当前 `RUN_DIR/status.txt`；仅 `COMPLETE` 可继续尝试自动初筛，其他值（包括缺失）统一增加理由 `Current GitHub run has no verified COMPLETE Kaggle status`。不会将不可信状态原文写入理由。
- 更新两个现有测试文件的合成状态夹具，新增 3 个离线回归：下载失败但存在旧完整文件、已有活动 Kernel 的旧文件、当前状态缺失。
- 失败复现： [Static Preflight 40251989891](https://github.com/mjw3177109/damoxingtest/actions/runs/40251989891)，`completed/failure`，203 项测试中 3 项失败（质量门槛代码更新但测试夹具尚未同步）；**仅 CI，未启动 GPU**。
- 修复验证：[Static Preflight 40251998479](https://github.com/mjw3177109/damoxingtest/actions/runs/40251998479)，`completed/success`，Job `121345741718`，**206/206 单元测试通过**；Ruff F821、response-only collator 和 `-100` 掩码检查通过。三个新增测试全部 PASS。
- 代码提交 SHA：`1515a1b271436690b8e0dc0cf93a7a96b36f8357`；回归测试 SHA：`3a2deece43630e265771670f71a1a9ec6201db0b`；夹具修复 SHA：`770cd059c145d7be66cdbb14990041e17fcf4155`。
- PR：[Draft #70](https://github.com/mjw3177109/damoxingtest/pull/70)，保持 Draft，不合并，不授权 GPU 训练。离线测试通过**不等于** Kaggle 端到端验收。

## 当前真实训练/报告/Artifact 证据
- 最近 Daily：[Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)，`completed/success` 但实际 `SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`，没有新的训练、评估或样例。
- `reports/2026-10-25/run-40165941479/` 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已直接读取；Daily Artifact `12588187512` 存在、未过期。
- 最近真实 GPU：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，`completed/success`，`reports/2026-10-23/run-39921870784/` 的来源日志、指标、元数据及质量门槛已读取；GPU Artifact `12487687305` 存在、未过期。训练代码来源 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`。
- 历史 GPU 为 NVIDIA Tesla T4 / 14.56 GiB，3 Epoch、33 步，Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`，同轮基线 Val Loss `3.389291`。**本轮新增 GPU 步数 0；没有新增 Train Loss、Val Loss、PPL 或模型生成**。
- 历史训练集 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证集 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 历史固定生成样例 10 条：9 条重复句点、1 条重复问号，0/10 通过初筛，人工审核 pending，`promotion_approved=false`。没有新模型回答。
- 当前 Kaggle Kernel 实时状态、Kernel Version、GPU 剩余额度**无法独立核实**；不把旧 COMPLETE 或 Actions success 当成当前训练成功。Run 8 和 Run 12 使用不同验证集，无法作同口径历史最佳比较；保留上一已批准版本。

## 本轮经验、限制和下一步
1. **产物存在 ≠ 当前运行成功。** 质量初筛必须同时验证本次 Run 的完成状态；现已增加最小保护并通过 3 项回归。
2. 本修复仍未建立 Kaggle 远端 Kernel Version 与 GitHub Run/数据/代码 SHA 的完整绑定，不能证明历史/未来下载文件一定来自本次 push；下一阶段优先验证端到端来源标识，禁止冒领旧产物。
3. 历史 `DataCollatorForLanguageModeling` NameError 在当前训练脚本不存在，`response_only_collator` 仍接入 Trainer，避免重复修复。
4. 下次只做一次受控、可测量的来源一致性实验（无 GPU）：模拟当前 Run 状态 `COMPLETE` 但输出 `run_metadata.json` 的代码/数据来源不一致，要求质量初筛明确拒绝；在确认预期契约和必要元数据字段后才实现，不作未经验证的架构改造。
5. PR 保持 Draft，不启动第 13 次 GPU 训练；待远端状态/配额、并发、独立评估与回滚能力核实后再决定。禁止泄露 Token、密钥或隐私；保护用户、维护人类。
