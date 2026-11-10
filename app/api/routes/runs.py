from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.orchestrator import AgentOrchestrator, AgentRunResult
from app.db.connection import get_connection
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore
from app.policy.service import PolicyService, PolicyServiceError
from app.txn.models import Transaction
from app.txn.store import TransactionStore

router = APIRouter(prefix="/api/v1/runs", tags=["Runs"])


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str = Field(min_length=1, max_length=10_000)
    planner_model: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("user_request", "planner_model")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class RunModelsResponse(BaseModel):
    models: list[str]
    default_model: str


def _transaction_payload(transaction: Transaction) -> dict[str, Any]:
    return transaction.model_dump(mode="json")


def _run_row(run_id: str, request: Request) -> dict[str, Any]:
    store: TransactionStore = request.app.state.transaction_store
    with get_connection(store.db_path) as connection:
        row = connection.execute(
            """
            SELECT id, policy_id, user_request, planner_model, created_at,
                   status, completed_at, termination_reason, response,
                   tool_calls, model_iterations, provider_usage_json, error
            FROM runs WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    transactions = store.list_transactions(run_id=run_id)
    events = request.app.state.ledger_store.get_events(run_id=run_id)
    return {
        "id": row["id"],
        "run_id": row["id"],
        "policy_id": row["policy_id"],
        "user_request": row["user_request"],
        "planner_model": row["planner_model"],
        "created_at": row["created_at"],
        "status": row["status"],
        "completed_at": row["completed_at"],
        "termination_reason": row["termination_reason"],
        "response": row["response"],
        "tool_calls": row["tool_calls"],
        "model_iterations": row["model_iterations"],
        "provider_usage": (
            json.loads(row["provider_usage_json"])
            if row["provider_usage_json"]
            else {}
        ),
        "error": row["error"],
        "proposals": [_transaction_payload(item) for item in transactions],
        "proposal_count": len(transactions),
        "events": [event.model_dump(mode="json") for event in events],
    }


def _set_run_result(
    db_path: str,
    run_id: str,
    *,
    result: AgentRunResult | None = None,
    error: str | None = None,
) -> None:
    completed_at = datetime.now(UTC).isoformat()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE runs
            SET status = ?, completed_at = ?, termination_reason = ?,
                response = ?, tool_calls = ?, model_iterations = ?,
                provider_usage_json = ?, error = ?
            WHERE id = ?
            """,
            (
                "FAILED" if error else "COMPLETED",
                completed_at,
                result.termination_reason if result else None,
                result.response if result else None,
                result.tool_calls if result else 0,
                result.model_iterations if result else 0,
                json.dumps(result.provider_usage) if result else "{}",
                error,
                run_id,
            ),
        )
        connection.commit()


async def _execute_run(
    request: Request,
    *,
    run_id: str,
    user_request: str,
    planner_model: str,
) -> None:
    app = request.app
    db_path = app.state.transaction_store.db_path

    def progress(message: str) -> None:
        try:
            app.state.ledger_store.append_event(
                LedgerEventCreate(
                    run_id=run_id,
                    type="RUN_ACTIVITY",
                    payload={"message": message},
                )
            )
        except Exception:
            # Activity is useful observability, but must not alter run safety.
            pass

    try:
        orchestrator = AgentOrchestrator(
            client=app.state.planner_client,
            dispatcher=app.state.agent_dispatcher,
            proposal_evaluator=app.state.proposal_evaluator,
            model=planner_model,
            progress_callback=progress,
        )
        result = await orchestrator.run(run_id=run_id, user_request=user_request)
        _set_run_result(db_path, run_id, result=result)
        app.state.ledger_store.append_event(
            LedgerEventCreate(
                run_id=run_id,
                type="RUN_COMPLETED",
                payload={
                    "termination_reason": result.termination_reason,
                    "tool_calls": result.tool_calls,
                    "proposals": len(
                        app.state.transaction_store.list_transactions(run_id=run_id)
                    ),
                },
            )
        )
    except Exception as exc:
        _set_run_result(db_path, run_id, error=str(exc))
        app.state.ledger_store.append_event(
            LedgerEventCreate(
                run_id=run_id,
                type="RUN_FAILED",
                payload={"error": type(exc).__name__},
            )
        )


@router.get("/models", response_model=RunModelsResponse)
async def get_run_models(request: Request) -> RunModelsResponse:
    model = request.app.state.settings.tr_planner_model
    return RunModelsResponse(models=[model], default_model=model)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    payload: RunCreateRequest,
    request: Request,
) -> dict[str, Any]:
    app = request.app
    if app.state.agent_dispatcher is None or app.state.planner_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent run service is not configured",
        )

    planner_model = payload.planner_model or app.state.settings.tr_planner_model
    if planner_model != app.state.settings.tr_planner_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Planner model is not supported by this deployment",
        )

    try:
        active = PolicyService(app.state.settings.tr_db_path).active()
    except PolicyServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active policy is configured",
        )

    run_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    with get_connection(app.state.settings.tr_db_path) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                id, policy_id, user_request, planner_model, created_at, status
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING')
            """,
            (
                run_id,
                active["policy_id"],
                payload.user_request,
                planner_model,
                created_at,
            ),
        )
        connection.commit()
    app.state.ledger_store.append_event(
        LedgerEventCreate(
            run_id=run_id,
            type="RUN_STARTED",
            payload={
                "policy_id": active["policy_id"],
                "policy_version": active["version"],
                "planner_model": planner_model,
            },
        )
    )
    task = asyncio.create_task(
        _execute_run(
            request,
            run_id=run_id,
            user_request=payload.user_request,
            planner_model=planner_model,
        )
    )
    app.state.run_tasks[run_id] = task
    task.add_done_callback(lambda _: app.state.run_tasks.pop(run_id, None))
    return _run_row(run_id, request)


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    return _run_row(run_id, request)


@router.get("/{run_id}/transactions")
async def get_run_transactions(
    run_id: str,
    request: Request,
) -> list[dict[str, Any]]:
    data = _run_row(run_id, request)
    return data["proposals"]


@router.get("/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> list[dict[str, Any]]:
    _run_row(run_id, request)
    return [
        event.model_dump(mode="json")
        for event in request.app.state.ledger_store.get_events(run_id=run_id)
    ]
