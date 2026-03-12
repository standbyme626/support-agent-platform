# web_console (升级2 Ops Console)

本目录是升级2 Ops Console 的前端工程。

当前状态：

- A~H 全组已完成：Dashboard、Tickets、Ticket Detail、Timeline、Traces、Queues、KB、Channels/Gateway。
- 页面三态统一：Loading / Empty / Error。
- Ticket 动作链已闭环：`claim -> reassign/escalate -> resolve -> close`，并修复动作失败场景的反馈准确性。
- Ticket List/Detail 已补齐升级2要求的核心定制字段可见性与可筛选性（`service_type/community_name/building/parking_lot/approval_required`）。
- Trace 详情已覆盖：route decision、tool calls、grounding docs、summary、handoff、latency。
- Queue 支持按队列跳转 Ticket List 过滤视图。
- KB 支持 `faq/sop/history_case` 的 CRUD。
- Channels 页面支持 gateway status、channel health、webhook events 展示。
- Ticket List / Traces / Queues / Channels 均已提供显式刷新按钮。
- 已新增统一反馈组件 `components/shared/action-feedback.tsx`，用于成功/失败提示样式收敛。
- 已补前端最小 e2e 流程用例：`tests/e2e/upgrade2-minimal-flow.test.tsx`（Ticket 动作链、Trace drill-down、KB CRUD、Channels 观测）。

## 目录入口

- 路由层：`app/(dashboard)/**`
- 组件层：`components/{tickets,traces,queues,channels,kb,shared}`
- API 客户端：`lib/api/**`
- 页面/组件测试：`tests/**`

## 常用命令

- `npm run lint`
- `npm run typecheck`
- `npm test`

## 关联文档

- [`../升级2.md`](../升级2.md)
- [`../升级2-实施要求与验收测试规范.md`](../升级2-实施要求与验收测试规范.md)
- [`../升级2-任务分解与执行清单-A1-H4.md`](../升级2-任务分解与执行清单-A1-H4.md)
