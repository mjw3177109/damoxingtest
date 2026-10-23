# Run 12 八步 Token 审计：输入一致性事故记录（2026-10-24）

## 证据与范围
- 首次八步 CPU 审计：Actions Run [39983543880](https://github.com/mjw3177109/damoxingtest/actions/runs/39983543880)，Artifact `12513664665`，PR #11，主分支提交 `0089de1f489d927161daecd192565a282ac7f8fc`。
- 历史首 Token 对照：Actions Run [39975111441](https://github.com/mjw3177109/damoxingtest/actions/runs/39975111441)，Artifact `12511430496`，固定验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 原始训练 Run `39921870784`，候选 Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`。训练状态与历史指标不受本次诊断变更影响。

## 发现的问题
首次八步审计的模型前向调用只传 `input_ids`，遗漏了 Tokenizer 提供的 `token_type_ids` 和 `attention_mask`。先前首 Token 审计使用 `model(**inputs)`，包含完整 Tokenizer 输入，因此两次实验**并非同一输入条件**。实际第一步预测已经不一致：
- 历史基础模型前四条处理后首 Token ID：`[119, 8601, 119, 8601]`。
- 首次八步审计基础模型前四条首 Token ID：`[2769, 8021, 2458, 8021]`。
- 历史候选模型前四条首 Token ID：`[119, 119, 119, 119]`。
- 首次八步审计候选模型前四条首 Token ID：`[119, 119, 1141, 100]`。

**结论：首次八步审计 Run 39983543880 的后续条件概率及重复率不具备与历史审计同口径的可比性，必须标记为无效证据；不能据此判断模型退化原因，更不能晋级。**

## 最小修复与验证
- 在每步完整上下文前向时保留 `attention_mask`，并按照生成流程将最后一个提示 Token 的 `token_type_ids` 延伸到新生成 Token。
- 增加纯 CPU 单元测试，验证 Token 类型延伸与异常边界。
- 新增**第一步一致性门槛**：基础模型和候选模型在四条固定提示词上的第一步 Token ID 必须分别匹配上面的历史序列，否则整个诊断失败，不生成可接受报告。
- 本地已通过 Python 编译与 6 项离线测试；完整模型端到端一致性必须等待修复后 GitHub Actions 真实运行结果，不能预先宣称成功。
- 无新 GPU 训练，不改变模型、训练配方、训练数据，不写入凭据和原始提示词。

## 经验与下一步
比较条件概率时，必须锁定 **Token IDs、attention_mask、token_type_ids、Tokenizer、模型 revision、Adapter SHA、解码处理器及提示词 SHA**。工具通过 CI、Artifact 存在不等于实验条件正确。待修复工作流完成并通过第一步一致性门槛，再审计前八步结果，随后才决定是否设计单变量训练实验。保留历史最佳，不晋级当前候选。
