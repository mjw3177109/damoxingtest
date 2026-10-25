# GPT-2 Run 12 推理输入字段一致性：受控修复候选（2026-10-25 06 时档，CST）

## 本轮新增与结论
- 只在草稿 PR #60 分支 `fix/inference-token-type-parity-20261025-06` 修改 `scripts/train_gpt2_lora.py` 的生成输入构造，并新增 4 项离线回归测试；**没有合并主分支，没有启动 Kaggle GPU 训练，没有修改数据、权重、已批准 Adapter、质量门槛或凭据**。
- 已确认的输入协议差异：`response_only_collator` 向 Trainer 提供 `input_ids`、`attention_mask`、`labels`；原推理 `tokenizer(..., return_tensors="pt")` 会额外产生 `token_type_ids`，再传入 GPT-2 `generate`。历史固定实验 [Run 40043428043](https://github.com/mjw3177109/damoxingtest/actions/runs/40043428043) 已测得移除该字段会改变候选输出，但仍有 7/10 纯标点，因此**不是已经验证的语义质量修复**。
- 最小补丁新增 `prepare_generation_inputs`：仅移除 `token_type_ids`，其余字段及设备迁移保持不变，生产生成调用改用该函数；保留 `response_only_collator`。
- 当前 PR：[#60](https://github.com/mjw3177109/damoxingtest/pull/60)，草稿，**未合并**；基线 main SHA `4a080a6b39f1a820fa789ecc0a47cf0c977ca433`，测试通过的 PR SHA `a1a65497201c170da28ea04eeb5b706e1551eb53`。

## 真实验证
- [Static Preflight Run 40136877113](https://github.com/mjw3177109/damoxingtest/actions/runs/40136877113)：`completed/success`，`142/142` 单元测试通过（上一轮 138 项，本轮新增 4 项）。
- Python 编译、Ruff F821、response-only 掩码/Trainer wiring 检查全部成功；不需要 Kaggle Token、模型下载或 GPU。
- 新测试验证：有 `token_type_ids` 时仅删除该字段；缺失时安全兼容；其余输入字段保留；生产生成调用使用新函数。
- **尚未执行**真实模型权重下的端到端生成质量评估，因此不得将此 PR 标为“已修复模型重复问题”，也不得晋级模型。

## 训练与数据基线（全部历史值）
- 真实 GPU 训练：Actions Run `39921870784`，Tesla T4 / 14.56 GiB，3 Epoch / 33 有效步；Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`；质量门槛 0/10，`promotion_approved=false`。
- 训练数据 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；固定验证 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 最近 Daily Run `40065584092`：`SKIPPED_NO_CHANGES`，0 新 GPU 步；旧报告 Adapter 缺失误报已修复但未通过下一次 Daily 端到端验收。
- 真实 Tokenizer/EOS 审计 Run `40037146803`：109 条无截断、EOS 标签均保留，不重复排查该假设。
- 历史第 8 次与第 12 次的验证集不同，不能直接比较为历史最优。
- 历史训练 Artifact ID `12487687305`、Daily Artifact ID `12549545432` 均已核实存在、未过期。Kaggle 当前实时 Kernel 状态没有独立授权 API 证据。

## 风险与下一步
1. **先保持 PR 为草稿**：修改 `scripts/**` 一旦合并到 main，会改变训练 recipe hash 并触发 Daily 工作流；当前不能以静态 CI 成功为理由自动耗费 T4。
2. 下次使用固定模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`、原拒绝 Adapter、相同 10 条验证提示和 seed，隔离 CPU 对比改动前后：真实直接回答率、纯标点率、UNK、EOS、事实与安全性。若仍不合格，不晋级、不宣称进化。
3. 若计划合并，先核实 Kaggle Kernel 空闲、配额和已批准模型可回滚，再决定是否执行受控 GPU 实验；严禁并发、无限重试或绕过安全门槛。
4. 保持最小权限，不提交 Token、密钥、个人信息或未脱敏样例；记录失败经验，避免重复浪费 GPU。

**本轮判定：工程补丁已通过静态与离线单测；生产未合并，真实生成质量尚未验证；训练与模型晋级均无新增。**
