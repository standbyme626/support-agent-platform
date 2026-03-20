from __future__ import annotations

import re
from typing import Any

from app.transport.http.systems.routes import create_systems_routes


class SystemsRequestHandler:
    def __init__(self, routes: dict[str, Any]) -> None:
        self._routes = routes

    def handle(self, method: str, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        for route_key, route_config in self._routes.items():
            if route_config["method"] != method:
                continue

            path_template = route_config["path_template"]
            match_result = self._match_path(path_template, path)

            if match_result is None:
                continue

            handler = route_config["handler"]
            router = route_config["router"]
            intent_router = route_config.get("intent_router")

            if match_result["system"] and match_result.get("entity_id"):
                action = match_result.get("action")
                if action:
                    return handler(
                        system_key=match_result["system"],
                        entity_id=match_result["entity_id"],
                        action=action,
                        body=body,
                        router=router,
                    )
                return handler(
                    system_key=match_result["system"],
                    entity_id=match_result["entity_id"],
                    router=router,
                )
            elif match_result["system"]:
                return handler(
                    system_key=match_result["system"],
                    body=body,
                    router=router,
                    intent_router=intent_router,
                )

        return 404, {"ok": False, "error": "Route not found"}

    @staticmethod
    def _match_path(template: str, path: str) -> dict[str, Any] | None:
        pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", template)
        pattern = f"^{pattern}$"

        match = re.match(pattern, path)
        if match is None:
            return None

        return match.groupdict()
