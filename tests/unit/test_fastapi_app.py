from __future__ import annotations

from fastapi.testclient import TestClient

from app.transport.http.fastapi_app import app


class TestFastAPIApp:
    def setup_method(self) -> None:
        self.client = TestClient(app)

    def test_health_check(self) -> None:
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_list_systems(self) -> None:
        response = self.client.get("/api/systems")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["systems"]) == 10
        assert "ticket" in data["systems"]
        assert "procurement" in data["systems"]

    def test_route_intent_procurement(self) -> None:
        response = self.client.post("/api/route", json={"text": "申请采购2台显示器"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["system"] == "procurement"
        assert "confidence" in data

    def test_route_intent_finance(self) -> None:
        response = self.client.post("/api/route", json={"text": "发票有问题需要财务处理"})
        assert response.status_code == 200
        data = response.json()
        assert data["system"] == "finance"

    def test_route_intent_fallback(self) -> None:
        response = self.client.post("/api/route", json={"text": "会议室空调不制冷"})
        assert response.status_code == 200
        data = response.json()
        assert data["system"] == "ticket"

    def test_system_not_found(self) -> None:
        response = self.client.get("/nonexistent/T-001")
        assert response.status_code == 404

    def test_openapi_schema(self) -> None:
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Support Agent Platform API"
        assert "paths" in data
