# TimeCat V2 私人记忆双端同步：安装、限制和验收

## 部署与验收状态更新（2026-10-29，北京时间）

- **V2 代码**：PR #77 已合并到 `main`；本地/模拟双端同步与 RLS 相关代码已具备，静态 CI 通过不等于线上服务验收。
- **专属云库**：用户指定的 TimeCat-Memory Supabase 项目已创建且状态健康；`public.timecat_memory_v2` 的 RLS 与基础权限已检查。只允许使用此专属项目，不得扫描其他项目或用管理员权限代替用户身份。
- **真实 Auth E2E**：师傅在本机运行独立验收程序并提交 `result=PASS`、`auth_sessions=2`、`created=true`、`remote_approval_verified=true`、`cleanup=verified`。这是**用户提交的双会话验收证据，尚未由本仓库 CI 独立复核**，不含密码、JWT、邮箱或私聊。
- **仍未上线**：ChatGPT 每小时/每日任务尚无经用户授权、可安全续期的普通用户连接；无法自动读取 approved 私人记忆或把对话回复写为待审记忆。不得声称生产自动同步已上线。
- **安全待办**：Auth 泄露密码防护仍有告警；JWT 安全续期、离线冲突与删除/恢复验收、最小权限后台网关仍待实现。PR #79 网页入口待审核，不能视为已发布。

## 已实现的部分
- 本地 SQLite 私人记忆仓库：标准库、UUID 跨设备主键、提议→人工批准/拒绝、可验证来源、只召回 approved，重启可恢复。
- Supabase PostgREST：只接受 HTTPS、用户 JWT、publishable key；不允许把 service_role 当用户密钥；基于 ID 和 revision 的冲突检测、离线待同步队列与幂等同步。
- 同步包括两个方向：先发送未提交的本地记忆，再拉取云端经所有会话审核的最新状态；云端版本冲突时保存本地变更而非覆盖。
- PostgreSQL SQL migration 提供按 auth.uid() 锁定私有数据的 RLS，拒绝匿名访问。
- 合成样例和本地测试验证两个独立 SQLite 实例经模拟云端的跨会话恢复，不代表云上服务已经可达。

## 必须先配置的真实云端资源
1. 使用**独立的 TimeCat Supabase 项目**，不要擅自把记忆表加入其他生产项目。项目首次创建/恢复可能有费用，需先得到用户同意。
2. 在项目 SQL 编辑器运行 timecat/migrations/001_private_memory.sql (或使用 Supabase 管理连接安全地应用)，完成后确认 RLS、角色权限、数据 API 暴露情况及安全建议。
3. 创建用户独占登录主体；使用该用户的 JWT 及 publishable key。不要用 service_role，永不提交 JWT 到 GitHub。
4. 把以下环境变量放到受保护的运行环境（不要放公开仓库）：
   TIMECAT_SUPABASE_URL=https://<PROJECT>.supabase.co
   TIMECAT_SUPABASE_PUBLISHABLE_KEY=<PUBLIC_KEY>
   TIMECAT_SUPABASE_ACCESS_TOKEN=<USER_SESSION_JWT>
   Token 到期后，需要通过受保护的登录/刷新过程更新；目前 CLI 不实现长期无人值守的 JWT 刷新。
5. 每次写入师傅私密偏好都应有师傅显式确认和来源；公开 GitHub 仓库不得保存聊天记录、JWT、私密摘要或数据库备份。

## 实际命令
\`\`\`bash
python -m unittest discover -s timecat/tests -v
python -m timecat.cloud_cli init
python -m timecat.cloud_cli propose preference "TimeCat称呼用户为bobo师傅" --source "user-confirmed-in-private-chat"
python -m timecat.cloud_cli status
python -m timecat.cloud_cli review "<ID>" approve
python -m timecat.cloud_cli sync
python -m timecat.cloud_cli recall bobo
\`\`\`
在第二个独立工作目录/机器中设置同一 Supabase 配置执行 \`python -m timecat.cloud_cli sync\` 后应能召回这条批准的记忆。正式验收还需真实云端双客户端读写、过期 JWT 拒绝、RLS 隔离用户与离线冲突验证。

## 定时任务与 ChatGPT 对话边界
目前 ChatGPT 的每小时/每日自动化并不会继承本地 Python 进程或 SQLite 文件。上线后必须让自动化通过**已连接的 Supabase 授权工具**访问正确的 TimeCat 项目（或调用已部署的受保护 TimeCat 网关），在发问之前读取经批准的记忆，并在师傅真正答复之后写入待审项。只修改自动化提示词不是线上同步。
禁止使用公共 GitHub 作为私人记忆缓存。没有用户答复就不编造；有回答也需要获授权才保存。
如果云端不可达，本地 outbox 可以保存，但不可声称“已同步”；最终报告要明确未同步状态。

## 还未实现的功能
- 专属 Supabase 项目与 RLS 已部署；师傅已提交真实 Auth E2E PASS（待独立复核）；**自动化持久授权连接尚未实现**。
- Supabase JWT 自动续期与真正永远在线的同步 Worker。
- 私人数据的导出、彻底删除、备份与冲突 UI；上线前需补齐。
- 语义向量检索、多模型长期记忆检索增强。
