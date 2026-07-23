from pathlib import Path

from llm_output_contract.contracts import load_contract
from llm_output_contract.models import Action
from llm_output_contract.repair import (
    close_truncated,
    normalize_python_literals,
    object_repairs,
    quote_unquoted_keys,
    remove_trailing_commas,
    single_to_double_quotes,
    string_repairs,
)

MOD = load_contract(Path("config/contracts/moderation.yaml"))


def test_remove_trailing_comma_object_and_array():
    out, changed = remove_trailing_commas('{"a": [1, 2,], "b": 3,}')
    assert changed
    assert out == '{"a": [1, 2], "b": 3}'


def test_quote_unquoted_keys():
    out, changed = quote_unquoted_keys('{label: "allow", confidence: 0.5}')
    assert changed
    assert out == '{"label": "allow", "confidence": 0.5}'


def test_single_to_double_quote():
    out, changed = single_to_double_quotes("{'a': 'b'}")
    assert changed
    assert out == '{"a": "b"}'


def test_single_quote_leaves_apostrophe_in_double_string():
    text = '{"summary": "it\'s fine"}'
    out, changed = single_to_double_quotes(text)
    assert changed is False
    assert out == text


def test_normalize_python_literals_outside_strings():
    out, changed = normalize_python_literals('{"ok": True, "note": "True story"}')
    assert changed
    assert out == '{"ok": true, "note": "True story"}'


def test_close_truncated_appends_closers():
    out, changed = close_truncated('{"label": "allow", "reasons": ["a", "b"')
    assert changed
    assert out == '{"label": "allow", "reasons": ["a", "b"]}'


def test_close_truncated_drops_dangling_comma():
    out, changed = close_truncated('{"reasons": ["a",')
    assert changed
    assert out == '{"reasons": ["a"]}'


def test_string_repairs_stops_early_when_parseable():
    obj, actions = string_repairs('{"label": "allow"}')
    assert obj == {"label": "allow"}
    assert actions == []


def test_object_repairs_coerce_number_from_string():
    obj, actions = object_repairs(
        {"label": "allow", "confidence": "0.8", "reasons": []}, MOD
    )
    assert obj["confidence"] == 0.8
    assert Action.COERCE_TYPES in actions


def test_object_repairs_enum_alias_snapped():
    obj, actions = object_repairs(
        {"label": "blocked", "confidence": 0.9, "reasons": []}, MOD
    )
    assert obj["label"] == "block"
    assert Action.COERCE_ENUM in actions


def test_object_repairs_fills_optional_default_only():
    obj, actions = object_repairs(
        {"label": "allow", "confidence": 0.5, "reasons": []}, MOD
    )
    assert obj["category"] == "none"
    assert Action.FILL_DEFAULTS in actions
    # A required field is never fabricated.
    obj2, actions2 = object_repairs({"confidence": 0.5, "reasons": []}, MOD)
    assert "label" not in obj2
