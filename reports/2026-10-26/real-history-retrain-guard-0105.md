# GPT-2 每小时审计：真实 Run 12 数据的同数据重训阻断回归（2026-10-26 01:05 Asia/Shanghai）

## 本轮真实状态与来源
- 仓库：`mjw3177109/damoxingtest`；主分支最新已核实 SHA `1237531d03cb3d43837e76da21d2a00b5d19cc24`。本轮仅修改 Draft [PR #70](https://github.com/mjw3177109/damoxingtest/pull/70) 分支，**没有合并 main**。
- 本轮新增真实历史数据离线回归：`tests/test_real_same_data_guard.py`，提交 `8574879fe98879d715dfa6f1050fedd4388d1fe4`。
- [Static Preflight Run 40214913778](https://github.com/mjw3177109/damoxingtest/actions/runs/40214913778)：**completed/success**，Job `121233844765`。实际 Job 日志记录新增测试 `test_run12_recipe_only_change_does_not_submit_gpu ... ok`，**191/191 单元测试通过**；Ruff F821 与 response-only/-100 掩码检查通过。该 CI 只运行 CPU/静态检查，不代表新训练。
- 最新 [Daily Training Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：completed/success，但 `SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`，未执行 Kaggle 提交。最近真实 GPU 训练 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束。
- Kaggle 当前 Kernel 实时状态、GPU 配额及是否存在仓库之外的手动提交，**无法通过当前可用的已授权工具独立核实**；本轮没有提交 Kernel，也未声称远端训练成功。
- 最新主分支报告日期目录为 `reports/2026-10-25`；本报告目前只存在于 PR #70 分支，待合并后才进入 main。

## 实际问题、假设、最小增量测试
- 已知根因：训练复用判断只比较旧版数据与整脚本 recipe hash；PR #70 的防护代码修改本身改变 recipe hash，可能使默认复用失效并误进入 Kaggle 提交路径。
- 本轮假设：在**真实 Run 12 数据未变化、历史已完成训练存在、仅训练守护逻辑变化**的情况下，即使精确配方复用失败，也必须在 Kaggle 提交前输出 `blocked=true`，不能重复消耗 GPU。
- 测试直接读取真实 `reports/2026-10-23/run-39921870784/run_metadata.json` 和 `training_status.json`，计算当前 `data/safety_humanity_train_v2.jsonl`、`data/safety_humanity_eval_v1.jsonl` 的 SHA-256，与历史记录比较；仅当两者匹配才执行同数据断言，数据正式更新时跳过不再适用的历史对照。
- 真实数据 SHA-256：train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`（85 条），eval `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`（24 条）。
- 模拟 recipe-only 不匹配时，真实历史证据检索为真，CLI guard 写出 `blocked=true`、`reuse=false`、`BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL` 和 `kaggle_kernel_submitted=false`，且未创建 Kaggle 输出目录。CI 日志确认测试通过。
- **边界**：本轮测试使用真实数据及历史元数据，但模拟了精确复用失败，未触发 Kaggle CLI、GPU、实际远端配额检查或端到端 Kernel；不能据此认定真实 Kaggle 端到端已验收。
- 训练脚本的历史 `DataCollatorForLanguageModeling` NameError 已不在最新代码中；`response_only_collator` 和 `-100` 掩码保持通过，不重复修复。

## 历史指标、样例、Artifact 与质量门槛
- Run 12 历史实测：Tesla T4、14.56 GiB，3 epoch、33 有效步，Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。本小时**新增 GPU 步数 0，Loss/PPL 无新测量**。
- 最新 Daily `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 在历史归档中存在；本轮再次核对了 `metrics.json`、`samples.json`、`run_metadata.json`、`training_status.json`、`quality_gate.json`、`report.md`，其中指标和样例均明确复用 Run 12，不能算本轮新产出。
- 历史固定生成样例包含 `................................................................`；有效生成 **0/10**，`human_review_status=pending`、`promotion_approved=false`，**模型晋级拒绝**。
- 最新 Daily Actions Artifact `12588187512` 存在且未过期（到期 2026-11-24）；本轮 Static Preflight 未产生新模型 Artifact。历史 Run 12 与 Run 8 验证集不同，不能直接比较跨轮历史最佳。

## 经验与下一步
1. 先用真实归档证明历史训练已完成，再在离线条件下验证守护代码变化不会触发重复 GPU；避免只用合成数据掩盖路径不一致。
2. PR #70 保持 Draft，不能因 191 项 CI 通过就宣称 Kaggle 端到端安全。下一步验证审批参数、失败路径、报告归档，以及 Kaggle 实时状态/配额，才决定是否合并。
3. 若未来训练得到独立批准，应记录数据 SHA、配置、代码 SHA、Kernel/Run ID、真实指标、生成样例、独立质量门槛、回滚证据。没有真实新结果不得宣称“进化”。
4. 不修改安全保护，不泄露凭据或个人信息，不覆盖上一个可回滚的候选模型；项目原则：保护用户、维护人类。
