import hashlib
from typing import Any

from app.ledger.canonical import canonical_json


def policy_content_hash(policy: Any) -> str:
    return hashlib.sha256(canonical_json(policy).encode("utf-8")).hexdigest()


def approval_binding_hash(
    *,
    tool: str,
    args: dict[str, Any],
    policy_version: int,
    facts_that_matter: dict[str, Any],
    server_revision: str,
    policy_hash: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "tool": tool,
        "args": args,
        "policy_version": policy_version,
        "facts_that_matter": facts_that_matter,
        "server_revision": server_revision,
    }
    if policy_hash is not None:
        payload["policy_hash"] = policy_hash
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
