
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.migrations import run_migrations
from app.txn.store import TransactionStore


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Initialize database schema.
    run_migrations(db_path=settings.tr_db_path)

    # Recover transactions left in DISPATCHING after a crash.
    transaction_store = TransactionStore(db_path=settings.tr_db_path)
    recovered_count = transaction_store.recover_on_start()

    print(
        f"Startup recovery completed. "
        f"Recovered {recovered_count} transaction(s)."
    )

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
