from __future__ import annotations

import pytest

from app.domain.systems import (
    BaseSystem,
    SystemKey,
    SystemRegistry,
    SystemResult,
)
from app.application.systems import SystemIntentRouter, SystemRuntimeRouter


class TestSystemKey:
    def test_all_returns_ten_systems(self) -> None:
        systems = SystemKey.all()
        assert len(systems) == 10
        assert "ticket" in systems
        assert "procurement" in systems
        assert "finance" in systems
        assert "approval" in systems
        assert "hr" in systems
        assert "asset" in systems
        assert "kb" in systems
        assert "crm" in systems
        assert "project" in systems
        assert "supply_chain" in systems


class TestSystemRegistry:
    def test_singleton(self) -> None:
        registry1 = SystemRegistry()
        registry2 = SystemRegistry()
        assert registry1 is registry2

    def test_register_and_get(self) -> None:
        registry = SystemRegistry()
        registry.reset()

        class MockSystem(BaseSystem):
            @property
            def system_key(self) -> str:
                return "test"

            @property
            def entity_type(self) -> str:
                return "test_entity"

            @property
            def id_prefix(self) -> str:
                return "TST"

            @property
            def lifecycle(self) -> tuple[str, ...]:
                return ("new", "active", "closed")

            @property
            def terminal_status(self) -> str:
                return "closed"

            def create(self, payload: dict) -> dict:
                return {}

            def get(self, entity_id: str) -> dict | None:
                return None

            def list(self, filters=None, page=1, page_size=20) -> dict:
                return {"items": [], "total": 0}

            def execute_action(
                self, entity_id: str, action: str, operator_id: str, payload: dict, trace_id: str
            ) -> dict:
                return {}

        system = MockSystem()
        registry.register(system)

        assert registry.has_system("test")
        assert registry.get("test") is system
        assert registry.get("nonexistent") is None

    def test_list_systems(self) -> None:
        registry = SystemRegistry()
        registry.reset()
        systems = registry.list_systems()
        assert isinstance(systems, list)


class TestSystemResult:
    def test_success_result(self) -> None:
        result = SystemResult.success(
            system="ticket",
            entity_type="ticket",
            entity_id="T-001",
            status="new",
            summary="Test ticket",
        )
        assert result.ok is True
        assert result.system == "ticket"
        assert result.entity_id == "T-001"

    def test_failure_result(self) -> None:
        result = SystemResult.failure(
            system="ticket",
            entity_type="ticket",
            entity_id="T-001",
            status="error",
            error_code="not_found",
            error_message="Ticket not found",
        )
        assert result.ok is False
        assert result.error is not None
        assert result.error["code"] == "not_found"


class TestSystemIntentRouter:
    def test_route_procurement(self) -> None:
        router = SystemIntentRouter()
        assert router.route("申请采购2台显示器") == SystemKey.PROCUREMENT

    def test_route_finance(self) -> None:
        router = SystemIntentRouter()
        assert router.route("发票有问题需要财务处理") == SystemKey.FINANCE

    def test_route_ticket_fallback(self) -> None:
        router = SystemIntentRouter()
        assert router.route("会议室空调不制冷") == SystemKey.TICKET

    def test_route_with_confidence(self) -> None:
        router = SystemIntentRouter()
        system, confidence = router.route_with_confidence("申请采购2台显示器")
        assert system == SystemKey.PROCUREMENT
        assert 0 < confidence <= 1.0
