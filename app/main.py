from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.migrations import run_migrations


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations(db_path=settings.tr_db_path)
    yield


app = FastAPI(
    title="TrustRail",
    description="Authorization and transaction-control layer for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trustrail",
    }