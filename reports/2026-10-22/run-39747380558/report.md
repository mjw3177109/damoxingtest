# GPT-2 首次真实 T4 微调运行报告

- GitHub Actions Run： [#39747380558](https://github.com/mjw3177109/damoxingtest/actions/runs/39747380558)
- Kaggle Notebook： [damoxingtest-gpt-2-daily-training](https://www.kaggle.com/code/mjw3177109/damoxingtest-gpt-2-daily-training)
- 完整运行 Artifact（含 Adapter 权重、metrics、samples 和阶段日志）： [下载 Artifact](https://github.com/mjw3177109/damoxingtest/actions/runs/39747380558/artifacts/12412086613)
- Kaggle Kernel 执行状态： COMPLETE
- 训练脚本最终状态： FAILED（第四阶段报告写入时出现 Python 变量顺序错误）
- 实际 GPU： Tesla T4，14.56 GiB 可见显存

## 训练过程

1. 环境检查通过，确认 CUDA 可用且 GPU 为 Tesla T4。
2. 数据准备完成：35 条人工编写的安全与人类福祉种子样本，30 条训练、5 条验证。
3. 基础模型评估完成：验证 loss 3.552408，PPL 34.8972。
4. LoRA 微调执行 3 个 epoch，学习率 0.0002，rank 8；训练耗时约 60.91 秒。
5. 微调后评估与生成样例已实际执行，Adapter、metrics.json 和 samples.json 已生成。
6. 最终阶段文档写入失败：代码在赋值 loss_change 之前引用该变量，抛出 UnboundLocalError。因此本次不能标记为完整成功。

## 实测指标

| 指标 | 基础模型 | 微调后 |
|---|---:|---:|
| 验证集 Loss | 3.552408 | 3.424955 |
| 验证集 PPL | 34.8972 | 30.7213 |

验证 Loss 相对下降 3.588%。这只说明当前极小验证集上的预测指标有所改善，不代表模型具备通用能力或安全性。该脚本版本未将训练步数写入 metrics，因此本报告不猜测步数。

## 模型输出质量

生成的 5 条样例均已保存到 samples.json。实际输出包含异常网址片段、乱码式文本，且至少一条为空。**本次微调的生成质量不合格，不能将它作为可用助手发布，也不能宣称已经学会项目原则。**

## 失败原因与修复

根因：scripts/train_gpt2_lora.py 在写入 stage4_evaluation.md 时，先使用 loss_change，后面才给它赋值。已在提交 [b1682cb](https://github.com/mjw3177109/damoxingtest/commit/b1682cb240a7a1508c328694ae1d3c65fa61ac62) 中修复；同时增加训练步数指标、逐步 Trainer 日志、输出目录清理和报告同步重试。

## 项目原则

- 保护用户：保护隐私、数据、账户与合法权益。
- 维护人类：尊重生命、尊严、自由与安全。

这些原则是训练目标，不是模型已通过安全认证的证据。
