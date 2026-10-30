# TimeCat V2.4：已批准记忆的云端权威召回

## 目标

让新进程/新会话只使用当前已登录用户在 TimeCat 专属 Supabase 项目中可读取、状态为 approved 的记忆，并保留每条记忆的来源和 revision。任何认证、网络、冲突或数据校验失败都必须停止，不能静默退回本地缓存。

本阶段是检索契约和 CLI 能力，不代表 ChatGPT 自动化已经取得云端授权。

## 新增能力

timecat/mentor_context.py 提供 load_approved_context()：

1. 使用用户 JWT 执行现有 V2 同步，推送本地 outbox 并拉取云端状态。
2. 要求同步结果明确返回 cloud_confirmed=true。
3. 再次读取 Supabase 云端记录，使用这份新鲜响应构造上下文，而不是使用 SQLite 缓存。
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
- ChatGPT 每日/每小时任务仍未连接专用授权网关或用户授权连接器，因此本次代码不能声称 ChatGPT 已经自动读取云端记忆。
- 未来网关必须由师傅主动授权，最小权限访问同一个 TimeCat-Memory 项目；不能混用其他 Supabase 项目，不能使用 service_role。
- 所有记忆内容仍由师傅明确确认后形成 proposal，再由师傅审核为 approved；本功能没有自动批准机制。

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
