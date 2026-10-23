# Run 12 生成轨迹同前缀复核（只读离线分析）

- 复核日期：2026-10-24（北京时间）；本报告不代表新 GPU 训练或新模型推理。
- 证据：GitHub Actions CPU Run `39984106556`，Artifact `12514931481`；原始 `conditional_tokens.json` SHA-256：`f2b8dc5e1c9a094a1cd9c53d6ffce3796069ee9137d50bfe1ef2fab5eb4d7143`。
- 训练来源：Run `39921870784`，训练代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958`；基础模型 commit `c2c0249d8a2731f269414cc3b22dff021f8e07a3`；候选 Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。
- 固定验证数据 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；模型 `uer/gpt2-chinese-cluecorpussmall`；解码 greedy、repetition_penalty=1.12，修复后的 Tokenizer 输入一致性检查通过。
- **待验证假设**：不同模型一旦生成了不同 Token，后续概率分布不能直接比较并归因于 LoRA，因为生成历史也变了。只比较相同提示词、相同已生成 Token 前缀的步骤。
- **真实结果**：4 条提示词 × 最多 8 步，理论上 32 组配对；只有 **18 组具有相同生成历史**，其中候选 Token 119 处理后概率较基础模型高 **13 组**、低 **5 组**。提示词索引 0、2 均有 8 个同前缀步骤；索引 1、3 在第 1 步输出分歧，只有首步可直接比较。
- **关键解释**：LoRA 并非在所有可比步骤上都提高 Token 119 的概率；历史 8 步实验中的候选 4/4 重复现象不能简单解释为“每步 Token 119 概率都比基础模型高”。本次没有新模型前向计算，也没有确定唯一根因。
- **本地验证**：4 项纯 Python 单测通过；使用真实 Artifact 原始 JSON 验证 SHA-256 后离线生成 `matched_history_summary.json`；不读取凭据、原始提示词或模型回答。
- **训练与晋级**：无新 GPU 分配、有效训练步数、Train Loss、Val Loss、PPL 或新回答；第 12 次历史质量门槛仍为 `promotion_approved=false`，不晋级，不覆盖上一最佳版本。
- **下一步单变量实验**：使用完全相同的 Token 前缀（teacher forcing）分别前向基础模型和候选模型，锁定模型/Tokenizer/Adapter/验证集/seed，记录原始与处理后 Token 119 概率；必须先通过首步一致性与输入张量检查，再判断是否需要调整训练配置。不得直接重复 Kaggle GPU 训练。

可复现命令：

```bash
python tools/audit_matched_token_trajectories.py \
  --input conditional_tokens.json \
  --sha256 f2b8dc5e1c9a094a1cd9c53d6ffce3796069ee9137d50bfe1ef2fab5eb4d7143 \
  --output matched_history_summary.json
```
