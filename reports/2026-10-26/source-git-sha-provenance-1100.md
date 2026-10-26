# GPT-2 Kaggle 训练源代码精确 SHA 归属审计（2026-10-26 11:00 CST）

## 假设与已确认根因
Kaggle notebook 通过 `git clone --depth 1` 独立克隆 `main`，并不自动锁定触发 GitHub Actions 的 `GITHUB_SHA`。已有训练/验证数据 SHA-256 和 recipe SHA-256 校验只能确认部分文件相同，无法证明完整源代码 commit 一致；历史 `run_metadata.json` 和 `metrics.json` 均未记录训练端实际 checkout commit。此处为静态代码审计确认的潜在来源误认领风险，不代表历史已经发生误晋级。

## 最小修复（仅 PR #70 Draft）
- `scripts/train_gpt2_lora.py`：通过 `git -C <repo> rev-parse --verify HEAD` 读取 Kaggle 实际 checkout commit，严格验证 40 位十六进制 SHA；不可获取时返回 null，写入 `run_metadata.json` 与 `metrics.json` 的 `source_git_commit_sha`。
- `.github/workflows/daily-gpt2-training.yml`：自动质量初筛比较两份产物中的 `source_git_commit_sha` 与当前 Actions `GITHUB_SHA`；缺失、无效或不一致则阻断；在 `quality_gate.json` 中留存期望值与实际值供审计。
- `tests/test_quality_gate_provenance.py`：增加来源 SHA 不一致、缺失、当前 SHA 缺失的三项负向回归。
- `tests/test_source_git_sha.py`：增加合法 SHA、Git 不可用、无效输出三项单测。
- `tests/test_promotion_review_gate.py`：仅同步测试夹具中的来源 SHA 与 GitHub 事件 SHA，不放宽任何生产质量门槛。

## 代码与测试证据
- 修复代码提交：`389f03d6acaa42cab175b6829cde8e60c7e0405e`
- 测试夹具修正提交：`741db40554781b2dae79d6d5677e3af797f693e7`
- 首次 CI：`40261919764`（failure，216 项中 2 项失败，原因是旧的 promotion 测试夹具没有新增来源 SHA；没有 GPU 执行）。
- 修正后 CI：`40261970922`（completed / success，216/216 单测通过，Ruff F821、response-only label masking 检查通过）。
- 本次只运行 GitHub Static Preflight；**没有执行真实 Kaggle 提交、训练、推理或模型晋级**。
- PR：https://github.com/mjw3177109/damoxingtest/pull/70 （保持 Draft，未合并）。

## 历史真实训练对照（非本小时新结果）
- 最近 Daily：Actions `40165941479`，`SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`；主分支最新报告目录 `reports/2026-10-25`。
- 最近实际 GPU：Actions `39921870784`（2026-10-23），Tesla T4，14.56 GiB；85 条训练、24 条验证、3 epochs、33 steps；Train Loss 3.246455，Val Loss 3.147277，PPL 23.272599；基线 Val Loss 3.389291，同轮下降 7.141%。
- 固定生成 10 条样例中 0 条有效；`promotion_approved=false`，不晋级。
- 本小时没有新 GPU 训练指标或新生成样例；与上一轮模型指标不变。Run 8 和 Run 12 验证集不同，不能直接宣称跨轮历史最佳。
- 训练数据 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`。
- 验证数据 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 历史 recipe SHA-256：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`（本次代码变更后 recipe SHA 将变化，不将历史值冒充当前值）。
- 当前真实 Kaggle Kernel 版本、实时状态、剩余 GPU 配额仍未独立核实；不做远端训练成功声明。

## 产物存在性（GitHub 仓库）
- `reports/2026-10-25/run-40165941479/` 中已核实：`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`。
- 最新 Daily Artifact `12588187512`，未过期，2026-11-24 UTC 到期。
- 历史 GPU Artifact `12487687305`，未过期，2026-11-22 UTC 到期。
- 本轮 Static Preflight 未生成新模型 Artifact。

## 经验与下一步
1. 数据/recipe 哈希相同 ≠ 训练端与当前 Actions 处于同一 Git commit；精确来源应由实际克隆的 Git 仓库记录，并在质量初筛中失败关闭。
2. 代码审计、模拟测试与真实 Kaggle 端到端验证必须分开标注；当前验证只支持“离线质量门槛能阻断错误 SHA”。
3. 保持 PR #70 Draft，不合并、不重复提交同数据 GPU 训练、不覆盖上一已批准版本；待具备安全的远端只读状态/配额/Kernel 版本核实手段后再做端到端验证。
4. 下一可测量实验：对历史 Run 12 固定提示词的首 Token 候选分布和重复标点进行 CPU/离线复核，固定 Adapter、数据和解码设置，仅改变一项可解释因素，记录样例可读性变化。若缺少真实 Adapter 或模型环境，标记阻塞，不虚构结果。
5. 遵循保护用户、维护人类原则；只使用最小权限，绝不写入 Token、密钥或个人隐私。
