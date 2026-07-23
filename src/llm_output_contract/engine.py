"""The repair engine: from raw model text to a validated object or a failure.

Flow:
    raw text
      -> extract JSON span (strip fences, isolate first balanced object)
      -> string-level repairs (re-parse after each)
      -> object-level coercion (types, enum aliases, optional defaults)
      -> validate against the contract schema
    The report records every action and whether the result validates.
"""
from __future__ import annotations

import json

from .contracts import Contract
from .extract import candidate_json
from .logging_config import get_logger
from .models import Action, RepairReport
from .repair import object_repairs, string_repairs, try_parse

log = get_logger(__name__)


def repair_output(raw: str, contract: Contract) -> RepairReport:
    # Fast path: the raw text is already valid JSON that satisfies the contract.
    direct = try_parse(raw.strip())
    if direct is not None and contract.is_valid(direct):
        return RepairReport(
            contract=contract.name,
            was_valid=True,
            repaired_ok=True,
            actions=[Action.ALREADY_VALID],
            obj=direct,
        )

    actions: list[Action] = []

    candidate, fenced = candidate_json(raw)
    if fenced:
        actions.append(Action.STRIP_FENCE)
    if candidate.strip() != raw.strip():
        actions.append(Action.EXTRACT_OBJECT)

    obj, str_actions = string_repairs(candidate)
    actions.extend(str_actions)

    if obj is None or not isinstance(obj, dict):
        report = RepairReport(
            contract=contract.name,
            was_valid=False,
            repaired_ok=False,
            actions=actions,
            error="could not parse a JSON object from output",
        )
        log.info("repair_failed", extra=_log_fields(report))
        return report

    obj, obj_actions = object_repairs(obj, contract)
    actions.extend(obj_actions)

    ok = contract.is_valid(obj)
    report = RepairReport(
        contract=contract.name,
        was_valid=False,
        repaired_ok=ok,
        actions=actions,
        obj=obj if ok else None,
        error=None if ok else "; ".join(contract.errors(obj)),
    )
    log.info("repair_ok" if ok else "repair_failed", extra=_log_fields(report))
    return report


def _log_fields(report: RepairReport) -> dict:
    return {
        "contract": report.contract,
        "was_valid": report.was_valid,
        "repaired_ok": report.repaired_ok,
        "actions": [a.value for a in report.actions],
    }


def report_to_json(report: RepairReport) -> str:
    return json.dumps(report.to_dict(), default=str)
