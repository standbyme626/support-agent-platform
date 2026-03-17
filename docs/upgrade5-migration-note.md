# Upgrade 5 迁移说明（Runtime 脚手架阶段）

## 1. 阶段目标

在不破坏现有线上行为的前提下，完成运行时基础设施建设，并逐步把主线路径迁到新架构。

## 2. 状态更新（2026-03-17）

- Workflow1 已完成默认路径迁移，当前主线为 `app/graph_runtime/intake_graph.py`。
- `runtime/graph/intake_graph.py` 保留为 compat/frozen 兼容壳。
- runtime scaffold 相关模块继续作为共享运行时基础设施存在。

## 3. 仍保留的兼容壳

- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`
- `core/workflow_engine.py`
- `scripts/ops_api_server.py`

这些模块当前主要承担请求入口、编排衔接和兼容职责，不再作为新业务逻辑的首选落点。

## 4. 已新增的运行时模块

- `runtime/state/schema.py`
- `runtime/graph/scaffold.py`
- `runtime/checkpoints/store.py`
- `runtime/tools/registry.py`
- `runtime/agents/registry.py`

## 5. 当前边界定义

- 主线路径：Workflow1 图执行走 `app/graph_runtime/intake_graph.py`。
- 兼容路径：`runtime/graph/intake_graph.py` 仅做转发兼容。
- 基础能力路径：`runtime/graph/scaffold.py` 用于 pause/resume 基线与集成验证。

## 6. 为什么这个迁移是安全的

- 没有做一次性破坏式重线。
- 运行时脚手架是增量引入，可独立测试。
- checkpoint/resume 能力有隔离验证，便于回归与审计。

## 7. 下一步收口

继续执行 Upgrade 5 收口：

- P1-1：继续把 `scripts/ops_api_server.py` 做薄壳化，下沉业务逻辑到 `app/transport + app/application + app/domain`。
- P1-2：补一页版收口报告（已完成/未完成/风险点/旧路径退役窗口）。
