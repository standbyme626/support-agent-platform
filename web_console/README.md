# web_console (升级2前端骨架)

本目录是升级2 Ops Console 的前端工程。

当前状态：

- 已落地 Dashboard A1~A4：
  - 页面骨架和统计卡片（含 Loading/Empty/Error）
  - `/api/dashboard/summary` 和 `/api/dashboard/recent-errors` 联调
  - SLA 状态语义（normal/warning/breached）与跳转链接
  - 前端页面测试：`tests/dashboard/dashboard.page.test.tsx`
- 已落地 Ticket List B1~B4：
  - 列表页、过滤栏、搜索输入、分页和排序
  - `/api/tickets` 与 `/api/agents/assignees` 联调
  - MUST 筛选项（含 `service_type/risk_level/sla_state`）与持久化
  - 前端/后端测试：`tests/tickets/ticket-list.page.test.tsx`、`tests/integration/test_ticket_list_api_filters.py`
- 已落地 Ticket Detail C1~C4：
  - 三栏详情页（核心字段、AI summary、recommended actions、similar cases、timeline）
  - `/api/tickets/:ticketId`、`/events`、`/assist`、`/similar-cases` 联调
  - 动作链 `claim/reassign/escalate/resolve/close` 可闭环
  - 前端/后端测试：`tests/tickets/ticket-detail.page.test.tsx`、`tests/integration/test_ticket_actions_api.py`
- 其余模块（D~H）仍按任务清单逐步补齐。

后续在 A1~H4 任务中逐步填充真实组件与联调逻辑。
