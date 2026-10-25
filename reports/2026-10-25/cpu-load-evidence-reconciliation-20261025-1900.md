# GPT-2 每小时证据纠偏｜历史 Adapter 已完成真实 CPU 加载（2026-10-25 19:00 Asia/Shanghai）

## 本轮发现、根因与最小纠偏
- 巡检基线 main SHA：`4f4c28086124c16f998c27ed0797c3b80e608e6b`。最新 GitHub Actions 总数 92；最新静态预检 Run `40182926751` completed/success，日志为 172/172 单测通过（属于合并前 PR #68 的 CI，不能称作本轮新测试）。
- 发现前几轮报告把“Run 12 历史 Adapter 尚未完成真实 CPU/PEFT 加载”当作待办。经读取现有 CPU 工作流源码、历史报告、Run Jobs/真实日志和 Artifact 元数据，**该表述不准确**：已有成功的 CPU PEFT 加载与实际推理。根因是巡检只检查近期审计工具的 ZIP/配置/结构结果，未回溯已存在的 CPU 真实生成证据。
- 本轮最小纠偏：归档本报告，明确区分“历史候选在隔离 CPU 环境成功加载并推理”与“正式已批准版本持久备份/生产回滚成功”。不重跑相同 CPU 实验，不重复耗费 GPU，不修改生产训练脚本/模型/安全门槛。
- 已核对 `scripts/train_gpt2_lora.py`：旧 `DataCollatorForLanguageModeling` 引用 0 处，`response_only_collator` 仍定义并用于 Trainer；无须重复提交 NameError 修复。

## 真实 CPU PEFT 加载与质量证据（历史，非本小时新实验）
- `.github/workflows/run12-readability-review.yml` 从真实训练 Run `39921870784` 下载名为 `gpt2-training-39921870784` 的 Artifact，校验 Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c` 和基础模型 `uer/gpt2-chinese-cluecorpussmall`；`tools/run12_readability_review.py` 通过 `PeftModel.from_pretrained(base, adapter, is_trainable=False)` 在 CPU 加载并执行 4 条基础模型 + 4 条候选模型生成。
- [CPU Run 40119328101](https://github.com/mjw3177109/damoxingtest/actions/runs/40119328101)：Job `120947220737` completed/success；真实日志显示运行 Python 推理脚本并上传 Artifact `12569273751`，仍未过期（到期 2026-11-23 UTC）。`reports/2026-10-25/readability-review-40119328101/summary.json` 记录 8/8 CPU 生成；候选 2/4 纯标点、1/4 全特殊 Token 空白、初步人工直接回答 0/4。模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- [CPU Run 40123632273](https://github.com/mjw3177109/damoxingtest/actions/runs/40123632273)：Job `120960305612` completed/success；再次实际加载并运行 8/8 CPU 生成，Artifact `12571643988` 未过期（到期 2026-11-23 UTC）。仅将 `no_repeat_ngram_size` 从 0 改为 2、固定 4 条和 64 Token，候选纯标点 2/4→1/4，直接回答 **0/4→0/4**，并出现不符合问题要求的输出。减少标点不是语义质量提升。
- 上述证据支持“**被拒绝的 Run 12 候选可在隔离 CPU 环境加载并生成**”，但不支持“已批准生产模型存在、正式回滚链路完成、模型通过质量或安全门槛”；历史 Run 8 的真实 PEFT 加载本轮未核实。

## 最新 Daily、Artifacts、指标及样例
- 最新 Daily [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) completed/success，但 `reports/2026-10-25/run-40165941479/training_status.json` 为 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；本小时 **0 新 GPU 步**、无新训练或评估。
- 已核对该日期目录下 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`quality_gate.json`、`training_status.json`。Daily Artifact `12588187512` 存在、未过期；真实训练 Run 12 Artifact `12487687305` 存在、未过期；最新 Static Preflight Run `40182926751` 无 Artifact。
- 历史真实 GPU [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4、14.56 GiB、3 epochs、33 steps、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`、同轮基线 Val Loss `3.389291`。训练 85 条（SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`），验证 24 条（SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`），学习率 0.0002、LoRA rank 8、seed 42、max_length 256。
- 最新 Daily `samples.json` 是历史复用的 10 条生成，主要是连续句点及问号；质量初筛 0/10，`promotion_approved=false`，人工审核 pending。没有本小时新样例、Train Loss、Val Loss 或 PPL。
- Kaggle 当前实时 Kernel 状态及 GPU 配额无法独立核实；历史 Version 8 COMPLETE 不是实时证明。Run 8/12 的验证集不同，不能跨数据版本宣称历史最佳。

## 下一步可测量实验与风险边界
1. **取消“重复验证 Run 12 能否 CPU 加载”这一冗余待办**。剩余真正阻塞：语义回答率 0/4、生产批准版本与回滚证据缺失、独立盲测集不足。
2. 下次只做一项有新信息量的离线实验：审计训练输入 `用户：...\n助手：...`、响应标签掩码与特殊 Token，记录 85 条的有效监督 Token 数、零监督样本数、UNK 占比和模板对齐情况；先定位确定性数据/代码缺陷，修复并通过静态/单测后再考虑受控训练。
3. PR #60 的 `token_type_ids` 对照和 PR #62 的 eval v2 均已存在未通过语义质量门槛的证据，保持 Draft，避免合并触发 Kaggle。若需要新的 CPU 质量对照，应使用新信息量的固定样本和独立语义审核。
4. 本轮只归档证据纠偏；不修改生产训练、候选权重、正式版本或安全保护，不使用/写入凭据与隐私。正式晋级仍**拒绝**；未经证实的改善不称为“进化”。

## 本轮与上轮
- 上轮：172 项测试通过、PR #68 已合并，报告称真实 CPU 加载仍待执行。
- 本轮：核对两次**已经完成**的 CPU PEFT 加载与生成证据，纠正该待办；无新增测试、训练或模型质量改善。
- 经验：每次提出耗时/耗算力的实验前先检索历史 Run、源码和 Artifact；“工程验证未完成”必须指明是哪一层，避免重复做已经完成但失败的实验。
