# TimeCat V2 · 私人记忆入口（真实 Supabase Auth + RLS）

TimeCat 专用项目：`svlxyknltmeninipjrxo`，私有数据库：`public.timecat_memory_v2`。

## 运行

在 `damoxingtest` 仓库根目录启动只供你本机使用的静态页面：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory timecat/web
```

浏览器打开 `http://127.0.0.1:8765`，使用已在 **TimeCat-Memory → Authentication → Users** 注册并验证的 TimeCat Auth 邮箱和密码登录（不是 Supabase Dashboard 管理后台会话）。密码只从浏览器直接发送到 Supabase Auth HTTPS；此页面不把密码、JWT、刷新令牌、私人聊天写入 GitHub 或浏览器的持久存储。

## 使用

1. 登录后按用户身份从 Supabase 云端读取你拥有的记录。
2. 输入师傅明确允许保存的经验，先提交为 `proposed`。
3. 审核 **批准** 后，记录才成为 `approved`，后续检索只应使用已批准记录；也可以拒绝。
4. 关闭页面，在另一个浏览器或电脑同样登录可检索已有云端记录；**这才属于真实跨会话云端记忆**（需完成实际两端验证）。
5. 如果出现冲突（revision 不匹配），先重新读取，不允许无声覆盖。超过 200 条记录的列表当前只显示最新 200 条，需要分页升级。

## 安全说明

- 本页面是纯静态网页，不使用第三方 JS 依赖。只有 Supabase `sb_publishable_` 公钥嵌入前端，绝不嵌入 `service_role`、secret 或用户 JWT。
- 正式 Auth 会话只保存在浏览器内存中，刷新页面需重新登录，旧登录信息不会自动复用；页面运行过程中可使用 Supabase 颁发的 refresh token 在内存中续期。
- 数据库已开启强制 RLS，`owner_id = auth.uid()`，禁用匿名直接查询。密码与私人记忆不会出现在公开 GitHub。
- 若要供外部网络访问，请先部署到你自己控制的 HTTPS 域名并验证来源；不要使用非可信 HTML 预览代理网站。
- 由于 Supabase Auth 的安全顾问检测到泄露密码防护未启用，建议先在 Dashboard 的 Authentication → Settings 里开启 Leaked Password Protection（若当前方案支持该功能）。

## 与 ChatGPT 定时任务的真实边界

这个页面能让 bobo 师傅直接管理私人云端记忆，但**不会自动把 ChatGPT 的每日对话抓进数据库**。现有定时任务仍然不能直接使用网页的登录会话；要完成自动双向记忆闭环，仍需一个经用户独立授权且可审计的受保护同步网关/连接器，或经用户明确指示的安全录入流程。

只在完成真实登录、创建、批准、退出并在另一个浏览器重新登录读取后，才可称为已完成用户级跨会话验证。
