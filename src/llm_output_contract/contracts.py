"""Load task contract packs (YAML) into validators and coercion metadata."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class Contract:
    name: str
    version: int
    schema: dict[str, Any]
    defaults: dict[str, Any]
    enum_coercions: dict[str, dict[str, Any]]
    _validator: Draft202012Validator

    def is_valid(self, obj: Any) -> bool:
        return self._validator.is_valid(obj)

    def errors(self, obj: Any) -> list[str]:
        return [e.message for e in self._validator.iter_errors(obj)]

    def required_fields(self) -> set[str]:
        return set(self.schema.get("required", []))

    def optional_fields(self) -> set[str]:
        props = set(self.schema.get("properties", {}).keys())
        return props - self.required_fields()


def load_contract(path: Path) -> Contract:
    data = yaml.safe_load(path.read_text())
    schema = data["schema"]
    Draft202012Validator.check_schema(schema)
    return Contract(
        name=data["name"],
        version=int(data.get("version", 1)),
        schema=schema,
        defaults=data.get("defaults", {}) or {},
        enum_coercions=data.get("enum_coercions", {}) or {},
        _validator=Draft202012Validator(schema),
    )


def load_all(contracts_dir: Path) -> dict[str, Contract]:
    out: dict[str, Contract] = {}
    for path in sorted(contracts_dir.glob("*.yaml")):
        contract = load_contract(path)
        out[contract.name] = contract
    if not out:
        raise FileNotFoundError(f"no contract packs found in {contracts_dir}")
    return out
