"""SQLite audit store for repair outcomes.

The DDL is read from sql/schema.sql rather than embedded here, so the schema
is reviewable on its own and versioned as SQL. The store is optional: the
engine works without it, but a deployment uses it to answer operational
questions about repair volume and failure rates over time.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import RepairReport


class AuditStore:
    def __init__(self, db_path: Path, ddl_path: Path) -> None:
        self.db_path = db_path
        self.ddl_path = ddl_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        ddl = self.ddl_path.read_text()
        self._conn.executescript(ddl)
        self._conn.commit()

    def record(self, report: RepairReport, raw_output: str) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO repair_audit
                (created_at, contract, was_valid, repaired_ok,
                 actions, raw_output, repaired_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(tz=timezone.utc).isoformat(),
                report.contract,
                int(report.was_valid),
                int(report.repaired_ok),
                json.dumps([a.value for a in report.actions]),
                raw_output,
                json.dumps(report.obj) if report.obj is not None else None,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def failure_rate(self, contract: str) -> float:
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN repaired_ok = 0 THEN 1 ELSE 0 END) AS failed
            FROM repair_audit
            WHERE contract = ?
            """,
            (contract,),
        ).fetchone()
        total = row["total"] or 0
        if total == 0:
            return 0.0
        return (row["failed"] or 0) / total

    def count(self) -> int:
        return int(
            self._conn.execute("SELECT COUNT(*) FROM repair_audit").fetchone()[0]
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "AuditStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
