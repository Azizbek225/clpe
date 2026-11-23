import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (jadvallarni ro'yxatga olish)
from app.api.v1 import api_router
from app.api.v1.ws import router as ws_router
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.labengine import orchestrator
from app.plugins import load_plugins
from app.services.seed import seed_all

logging.basicConfig(level=logging.INFO)
settings = get_settings()


async def _janitor() -> None:
    """Celery ishlatilmasa: muddati tugagan laboratoriyalarni tozalash (9.12)."""
    while True:
        await asyncio.sleep(60)
        with contextlib.suppress(Exception):
            await asyncio.to_thread(orchestrator.cleanup_expired)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    load_plugins()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)
    task = None if settings.use_celery else asyncio.create_task(_janitor())
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="CLPE API",
    description="Cybersecurity Learning & Practice Environment — REST API (OpenAPI/Swagger: /docs)",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "provider": settings.lab_provider}
