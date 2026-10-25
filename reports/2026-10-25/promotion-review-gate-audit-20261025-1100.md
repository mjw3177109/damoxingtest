# GPT-2 自动晋级安全门槛审计与最小修复候选（2026-10-25 11 时档，Asia/Shanghai）

## 已确认的逻辑风险
- 仓库 `.github/workflows/daily-gpt2-training.yml` 原先把 `promotion_approved` 直接设为 `not reasons`，其中主要条件是验证 Loss 改善、10 条生成样例的字符级启发式检查和文件存在性；当这些初筛条件满足时，立即把 Adapter 复制到 `checkpoints/adapter_latest`，并写入 `approved: true`。
- `TRAINING_METHOD.md` 同时指出自动门槛不是安全证明，仍需人工审核与独立评测。原实现存在**“初筛通过就实际晋级”**的控制流缺口。此项是静态源码确认的风险，**未发现历史 Run 12 实际发生了错误晋级**（历史质量门槛明确为拒绝）。
- 该缺口与本项目的“只有经过可审计验证才晋级、保留上一批准版本、保护用户和人类”原则不一致。

## 本轮最小修复候选（Draft PR #63）
- 仅调整工作流的候选质量门槛，不改训练脚本、数据、模型、Kaggle 资源配置或历史报告。
- 将 `automated_precheck_passed` 与最终 `promotion_approved` 分离，记录 `human_review_status: pending`，未建立独立审批链之前强制 `promotion_approved: false`。
- 禁止工作流自动覆盖 `checkpoints/adapter_latest`；候选继续随 Actions Artifact 留存。将来如需晋级，必须另行设计明确授权、独立语义/安全评估、版本哈希及回滚验证的审批机制。
- 新增 `tests/test_promotion_review_gate.py`：使用合成的成功样例、无效样例及复用训练状态，执行工作流实际 Python 质量门槛脚本，检查未审批模型不会被复制为正式 Adapter。测试不下载模型、不使用 Kaggle Token/GPU。
- 草稿分支：`fix/promotion-review-gate-20261025-11`；PR：https://github.com/mjw3177109/damoxingtest/pull/63。**本文件记录修复候选，不代表 CI 已通过或已合并。**

## 本轮核实的历史事实
- 最近真实 GPU 训练：GitHub Actions Run `39921870784`，`completed/success`；`training_status.json` 明确 `completed`，日志有实际参数更新。Tesla T4，14.56 GiB，3 Epoch / 33 Step，Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`，同轮基线 Val Loss `3.389291`。生成质量门槛 **0/10**，`promotion_approved=false`，没有晋级。
- 最近 Daily Run `40065584092`：`completed/success` 但实际 `SKIPPED_NO_CHANGES`，复用历史结果，**没有新训练**。其旧 `quality_gate.json` 仍有已识别的“LoRA adapter files missing”误报；修复是否通过下一次 Daily 尚待验证。
- 训练数据 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；旧固定验证集 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 最近训练 Artifact ID `12487687305` 与 Daily Artifact ID `12549545432` 均存在且未过期。仓库报告 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均可读取。
- 最新生成样例仍为句点/问号重复；本轮没有新增模型生成、Loss、PPL 或 GPU 训练。历史 Run 8 与 Run 12 使用不同验证集，不能直接声称历史最优。
- 当前 Kaggle Kernel 实时状态与剩余 GPU 配额尚无独立可用的授权 API 证据；历史 COMPLETE 不能视为实时证明。

## 验证边界与下一步
1. 等待 Draft PR #63 的静态 CI 与新增合成回归测试结果，若失败先定位日志并最小修复；CI 通过也仅证明门槛控制流，不代表模型质量合格。
2. 先保留 Draft，不自动合并，避免未经评审改变生产晋级策略。需要另建独立人工审批机制，不能通过“增加一个可伪造标志”绕过门槛。
3. PR #60（推理字段一致性）与 PR #62（eval v2 候选）仍是 Draft。eval v2 候选存在 16/24 高语义重叠风险，不能当作独立盲测集。
4. 在数据独立性、语义正确率、安全性、真实回滚能力、Kaggle 空闲和配额得到验证之前，不启动第 13 次 GPU 训练；不得重复已失败实验。
5. 经验：**初筛指标和人工审批必须在数据结构与执行路径中明确分离**。记录“待审核”不等于“已批准”，CI success、Kaggle COMPLETE 也不等于模型成功。

本报告只包含公开仓库代码、运行 ID、SHA、合成测试说明及非敏感指标；未写入凭据、Token 或私人信息。
