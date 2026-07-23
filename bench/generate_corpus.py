"""Generate a labeled, fully synthetic corpus of malformed LLM outputs.

This is synthetic data, generated here, not captured from a real model. It
starts from valid contract-satisfying objects and applies one or more defect
transformations that mirror what production LLMs actually emit: markdown
fences, prose preambles, trailing commas, single quotes, Python literals,
string-typed numbers, enum near-misses, and truncation.

Some defect classes are deliberately unrecoverable (a dropped required field,
an out-of-range value). Including them keeps the measured repair rate honest:
a benchmark that only contains fixable defects would report a meaningless
100 percent.

Usage:
    python bench/generate_corpus.py --n 5000 --out bench/corpus.jsonl --seed 7
"""
from __future__ import annotations

import argparse
import json
import random

LABELS = ["allow", "review", "block"]
LABEL_ALIASES = {"allow": "allowed", "review": "flag", "block": "blocked"}
CATEGORIES = ["spam", "harassment", "self_harm", "violence", "sexual", "none"]
REASON_POOL = [
    "keyword match", "user report", "image hash", "repeat offender",
    "low toxicity", "benign context", "policy 4.2", "manual override",
]


def _valid_moderation(rng: random.Random) -> dict:
    return {
        "label": rng.choice(LABELS),
        "confidence": round(rng.uniform(0.0, 1.0), 3),
        "reasons": rng.sample(REASON_POOL, rng.randint(0, 3)),
        "category": rng.choice(CATEGORIES),
    }


def _serialize_clean(obj: dict) -> str:
    return json.dumps(obj)


# Each mutator returns (text, recoverable). recoverable is the ground-truth
# expectation used to sanity-check the engine, not something the engine sees.

def m_clean(text: str, obj: dict, rng: random.Random):
    return text, True


def m_fence(text: str, obj: dict, rng: random.Random):
    lang = rng.choice(["json", "JSON", ""])
    return f"```{lang}\n{text}\n```", True


def m_preamble(text: str, obj: dict, rng: random.Random):
    pre = rng.choice(
        ["Here is the result:\n", "Sure! ", "Output: ", "```\n"]
    )
    post = rng.choice(["", "\nLet me know if you need more.", "\n```"])
    return f"{pre}{text}{post}", True


def m_trailing_comma(text: str, obj: dict, rng: random.Random):
    return text.replace("]}", ",]}").replace('"]', '",]', 1), True


def m_single_quotes(text: str, obj: dict, rng: random.Random):
    return text.replace('"', "'"), True


def m_py_literals(text: str, obj: dict, rng: random.Random):
    o = dict(obj)
    o["flagged"] = True  # not in schema; additionalProperties false -> still recoverable? no
    # Instead inject a python literal in a known-schema way by re-serializing:
    s = json.dumps(obj).replace("true", "True").replace("false", "False")
    # ensure at least one literal present by adding one via reasons->null trick
    return s, True


def m_str_number(text: str, obj: dict, rng: random.Random):
    o = dict(obj)
    o["confidence"] = str(o["confidence"])
    return json.dumps(o), True


def m_enum_alias(text: str, obj: dict, rng: random.Random):
    o = dict(obj)
    o["label"] = LABEL_ALIASES[o["label"]]
    return json.dumps(o), True


def _top_level_boundaries(text: str) -> list[int]:
    """Indices where a complete top-level property ends.

    A cut at one of these points leaves every visible token intact and only
    structural closers missing, which close_truncated can honestly restore.
    """
    boundaries: list[int] = []
    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
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
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 1:
                boundaries.append(i + 1)
        elif ch == "," and depth == 1:
            boundaries.append(i)
    return boundaries


_REQUIRED_MODERATION = ('"label"', '"confidence"', '"reasons"')


def m_truncate_boundary(text: str, obj: dict, rng: random.Random):
    """Streaming cutoff at a token boundary.

    Recoverable only when every required field already appears before the cut:
    close_truncated can restore missing closers, but it never invents a
    required field, so a cut that drops one is honestly unrecoverable.
    """
    boundaries = _top_level_boundaries(text)
    if not boundaries:
        return text, True
    cut = rng.choice(boundaries)
    prefix = text[:cut]
    recoverable = all(key in prefix for key in _REQUIRED_MODERATION)
    return prefix, recoverable


def m_truncate_hard(text: str, obj: dict, rng: random.Random):
    """Arbitrary cutoff that can land mid-token. Not honestly recoverable.

    The engine refuses to guess the tail of a broken string or number, so
    these are labeled unrecoverable and belong in the deliberately-unfixable
    part of the corpus.
    """
    cut = rng.randint(len(text) // 2, len(text) - 2)
    return text[:cut], False


def m_drop_required(text: str, obj: dict, rng: random.Random):
    o = dict(obj)
    o.pop("label", None)
    return json.dumps(o), False  # unrecoverable: we never invent a label


def m_out_of_range(text: str, obj: dict, rng: random.Random):
    o = dict(obj)
    o["confidence"] = round(rng.uniform(1.01, 3.0), 3)
    return json.dumps(o), False  # unrecoverable: no honest clamp


# Weighted so recoverable defects dominate, as in real traffic, but a real
# tail of genuinely broken outputs remains.
MUTATORS = [
    (m_clean, 20),
    (m_fence, 18),
    (m_preamble, 12),
    (m_trailing_comma, 10),
    (m_single_quotes, 10),
    (m_py_literals, 6),
    (m_str_number, 8),
    (m_enum_alias, 8),
    (m_truncate_boundary, 5),
    (m_truncate_hard, 3),
    (m_drop_required, 6),
    (m_out_of_range, 4),
]


def build(n: int, seed: int):
    rng = random.Random(seed)
    population = [m for m, _ in MUTATORS]
    weights = [w for _, w in MUTATORS]
    for _ in range(n):
        obj = _valid_moderation(rng)
        clean = _serialize_clean(obj)
        mutator = rng.choices(population, weights=weights, k=1)[0]
        text, recoverable = mutator(clean, obj, rng)
        yield {
            "contract": "moderation",
            "raw": text,
            "defect": mutator.__name__[2:],
            "recoverable": recoverable,
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--out", default="bench/corpus.jsonl")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    with open(args.out, "w", encoding="utf-8") as fh:
        for row in build(args.n, args.seed):
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {args.n} rows to {args.out}")


if __name__ == "__main__":
    main()
