"""Configuration, sourced from environment variables with defaults.

Nothing operational is hardcoded in modules. Paths, the audit database
location, and the re-prompt cost model all live here so the same code runs
unchanged in a test, a container, or a CI job.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_ROOT.parent.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    """Runtime settings.

    contracts_dir: where task contract packs (YAML) live.
    audit_db: SQLite file for the repair audit log.
    reprompt_tokens: average tokens a naive re-prompt would cost (prompt +
        completion). Used only to translate recovered outputs into a cost
        avoided figure. This is an assumption, stated in the README, not a
        measured latency.
    price_per_1k_tokens: blended input/output price used for the same
        translation. Override both to match a specific deployment.
    """

    contracts_dir: Path = _env_path(
        "LOC_CONTRACTS_DIR", _REPO_ROOT / "config" / "contracts"
    )
    audit_db: Path = _env_path("LOC_AUDIT_DB", _REPO_ROOT / "audit.db")
    schema_ddl: Path = _env_path("LOC_SCHEMA_DDL", _REPO_ROOT / "sql" / "schema.sql")
    reprompt_tokens: float = _env_float("LOC_REPROMPT_TOKENS", 900.0)
    price_per_1k_tokens: float = _env_float("LOC_PRICE_PER_1K_TOKENS", 0.005)

    @property
    def reprompt_cost_usd(self) -> float:
        """Dollar cost of a single avoided re-prompt under the stated model."""
        return (self.reprompt_tokens / 1000.0) * self.price_per_1k_tokens


def load_settings() -> Settings:
    return Settings()
