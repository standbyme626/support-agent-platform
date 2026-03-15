## 一、发给 Codex 的“总前置说明”模板

```text
你接下来收到的是 support-agent-platform 的 Upgrade 5 系列任务。

先确认并严格遵守以下前提，这些前提优先级高于你自己的默认实现习惯：

【项目目标】
1. Upgrade 5 的目标不是“继续把现有 workflow-first 架构补完整”。
2. Upgrade 5 的目标是：在保留现有业务能力与兼容性的前提下，把系统逐步迁移到 LangGraph + LangChain + Deep Agents 支撑的运行时架构。
3. 你不允许通过删除、弱化、规避 LangGraph / Deep Agents 目标来完成任务。
4. 你不允许把“旧 workflow 继续增强”伪装成“框架升级完成”。

【架构原则】
1. LangGraph 负责：
   - stateful runtime
   - durable execution
   - checkpoint / resume
   - human-in-the-loop
   - graph state / node / edge / trace
2. Deep Agents 负责：
   - 复杂多步推理
   - planning / decomposition
   - context management
   - subagents
   - memory
3. 高风险业务动作（例如 resolve / customer-confirm / operator-close / approval）不能完全交给 agent 自治，必须保留 graph / policy gate / domain guardrail。
4. 旧的 workflows、ops_api、adapter、web_console 可以保留兼容层，但新 runtime 必须成为 Upgrade 5 的核心落点。

【执行边界】
1. 允许保留 compatibility shell。
2. 不允许只改文档、命名、注释而不落代码。
3. 不允许只加依赖、不做真实集成。
4. 不允许只做 stub / fake route / fake agent。
5. 不允许交付“未来再补”的空壳。
6. 不允许通过砍功能来让测试通过。
7. 每次任务都必须保持：
   - 可运行
   - 可测试
   - 可解释
   - 可追踪

【输出要求】
你每次接到任务，必须按以下结构输出：
1. 任务理解
2. 变更计划
3. 涉及文件与模块
4. 代码实现
5. 测试与验证
6. 变更摘要
7. 剩余风险
8. 不在本次范围内的内容

【实现要求】
1. 优先复用当前仓库已有 ticket/case core 的领域约束。
2. 优先把旧流程迁到 graph runtime，而不是平行再造一套无法接线的新系统。
3. 所有新 agent 必须说明：
   - 职责
   - tools
   - 输入
   - 输出
   - 不能直接执行的动作
4. 所有新 graph 必须说明：
   - state schema
   - nodes
   - edges
   - interrupt points
   - resume points
   - trace fields
5. 所有面向前端和渠道的能力都必须说明：
   - 与旧接口的兼容关系
   - 新 runtime 的真实来源
   - 降级策略

【代码风格与交付约束】
1. 每次任务应尽量形成小步、可审阅的提交。
2. 禁止再做“大收尾式”巨型改动。
3. 新增目录命名要清晰，例如：
   - runtime/graph/
   - runtime/agents/
   - runtime/state/
   - runtime/tools/
   - runtime/checkpoints/
4. 文档必须同步更新，但文档不能代替实现。
5. 测试必须覆盖主路径，不能只测 happy path。

【验收总原则】
如果结果仍然主要依赖旧的 SupportIntakeWorkflow / CaseCollabWorkflow 自定义流程，而 LangGraph / Deep Agents 只是外围点缀，则视为未完成 Upgrade 5 目标。
如果结果能明确体现：
- graph runtime 成为主干
- deep agents 承担复杂 agent 能力
- policy gate 仍控制高风险动作
- 前端 / WeCom / Ops API 真正接到新 runtime
则视为沿正确方向完成。

收到后，不要先写代码。
先复述你对本次任务的理解、范围、风险、实施步骤，再开始实现。
```

---

