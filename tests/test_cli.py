"""CLI orchestration tests."""
from __future__ import annotations

from src import cli


def test_all_aborts_when_doctor_fails(tmpdb, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(cli.doctor, "run", lambda: 1)
    monkeypatch.setattr(cli, "cmd_seed", lambda args: calls.append("seed") or 0)

    assert cli.main(["all"]) == 1
    assert calls == []
    row = tmpdb.execute("SELECT command, status, error_count FROM pipeline_runs").fetchone()
    assert row["command"] == "all"
    assert row["status"] == "error"
    assert row["error_count"] == 1


def test_all_records_ok_when_steps_succeed_with_skip_doctor(tmpdb, monkeypatch):
    for name in (
        "cmd_seed",
        "cmd_prices",
        "cmd_harvest",
        "cmd_fulltext",
        "cmd_insider",
        "cmd_tweets",
        "cmd_diffwatch",
        "cmd_enrich",
        "cmd_score",
        "cmd_paper",
        "cmd_monitor",
        "cmd_digest",
    ):
        monkeypatch.setattr(cli, name, lambda args, step=name: 0)

    assert cli.main(["all", "--skip-doctor"]) == 0
    row = tmpdb.execute("SELECT command, status, error_count FROM pipeline_runs").fetchone()
    assert row["command"] == "all"
    assert row["status"] == "ok"
    assert row["error_count"] == 0


def test_consensus_cli_prints_unknown_without_metrics(tmpdb, capsys):
    assert cli.main(["consensus", "TST"]) == 0
    assert "TST: unknown" in capsys.readouterr().out


def test_sources_cli_returns_zero_when_no_stale_sources(tmpdb, capsys):
    assert cli.main(["sources"]) == 0
    assert "source feeds: all fresh/ok" in capsys.readouterr().out


def test_exitplans_cli_creates_defaults_for_open_positions(tmpdb, capsys):
    tmpdb.execute(
        "INSERT INTO positions (ticker, cost_basis, shares, high_water, last_price, pnl_pct) "
        "VALUES ('TST', 10, 1, 10, 10, 0)"
    )
    tmpdb.commit()
    assert cli.main(["exitplans"]) == 0
    assert "exit plans: +1" in capsys.readouterr().out


def test_pairwatch_cli_runs_without_candidates(tmpdb, capsys):
    assert cli.main(["pairwatch", "--snapshot"]) == 0
    assert "pair watchlist:" in capsys.readouterr().out
