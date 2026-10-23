# GPT-2 Run 12：response-only 标签与 EOS 边界回归审计（2026-10-24 06:00 CST）

## 本轮证据与范围

- 训练仓库：`mjw3177109/damoxingtest`；训练源 Run：`39921870784`，训练代码 SHA：`647b909a994441e3affa3f65fc46f9d0acb2c958`。
- 审计基线主分支：`f9099abf219db0d18990bb44ba8bc740ebe057fa`；新增测试提交：`75c3e0b0db32f04c8560fbb4daa6f086bfec1c5f`。
- 测试 PR：[#21](https://github.com/mjw3177109/damoxingtest/pull/21)；实际 GitHub CI：[Static Preflight Run 40030695396](https://github.com/mjw3177109/damoxingtest/actions/runs/40030695396)，`completed/success`。
- 该 PR **仅新增** `tests/test_response_label_contract.py`；没有修改训练脚本、Kaggle notebook、模型权重、数据集、Secrets、训练工作流或质量门槛。
- 测试为标准库 unittest + AST 提取**仓库真实嵌套函数**，使用合成 Tokenizer/张量替身；不加载 Hugging Face 模型、不使用 GPU、无 Kaggle 任务、无网络或真实生成文本。

## 已验证的五项合同

1. 正常样本的用户/助手提示词 Token 标签为 `-100`，回答 Token 参与监督，末尾合成 EOS 参与监督。
2. 输入总长度恰好等于 `max_length` 时，合成 EOS 保留。
3. 指令前缀过长导致没有任何回答 Token 时，抛出 `ValueError`，不静默训练空回答。
4. 批次 padding 的注意力掩码为 0、标签为 `-100`，不会参与 loss。
5. `Trainer(data_collator=...)` 绑定 `response_only_collator`；历史未定义的 `DataCollatorForLanguageModeling` 名称未出现。

本地对等代码片段验证：5/5；GitHub CI 对**真实仓库源文件**执行了 unittest、Python 编译、Ruff F821 和现有 AST 检查，所有步骤 `success`。CI 通过只说明上述静态与替身合同成立，**不代表真实 Tokenizer/EOS 配置、模型训练或生成质量通过**。

## 新识别的边界风险（尚未修复）

`encode_record` 先将 `response + eos_token` 编码，再将 `prefix_ids + answer_ids` 按 `max_length` 截断。若截断发生在回答末尾，可能**静默删除 EOS 标签**，但仍保留其他回答标签，不触发“没有回答 Token”的异常。

合成替身复现：完整输入 10 Token，`max_length=9` 时仅留下 9 Token；`eos_in_full=true`，`eos_in_truncated=false`，仍有 1 个非 `-100` 标签。这是**边界条件风险**，不是 Run 12 发生 EOS 截断的证据。当前 85/24 条语料是否实际超过 256 Token，尚需使用 Run 12 固定模型 commit `c2c0249d8a2731f269414cc3b22dff021f8e07a3` 的**真实 Tokenizer** 验证。

因此本轮**不直接改训练配方**：修改 `scripts/train_gpt2_lora.py` 会触发 GPU 训练工作流，未取得真实 Tokenizer 分布证据前不应浪费 Kaggle 配额。

## 训练和模型质量状态

- 最新 GPU 训练仍为 Run `39921870784`，Tesla T4 / 14.56 GiB、33 步、Train Loss `3.246455`、Val Loss `3.147277`、PPL `23.272599`（均为历史实测，非本轮新增）。
- 最新候选 `quality_gate.json`：`promotion_approved=false`，10 条历史生成样例均为重复标点；无新的训练或生成质量改善。
- 第 8 次与第 12 次验证集不同，不可声称同口径超过历史最佳。
- Kaggle 当前 Kernel 实时状态未获得独立 API 证据；历史 Actions 中的 COMPLETE 不等于本轮有训练。

## 下一步可验证实验

在**只读 CPU 环境**固定模型 commit、Tokenizer 和原始 109 条数据，统计每条 `prefix_ids`、`answer_ids`、EOS ID、截断后 EOS 是否保留、有效监督 Token 数和标签掩码；对比 train/eval 分布，先产出无敏感文本的聚合统计与测试。若真实发现 EOS 截断，再单变量最小修复并完成静态/单测/初始化验证；只在安全门槛通过且确认无并发 Kernel、配额可用后考虑新 GPU 实验。保留旧版本与被拒绝候选，不做未经验证的晋级。

## 经验

`-100` 和 collator 的 AST 存在性检查不等于真实行为测试；但替身测试也不能替代真实 Tokenizer 的特殊 Token ID、长度分布与模型生成验证。逐层建立可重复证据，避免将 CI success、EOS 合成测试或 Loss 下降误报为模型进化。全过程保护用户、维护人类，不记录或暴露凭据。
