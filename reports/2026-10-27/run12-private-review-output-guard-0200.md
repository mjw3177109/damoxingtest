# GPT-2 Run 12｜02 时档公开生成文本保护审计（2026-10-27 CST）

## 问题、假设和根因
- 目标：为下一步**私有语义审核**建立安全边界；防止公开 GitHub Actions 日志或 Artifact 泄露生成内容。
- 发现：`tools/run12_readability_review.py` 原先使用正则识别邮箱、URL、电话及部分密钥后，仍允许其他生成文本以 `safe_output_excerpt` 写入公开 Artifact。该策略不能可靠识别姓名、住址或其他上下文相关的隐私信息；不应把“通过正则”解释为可公开。
- 根因：采用了**黑名单脱敏**而不是“默认不导出生成文本”的白名单策略。这是已确认的隐私边界风险，不是已确认发生了真实个人信息泄露。

## 最小修复与测试
- 代码 SHA：`e81444b18ef9120f815cb3087a5b643f19d7988b`，基于上一轮 `6eb55d8e093334cd6302e9e1d822e300b074a02a`。
- 修改：`tools/run12_readability_review.py`、`tests/test_run12_readability_review.py`、`tests/test_run12_direct_answer_generation.py`。不改变模型、数据、训练参数、推理参数或质量门槛。
- 新策略：所有公开诊断的 `safe_output_excerpt` 均为固定 `[REDACTED: raw output withheld]`；是否包含中文仅在进程内计算并输出布尔值，仍可保留数值诊断，不输出原文。
- 验证：GitHub Static Preflight Run `40375175359`，Job `121756157282`，completed/success，日志确认 **266 tests / OK**、**All checks passed!**，并确认 response-only collator 静态契约通过。相较上一轮 265 项，新增 1 项测试且调整原有回归预期。
- 限制：该修复保护**未来使用此函数生成的报告**；既有公开历史 Artifact 可能仍包含过去的截断文本，**不会被此提交追溯清除**。后续应审查并按保留策略处理历史 Artifact，不将未验证的历史内容称为安全。
- 此次未运行模型推理、未运行 Kaggle GPU、未产生新的模型权重或语义评分。

## 本小时运行、文件与产物
- 最近 Daily Training：Actions Run `40275426137`，completed/success 但 `SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`。最新 main 报告目录：`reports/2026-10-26/run-40275426137`。
- main 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均已重新读取。最新 `metrics.json` 中 `train_steps=0`、`train_loss=null`、`gpu_name=null`，均不是新训练指标。
- 最新 Daily Artifact `12629319793` 存在、未过期；历史 GPU Artifact `12487687305` 存在、未过期；最近 CPU 参考答案实验 Artifact `12665288586` 存在、未过期。最新静态 CI 无模型 Artifact。
- 历史 GPU 来源：Actions Run `39921870784`，已完成；Tesla T4 / 14.56 GiB；3 epochs、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 历史正式样例 0/10 有效；本小时没有新生成样例。前轮 CPU 参考答案对照中，base 与 Run 12 候选平均 character-bigram F1 均为 0.004494；与上一轮、历史最佳的**新模型质量变化无可测量证据**。不同验证集的历史 Run 8 不可直接横比。
- Kaggle 目标 Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 公开页面不可访问；实时 Kernel 状态、版本、剩余配额与外部并发均未能独立核实。
- `scripts/train_gpt2_lora.py` 最新 PR 代码不存在 `DataCollatorForLanguageModeling` 名称，Trainer 保留 `data_collator=response_only_collator`，未重复修复。

## 经验、晋级判定与下一步
- **经验：** 正则黑名单不能证明生成文本不含隐私；公开自动化产物应默认只包含预先定义的数值字段和固定占位符。
- **质量门槛：** `promotion_approved=false`；人工语义与安全审核未完成；不晋级、不替换上一已批准版本。
- **下一步可执行措施：** 在授权的私有 CPU 环境运行固定提示词的原文生成与本地审阅，原文只保留在受控本地内存/临时文件；导出仅含逐题数值评分与聚合指标的报告，人工核对相关性、事实性、完整性、拒绝行为、EOS 及安全性。禁止上传原文到公开 CI、Artifact、提交或日志。
- **训练策略：** 先验证语义与安全，确认 Kaggle 运行状态、配额、并发和可回滚检查点后才考虑新的受控 GPU 实验。避免无效重复训练和未经证据支持的“自我进化”宣称。
