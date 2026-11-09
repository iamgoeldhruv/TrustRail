from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.dispatcher import AgentToolDispatcher
from app.agent.evaluation import ProposalEvaluationService
from app.agent.orchestrator import AgentOrchestrator
from app.agent.proposal_service import ProposalService
from app.agent.tool_handlers import AgentToolHandlers
from app.api.routes.dry_run import router as dryrun_router
from app.api.routes.policy_compilation import router as policy_compilation_router
from app.api.routes.reconciliation import router as reconciliation_router
from app.core.config import settings
from app.db.migrations import run_migrations
from app.ledger.store import LedgerStore
from app.otari.client import OtariClient
from app.otari.mcp import OtariMCPClient
from app.policy.compiler import PolicyCompiler
from app.reconcile.engine import ReconciliationEngine
from app.txn.store import TransactionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations(db_path=settings.tr_db_path)

    transaction_store = TransactionStore(db_path=settings.tr_db_path)
    recovered_count = transaction_store.recover_on_start()
    print(f"Startup recovery completed. Recovered {recovered_count} transaction(s).")

    ledger_store = LedgerStore(db_path=settings.tr_db_path)

    app.state.transaction_store = transaction_store
    app.state.ledger_store = ledger_store
    app.state.agent_orchestrator = None
    app.state.reconciliation_engine = None
    app.state.policy_compiler = None

    # Chat completions are independent of GitHub MCP configuration.
    async with (
        OtariClient() as compiler_client,
        OtariClient(api_key=settings.otari_agent_api_key) as planner_client,
    ):
        app.state.policy_compiler = PolicyCompiler(
            otari_client=compiler_client,
            model=settings.tr_compiler_model,
        )

        print(f"Policy compiler initialized with routing policy: {settings.tr_compiler_model}")

        if settings.otari_mcp_server_id:
            async with OtariMCPClient(
                base_url=settings.otari_base_url,
                api_key=settings.otari_api_key,
                timeout=settings.otari_timeout,
            ) as otari_client:
                proposal_service = ProposalService(
                    store=transaction_store,
                    expected_repository=settings.mcp_github_repo,
                    db_path=settings.tr_db_path,
                )

                handlers = AgentToolHandlers(
                    client=otari_client,
                    server_id=settings.otari_mcp_server_id,
                    expected_repository=settings.mcp_github_repo,
                    proposal_service=proposal_service,
                )

                dispatcher = AgentToolDispatcher(
                    handlers=handlers,
                    ledger=ledger_store,
                )

                proposal_evaluator = ProposalEvaluationService(
                    store=transaction_store,
                    client=otari_client,
                    server_id=settings.otari_mcp_server_id,
                    expected_repository=settings.mcp_github_repo,
                    db_path=settings.tr_db_path,
                )

                app.state.agent_orchestrator = AgentOrchestrator(
                    client=planner_client,
                    dispatcher=dispatcher,
                    proposal_evaluator=proposal_evaluator,
                )

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

app.include_router(reconciliation_router)
app.include_router(dryrun_router)
app.include_router(policy_compilation_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trustrail",
    }
