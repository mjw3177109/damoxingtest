# 每日 GPT-2 训练运行报告

- 生成时间（UTC）： 2026-10-22T08:24:47.880567+00:00
- 运行目录： /home/runner/work/damoxingtest/damoxingtest/reports/2026-10-22/run-39747465436
- GitHub Actions 运行记录： https://github.com/mjw3177109/damoxingtest/actions/runs/39747465436
- 模型与完整输出 Artifact： https://github.com/mjw3177109/damoxingtest/actions/runs/39747465436/artifacts
- Kaggle 任务状态： COMPLETE
- 最终判定： **TRAINING_FAILED**

## 本次结果

- 基础模型： uer/gpt2-chinese-cluecorpussmall
- GPU： Tesla T4
- 显存（GiB）： 14.56
- 训练样本： 30
- 验证样本： 5
- 基线验证 loss： 3.55241
- 微调后验证 loss： 3.42495
- 基线 PPL： 34.89723
- 微调后 PPL： 30.72125
- 验证 loss 相对改善（%）： 3.588
- 训练耗时（秒）： 60.91

## 整体评价

本次验证集 loss 在当前小规模保留集上下降，说明该指标有改善迹象。由于语料和验证集规模很小，这不是通用能力提升或安全性的证明；仍需审查生成样例、过拟合和数据质量。

## 阶段记录

- stages/stage0_environment.md
- stages/stage1_data_prep.md
- stages/stage2_base_evaluation.md
- stages/stage3_lora_training.md

## 模型输出与日志

- 已保存生成样例： samples.json（5 条）
- 已保存： training.log
- 已保存： metrics.json
- 已保存： run_metadata.json
- 已保存： training_status.json

## 安全与质量边界

- 自动生成的回答都需要人工审核；本报告不是安全认证。
- 小数据集上的 loss 和 PPL 不能证明事实准确性、通用推理能力或价值观稳定性。
- 不将失败、超时、未配置凭据或缺失指标描述为成功。
- 本项目原则仍为：保护用户；维护人类。

## 下一步计划

1. 根据 status.txt、Kaggle 日志和训练日志定位阻塞原因。
2. 修复凭据、GPU 配额、网络或训练问题后，再进行新的真实运行。
3. 只有指标文件、样例输出和报告齐全时才判定训练成功。
