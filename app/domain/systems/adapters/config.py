from __future__ import annotations

import os
from typing import Any


class ERPNextConfig:
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
    ):
        self.url = url or os.getenv("ERPNEXT_URL") or "http://localhost:8080"
        self.api_key = api_key or os.getenv("ERPNEXT_API_KEY") or "Administrator"
        self.api_secret = api_secret or os.getenv("ERPNEXT_API_SECRET") or "admin"

    @property
    def base_url(self) -> str:
        return f"{self.url.rstrip('/')}/api/resource"

    @property
    def auth(self) -> tuple[str, str]:
        return (self.api_key, self.api_secret)
