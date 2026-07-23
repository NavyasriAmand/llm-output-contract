# ADR-0002: jsonschema for the contract layer, not pydantic

## Status
Accepted

## Context
The contract layer needs to answer one question: does this object satisfy the
declared shape? The obvious modern choice in a FastAPI codebase is pydantic,
which is already a transitive dependency and gives ergonomic model classes. The
alternative is JSON Schema validated with the `jsonschema` library, with the
schemas authored as data in YAML.

## Options considered
1. **pydantic models per contract.** Idiomatic in a FastAPI project, fast
   validation, good error messages. But each new contract is a Python class,
   which means a code change and a deploy to add or edit a contract, and the
   schema is expressed in code rather than as a portable artifact.
2. **JSON Schema via jsonschema (chosen).** Contracts are declarative YAML
   files. The same schema string can be handed to a prompt, to a downstream
   consumer, or to a different language runtime unchanged. Adding a contract is
   a config edit, not a deploy.

## Decision
Use JSON Schema (Draft 2020-12) validated by the `jsonschema` library, with
each contract stored as a YAML pack under `config/contracts/`. pydantic is kept
only at the HTTP boundary for request and response shapes, where it earns its
place, and is deliberately not used to express the domain contracts.

This is the boring choice. JSON Schema is older, more verbose, and less
fashionable than pydantic. It is chosen precisely because the contract is data
the organization wants to version, share across services and languages, and
edit without a code deploy. Coupling the contract to a Python class would trade
that portability for ergonomics the project does not need.

## Consequences
- Positive: a contract is added or changed by editing a YAML file; no code
  change, no redeploy of logic. The audit and repair code is agnostic to how
  many contracts exist.
- Positive: the exact schema can be embedded in the model prompt, so the
  contract the model is asked to follow and the contract it is validated
  against are the same artifact, removing a class of drift.
- Positive: portable to any consumer that speaks JSON Schema, including
  non-Python services.
- Negative: JSON Schema error messages are less friendly than pydantic's and
  need light formatting for humans. Acceptable, since the primary consumers of
  errors here are the repair pipeline and the audit log, not end users.
- Negative: schema authoring is more verbose than a pydantic class. Mitigated by
  keeping contracts small and focused on the fields that matter.
