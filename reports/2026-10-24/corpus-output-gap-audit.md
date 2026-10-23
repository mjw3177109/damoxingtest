# 第 12 次候选模型：语料与生成退化差距审计（2026-10-24 04:57 CST）

## 审计边界与证据
- 本次为**只读 JSONL 静态审计**，没有模型前向计算、GPU 训练、Kaggle Kernel 启动、训练代码修改或模型晋级。
- 主分支基线：`6d24985fe1a13e4c46b1d430cbac331c893edc8f`。
- 训练来源：[Actions Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`。
- 训练数据 `data/safety_humanity_train_v2.jsonl`，SHA-256（源运行元数据）`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`。
- 固定验证 `data/safety_humanity_eval_v1.jsonl`，SHA-256（源运行元数据）`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 生成证据：[第 12 次 samples.json](../run-39921870784/samples.json) 的相对路径应以本仓库 `reports/2026-10-23/run-39921870784/samples.json` 为准；[第 12 次质量门槛](https://github.com/mjw3177109/damoxingtest/blob/main/reports/2026-10-23/run-39921870784/quality_gate.json) 为 `promotion_approved=false`。
- 最近一次 CPU 对照：[Run 40016790586](https://github.com/mjw3177109/damoxingtest/actions/runs/40016790586)，其统计见 `reports/2026-10-24/no-repeat-40016790586/summary.json`。

## 静态检查方法与结果
将两个 JSONL 文件逐行按 JSON 对象解析；验证每条有非空 `instruction` 与 `response`；按 Python/JS 字符串长度统计回复长度；以 Unicode 汉字范围 `U+4E00–U+9FFF` 判断是否包含中文；以是否含中英文字母或数字判断是否为“纯标点/符号”；以去空白并小写的指令比较训练/验证集交集。该方法是字符级审计，不是 Tokenizer 分词统计。

| 指标 | 训练集 | 固定验证集 |
|---|---:|---:|
| 记录数 | 85 | 24 |
| 不同指令 | 85 | 24 |
| 不同回复 | 85 | 24 |
| 包含汉字的回复 | 85 | 24 |
| 纯标点/符号回复 | **0** | **0** |
| 回复字符数：最小/中位/最大 | 39 / 50 / 72 | 42 / 53 / 62 |
| 回复平均字符数 | 49.81 | 52.13 |

- 五项断言全部通过：训练≥80、验证≥20、字段非空、训练指令不重复、训练/验证标准化指令交集为 **0**。
- 第 12 次生成样例却是 **10/10 纯标点**（9 条重复句点、1 条重复问号）；该现象与源语料回复的表面分布明显不一致。
- **这不能证明数据无缺陷，也不能证明唯一根因是 LoRA、Tokenizer 或解码策略。** 语料仅 85 条、回复较短，规模有限；现有结果不能证明泛化质量。
- 旧 `DataCollatorForLanguageModeling` NameError 已在当前 `scripts/train_gpt2_lora.py` 消除：该名称出现次数为 0；`response_only_collator` 仍被定义并传入 Trainer。无需重复提交旧修复。

## 可测量的下一步（先 CPU，不耗 Kaggle 配额）
1. 在隔离环境使用**完全相同的 10 条验证提示词**、固定基础模型 commit、原第 12 次被拒绝 Adapter、Tokenizer 和 seed，比较 base/candidate 的真实回答；优先进行小规模人工可读性与安全审阅，**不得将未审阅回答公开提交**。
2. 对同一批输出统计：中文字符占比、纯标点比例、EOS、截断、长度、是否回答了问题；将可公开的聚合指标和人工审阅结果（不含原文/隐私）归档。
3. 同时审计 Tokenizer 的 EOS/SEP 设置、回答标签掩码（`-100`）及生成模板一致性；只在获得可复现差异后设计单变量修复/训练实验。
4. 如需重训，先通过静态检查、单测和初始化验证，再检查已有 Kaggle 任务/配额与历史最佳版本；严格保留回滚，且未通过人工与自动质量门槛不得晋级。

## 判定
- 本次仅新增可复核的语料分布证据和实验假设；**无新 Train Loss、Val Loss、PPL、GPU 步数或新模型回答**。
- 最新 GPU 训练仍为第 12 次（33 步；Tesla T4 14.56 GiB；Train Loss 3.246455；Val Loss 3.147277；PPL 23.272599），属于历史数据而非本小时新增结果。
- 与第 8 次因验证数据不同，**不能**声称同口径超越历史最佳。
- 候选模型 `promotion_approved=false`；未修改任何安全保护、凭据、训练数据或模型权重。
