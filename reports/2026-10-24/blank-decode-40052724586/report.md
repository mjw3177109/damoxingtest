# Run 12 空白生成：特殊 Token 解码根因审计（2026-10-24 10:07 CST）

## 假设与证据来源

上一轮候选模型在固定验证集第 4 条提示词生成了 **64 个 Token，却解码为空字符串**。本轮区分“全为特殊 Token”“全为空白字符”“普通 Token 被解码器过滤”三种解释，**不保存原始 Token ID、未经脱敏的提示词或输出**。

- 生产 GPU 训练：Actions Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，历史训练已结束，质量门槛拒绝晋级。
- 隔离 CPU 审计：Actions Run [40052724586](https://github.com/mjw3177109/damoxingtest/actions/runs/40052724586)，`completed/success`；**8 次 CPU 生成，0 次新 GPU 训练**。
- 静态预检：Actions Run [40052587955](https://github.com/mjw3177109/damoxingtest/actions/runs/40052587955)，`completed/success`；新增 6 项离线回归测试，完整单测通过。
- [PR #29](https://github.com/mjw3177109/damoxingtest/pull/29) 已合并；CPU 审计代码 SHA `40dfa067ecb73fcd00dda26fda55580fd07b47f5`。
- 模型：`uer/gpt2-chinese-cluecorpussmall`，固定 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 被拒绝的 Run 12 Adapter 权重 SHA-256：`979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 验证集 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 条件：固定前 4 条验证提示词、seed 42、贪婪解码、`repetition_penalty=1.12`、最多 64 个新 Token，推理输入不含 `token_type_ids`。
- Artifact ID `12543813789`，`run12-readability-review-40052724586`；ZIP SHA-256 `75996fa81f5f8af85c166d0d88874a8d45ecf7546badbe94d493b0d41eace595`；内部 `review.json` SHA-256 `c15eb874ec394d1e2a01bf7e1a190fc334ac04abec80ef2176a30db1dc95369d`。

## 实测结果

| 项目 | 基础模型 | Run 12 LoRA 候选 |
|---|---:|---:|
| 固定提示词 | 4 | 4 |
| 生成次数 | 4 | 4 |
| 纯标点输出 | 0/4 | 2/4 |
| 含中文字符 | 4/4 | 1/4 |
| EOS 停止 | 1/4 | 1/4 |
| 64 Token 上限 | 3/4 | 3/4 |

**新确认：候选模型第 4 条输出的 64 个生成 Token，全部属于 Tokenizer 的特殊 Token 集合。** 其中 EOS Token 数量为 0，PAD Token 数量为 0。原始（不跳过特殊 Token）解码长度为 383 字符；设置 `skip_special_tokens=True` 后长度为 0，`.strip()` 后仍为 0。故空字符串的**直接解码机制**已定位：64 个特殊 Token 被过滤；不是空白字符被 `.strip()` 去除，也不是模型没有生成 Token。

**尚未确定**这 64 个特殊 Token 的具体类别（例如 UNK/CLS/MASK 等）及模型为何持续选择它们。不能将“解码机制已确认”误写成“训练退化根因已修复”。其他 3 条候选输出仍不合格。

## 历史训练指标、质量门槛与对照

- Run 12 历史 GPU：Tesla T4、14.56 GiB、3 Epoch、33 有效步。
- Train Loss 3.246455；Val Loss 3.147277；PPL 23.272599；同轮基线 Val Loss 3.389291；同轮 Loss 改善 7.141%。**本轮没有新的训练指标**。
- Run 12 的 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json` 和 `quality_gate.json` 均在历史报告/Artifact 中；原训练 Artifact ID `12487687305`，本轮核实仍未过期。
- 质量门槛：`promotion_approved=false`，原 10 条样例 **0/10 合格**；本轮不晋级。
- 历史第 8 次 Val Loss 3.424955、PPL 30.721252，但验证集不同，**不能作为同口径历史最佳突破**。
- Kaggle Kernel 历史状态 `COMPLETE`；本轮未取得 Kaggle 实时 API 状态，不宣称当前 Kernel 已被实时核实。

## 本轮经验与下一步（只进行一个受控实验）

1. **不要把解码为空误判成没有生成。** 需要同时统计生成 Token 数、特殊 Token 数、EOS/PAD 数以及跳过特殊 Token 前后的解码长度。
2. 下一轮仅增加不含原始 ID 的特殊 Token **类别计数**（如 UNK/CLS/MASK），在相同模型、Adapter、提示词和解码参数下重跑有限 CPU 生成，确认 64 个特殊 Token 的具体类别。
3. 如确认是 UNK 等类别持续重复，再检查固定前缀下该 Token 的 Logits 与模型训练目标；先复核后修复，禁止盲目重训。
4. 不修改生产训练脚本、不启动 Kaggle GPU、不覆盖上一批准版本、不放宽质量门槛；不写入凭据或个人隐私。

**结论：本小时有可审计的 CPU 实验进展，确认空白输出的直接机制；模型仍不合格、未晋级。**
