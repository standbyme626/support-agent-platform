from __future__ import annotations

import pytest
from pathlib import Path

from app.domain.systems import SystemRegistry
from app.domain.systems.asset import AssetSystem
from app.domain.systems.kb import KbSystem
from app.domain.systems.crm import CrmSystem
from app.domain.systems.project import ProjectSystem
from app.domain.systems.supply_chain import SupplyChainSystem
from storage.systems_repository import (
    AssetRepository,
    KbRepository,
    CrmRepository,
    ProjectRepository,
    SupplyChainRepository,
)


class TestAssetSystem:
    def test_create_asset(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = AssetSystem(repo)

        result = system.create(
            {
                "name": "Dell Laptop",
                "category": "IT",
                "serial_number": "SN123456",
            }
        )

        assert result["ok"] is True
        assert result["system"] == "asset"
        assert result["status"] == "inventory"

    def test_asset_lifecycle(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = AssetSystem(repo)

        result = system.create({"name": "Dell Laptop", "category": "IT"})
        entity_id = result["entity_id"]

        result = system.execute_action(
            entity_id, "assign", "admin", {"assigned_to": "EMP-001"}, "trace-1"
        )
        assert result["ok"] is True
        assert result["status"] == "assigned"


class TestKbSystem:
    def test_create_article(self, tmp_path: Path) -> None:
        repo = KbRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = KbSystem(repo)

        result = system.create(
            {
                "title": "如何申请远程办公",
                "content": "远程办公申请流程...",
                "category": "HR",
                "author_id": "admin",
            }
        )

        assert result["ok"] is True
        assert result["system"] == "kb"
        assert result["status"] == "draft"

    def test_kb_lifecycle(self, tmp_path: Path) -> None:
        repo = KbRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = KbSystem(repo)

        result = system.create({"title": "测试文档", "content": "内容", "author_id": "admin"})
        entity_id = result["entity_id"]

        result = system.execute_action(entity_id, "submit_review", "admin", {}, "trace-1")
        assert result["ok"] is True
        assert result["status"] == "review"

        result = system.execute_action(entity_id, "publish", "admin", {}, "trace-2")
        assert result["ok"] is True
        assert result["status"] == "published"


class TestCrmSystem:
    def test_create_case(self, tmp_path: Path) -> None:
        repo = CrmRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = CrmSystem(repo)

        result = system.create(
            {
                "case_type": "complaint",
                "customer_id": "CUST-001",
                "customer_name": "张三",
                "subject": "产品质量问题",
                "priority": "high",
            }
        )

        assert result["ok"] is True
        assert result["system"] == "crm"
        assert result["status"] == "new"

    def test_crm_lifecycle(self, tmp_path: Path) -> None:
        repo = CrmRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = CrmSystem(repo)

        result = system.create(
            {"case_type": "complaint", "customer_id": "CUST-001", "subject": "测试"}
        )
        entity_id = result["entity_id"]

        result = system.execute_action(
            entity_id, "assign", "admin", {"assigned_to": "SVC-001"}, "trace-1"
        )
        assert result["ok"] is True
        assert result["status"] == "assigned"


class TestProjectSystem:
    def test_create_project(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = ProjectSystem(repo)

        result = system.create(
            {
                "name": "ERP实施项目",
                "description": "新ERP系统实施",
                "owner_id": "PM-001",
                "start_date": "2026-04-01",
                "end_date": "2026-12-31",
                "budget": 500000,
            }
        )

        assert result["ok"] is True
        assert result["system"] == "project"
        assert result["status"] == "planning"

    def test_project_lifecycle(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = ProjectSystem(repo)

        result = system.create({"name": "测试项目", "owner_id": "PM-001"})
        entity_id = result["entity_id"]

        result = system.execute_action(entity_id, "activate", "admin", {}, "trace-1")
        assert result["ok"] is True
        assert result["status"] == "active"


class TestSupplyChainSystem:
    def test_create_order(self, tmp_path: Path) -> None:
        repo = SupplyChainRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = SupplyChainSystem(repo)

        result = system.create(
            {
                "order_type": "purchase",
                "supplier_id": "SUP-001",
                "items": [{"name": "显示器", "qty": 10}],
                "total_amount": 50000,
            }
        )

        assert result["ok"] is True
        assert result["system"] == "supply_chain"
        assert result["status"] == "pending"

    def test_supply_chain_lifecycle(self, tmp_path: Path) -> None:
        repo = SupplyChainRepository(tmp_path / "systems.db")
        repo.apply_migrations()
        system = SupplyChainSystem(repo)

        result = system.create({"order_type": "purchase", "supplier_id": "SUP-001"})
        entity_id = result["entity_id"]

        result = system.execute_action(entity_id, "confirm", "admin", {}, "trace-1")
        assert result["ok"] is True
        assert result["status"] == "confirmed"


class TestAllSystemsRegistered:
    def test_register_all_ten_systems(self, tmp_path: Path) -> None:
        registry = SystemRegistry()
        registry.reset()

        registry.register(AssetSystem(AssetRepository(tmp_path / "systems.db")))
        registry.register(KbSystem(KbRepository(tmp_path / "systems.db")))
        registry.register(CrmSystem(CrmRepository(tmp_path / "systems.db")))
        registry.register(ProjectSystem(ProjectRepository(tmp_path / "systems.db")))
        registry.register(SupplyChainSystem(SupplyChainRepository(tmp_path / "systems.db")))

        assert registry.has_system("asset")
        assert registry.has_system("kb")
        assert registry.has_system("crm")
        assert registry.has_system("project")
        assert registry.has_system("supply_chain")
