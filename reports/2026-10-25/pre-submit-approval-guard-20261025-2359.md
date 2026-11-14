# GPT-2 每小时审计：同数据重训审批门槛（2026-10-25 23:59 Asia/Shanghai）

## 真实状态（禁止把 CI 成功当作 GPU 训练）
- 本轮核查主分支 SHA：`1237531d03cb3d43837e76da21d2a00b5d19cc24`；修复仍在 [Draft PR #70](https://github.com/mjw3177109/damoxingtest/pull/70)，**未合并**，最新通过测试的候选 SHA `b74cf5dd02b077046e607dc2d00fd97b7a81cbfe`。
- 最新 CI [Run 40209515487](https://github.com/mjw3177109/damoxingtest/actions/runs/40209515487)：completed/success，Job `121217561065`；**190/190 单元测试通过**，Python/Ruff F821/response-only collator/-100 掩码检查通过。CI 不产生模型 Artifact。
- 最近 Daily [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：completed/success，但 `PRE_SUBMIT_SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`；最近真实 GPU 训练 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束。**本小时新增 GPU 训练步数 0，无新 Loss/PPL/样例**。
- Kaggle 当前 Kernel 状态、版本及剩余 GPU 配额无法通过已授权接口独立核实；不推断可提交、也未启动新 Kernel。

## 本小时修复与最小范围验证
- 已知缺陷：PR #70 修改 `scripts/train_gpt2_lora.py` 的复用判断会改变整个脚本参与的 `training_recipe_hash()`；原 `pre_submit_reuse_guard.py` 因哈希不匹配可能允许同数据无意义重训。
- 修复提交：`e8380d4a02ef677c927c402fc5e3337cc4c328fc` 在 `tools/pre_submit_reuse_guard.py` 增加**只读**同数据已完成历史训练检查。精确复用失败且训练/验证数据 SHA 均与已完成、非跳过的历史训练一致时，默认输出 `blocked=true` 和 `BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL`，**不提交 Kaggle**。
- 工作流提交：`fcc77b29793938fd6a5c8d5a37e4fdc07457637f`。四个 Kaggle 安装/准备/校验/启动步骤均要求 `blocked != true`。仅 `workflow_dispatch` 明确选择 `approve_same_data_retrain` 时允许进入既有远端状态检查及配额保护流程；未放宽模型晋级、安全门槛、并发限制或失败重试策略。
- 测试提交：`6ede9dea08ca15ce2b234231588a7f242bee24c0`、`b74cf5dd02b077046e607dc2d00fd97b7a81cbfe`。新增 7 项离线回归测试，覆盖同数据已完成训练、数据变化、历史跳过/失败、四处工作流条件、CLI 无审批阻断、CLI 显式审批路径。最新 190 项测试全部通过，**没有真实 Kaggle 端到端验证**。
- 经验：配置复用检查与脚本整体哈希必须同时审查；同数据重训需要显式审批，不能因为守护代码修改而自动消耗 GPU。该工程修复并非模型质量改善，也不代表代码已经获准合并。

## 历史训练证据及质量
- 数据版本：训练 85 条 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证 24 条 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；基础模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- Run 12 历史实测：NVIDIA Tesla T4、14.56 GiB、3 epoch、33 有效步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，下降 7.141%。本小时均无新测量。
- 最近 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已逐一读取；其中 Loss/PPL/样例均明确复用历史 Run 12。代表样例 `................................................................`，有效样例 **0/10**；`promotion_approved=false`，人工审核 pending。
- 已核实 GitHub Artifact：Daily `12588187512`（未过期）、Run 12 `12487687305`（未过期）、Tokenizer 审计 `12599861115`（未过期）；本小时 CI 无模型 Artifact。Run 8 与 Run 12 的验证集不同，不能宣称跨轮历史最优已改善。

## 阻塞与下一步
1. PR #70 仍保持 Draft，待进一步检查真实数据下的预提交模拟、workflow_dispatch 审批行为及 GitHub Actions 合并后触发；**不在本轮合并或提交 GPU**。
2. Kaggle 实时状态、GPU 额度及远端并发无法独立核实，真实训练继续暂停；如将来审批训练，必须先核查远端状态、配额和可回滚版本。
3. 历史 `DataCollatorForLanguageModeling` NameError 在最新 main 中已不存在；`response_only_collator` 仍被 Trainer 使用，无须重复修复。
4. 下一次可测量实验：在无 GPU 条件下验证同数据、仅守护代码变化时 `blocked=true`，真实数据变化时不触发同数据阻断，显式审批时才可进入现有 Kaggle 安全检查。PR #60/#62 的语义生成与独立验证集问题仍待解决。
5. **模型晋级：拒绝。** 不覆盖已批准版本，不泄露凭据或个人信息，保护用户、维护人类。
