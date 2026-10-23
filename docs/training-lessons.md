# GPT-2 训练故障与实验经验库

本文件记录可审计的真实运行结果。没有日志支持的改进不得记为成功；训练样例和指标不得虚构。所有训练始终遵守“保护用户、维护人类”，不记录凭据、Token 或个人隐私。

## 2026-10-23：Trainer 初始化前的 NameError

- 证据：GitHub Actions Run [39906737838](https://github.com/mjw3177109/damoxingtest/actions/runs/39906737838)，第 11 次运行，最终 `completed / failure`；[原始报告](../reports/2026-10-23/run-39906737838/report.md)。
- 代码基线：该次运行 `head_sha=de5f1ffadee73e146cdf7ae16abaa159f4470060`；修复前主分支 `03093013a156d665444d036ac5b7538f8c58c791`。
- 数据版本：训练 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`（85 条）；固定验证 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`（24 条）。
- 真实环境：历史运行日志显示 Kaggle Tesla T4，14.56 GiB；Kernel 第 6 版最终轮询为 COMPLETE，但训练本身 FAILED。
- 根因：`scripts/train_gpt2_lora.py:395` 实例化未导入的 `DataCollatorForLanguageModeling`，产生 `NameError`。该局部变量未被使用；`Trainer` 实际传入 `response_only_collator`。
- 最小修复：删除未使用的初始化行，保留 `response_only_collator` 及 `-100` 回答标签掩码。先在修复分支提交，验证通过后才进入新 GPU 训练。
- 防复发：增加仅 CPU 的 PR 静态预检：Python 编译、Ruff F821 未定义名称检测、Trainer 数据整理器接线和 `-100` 掩码结构检查。
- 第 11 次训练指标：有效训练步数 0；Train Loss、Val Loss、PPL 和 `samples.json` 均未生成。不得用第 8 次历史指标代替本次。
- 晋级：拒绝；不覆盖历史已批准的 Adapter。
- 验证状态：修复分支静态结构已检查；CI 和 Kaggle 运行时验证需以对应真实 Actions 记录为准。**本条不是训练成功声明。**
- 后续实验：修复并完成至少一轮有效训练后，固定训练/验证数据及随机种子，仅改变一个超参数进行对照；以固定验证集 Loss/PPL、样例质量和安全审查共同决定是否晋级。

## 2026-10-23：第 12 次完成训练，但生成质量门槛未通过

- 证据：GitHub Actions Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，`completed / success`；[本次报告](../reports/2026-10-23/run-39921870784/report.md)、[指标](../reports/2026-10-23/run-39921870784/metrics.json)、[样例](../reports/2026-10-23/run-39921870784/samples.json) 与 [质量门槛](../reports/2026-10-23/run-39921870784/quality_gate.json)。
- 训练代码 SHA：`647b909a994441e3affa3f65fc46f9d0acb2c958`；训练方案 SHA-256：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 数据：85 条训练样本，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；24 条固定验证样本，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- Kaggle：历史轮询为 `QUEUED → RUNNING → COMPLETE`；训练日志及元数据确认实际使用 Tesla T4、14.56 GiB 显存，完成 3 epochs、33 个有效训练步；本记录不等于实时 Kaggle 状态查询。
- 实测指标：Train Loss `3.2464554599`；基础验证 Loss `3.3892908096`、PPL `29.6449209212`；微调后验证 Loss `3.1472766399`、PPL `23.2725985343`；本次相对基线验证 Loss 下降 `7.141%`。训练日志记录总流程耗时 `67.25s`，其中 Trainer 内部训练耗时约 `11.6575s`，两者不能混为一谈。
- **生成质量失败**：`samples.json` 有 10 条，9 条输出为重复句点、1 条为重复问号；自动生成质量启发式仅 `0/10` 通过。质量门槛 `promotion_approved=false`，因此 **候选 Adapter 不晋级**。工作流成功只证明训练/报告流程执行成功，不证明模型可用。
- 与第 11 次对比：旧的 `NameError` 已消失；从 0 步、无指标变为 33 步、完整指标及 10 条样例。第 8 次历史运行使用不同数据规模，不能直接当作同口径模型提升证据。
- **未确认根因**：重复标点可能与极小语料、目标模型能力、tokenizer/终止符、贪婪解码、训练超参数等因素有关；仅凭现有日志无法确定哪一个是主因，不应擅自声称已修复。
- **下一次受控实验（先推理、后决定是否重训）**：保留第 12 次 Artifact 内的候选 Adapter 与固定 10 条提示词，锁定模型权重、tokenizer、输入、随机种子，比较原有 greedy 解码与一组受控采样参数（例如 `do_sample=True, top_p=0.9, temperature=0.8, repetition_penalty=1.12, no_repeat_ngram_size=3`）；分别记录原始 token IDs、终止符、重复率、可读回答比例、人工安全审核。若采样仍无法产生有意义的中文回答，先诊断数据与 tokenizer/训练目标，再决定是否设计仅改变一个变量的 GPU 训练实验。**当前未执行该实验，不得报告其结果。**
- 防止浪费 GPU：本次已有完整训练证据，若训练数据与 recipe hash 未变化，使用仓库的重复训练保护；文档更新不应触发 GPU 工作流。

## 2026-10-23：第 12 次生成退化的离线定量复核（无新 GPU 训练）

- 证据来源：[第 12 次 samples.json](../reports/2026-10-23/run-39921870784/samples.json)；运行 ID `39921870784`，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`。
- 直接统计保存的 10 条输出：**10/10 仅包含标点；10/10 各恰好 64 个相同字符；9 条是连续句点，1 条是连续问号；不同输出仅 2 种；最长相同字符连续长度为 64**。该复核没有产生新的模型回答。
- 当前 `scripts/train_gpt2_lora.py` 的默认 `--max-new-tokens=64`，与上述可见输出长度一致，但没有保存原始生成 token IDs、EOS 位置或停止原因，**不能仅凭字符长度断言模型一定因 token 上限停止**。
- 已合并 CPU-only 离线诊断工具 `tools/analyze_generation_samples.py` 和 4 项单测（PR #2），对应 CI [GPT-2 Static Preflight](https://github.com/mjw3177109/damoxingtest/actions/runs/39935735122) 通过。工具不复制提示词或原始回答到诊断结果，且不修改训练 recipe、数据或 Adapter。
- **下一步可验证假设**：对相同 10 条提示词、固定 seed 和同一基础模型/Tokenizer，在第 12 次候选 Adapter 与基础模型之间进行 greedy/采样交叉对照；必须记录原始 token IDs、EOS/停止原因、标点占比、回答可读率，并检查是否出现训练前就存在的相同退化。仅改变解码策略不足以证明模型权重质量改善。
- **晋级结论仍为拒绝**：`promotion_approved=false`，无新训练、无新 Loss/PPL，也无已验证的中文生成质量提升。不得将本次诊断工具改进称为模型进化。

## 2026-10-23：第 12 次基础模型 / Adapter 解码对照已完成（只推理，不训练）

- **证据**：只读 CPU 工作流 [Run 39950178751](https://github.com/mjw3177109/damoxingtest/actions/runs/39950178751) 已 `completed/success`，40/40 次推理及校验通过；对应 Artifact ID `12500012305`（`run12-readonly-decode-probe-39950178751`），永久统计摘要见 [summary.json](../reports/2026-10-23/probe-39950178751/summary.json)。PR #4 合并提交 `00b9e8d377051536fda3eeacf40972b4774a0a97`。
- **对照配置**：原始训练 Run `39921870784`；基础模型 `uer/gpt2-chinese-cluecorpussmall`，模型 commit `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；固定验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；10 条相同提示词，固定 seed 42、`max_new_tokens=64`，base/candidate × greedy/sample 各 10 次。仅使用 GitHub Actions CPU，没有重新分配 Kaggle GPU、没有训练或晋级。
- **真实对照（纯标点输出数 /10）**：基础模型贪婪解码 **7/10**；基础模型采样 **0/10**；候选 Adapter 贪婪解码 **10/10**；候选 Adapter 采样 **1/10**。
- **终止情况（根据 Token 推断）**：base/greedy 10/10 达到 64 Token、0 EOS；base/sample 7/10 达上限、3 EOS；candidate/greedy 10/10 达上限、0 EOS；candidate/sample 4/10 达上限、6 EOS。平均最长连续相同字符长度依次为 **45.4、2.3、64.0、2.3**。
- **可确认的新经验**：基础模型的贪婪解码本身就出现大量标点退化；候选 Adapter 在相同解码下更严重。采样明显改变了重复标点的形式，但 **不证明微调权重变好，也不证明回答可读、正确或安全**。报告默认不包含原始提示词和输出；原始 Token ID 在短期 Artifact 中供复核。停止原因只是基于 EOS/长度推断。
- **质量与晋级**：第 12 次训练的 Loss/PPL、GPU 和 33 步均未变化，候选 Adapter 仍 **不晋级**。本轮不产生新的 Train/Val Loss、PPL，也不能声称模型进化。
- **下一步**：在隔离环境对抽样输出做人工可读性/安全审核；再验证 Tokenizer、输入模板、EOS 与 base-vs-candidate 的逐 Token 分布。先完成归因和固定基准，再决定是否只调整一个训练变量。保留可回滚版本，不公开 Token 或隐私。

## 2026-10-23：第 12 次首 Token 重复惩罚处理后对照（无新训练）

- **真实运行**：只读 CPU [Run 39975111441](https://github.com/mjw3177109/damoxingtest/actions/runs/39975111441) 已 completed/success；Artifact ID 12511430496，原始 JSON SHA-256 75bd467d805da94c653d194fe9660b2194206edd8d9f990170c8f7e1fd338ad9；统计见 [summary.json](../reports/2026-10-23/probe-39975111441/summary.json)。
- **假设和配置**：此前原始首 Token logits 尚未经过 repetition_penalty=1.12，而生成处理器会将提示词中的 Token 纳入惩罚历史。固定 10 条提示词（验证集 SHA-256 5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f）、相同基础模型和被拒绝的第 12 次 Adapter（权重 SHA-256 979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c），CPU 前向共 20 次。
- **实际结果**：基础模型 raw top-1 为 ID 4500×3、8601×3、119×3、136×1；处理后为 119×6、8601×3、136×1。3/10 基础模型提示词首位 Token 从 4500 改为 119；候选模型 raw/processed 均为 119×9、136×1，0/10 改变。处理后 base 与 candidate 首位 Token 有 3/10 不同。
- **经验**：三个此前 raw-vs-greedy 首 Token 差异可以由重复惩罚处理解释，无须假设新的训练效果。ID 119/136/8601 在这 10 条提示词中均未出现；ID 119 的归一化概率仍可因其他已出现 Token 被惩罚而上升。此实验仅解释首步排序，**不能解释后续连续 64 Token 重复的根因**。
- **测试证据**：PR #9 合并代码 SHA f5cd209d667d215a89ca1bc4b9d6b336c699aa1a；[静态预检 Run 39975017533](https://github.com/mjw3177109/damoxingtest/actions/runs/39975017533) 通过，包含新增 4 项纯 Python 单测；CPU 实验完成并上传 Artifact。
- **质量结论**：无新增 GPU 训练、Train Loss、Val Loss、PPL 或生成文本；第 12 次候选质量门槛仍为 promotion_approved=false，保留历史已批准版本。
- **下一步**：在相同提示词、固定 Tokenizer 和 Adapter 下，对前 8 个生成步骤逐步记录处理前/后 logits top-1 与重复 Token 概率，比较 base 与 candidate；先只读 CPU 验证，不直接扩大 GPU 训练。
