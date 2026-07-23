-- Repair audit log.
--
-- Every call to the engine writes one row. This is the operational record a
-- team uses to answer "what fraction of model outputs needed repair last
-- week, and which contract is drifting?" The raw input is stored so a failed
-- repair can be replayed after the repair rules improve.
--
-- Kept deliberately in a standalone .sql file rather than an inline Python
-- string so the schema is reviewable on its own and the repo's language
-- profile reflects the SQL surface.

CREATE TABLE IF NOT EXISTS repair_audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT    NOT NULL,          -- ISO-8601 UTC
    contract      TEXT    NOT NULL,          -- contract pack name
    was_valid     INTEGER NOT NULL,          -- 1 if raw output already valid
    repaired_ok   INTEGER NOT NULL,          -- 1 if valid after repair
    actions       TEXT    NOT NULL,          -- JSON array of repair action codes
    raw_output    TEXT    NOT NULL,          -- original model text
    repaired_json TEXT                       -- serialized repaired object, or NULL
);

-- The dashboards filter on contract and recency, and count failures, so index
-- the two columns those queries touch most.
CREATE INDEX IF NOT EXISTS idx_repair_audit_contract_created
    ON repair_audit (contract, created_at);

CREATE INDEX IF NOT EXISTS idx_repair_audit_repaired_ok
    ON repair_audit (repaired_ok);
