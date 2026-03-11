# web_console (升级2 Ops Console)

本目录是升级2 Ops Console 的前端工程。

当前状态：

- A~H 全组已完成：Dashboard、Tickets、Ticket Detail、Timeline、Traces、Queues、KB、Channels/Gateway。
- 页面三态统一：Loading / Empty / Error。
- Ticket 动作链已闭环：`claim -> reassign/escalate -> resolve -> close`。
- Trace 详情已覆盖：route decision、tool calls、grounding docs、summary、handoff、latency。
- Queue 支持按队列跳转 Ticket List 过滤视图。
- KB 支持 `faq/sop/history_case` 的 CRUD。
- Channels 页面支持 gateway status、channel health、webhook events 展示。

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
