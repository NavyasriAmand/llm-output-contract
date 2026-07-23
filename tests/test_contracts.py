from pathlib import Path

import pytest

from llm_output_contract.contracts import load_all, load_contract


def test_load_moderation_contract():
    c = load_contract(Path("config/contracts/moderation.yaml"))
    assert c.name == "moderation"
    assert "label" in c.required_fields()
    assert "category" in c.optional_fields()


def test_load_all_finds_both_packs():
    packs = load_all(Path("config/contracts"))
    assert set(packs.keys()) == {"moderation", "tagging"}


def test_load_all_raises_when_empty(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_all(tmp_path)


def test_is_valid_and_errors():
    c = load_contract(Path("config/contracts/moderation.yaml"))
    assert c.is_valid({"label": "allow", "confidence": 0.5, "reasons": []})
    errs = c.errors({"label": "nope", "confidence": 0.5, "reasons": []})
    assert errs
