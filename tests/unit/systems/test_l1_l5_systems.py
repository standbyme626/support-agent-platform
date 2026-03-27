from __future__ import annotations

import pytest
from pathlib import Path

from app.domain.systems import register_all_systems
from app.domain.systems.procurement import ProcurementSystem
from app.domain.systems.finance import FinanceSystem
from app.domain.systems.approval import ApprovalSystem
from app.domain.systems.hr import HrSystem
from app.domain.systems.ticket import TicketSystem
from storage.ticket_repository import TicketRepository


class TestSystemsRegistration:
    def test_register_all_systems(self, tmp_path: Path) -> None:
        from app.domain.systems import SystemRegistry
        from app.domain.systems.procurement import ProcurementSystem
        from app.domain.systems.finance import FinanceSystem
        from app.domain.systems.approval import ApprovalSystem
        from app.domain.systems.hr import HrSystem
        from app.domain.systems.ticket import TicketSystem

        registry = SystemRegistry()
        registry.reset()
        registry.register(TicketSystem(TicketRepository(tmp_path / "tickets.db")))
        registry.register(ProcurementSystem())
        registry.register(FinanceSystem())
        registry.register(ApprovalSystem())
        registry.register(HrSystem())

        assert registry.has_system("ticket")
        assert registry.has_system("procurement")
        assert registry.has_system("finance")
        assert registry.has_system("approval")
        assert registry.has_system("hr")


class TestProcurementSystem:
    def test_create_procurement_request(self) -> None:
        system = ProcurementSystem()
        result = system.create(
            {
                "requester_id": "EMP-001",
                "item_name": "显示器",
                "category": "IT设备",
                "quantity": 2,
                "budget": 5000,
                "business_reason": "办公需要",
                "urgency": "normal",
            }
        )
        assert result["ok"] is True
        assert result["system"] == "procurement"
        assert result["entity_id"].startswith("PR-")
        assert result["status"] == "draft"

    def test_procurement_lifecycle(self) -> None:
        system = ProcurementSystem()
        result = system.create(
            {
                "requester_id": "EMP-001",
                "item_name": "显示器",
                "quantity": 2,
                "budget": 5000,
            }
        )
        entity_id = result["entity_id"]

        result = system.execute_action(entity_id, "submit", "system", {}, "trace-001")
        assert result["ok"] is True
        assert result["status"] == "pending_approval"

        result = system.execute_action(
            entity_id, "approve", "manager", {"approver_id": "MGR-001"}, "trace-002"
        )
        assert result["ok"] is True
        assert result["status"] == "approved"

    def test_invalid_procurement_action(self) -> None:
        system = ProcurementSystem()
        result = system.create(
            {
                "requester_id": "EMP-001",
                "item_name": "显示器",
                "quantity": 2,
                "budget": 5000,
            }
        )
        entity_id = result["entity_id"]

        result = system.execute_action(
            entity_id, "approve", "manager", {"approver_id": "MGR-001"}, "trace-001"
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_state_transition"


class TestFinanceSystem:
    def test_create_invoice(self) -> None:
        system = FinanceSystem()
        result = system.create(
            {
                "vendor_id": "VND-001",
                "invoice_no": "INV-2026-001",
                "po_no": "PO-001",
                "amount": 10000,
                "currency": "CNY",
                "invoice_date": "2026-03-01",
            }
        )
        assert result["ok"] is True
        assert result["system"] == "finance"
        assert result["status"] == "invoice_received"

    def test_finance_lifecycle(self) -> None:
        system = FinanceSystem()
        result = system.create(
            {
                "vendor_id": "VND-001",
                "invoice_no": "INV-001",
                "amount": 10000,
            }
        )
        entity_id = result["entity_id"]

        result = system.execute_action(
            entity_id, "match", "finance_clerk", {"match_reference": "PO-001"}, "trace-001"
        )
        assert result["ok"] is True
        assert result["status"] == "matching"


class TestApprovalSystem:
    def test_create_approval(self) -> None:
        system = ApprovalSystem()
        result = system.create(
            {
                "request_type": "leave",
                "requester_id": "EMP-001",
                "title": "年假申请",
                "content": "申请3天年假",
            }
        )
        assert result["ok"] is True
        assert result["system"] == "approval"
        assert result["status"] == "submitted"

    def test_approval_lifecycle(self) -> None:
        system = ApprovalSystem()
        result = system.create(
            {
                "request_type": "leave",
                "requester_id": "EMP-001",
                "title": "年假申请",
            }
        )
        entity_id = result["entity_id"]

        result = system.execute_action(entity_id, "submit", "emp", {}, "trace-001")
        assert result["status"] == "pending_approval"

        result = system.execute_action(
            entity_id, "approve", "manager", {"approver_id": "MGR-001"}, "trace-002"
        )
        assert result["ok"] is True
        assert result["status"] == "approved"


class TestHrSystem:
    def test_create_onboarding(self) -> None:
        system = HrSystem()
        result = system.create(
            {
                "candidate_name": "张三",
                "department": "技术部",
                "position": "工程师",
                "manager_id": "MGR-001",
                "start_date": "2026-04-01",
            }
        )
        assert result["ok"] is True
        assert result["system"] == "hr"
        assert result["status"] == "preboarding"

    def test_hr_lifecycle(self) -> None:
        system = HrSystem()
        result = system.create(
            {
                "candidate_name": "李四",
                "department": "市场部",
                "position": "经理",
                "manager_id": "MGR-001",
                "start_date": "2026-04-01",
            }
        )
        entity_id = result["entity_id"]
        assert result["status"] == "preboarding"

        result = system.execute_action(
            entity_id,
            "send_offer",
            "hr",
            {"candidate_name": "李四", "position": "经理"},
            "trace-001",
        )
        assert result["status"] == "submitted"

        result = system.execute_action(entity_id, "submit", "hr", {}, "trace-002")
        assert result["status"] == "pending_approval"

        result = system.execute_action(
            entity_id, "approve", "hr", {"hr_approver_id": "HR-001"}, "trace-003"
        )
        assert result["ok"] is True
        assert result["status"] == "profile_created"


class TestTicketSystem:
    def test_ticket_system_integration(self, tmp_path: Path) -> None:
        repo = TicketRepository(tmp_path / "tickets.db")
        repo.apply_migrations()
        system = TicketSystem(repo)

        result = system.create(
            {
                "channel": "api",
                "session_id": "test-session",
                "thread_id": "test-thread",
                "title": "测试工单",
                "description": "这是一个测试工单",
                "priority": "P2",
            }
        )

        assert result["ok"] is True
        assert result["system"] == "ticket"
        assert result["entity_id"].startswith("TCK-")

        entity_id = result["entity_id"]
        ticket = system.get(entity_id)
        assert ticket is not None
        assert ticket["title"] == "测试工单"
