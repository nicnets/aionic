from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.database import engine, Base, AsyncSessionLocal
from backend.db.seeds import run_all_seeds
from backend.api.main import api_router


import backend.log_store as log_store
log_store.install()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await run_all_seeds(session)

    from backend.db.system_config import get_config_dict
    async with AsyncSessionLocal() as session:
        config = await get_config_dict(session)

    from backend.scheduler.jobs import start_scheduler
    scheduler = start_scheduler(config)

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)

    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Aionic — AI Content Intelligence API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()
