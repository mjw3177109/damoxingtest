# GPT-2 T4 每小时证据复核与诊断去重（2026-10-26 13:56 Asia/Shanghai）

## 本轮核实的真实运行
- main 当前 SHA：`c56f9e0e1d353210460da44499de2338c70334da`；PR #70 检查前 head SHA：`598f44b22fb54b860b108542fb1d02d7745444e2`，open/draft，未合并。
- 最新 Daily [Actions Run 40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137) 于 2026-10-26 05:39 UTC 完成，Actions conclusion=success，**实际结果为 `SKIPPED_NO_CHANGES`**。Job `121417054103` 日志证明预提交复用历史 `reports/2026-10-23/run-39921870784`，Kaggle CLI 安装、推送与输出下载步骤全部 skipped。不是新 GPU 训练或新评估。
- main 最新报告目录已从上一时档的 `reports/2026-10-25` 更新为 **`reports/2026-10-26/run-40275426137`**。该目录 `status.txt=PRE_SUBMIT_SKIPPED_NO_CHANGES`、`final_status.txt=SKIPPED_NO_CHANGES`、`training_status.json` 中 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`。
- 已逐项读取当前 Daily 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`；`metrics.json` 中 `train_steps=0`、`train_loss=null`、`gpu_name=null`，历史 Loss/PPL 明确标为复用。10 条 `samples.json` 输出均为 64 字符重复标点（9 句点、1 问号），**本小时没有新生成**。
- 本轮最新 Daily Artifact：`12629319793`，名称 `gpt2-training-40275426137`，5186 字节，未过期；该 Artifact 仅是本轮状态/质量证据，**不是新模型权重**。历史 GPU Artifact：`12487687305`，Run `39921870784`，未过期。最近静态 CI [Run 40272136530](https://github.com/mjw3177109/damoxingtest/actions/runs/40272136530) completed/success、224/224 测试通过，**没有 CI Artifact**。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 实时状态、Kernel 版本及 GPU 剩余配额仍**未能独立核实**；公开页面访问失败。不能用历史 COMPLETE 推断当前可提交。没有使用密钥或启动 GPU。

## 历史 GPU 事实（非本轮新增）
- 来源 Run `39921870784`：Tesla T4，14.56 GiB；3 epochs、33 步、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`；同轮基线 Val Loss `3.389291`，相对改善 `7.141%`。
- 数据：85 train / 24 eval，训练 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`；基础模型 `uer/gpt2-chinese-cluecorpussmall` revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 最新质量门槛：`automated_precheck_passed=false`、`meaningful_generation_samples=0/10`、`human_review_status=pending`、`promotion_approved=false`。Run 8 与 Run 12 验证集不同，不作跨轮最佳排序。

## 本轮新发现：下一步不能重复“首次首 Token 诊断”
- 复核现有 `tools/first_token_probability_probe.py`、`tools/run12_first_step_category_cpu.py` 和历史 [Run 40092707377](https://github.com/mjw3177109/damoxingtest/actions/runs/40092707377) 真实 CPU 结果：**首 Token 类别概率对照已经执行过**，不能再把“首次运行首 Token”作为新进展。
- 历史 [Run 39950178751](https://github.com/mjw3177109/damoxingtest/actions/runs/39950178751) 在相同 10 条提示下的只读 CPU 对照：base/greedy 纯标点 7/10，candidate/greedy 10/10；base/sample 0/10，candidate/sample 1/10。解码改变了输出表面分布，**未证明语义回答改善**。
- 历史 [Run 40119328101](https://github.com/mjw3177109/damoxingtest/actions/runs/40119328101) 的 4 条 CPU 可读性对照中 candidate 直接回答 0/4；[Run 40123632273](https://github.com/mjw3177109/damoxingtest/actions/runs/40123632273) 只改变 no_repeat_ngram_size=2，candidate 直接回答仍 0/4。**不重复该失败实验**。
- 旧 `DataCollatorForLanguageModeling` NameError 在 PR #70 当前脚本中不存在，`response_only_collator` 仍连接 Trainer；没有需要重复提交的已确定 NameError 修复。
- 本轮没有找到可以安全声称已确定根因的新训练缺陷，因此不修改训练代码、数据、模型或工作流；这是证据去重与可审计阻塞确认，**不是模型修复或能力升级**。

## 下一项单变量可测量实验（尚未执行）
- 前提：先核验 Kaggle 无并发、配额与可回滚历史权重；若仅 CPU 推理则不需 Kaggle GPU，但仍需相同 pinned 基础模型、真实 Adapter、Tokenizer 与依赖。
- 对照：在已使用的同一 10 条固定 holdout 提示、同一 Run 12 Adapter、max_new_tokens=64、repetition_penalty=1.12、do_sample=True、固定种子下，仅将 `temperature` 从 `1.0` 改为 `0.7`；保持其余采样参数不变。输出仅保存聚合：有效直接回答率、纯标点率、EOS 率、重复长度和人工审核状态。
- 主要判据：直接回答率提升且不引入明显不安全或无关内容；单靠标点率下降不能晋级。与历史 CPU 采样结果比较时必须先核实其确切 temperature/top_p 配置，不能假设完全同口径。
- 当前执行环境缺少 transformers/peft，外部模型下载不可用；本轮未运行该新推理实验，不能预报结果。若依赖与模型可核验，优先使用现有授权的隔离 CPU Actions 流程做受控试验，不启动第 13 次 GPU 训练。

## 安全与经验
- 最新 Daily 新增了真实状态/Artifact，但没有新训练。与上轮相比：新 Daily Run `40275426137`、新 Artifact `12629319793`、main 最新报告目录变为 2026-10-26；GPU 指标和模型质量不变，CI 仍为 224/224。
- 避免把“已经完成的 CPU 首 Token 诊断”重复列为未执行，避免重复消耗算力。只在真实可复现缺陷存在时最小修复、测试并申请合并；PR #70 保持 Draft，保留回滚版本。
- 保护用户、维护人类。报告不含凭据、Token、个人隐私或原始模型问答；不修改或绕过安全保护，不将未核实的改善称为进化。
