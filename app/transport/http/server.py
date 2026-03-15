from __future__ import annotations

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse


def build_http_handler(
    *,
    runtime: Any,
    dispatch_request: Callable[..., Any],
    request_id_factory: Callable[[str | None], str],
    error_factory: Callable[..., Any],
) -> type[BaseHTTPRequestHandler]:
    class OpsApiHandler(BaseHTTPRequestHandler):
        server_version = "SupportAgentOpsAPI/1.0"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PATCH(self) -> None:
            self._dispatch("PATCH")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            parsed = urlparse(self.path)
            query = {
                key: values[-1]
                for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                if values
            }
            request_id = self.headers.get("X-Request-Id")
            body: dict[str, Any] | None = None
            if method in {"POST", "PATCH"}:
                body = self._read_json_body()
                if body is None:
                    response = error_factory(
                        request_id_factory(request_id),
                        code="invalid_json",
                        message="request body must be a JSON object",
                    )
                    self._write_json(response.status, response.payload)
                    return

            response = dispatch_request(
                runtime,
                method=method,
                path=parsed.path,
                query=query,
                body=body,
                request_id=request_id,
            )
            self._write_json(response.status, response.payload)

        def _read_json_body(self) -> dict[str, Any] | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return {}
            try:
                length = int(raw_length)
            except ValueError:
                return None
            if length <= 0:
                return {}
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None
            return payload

        def _write_json(self, status: Any, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(int(getattr(status, "value", status)))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    return OpsApiHandler
