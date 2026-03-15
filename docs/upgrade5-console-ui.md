# Upgrade 5 Console UI（U5-Console-Graph-UI）

## 页面信息架构

- `Ticket Detail` 统一为四区工作台：
  - 主视图区：事件时间线、核心字段、`Runtime 视角`、定制字段
  - AI 助手区：Grounding、推荐动作、Copilot 查询、调查/会话结束
  - 人工动作区：`Graph Transition Controls`
  - 审批恢复区：审批状态、恢复动作、恢复结果 + 审批记录列表
- `Trace Detail` 提供 trace 元信息卡 + 路由/工具/Grounding 卡 + `Graph Execution Drilldown`。

## Graph / Runtime 显示内容

`Ticket Detail` 的 `Runtime 视角` 卡至少展示：

- `current graph node`
- `graph state summary`
- `pending approval`
- `pending customer`
- `pending handoff`
- `dispatch status`
- `delivery status`

这些字段优先读 runtime/metadata/cp branch payload，并保留 `status + handoff_state + lifecycle_stage` 作为兜底摘要。

## AI 区规则（ticket/operator/dispatch）

- 同时展示三路建议输出：
  - `ticket copilot`
  - `operator agent`
  - `dispatch agent`
- 每一路显示：
  - `agent source`
  - `grounding` 数量
  - `recommended_actions` 数量
  - `runtime_trace`（含 tool/policy gate 线索）
- 局部降级规则：
  - 使用 `Promise.allSettled` 聚合三路查询。
  - 某一路失败仅标记 `AI partial degradation`，保留其余成功路输出。
  - 仅当三路都失败时才将查询判定为整体失败。

## Handoff / Approval / Trace 展示策略

- 人工动作区以状态迁移语义展示，不再仅堆叠旧按钮：
  - 展示主要 transition（from -> to）与当前 `handoff_state`。
  - 明确高风险动作会进入审批链路。
- 审批恢复区展示：
  - 当前审批状态（含 `pending_approval` 数量）
  - `resume` 所需动作（approve/reject 或下一步人工动作）
  - 审批后的 graph 恢复结果（基于最近决定记录）
- Trace 页面新增 `Graph Execution Drilldown`：
  - `node`
  - `edge`
  - `tool calls`
  - `agent outputs`
  - 并附 `route_decision` 预览，支持执行路径排查。

## 兼容关系与降级

- 仍保留 `close_compat`（v1 `/close`）作为灰度/回滚兼容入口。
- 默认动作语义为 v2 runtime transition。
- 即使某一路 agent 临时失败，页面仍保留主流程与可操作路径，不阻断人工接入。
