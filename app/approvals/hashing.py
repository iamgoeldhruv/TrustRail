import hashlib
from typing import Any

from app.ledger.canonical import canonical_json


def approval_binding_hash(
    *,
    tool: str,
    args: dict[str, Any],
    policy_version: int,
    facts_that_matter: dict[str, Any],
    server_revision: str,
) -> str:
    payload = {
        "tool": tool,
        "args": args,
        "policy_version": policy_version,
        "facts_that_matter": facts_that_matter,
        "server_revision": server_revision,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
