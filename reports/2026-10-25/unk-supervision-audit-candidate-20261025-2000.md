# Run 12 监督标签 UNK 覆盖率：增量审计候选（2026-10-25 20:00 Asia/Shanghai）

## 本轮事实与证据
- 巡检主分支 SHA：`3bb66630d8900b7934adf2ada32b1ac9192e5f9a`；截至巡检时 GitHub Actions 共 92 次，最新 Static Preflight [40182926751](https://github.com/mjw3177109/damoxingtest/actions/runs/40182926751) 为 completed/success（**历史 PR #68 的 172 项测试，不是本候选代码的测试**）。
- 最近 Daily [40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) completed/success，但 `training_status.json` 明确 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`。本轮无 GPU 训练或新评估。该 Daily Artifact ID `12588187512`，已核实未过期。
- 最近真实训练 [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4 14.56 GiB，3 epochs、33 steps、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；85/24 条，训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`、验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。本轮无新增 Loss、PPL、生成样例。
- 最近 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`quality_gate.json` 已读取；10 条历史样例仅重复标点，质量门槛 0/10，`promotion_approved=false`。历史训练 Artifact `12487687305`、CPU 对照 Artifact `12569273751` / `12571643988` 均有此前核实证据。本轮不把历史数据误记为新增。
- Kaggle Kernel 的实时状态和 GPU 配额未独立核实，不能用历史 COMPLETE 推断当前可用；第 8 次和第 12 次验证集不同，无法进行同口径历史最优排名。

## 为什么需要本增量
- [真实 Tokenizer 审计 40037146803](https://github.com/mjw3177109/damoxingtest/actions/runs/40037146803) 已证明 Run 12 训练 85 条、验证 24 条：EOS 缺失 0、截断 0、零监督 0；因此**不再重复排查 EOS 丢失**。
- 该真实审计尚未提供训练提示前缀与回答监督区的 `[UNK]` 占比。Run 12 CPU 生成曾出现纯特殊 Token/UNK 空白输出，但生成端 UNK 不等于训练监督中含 UNK。两者因果关系尚无证据。
- 本候选只为 `tools/audit_tokenizer_contract.py` 增加只读、聚合的前缀、完整回答、截断后监督标签三组 UNK 数量/分母/百分比；未知 UNK ID 时返回 null 而非错误地报 0。增加 4 项无模型、无网络、无 GPU 的合成测试，覆盖前缀/回答分离、聚合分母、截断和缺失 UNK ID。
- 本候选**没有重新执行真实 Tokenizer**，因此尚无 Run 12 真实 UNK 比例，不能推断根因，也不能称作模型能力改善。待 PR CI 后在固定真实 tokenizer/revision 上只读运行审计；若 UNK 很低，应转向 logits/数值诊断而非修改训练配方。

## 变更、验证、晋级
- 仅新增/修改 `tools/audit_tokenizer_contract.py`、`tests/test_tokenizer_unk_supervision.py`、本报告；未修改训练脚本、Kaggle 工作流、数据、模型、质量门槛、安全保护。
- 历史 `DataCollatorForLanguageModeling` NameError 已确认当前主分支无旧引用；`response_only_collator` 仍在 Trainer 中使用。
- 本报告提交时 PR CI 尚未完成；**不能声称本候选已通过 CI**。本轮未启动 Kaggle、未写入凭据或私人数据、未创建/覆盖已批准权重。
- 当前候选模型仍拒绝晋级；后续先核实静态检查和 4 项合成测试，再在 CPU 固定真实 Tokenizer 上测 UNK 聚合，记录差异和下一次单变量实验；只有真实可复现缺陷、最小修复及回归证据成立才考虑 GPU。
- 经验：在新建诊断前先核查已完成的真实 Tokenizer/EOS 实验；必须区分**训练监督的 UNK**与**生成阶段的 UNK**，不得把生成异常直接当作训练标签缺陷。
