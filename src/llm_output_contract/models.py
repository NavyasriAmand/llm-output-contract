"""Domain models. Plain dataclasses to keep the core free of framework types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Action(str, Enum):
    """Codes for each deterministic repair step that fired.

    Recorded per call so the audit log shows *why* a raw output needed work,
    which is the signal a team watches to catch prompt or model drift.
    """

    ALREADY_VALID = "already_valid"
    STRIP_FENCE = "strip_code_fence"
    EXTRACT_OBJECT = "extract_json_object"
    REMOVE_TRAILING_COMMA = "remove_trailing_comma"
    QUOTE_KEYS = "quote_unquoted_keys"
    SINGLE_TO_DOUBLE_QUOTE = "single_to_double_quote"
    PY_LITERALS = "normalize_python_literals"
    CLOSE_TRUNCATED = "close_truncated_structure"
    COERCE_TYPES = "coerce_scalar_types"
    COERCE_ENUM = "coerce_enum_alias"
    FILL_DEFAULTS = "fill_optional_defaults"


@dataclass
class RepairReport:
    """Outcome of running one raw output through the engine."""

    contract: str
    was_valid: bool
    repaired_ok: bool
    actions: list[Action] = field(default_factory=list)
    obj: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "was_valid": self.was_valid,
            "repaired_ok": self.repaired_ok,
            "actions": [a.value for a in self.actions],
            "obj": self.obj,
            "error": self.error,
        }
