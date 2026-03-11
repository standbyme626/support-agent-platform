# API Client Overview

`web_console/lib/api` 已覆盖升级2页面所需接口模块。

## Core

- `client.ts`：统一 JSON 请求与错误归一化（`code/message/request_id`）。

## Domain Modules

- `dashboard.ts`：`/api/dashboard/summary`、`/api/dashboard/recent-errors`
- `tickets.ts`：Ticket list/detail/events/assist/similar-cases/actions + assignees
- `traces.ts`：Trace list/detail
- `queues.ts`：Queues + queue summary
- `kb.ts`：KB list/create/update/delete
- `channels.ts`：channels health/events + openclaw status/routes

## Notes

- 列表接口统一支持分页参数和总数回传（`page/page_size/total`）。
- 过滤参数与 URL 查询参数在 hooks 层串联（如 `useTickets`、`useTraceList`）。
