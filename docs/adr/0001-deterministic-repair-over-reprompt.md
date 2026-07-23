# ADR-0001: Deterministic repair over re-prompting the model

## Status
Accepted

## Context
LLMs asked for JSON emit a non-trivial fraction of responses that do not parse
or do not satisfy the target schema: markdown fences, prose preambles, trailing
commas, single quotes, string-typed numbers, enum near-misses, and truncated
streams. The default industry pattern is to detect the failure and re-prompt
the model, often with the error appended. That works, but every re-prompt adds
one full round trip of latency and pays for the prompt and completion tokens a
second time. At scale this is a real, recurring cost on the exact requests that
already misbehaved once.

## Options considered
1. **Re-prompt on every parse or validation failure.** Simple, high recall, but
   doubles cost and latency on the failing slice and offers no bound on retries.
2. **Constrained decoding / grammar-forced generation.** Strong guarantees, but
   requires control of the serving stack and is unavailable behind hosted APIs
   like GPT-4. Not portable across the providers this project targets.
3. **Deterministic post-hoc repair (chosen).** A fixed, ordered pipeline of
   conservative string and object transformations that never calls the model.
   Fast, free, fully testable, and provider-agnostic.

## Decision
Repair deterministically first. Re-prompting is a fallback the operator can add
later (see the Pivot), not the default path. The repair layer is explicitly
conservative: it restores structure (fences, closers, quotes) and coerces
values the schema pins down (types, enum aliases, optional defaults), but it
never invents a required field or guesses the tail of a truncated token. When
it cannot produce a schema-valid object honestly, it reports failure and stores
the raw output for replay.

## Consequences
- Positive: repair runs in microseconds per output (measured ~12k outputs/sec,
  single thread) with zero token cost. On the benchmark corpus it recovers 100
  percent of the honestly-recoverable outputs, avoiding that many re-prompts.
- Positive: every repair is unit-testable with a known-answer expectation,
  which re-prompting is not.
- Negative: deterministic rules cannot recover outputs that are missing
  required information (a dropped field, a truncated string). Those still need a
  re-prompt or a human. The project treats that tail as out of scope by design
  rather than papering over it, and the benchmark reports it honestly as the gap
  between overall repair rate (80.9 percent) and recoverable-repair rate (100
  percent).
- Negative: the rules encode assumptions about how models misformat JSON. New
  failure shapes require a new rule and a new test, which is a maintenance cost
  the audit log is designed to surface.
