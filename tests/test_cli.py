import json

from llm_output_contract.cli import main


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def test_cli_all_recoverable_exits_zero(tmp_path, capsys):
    inp = tmp_path / "in.jsonl"
    _write_jsonl(
        inp,
        [
            {"contract": "moderation", "raw": '{"label":"allow","confidence":0.5,"reasons":[]}'},
            {"contract": "moderation", "raw": "{'label':'blocked','confidence':'0.8','reasons':[]}"},
        ],
    )
    code = main([str(inp), "--max-fail-rate", "0.0"])
    assert code == 0
    err = capsys.readouterr().err
    summary = json.loads(err.strip().splitlines()[-1])
    assert summary["total"] == 2
    assert summary["failed"] == 0


def test_cli_gate_trips_on_failure(tmp_path, capsys):
    inp = tmp_path / "in.jsonl"
    _write_jsonl(
        inp,
        [
            {"contract": "moderation", "raw": '{"confidence":0.5,"reasons":[]}'},  # no label
        ],
    )
    code = main([str(inp), "--max-fail-rate", "0.0"])
    assert code == 1


def test_cli_unknown_contract_reported(tmp_path, capsys):
    inp = tmp_path / "in.jsonl"
    _write_jsonl(inp, [{"contract": "ghost", "raw": "{}"}])
    code = main([str(inp)])
    assert code == 0
    err = capsys.readouterr().err
    assert "unknown contract" in err
