
CREATE INDEX idx_runs_policy_id
    ON runs(policy_id);

CREATE INDEX idx_transactions_run_id
    ON transactions(run_id);

CREATE INDEX idx_transactions_status
    ON transactions(status);

CREATE INDEX idx_transactions_created_at
    ON transactions(created_at);

CREATE INDEX idx_approvals_txn_id
    ON approvals(txn_id);

CREATE INDEX idx_events_txn_id_seq
    ON events(txn_id, seq);
