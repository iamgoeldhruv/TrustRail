
import json

import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_connection
from app.main import app


FACTS = {
    "repository": "owner/repo",
    "issue_number": 1,
    "state": "open",
    "labels": [],
    "priority": "P2",
    "inactive_days": 45,
}

ARGS = {
    "issue_number": 1,
    "note": "demo",
    "txn_id": "txn-001",
}



@pytest.fixture
def client(database, monkeypatch):
    from app.core.config import settings

    # Make the application lifespan use the temporary test database.
    monkeypatch.setattr(settings, "tr_db_path", database)

    with get_connection(database) as connection:
        connection.execute(
            """
            UPDATE transactions
            SET status = 'PENDING_APPROVAL',
                authorization_decision = 'REQUIRES_APPROVAL',
                facts_json = ?,
                server_revision = 'revision-1',
                tool = 'close_issue_with_note',
                args_json = ?
            WHERE id = 'txn-001'
            """,
            (json.dumps(FACTS), json.dumps(ARGS)),
        )
        connection.commit()

    # Let the real application lifespan initialize all stores and services.
    with TestClient(app) as test_client:
        yield test_client


def test_approve_endpoint(client):
    response = client.post(
        "/api/v1/transactions/txn-001/approve",
        json={"approver": "demo-operator"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["txn_id"] == "txn-001"
    assert body["decision"] == "APPROVE"
    assert body["approver"] == "demo-operator"
    assert len(body["binding_hash"]) == 64


def test_reject_endpoint(client):
    response = client.post(
        "/api/v1/transactions/txn-001/reject",
        json={"approver": "demo-operator"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["txn_id"] == "txn-001"
    assert body["decision"] == "REJECT"


def test_unknown_transaction_returns_404(client):
    response = client.post(
        "/api/v1/transactions/unknown/approve",
        json={"approver": "demo-operator"},
    )

    assert response.status_code == 404


def test_non_pending_transaction_returns_409(client):
    with get_connection(app.state.transaction_store.db_path) as connection:
        connection.execute(
            "UPDATE transactions SET status = 'PROPOSED' WHERE id = ?",
            ("txn-001",),
        )
        connection.commit()

    response = client.post(
        "/api/v1/transactions/txn-001/approve",
        json={"approver": "demo-operator"},
    )

    assert response.status_code == 409


def test_duplicate_approval_returns_409(client):
    url = "/api/v1/transactions/txn-001/approve"
    payload = {"approver": "demo-operator"}

    first = client.post(url, json=payload)
    second = client.post(url, json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_blank_approver_returns_422(client):
    response = client.post(
        "/api/v1/transactions/txn-001/approve",
        json={"approver": "   "},
    )

    assert response.status_code == 422


def test_client_cannot_supply_binding_hash(client):
    response = client.post(
        "/api/v1/transactions/txn-001/approve",
        json={
            "approver": "demo-operator",
            "binding_hash": "a" * 64,
        },
    )

    assert response.status_code == 422
