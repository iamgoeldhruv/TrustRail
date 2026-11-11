from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.agent.proposal_service import ProposalService
from app.db.connection import get_connection
from app.txn.executor import ApprovalRequiredError, TransactionExecutionError
from app.txn.states import TransactionState
from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings
from mcp_github.fault_injection import FaultMode, fault_controller

router = APIRouter(prefix="/api/v1/chaos", tags=["Chaos Lab"])


class ChaosRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_number: int = Field(gt=0)
    note: str = Field(min_length=1, max_length=5000)
    executor: Literal["secure", "naive"] = "secure"


class FaultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FaultMode


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_number: int = Field(gt=0)


def _settings() -> GitHubSettings:
    return GitHubSettings()


def _mcp_url() -> str:
    value = "https://trustrail-djkv.onrender.com"
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP_GITHUB_SERVER_URL is not configured",
        )
    return value.rstrip("/")


async def _set_remote_fault(mode: FaultMode, request: Request) -> dict[str, Any]:
    settings = request.app.state.settings

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{_mcp_url()}/admin/fault",
                headers={
                    "Authorization": (
                        f"Bearer {settings.mcp_admin_token}"
                    )
                },
                json={"mode": mode.value},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise HTTPException(
                    status_code=502,
                    detail="MCP fault server returned an invalid response",
                )
            return payload
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="MCP fault configuration was rejected") from exc
    except httpx.RequestError as exc:
        print(exc)
        raise HTTPException(status_code=502, detail="MCP fault server is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="MCP fault server returned invalid JSON",
        ) from exc


async def _issue_state(issue_number: int, txn_id: str | None = None) -> dict[str, Any]:
    settings = _settings()
    async with GitHubClient(settings=settings) as client:
        issue = await client.get_issue(issue_number)
        comments = await client.get_issue_comments(issue_number)
    marker = f"<!-- trustrail:txn={txn_id} -->" if txn_id else None
    matches = [comment.id for comment in comments if marker and marker in (comment.body or "")]
    marker_pattern = re.compile(r"<!--\s*trustrail:txn=[A-Za-z0-9_-]{1,128}\s*-->")
    marker_count = sum(len(marker_pattern.findall(comment.body or "")) for comment in comments)
    return {
        "repository": settings.mcp_github_repo,
        "issue_number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "labels": [label.name for label in issue.labels],
        "total_comments": len(comments),
        "txn_id": txn_id,
        "matching_comment_ids": matches,
        "marker_count": marker_count,
        "probed_at": datetime.now(UTC).isoformat(),
    }


@router.get("/status")
async def chaos_status(request: Request) -> dict[str, Any]:
    settings = _settings()
    return {
        "repository": settings.mcp_github_repo,
        "fault_mode": (await fault_controller.get_mode()).value,
        "fault_modes": [
            {"value": mode.value, "label": mode.value.replace("_", " ").title()}
            for mode in FaultMode
        ],
        "naive_demo_enabled": settings.trustrail_enable_naive_demo,
    }


@router.get("/issues")
async def chaos_issues() -> dict[str, Any]:
    settings = _settings()
    async with GitHubClient(settings=settings) as client:
        issues = await client.list_issues(state="open")
    return {
        "repository": settings.mcp_github_repo,
        "issues": [
            {
                "number": item.number,
                "title": item.title,
                "state": item.state,
                "labels": [label.name for label in item.labels],
            }
            for item in issues
        ],
    }


@router.get("/issues/{issue_number}/state")
async def chaos_issue_state(issue_number: int) -> dict[str, Any]:
    if issue_number <= 0:
        raise HTTPException(status_code=422, detail="Issue number must be positive")
    return await _issue_state(issue_number)


@router.put("/fault")
async def configure_fault(body: FaultRequest, request: Request) -> dict[str, Any]:
    result = await _set_remote_fault(body.mode, request)
    return {"configured": result, "mode": body.mode.value}


@router.post("/run")
async def run_chaos_demo(body: ChaosRunRequest, request: Request) -> dict[str, Any]:
    app = request.app
    executor = app.state.transaction_executor
    if executor is None:
        raise HTTPException(status_code=503, detail="Transaction executor is not configured")
    if body.executor == "naive" and not _settings().trustrail_enable_naive_demo:
        raise HTTPException(status_code=403, detail="Naive demo execution is disabled")

    run_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    active = app.state.settings
    with get_connection(active.tr_db_path) as connection:
        policy = connection.execute(
            "SELECT id, version FROM policies WHERE status = 'ACTIVE' ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if policy is None:
            raise HTTPException(status_code=409, detail="No active policy is configured")
        connection.execute(
            "INSERT INTO runs (id, policy_id, user_request, planner_model, created_at, status) VALUES (?, ?, ?, ?, ?, 'COMPLETED')",
            (
                run_id,
                policy["id"],
                f"Chaos Lab: close issue #{body.issue_number}",
                active.tr_planner_model,
                created_at,
            ),
        )
        connection.commit()

    proposal = ProposalService(
        store=app.state.transaction_store,
        expected_repository=active.mcp_github_repo,
        db_path=active.tr_db_path,
    ).create_close_proposal(run_id=run_id, issue_number=body.issue_number, reason=body.note)
    try:
        transaction = await executor.execute(proposal.id, executor=body.executor)
    except ApprovalRequiredError:
        transaction = app.state.transaction_store.get_transaction(proposal.id)
    except (TransactionExecutionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run_id": run_id,
        "transaction": transaction.model_dump(mode="json") if transaction else None,
        "issue": await _issue_state(body.issue_number, proposal.id),
    }


@router.get("/runs/{run_id}")
async def chaos_run(run_id: str, request: Request) -> dict[str, Any]:
    transactions = request.app.state.transaction_store.list_transactions(run_id=run_id)
    if not transactions:
        raise HTTPException(status_code=404, detail="Chaos run not found")
    transaction = transactions[-1]
    return {
        "run_id": run_id,
        "transaction": transaction.model_dump(mode="json"),
        "issue": await _issue_state(transaction.args["issue_number"], transaction.id),
    }


@router.post("/reset")
async def reset_chaos(body: ResetRequest, request: Request) -> dict[str, Any]:
    issue_number = body.issue_number
    settings = _settings()
    async with GitHubClient(settings=settings) as client:
        issue = await client.get_issue(issue_number)
        if issue.state == "closed":
            await client.reopen_issue(issue_number)
        comments = await client.get_issue_comments(issue_number)
        for comment in comments:
            if re.search(r"<!--\s*trustrail:txn=[A-Za-z0-9_-]{1,128}\s*-->", comment.body or ""):
                await client.delete_issue_comment(issue_number, comment.id)
    await _set_remote_fault(FaultMode.NONE, request)
    return {"reset": True, "issue": await _issue_state(issue_number)}
