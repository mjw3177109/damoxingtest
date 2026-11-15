# Kaggle 初始状态混合错误优先级审计（2026-10-29 CST）

## 假设与根因

PR #72 先前已保护 Kaggle 轮询阶段的混合 `COMPLETE + 429` 响应，但首次 `kaggle kernels status` 的解析仍先进入 `STATUS_CODE=0` 分支，并优先匹配 `COMPLETE`。如果 CLI 退出码为 0，同时输出 `KernelWorkerStatus.COMPLETE` 与 `403 Forbidden` 或 `429 Too Many Requests`，旧逻辑可能设置 `NEED_PUSH=true`，错误调用 `kaggle kernels push`。这是离线代码审查确认的潜在控制流风险，不是已观察到的 Kaggle 线上事故。

## 最小修复及测试

- 修复提交：`fd90c7d0e6578e05b80f40b3a14d640af32b7a6a`；随后恢复 Shell 正则完整性：`cb28cfa766185c38b25e74e75f23044c00910148`。
- 测试提交：`219820f09828b6c545df2a4fa4e211f0e74656e5`，测试字符串换行修正：`cd43baff7ff9212219b10dea75c6d05ace2da562`。
- 初始状态现在**无条件先判断 401/403/429、Forbidden、Unauthorized、rate limit**，再考虑 `COMPLETE`、活跃状态或首次 404 创建；异常返回 `KAGGLE_STATUS_FAILED`，拒绝 GPU 提交。
- `tests/test_kaggle_terminal_retry_execution.py` 增加两种退出码为 0 的混合响应模拟：`COMPLETE + 403` 与 `COMPLETE + 429`；要求没有 `kaggle kernels push`，也不生成伪训练结果。测试使用本地假 Kaggle CLI，不调用网络/GPU。

## 验证与失败教训

- 中间静态 CI `40741464969`、`40741480360`、`40741512666`：**失败**。原因是文本替换时 Shell 正则中的 `$'` 被替换器解释为特殊后缀引用，截断引号并引发 `bash: -c: line 24: syntax error near unexpected token '('`。这些失败是工程 CI 失败，不是 Kaggle 训练失败。
- 修复后 CI [40741578709](https://github.com/mjw3177109/damoxingtest/actions/runs/40741578709)：**completed / success**；Job `123004277920` 原始日志确认 `Ran 198 tests`、`OK`、Ruff `All checks passed!`，Response-only Collator 和 `-100` 标签掩码 PASS。总测试数仍为 198，新增的是现有测试中的子用例。
- 经验：修改含 `$'` 的 Shell 片段时必须使用字面量安全的替换方式；先做 `bash -n` 或等效语法检查，再执行模拟测试。异常状态必须优先于看似成功的状态标志。

## 训练/数据对照与安全边界

- 生产主分支检查时 SHA：`361fa9ca36528eea70a7fea2d606c1bab50e24b8`，**未修改**。PR #72/#73 保持 Draft，未合并。
- 最近正式 Daily Run `40457573324`：`SKIPPED_NO_CHANGES`，没有 Kaggle 提交。历史 GPU Run `39921870784` 已结束，使用 Tesla T4 14.56 GiB、33 步、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599；这些指标不是本轮测量。
- 训练配置（历史）：`uer/gpt2-chinese-cluecorpussmall`、LoRA r=8、学习率 0.0002、3 epochs、seed 42、max_length 256；训练数据 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证数据 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`。
- 本轮没有新训练、模型生成、指标或 Kaggle Kernel ID。远端实时 Kernel 状态、配额和并发仍无法独立核实。历史有效样例 0/10，人工审核 pending，`promotion_approved=false`。
- 与上一轮比较：工程防重复 GPU 提交覆盖范围增加；模型指标无变化且无可比的新数据。没有证据支持模型晋级或“自我进化”。
- 下一步：保持 Draft，独立检查生产合并差异与 Kaggle 远端状态/配额；先做固定 Run 12 权重的 CPU 配对推理评估，再决定是否允许受控 GPU 实验。保留可回滚历史最佳版本，不修改或绕过安全门槛，不提交凭据/隐私。
