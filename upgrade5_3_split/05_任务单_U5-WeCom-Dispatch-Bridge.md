### 任务单 4：U5-WeCom-Dispatch-Bridge

这份专门解决你现在最明显的现场问题：**建单了不会自动发送到另外一个群**。当前 README 自己都把“处理群、工单系统、前端工作台之间状态不一致”列为业务痛点之一，所以这个任务必须被做成 Upgrade 5 正式内容，而不是边缘修补。([GitHub][1])

```text
你现在要做的是 Upgrade 5 第四阶段：打通 WeCom 跨群协同分发，把“建单后自动推送到处理群/工单群”真正落地。

重要约束：
1. 这不是简单改文案。
2. 这不是只在当前用户 session 回复一条消息。
3. 必须与新的 graph runtime 和 Dispatch Agent 对齐。
4. 必须能解释：为什么发给这个群、谁决定的、是否经过 gate。

任务目标：
A. 在统一 graph state 中加入：
   - channel_route
   - collab_target
   - dispatch_decision
   - delivery_status
B. 由 Dispatch Agent 给出目标处理群/处理人建议。
C. 由 policy gate 决定是否允许自动分发。
D. WeCom adapter 必须支持“非当前 session 的二次 outbound”。
E. 实现 queue/inbox -> target_session_id 或 target_group_id 的映射机制。
F. 建单后如果允许自动分发：
   - 用户群收到建单回执
   - 处理群收到协同消息
   - 前端可看到 dispatch edge 和 delivery status
G. 如果不允许自动分发：
   - 必须记录拒绝原因
   - 必须在 trace 中可见

必须交付：
1. graph state 扩展。
2. Dispatch Agent -> route decision -> policy gate -> WeCom outbound 的完整链路。
3. 至少 2 个集成测试：
   - 自动分发成功
   - 自动分发被 gate 拦截
4. 一份 docs/upgrade5-wecom-dispatch.md，说明：
   - routing model
   - target mapping
   - delivery trace
5. 一份 demo 或 replay 脚本，能模拟：
   - 用户报修
   - 建单
   - 处理群收到协同消息

完成定义（DoD）：
- “不会自动发到另一个群”的问题必须被真正解决。
- 不是只生成 collab_push message。
- 必须真的支持目标群 outbound。
- 必须能在 trace / console 中解释分发结果。
```

---

