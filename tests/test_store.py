from pathlib import Path

from llm_output_contract.config import load_settings
from llm_output_contract.contracts import load_contract
from llm_output_contract.engine import repair_output
from llm_output_contract.store import AuditStore

SETTINGS = load_settings()
MOD = load_contract(Path("config/contracts/moderation.yaml"))


def test_record_and_count(tmp_path):
    db = tmp_path / "audit.db"
    with AuditStore(db, SETTINGS.schema_ddl) as store:
        r = repair_output("{'label':'flag','confidence':0.5,'reasons':[]}", MOD)
        rid = store.record(r, "raw")
        assert rid == 1
        assert store.count() == 1


def test_failure_rate(tmp_path):
    db = tmp_path / "audit.db"
    with AuditStore(db, SETTINGS.schema_ddl) as store:
        good = repair_output('{"label":"allow","confidence":0.5,"reasons":[]}', MOD)
        bad = repair_output('{"confidence":0.5,"reasons":[]}', MOD)  # missing label
        store.record(good, "g")
        store.record(bad, "b")
        assert store.count() == 2
        assert store.failure_rate("moderation") == 0.5
        assert store.failure_rate("unknown") == 0.0
