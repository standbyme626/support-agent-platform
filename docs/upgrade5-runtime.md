# Upgrade 5 Runtime 脚手架说明

## 1. 范围

本文档说明 Upgrade 5 的运行时脚手架建设，以及当前主线路径与兼容壳的边界，目标是保证“可演进”与“不破坏现网行为”同时成立。

## 2. 当前状态（2026-03-17）

- Workflow1（Support Intake）默认图执行路径已经切到 `app/graph_runtime/intake_graph.py`。
- `runtime/graph/intake_graph.py` 已冻结为兼容转发壳，不再承载新增业务逻辑。
- `runtime/graph/scaffold.py` 继续保留，用于运行时基础能力与中断恢复链路验证。

## 3. 运行时目录结构

```text
runtime/
  agents/
    registry.py
  checkpoints/
    store.py
  graph/
    scaffold.py
  state/
    schema.py
  tools/
    registry.py
```

## 4. 核心组件说明

1. `runtime/state/schema.py`
- 定义图节点共享状态信封。
- 关键字段包含：`ticket`、`session`、`handoff`、`approval`、`grounding`、`trace`、`copilot_outputs`、`channel_route`。

2. `runtime/graph/scaffold.py`
- 提供最小可运行图示例：
- `ticket_open -> investigate -> approval_wait`
- 支持 checkpoint 中断保存与 `resume -> resolve_candidate` 恢复。

3. `runtime/checkpoints/store.py`
- 文件型 checkpoint 存储（`FileCheckpointStore`）。
- 保存运行时状态与恢复目标节点。

4. `runtime/tools/registry.py`
- 建立运行时工具注册边界（检索、摘要、工单动作、推荐动作等）。

5. `runtime/agents/registry.py`
- 建立运行时 agent 注册边界，覆盖 Upgrade 5 四类角色：
- intake
- case copilot
- operator/supervisor
- dispatch/collaboration

6. `app/bootstrap/runtime.py`
- 将运行时装配从 `scripts/ops_api_server.py` 抽离。
- 统一配置加载、仓储迁移、ticket API v1/v2 组合与审批运行时初始化。
- `scripts/ops_api_server.py::build_runtime()` 目前保留为兼容入口。

## 5. HTTP 处理器拆分现状

`scripts/ops_api_server.py` 目前保留入口、装配与高层调度；业务分支已下沉到 `app/transport/http/handlers.py`，降低脚本层耦合。

当前路由簇：

1. 会话/工单读取
- `try_handle_session_read_routes`
- `try_handle_ticket_read_routes`

2. Copilot/检索/待审批/会话控制
- `try_handle_copilot_routes`
- `try_handle_retrieval_and_approval_routes`
- `try_handle_session_control_routes`

3. 工单动作簇（v1/v2 + workflow 控制）
- `try_handle_ticket_action_routes`
- 覆盖 switch-active、merge-suggestion、v2 action、v2 investigate、v2 intake-run、v2 session-end、v1 action

4. 审批动作
- `try_handle_approval_action_routes`
- 覆盖 `/api/approvals/:approvalId/approve|reject`

5. 可观测性与知识库
- `try_handle_trace_routes`（`/api/traces*`）
- `try_handle_kb_routes`（`/api/kb*`）
- `try_handle_channel_routes`（`/api/channels*`、`/api/openclaw*`）

职责边界：

- `handlers.py`：路径匹配 + 路由行为
- `routes.py`：路由常量/正则
- `ops_api_server.py`：传输入口 + 运行时装配 + 高层调度

## 6. 与现有工作流的兼容关系

- 兼容入口仍保留在：
- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`
- 其中 `SupportIntakeWorkflow` 默认已接入 `app/graph_runtime/intake_graph.py`（`SupportIntakeGraphRunner`）。
- `runtime/graph/intake_graph.py` 仅作为兼容重定向壳存在。
- API 编排主入口仍为 `scripts/ops_api_server.py`。

## 7. 验证

关键验证：

- `tests/integration/test_u5_runtime_scaffold.py`

覆盖点：

- 图运行
- checkpoint 中断保存
- resume 恢复与 checkpoint 清理

## 8. 后续状态

1. U5-2 Workflow1 Graphize：已完成
- Support Intake 默认路径已切到 `app/graph_runtime/intake_graph.py`
- 会话/工单语义边界已经落到显式图节点与边

2. U5-3 Agent Operator/Dispatch：已完成
- operator/dispatch 查询链路已接入运行时 agent 注册
- 高风险动作保持 advice-only，并由策略门阻断直执

3. U5-4 前端与企微收口：进行中
- 关键 API 已暴露 runtime node/state/trace
- 分派目标路由与 UI/Bridge 最终收口继续在 P1 阶段推进
