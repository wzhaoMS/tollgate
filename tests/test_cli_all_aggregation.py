"""Test that cmd_all aggregates step failures and exit codes correctly."""
from __future__ import annotations

import pytest

from src import cli


def _stub_pipeline(monkeypatch, **overrides):
    """Patch the pipeline so cmd_all runs offline. Each step is a no-op
    returning 0 unless overridden."""
    no_op = lambda args: 0  # noqa: E731
    names = [
        "cmd_backup", "cmd_seed", "cmd_prices", "cmd_harvest", "cmd_fulltext",
        "cmd_relationships", "cmd_insider", "cmd_tweets", "cmd_diffwatch",
        "cmd_enrich", "cmd_score", "cmd_paper", "cmd_monitor", "cmd_digest",
    ]
    for n in names:
        monkeypatch.setattr(cli, n, overrides.get(n, no_op))
    monkeypatch.setattr(cli.doctor, "run", lambda: 0)


def test_cmd_all_returns_zero_when_all_steps_succeed(tmpdb, monkeypatch):
    _stub_pipeline(monkeypatch)
    assert cli.cmd_all([]) == 0
    last = tmpdb.execute(
        "SELECT status, error_count FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert last["status"] == "ok"
    assert last["error_count"] == 0


def test_cmd_all_returns_one_when_noncritical_step_fails(tmpdb, monkeypatch):
    def failing(args):
        raise RuntimeError("nitter is down")
    _stub_pipeline(monkeypatch, cmd_tweets=failing)
    assert cli.cmd_all([]) == 1
    last = tmpdb.execute(
        "SELECT status, error_count, warnings FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert last["status"] == "warn"
    assert last["error_count"] == 1
    assert "tweets" in last["warnings"]


def test_cmd_all_aborts_on_critical_step_failure(tmpdb, monkeypatch):
    called: list[str] = []

    def make_tracker(name):
        def fn(args):
            called.append(name)
            return 0
        return fn

    def failing_score(args):
        called.append("score")
        raise RuntimeError("scoring failed hard")

    overrides = {f"cmd_{n}": make_tracker(n) for n in [
        "backup", "seed", "prices", "harvest", "fulltext", "relationships",
        "insider", "tweets", "diffwatch", "enrich", "paper", "monitor", "digest",
    ]}
    overrides["cmd_score"] = failing_score
    _stub_pipeline(monkeypatch, **overrides)

    assert cli.cmd_all([]) == 2
    # Steps after `score` (paper/monitor/digest) must NOT have run.
    assert "score" in called
    for after in ("paper", "monitor", "digest"):
        assert after not in called

    last = tmpdb.execute(
        "SELECT status, error_count FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert last["status"] == "error"
    assert last["error_count"] >= 1


def test_cmd_all_aborts_when_doctor_fails(tmpdb, monkeypatch):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(cli.doctor, "run", lambda: 1)
    assert cli.cmd_all([]) == 1
    last = tmpdb.execute(
        "SELECT status, warnings FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert last["status"] == "error"
    assert "doctor" in (last["warnings"] or "")


@pytest.mark.parametrize("skip", [["--skip-doctor"]])
def test_cmd_all_skip_doctor(tmpdb, monkeypatch, skip):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(cli.doctor, "run", lambda: 1)  # would normally abort
    assert cli.cmd_all(skip) == 0
