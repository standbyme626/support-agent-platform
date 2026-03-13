# API Contract v2 (Upgrade 5 Draft)

- Contract ID: `api-contract-v2`
- Status: `draft`
- Phase: `upgrade5-s2`
- Compatibility Base: `API_CONTRACT_V1.md`

## 1. Global Conventions

- Base path: `/api`
- V2 recommendation: use explicit action endpoints under `/api/v2/*`
- Pagination fields: `page`, `page_size`, `total`
- Error schema:

```json
{
  "code": "string",
  "message": "string",
  "request_id": "string",
  "details": {}
}
```

## 2. V2 Action Endpoints (Boundary Definition)

### 2.1 Ticket Actions

- `POST /api/v2/tickets/:ticketId/resolve`
  - Meaning: mark ticket resolved, but not closed.
- `POST /api/v2/tickets/:ticketId/customer-confirm`
  - Meaning: customer confirms closure after resolve/handoff flow.
- `POST /api/v2/tickets/:ticketId/operator-close`
  - Meaning: operator/admin forced close with audit reason.

### 2.2 Session Action

- `POST /api/v2/sessions/:sessionId/end`
  - Canonical action name: `session_end`
  - Meaning: end current session context; not equal to ticket close.

## 3. Compatibility Strategy (v1 -> v2)

- `API_CONTRACT_V1.md` remains frozen during transition.
- Existing v1 endpoint `POST /api/tickets/:ticketId/close` is compatibility-only.
- Compatibility behavior must be explicit and deterministic:
  - `customer_confirm` and `operator_close` are distinct semantics in v2.
  - Ambiguous `close` requests should return validation errors instead of semantic guessing.

## 4. Boundary Rules

- Session state and ticket workflow state are separated.
- `session_end` cannot be used as an alias for ticket close.
- High-risk final actions remain HITL-governed by workflow/domain layers.
