from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from app.domain.systems.base import BaseSystem, SystemAction, SystemKey
from app.domain.systems.system_errors import (
    DuplicateRequestError,
    EntityNotFoundError,
    ForbiddenActionError,
    InternalError,
    InvalidStateTransitionError,
    SystemError,
    ValidationError,
)
from app.domain.systems.system_registry import SystemRegistry, registry
from app.domain.systems.system_result import SystemResult
from app.domain.systems.system_transition_engine import SystemTransitionEngine


def register_all_systems(registry: SystemRegistry | None = None) -> SystemRegistry:
    if registry is None:
        registry = SystemRegistry()
    registry.reset()

    registry.register(_create_ticket_system())
    registry.register(_create_procurement_system())
    registry.register(_create_finance_system())
    registry.register(_create_approval_system())
    registry.register(_create_hr_system())

    return registry


def _create_ticket_system() -> BaseSystem:
    from storage.ticket_repository import TicketRepository
    from app.domain.systems.ticket import TicketSystem

    repo = TicketRepository(Path("storage/tickets.db"))
    repo.apply_migrations()
    return TicketSystem(repo)


def _create_procurement_system() -> BaseSystem:
    from app.domain.systems.procurement import ProcurementSystem

    return ProcurementSystem()


def _create_finance_system() -> BaseSystem:
    from app.domain.systems.finance import FinanceSystem

    return FinanceSystem()


def _create_approval_system() -> BaseSystem:
    from app.domain.systems.approval import ApprovalSystem

    return ApprovalSystem()


def _create_hr_system() -> BaseSystem:
    from app.domain.systems.hr import HrSystem

    return HrSystem()


__all__ = [
    "BaseSystem",
    "SystemAction",
    "SystemKey",
    "SystemError",
    "ValidationError",
    "EntityNotFoundError",
    "InvalidStateTransitionError",
    "ForbiddenActionError",
    "DuplicateRequestError",
    "InternalError",
    "SystemResult",
    "SystemRegistry",
    "SystemTransitionEngine",
    "registry",
    "register_all_systems",
]
