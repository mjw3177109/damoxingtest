# Daily GPT-2 T4 Training 调度延迟审计与最小配置实验

- 巡检时间：2026-10-27 11:56 CST（03:56 UTC），以本轮 GitHub API 查询为准。
- 变更目标：仅调整 `.github/workflows/daily-gpt2-training.yml` 的 schedule 触发分钟，从 `0 1 * * *` 改为 `17 1 * * *`（北京时间 09:17）。
- 假设：GitHub Actions 在整点高负载时更容易延迟；避开整点可能降低调度延迟。**尚未验证效果，不能保证准点。**
- 来源：GitHub Actions schedule 官方文档指出整点可能高负载，部分任务可能延迟或被丢弃；建议改为非整点。https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## 真实调度基线

以下仅统计 event=schedule 的 Daily GPT-2 T4 Training Run。预期时间均为当天 09:00 CST（01:00 UTC），实际创建时间来自 GitHub Actions API。

| 日期 CST | Run ID | 实际开始 CST | 相对 09:00 延迟 |
|---|---|---|---|
| 2026-10-23 | 39906737838 | 13:36:58 | 4h36m58s |
| 2026-10-24 | 40065584092 | 13:16:06 | 4h16m06s |
| 2026-10-25 | 40165941479 | 13:33:02 | 4h33m02s |
| 2026-10-26 | 40275426137 | 13:39:48 | 4h39m48s |
| 2026-10-27 | 尚无已确认 Run | 截至 11:56 尚未出现 | 至少 2h56m（仍可能迟到） |

前四次完成触发的平均延迟约 4h31m29s。10 月 27 日记录为观察中，不能称为确定丢失。

## 改动范围与安全检查

- 仅变更 cron 一行，GitHub Connector 更新前后逐字反向校验其余内容不变。
- 每日触发次数保持 1 次；保留 `workflow_dispatch`、`push` 过滤、`concurrency: daily-gpt2-training-canonical-kernel`、`cancel-in-progress: false`、`pre_submit_reuse_guard.py`、Kaggle 状态预检和质量门槛。
- 不更改模型、数据、训练超参数、凭据、GPU 提交路径或晋级机制。
- 修改仅在独立 PR 分支，**main 尚未改变；未启动 GPU 训练**。合并前须通过静态 CI 和人工审阅。
- 静态变更验证：原 cron 精确匹配一次；替换后可完整还原原文件，除该行外无改动。PR CI 结果待核实。

## 真实训练与 Artifact 基线

- 最新 Daily [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137) completed/success，但 `training_status.json` 明确 `skipped_no_changes=true`、`kaggle_kernel_submitted=false`；并无本轮训练。Artifact `12629319793` 存在且未过期。
- 最近真实 GPU [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) 已结束：Tesla T4、14.56 GiB、3 epochs、33 steps、Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599。GPU Artifact `12487687305` 存在。
- 最新 CPU EOS 审计 [40417564007](https://github.com/mjw3177109/damoxingtest/actions/runs/40417564007) 已结束，Artifact `12696138797` 存在；109/109 EOS 标签监督正确，未进行新生成。
- 最近静态 CI [40417706449](https://github.com/mjw3177109/damoxingtest/actions/runs/40417706449) completed/success，290/290 tests。
- main 最新报告目录：`reports/2026-10-26/run-40275426137`。已核实 `training.log`、`metrics.json`、`samples.json`、`report.md`、`run_metadata.json`、`training_status.json`、`quality_gate.json`；`promotion_approved=false`，历史有效样例 0/10。
- 训练集 SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`；验证集 SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`；训练方案 SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`。
- Kaggle Kernel 实时状态、剩余 GPU 配额及仓库外并发未能独立核实。**不触发第 13 次训练。**

## 实验验收与回滚

- 先审阅并合并独立 PR（不与 PR #70 的模型实验混合），再观察至少 7 次 event=schedule 的真实触发时间。
- 以新预期时间 09:17 CST 计算每次延迟；记录触发缺失率、延迟中位数和最大值；与旧 09:00 基线分别对齐，避免混淆目标时刻变化与实际延迟改善。
- 若触发仍严重延迟、出现重复任务或安全检查失败，回滚单行 cron 至 `0 1 * * *`。任何晚到运行仍须通过现有并发与复用守卫。
- 不将 cron 改动称为已解决调度问题；不将 Actions success 或 Kernel COMPLETE 等同模型训练成功。
- 训练质量问题仍为独立阻塞：严格输入 CPU 实验发现 2/10 疑似短答，语义/安全审核未完成，候选模型不晋级。
- 经验：整点调度是可测量的潜在延迟因素；修复须以未来真实 Run 证据验收，且与 GPU 训练质量及隐私边界严格隔离。
