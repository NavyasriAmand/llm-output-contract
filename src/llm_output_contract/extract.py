"""Locate a JSON object inside noisy model text.

Models wrap JSON in markdown fences, prefix it with prose ("Here is the
result:"), or append a trailing explanation. This module isolates the JSON
substring so the repair layer can work on just that span.

The brace scanner is string-aware: braces that appear inside a JSON string
literal must not affect nesting depth, and an escaped quote inside a string
must not end the string. Getting this wrong is the source of the war story
documented in the README.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def strip_code_fence(text: str) -> tuple[str, bool]:
    """Return the contents of the first ```...``` block, if any."""
    m = _FENCE.search(text)
    if m:
        return m.group(1).strip(), True
    return text, False


def find_json_span(text: str) -> str | None:
    """Return the substring of the first balanced top-level object.

    Scans for the first '{' and walks forward tracking nesting depth while
    respecting string literals and escapes. Returns None if no balanced
    object is present (the structure may be truncated, which the repair layer
    handles separately).
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
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
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def candidate_json(text: str) -> tuple[str, bool]:
    """Best-effort isolation of the JSON payload.

    Returns (candidate_text, fenced) where fenced indicates a code fence was
    stripped. If no balanced object is found, returns the fence-stripped text
    from the first brace onward so the repair layer can attempt truncation
    recovery.
    """
    body, fenced = strip_code_fence(text)
    span = find_json_span(body)
    if span is not None:
        return span, fenced
    start = body.find("{")
    if start != -1:
        return body[start:].strip(), fenced
    return body.strip(), fenced
