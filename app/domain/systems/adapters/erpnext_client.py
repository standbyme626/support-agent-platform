from __future__ import annotations

import random
from typing import Any

import requests

from app.domain.systems.adapters.config import ERPNextConfig

DEPENDENCIES = {
    "Purchase Order": {
        "Supplier": {"supplier_name": "Default Supplier", "supplier_group": "Local Suppliers"},
        "Item": {
            "item_code": "STOCK_ITEM",
            "item_name": "Stock Item",
            "item_group": "General",
            "stock_uom": "Pcs",
            "is_stock_item": 1,
        },
    },
    "Purchase Invoice": {
        "Supplier": {"supplier_name": "Default Supplier", "supplier_group": "Local Suppliers"},
        "Item": {
            "item_code": "STOCK_ITEM",
            "item_name": "Stock Item",
            "item_group": "General",
            "stock_uom": "Pcs",
            "is_stock_item": 1,
        },
    },
    "Asset": {
        "Item": {
            "item_code": "STOCK_ITEM",
            "item_name": "Stock Item",
            "item_group": "General",
            "stock_uom": "Pcs",
            "is_stock_item": 1,
        },
    },
    "Employee": {
        "Department": {"department_name": "All Departments"},
        "Designation": {"designation_name": "Staff", "description": "General Staff"},
    },
    "CRM Lead": {
        "Customer": {"customer_name": "Default Customer", "customer_group": "All Customer Groups"},
    },
    "Stock Entry": {
        "Item": {
            "item_code": "STOCK_ITEM",
            "item_name": "Stock Item",
            "item_group": "General",
            "stock_uom": "Pcs",
            "is_stock_item": 1,
        },
    },
}

GENDER_VALUES = ["Male", "Female", "Other"]


_shared_client = None
_shared_config = None


def get_shared_client(config: ERPNextConfig | None = None) -> "ERPNextClient":
    global _shared_client, _shared_config
    if _shared_client is None:
        _shared_config = config or ERPNextConfig()
        _shared_client = ERPNextClient(_shared_config)
    return _shared_client


class ERPNextClient:
    _global_session = None
    _global_sid = None

    def __init__(self, config: ERPNextConfig | None = None):
        self._config = config or ERPNextConfig()

        # 复用全局 session
        if ERPNextClient._global_session is None:
            ERPNextClient._global_session = requests.Session()
            ERPNextClient._global_session.headers.update(
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
            ERPNextClient._global_sid = self._do_login(ERPNextClient._global_session)

        self._session = ERPNextClient._global_session
        self._sid = ERPNextClient._global_sid

    def _do_login(self, session) -> str:
        login_url = f"{self._config.url.rstrip('/')}/api/method/login"
        response = session.post(
            login_url,
            json={"usr": self._config.api_key, "pwd": self._config.api_secret},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("message") != "Logged In":
            raise Exception("Login failed")
        for cookie in session.cookies:
            if cookie.name == "sid":
                return cookie.value
        raise Exception("No session cookie found")

    def _get_cookies(self) -> dict[str, str]:
        return {"sid": self._sid}

    def get_doc(self, doctype: str, name: str) -> dict[str, Any] | None:
        url = f"{self._config.base_url}/{doctype}/{name}"
        response = self._session.get(url, cookies=self._get_cookies(), timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("data")

    def insert(self, doctype: str, data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url}/{doctype}"
        response = self._session.post(url, json=data, cookies=self._get_cookies(), timeout=30)
        response.raise_for_status()
        return response.json().get("data", {})

    def update(self, doctype: str, name: str, data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url}/{doctype}/{name}"
        response = self._session.put(url, json=data, cookies=self._get_cookies(), timeout=30)
        response.raise_for_status()
        return response.json().get("data", {})

    def delete(self, doctype: str, name: str) -> None:
        url = f"{self._config.base_url}/{doctype}/{name}"
        response = self._session.delete(url, cookies=self._get_cookies(), timeout=30)
        response.raise_for_status()

    def list(
        self,
        doctype: str,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
        page: int = 1,
        page_length: int = 20,
    ) -> dict[str, Any]:
        url = f"{self._config.base_url}/{doctype}"
        params: dict[str, Any] = {
            "limit_page_length": page_length,
            "limit_start": (page - 1) * page_length,
        }
        if filters:
            params["filters"] = filters
        if fields:
            params["fields"] = fields
        response = self._session.get(url, params=params, cookies=self._get_cookies(), timeout=30)
        response.raise_for_status()
        return response.json()

    def call_method(
        self, doctype: str, name: str, method: str, args: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self._config.base_url}/{doctype}/{name}"
        payload = {
            "cmd": f"frappe.client.run_doc_method",
            "docs": [{"doctype": doctype, "name": name}],
            "method": method,
            "args": args or {},
        }
        response = self._session.post(url, json=payload, cookies=self._get_cookies(), timeout=60)
        response.raise_for_status()
        return response.json()
