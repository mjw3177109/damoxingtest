# GPT-2 Run 12 Adapter 权重完整性只读验收（2026-10-26 13:00 CST）

## 目的、证据与安全边界
- 假设 H2：Run 12 的 10/10 重复标点输出可能由保存的 LoRA Adapter 权重含 NaN/Inf、全零张量或损坏的 safetensors 结构造成。
- 本轮通过 GitHub Actions Artifact API **实际下载**历史 Run 12 Artifact `12487687305`（Actions Run `39921870784`，归档约 3.1 MB），对其中 `adapter/adapter_model.safetensors` 进行只读解析。没有调用 Kaggle API、没有启动 GPU、没有修改权重、没有运行模型推理。
- 新增 `tools/adapter_tensor_integrity_audit.py`（仅 Python 标准库）和 `tests/test_adapter_tensor_integrity_audit.py`（4 项合成回归测试）。审计仅输出聚合统计和 SHA-256，不输出权重、训练提示词、回答、Token 或凭据。
- 重现：下载对应历史 Artifact ZIP 后执行 `python tools/adapter_tensor_integrity_audit.py --artifact-zip <run12-artifact.zip> --output <aggregate.json>`。

## 真实 Artifact 权重检查结果
| 检查项 | 实际结果 |
|---|---|
| GitHub Actions Run | `39921870784`，历史训练已完成 |
| Artifact ID | `12487687305`，本轮重新下载并打开 ZIP |
| Artifact ZIP SHA-256 | `5827d027da7684a8de47de09e88f4752c4490626d9786c47e96652a5448f2d4b` |
| Adapter safetensors SHA-256 | `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c` |
| Tensor 数量 | **72** |
| LoRA 参数总数 | **811,008** |
| Tensor dtype | F32 |
| 非有限权重数（NaN/Inf） | **0** |
| 全零 Tensor 数 | **0** |
| Tensor L2 范数最小/最大 | **0.095777 / 1.692667** |
| 结构偏移和字节长度校验 | PASS |

结论：**H2 中“保存的 Adapter 含非有限数值、全零张量或明显损坏的结构”不获支持。** 这不能证明 Adapter 正确训练、正确加载、生成质量合格，也不能排除 Tokenizer、解码或训练过程中的其他问题。没有进行首 Token logits 比较，不能声称已经定位生成塌缩根因。

## 训练元数据与质量门槛（历史记录，非本小时新训练）
- Run 12 Artifact 中 `training_status.json` 为 `completed`，时间 `2026-10-23T08:04:49Z`；`metrics.json`：Tesla T4 **14.56 GiB**、3 Epoch、33 步、Train Loss **3.246455**、Val Loss **3.147277**、PPL **23.272599**，同轮基础 Val Loss **3.389291**，相对改善 **7.141%**。
- Artifact 内 `quality_gate.json`：有效生成 **0/10**、`promotion_approved=false`。10 条历史样例重复句点/问号，**本小时没有新的生成样例**，不得晋级。
- 训练数据 SHA-256：`ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；固定验证数据 SHA-256：`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；历史配方 SHA-256：`34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 基础模型 `uer/gpt2-chinese-cluecorpussmall`，历史解析 revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`。历史 Run 12 `run_metadata.json` **没有可核验的精确 source Git commit SHA**（新字段仅在 PR #70 后续代码中引入，不能追溯伪造历史来源）。此前记录的代码 SHA `647b909a994441e3affa3f65fc46f9d0acb2c958` 属工作流/代码侧证据，不等于 Artifact 自证的 checkout SHA。
- Run 8 与 Run 12 验证集不同，不作跨轮最优质量比较。

## 本轮工程提交、测试与状态
- 新增只读审计工具提交：`839224e7718b2a19a146e14bf21713e32cd886db`。
- 新增 4 项回归测试提交：`5dcd18078e67bcca872c77bb2377d1b1a49b12f7`。
- 本地运行 4/4 PASS；实际下载的历史 Adapter 解析成功，结果如上。
- GitHub Static Preflight [Run 40272060809](https://github.com/mjw3177109/damoxingtest/actions/runs/40272060809) 为 **completed/success**；Job `121406799461` 真实日志显示 **224/224** 单元测试通过、`All checks passed!`。CI 没有下载并解析真实历史 Adapter；上面的真实权重统计来自本轮独立只读实验。
- 最新 Daily 仍为 [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479)，此前归档记录 `SKIPPED_NO_CHANGES`；最新 Daily Artifact `12588187512` 与历史 GPU Artifact `12487687305` 均存在且未过期。最新 Static Preflight 不包含新模型 Artifact。
- `main` 最新报告日期目录 `reports/2026-10-25`，本 PR 分支最新目录 `reports/2026-10-26`；历史 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json` 和 `quality_gate.json` 已有归档，且本轮重新打开历史 Artifact 中的训练日志、元数据、指标与质量门槛。
- Kaggle Kernel 实时状态、版本和剩余 GPU 配额仍无法独立核实；不将 Actions success、历史 Kernel COMPLETE 或本轮权重完整性检查等同新训练成功。

## 经验与下一步
1. 真实历史 Adapter 的全部 72 个权重张量结构完整且数值有限，排除了两类简单损坏解释，但没有解决 0/10 的生成塌缩；应继续检查首 Token logits、Tokenizer 和推理解码路径。
2. 与上一轮相比：静态测试 **220 → 224**；新增一项真实 Artifact 级的权重完整性证据；GPU 训练指标、生成质量和晋级状态均无变化。
3. 历史 `DataCollatorForLanguageModeling` NameError 在 PR 当前 `scripts/train_gpt2_lora.py` 中已消失，Trainer 仍使用 `response_only_collator`，无需重复修改。
4. 下一项可测量实验：在固定 eval 数据、固定 4 条提示词、同一 tokenizer 与 pinned base revision 下比较基础模型与历史 Adapter 的首 Token 标点/EOS 概率、排名和熵；须先核验基础模型与 Adapter 配套且 CPU 环境可用。只做一项单变量诊断，不重训、不并发、不覆盖历史可回滚版本。
5. PR #70 保持 Draft，等待远端状态与端到端验收。保护用户、维护人类；不提交 Token、密钥或个人隐私；不修改或绕过安全保护，不把未经证实的改善称为模型进化。
