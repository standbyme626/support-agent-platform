# Upgrade 5: Operator / Dispatch Agent Runtime

## 概览

本阶段将 `Operator / Supervisor Agent` 与 `Dispatch / Collaboration Agent` 从接口占位提升为可运行 agent：

- 接入 `build_runtime(...)`，并通过 `/api/copilot/operator/query`、`/api/copilot/dispatch/query` 对外提供能力。
- 保持 `advice_only` 模式，所有高风险动作只给建议，不直接执行。
- 输出包含 grounding 与 trace，支持审计与回溯。

## Agent 职责

### Operator / Supervisor Agent

文件：`app/agents/deep/operator_dispatch_agent.py`

- 面向队列压力、SLA 风险、升级工单进行多步分析。
- 工具调用链：
  - `dashboard.summary`（读取看板风险）
  - `queue.summary`（读取队列负载）
  - `retriever.grounded_search`（补充 grounding 依据）
- 输出字段：
  - `answer`
  - `advice_only=true`
  - `dashboard_summary`
  - `grounding_sources`
  - `recommended_actions`
  - `confidence`
  - `runtime_trace`

### Dispatch / Collaboration Agent

文件：`app/agents/deep/operator_dispatch_agent.py`

- 面向分派优先级、协同建议与处理队列推荐。
- 工具调用链：
  - `queue.summary`
  - `retriever.grounded_search`
- 输出字段：
  - `answer`
  - `advice_only=true`
  - `dispatch_priority`
  - `grounding_sources`
  - `recommended_actions`
  - `confidence`
  - `runtime_trace`

## Policy Gate 与禁止直执动作

Dispatch 与 Operator 均在 `runtime_trace.policy_gate` 中明确策略门：

- `enforced=true`
- 禁止 agent 直接执行：`reassign`、`resolve`、`operator-close`、`approve`
- 当 query 含终态执行意图（如“直接执行 reassign 并关闭工单”）时：
  - `blocked_execution=true`
  - 仍返回建议，但不执行状态迁移

## Runtime 与 Registry 接入

`scripts/ops_api_server.py` 中 `build_runtime(...)` 完成：

- 初始化 `ToolRegistry`：`build_default_tool_registry()`
- 初始化 `AgentRegistry`：`build_default_agent_registry()`
- 构建并注入：
  - `operator_agent = build_operator_supervisor_agent(...)`
  - `dispatch_agent = build_dispatch_collaboration_agent(...)`
- `OpsApiRuntime` 新增字段：
  - `tool_registry`
  - `agent_registry`
  - `operator_agent`
  - `dispatch_agent`

`runtime/agents/registry.py` 已包含：

- `operator-supervisor-agent`
- `dispatch-collaboration-agent`

并声明 runtime mode 与 toolset，用于后续编排与审计。

## API 返回兼容

`/api/copilot/operator/query` 与 `/api/copilot/dispatch/query` 统一返回：

- `answer`
- `advice_only`
- `grounding_sources`
- `recommended_actions`
- `confidence`
- `runtime_trace`
- `llm_trace`（兼容字段，fallback）

## 测试

新增/覆盖测试：

- `tests/unit/test_operator_dispatch_agent_runtime.py`
  - operator 问队列压力
  - operator 问 SLA 风险
  - dispatch 问优先分派建议
  - dispatch 高风险动作被 gate 阻断
- `tests/integration/test_copilot_api.py`
  - operator/dispatch API 返回统一字段
  - dispatch 终态执行意图请求被阻断（advice-only）
