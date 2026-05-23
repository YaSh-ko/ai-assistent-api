"""
delëz API - Main Application Entry Point
"""
import logging
import os
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

import os
from src.core.config import settings

# Force common library (which uses os.getenv) to use our robustly constructed URL
# This fixes the issue where common/database/connection.py sees an empty/broken DATABASE_URL
try:
    if settings.db_url:
        os.environ["DATABASE_URL"] = settings.db_url
        if settings.DEBUG:
            print("DEBUG: Injected DATABASE_URL into env for common lib")
except Exception:
    pass

from src.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    InvalidTokenException,
    UnauthorizedException,
    BadRequestException,
    JwtConfigurationException,
    TooManyRequestsException,
)
from src.core.rate_limit import global_rate_limiter
from src.api.v1.routes import (
    health, 
    user, 
    auth,
    graph,
    conversations,
    messages,
    entries,
    experiments,
    goals,
    analyses,
    audio,
    beta_test,
    concepts,
    virtual_fields,
    imports,
    insights,
    memoirs,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    first_hop = forwarded.split(",")[0].strip() if forwarded else ""
    return first_hop or (request.client.host if request.client else "unknown")


def _is_rate_limit_excluded(path: str) -> bool:
    excluded = [p.strip() for p in settings.RATE_LIMIT_EXCLUDE_PATHS.split(",") if p.strip()]
    return any(path.startswith(p) for p in excluded)


def _ensure_cors_origins_list() -> None:
    """Приводит CORS_ORIGINS к списку и логирует."""
    logger.info("CORS origins configured: %s", settings.CORS_ORIGINS)
    if isinstance(settings.CORS_ORIGINS, list):
        return
    logger.warning("CORS_ORIGINS is not a list: %s, converting...", settings.CORS_ORIGINS)
    if isinstance(settings.CORS_ORIGINS, str):
        settings.CORS_ORIGINS = [
            o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
        ]


def _add_cors_to_response(response: JSONResponse, request: Request) -> JSONResponse:
    """Добавляет CORS-заголовки к ответу при разрешённом origin."""
    origin = request.headers.get("Origin")
    if origin and origin in settings.CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin, X-Requested-With"
    return response


def _setup_cors(app: FastAPI) -> None:
    """Подключает стандартный CORSMiddleware для автоматической обработки CORS."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With",
            "Access-Control-Request-Method", "Access-Control-Request-Headers",
        ],
        expose_headers=[
            "Content-Type", "Authorization",
            "Access-Control-Allow-Origin", "Access-Control-Allow-Credentials",
        ],
        max_age=3600,
    )


def _register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует глобальные обработчики исключений."""

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        r = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Validation Error", "message": "Invalid request data", "details": exc.errors()},
        )
        return _add_cors_to_response(r, request)

    @app.exception_handler(SQLAlchemyError)
    async def _db_handler(request: Request, exc: SQLAlchemyError):
        logger.error("Database error: %s", exc, exc_info=True)
        err_str = str(exc).lower()
        msg = "An error occurred while processing your request"
        if settings.DEBUG:
            msg = f"Database error: {exc}"
        if "connection" in err_str or "connect" in err_str:
            msg = "Database connection error. Please check database configuration."
        elif "constraint" in err_str or "unique" in err_str:
            msg = "Database constraint violation" if not settings.DEBUG else f"Database constraint error: {exc}"
        r = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Database Error", "message": msg, "type": exc.__class__.__name__ if settings.DEBUG else None},
        )
        return _add_cors_to_response(r, request)

    @app.exception_handler(InvalidCredentialsException)
    @app.exception_handler(UserAlreadyExistsException)
    @app.exception_handler(InvalidTokenException)
    @app.exception_handler(UnauthorizedException)
    @app.exception_handler(BadRequestException)
    @app.exception_handler(JwtConfigurationException)
    @app.exception_handler(TooManyRequestsException)
    async def _auth_handler(request: Request, exc: Exception):
        code = getattr(exc, "status_code", status.HTTP_400_BAD_REQUEST)
        detail = getattr(exc, "detail", str(exc))
        r = JSONResponse(status_code=code, content={"error": exc.__class__.__name__, "message": detail})
        return _add_cors_to_response(r, request)

    @app.exception_handler(Exception)
    async def _general_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        msg = "An unexpected error occurred" if not settings.DEBUG else str(exc)
        r = JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Internal Server Error", "message": msg})
        return _add_cors_to_response(r, request)


def _register_routers(app: FastAPI) -> None:
    """Подключает все роутеры."""
    app.include_router(health.router, prefix="/v1", tags=["system"])
    app.include_router(user.router, prefix="/v1/user", tags=["user"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(graph.router, prefix="/v1/graph", tags=["graph"])
    app.include_router(conversations.router, prefix="/v1/conversations", tags=["conversations"])
    app.include_router(messages.router, prefix="/v1", tags=["messages"])
    app.include_router(entries.router, prefix="/v1/entries", tags=["entries"])
    app.include_router(experiments.router, prefix="/v1/experiments", tags=["experiments"])
    app.include_router(goals.router, prefix="/v1/goals", tags=["goals"])
    app.include_router(analyses.router, prefix="/v1/analyses", tags=["analyses"])
    app.include_router(audio.router, prefix="/v1", tags=["audio"])
    app.include_router(beta_test.router, prefix="/v1/beta-test", tags=["beta-test"])
    app.include_router(concepts.router, prefix="/v1/concepts", tags=["concepts"])
    app.include_router(virtual_fields.router, prefix="/v1/virtual-fields", tags=["virtual-fields"])
    app.include_router(imports.router, prefix="/v1/import", tags=["import"])
    app.include_router(insights.router, prefix="/v1/insights", tags=["insights"])
    app.include_router(memoirs.router, prefix="/v1/memoirs", tags=["memoirs"])






def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Backend API for delëz project",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        root_path="/api",
    )

    _ensure_cors_origins_list()
    # Добавляем WWW вариант в список разрешенных
    if "https://delez.tech" in settings.CORS_ORIGINS and "https://www.delez.tech" not in settings.CORS_ORIGINS:
        settings.CORS_ORIGINS.append("https://www.delez.tech")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    _register_exception_handlers(app)
    _register_routers(app)

    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.get("/api/v1/health", tags=["health"])
    @app.get("/v1/health", tags=["health"])
    async def health_check():
        return {"status": "ok", "service": "api"}

    @app.get("/api/metrics")
    @app.get("/metrics")
    async def metrics_handler():
        return Response(content="metrics data would be here", media_type="text/plain")

    @app.middleware("http")
    async def handle_options_requests(request: Request, call_next):
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin", "*")
            requested_headers = request.headers.get(
                "Access-Control-Request-Headers",
                "Content-Type, Authorization, X-Requested-With, Accept, Origin, Cookie"
            )
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": requested_headers,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "86400",
                    "Vary": "Origin, Access-Control-Request-Headers",
                },
            )
        response = await call_next(request)
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Vary"] = "Origin"
        return response

    @app.middleware("http")
    async def _global_rate_limit_mw(request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        path = request.url.path
        if request.method == "OPTIONS" or _is_rate_limit_excluded(path):
            return await call_next(request)

        ip = _extract_client_ip(request)
        key = f"{ip}:{path}"
        allowed = global_rate_limiter().allow(
            key,
            limit=settings.RATE_LIMIT_MAX_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
        if not allowed:
            r = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "TooManyRequestsException",
                    "message": "Too many requests. Please try again later.",
                },
            )
            return _add_cors_to_response(r, request)
        return await call_next(request)

    return app


app = create_app()
