
-- Migration 005: Support run-scoped and transaction-scoped ledger events.

-- 1. Create the replacement table.
CREATE TABLE events_new (
    id TEXT PRIMARY KEY,

    txn_id TEXT,
    run_id TEXT,

    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT,
    hash TEXT NOT NULL,
    ts TEXT NOT NULL,

    FOREIGN KEY (txn_id)
        REFERENCES transactions(id),

    FOREIGN KEY (run_id)
        REFERENCES runs(id),

    CHECK (
        (txn_id IS NOT NULL AND run_id IS NULL)
        OR
        (txn_id IS NULL AND run_id IS NOT NULL)
    )
);

-- 2. Copy existing transaction events without modifying their hashes.
INSERT INTO events_new (
    id,
    txn_id,
    run_id,
    seq,
    type,
    payload_json,
    prev_hash,
    hash,
    ts
)
SELECT
    id,
    txn_id,
    NULL,
    seq,
    type,
    payload_json,
    prev_hash,
    hash,
    ts
FROM events;

-- 3. Replace the old table.
DROP TABLE events;

ALTER TABLE events_new RENAME TO events;

-- 4. Enforce independent sequence numbers for each scope.
CREATE UNIQUE INDEX idx_events_txn_seq
ON events(txn_id, seq)
WHERE txn_id IS NOT NULL;

CREATE UNIQUE INDEX idx_events_run_seq
ON events(run_id, seq)
WHERE run_id IS NOT NULL;

-- 5. Restore append-only protection.
CREATE TRIGGER prevent_event_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'ledger events are append-only');
END;

CREATE TRIGGER prevent_event_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'ledger events are append-only');
END;
