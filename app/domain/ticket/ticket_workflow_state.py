from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TicketStatus = Literal["open", "pending", "escalated", "handoff", "resolved", "closed"]
HandoffState = Literal["none", "pending_claim", "claimed", "in_progress", "waiting_customer", "completed"]
ApprovalState = Literal["none", "pending_approval", "approved", "rejected", "timeout"]


@dataclass
class TicketWorkflowState:
    """Ticket-scoped workflow state model."""

    ticket_id: str
    status: TicketStatus
    handoff_state: HandoffState
    lifecycle_stage: str
    approval_state: ApprovalState = "none"

    def can_resolve(self) -> bool:
        return self.status not in ("resolved", "closed")

    def can_customer_confirm(self) -> bool:
        return self.status == "resolved" and self.handoff_state == "waiting_customer"

    def can_operator_close(self) -> bool:
        return self.status in ("open", "pending", "escalated", "handoff", "resolved")

    def can_mutate(self) -> bool:
        return self.status != "closed"
