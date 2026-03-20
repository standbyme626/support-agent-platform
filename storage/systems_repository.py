from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from storage.migration_manager import MigrationManager


class SystemRepository:
    def __init__(self, sqlite_path: str | Path, migrations_dir: Path | None = None) -> None:
        self._sqlite_path = Path(sqlite_path)
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        default_migrations = Path(__file__).resolve().parent / "migrations"
        self._migration_manager = MigrationManager(
            sqlite_path, migrations_dir or default_migrations
        )
        self._conn: sqlite3.Connection | None = None

    def apply_migrations(self) -> list[str]:
        return self._migration_manager.apply_all()

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._sqlite_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class ProcurementRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = (
            data.get("id")
            or f"PR-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )

        conn.execute(
            """INSERT INTO procurement_requests 
               (id, status, requester_id, item_name, category, quantity, budget, 
                business_reason, urgency, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "draft",
                data.get("requester_id"),
                data.get("item_name"),
                data.get("category"),
                data.get("quantity"),
                data.get("budget"),
                data.get("business_reason"),
                data.get("urgency", "normal"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM procurement_requests WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        values.append(entity_id)
        conn.execute(
            f"UPDATE procurement_requests SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM procurement_requests {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM procurement_requests {where_sql} LIMIT ? OFFSET ?",
            values + [page_size, offset],
        )
        return [dict(row) for row in cursor.fetchall()], total


class FinanceRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = (
            data.get("id")
            or f"INV-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )

        conn.execute(
            """INSERT INTO finance_invoices 
               (id, status, vendor_id, invoice_no, po_no, receipt_no, amount, 
                currency, invoice_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "invoice_received",
                data.get("vendor_id"),
                data.get("invoice_no"),
                data.get("po_no"),
                data.get("receipt_no"),
                data.get("amount"),
                data.get("currency", "CNY"),
                data.get("invoice_date"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM finance_invoices WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        values.append(entity_id)
        conn.execute(
            f"UPDATE finance_invoices SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM finance_invoices {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM finance_invoices {where_sql} LIMIT ? OFFSET ?",
            values + [page_size, offset],
        )
        return [dict(row) for row in cursor.fetchall()], total


class ApprovalRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = (
            data.get("id")
            or f"AP-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )

        attachments = json.dumps(data.get("attachments", []))
        approver_chain = json.dumps(data.get("approver_chain", []))

        conn.execute(
            """INSERT INTO approval_requests 
               (id, status, request_type, requester_id, title, content, 
                attachments_json, approver_chain_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "submitted",
                data.get("request_type"),
                data.get("requester_id"),
                data.get("title"),
                data.get("content"),
                attachments,
                approver_chain,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if "attachments_json" in result:
                result["attachments"] = json.loads(result.pop("attachments_json"))
            if "approver_chain_json" in result:
                result["approver_chain"] = json.loads(result.pop("approver_chain_json"))
            return result
        return None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at", "attachments", "approver_chain"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if "attachments" in data:
            set_clauses.append("attachments_json = ?")
            values.append(json.dumps(data["attachments"]))
        if "approver_chain" in data:
            set_clauses.append("approver_chain_json = ?")
            values.append(json.dumps(data["approver_chain"]))

        values.append(entity_id)
        conn.execute(
            f"UPDATE approval_requests SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM approval_requests {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM approval_requests {where_sql} LIMIT ? OFFSET ?",
            values + [page_size, offset],
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if "attachments_json" in result:
                result["attachments"] = json.loads(result.pop("attachments_json"))
            if "approver_chain_json" in result:
                result["approver_chain"] = json.loads(result.pop("approver_chain_json"))
            results.append(result)
        return results, total


class HrRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = (
            data.get("id")
            or f"ONB-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
        )

        accounts = json.dumps(data.get("accounts", []))
        devices = json.dumps(data.get("devices", []))

        conn.execute(
            """INSERT INTO hr_onboardings 
               (id, status, candidate_name, department, position, manager_id, 
                start_date, employee_id, accounts_json, devices_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "preboarding",
                data.get("candidate_name"),
                data.get("department"),
                data.get("position"),
                data.get("manager_id"),
                data.get("start_date"),
                data.get("employee_id"),
                accounts,
                devices,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM hr_onboardings WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if "accounts_json" in result:
                result["accounts"] = json.loads(result.pop("accounts_json"))
            if "devices_json" in result:
                result["devices"] = json.loads(result.pop("devices_json"))
            return result
        return None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at", "accounts", "devices"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if "accounts" in data:
            set_clauses.append("accounts_json = ?")
            values.append(json.dumps(data["accounts"]))
        if "devices" in data:
            set_clauses.append("devices_json = ?")
            values.append(json.dumps(data["devices"]))

        values.append(entity_id)
        conn.execute(
            f"UPDATE hr_onboardings SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM hr_onboardings {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM hr_onboardings {where_sql} LIMIT ? OFFSET ?",
            values + [page_size, offset],
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if "accounts_json" in result:
                result["accounts"] = json.loads(result.pop("accounts_json"))
            if "devices_json" in result:
                result["devices"] = json.loads(result.pop("devices_json"))
            results.append(result)
        return results, total


class AssetRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = data.get("id") or f"ASSET-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """INSERT INTO assets 
               (id, status, asset_tag, name, category, model, serial_number, 
                location, assigned_to, purchase_date, warranty_expires, value, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "requested",
                data.get("asset_tag"),
                data.get("name"),
                data.get("category"),
                data.get("model"),
                data.get("serial_number"),
                data.get("location"),
                data.get("assigned_to"),
                data.get("purchase_date"),
                data.get("warranty_expires"),
                data.get("value"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM assets WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        values.append(entity_id)
        conn.execute(f"UPDATE assets SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM assets {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM assets {where_sql} LIMIT ? OFFSET ?", values + [page_size, offset]
        )
        return [dict(row) for row in cursor.fetchall()], total


class KbRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = data.get("id") or f"KB-{uuid.uuid4().hex[:8].upper()}"

        tags = json.dumps(data.get("tags", []))

        conn.execute(
            """INSERT INTO kb_articles 
               (id, status, title, content, category, tags_json, author_id, 
                version, views, helpful, not_helpful, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "draft",
                data.get("title"),
                data.get("content"),
                data.get("category"),
                tags,
                data.get("author_id"),
                1,
                0,
                0,
                0,
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM kb_articles WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if "tags_json" in result:
                result["tags"] = json.loads(result.pop("tags_json"))
            return result
        return None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at", "tags"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if "tags" in data:
            set_clauses.append("tags_json = ?")
            values.append(json.dumps(data["tags"]))

        values.append(entity_id)
        conn.execute(f"UPDATE kb_articles SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM kb_articles {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM kb_articles {where_sql} LIMIT ? OFFSET ?", values + [page_size, offset]
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if "tags_json" in result:
                result["tags"] = json.loads(result.pop("tags_json"))
            results.append(result)
        return results, total


class CrmRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = data.get("id") or f"CRM-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """INSERT INTO crm_cases 
               (id, status, case_type, customer_id, customer_name, contact_email, 
                contact_phone, subject, description, priority, assigned_to, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "new",
                data.get("case_type"),
                data.get("customer_id"),
                data.get("customer_name"),
                data.get("contact_email"),
                data.get("contact_phone"),
                data.get("subject"),
                data.get("description"),
                data.get("priority", "medium"),
                data.get("assigned_to"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM crm_cases WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        values.append(entity_id)
        conn.execute(f"UPDATE crm_cases SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM crm_cases {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM crm_cases {where_sql} LIMIT ? OFFSET ?", values + [page_size, offset]
        )
        return [dict(row) for row in cursor.fetchall()], total


class ProjectRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = data.get("id") or f"PRJ-{uuid.uuid4().hex[:8].upper()}"

        milestones = json.dumps(data.get("milestones", []))
        resources = json.dumps(data.get("resources", []))

        conn.execute(
            """INSERT INTO projects 
               (id, status, name, description, owner_id, start_date, end_date, 
                milestones_json, resources_json, budget, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "requested",
                data.get("name"),
                data.get("description"),
                data.get("owner_id"),
                data.get("start_date"),
                data.get("end_date"),
                milestones,
                resources,
                data.get("budget"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM projects WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if "milestones_json" in result:
                result["milestones"] = json.loads(result.pop("milestones_json"))
            if "resources_json" in result:
                result["resources"] = json.loads(result.pop("resources_json"))
            return result
        return None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at", "milestones", "resources"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if "milestones" in data:
            set_clauses.append("milestones_json = ?")
            values.append(json.dumps(data["milestones"]))
        if "resources" in data:
            set_clauses.append("resources_json = ?")
            values.append(json.dumps(data["resources"]))

        values.append(entity_id)
        conn.execute(f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM projects {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM projects {where_sql} LIMIT ? OFFSET ?", values + [page_size, offset]
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if "milestones_json" in result:
                result["milestones"] = json.loads(result.pop("milestones_json"))
            if "resources_json" in result:
                result["resources"] = json.loads(result.pop("resources_json"))
            results.append(result)
        return results, total


class SupplyChainRepository(SystemRepository):
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()
        entity_id = data.get("id") or f"SC-{uuid.uuid4().hex[:8].upper()}"

        items = json.dumps(data.get("items", []))

        conn.execute(
            """INSERT INTO supply_chain_orders 
               (id, status, order_type, supplier_id, items_json, total_amount, 
                expected_delivery, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id,
                "pending",
                data.get("order_type"),
                data.get("supplier_id"),
                items,
                data.get("total_amount"),
                data.get("expected_delivery"),
                data.get("notes"),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(entity_id)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM supply_chain_orders WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if "items_json" in result:
                result["items"] = json.loads(result.pop("items_json"))
            return result
        return None

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        conn = self.get_connection()
        now = datetime.now(UTC).isoformat()

        set_clauses = ["updated_at = ?"]
        values = [now]

        for key, value in data.items():
            if key not in ("id", "created_at", "items"):
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if "items" in data:
            set_clauses.append("items_json = ?")
            values.append(json.dumps(data["items"]))

        values.append(entity_id)
        conn.execute(
            f"UPDATE supply_chain_orders SET {', '.join(set_clauses)} WHERE id = ?", values
        )
        conn.commit()
        return self.get(entity_id)

    def list(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self.get_connection()
        filters = filters or {}

        where_clauses = []
        values = []
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            values.append(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cursor = conn.execute(f"SELECT COUNT(*) FROM supply_chain_orders {where_sql}", values)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM supply_chain_orders {where_sql} LIMIT ? OFFSET ?",
            values + [page_size, offset],
        )
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if "items_json" in result:
                result["items"] = json.loads(result.pop("items_json"))
            results.append(result)
        return results, total
