# GPT-2 Run 12 标点塌缩：语料与生成输出的只读对照（2026-10-26 12:00 CST）

## 本轮目标、假设与证据边界
- 假设 H1：Run 12 连续 64 个句点/问号的退化输出，是因为监督回答语料本身以纯标点或长串重复标点为主。
- 本轮直接读取仓库 main 的 85 条训练回答、24 条固定验证回答，以及 `reports/2026-10-25/run-40165941479/samples.json` 中复用自 Run 12 的 10 条历史生成输出；仅计算聚合字符统计，不输出原始提示词、回答或私人内容。
- 使用固定字符集合 `。！？!?.,，、；;：:…·` 统计标点占比，Unicode P/S 类别判定纯标点；相同标点连续 8 个及以上视为长重复。**这不是 Token 概率实验，不进行模型推理，不是因果检验。**
- 本轮新增只读、可复现的 `tools/punctuation_collapse_audit.py` 和 `tests/test_punctuation_collapse_audit.py`。代码不读取密钥、不访问网络、不修改训练文件或模型；输出只有聚合数字。
- 重跑命令（仓库根目录）：`python tools/punctuation_collapse_audit.py --train data/safety_humanity_train_v2.jsonl --eval data/safety_humanity_eval_v1.jsonl --samples reports/2026-10-25/run-40165941479/samples.json`。

## 实际聚合结果（当前 main 语料、历史 Run 12 生成）
| 指标 | train | eval | Run 12 历史生成 |
|---|---:|---:|---:|
| 条目数 | 85 | 24 | 10 |
| 回答/输出总字符 | 4234 | 1251 | 640 |
| 指定标点字符数 | 383 | 110 | 640 |
| 标点字符占比 | **9.0458%** | **8.7929%** | **100.0000%** |
| 纯标点条目 | **0/85** | **0/24** | **10/10** |
| 首字符为指定标点 | 0/85 | 0/24 | 10/10 |
| 同一标点最大连续长度 | 0 | 0 | **64** |
| 相同输出/回答的去重数 | 85 | 24 | **2** |

- 历史生成 10 条均为 64 字符；9 条全句点，1 条全问号。此处是历史结果的重新统计，**不是本小时新生成**。
- 训练回答长度 39–72 字符，中位数 50；验证回答 42–62 字符，中位数 53。训练集没有纯标点回答、也没有连续 3 个及以上相同标点的回答。
- **H1 不获支持：** 现有监督语料并非纯标点主导，生成却完全塌缩。不能因此推断唯一根因是解码、优化器、模型或标签，也不能把字符比例当作 Token 概率。
- 下一项可测量实验（尚未执行）：对已经存在的 Run 12 Adapter 与同 revision 基础模型，使用相同 4 条固定非敏感提示词、同一 Tokenizer/随机种子/解码参数，仅比较首步 `.`、`?`、EOS 和非标点候选 Token 的 logit/rank/概率及熵；CPU 运行，记录 Adapter 与基础模型差异。只有真实 Adapter 和基础模型可核验且不需重新训练时才执行；不得宣称尚未运行的实验结果。

## 代码、测试与来源
- 诊断脚本提交：`b0876e33210435822ccbd7f275297e6bfa85be0b`。
- 测试提交：`5e901cc4d3f7587215429b7f170b580213e6de84`。
- GitHub Static Preflight [Run 40267391739](https://github.com/mjw3177109/damoxingtest/actions/runs/40267391739)：completed/success；真实 Job `121392650797` 日志确认 **220/220** 单元测试通过、Ruff F821 与 response-only 标签掩码检查通过。
- 本轮本地隔离 Python 合成测试 **4/4 PASS**、编译通过；CI 执行了相同四项单测。CI **没有运行真实语料聚合命令**；上表聚合结果来自本轮只读读取真实 GitHub 文件后计算，不冒充 CI 产物。
- 真实 GPU 来源：Actions [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`，基础模型 `uer/gpt2-chinese-cluecorpussmall` revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。
- 数据 SHA-256（历史训练元数据）：train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`，eval `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；历史 recipe SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。本轮没有更改上述数据和训练配方。

## 运行、模型指标与产物
- 最新 Daily [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：completed/success，但 `training_status.json` 记录 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；本小时无新 GPU 训练、评估或样例。
- 历史真实 GPU：Tesla T4 14.56 GiB；3 Epoch、33 步；Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基础 Val Loss 3.389291，改善 7.141%。本轮没有新的 Train Loss、Val Loss 或 PPL；Run 8/12 的验证集不同，不能认定跨轮历史最佳变化。
- 已核实 `reports/2026-10-25/run-40165941479/` 存在 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`。最新 Daily Artifact `12588187512`（未过期，2026-11-24 UTC 到期）；历史 Run 12 Artifact `12487687305`（未过期，2026-11-22 UTC 到期）。
- 最新 CI 不包含模型 Artifact；历史 10 条生成自动质量门槛 0/10，`promotion_approved=false`，人工审核 pending，模型不晋级。
- Kaggle 实时 Kernel 状态、Kernel 版本和剩余 GPU 配额尚未独立核实；不能将历史 COMPLETE 或 GitHub Actions success 当作本小时训练成功。

## 经验、风险与下一步
1. 对同一份真实数据做最小只读实验，已经排除“监督回答几乎全是纯标点”这一简单解释；但不代表查明了生成塌缩的根因。
2. 与上一轮比较：静态 CI 单测 **216 → 220**，新增可复现聚合诊断与 4 项测试；模型指标、语义质量、晋级状态均无变化。
3. `scripts/train_gpt2_lora.py` 当前没有 `DataCollatorForLanguageModeling` 未定义引用，`response_only_collator` 仍连接 Trainer；无需重复修复已消失的 NameError。
4. 保持 PR #70 Draft，等待真实 Kaggle 状态、配额、来源归属及独立评估核验；不启动第 13 次 GPU 训练、不并发重复提交、不放宽质量门槛、不覆盖历史可回滚版本。
5. 保护用户、维护人类；不提交密钥、Token、个人隐私或原始问答内容。所有改善必须经过独立可重复的质量验证，不能称未经证实的“进化”。
