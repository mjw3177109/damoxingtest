# GPT-2 T4 每小时证据巡检与采样实验基线纠偏（2026-10-26 15:00 Asia/Shanghai）

## 事实与来源
- 本轮只读核实 GitHub Actions API、Daily Job 日志、main 最新报告与质量门槛，以及 Draft PR #70 的训练代码；**未执行 Kaggle 提交、GPU 训练或新模型推理**。
- 最新 Daily [Run 40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137)：completed/success，但日志明确为 `SKIPPED_NO_CHANGES`；`training_status.json` 为 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；main 最新目录 `reports/2026-10-26/run-40275426137`。
- 最新静态 CI [Run 40277277060](https://github.com/mjw3177109/damoxingtest/actions/runs/40277277060)：completed/success；真实 Job 日志 `Ran 224 tests`、`OK`、Ruff F821 通过、response-only collator / -100 masking 通过。该 CI **不包含新的模型推理**。
- 最新 Daily Artifact `12629319793`（5186 bytes，未过期，状态/报告证据，不是新权重）；历史 GPU Artifact `12487687305`（未过期，来源 Run `39921870784`）。本轮仅通过 Actions 元数据核实 Artifact 存在，未重新下载 ZIP。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 的实时状态、版本、GPU 配额无法经当前授权通道独立读取；不能从历史 COMPLETE 推断当前运行状态。PR #70 head `63eed9d70541fe9b696ef631ee59944a342f4845`，open/draft，未合并。

## 历史 GPU 数据（非本轮新增）
- Run `39921870784`：Tesla T4 14.56 GiB；3 epochs、33 步；Train Loss 3.246455；Val Loss 3.147277；PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。85 条训练、24 条验证。
- 最新 Daily `metrics.json` 的 `train_steps=0`、`train_loss=null`、`gpu_name=null`；上述数值来自历史复用，不是本小时实测。
- 固定生成 10 条，9 条连续句点、1 条连续问号；0/10 有效回答；`automated_precheck_passed=false`、`human_review_status=pending`、`promotion_approved=false`。Run 8 和 Run 12 验证集不同，不能跨轮声称历史最优改善。
- 已核实 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均存在。PR 脚本无 `DataCollatorForLanguageModeling` 未定义引用，`response_only_collator` 仍传入 Trainer。

## 本小时发现并纠正的实验设计问题
- 上一轮报告 `hourly-evidence-reconciliation-1356.md` 拟将采样温度 `1.0 → 0.7` 与“历史 CPU 采样结果”比较，却没有核实历史温度。直接核查 `tools/generation_decode_probe.py` 发现历史实际配置为 `temperature=0.8`、`top_p=0.9`、`no_repeat_ngram_size=3`、`repetition_penalty=1.12`、`max_new_tokens=64`、每条提示固定种子 `42 + index`。因此不能把 `1.0` 当作历史对照温度。
- 已执行 **6/6 项源码静态断言通过**，验证上述历史采样配置、对应 CPU 工作流及旧报告中的错误比较方案；这只是配置审计，**不是模型质量实验或代码缺陷修复**。
- 修正的下一项单变量 CPU 试验：固定 Run 12 拒绝晋级的 Adapter（SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`）、基础模型 `uer/gpt2-chinese-cluecorpussmall` revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`、验证集 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`、前 10 条提示、每条种子 42+index、max_new_tokens=64、do_sample=True、top_p=0.9、no_repeat_ngram_size=3、repetition_penalty=1.12；**仅比较 temperature=0.8（历史对照）与 0.7（新候选）**。
- 主要评价：人工审核后的直接回答数/10，次要评价：纯标点率、EOS 率、重复长度；不以标点率单项改善作为晋级证据。输出仅聚合指标或经脱敏的人工复核摘录，禁止凭据/个人隐私。
- **未执行该温度实验**：当前容器无 Transformers/PEFT 与基础模型缓存；GitHub 现有 CPU workflow 只在 main 指定路径推送或手动 dispatch 触发，当前授权工具无 workflow_dispatch 写操作。不能将此设计审计冒充新推理。下一步在受控、只读 CPU Actions 环境执行，先核验精确权重和版本，禁止 GPU/训练/自动晋级。

## 经验、阻塞与安全
- 本小时暂无新训练或模型质量结果。实验必须核对历史真实超参数，避免因温度基线错误而进行不可比的重复计算。
- 训练已结束；Kaggle 远端实时状态、配额和端到端来源仍未独立核实；PR #70 保持 Draft。当前无经证据确认、需要再次修改训练代码的 NameError 阻塞；不为凑修复提交未经验证的架构变更。
- 保护用户、维护人类；最小权限；不泄露凭据或个人隐私，不绕过安全保护，不覆盖上一个可回滚版本，不将未核实的改善称为进化。
