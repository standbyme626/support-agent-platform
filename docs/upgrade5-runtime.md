# Upgrade 5 Runtime Scaffold

## Scope

This document defines the first Upgrade 5 landing step: introduce a runnable runtime skeleton backed by LangGraph while keeping existing workflow entrypoints compatible.

## New Runtime Structure

```
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

## Runtime Components

1. `runtime/state/schema.py`
- Defines the shared state envelope used by graph nodes.
- Required fields are included: `ticket`, `session`, `handoff`, `approval`, `grounding`, `trace`, `copilot_outputs`, `channel_route`.

2. `runtime/graph/scaffold.py`
- Implements a minimal runnable graph demo:
  - `ticket_open -> investigate -> approval_wait`
  - interrupt through checkpoint persistence
  - `resume -> resolve_candidate`
- Uses LangGraph `StateGraph` for node/edge orchestration.

3. `runtime/checkpoints/store.py`
- File-backed checkpoint storage (`FileCheckpointStore`) for pause/resume.
- Persists runtime state and target resume node.

4. `runtime/tools/registry.py`
- Introduces a runtime tool registry boundary for retrieval/summary/ticket transition/recommended actions.

5. `runtime/agents/registry.py`
- Introduces a runtime agent registry boundary for four Upgrade 5 roles:
  - intake
  - case copilot
  - operator/supervisor
  - dispatch/collaboration

6. `app/bootstrap/runtime.py`
- Extracts runtime bootstrap wiring out of `scripts/ops_api_server.py`.
- Centralizes config/loading/repository migration/ticket API v1+v2 composition/approval runtime initialization.
- Keeps `scripts/ops_api_server.py::build_runtime()` as a compatibility wrapper.

## HTTP Handler Split (Upgrade 5 Final Round)

`scripts/ops_api_server.py` now keeps request entry, runtime wiring, and minimal orchestration.  
Business route branches are moved into `app/transport/http/handlers.py` to reduce script-level coupling.

Current route handler clusters:

1. Session + ticket read paths
- `try_handle_session_read_routes`
- `try_handle_ticket_read_routes`

2. Copilot + retrieval + pending approvals + session control
- `try_handle_copilot_routes`
- `try_handle_retrieval_and_approval_routes`
- `try_handle_session_control_routes`

3. Ticket action cluster (v1/v2 + workflow controls)
- `try_handle_ticket_action_routes`
- Covers: switch-active, merge-suggestion, v2 action, v2 investigate, v2 intake-run, v2 session-end, v1 action

4. Approval decisions
- `try_handle_approval_action_routes`
- Covers: `/api/approvals/:approvalId/approve|reject`

5. Observability and knowledge base routes
- `try_handle_trace_routes` for `/api/traces*`
- `try_handle_kb_routes` for `/api/kb*`
- `try_handle_channel_routes` for `/api/channels*` and `/api/openclaw*`

Responsibility boundary:
- `handlers.py`: path matching and per-route API behavior
- `routes.py`: path regex/constants only
- `ops_api_server.py`: transport entrypoint, runtime bootstrap, and high-level dispatch sequence

## Compatibility with Existing Workflows

- Existing workflow modules remain intact and are still the live compatibility shell:
  - `workflows/support_intake_workflow.py`
  - `workflows/case_collab_workflow.py`
- Existing API orchestration remains intact:
  - `scripts/ops_api_server.py`

This keeps current behavior stable while creating a concrete runtime foundation for migration.

## Verification

Test:
- `tests/integration/test_u5_runtime_scaffold.py`

Covers:
- graph run
- interrupt/checkpoint save
- resume/checkpoint cleanup

## Follow-up Wiring Plan

1. U5-2 Workflow1 Graphize
- Route Support Intake compatibility shell into the runtime graph nodes.
- Move session/ticket semantic boundaries into explicit graph edges.

2. U5-3 Agent Operator/Dispatch
- Bind operator and dispatch query paths to runtime agent registry entries.
- Keep high-risk actions behind graph/policy gates.

3. U5-4 Frontend + WeCom closure
- Surface runtime node/state/trace in console APIs.
- Add dispatch target routing from `channel_route` state into channel adapters.
