from llm_output_contract.extract import (
    candidate_json,
    find_json_span,
    strip_code_fence,
)


def test_strip_plain_fence():
    body, fenced = strip_code_fence("```json\n{\"a\": 1}\n```")
    assert fenced is True
    assert body == '{"a": 1}'


def test_no_fence_passthrough():
    body, fenced = strip_code_fence('{"a": 1}')
    assert fenced is False
    assert body == '{"a": 1}'


def test_find_span_ignores_prose():
    text = 'Sure, here is the answer: {"label": "allow"} hope that helps'
    assert find_json_span(text) == '{"label": "allow"}'


def test_find_span_respects_braces_inside_strings():
    # A brace inside a string value must not end the object early.
    text = '{"summary": "use {curly} carefully", "n": 1}'
    assert find_json_span(text) == text


def test_find_span_respects_escaped_quote():
    text = '{"summary": "she said \\"hi\\"", "n": 1}'
    assert find_json_span(text) == text


def test_find_span_returns_none_when_truncated():
    text = '{"label": "allow", "reasons": ['
    assert find_json_span(text) is None


def test_candidate_json_returns_from_brace_when_truncated():
    text = 'prefix {"label": "allow", "reasons": ['
    cand, fenced = candidate_json(text)
    assert cand.startswith('{"label"')
    assert fenced is False
