"""FastAPI wrapper around the repair engine.

One endpoint, POST /repair, plus a health check. The service loads contract
packs once at startup and reuses their compiled validators across requests.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import load_settings
from .contracts import load_all
from .engine import repair_output
from .logging_config import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

app = FastAPI(title="llm-output-contract", version="0.1.0")

_settings = load_settings()
_contracts = load_all(_settings.contracts_dir)


class RepairRequest(BaseModel):
    contract: str
    raw: str


class RepairResponse(BaseModel):
    contract: str
    was_valid: bool
    repaired_ok: bool
    actions: list[str]
    obj: dict[str, Any] | None = None
    error: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "contracts": sorted(_contracts.keys())}


@app.post("/repair", response_model=RepairResponse)
def repair(req: RepairRequest) -> RepairResponse:
    contract = _contracts.get(req.contract)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"unknown contract {req.contract}")
    report = repair_output(req.raw, contract)
    return RepairResponse(
        contract=report.contract,
        was_valid=report.was_valid,
        repaired_ok=report.repaired_ok,
        actions=[a.value for a in report.actions],
        obj=report.obj,
        error=report.error,
    )
