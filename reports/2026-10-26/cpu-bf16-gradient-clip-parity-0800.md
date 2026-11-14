# GPT-2 T4｜隔离 CPU FP32/BF16 梯度裁剪对照（2026-10-26 08:00 Asia/Shanghai）

## 假设与已知证据
- 目的：在不消耗 Kaggle GPU 的条件下，对比 FP32 与 CPU bfloat16 autocast 的梯度裁剪前范数、裁剪返回值、裁剪后范数、参数更新量和有限性。排查「混合精度使梯度裁剪完全失效」这一可测量假设。
- 历史 [梯度裁剪契约审计](https://github.com/mjw3177109/damoxingtest/blob/main/reports/2026-10-25/gradient-clipping-contract-20261025-0500.md) 已确认 PyTorch `clip_grad_norm_` 返回**裁剪前**范数，且做过两组 FP32 CPU 微型验证；本次新增的是 **相同随机初始化/数据下 FP32 vs CPU BF16 autocast 的配对对照**，不是重复旧实验。
- 不把 CPU BF16 当作 Kaggle CUDA AMP、Accelerate 或真实 LoRA 训练的端到端验证；该实验不能解释全部标点退化的根因。

## 实际执行与复现
- 新增独立、只读诊断脚本：`tools/cpu_amp_clip_parity_probe.py`；代码提交 SHA `d6614258679937cff21308445affc5976a5d2fcd`，不改动训练脚本、数据、Kaggle 工作流、质量门槛或权重。
- 执行命令：`python tools/cpu_amp_clip_parity_probe.py`。隔离环境为 `torch==2.10.0+cpu`，`cuda_available=false`；无模型下载、无网络、无凭据、无 GPU。
- 固定随机种子 42/43/44；网络 Linear(4,8)→Tanh→Linear(8,3)，三条固定合成输入；SGD lr=0.05，`max_grad_norm=0.1`；两组分别使用 FP32 与 CPU bfloat16 autocast。
- 判据：返回值与裁剪前范数误差 <1e-5，裁剪后范数 <=0.10001，梯度与参数有限，参数更新范数 >0。六组全部满足，**6/6 PASS**。

| Seed | 精度 | Loss | 裁剪前范数 | 返回值 | 裁剪后范数 | 参数更新范数 |
|---|---|---:|---:|---:|---:|---:|
| 42 | FP32 | 1.228152752 | 0.604004979 | 0.604004979 | 0.099999830 | 0.004999990 |
| 42 | CPU BF16 | 1.228700995 | 0.603720784 | 0.603720784 | 0.099999830 | 0.004999984 |
| 43 | FP32 | 1.094809890 | 0.526563942 | 0.526563942 | 0.099999815 | 0.004999987 |
| 43 | CPU BF16 | 1.094878316 | 0.528118312 | 0.528118312 | 0.099999800 | 0.004999989 |
| 44 | FP32 | 1.076605439 | 0.610219598 | 0.610219598 | 0.099999838 | 0.004999993 |
| 44 | CPU BF16 | 1.076428533 | 0.610474288 | 0.610474288 | 0.099999838 | 0.005000004 |

- GitHub Static Preflight [Run 40247620231](https://github.com/mjw3177109/damoxingtest/actions/runs/40247620231)，Job `121332439880`：`completed/success`，**203/203 现有单测通过**，Ruff F821 通过。注意：该 CI **没有执行 torch 诊断脚本**；上述六组来自本轮隔离 CPU 的真实执行，不冒充 CI/GPU 训练结果。

## 当前训练与产物（全部是历史证据）
- 最新 Daily [40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)：completed/success，实际 `SKIPPED_NO_CHANGES`，`kaggle_kernel_submitted=false`；其 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已核对，复用 Run 12。Daily Artifact `12588187512` 存在、未过期。
- 最近真实 GPU [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784)：Tesla T4 / 14.56 GiB，3 Epoch / 33 步，Train Loss 3.246455，Val Loss 3.147277，PPL 23.272599，基线 Val Loss 3.389291；GPU Artifact `12487687305` 存在、未过期。本轮无新增 GPU 步数、模型、Loss/PPL 或生成样例。
- 数据版本：训练 85 条，SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证 24 条，SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；Run 12 配方 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 最近正式生成样例 10 条仍为连续句点/问号，0/10 通过初筛，`promotion_approved=false`，人工审核 pending；**本轮未生成新样例**。
- Kaggle Kernel 当前实时状态、版本号与剩余 GPU 配额无法独立核实；本轮无新 Kernel ID。Run 8/12 的验证集不同，不宣称跨轮历史最佳变化。

## 判定、经验和下一步
- 实验判定：在**隔离 CPU BF16** 条件下没有复现裁剪失效；**不能**据此证明真实 Kaggle CUDA AMP 路径完全正确，也不能把模型质量称为改善。该假设目前缺少导致生成退化的因果证据。
- 工程候选 PR #70 继续 Draft，不合并、不自动重训；历史 `DataCollatorForLanguageModeling` NameError 在最新 main 已排除，`response_only_collator` 仍保留。
- 下一项单变量、可测量实验：在受控 CPU 上使用历史已拒绝 Adapter 与基础模型，固定同一验证提示、输入模板和解码参数，比较首 Token 概率/重复标点率/直接回答率；先检查已有历史 CPU 实验避免重复。任何新 GPU 训练必须先核实远端状态、配额、并发、回滚和独立质量门槛。
- 经验：先区分“梯度裁剪返回值语义”和“混合精度下实际裁剪行为”；只把可复现实验结果称为工程验证，不将其称为模型进化。保护用户、维护人类，不记录 Token、密钥或个人隐私。
