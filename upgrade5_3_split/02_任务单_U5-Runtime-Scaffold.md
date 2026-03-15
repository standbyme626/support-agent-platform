### 任务单 1：U5-Runtime-Scaffold

```text
你现在要做的是 Upgrade 5 的第一阶段：建立 LangGraph + LangChain + Deep Agents 运行时骨架。

重要约束：
1. 不允许把目标降级为“继续完善现有 workflow-first 架构”。
2. 不允许通过删除 LangGraph / Deep Agents 目标来完成任务。
3. 必须把当前仓库改造成“兼容现有业务，但开始由新 runtime 托底”的结构。
4. 所有改动必须小步提交，禁止再做一个巨大收尾式提交。
5. 你可以保留现有 workflows 作为兼容壳，但新的主运行时骨架必须出现。

任务目标：
A. 在后端引入 LangGraph、LangChain、Deep Agents 依赖。
B. 新建统一运行时目录，例如：
   - runtime/graph/
   - runtime/agents/
   - runtime/state/
   - runtime/checkpoints/
   - runtime/tools/
C. 定义 Upgrade 5 的统一 state schema，至少包含：
   - ticket
   - session
   - handoff
   - approval
   - grounding
   - trace
   - copilot_outputs
   - channel_route
D. 建立一个最小可运行的 LangGraph demo 流程：
   ticket_open -> investigate -> approval_wait -> resume -> resolve_candidate
E. 接入 checkpoint / persistence 骨架，要求支持中断恢复。
F. 为后续 Deep Agents 预留 agent registry 和 tool registry。
G. 保持现有 API 不立即全部报废，但需要明确兼容层与新 runtime 的边界。

必须交付：
1. pyproject.toml / requirements 中新增 LangGraph / LangChain / Deep Agents 相关依赖。
2. 新 runtime 目录和最小实现代码。
3. 至少 1 个集成测试，验证 graph 可运行、可中断、可恢复。
4. 一份 docs/upgrade5-runtime.md，说明：
   - 新 runtime 结构
   - 现有 workflow 与新 runtime 的关系
   - 后续 U5-2/U5-3/U5-4 如何接入
5. 一份 migration note，说明哪些旧模块暂时保留为 compatibility shell。

完成定义（DoD）：
- 代码库中明确出现 LangGraph / Deep Agents runtime 骨架。
- 不是只有依赖声明，必须有真实可运行 graph。
- 不是只写文档，必须有测试。
- 不能修改任务目标，不能绕过 Deep Agents 方向。

输出要求：
1. 先给我变更计划。
2. 然后实施代码修改。
3. 最后给我：
   - 变更文件列表
   - 测试结果
   - 剩余风险
   - 下一步建议（但不要替我做下一步）
```

---

