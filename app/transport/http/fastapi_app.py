from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.transport.http.api import api_router
from app.transport.http.systems.routes import create_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.domain.systems import register_all_systems

    registry = register_all_systems()
    app.state.registry = registry
    yield


def create_app(runtime: Any | None = None) -> FastAPI:
    app = FastAPI(
        title="Support Agent Platform API",
        description="Workflow-first support ticket platform with ten-system integration",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": str(exc),
                },
            },
        )

    app.include_router(api_router)
    systems_router, intent_router = create_router()
    app.include_router(systems_router)
    app.include_router(intent_router)

    return app


app = create_app()
