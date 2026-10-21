# 大模型实验室：保护用户，维护人类

这是一个面向初学者、可追踪、可复核的 GPT-2 微调实验项目。项目原则只有两条：

1. **保护我**：保护用户隐私、数据、账户、密钥与合法权益。
2. **维护人类**：尊重人的生命、尊严、自由与安全，诚实披露能力边界，不把未经验证的结果包装成成功。

## 目前采用的路线

- 基础模型：uer/gpt2-chinese-cluecorpussmall（中文 GPT-2）。
- 训练方式：LoRA 参数高效微调，目标 GPU 为 Kaggle 分配的 NVIDIA T4（16GB 显存）。
- 数据：仓库内公开、人工编写的安全与人类福祉种子语料；不上传私人聊天、密码、密钥或个人资料。
- 每日自动任务：GitHub Actions 每天北京时间 09:00 尝试启动 Kaggle GPU Notebook，收集日志、评估指标、样例输出和阶段评价。
- 模型权重：作为 GitHub Actions Artifact 保存，不将大文件或密钥提交到源码仓库。
- 结果报告：reports/日期/run-运行编号/，每次运行独立归档。

## 重要限制

仓库和 GitHub Actions 自身不提供 T4 GPU。训练需要 Kaggle 账户、有效 API 凭据、可用 GPU 配额和互联网访问权限。免费 GPU 可能排队、被分配到其他型号或因配额而不可用；若实际 GPU 不是 T4，脚本会记录原因并停止，不会谎称训练成功。

GPT-2 微调只是实验原型。小规模种子语料上的 loss 下降不代表模型具备通用推理能力，也不代表模型已经安全、可靠或真正理解伦理原则。每次输出仍需人工审核。

## 首次配置

1. 在 Kaggle 账户的 Settings / API 中创建 API 凭据。
2. 在本仓库 Settings → Secrets and variables → Actions 中添加：
   - KAGGLE_USERNAME：可选；默认使用已配置过的 Kaggle 用户名 mjw3177109。
   - KAGGLE_KEY：旧式 API Key；或者添加 KAGGLE_API_TOKEN：当前 API Token；也兼容 secret 名称 shipin。至少提供一种认证凭据。
3. 不要把 API 凭据写入代码、Notebook、日志或提交记录。
4. 打开 Actions，手动运行 Daily GPT-2 T4 Training。第一次运行可能因 Kaggle 审核、配额或 GPU 不可用而失败。
5. 查看 reports/ 下的日期报告，以及 Actions 运行页中的模型 Artifact。

工作流使用 GitHub 自动提供的 GITHUB_TOKEN 写回运行报告，因此通常不需要个人访问令牌 PAT。若组织策略限制自动写入，需要在 GitHub 仓库设置中检查 Actions 权限；不要把 PAT 硬编码进脚本。

## 项目文档

- 小白.md：从零理解项目、配置 GPU、阅读结果和处理失败。
- TRAINING_METHOD.md：模型、LoRA、损失函数、评估和局限。
- data/safety_humanity_seed.jsonl：公开种子训练语料。
- scripts/train_gpt2_lora.py：训练、评估、生成样例和保存 LoRA Adapter。
- .github/workflows/daily-gpt2-training.yml：每日调度与报告回写。

## 结果如何判定

只有当报告明确显示 SUCCESS，且包含训练指标与输出样例时，才把该次训练视为完成。Kaggle Notebook 成功启动不等于模型训练成功；loss 降低也不等于整体质量提升。请同时检查验证集 loss、困惑度、样例质量、隐私保护和潜在伤害风险。
## 训练是否跨日累积

当前版本每天从指定的基础 GPT-2 权重重新执行同一组小规模种子语料微调，目的是建立可重复的基线和每日运行审计；它不会自动接续前一天的 Adapter。原因是当前语料很小，反复累积训练容易过拟合。待新增经过许可和审核的数据、固定验证集与回滚标准后，再单独启用有版本控制的持续训练。

注意：GitHub Secrets 按仓库隔离。若 shipin 目前只存在于另一个仓库，damoxingtest 不会自动读取它；需要在本仓库的 Actions Secrets 中重新添加同一凭据，或创建新的 Kaggle API Token 并保存为 KAGGLE_API_TOKEN。不要把 token 发到聊天或写入源码。

每次训练还会在输出目录中逐阶段写入 stages/ 下的环境检查、数据准备、基线评估、LoRA 微调和最终评估说明。Kaggle Kernel 的输出通过 Kaggle API 在任务结束后下载，因此 GitHub 会在本次任务结束时统一提交已完成阶段的说明和日志，而不是每个阶段运行时实时推送。
