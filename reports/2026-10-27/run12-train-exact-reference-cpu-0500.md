# GPT-2 Run 12｜05 时档严格输入下基础模型与 Adapter 参考质量对照（2026-10-27 CST）

## 判定

- **真实 CPU 对照已完成**：GitHub Actions Run [40401678864](https://github.com/mjw3177109/damoxingtest/actions/runs/40401678864) `completed/success`，10 条固定提示词 × 基础模型/被拒绝的 Run 12 Adapter，共 **20 次 CPU 生成**。没有提交 Kaggle、没有使用 GPU、没有训练或晋级。
- **假设**：上一轮 `train_exact` 输入令候选 EOS 达到 10/10；需要在**完全相同的训练输入契约**下比较基础模型和候选模型，排除此前基础模型/候选模型对照中 `token_type_ids` 的混杂因素，并检查是否过早结束。
- **实测**：两组 10 条参考答案字符 Bigram F1 均为 **0.000000**，候选减基础为 **0.000000**；本次未观察到词面重叠质量提升。此指标不能证明语义正确性或安全性。
- 基础模型：EOS **1/10**，平均生成 Token **59.2**，平均输出/参考字符长度比 **2.329**，短于参考答案 25% 长度 **0/10**。
- Run 12 Adapter：EOS **10/10**，平均生成 Token **19.0**，平均输出/参考字符长度比 **0.681**，短于参考答案 25% 长度 **2/10**（提示词索引 2、3）。
- 两组非空输出 **10/10**、包含中文 **10/10**、纯标点 **0/10**。EOS 10/10 不等于回答正确，且两条明显短答需要人工排查是否过早结束。
- **不晋级**：`promotion_approved=false`，`quality_certified=false`，直接回答率/事实性/安全性仍未审定。

## 可核查证据与环境

- 本轮实验工作流 `.github/workflows/run12-train-exact-reference-cpu.yml`，提交 `a35469218942b4c7357bf3f6941eb934f8e99048`；诊断工具 `tools/run12_train_exact_reference_cpu.py` 提交 `51806f964ed6a2436e840461856b98f9db020f00`；6 项测试 `tests/test_run12_train_exact_reference_cpu.py` 提交 `6d98a2f0c32ab83732f002b32ce660ba89f18b2a`。
- 静态 CI Run [40401556336](https://github.com/mjw3177109/damoxingtest/actions/runs/40401556336)：`completed/success`，**284/284 tests PASS**，Ruff F821、response-only collator 和 `-100` 标签掩码检查通过。CPU 工作流在推理前再次通过 6 项离线测试。
- GPU 历史权重来自 Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 基础模型 `uer/gpt2-chinese-cluecorpussmall`，固定 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；固定验证集 `data/safety_humanity_eval_v1.jsonl`，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 两组使用相同 10 条提示词、相同 tokenizer、`train_exact`（`add_special_tokens=False` 且删除 `token_type_ids`）、贪心解码、`max_new_tokens=64`、`repetition_penalty=1.12`。唯一模型变量为是否加载 Run 12 Adapter。
- 实验 Artifact ID **12688029323**，名称 `run12-train-exact-reference-40401678864`，已实际下载、解压并解析。内部 `train_exact_reference.json` SHA-256 **`dae4ec80378eb3e4d7f5644f5760ed70c3307bc710f1d0ab6b91d6b8914e5d2f`**。仅含聚合/逐题数值和提示词哈希，**不含原始生成文本、原始提示词、Token ID 列表或密钥**。

## Daily、Kaggle 与文件核验

- main 最新 Daily Training Run [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137)：`completed/success`，但 `SKIPPED_NO_CHANGES`、`kaggle_kernel_submitted=false`，没有新训练/新评估。
- main 最新目录 `reports/2026-10-26/run-40275426137`：`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已读取。Daily Artifact **12629319793** 和历史 GPU Artifact **12487687305** 存在且未过期。
- 历史真实 GPU Run 39921870784：Tesla T4，14.56 GiB，3 Epoch，33 步，Train Loss **3.246455**、Val Loss **3.147277**、PPL **23.272599**；本小时新 GPU 训练步数为 0，以上数值非本小时新指标。
- 正式归档旧样例有效回答 **0/10**，典型输出为连续标点；本次 CPU 实验没有公开新生成原文。正式质量门槛仍 `promotion_approved=false`、人工审核 pending。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 实时状态、GPU 配额及仓库外并发无法独立核实；**未启动第 13 次 GPU 训练**。

## 与上一轮、历史最佳及经验

- 上轮静态测试 **278**，本轮 **284**（+6）；上轮仅对同一 Adapter 比较 `train_parity` / `train_exact`，本轮已在严格输入下对比**基础模型与候选模型**，补齐了关键控制组。
- 候选相对基础模型 Bigram F1 差值 **0**；EOS 10/10 伴随平均回答长度明显缩短和 **2/10** 极短输出，不能据此宣布模型进化。
- 历史 Run 8 与 Run 12 验证集不同，不能跨轮直接比较 Loss/PPL 判断历史最优；保留上一可回滚版本，Draft PR #70 不合并。
- **经验**：训练/推理输入契约必须在基础模型和候选模型两侧同时固定；平均 EOS、中文占比、长度与词面重叠都只能作为诊断指标，不能替代逐题语义、安全和事实性评估。
- **下一步**：在不导出原文的受控私有 CPU 环境中，针对索引 2、3 和其余 8 条输出进行语义/事实/安全审核；记录可审计的聚合指标及人工判定，明确是否过早 EOS。若未达标，先定位监督数据和目标问题，再提出一次单变量训练实验；仅在 Kaggle 配额、并发、回滚与质量门槛核实后才允许 GPU。
