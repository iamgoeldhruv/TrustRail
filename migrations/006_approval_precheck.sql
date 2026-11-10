ALTER TABLE approvals ADD COLUMN policy_hash TEXT;
ALTER TABLE transactions ADD COLUMN approval_invalidation_reason TEXT;
