# Upgrade 5 Workflow 1 Graphize

## Scope

This phase migrates Workflow 1 (Support Intake) to a graph-first execution path while preserving the existing `SupportIntakeWorkflow.run()` response contract as a compatibility shell.

## Entry and Compatibility

- Entry API is unchanged: `SupportIntakeWorkflow.run(envelope, existing_ticket_id=...)`.
- Internally, the workflow now uses `app/graph_runtime/intake_graph.py` (`SupportIntakeGraphRunner`) by default.
- A graph-disabled fallback remains available through `use_graph_runtime=False`.
- `runtime/graph/intake_graph.py` remains as a compat shell and should not carry new business logic.

## Graph Nodes

The intake graph uses explicit nodes:

1. `ingest_message`
2. `classify_intent`
3. `session_control_detect`
4. `customer_confirm_detect`
5. `retrieve_context`
6. `faq_answer_or_ticket_open`
7. `emit_collab_push`
8. `emit_user_reply`

## Edge Rules

- `session_control_detect -> emit_user_reply` when `/end` or `/new` style session control is matched.
- `session_control_detect -> customer_confirm_detect` otherwise.
- `customer_confirm_detect -> emit_user_reply` when command/customer-confirm/advice/clarification result is produced.
- `customer_confirm_detect -> retrieve_context` when normal intake processing should continue.
- `retrieve_context -> faq_answer_or_ticket_open -> emit_collab_push -> emit_user_reply`.

## Semantic Boundaries Preserved

1. `session_end` does not close tickets:
- Ends session context and switches mode to `awaiting_new_issue`.

2. `customer_confirm` closes only resolved/waiting-customer tickets:
- Natural language confirmation is mapped to `/customer-confirm`.

3. `new_issue` mode remains separate from ticket close:
- Explicit `/new` and contextual new-issue detections are preserved.

## Runtime Trace Fields

Workflow output now carries graph trace metadata in `reply_trace`:

- `runtime_graph`
- `runtime_current_node`
- `runtime_path`
- `runtime_state`

This enables node/edge/state visibility without breaking legacy payload shape.

## Minimal Trace Example

```json
{
  "runtime_graph": "workflow1-intake-graph-v1",
  "runtime_current_node": "emit_user_reply",
  "runtime_path": [
    "ingest_message",
    "classify_intent",
    "session_control_detect",
    "customer_confirm_detect",
    "retrieve_context",
    "faq_answer_or_ticket_open",
    "emit_collab_push",
    "emit_user_reply"
  ],
  "runtime_state": {
    "decision": "continue_current",
    "reason": "active_ticket_default",
    "session_action": null,
    "ticket_action": "create_ticket",
    "ticket_id": "TCK-000123"
  }
}
```

## Verification

- `tests/workflow/test_support_intake_workflow.py`
  - New graph trace coverage across:
    - FAQ direct reply
    - Ticket create/handoff path
    - Session end (`/end`)
    - New issue mode (`/new`)
    - Customer natural-language confirmation close
