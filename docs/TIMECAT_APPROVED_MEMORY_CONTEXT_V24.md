# TimeCat V2.4：已批准记忆的云端权威召回

## 目标

让新进程/新会话只使用当前已登录用户在 TimeCat 专属 Supabase 项目中可读取、状态为 approved 的记忆，并保留每条记忆的来源和 revision。任何认证、网络、冲突或数据校验失败都必须停止，不能静默退回本地缓存。

本阶段的代码交付是检索契约和 CLI 能力，不等于为 ChatGPT 自动化提供了独立用户级 OAuth 授权。2026-10-30 的定时巡检另经用户已连接的 Supabase 管理工具，在唯一专用项目内临时 `SET LOCAL ROLE` 降权读取；这与 CLI 所要求的普通用户 JWT 是两条不同链路，均须逐次以真实返回值验收。

## 新增能力

timecat/mentor_context.py 提供 load_approved_context()：

1. 使用当前用户 JWT 直接向 Supabase 只读获取最新云端记录，不执行本地 outbox 同步或上传。
2. 验证云端读取响应及每条记录的必要字段；认证或网络失败时立即报错。
3. 使用这份新鲜云端响应构造上下文，不读取 SQLite 缓存，也不调用 synchronize()。
4. 校验 ID、分类、内容、来源、状态、revision 和时间戳。
5. 只返回 approved 记录；proposed 与 rejected 永远不进入对话上下文。
6. 按确定性的文本匹配筛选，并输出 id、source、updated_at、revision 供审计。
7. 云端失败时抛出错误，不返回本地记忆作为替代。

## 使用

在本机受保护环境中设置现有 V2 所需的三个环境变量：

- TIMECAT_SUPABASE_URL
- TIMECAT_SUPABASE_PUBLISHABLE_KEY
- TIMECAT_SUPABASE_ACCESS_TOKEN（必须是普通用户的 authenticated JWT）

运行：

~~~powershell
python -m timecat.cloud_cli context "bobo师傅" --limit 10
~~~

该命令输出 JSON 上下文。不要把 JWT、刷新令牌、密码或私人记忆贴进聊天、提交到 GitHub 或写入日志。不得使用 service_role 或管理员 SQL 绕过 RLS。

recall 命令仍是本地 SQLite 检索，只用于离线维护；它不是新会话权威上下文的验收方式。新会话路径应使用 context。

## 关键边界

- 目前 Supabase 客户端仍要求运行环境提供有效用户 access JWT；V2 CLI 尚未实现安全的长期 refresh-token 管理。
- 现有静态网页 PR #79 仍是独立人工登录/管理入口，不会把浏览器会话授权给 ChatGPT。
- ChatGPT 定时巡检已获用户长期授权，允许在专用 Supabase 项目中以 `timecat_v23_reader` 降权读取 approved 记忆，并以 `timecat_v24_candidate_reader` 降权检查 proposed 候选；必须以每次真实 SQL 结果为准，失败则报告失败。管理连接临时切换数据库角色**不是**独立 OAuth/JWT 自动续期网关，不能把此能力归功于本 PR 的 CLI。
- 未来网关必须由师傅主动授权，最小权限访问同一个 TimeCat-Memory 项目；不能混用其他 Supabase 项目，不能使用 service_role。
- 2026-10-30 师傅已授权 TimeCat 在有真实来源、低风险、去敏、防重和最小权限保护的条件下，自主批准或拒绝**普通私人长期记忆**，无需逐条人工批准；无证据或不确定则暂缓。此授权不涵盖敏感信息、外部高影响操作、模型晋级或权限扩张。本 PR 的 `mentor_context.py` 仍只实现 approved 召回，**不包含**自动审核代码；定时巡检的独立治理链路须另行验证。

## V2.4 定时治理与权限边界（2026-10-30 增量说明）

- 已批准召回：`timecat_v23_reader` 只读 approved，数据库 RLS 限制唯一师傅所有权；不能用管理员裸查询替代。
- 候选审查：`timecat_v24_candidate_reader` 只读 proposed；`timecat_v23_proposer` 仅提议 INSERT，`timecat_v23_reviewer` 仅在授权及 RLS 约束下完成 proposed → approved/rejected 状态迁移。不同角色须使用独立事务 `SET LOCAL ROLE`，提交后不能假设角色仍生效。
- 审核标准：真实来源、长期价值、低敏、无重复、符合安全原则；不自动修改历史已批准记录，不保存凭据、私聊全文或第三方私密信息。
- 定时读取已批准记忆与普通记忆自主审核的授权不等于数据库角色可任意扩权；真实候选为空时只能报告“0 条”，不能声称已完成候选编辑或审核的端到端验收。
- 仅允许向公开 GitHub 提交不含私人记忆正文的工程证据；每日反思与周日评审已并入同一个每小时巡检任务，反思不能替代质量门槛或人工模型晋级审批。

## 验收

CPU-only 单测覆盖：

- 第二个独立 SQLite 会话从共享云端恢复 approved 记忆；
- proposed/rejected 不进入上下文；
- 本地缓存被篡改时，输出仍来自新鲜云端快照；
- 云端不可用时 fail closed，不回退本地；
- 查询筛选与条数上限。

这些测试使用隔离 FakeCloud，只能证明程序逻辑，不等于真实 Supabase 项目或 ChatGPT 自动化的端到端验收。

运行：

~~~powershell
python -m compileall -q timecat
python -m unittest discover -s timecat/tests -v
~~~

真实验收仍需在用户授权的 TimeCat-Memory 项目上，通过普通用户 JWT 完成新会话读取，并由独立测试确认 RLS 隔离。
