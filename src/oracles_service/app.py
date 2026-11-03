from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from controlplane_api.exceptions import ForbiddenException, UnauthorizedException
from controlplane_api.logging import configure_logging
from controlplane_api.utils import get_logger
from controlplane_api.config import settings
from api.infrastructure.messaging.tenant_event_publisher import (
    install_tenant_event_publisher,
    set_tenant_event_publisher,
    shutdown_tenant_event_publisher,
)
from controlplane_tenancy.db_session import configure_session_maker
from controlplane_api.service_cors import add_optional_service_cors
from controlplane_api.health import router as health_router
from controlplane_api.version import router as version_router
from controlplane_db.session import normalize_database_url
from oracles_service.interfaces.api.routes import router as oracles_router
from oracles_service.middleware import OraclesServiceDbMiddleware
from oracles_service.upstream import AttestUpstream

logger = get_logger(__name__)


def create_app(
    *,
    test_event_sink: list | None = None,
    enable_db_middleware: bool = True,
    service_name: str | None = None,
    attest_upstream: AttestUpstream | None = None,
) -> FastAPI:
    svc_name = service_name or settings.service_name

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        engine = None
        if enable_db_middleware:
            engine = create_async_engine(normalize_database_url(settings.database_url))
            maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
            configure_session_maker(maker)
            app.state.async_engine = engine

        if test_event_sink is not None:

            class _ListSink:
                async def publish(
                    self,
                    *,
                    tenant_id,
                    event_type: str,
                    payload: dict,
                    correlation_id: str | None = None,
                ) -> None:
                    test_event_sink.append(
                        {
                            "tenant_id": tenant_id,
                            "event_type": event_type,
                            "payload": payload,
                            "correlation_id": correlation_id,
                        }
                    )

            set_tenant_event_publisher(_ListSink())
        else:
            await install_tenant_event_publisher(service_name=svc_name)

        yield

        await shutdown_tenant_event_publisher()
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="Panopticon oracles",
        description=(
            "Open product: POST /api/v1/oracles/v0/attest observes a public "
            "attestation or relay subject via a mockable upstream. Looks like "
            "a crypto relay/validator — not a privileged social backend. "
            "Does not run SIWE / ERC-1271 / ENS, write Gun, or merge "
            "Hypermesh / s3r.ch login."
        ),
        version="0.1.0",
    )

    if attest_upstream is not None:
        app.state.attest_upstream = attest_upstream

    @app.exception_handler(UnauthorizedException)
    async def _unauthorized(_: Request, ex: UnauthorizedException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": ex.message},
        )

    @app.exception_handler(ForbiddenException)
    async def _forbidden(_: Request, ex: ForbiddenException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": ex.message},
        )

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description or "",
            routes=app.routes,
        )
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-Api-Key",
            "description": (
                "Product API key (prefix.secret) plus X-Tenant-ID. "
                "Machine/service credential for integrators. "
                "s3r.ch later hops SIWE on its own Next origin, then calls "
                "attest with this key — Keycloak is not s3r.ch login."
            ),
        }
        schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API key or exchange JWT",
            "description": (
                "Same product API key as Bearer, or a gateway-minted "
                "API-key exchange JWT with purpose=service. "
                "Not Keycloak-as-s3r.ch-login. Not SIWE-as-Panopticon-login."
            ),
        }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    if enable_db_middleware:
        app.add_middleware(OraclesServiceDbMiddleware)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(version_router)
    app.include_router(oracles_router, prefix="/api/v1")
    add_optional_service_cors(app, env_var="ORACLES_SERVICE_CORS_ORIGINS")
    logger.info("Oracles service: health + /api/v1/oracles/v0/attest + optional CORS")
    from controlplane_api.metrics import install_http_metrics

    install_http_metrics(app)
    return app


app = create_app()
