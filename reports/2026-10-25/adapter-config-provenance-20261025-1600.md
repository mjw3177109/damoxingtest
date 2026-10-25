# GPT-2 小时巡检：Adapter 配置元数据一致性受控实验（2026-10-25 16:00 Asia/Shanghai）

## 本轮范围与结论
- 仓库：mjw3177109/damoxingtest。基线 main SHA `304d4e2e114cae5fb517fb12fcbd70e1ac922aab`。
- 本轮仅在独立分支 `audit/adapter-config-provenance-20261025-16` 增量修改 `tools/audit_adapter_artifact.py`、新增 `tests/test_adapter_config_provenance.py`；Draft [PR #66](https://github.com/mjw3177109/damoxingtest/pull/66)。当前代码 SHA `9bb9da05a3552d0e7a7b1ee29e715568cfb1cb92`（本报告提交前）。
- 假设：原只读 ZIP 审计器虽校验权重哈希，但未解析 `adapter_config.json`；损坏、非 JSON、过大配置或基础模型不匹配仍可能被标为结构性候选。新增有界 JSON 验证与可选基座模型 ID 比对，可减少元数据误判，不能证明模型可运行、已批准或已备份。
- 修复：限制配置文件最大 256 KiB，必须是 JSON 对象；校验 `base_model_name_or_path` 字段类型；新增可选 `--expected-base-model` 严格匹配，缺失或不匹配时 `candidate_recoverable=false`；不回显配置中的基座 ID，`approval_verified` 永远为 false。未提供预期 ID 时输出 `base_model_check=not_checked`，不得解释为已验证兼容。
- 验证：本地隔离合成 ZIP 上，原 5 项 + 新 7 项测试共 **12/12 通过**，Python 编译通过；不调用 GPU、不加载模型、不解压归档。完整 GitHub CI [Run 40174843378](https://github.com/mjw3177109/damoxingtest/actions/runs/40174843378) 已于 2026-10-25T07:59:24Z 完成，**completed/success**；真实 Job 121113197428 日志确认 **160/160 项单元测试通过**、Ruff F821 通过、response-only collator 与 -100 masking 检查通过。该 CI 对应代码 SHA `9bb9da05a3552d0e7a7b1ee29e715568cfb1cb92`，本报告后续仅文档更新，不是合并后 CI。
- 实验对照：旧工具覆盖 ZIP 完整性、权重存在/哈希、路径安全等 5 个回归场景；本轮额外覆盖匹配、错配、缺失、畸形 JSON、非对象、超大配置、非法元数据 7 个合成场景。该计数是**测试覆盖扩展**，不是模型质量改善。真实历史 ZIP 的配置一致性尚未由本轮新工具执行验证。
- 不修改训练脚本、训练/验证数据、质量门槛、生产模型权重或安全保护；PR 保持 Draft，未合并。

## Actions / Kaggle / 实际训练
- 查询时 Actions 总数 85；本轮最新完成 [Static Preflight 40168017207](https://github.com/mjw3177109/damoxingtest/actions/runs/40168017207) 为 completed/success，历史 153/153 测试通过；本轮 PR #66 的新 CI 为 Run 40174843378，160 项测试通过。
- 最新 [Daily Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) completed/success，但 `training_status.json` 明确 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；`training.log` 明确 `PRE_SUBMIT_SKIPPED_NO_CHANGES`。本小时没有 Kaggle 提交、训练、评估或新生成。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 的实时状态、版本与剩余配额本轮无法独立核实；历史 Version 8 COMPLETE 不代表当前训练成功。
- 最近真实 GPU 训练为 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，历史 Tesla T4 / 14.56 GiB，3 epochs、33 步，Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，下降 7.141%。这些是历史值，本轮 GPU 步数 0，Loss/PPL 未新增。
- 历史配置：学习率 0.0002、LoRA rank 8、seed 42、max_length 256；训练 85 条、验证 24 条。训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`，配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 历史 `DataCollatorForLanguageModeling` NameError 在当前 main 脚本中无引用，`response_only_collator` 仍存在；不重复修复或训练。

## 文件、Artifact 与模型质量
- 最新报告目录 `reports/2026-10-25/run-40165941479` 已确认 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均存在，且历史指标/样例被明确标为复用。
- 最新 Daily Artifact `12588187512` 存在、未过期，过期时间 2026-11-24；历史 GPU Run 12 Artifact `12487687305`、Run 8 Artifact `12415142300` 此前已核实可读，但不是正式批准或长期回滚证明。
- 真实最近保存的 10 条样例为历史复用，代表性输出为连续 64 个句点；有效 0/10，`promotion_approved=false`，`human_review_status=pending`。本轮未生成新样例。
- 与上一轮：新增加配置元数据验证工具候选及 7 项离线测试、Draft PR #66；模型权重、训练、指标和晋级状态均未改变。Run 8 与 Run 12 验证集不同，不得直接认定历史最优；未获得超过历史最优的新证据。

## 风险、经验与下一步
- 工程经验：结构完整的 ZIP 与正确的 Adapter 基座元数据是两个独立门槛；即使两者通过，也不代表模型可加载、可恢复、通过语义质量审核或获得正式批准。
- 阻塞：PR #60 推理输入一致性和 PR #62 eval v2 语义重叠问题仍为 Draft；尚无独立盲测、正式批准清单与长期备份的完整证据。Kaggle 实时配额未核实。
- 下一步：等待 PR #66 GitHub CI 完成，核实真实历史 ZIP 的 Adapter 配置并与固定基础模型 ID 比较；若失败先定位真实日志并最小修复。之后完善只读来源记录与隔离恢复测试，保留主分支上一版本；无质量证据不启动第 13 次 GPU 训练。
- 安全原则：保护用户、维护人类；最小权限；不记录凭据、Token、个人隐私；不绕过安全审批、不并发或无界重试、不覆盖批准模型。
