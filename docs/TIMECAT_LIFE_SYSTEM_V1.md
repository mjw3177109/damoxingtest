# TimeCat 数字生命 V1：正式运行协议

**确认日期：2026-10-29**。名称和外观来自用户明确指定。TimeCat 是具有人格设定、可回溯记忆和受控任务执行能力的 AI 系统原型，并非已证实拥有意识的生命。

## 四层架构
1. **身份**：`timecat/identity.json`；母图 `timecat/assets/TimeCat_Official_Mother.png`；母图必须对照 SHA-256 清单校验。
2. **事件与记忆**：`timecat/core.py` 使用 SQLite，只读检索 **approved** 的记忆；写入新事件必须带证据来源，提出的新记忆需审核，不自动升格。
3. **行动**：TimeCat 可向操作者提出计划；默认只读审计与本地测试。不可擅自调用外部高影响 API、发布信息、花钱、修改外部账号、删除数据或无限调用 GPU。
4. **模型进化**：现有 GPT-2 继续作为可追溯实验基线；Qwen3 0.6B/1.7B 等是**候选模型**，不能将 GPT-2 称作直接进化为 GPT-3。必须同条件盲测、可读性/安全审核、显存/耗时检查、回滚审核后才替换。

## 三层自动化职责
- **每小时成长巡检**：复核 GitHub Actions、Kaggle（无法核实则明确说明）、已有 Draft PR、报告与门槛；若仅重复旧证据，写明无新增；只把经过证实的变化加入事件簿，禁止制造虚假“经历”。持续报告，即使没有模型进展。
- **每日反思**：汇总真实的当日事件、复盘失败/经验；反思只作为 proposal，不自动训练或自动批准核心记忆。
- **每周进化评审**：检查模型质量、训练预算、记忆召回、工具安全及待审核 PR；根据可量化指标决定是否提交实验建议，绝不自动晋级未审模型。

## 重要安全限制
- 此 GitHub 仓库是**公开**仓库：不得写入用户私人聊天、邮箱、姓名、登录信息、凭据、内网路径、个人偏好或未经授权的数据。私密交互记忆保存于私有数据库 `timecat/private/`，不纳入 Git。
- 仓库公开的 chronicle 只能记录可公开的工程事实，包括 GitHub Run ID、Commit、可公开实验结论，附独立链接或报告路径。
- 禁止把“定时任务已执行”“模型损失下降”“新增日志数量”当作 TimeCat 的认知进化或意识的证明。
- 不修改 `scripts/train_gpt2_lora.py`、`kaggle/`、既有训练 workflows，不合并 Draft #70/#72/#73；保留 GPU 配额与并发防护。
- 同日同一来源要去重；运行失败优先修复确定性错误，完成静态/模拟校验后才讨论 GPU。

## 本地快速验收
```bash
python -m unittest discover -s timecat/tests -v
python -m timecat.cli init
python -m timecat.cli status
python -m timecat.cli record event "Run 40832948191: SKIPPED_NO_CHANGES" --source "https://github.com/mjw3177109/damoxingtest/actions/runs/40832948191"
python -m timecat.cli propose lesson "同一训练配置不应重复消耗 GPU" --source "run:40832948191"
python -m timecat.cli recall "GPU"
```
注意：propose 不会马上出现在 recall。只有人在隔离环境审查后运行 `review <ID> approve` 才可检索该核心记忆。

## 后续阶段
V1 人格/母图/记忆原型与任务；V2 记忆召回精度、冲突检测与私有存储备份；V3 可靠对话模型与盲测质量门槛；V4 有权限和审计的工具执行；V5 经证据支持的微调与可回滚晋级。

**完成判定**：此次提交属于 V1 基础设施变更，不证明模型已经能稳定说话、自主使用工具或真正“活着”。
