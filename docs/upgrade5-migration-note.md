# Upgrade 5 Migration Note (Runtime Scaffold Phase)

## Goal of This Phase

Establish runtime foundations without breaking current production behavior.

## Compatibility Shells Kept Intact

- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`
- `core/workflow_engine.py`
- `scripts/ops_api_server.py`

These modules remain the current execution path for existing requests.

## New Runtime Modules Added

- `runtime/state/schema.py`
- `runtime/graph/scaffold.py`
- `runtime/checkpoints/store.py`
- `runtime/tools/registry.py`
- `runtime/agents/registry.py`

## Current Boundary

- Old path: workflow-first execution remains active.
- New path: runtime scaffold is available and test-verified, but not yet the default request path.

## Why This Is Safe

- No destructive rewiring of existing workflows.
- Runtime scaffold is additive and independently testable.
- Checkpoint/resume behavior is validated in isolation.

## Next Migration Step

U5-2 should connect `SupportIntakeWorkflow` compatibility shell to the runtime graph path for intake state transitions.
