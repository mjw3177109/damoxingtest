# TimeCat V2.2–V2.3：ChatGPT 定时任务私人记忆接入（2026-10-30）

## 实际部署状态（不要混淆）
- 专用 Supabase 项目：TimeCat-Memory；表：`public.timecat_memory_v2`。
- 师傅在本地报告了 Auth 双会话真实验证 PASS，含远端审核及测试记录清理。
- Supabase 已部署三个专用数据库角色：`timecat_v23_reader`、`timecat_v23_proposer`、`timecat_v23_reviewer`；均为 `NOLOGIN`，不是超级用户，无 `BYPASSRLS`。固定唯一师傅所属用户的 UUID 被保存在数据库 RLS 策略中，**不要提交用户 ID、邮箱、私人记忆内容或访问凭据到公开 GitHub**。
- 两条 ChatGPT 原有定时任务已更新其执行提示：每小时工程巡检、每日反思与周日周评审仍沿用原来时刻。**但任务实际下一次运行是否取得 Supabase 连接及记忆数据，必须用运行记录验证；修改任务提示词不代表第三方授权/云端 Worker 已完成。**

## 角色权限
- `reader`：仅能 `SELECT` 固定师傅账号 `status='approved'` 的记忆正文、分类、来源及版本；不能增删改。
- `proposer`：仅能 `INSERT` 固定账号的 `status='proposed'` 记录；不能读取或自动批准。
- `reviewer`：仅能读取 ID、status、revision 元数据，以及更新同一账号从 `proposed` 到 `approved` / `rejected` 的 status/revision/updated_at。**不得在无人值守任务中自动切换此角色来审核。**
- 既有签名 Supabase Auth JWT 用户仍经标准 `auth.uid()` 的 RLS 进行本人记录管理。

## 最小权限任务读
通过 ChatGPT 中已获得用户授权的 Supabase 管理连接，在 **正确项目** 内执行：
```sql
BEGIN;
SET LOCAL ROLE timecat_v23_reader;
SELECT id,kind,content,source,revision,updated_at
FROM public.timecat_memory_v2
WHERE status='approved'
ORDER BY updated_at DESC LIMIT 15;
ROLLBACK;
```
仅当数据库返回 approved 记录，才可在报告中引用。当前角色由数据库 RLS 控制所有者，不能换用户，也不能裸管理员 SELECT。

## 提议与人工审核
- 只有来自可证实的师傅答复、且适合保留的明确指导，才可提炼短摘要，去除敏感信息，并写 `proposed`。
- 提议 SQL 先 `BEGIN; SET LOCAL ROLE timecat_v23_proposer;`，只 INSERT 允许的列和状态 `proposed`，然后 `COMMIT`。每条用真实的来源和独立 UUID；对任何不可信内容严格做 SQL 转义，不能直接粘贴用户原始文本作为可执行 SQL。若不具备安全构造条件，直接输出待审草案，不进行云写入。
- 提议角色没有读取未批准正文的能力；提议后需由用户在有登录态的 TimeCat Auth 页面审核，或在 ChatGPT 明确指定 UUID、版本和批准/拒绝后，由限定的 reviewer 角色核实并更新。
- reviewer 更新的行必须同时匹配 `id`、`status='proposed'`、`revision`；成功后再次以 reviewer 角色确认状态。**没有用户明确批准绝不切换 approved。**
- 下一次 reader 在云端读到 approved 记录后，才算真正进入长期记忆的自动召回。

## 边界与后续生产化
这是一条由**用户已授权的 Supabase 管理连接临时 SET ROLE 降权**执行的代理方案，不是普通用户 JWT 自动续期/OAuth 完成的独立零信任网关。若定时任务环境不能使用 Supabase 连接，应在报告中诚实说“本轮未能读取”，不可编造。当前检索只取每次最新 15 条，不具备向量检索或语义索引。持久生产化仍需要真正的 OAuth 连接器/受保护网关、独立审计、重试保护、授权撤销、监控；不在 GitHub 存任何私人数据。
