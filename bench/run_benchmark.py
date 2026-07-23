"""Run the repair engine over the synthetic corpus and record real metrics.

Metrics captured (all from the actual run, none stated):
  - repair_rate: fraction of initially-invalid outputs made valid by repair.
  - recoverable_repair_rate: same, restricted to defects the generator marks
    as recoverable. This is the number that measures the engine, isolated from
    the deliberately-unfixable tail.
  - throughput: outputs processed per second, in-process, single thread.
  - reprompts_avoided and cost_avoided_usd: for every initially-invalid output
    the engine recovered, a naive pipeline would have re-called the model.
    The dollar figure multiplies recovered count by the stated re-prompt token
    cost from Settings. The token count and price are assumptions, printed in
    the output so they can never be quoted without their basis.

Usage:
    python bench/run_benchmark.py --corpus bench/corpus.jsonl \
        --out bench/results/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from llm_output_contract.config import load_settings
from llm_output_contract.contracts import load_all
from llm_output_contract.engine import repair_output


def run(corpus_path: Path) -> dict:
    settings = load_settings()
    contracts = load_all(settings.contracts_dir)

    rows = [json.loads(line) for line in corpus_path.read_text().splitlines() if line]

    total = len(rows)
    already_valid = 0
    invalid = 0
    repaired = 0
    recoverable_total = 0
    recoverable_repaired = 0
    by_defect = Counter()
    by_defect_fixed = Counter()

    start = time.perf_counter()
    for row in rows:
        contract = contracts[row["contract"]]
        report = repair_output(row["raw"], contract)
        defect = row.get("defect", "unknown")
        by_defect[defect] += 1
        if report.was_valid:
            already_valid += 1
            continue
        invalid += 1
        if row.get("recoverable"):
            recoverable_total += 1
        if report.repaired_ok:
            repaired += 1
            by_defect_fixed[defect] += 1
            if row.get("recoverable"):
                recoverable_repaired += 1
    elapsed = time.perf_counter() - start

    reprompts_avoided = repaired
    cost_avoided = reprompts_avoided * settings.reprompt_cost_usd

    return {
        "corpus_size": total,
        "already_valid": already_valid,
        "initially_invalid": invalid,
        "repaired": repaired,
        "repair_rate": round(repaired / invalid, 4) if invalid else 0.0,
        "recoverable_invalid": recoverable_total,
        "recoverable_repair_rate": (
            round(recoverable_repaired / recoverable_total, 4)
            if recoverable_total
            else 0.0
        ),
        "elapsed_seconds": round(elapsed, 4),
        "throughput_per_sec": round(total / elapsed, 1) if elapsed else 0.0,
        "reprompts_avoided": reprompts_avoided,
        "assumptions": {
            "reprompt_tokens": settings.reprompt_tokens,
            "price_per_1k_tokens": settings.price_per_1k_tokens,
            "reprompt_cost_usd_each": round(settings.reprompt_cost_usd, 6),
        },
        "cost_avoided_usd": round(cost_avoided, 4),
        "by_defect": dict(by_defect),
        "by_defect_fixed": dict(by_defect_fixed),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="bench/corpus.jsonl")
    ap.add_argument("--out", default="bench/results/benchmark.json")
    args = ap.parse_args()

    result = run(Path(args.corpus))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
