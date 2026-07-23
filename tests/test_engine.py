from pathlib import Path

from llm_output_contract.contracts import load_contract
from llm_output_contract.engine import repair_output
from llm_output_contract.models import Action

MOD = load_contract(Path("config/contracts/moderation.yaml"))
TAG = load_contract(Path("config/contracts/tagging.yaml"))


def test_already_valid_fast_path():
    r = repair_output('{"label": "allow", "confidence": 0.9, "reasons": []}', MOD)
    assert r.was_valid is True
    assert r.repaired_ok is True
    assert r.actions == [Action.ALREADY_VALID]


def test_fenced_with_multiple_defects_recovers():
    raw = (
        "Here is the moderation result:\n"
        "```json\n"
        '{"label": "blocked", "confidence": "0.8", "reasons": ["spam",]}\n'
        "```"
    )
    r = repair_output(raw, MOD)
    assert r.repaired_ok is True
    assert r.obj["label"] == "block"
    assert r.obj["confidence"] == 0.8
    assert r.obj["category"] == "none"
    assert Action.STRIP_FENCE in r.actions
    assert Action.COERCE_ENUM in r.actions


def test_single_quotes_and_alias():
    r = repair_output("{'label': 'flag', 'confidence': 0.5, 'reasons': ['x']}", MOD)
    assert r.repaired_ok is True
    assert r.obj["label"] == "review"


def test_truncated_array_recovers():
    r = repair_output('{"label": "review", "confidence": 0.6, "reasons": ["a", "b"', MOD)
    assert r.repaired_ok is True
    assert r.obj["reasons"] == ["a", "b"]


def test_unrecoverable_missing_required_field():
    # No label anywhere. We do not invent it, so repair must fail.
    r = repair_output('{"confidence": 0.6, "reasons": []}', MOD)
    assert r.repaired_ok is False
    assert r.error is not None


def test_out_of_range_confidence_fails_validation():
    # Confidence 1.5 violates the schema maximum; there is no honest repair.
    r = repair_output('{"label": "allow", "confidence": 1.5, "reasons": []}', MOD)
    assert r.repaired_ok is False


def test_tagging_contract_recovers_fenced():
    raw = '```\n{tags: ["ai", "ml",], summary: "a post about ml", language: "english"}\n```'
    r = repair_output(raw, TAG)
    assert r.repaired_ok is True
    assert r.obj["language"] == "en"
    assert r.obj["tags"] == ["ai", "ml"]
