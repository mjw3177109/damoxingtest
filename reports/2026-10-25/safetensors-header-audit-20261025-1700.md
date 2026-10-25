# GPT-2 每小时工程审计｜Safetensors 头部真实性检查（2026-10-25 17:00 Asia/Shanghai）

## 发现、假设与最小修复
- 基线 main SHA：`f8994a6bccfe0c573a645f9da601245137f5818d`；工作分支 `audit/safetensors-header-20261025-17`；验证通过的代码 SHA：`88727a5ca10f6880600820d13d3ed5e8da463014`。
- 已确定的审计缺口：原 `tools/audit_adapter_artifact.py` 仅检查 ZIP、配置 JSON、基础模型 ID、非空权重及哈希；即使 `adapter_model.safetensors` 是随意字节，也可能标为 `candidate_recoverable=true`。这是归档真实性判断的假阳性，**不是** GPU 训练错误。
- 最小修复：在现有只读工具中增加有界 safetensors 头部解析，最大头部 8 MiB；核查 JSON、tensor dtype/shape、data_offsets 的范围、连续性和字节长度；失败时拒绝标记可恢复候选。只更新 `tools/audit_adapter_artifact.py`、两个合成测试夹具、新增 `tests/test_safetensors_header_audit.py`，不修改生产训练脚本、数据、质量门槛或权重。
- 严格边界：不解压文件、不加载张量或执行模型、不访问 GPU/Kaggle、不回显敏感路径；`approval_verified=false` 保持不变。通过头部检查 **不等于** PEFT 真实加载成功、模型质量合格、正式批准或可持久回滚。

## 失败定位、修复与测试证据
- 首次 PR #67 CI [Run 40178810700](https://github.com/mjw3177109/damoxingtest/actions/runs/40178810700) completed/failure：168 项测试中 1 项失败。根因是旧测试 `test_complete_candidate_is_not_approved` 仍使用任意字节 `b"test-weights"`，与新增真实头部校验不兼容；这不是训练故障。
- 将旧测试夹具改为最小合法 safetensors，并保留其他断言；未回退严格检查。修复提交 `88727a5ca10f6880600820d13d3ed5e8da463014`。
- 第二次 [Static Preflight Run 40178852053](https://github.com/mjw3177109/damoxingtest/actions/runs/40178852053) completed/success，Job 121125358722 真实日志：**168/168 单元测试通过**、Ruff F821 通过、response-only collator 与 -100 masking 通过。新增 8 项离线头部检查测试。隔离本地测试为 20/20 通过，Python 编译通过。
- 历史 NameError：最新 main `scripts/train_gpt2_lora.py` 不含 `DataCollatorForLanguageModeling`，Trainer 仍使用 `response_only_collator`；不重复修复。

## 两份真实 Artifact 的新增只读验证
- 从 GitHub Actions 实际下载历史 Run 12 Artifact `12487687305` 和历史 Run 8 Artifact `12415142300`，在隔离环境运行同一新版审计工具，指定 `--expected-base-model uer/gpt2-chinese-cluecorpussmall`。
- Run 12：`archive_integrity=passed`、`base_model_check=matched`、`safetensors_header_check=passed`、**72 个 tensor**、3,253,104 bytes、权重 SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`；`approval_verified=false`。
- Run 8：相同检查均通过、**72 个 tensor**、3,253,104 bytes、权重 SHA-256 `193662ceb27b530e400e97a234492999acc9c395e9d7eddcec470b8266cade1a`；`approval_verified=false`。
- 两份历史候选通过新的文件格式结构检查，但尚未做真正的 CPU PEFT 加载、基础模型/Tokenizer 运行兼容性或持久回滚测试。

## Actions、Kaggle、训练和质量证据
- 最新 Daily [Run 40165941479](https://github.com/mjw3177109/damoxingtest/actions/runs/40165941479) completed/success，但 `training_status.json` 明确 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；本小时没有 GPU 提交、训练或新生成。最新 Daily Artifact `12588187512` 已核实存在且未过期。
- 最近真实 GPU 训练 [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束。历史 Tesla T4 / 14.56 GiB、3 epochs、33 steps、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；同轮基线 Val Loss 3.389291，改善 7.141%。学习率 0.0002、LoRA rank 8、seed 42、max_length 256、train 85 / eval 24。
- 数据版本 SHA-256：train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；eval `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；配方 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- 最新 `reports/2026-10-25/run-40165941479` 中 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json` 已核实存在；所有 Loss/样例是历史复用。代表性输出为 64 个句点，质量门槛 **0/10**，`promotion_approved=false`。
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` 实时状态与剩余 GPU 配额未能独立核实。不能把历史 COMPLETE 或 Actions success 视为训练成功。
- 与上一轮比较：新增真实文件格式校验、8 项回归测试、两份真实历史 ZIP 的 72-tensor 检查；GPU 步数、Loss/PPL、生成质量和晋级均**没有新结果**。Run 8/12 的验证集不同，无法据此确定历史最佳。

## 经验、晋级决定与下一步
- 经验：文件扩展名、ZIP CRC、非空文件和哈希均不能证明权重格式有效；应先验证 safetensors 头部与数据布局，再进行隔离 CPU 实际加载。CI 首次失败必须查日志并修正测试夹具，而非放宽检查。
- PR #67 的代码通过 CI 和两份真实历史 Artifact 结构验证；该 PR 仅涉及离线审计，不触发 Daily GPU 路径。**模型不晋级**；不得把格式检查当作模型能力进化。
- 下一步：隔离 CPU 环境验证真实 Adapter 与固定基础模型、Tokenizer 的加载及一条非敏感推理；检查 PR #60 推理输入协议与 PR #62 独立验证集的 Draft 风险；确认 Kaggle 空闲、配额和可回滚批准版本前，不启动第 13 次训练。
- 安全：保护用户、维护人类，最小权限，不记录 Token/密钥或隐私，不绕过安全保护，不覆盖已批准模型，不进行并发或无限重试。
