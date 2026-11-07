from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .catalog import load_places
from .database import Database
from .errors import APIError
from .routes import map_router, merchant_router, system_router
from .schemas import Error
from .services import MapService


def create_app(db_path=None, demo_mode=None, places_path=None):
    """Create the shared Quest backend. Header identities are development-only."""
    settings = Settings.from_env(db_path, demo_mode, places_path)
    database = Database(settings.database_path)
    service = MapService(settings, database)

    @asynccontextmanager
    async def lifespan(app):
        service.catalog = load_places(settings.places_path)
        database.initialize(service.now())
        yield

    app = FastAPI(title="Quest API", version="0.1.0", lifespan=lifespan,
                  responses={422: {"model": Error}, 404: {"model": Error}})
    app.state.map_service = service
    app.add_middleware(CORSMiddleware,
                       allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-User-Id", "X-Merchant-Id"])

    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        return JSONResponse(status_code=exc.status, content=dict(
            error=exc.code, message=exc.message, demo=service.demo(), **exc.extra))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=dict(error="invalid_request",
                            message="Check request fields, types, and allowed values.", demo=service.demo()))

    app.include_router(map_router)
    app.include_router(merchant_router)
    app.include_router(system_router)
    return app
