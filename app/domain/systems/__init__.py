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
    registry.register(_create_asset_system())
    registry.register(_create_kb_system())
    registry.register(_create_crm_system())
    registry.register(_create_project_system())
    registry.register(_create_supply_chain_system())

    return registry


def _create_ticket_system() -> BaseSystem:
    from storage.ticket_repository import TicketRepository
    from app.domain.systems.ticket import TicketSystem

    repo = TicketRepository(Path("storage/tickets.db"))
    repo.apply_migrations()
    return TicketSystem(repo)


def _create_procurement_system() -> BaseSystem:
    from app.domain.systems.procurement import ProcurementSystem
    from storage.systems_repository import ProcurementRepository

    repo = ProcurementRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return ProcurementSystem(repo)


def _create_finance_system() -> BaseSystem:
    from app.domain.systems.finance import FinanceSystem
    from storage.systems_repository import FinanceRepository

    repo = FinanceRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return FinanceSystem(repo)


def _create_approval_system() -> BaseSystem:
    from app.domain.systems.approval import ApprovalSystem
    from storage.systems_repository import ApprovalRepository

    repo = ApprovalRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return ApprovalSystem(repo)


def _create_hr_system() -> BaseSystem:
    from app.domain.systems.hr import HrSystem
    from storage.systems_repository import HrRepository

    repo = HrRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return HrSystem(repo)


def _create_asset_system() -> BaseSystem:
    from app.domain.systems.asset import AssetSystem
    from storage.systems_repository import AssetRepository

    repo = AssetRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return AssetSystem(repo)


def _create_kb_system() -> BaseSystem:
    from app.domain.systems.kb import KbSystem
    from storage.systems_repository import KbRepository

    repo = KbRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return KbSystem(repo)


def _create_crm_system() -> BaseSystem:
    from app.domain.systems.crm import CrmSystem
    from storage.systems_repository import CrmRepository

    repo = CrmRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return CrmSystem(repo)


def _create_project_system() -> BaseSystem:
    from app.domain.systems.project import ProjectSystem
    from storage.systems_repository import ProjectRepository

    repo = ProjectRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return ProjectSystem(repo)


def _create_supply_chain_system() -> BaseSystem:
    from app.domain.systems.supply_chain import SupplyChainSystem
    from storage.systems_repository import SupplyChainRepository

    repo = SupplyChainRepository(Path("storage/systems.db"))
    repo.apply_migrations()
    return SupplyChainSystem(repo)


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
