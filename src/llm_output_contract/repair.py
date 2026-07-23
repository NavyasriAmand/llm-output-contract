"""Deterministic repair steps.

Two layers:

1. String-level fixes applied to the extracted candidate before parsing:
   trailing commas, single quotes, unquoted keys, Python literals, and
   truncated closers. Each fix is conservative and reports the action it took.

2. Object-level coercion applied after a successful parse: scalar type
   coercion (a numeric confidence arriving as a string), enum alias snapping,
   and filling defaults for absent optional fields.

No step ever invents a required field. If a required field is missing after
extraction, the repair fails and the engine records it for replay.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .contracts import Contract
from .models import Action

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
# Unquoted object keys: a word char run followed by a colon, preceded by { or ,
_UNQUOTED_KEY = re.compile(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


def remove_trailing_commas(text: str) -> tuple[str, bool]:
    new = _TRAILING_COMMA.sub(r"\1", text)
    return new, new != text


def quote_unquoted_keys(text: str) -> tuple[str, bool]:
    new = _UNQUOTED_KEY.sub(r'\1"\2"\3', text)
    return new, new != text


def single_to_double_quotes(text: str) -> tuple[str, bool]:
    """Swap single-quoted strings for double quotes.

    Only fires when there are single quotes and no unescaped double quotes
    acting as string delimiters would be ambiguous. Conservative: it rewrites
    'foo' style tokens, leaving apostrophes inside double-quoted strings alone.
    """
    if "'" not in text:
        return text, False
    # Replace 'string' with "string" where the contents have no double quote.
    pattern = re.compile(r"'([^'\"]*)'")
    new = pattern.sub(r'"\1"', text)
    return new, new != text


def normalize_python_literals(text: str) -> tuple[str, bool]:
    """Turn Python True/False/None into JSON true/false/null outside strings."""
    changed = False
    out = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        for lit, repl in (("True", "true"), ("False", "false"), ("None", "null")):
            if text.startswith(lit, i) and (
                i + len(lit) == len(text) or not text[i + len(lit)].isalnum()
            ):
                out.append(repl)
                i += len(lit)
                changed = True
                break
        else:
            out.append(ch)
            i += 1
    return "".join(out), changed


def close_truncated(text: str) -> tuple[str, bool]:
    """Append missing closers for an object cut off mid-stream.

    Counts unmatched '{' and '[' outside strings and appends the right closers.
    A dangling trailing comma is dropped first. Does not attempt to complete a
    truncated key or value; that would be guessing.
    """
    depth_curly = 0
    depth_square = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth_curly += 1
        elif ch == "}":
            depth_curly -= 1
        elif ch == "[":
            depth_square += 1
        elif ch == "]":
            depth_square -= 1
    if in_string or (depth_curly <= 0 and depth_square <= 0):
        return text, False
    fixed = text.rstrip()
    fixed = re.sub(r",\s*$", "", fixed)
    fixed += "]" * max(0, depth_square)
    fixed += "}" * max(0, depth_curly)
    return fixed, fixed != text


def try_parse(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def string_repairs(text: str) -> tuple[Any | None, list[Action]]:
    """Apply string fixes in order, re-parsing after each.

    Returns the parsed object (or None) and the list of actions that fired.
    Stops early as soon as the text parses.
    """
    actions: list[Action] = []

    obj = try_parse(text)
    if obj is not None:
        return obj, actions

    steps = [
        (remove_trailing_commas, Action.REMOVE_TRAILING_COMMA),
        (single_to_double_quotes, Action.SINGLE_TO_DOUBLE_QUOTE),
        (quote_unquoted_keys, Action.QUOTE_KEYS),
        (normalize_python_literals, Action.PY_LITERALS),
        (close_truncated, Action.CLOSE_TRUNCATED),
    ]
    for fn, action in steps:
        text, changed = fn(text)
        if changed:
            actions.append(action)
            obj = try_parse(text)
            if obj is not None:
                return obj, actions
    return try_parse(text), actions


def _coerce_scalar(value: Any, expected: str) -> tuple[Any, bool]:
    if expected == "number" and isinstance(value, str):
        try:
            return float(value), True
        except ValueError:
            return value, False
    if expected == "integer" and isinstance(value, str):
        try:
            return int(value), True
        except ValueError:
            return value, False
    if expected == "string" and isinstance(value, (int, float, bool)):
        return str(value), True
    return value, False


def object_repairs(
    obj: dict[str, Any], contract: Contract
) -> tuple[dict[str, Any], list[Action]]:
    """Coerce scalar types, snap enum aliases, fill optional defaults."""
    actions: list[Action] = []
    props = contract.schema.get("properties", {})

    coerced_any = False
    for key, spec in props.items():
        if key in obj and "type" in spec and not isinstance(spec["type"], list):
            new_val, did = _coerce_scalar(obj[key], spec["type"])
            if did:
                obj[key] = new_val
                coerced_any = True
    if coerced_any:
        actions.append(Action.COERCE_TYPES)

    snapped_any = False
    for field, cfg in contract.enum_coercions.items():
        if field in obj and isinstance(obj[field], str):
            allowed = cfg.get("allowed", [])
            if obj[field] not in allowed:
                aliases = cfg.get("aliases", {})
                key = obj[field].strip().lower()
                if key in aliases:
                    obj[field] = aliases[key]
                    snapped_any = True
                elif obj[field].strip() in allowed:
                    obj[field] = obj[field].strip()
                    snapped_any = True
    if snapped_any:
        actions.append(Action.COERCE_ENUM)

    filled_any = False
    for field, default in contract.defaults.items():
        if field in contract.optional_fields() and field not in obj:
            obj[field] = default
            filled_any = True
    if filled_any:
        actions.append(Action.FILL_DEFAULTS)

    return obj, actions
