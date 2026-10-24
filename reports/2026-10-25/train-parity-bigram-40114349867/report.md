# Run 12：train-parity 下的 no-repeat bigram CPU 对照（北京时间 2026-10-25 01:04）

## 目的与避免重复
仓库已有 [Run 40016790586](https://github.com/mjw3177109/damoxingtest/actions/runs/40016790586)：10 条提示词、64 Token、不同输入协议下的二元组去重实验，结论为“减少机械重复但不能证明回答有用”。本轮**不把旧实验当作新发现**；只补齐与最新 [自由生成 Run 40109722670](https://github.com/mjw3177109/damoxingtest/actions/runs/40109722670) 严格可比的四条固定提示词、train-parity 输入与 32 Token 上限。目标是测量单变量 `no_repeat_ngram_size: 0→2` 对句点、UNK、EOS、中文字符出现率的影响，而不是声称模型能力升级。

## 代码、数据、测试、Artifact 证据
- 代码变更：[PR #52](https://github.com/mjw3177109/damoxingtest/pull/52) 已合并，实验代码 SHA `adb7541cdb579a9fa3a8b01a921fcc4ea618fdce`；仅新增独立 CPU 诊断脚本、6 项单测和只读 Actions 工作流。
- 静态预检：[Run 40114294567](https://github.com/mjw3177109/damoxingtest/actions/runs/40114294567)，`completed/success`；**126/126 单测通过**，编译、F821、response-only collator 和 -100 掩码检查通过。
- CPU 实验：[Run 40114349867](https://github.com/mjw3177109/damoxingtest/actions/runs/40114349867)，`completed/success`；**16/16 次 CPU greedy 生成**，4 条固定提示词 × 基础/被拒绝 LoRA × 控制/禁止重复二元组。严格校验控制组与 Run 40109722670 一致，验证通过。
- Artifact：ID `12566934514`，名称 `run12-train-parity-bigram-40114349867`，已下载、解压并读取 `diagnostics.json`；ZIP SHA-256 `9aead243f522406dd88b3fe73c9542173afbc8d9812b9376d61992a9275ba29a`。
- 源 GPU 训练：[Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)；模型 `uer/gpt2-chinese-cluecorpussmall` revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；被拒绝 Adapter 权重 SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证集 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 运行配置：CPU、seed `42+prompt_index`、`do_sample=false`、`max_new_tokens=32`、`repetition_penalty=1.12`、相同 Tokenizer/Adapter/输入历史，仅 `no_repeat_ngram_size` 从 0 改为 2；无 Kaggle 提交，无新 GPU 训练。

## 实测结果（每组 4 条）
| 模型 / 设置 | 句点 Token 总数 | UNK 总数 | 最长句点连续 | 纯标点输出 | 含中文字符 | EOS | 达上限 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 基础 / control | 0 | 1 | 0 | 0/4 | 4/4 | 0/4 | 4/4 |
| 基础 / no-repeat-bigram | 1 | 0 | 1 | 0/4 | 4/4 | 0/4 | 4/4 |
| 候选 / control | **64** | **32** | **32** | **2/4** | **1/4** | **1/4** | **3/4** |
| 候选 / no-repeat-bigram | **4** | **2** | **2** | **1/4** | **3/4** | **3/4** | **1/4** |

候选模型的句点数由 64→4、UNK 数由 32→2、最长句点连续长度由 32→2；但仍有 **1/4 纯标点输出**，含中文字符不等于回答正确，EOS 增多也可能只是提前终止。本实验**没有保存未经脱敏的原始文本或 Token ID，没有进行人工语义/安全评审，因此不能宣称回答质量改善**。

## 训练、质量门槛与历史对照
最近真实 GPU 训练仍是 Run 39921870784：NVIDIA Tesla T4，14.56 GiB，3 Epoch，33 有效步，Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`，同轮基线 Val Loss `3.389291`，改善 `7.141%`。**本轮新增 GPU 步数为 0，Train/Val Loss/PPL 均无新值**。Run 8 的验证集不同，不得据此宣称超过历史最佳。

最新 Daily [Run 40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092) 为 `SKIPPED_NO_CHANGES`，仅复用历史指标。历史正式生成质量为 **0/10**，`promotion_approved=false`；本轮亦 `promotion_approved=false`。最近 Kaggle Kernel Version 8 的 `COMPLETE` 仅来自历史 Actions 日志，本轮**未独立实时查询 Kaggle**。训练日志、指标、样例、元数据、质量门槛与历史 Artifact 仍可在对应 Run 报告/Actions 查验。

## 经验与下一步
1. **避免重复实验：** 旧 10 条提示词的 no-repeat 实验已经证明机械去重不等于语义改善。本轮新增价值仅在于与 Run 40109722670 的严格同口径控制组对照。
2. **确认结构变化但不晋级：** 在四条固定提示词上，候选句点和 UNK 循环显著减少，但仍有纯标点输出且没有经人工确认的有效回答；本轮拒绝晋级。
3. **下一步仅一项可测量实验：** 在同一四条固定提示词上，离线审阅隐私过滤后的候选回答，逐条评估“直接回答、相关性、事实正确性、安全性”，与基础模型、原始控制组配对；若只改变表面重复而不改善任务完成率，实验判失败。
4. **安全边界：** 不更改生产训练配方、模型权重、训练数据或质量门槛；不提交凭据、原始隐私、未脱敏文本；不启动第 13 次 GPU 训练；保留历史已批准模型和回滚路径。
