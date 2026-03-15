### 任务单 5：U5-Console-Graph-UI

这份是把前端真正拉到 Upgrade 5 的目标线上。README 明确把 Workflow 3 定义成前端工作台处理，并列出 `/tickets/[ticketId]` 是“工单详情 + 时间线 + AI Assist”；所以这里不能再停留在“详情页有骨架、但端到端不完整”的状态，要让前端成为 graph/runtime 的可视化入口。([GitHub][1])

```text
你现在要做的是 Upgrade 5 第五阶段：把 Web Console 从“旧 API 壳 + 局部 AI 区块”升级成 LangGraph / Deep Agents runtime 的前端工作台。

重要约束：
1. 不允许把前端任务简化成改几个按钮文案。
2. 不允许只展示旧 workflow 状态。
3. 必须把 graph state / agent outputs / approval / handoff 真正展示出来。
4. 不能依赖“以后再补”，这次要把 detail workspace 做成 Upgrade 5 的正式可验收入口。

任务目标：
A. Ticket Detail 页面显示 runtime 视角信息：
   - current graph node
   - graph state summary
   - pending approval
   - pending customer
   - pending handoff
   - delivery / dispatch status
B. AI 助手区接入三类输出：
   - ticket copilot
   - operator agent
   - dispatch agent
C. 人工动作区改造成 graph transition controls，而不是散乱的旧动作按钮集合。
D. 审批恢复区必须能显示：
   - 当前审批状态
   - resume 所需动作
   - 审批后的 graph 恢复结果
E. trace 页面必须能 drill down 到 graph execution：
   - node
   - edge
   - tool calls
   - agent outputs
F. 如果某一路 agent 暂时失败，前端必须局部降级，不允许整页 AI 区全部挂掉。
G. 明确把“人工接入/handoff”做成可操作流程，而不是只显示状态。

必须交付：
1. Ticket Detail 页面升级。
2. Graph trace / execution 可视化最小版本。
3. 前端 API 客户端与新 runtime 对齐。
4. 至少 3 个前端测试：
   - detail 页渲染 graph state
   - AI 区局部失败时可降级
   - handoff / approval 操作路径可见
5. 一份 docs/upgrade5-console-ui.md，说明：
   - 页面信息架构
   - graph/runtime 显示内容
   - agent outputs 的展示规则

完成定义（DoD）：
- 前端不再只是旧 workflow 的壳。
- Workflow 3 作为正式处理工作台可验收。
- AI 区、人工动作区、审批恢复区都与新 runtime 对齐。
- “前端还是看不见 AI 质询和人工接入”的问题必须显著改善。
```

---

### 发送顺序建议

按这个顺序发最稳：

1. **U5-Runtime-Scaffold**
2. **U5-Workflow1-Graphize**
3. **U5-Agent-Operator-Dispatch**
4. **U5-WeCom-Dispatch-Bridge**
5. **U5-Console-Graph-UI**

这个顺序的逻辑是：先建 runtime，再迁入口流，再补 agent 面，再打通 WeCom 调度，最后把前端接成正式工作台。它和官方框架能力边界是对齐的：LangGraph 先解决 orchestration/runtime 与持久状态，Deep Agents 再用于复杂 agent 面。([LangChain 文档][3])

如果你愿意，我下一条可以继续帮你写两样东西：
**第一，发给 Codex 的“总前置说明”模板；第二，每个任务完成后的“验收 checklist 原文”。**

可以，一起给你。

先把前提说清楚：当前仓库公开说明仍把系统定义为 **workflow-first, agent-assisted**，并明确“本文档描述当前代码已落地的系统架构，不包含未实现设想”；同时 `API_CONTRACT_V2.md` 仍然是 `Upgrade 5 Draft`、`Status: draft`、`Phase: upgrade5-s2`。而 LangGraph 官方定位是**长时运行、有状态、可持久恢复、支持 human-in-the-loop** 的运行时；Deep Agents 官方定位则是**复杂多步规划、文件系统上下文管理、子 agent、长期记忆**。所以你发给 Codex 的总前置说明，必须强制它按“Upgrade 5 = LangGraph / Deep Agents 迁移”来做，而不是继续把旧 workflow 收尾当成升级完成。([GitHub][1])

---

