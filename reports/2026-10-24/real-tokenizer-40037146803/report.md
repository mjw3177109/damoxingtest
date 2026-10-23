# Run 12 真实 Tokenizer / EOS 合同审计（2026-10-24 07:01 CST）

## 可复核来源与实验假设

- 源 GPU 训练：Run `39921870784`（`completed/success`；实际训练 33 步），代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`。
- 上轮假设：`encode_record` 先拼接 EOS 再截断，可能造成 EOS 标签丢失；但此前仅在合成输入上复现，**未证实 Run 12 真实数据触发**。
- 本轮只读 CPU 实验：GitHub Actions Run [40037146803](https://github.com/mjw3177109/damoxingtest/actions/runs/40037146803)，`completed/success`；Artifact ID `12537029487`。
- 代码 PR [#23](https://github.com/mjw3177109/damoxingtest/pull/23)，静态预检 Run [40037084356](https://github.com/mjw3177109/damoxingtest/actions/runs/40037084356)，`completed/success`；本地及 CI 合成测试 4/4。
- 模型 `uer/gpt2-chinese-cluecorpussmall`，固定模型 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`，`transformers==4.46.3`，`max_length=256`；不加载权重、不训练、不使用 Kaggle GPU。
- 训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`，均与 Run 12 元数据匹配。

## 真实 Tokenizer 结果

Tokenizer 为 `BertTokenizerFast`，词表 21128，EOS ID = SEP ID = `102`，PAD ID = `0`。与训练脚本一样使用 `add_special_tokens=False`，编码 `用户：...\\n助手：` 前缀和 `response + eos_token`，再按 256 截断，并统计实际参与监督的非 `-100` 标签。

| 真实指标 | 训练集 | 固定验证集 |
|---|---:|---:|
| 数据条数 | 85 | 24 |
| 前缀 Token 长度 min/median/max | 14 / 25 / 36 | 25 / 31 / 40 |
| 回答含 EOS Token 长度 min/median/max | 40 / 50 / 73 | 43 / 54 / 63 |
| 拼接总长度 min/median/max | 61 / 75 / 99 | 75 / 83 / 93 |
| 超过 256 并截断 | **0** | **0** |
| 无有效回答监督 Token | **0** | **0** |
| 完整回答末尾缺 EOS | **0** | **0** |
| 截断后监督标签末尾缺 EOS | **0** | **0** |

**结论：Run 12 的 109 条真实数据均未发生 EOS 截断，EOS 均参与监督。** 因此，合成边界条件确实存在，但不是当前 Run 12 重复标点输出的已证实根因。无需为了该假设修改训练脚本、触发新 GPU 训练。未来新增超长数据时仍应保留 EOS 边界回归测试。

## 训练、质量与对照（全部为历史值，非本轮新增）

- Run 12：Tesla T4 / 14.56 GiB，3 Epoch，33 步；Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`，相对自身基线 Val Loss 改善 `7.141%`。
- `samples.json` 中 10 条输出均为重复标点；`quality_gate.json`：`promotion_approved=false`、`meaningful_generation_samples=0/10`。**不晋级**。
- 历史第 8 次 Val Loss `3.424955`、PPL `30.721252`，但验证集不同，不能宣称 Run 12 超越历史最佳。
- GitHub Actions 训练 Run `39921870784` 与历史 Kaggle 状态 `COMPLETE` 只证明该轮结束；**本轮未获取 Kaggle 实时 Kernel 状态**。
- 本轮无新增 GPU 训练、Train/Val Loss、PPL、模型权重或完整回答；训练 Artifact `12487687305` 仍存在，CPU 审计 Artifact `12537029487` 已上传。

## 本轮经验、阻塞与下一步

1. **经验：先验证真实数据是否触发边界风险，再修改生产训练代码。** 合成 EOS 截断风险不能直接解释 Run 12 的质量失败；真实 Tokenizer 审计已排除当前 109 条数据的该因素。
2. 当前根因仍未确定；基础模型与 LoRA 候选均存在重复标点倾向。下一轮优先比较固定真实中文提示下的 EOS 概率、生成停止行为与训练目标/提示模板是否一致，设计只读 CPU 单变量实验，并保留原始指标与安全审阅。
3. 仅当有可复现根因、最小补丁、静态/单测/必要的初始化验证、无并发 Kernel、配额确认后，才考虑新 GPU 实验；不得自动覆盖上一批准版本。
4. 安全边界：保护用户、维护人类；不提交 Token、密钥、个人数据或原始提示词；报告仅记录聚合数值、版本与可审计证据。

原始聚合 JSON：同目录 `tokenizer_contract_audit.json`；GitHub Artifact 可用于交叉核对。