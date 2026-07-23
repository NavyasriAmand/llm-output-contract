"""Batch CLI. Reads a JSONL file of raw model outputs and repairs each.

Each input line is a JSON object: {"contract": "moderation", "raw": "<text>"}.
Emits a JSONL report to stdout and a summary to stderr. Exits non-zero when
the post-repair failure rate exceeds --max-fail-rate, which makes it usable
as a CI gate on a captured sample of production outputs.
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import load_settings
from .contracts import load_all
from .engine import repair_output, report_to_json
from .logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="loc", description="Repair LLM outputs.")
    parser.add_argument("input", help="JSONL file of {contract, raw} objects")
    parser.add_argument(
        "--max-fail-rate",
        type=float,
        default=1.0,
        help="exit non-zero if post-repair failure rate exceeds this (0..1)",
    )
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    settings = load_settings()
    contracts = load_all(settings.contracts_dir)

    total = 0
    already_valid = 0
    repaired = 0
    failed = 0

    with open(args.input, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            contract = contracts.get(record["contract"])
            if contract is None:
                print(
                    json.dumps({"error": f"unknown contract {record['contract']}"}),
                    file=sys.stderr,
                )
                continue
            report = repair_output(record["raw"], contract)
            total += 1
            if report.was_valid:
                already_valid += 1
            elif report.repaired_ok:
                repaired += 1
            else:
                failed += 1
            print(report_to_json(report))

    fail_rate = failed / total if total else 0.0
    summary = {
        "total": total,
        "already_valid": already_valid,
        "repaired": repaired,
        "failed": failed,
        "fail_rate": round(fail_rate, 4),
    }
    print(json.dumps(summary), file=sys.stderr)

    return 1 if fail_rate > args.max_fail_rate else 0


if __name__ == "__main__":
    raise SystemExit(main())
