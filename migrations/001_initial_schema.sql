
CREATE TABLE policies (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    nl_text TEXT NOT NULL,
    json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,

    UNIQUE (id, version)
);

CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    user_request TEXT NOT NULL,
    planner_model TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (policy_id)
        REFERENCES policies(id)
);

CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    server_revision TEXT,
    facts_json TEXT,
    approval_id TEXT,
    otari_request_ids_json TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES runs(id),

    FOREIGN KEY (policy_id, policy_version)
        REFERENCES policies(id, version)
);

CREATE TABLE approvals (
    id TEXT PRIMARY KEY,
    txn_id TEXT NOT NULL,
    approver TEXT NOT NULL,
    decision TEXT NOT NULL,
    binding_hash TEXT NOT NULL,
    decided_at TEXT NOT NULL,

    FOREIGN KEY (txn_id)
        REFERENCES transactions(id)
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    txn_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT,
    hash TEXT NOT NULL,
    ts TEXT NOT NULL,

    FOREIGN KEY (txn_id)
        REFERENCES transactions(id),

    UNIQUE (txn_id, seq)
);
