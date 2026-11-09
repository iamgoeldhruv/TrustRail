from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from app.agent.dispatcher import AgentToolDispatcher
from app.agent.evaluation import ProposalEvaluationService
from app.agent.orchestrator import AgentOrchestrator
from app.agent.proposal_service import ProposalService
from app.agent.tool_handlers import AgentToolHandlers
from app.core.config import settings
from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore
from app.otari.client import OtariClient
from app.otari.mcp import OtariMCPClient
from app.policy.compiler import PolicyCompiler
from app.policy.compiler_models import AmbiguousResponse
from app.policy.models import CompiledPolicyResponse, Policy
from app.policy.summary import generate_policy_summary
from app.policy.validator import validate_policy
from app.txn.store import TransactionStore


def _log(message: str, *, level: str = "INFO") -> None:
    timestamp = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[{timestamp}] [TrustRail] [{level}] {message}", flush=True)


def _create_run(
    *,
    policy_request: str,
    user_request: str,
    compiled: CompiledPolicyResponse,
) -> tuple[str, str]:
    policy_id = f"policy-{uuid4()}"
    run_id = str(uuid4())
    now = datetime.now(UTC).isoformat()

    with get_connection(settings.tr_db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO policies (id, version, nl_text, json, status, created_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (
                policy_id,
                compiled.policy.version,
                policy_request,
                compiled.policy.model_dump_json(),
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO runs (id, policy_id, user_request, planner_model, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, policy_id, user_request, settings.tr_planner_model, now),
        )
        LedgerStore(settings.tr_db_path).append_event_in_transaction(
            connection,
            LedgerEventCreate(
                run_id=run_id,
                type="RUN_STARTED",
                payload={
                    "policy_id": policy_id,
                    "policy_version": compiled.policy.version,
                    "planner_model": settings.tr_planner_model,
                },
            ),
        )
        connection.commit()

    return policy_id, run_id


def _append_run_event(run_id: str, event_type: str, payload: dict[str, object]) -> None:
    LedgerStore(settings.tr_db_path).append_event(
        LedgerEventCreate(run_id=run_id, type=event_type, payload=payload)
    )


def _print_result(
    *,
    policy_id: str,
    run_id: str,
    policy: Policy,
    request: str,
    result,
    transactions,
) -> None:
    allowed = sum(item.authorization_decision == "ALLOW" for item in transactions)
    denied = sum(
        item.authorization_decision in {"DENY", "POLICY_INVALID"}
        for item in transactions
    )
    approval = sum(
        item.authorization_decision == "REQUIRES_APPROVAL"
        for item in transactions
    )
    unevaluable = sum(item.authorization_decision is None for item in transactions)

    print("\nRun")
    print(f"  ID                 : {run_id}")
    print(f"  Request            : {request}")
    print(f"  Planner model      : {settings.tr_planner_model}")
    print(f"  Compiler model     : {settings.tr_compiler_model}")
    print(f"  Completion         : {result.termination_reason}")
    if result.provider_usage:
        print(f"  Token usage        : {json.dumps(result.provider_usage, sort_keys=True)}")
    print("\nCompiled policy")
    print(f"  ID                 : {policy_id}")
    print("  Status             : validated")
    print(f"  Summary            : {generate_policy_summary(policy)}")
    print("\nAgent activity")
    print(f"  Tool calls         : {result.tool_calls}")
    print(f"  Iterations         : {result.model_iterations}")
    if result.response:
        print(f"  Planner response   : {result.response}")
    print("\nProposal decisions")
    for transaction in transactions:
        print(f"  Transaction        : {transaction.id}")
        print(
            f"    Action           : {transaction.tool} "
            f"issue #{transaction.args.get('issue_number')}"
        )
        print(f"    Arguments        : {json.dumps(transaction.args, sort_keys=True)}")
        print(f"    Decision         : {transaction.authorization_decision or 'UNEVALUABLE'}")
        print(f"    Status           : {transaction.status.value}")
        print(f"    Approval needed  : {transaction.status.value == 'PENDING_APPROVAL'}")
        print(
            "    Reasons          : "
            f"{', '.join(transaction.authorization_reasons or ['evaluation_failed'])}"
        )
        if transaction.facts is not None:
            print(f"    Facts            : {json.dumps(transaction.facts, sort_keys=True)}")
    print("\nSummary")
    print(f"  Proposals         : {len(transactions)}")
    print(f"  Allowed           : {allowed}")
    print(f"  Denied            : {denied}")
    print(f"  Requires approval : {approval}")
    print(f"  Unevaluable       : {unevaluable}")
    print("  Execution         : no GitHub writes were executed")


async def run_command(*, policy: str, request: str) -> int:
    if not policy.strip() or not request.strip():
        print("Error: both --policy and --request must be non-empty.")
        return 2
    server_id = settings.otari_mcp_server_id
    if not server_id:
        print("Error: OTARI_MCP_SERVER_ID is not configured.")
        return 1

    _log("Starting agent run.")
    _log("Validating required configuration.")
    run_migrations(db_path=settings.tr_db_path)
    _log(f"Database ready: {settings.tr_db_path}")
    run_id: str | None = None
    try:
        _log(f"Compiling policy with routing policy '{settings.tr_compiler_model}'.")
        async with OtariClient() as compiler_client:
            compiled = await PolicyCompiler(
                otari_client=compiler_client,
                model=settings.tr_compiler_model,
            ).compile(policy)
        if isinstance(compiled, AmbiguousResponse):
            _log("Policy compilation requires clarification.", level="ERROR")
            print("Error: policy compilation was ambiguous; execution stopped.")
            for question in compiled.questions:
                print(f"  - {question}")
            return 2
        validate_policy(compiled.policy)
        _log("Policy compiled and validated successfully.")
        policy_id, run_id = _create_run(
            policy_request=policy,
            user_request=request,
            compiled=compiled,
        )
        _log(f"Run context persisted. Run ID: {run_id}")

        store = TransactionStore(settings.tr_db_path)
        _log(f"Initializing planner '{settings.tr_planner_model}'.")
        async with (
            OtariClient(api_key=settings.otari_agent_api_key) as planner_client,
            OtariMCPClient(
                base_url=settings.otari_base_url,
                api_key=settings.otari_api_key,
                timeout=settings.otari_timeout,
            ) as mcp_client,
        ):
            _log(f"Connected to Otari MCP server '{server_id}'.")
            proposal_service = ProposalService(
                store=store,
                expected_repository=settings.mcp_github_repo,
                db_path=settings.tr_db_path,
            )
            handlers = AgentToolHandlers(
                client=mcp_client,
                server_id=server_id,
                expected_repository=settings.mcp_github_repo,
                proposal_service=proposal_service,
            )
            evaluator = ProposalEvaluationService(
                store=store,
                client=mcp_client,
                server_id=server_id,
                expected_repository=settings.mcp_github_repo,
                db_path=settings.tr_db_path,
            )
            result = await AgentOrchestrator(
                client=planner_client,
                dispatcher=AgentToolDispatcher(
                    handlers=handlers,
                    ledger=LedgerStore(settings.tr_db_path),
                ),
                proposal_evaluator=evaluator,
                progress_callback=_log,
            ).run(run_id=run_id, user_request=request)

        _log("Planner completed; loading persisted proposals.")
        transactions = store.list_transactions(run_id=run_id)
        _log(f"Loaded {len(transactions)} proposal(s) for final reporting.")
        _append_run_event(
            run_id,
            "RUN_COMPLETED",
            {
                "termination_reason": result.termination_reason,
                "tool_calls": result.tool_calls,
                "proposals": len(transactions),
            },
        )
        _log("Run completion audit event persisted.")
        _print_result(
            policy_id=policy_id,
            run_id=run_id,
            policy=compiled.policy,
            request=request,
            result=result,
            transactions=transactions,
        )
        return 0
    except Exception as exc:
        if run_id is not None:
            try:
                _append_run_event(
                    run_id,
                    "RUN_FAILED",
                    {"error": type(exc).__name__},
                )
            except Exception as audit_error:
                print(f"Error: failed to persist run failure audit event: {audit_error}")
        _log(f"Run failed safely: {exc}", level="ERROR")
        return 1
