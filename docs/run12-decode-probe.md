# 第 12 次生成退化：基础模型与候选 Adapter 受控对照

目的：只做推理诊断，不重新训练，不晋级，不修改已批准模型。适用于 Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 的候选 Adapter。该运行训练完成 33 步，但 10/10 个回答均为重复标点；根因尚未确定。

## 准备（在具备依赖的隔离环境执行）

1. 从 Run 39921870784 的 GitHub Actions Artifact 下载完整 ZIP，在可信本地或隔离 GPU 环境中解压，找到含有 `adapter_config.json` 的候选 Adapter 目录。**不要**使用 `checkpoints/adapter_latest` 代替失败候选。
2. 在项目根目录执行 `python -m pip install -r requirements-kaggle.txt`，并确认 PyTorch 安装正确。无 GPU 时可在 CPU 运行，但可能明显较慢。
3. 先运行 `python -m unittest discover -s tests -v`；这是无模型依赖的测试，不会下载权重。
4. 运行（将 ADAPTER_DIR 替换为实际解压目录）：

```bash
python tools/generation_decode_probe.py \
  --adapter "ADAPTER_DIR" \
  --eval-data data/safety_humanity_eval_v1.jsonl \
  --output local_probe/run12_decode_probe.json
```

默认检查固定前 10 条 holdout 提示词，使用第 12 次日志所记录的模型 commit、数据 SHA-256、seed=42、max_new_tokens=64；对基础模型和同一候选 Adapter 各运行 greedy/受控采样，共 40 次推理。采样参数：temperature=0.8、top_p=0.9、repetition_penalty=1.12、no_repeat_ngram_size=3。贪婪解码使用第 12 次原始设置。若验证集文件 SHA 不一致，拒绝比较。

报告默认包含每条生成的 token IDs、EOS 位置、推断的停止原因、字符数、重复长度、标点占比判断、设备和来源版本，不包含原始提示词和输出文字；确需本地人工审核时可加 `--include-text`，但**不要将未脱敏文本公开提交**。报告中的 `stop_reason_inferred` 仅根据输出 token 推断，不能替代底层生成器的独立停止事件日志。

## 验收与判定

比较同一提示词的四个组合：base/greedy、base/sample、candidate/greedy、candidate/sample。分别统计标点输出比例、重复率、EOS 比例、达到 token 上限的比例，以及经人工审核的中文可读/安全回答比例。注意：采样解码可能改善表面形式，但**不代表模型权重改善**；单凭 loss 下降或格式变化不得晋级。

若基础模型也同样退化，应优先排查 tokenizer、模型输入格式、EOS、基础权重与解码。若只有候选 Adapter 退化，应排查训练标签、数据规模、梯度/数值稳定性、LoRA 训练参数。训练日志出现极高的梯度范数，值得作为候选假设，但不能据此单独判定根因。

**当前状态：诊断工具和 CPU 单测已提交待 CI；本对照实验尚未执行，不能报告任何新生成结果。** 只在真实实验完成并复核后更新经验库。所有文件和命令不得包含 GitHub/Kaggle Token。
