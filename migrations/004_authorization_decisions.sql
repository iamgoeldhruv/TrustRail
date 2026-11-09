ALTER TABLE transactions ADD COLUMN authorization_decision TEXT;
ALTER TABLE transactions ADD COLUMN authorization_reasons_json TEXT;
ALTER TABLE transactions ADD COLUMN evaluated_at TEXT;
