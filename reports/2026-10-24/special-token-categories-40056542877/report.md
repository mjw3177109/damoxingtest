# Run 12 特殊 Token 类别审计（2026-10-24 11:02 北京时间）

## 假设与实验范围

上一轮 CPU 实验确认：第 12 次被拒绝的 LoRA 候选模型在固定验证集第 4 条提示词上生成了 64 个特殊 Token，`skip_special_tokens=True` 后为空字符串，但**尚不清楚具体类别**。本轮只在隔离 CPU 诊断工具中新增互斥的特殊 Token 类别计数；**不导出原始 Token ID、未经脱敏的提示词或生成文本**。当 EOS 与 SEP 等类别共用一个 ID 时，按固定优先级归类，避免重复计数。

- 代码：PR [#31](https://github.com/mjw3177109/damoxingtest/pull/31) 已合并；代码 SHA `1cb467e67336299cd94ff37fd5fec59f1e85a658`。
- 静态预检：[Actions 40056516440](https://github.com/mjw3177109/damoxingtest/actions/runs/40056516440) `completed/success`；新增 **3 项**离线回归测试，完整测试发现无失败。
- CPU 诊断：[Actions 40056542877](https://github.com/mjw3177109/damoxingtest/actions/runs/40056542877) `completed/success`；固定 4 条提示词，基础模型与候选模型各 4 次，共 **8 次**生成；无新 GPU 训练。
- 生产训练来源：[Actions 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，第 12 次 GPU 训练已结束。
- 模型：`uer/gpt2-chinese-cluecorpussmall`，固定 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；沿用 Run 12 被拒绝的 Adapter，权重 SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 固定验证集 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 推理条件：seed 42、贪婪解码、`repetition_penalty=1.12`、最多 64 个新 Token，推理输入不含 `token_type_ids`；本轮只增加诊断字段，未更改生成策略。
- Artifact ID `12545676065`（`run12-readability-review-40056542877`）；ZIP SHA-256 `8cf22daa858ea37d8347981c22a8ca22ae587be4a6852f0c9ad40c662c7182a7`；内部 `review.json` SHA-256 `0a9cd4a2863a043d4c6e11a6e49a0228ad54e5e3d57c8206686fbc144dbb64f1`。

## 真实结果

| 项目 | 基础模型 | Run 12 LoRA 候选 |
|---|---:|---:|
| 生成次数 | 4 | 4 |
| 纯标点输出 | 0/4 | 2/4 |
| 包含中文 | 4/4 | 1/4 |
| EOS 结束 | 1/4 | 1/4 |

**核心发现：候选模型第 4 条输出的 64 个生成 Token 全部被归类为 UNK（未知词）特殊 Token；EOS=0、PAD=0、CLS=0、MASK=0、SEP=0、BOS=0、other_special=0。** 该条达到 64 Token 上限，没有通过 EOS 结束。过滤特殊 Token 后的解码文本长度为 0。

这把“空白输出由特殊 Token 过滤造成”的结论进一步精确为“**64 次 UNK 特殊 Token 输出被过滤**”。这是**直接输出机制**，并不等于已解释模型为何偏好 UNK；也不能将结果称为训练修复或模型进化。

## 与上一轮、历史训练对比

上一轮的 8 次 CPU 生成只确认“64/64 为特殊 Token”；本轮同样 8 次、相同配置下明确类别为 **64/64 UNK**。候选纯标点 2/4、含中文 1/4、EOS 1/4 与上一轮一致；**生成质量没有得到验证性改善**。

历史第 12 次 GPU 实测：Tesla T4、14.56 GiB、3 Epoch、33 步，Train Loss 3.246455，Val Loss 3.147277，PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。本轮没有新训练指标。第 8 次历史 Val Loss 3.424955、PPL 30.721252，但验证集不同，不能判定第 12 次优于历史最佳。

历史 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json` 和 `quality_gate.json` 已存在于第 12 次报告及 Artifact；原训练 Artifact ID `12487687305`，本轮检查未过期。第 12 次质量门槛 `promotion_approved=false`，原始生成样例 **0/10** 通过，**禁止晋级**。历史 `DataCollatorForLanguageModeling` NameError 已修复，`response_only_collator` 保留，本轮没有重复修改。Kaggle 历史状态为 COMPLETE，未取得实时 Kaggle API 状态。

## 经验与下一步（一次受控实验）

1. 解码为空时，不仅要统计特殊 Token 总量，还应使用**互斥类别计数**确认 UNK/CLS/MASK/EOS/PAD 等类别；遇到特殊 Token ID 别名必须避免双计。
2. 下一轮仅在固定前缀下测量基础模型与 Run 12 候选模型的 **UNK Logits/概率及排名**，保持模型、Adapter、提示词、Tokenizer、解码条件和随机种子一致；只运行受控 CPU 诊断，不泄露原始 ID、提示词或凭据。
3. 在确认根因、静态检查、单测和必要的初始化验证通过前，不更改生产训练配方、不重新启动 Kaggle GPU、不放宽安全或质量门槛、不覆盖历史批准版本。

**结论：本小时有可审计的工程与 CPU 实验进展；已确认空白输出的直接 UNK 机制，但模型仍不合格、未晋级。**
