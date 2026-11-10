from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.db.connection import get_connection
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy


class PolicyServiceError(ValueError):
    """Raised when a policy cannot be safely persisted or activated."""


class PolicyService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def activate(self, policy: Policy, nl_text: str) -> dict[str, object]:
        try:
            validate_policy(policy)
        except (PolicySemanticError, ValidationError) as exc:
            raise PolicyServiceError("Only a valid compiled policy can be activated.") from exc

        if not nl_text.strip():
            raise PolicyServiceError("The original policy description is required.")

        policy_id = f"policy-{uuid4()}"
        created_at = datetime.now(UTC).isoformat()
        policy_json = json.dumps(
            policy.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )

        with get_connection(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE policies SET status = 'INACTIVE' WHERE status = 'ACTIVE'"
            )
            connection.execute(
                """
                INSERT INTO policies (id, version, nl_text, json, status, created_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (policy_id, policy.version, nl_text.strip(), policy_json, created_at),
            )
            connection.commit()

        return {
            "policy_id": policy_id,
            "version": policy.version,
            "status": "ACTIVE",
            "activated_at": created_at,
            "policy": policy.model_dump(mode="json"),
        }

    def active(self) -> dict[str, object] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id, version, nl_text, json, status, created_at
                FROM policies
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return None

        try:
            policy = Policy.model_validate(json.loads(row["json"]))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise PolicyServiceError("The stored active policy is invalid.") from exc

        return {
            "policy_id": row["id"],
            "version": row["version"],
            "status": row["status"],
            "nl_text": row["nl_text"],
            "created_at": row["created_at"],
            "policy": policy.model_dump(mode="json"),
        }
