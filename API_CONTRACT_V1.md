# API Contract v1 (升级2联调冻结)

- Contract ID: `api-contract-v1`
- Frozen At (UTC): `2026-03-11T00:00:00Z`
- Scope: 升级2 Ops Console 联调最小可用接口
- Owner: `support-agent-platform` backend

## 1. 统一约定

- Base path: `/api`
- Pagination: `page`, `page_size`, `total`
- Error schema:

```json
{
  "code": "string",
  "message": "string",
  "request_id": "string",
  "details": {}
}
```

## 2. 接口冻结清单

### 2.1 Dashboard

- `GET /api/dashboard/summary`
- `GET /api/dashboard/recent-errors`

### 2.2 Tickets

- `GET /api/tickets`
- `GET /api/tickets/:ticketId`
- `GET /api/tickets/:ticketId/events`
- `GET /api/tickets/:ticketId/assist`
- `GET /api/tickets/:ticketId/similar-cases`
- `POST /api/tickets/:ticketId/claim`
- `POST /api/tickets/:ticketId/reassign`
- `POST /api/tickets/:ticketId/escalate`
- `POST /api/tickets/:ticketId/resolve`
- `POST /api/tickets/:ticketId/close`

### 2.3 Queue

- `GET /api/queues`
- `GET /api/queues/summary`

### 2.4 Trace

- `GET /api/traces`
- `GET /api/traces/:traceId`

### 2.5 KB

- `GET /api/kb`
- `POST /api/kb`
- `PATCH /api/kb/:docId`
- `DELETE /api/kb/:docId`

### 2.6 Channel / OpenClaw

- `GET /api/channels/health`
- `GET /api/channels/events`
- `GET /api/openclaw/status`
- `GET /api/openclaw/routes`

### 2.7 支撑

- `GET /api/agents/assignees`

## 3. 变更规则

- 本文档冻结后，联调阶段不允许破坏性改动。
- 新增字段允许（backward-compatible）。
- 删除字段、修改字段语义、修改错误结构均视为破坏性改动，必须升级契约版本（例如 `api-contract-v2`）。
