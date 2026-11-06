
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.migrations import run_migrations
from app.otari.mcp import OtariMCPClient
from app.reconcile.engine import ReconciliationEngine
from app.txn.store import TransactionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema.
    run_migrations(db_path=settings.tr_db_path)

    # Initialize transaction store and recover interrupted transactions.
    transaction_store = TransactionStore(db_path=settings.tr_db_path)
    recovered_count = transaction_store.recover_on_start()

    print(
        f"Startup recovery completed. "
        f"Recovered {recovered_count} transaction(s)."
    )

    app.state.transaction_store = transaction_store
    app.state.reconciliation_engine = None

    # Initialize reconciliation dependencies when the MCP server is configured.
    if settings.otari_mcp_server_id:
        async with OtariMCPClient(
            base_url=settings.otari_base_url,
            api_key=settings.otari_api_key,
            timeout=settings.otari_timeout,
        ) as otari_client:
            app.state.reconciliation_engine = ReconciliationEngine(
                store=transaction_store,
                otari_client=otari_client,
                server_id=settings.otari_mcp_server_id,
                expected_repository=settings.mcp_github_repo,
            )

            yield
    else:
        yield


app = FastAPI(
    title="TrustRail",
    description="Authorization and transaction-control layer for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


from app.api.routes.reconciliation import router as reconciliation_router

app.include_router(reconciliation_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trustrail",
    }

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.migrations import run_migrations
from app.otari.mcp import OtariMCPClient
from app.reconcile.engine import ReconciliationEngine
from app.txn.store import TransactionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema.
    run_migrations(db_path=settings.tr_db_path)

    # Initialize transaction store and recover interrupted transactions.
    transaction_store = TransactionStore(db_path=settings.tr_db_path)
    recovered_count = transaction_store.recover_on_start()

    print(
        f"Startup recovery completed. "
        f"Recovered {recovered_count} transaction(s)."
    )

    app.state.transaction_store = transaction_store
    app.state.reconciliation_engine = None

    # Initialize reconciliation dependencies when the MCP server is configured.
    if settings.otari_mcp_server_id:
        async with OtariMCPClient(
            base_url=settings.otari_base_url,
            api_key=settings.otari_api_key,
            timeout=settings.otari_timeout,
        ) as otari_client:
            app.state.reconciliation_engine = ReconciliationEngine(
                store=transaction_store,
                otari_client=otari_client,
                server_id=settings.otari_mcp_server_id,
                expected_repository=settings.mcp_github_repo,
            )

            yield
    else:
        yield


app = FastAPI(
    title="TrustRail",
    description="Authorization and transaction-control layer for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


from app.api.routes.reconciliation import router as reconciliation_router

app.include_router(reconciliation_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trustrail",
    }
