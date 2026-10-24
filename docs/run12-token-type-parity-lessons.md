# 2026-10-24 Run 12 token_type_ids 输入一致性经验

[完整可复核报告](../reports/2026-10-24/token-type-parity-40043428043/report.md)

- 假设：训练 response_only_collator 未传 token_type_ids，推理 generate(**inputs) 却传入该字段，导致条件不一致。
- 验证：PR #25，静态预检 Run 40043374029 success，新增 6 项离线测试；CPU Run 40043428043 completed/success，40 次推理；Artifact 12540092198，原始 diagnostics.json SHA-256 6e7592a4f84a9c3aa08eb4ebb59a7f947afd116ffebc38115c7abefb5f9eb56d。
- 实测：基础模型纯标点 7/10→3/10；候选 LoRA 10/10→7/10。首 Token 变化分别为 7/10 和 3/10。
- 历史 GPU：Run 39921870784，Tesla T4 14.56 GiB、33 步，Train Loss 3.246455、Val Loss 3.147277、PPL 23.272599。未新训练，质量门槛仍拒绝晋级。
- 经验：输入字段不一致影响生成行为，但消除该差异仍不能解决多数候选输出的纯标点问题。不要把标点率降低称为模型能力进化。
- 下一步：先审阅真实中文输出，再设计最小推理补丁。防止脚本修改意外触发 Kaggle GPU 重训，保留可回滚版本，保护用户、维护人类，不泄露凭据。
