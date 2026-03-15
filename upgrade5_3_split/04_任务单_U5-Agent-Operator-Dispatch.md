### 任务单 3：U5-Agent-Operator-Dispatch

这份是你最需要的，因为前端公开代码已经把 ticket/operator/dispatch 三类 copilot 面都设计出来了，但你现在的感受是“前端看不见 AI 质询和人工接入真正落地”，核心原因之一就是 Operator / Dispatch 这两类 agent 面没有真正成为可用运行时。官方文档也说明 Deep Agents 适合多步骤规划、子 agent、长期记忆，所以这里正适合用在 operator 和 dispatch 这种复杂问答面。([GitHub][1])

```text
你现在要做的是 Upgrade 5 第三阶段：把四个 Agent 中的 Operator / Supervisor Agent 和 Dispatch / Collaboration Agent 做成真实可用的 agent runtime，而不是只停留在接口命名。

重要约束：
1. 必须保留 LangGraph / Deep Agents 目标。
2. Operator Agent 和 Dispatch Agent 不能只是规则拼接器。
3. 但高风险动作不能放任 agent 自治执行，必须经过 graph / policy gate。
4. 输出必须可追踪、可 grounding、可审计。

任务目标：
A. 实现 Operator / Supervisor Agent：
   - 面向 queue / SLA / 风险 / 优先级建议
   - 使用 Deep Agents 或 graph-based agent runtime
   - 支持多步分析，不是单轮字符串模板
B. 实现 Dispatch / Collaboration Agent：
   - 面向调度建议、协同问答、分派建议
   - 支持目标处理组/处理人建议
   - 但真正的 reassign / operator-close / approval 仍需走 graph gate
C. 补齐后端 API：
   - POST /api/copilot/operator/query
   - POST /api/copilot/dispatch/query
D. 返回统一 payload，至少包含：
   - answer
   - advice_only
   - grounding_sources
   - llm_trace / runtime_trace
   - recommended_actions
   - confidence
E. 将 Operator Agent、Dispatch Agent 接入 runtime/agents/ registry。
F. 给每个 agent 明确 toolset，不允许直接访问一切对象。

必须交付：
1. operator agent 实现。
2. dispatch agent 实现。
3. 新增后端 API 路由与处理逻辑。
4. 至少 4 个测试：
   - operator 问队列压力
   - operator 问 SLA 风险
   - dispatch 问优先分派建议
   - dispatch 给出建议但不直接执行高风险动作
5. 文档 docs/upgrade5-agents-ops-dispatch.md，说明：
   - 两个 agent 的职责
   - 使用的 tools
   - 哪些动作只能建议，不能直执

完成定义（DoD）：
- 不是只新增接口 stub。
- 不是只返回固定字符串。
- 至少有真实 agent runtime、真实 tool usage、真实 trace。
- 对高风险动作有 gate，不允许 agent 自治闭环。
```

---

