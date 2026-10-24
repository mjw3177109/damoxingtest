# Run 12 梯度裁剪返回值语义验证（2026-10-25 05 时档，北京时间）

## 结论与范围
- **本轮新增的是代码路径核查 + 2 组隔离 CPU 微型实验；没有运行 Kaggle、没有 GPU 训练、没有生成新模型，也没有改动生产训练代码。**
- 在仓库固定的 `transformers==4.46.3`、`accelerate==1.1.1` 普通单机 Trainer 路径中，日志记录的 `grad_norm` 取自 `clip_grad_norm_` 的**返回值**。该返回值是**裁剪前的梯度总范数**，并不是裁剪后的梯度范数。
- 因此历史 Run 12 的 7/7 条 `grad_norm > max_grad_norm=1.0` **不能认定为裁剪失效**。这消除了上一轮“数值大就代表裁剪失败”的疑点，但**尚未独立验证历史 Kaggle GPU 每次实际裁剪后的梯度或 AMP 更新**；不能将模型重复句点、UNK 归咎于此，也不能据此认定模型改善。

## 可核实的版本与源码路径
- 代码基线 main SHA：`fa1589e7320a7d5e6e82b2db1dd078fd2490289a`。
- 仓库 `requirements-kaggle.txt` 锁定 `transformers==4.46.3`、`accelerate==1.1.1`；Notebook 通过该 requirements 安装。
- Transformers v4.46.3 `src/transformers/trainer.py` 第 2499–2534 行：普通路径在 optimizer.step() 前调用 `self.accelerator.clip_grad_norm_(model.parameters(), args.max_grad_norm)`，将返回值赋给 `grad_norm`。特殊分布式/DeepSpeed 路径需另行核对，不能直接套用本结论。
  - 源码： https://github.com/huggingface/transformers/blob/v4.46.3/src/transformers/trainer.py#L2499-L2534
- Accelerate v1.1.1 `src/accelerate/accelerator.py` 第 2391–2392 行：普通路径先 `unscale_gradients()`，然后直接返回 `torch.nn.utils.clip_grad_norm_(...)`。
  - 源码： https://github.com/huggingface/accelerate/blob/v1.1.1/src/accelerate/accelerator.py#L2391-L2392
- PyTorch 官方 API `clip_grad_norm_` 返回裁剪前的总范数；函数在原地裁剪梯度。
  - 说明： https://docs.pytorch.org/docs/stable/generated/torch.nn.utils.clip_grad_norm_.html

## 本轮 CPU 实验：两个受控样例，均通过断言
环境：隔离 CPU，`torch==2.10.0+cpu`（**不是**历史 Kaggle 的 `torch==2.11.0+cu128`，不能当成对 Kaggle AMP 的端到端验证）；参数向量初始值 `[2.0, -1.0]`，SGD `lr=0.1`，梯度来自 `loss=(parameter * scale).sum()`，裁剪阈值 `1.0`。每组断言：返回值约等于裁剪前范数；裁剪后范数不大于 1；optimizer.step() 发生非零更新。

| scale | 裁剪前范数 | 函数返回值 | 裁剪后范数 | 参数更新范数 | 断言 |
|---:|---:|---:|---:|---:|---|
| 1000.0 | 1414.213623 | 1414.213623 | 0.999999881 | 0.099999972 | PASS |
| 0.01 | 0.014142135 | 0.014142135 | 0.014142135 | 0.001414280 | PASS |

**可复现的最小 CPU 验证：**
```python
import torch
for scale in (1000.0, 0.01):
    p = torch.nn.Parameter(torch.tensor([2., -1.]))
    opt = torch.optim.SGD([p], lr=0.1)
    (p * scale).sum().backward()
    before = torch.linalg.vector_norm(p.grad).item()
    returned = torch.nn.utils.clip_grad_norm_([p], 1.0).item()
    after = torch.linalg.vector_norm(p.grad).item()
    old = p.detach().clone()
    opt.step()
    assert abs(returned - before) < 1e-3 and after <= 1.00001
    assert not torch.equal(p.detach(), old)
```

## 历史训练、报告、质量门槛与本轮对照
- 历史 GPU：Actions Run `39921870784`，Tesla T4 / 14.56 GiB，3 Epoch / 33 有效步，Train Loss `3.246455`，Val Loss `3.147277`，PPL `23.272599`；固定质量门槛 0/10，`promotion_approved=false`。
- 历史训练数据 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`（85 条）；验证集 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`（24 条）。
- 最近 Daily Run `40065584092`：`SKIPPED_NO_CHANGES`，`training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 均在 `reports/2026-10-24/run-40065584092/`；指标来自历史 Run 12，不是新训练。该旧报告的 `LoRA adapter files missing` 属于已修复但**尚未经下次真实 Daily 端到端验证**的误报。
- 最近 Static Preflight Run `40127696933`：`completed/success`、138/138 测试通过（**上一轮结果，不冒充本轮新增 CI**）。
- 历史 GPU Artifact ID `12487687305`、Daily Artifact ID `12549545432` 均存在且未过期；本轮未生成新 Actions Artifact。
- 第 8 次与第 12 次的验证集不一致，不能做同口径历史最优排名；保留已批准版本。
- 最近正式生成样例仍含连续句点；**本轮没有新生成文本**。本轮只修正对梯度日志的解释，不等于模型晋级。

## 可审计经验与下一步
1. **修正假设**：大 `grad_norm` 并不直接代表梯度裁剪失效；先检查返回值语义、混合精度 unscale 与 optimizer.step 顺序。当前没有确定的训练代码缺陷，因此不做无依据的参数/架构改造，也不重复消耗 T4。
2. **下一次唯一受控实验建议**：优先检查 response-only `labels=-100`、EOS、Tokenizer 和 `用户：...\n助手：...` 分隔符是否与推理提示词一致；以固定样本的有效监督 Token 数、掩码比例和完整生成正确率为指标，先 CPU 静态验证。若确有确定性缺陷，再做最小修复、单测、模拟验证；通过后才考虑新的 GPU 训练。
3. 不提交 Token、凭据、个人信息；不绕过安全质量门槛；没有新增 Train Loss / Val Loss / PPL、没有新 Kernel ID，也没有模型晋级。
