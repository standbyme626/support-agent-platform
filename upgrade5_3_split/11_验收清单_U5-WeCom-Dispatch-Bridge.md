### 4）U5-WeCom-Dispatch-Bridge 验收 checklist

```text
【U5-WeCom-Dispatch-Bridge 验收 Checklist】

请逐项回答“是 / 否”，并给出证据文件路径与说明：

一、建模是否完整
[x] graph state 是否新增了：
    - channel_route
    - collab_target
    - dispatch_decision
    - delivery_status
[x] 是否不是只返回一段 collab_push message？
[x] 是否能追踪 dispatch 的决策过程？

二、决策与 gate
[x] Dispatch Agent 是否能给出目标处理群/处理人建议？
[x] 是否存在 policy gate 决定能否自动分发？
[x] 如果被 gate 拦截，是否记录原因？
[x] gate 结果是否进入 trace / state？

三、WeCom adapter 能力
[x] WeCom adapter 是否支持非当前 session 的 outbound？
[x] 是否存在 queue/inbox -> target_session_id 或 target_group_id 的映射？
[x] 是否不是仍然只能回当前用户会话？
[x] 是否有明确的 delivery status 反馈？

四、端到端链路
[x] 用户群是否收到建单回执？
[x] 处理群是否能收到协同消息？
[x] 前端是否能看到 dispatch edge 和 delivery status？
[x] 是否能解释“为什么发到这个群”？

五、测试
[x] 是否至少有以下集成测试：
    - 自动分发成功
    - 自动分发被 gate 拦截
[x] 测试是否覆盖真实 route / outbound 逻辑？
[x] 是否能证明“不会自动发到另一个群”的问题已被真正解决？

六、文档与演示
[x] 是否新增 docs/upgrade5-wecom-dispatch.md？
[x] 是否说明：
    - routing model
    - target mapping
    - dispatch decision
    - delivery trace
[x] 是否提供 demo / replay 脚本？
[x] demo 是否可模拟：
    - 用户报修
    - 建单
    - 协同推送到处理群

七、判定标准
[x] 当前是否已实现“建单后自动推送到处理群/工单群”的 Upgrade 5 要求？
[x] 是否不是靠改文案掩盖未投递？
[x] 如果关闭新的 dispatch/runtime 逻辑，这个能力是否会消失？

请最后输出：
1. 通过项
2. 未通过项
3. 真实联调剩余风险
4. 建议是否进入 U5-Console-Graph-UI
```

---

