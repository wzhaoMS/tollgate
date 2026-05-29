"""Tests for Kelly-lite position sizing."""
from __future__ import annotations

from src import cli, risk_sizing


def test_kelly_lite_pct_uses_quarter_kelly_formula():
    # (0.5*100 - 0.5*40) / 100 * 0.25 = 7.5% portfolio allocation before caps.
    assert risk_sizing.kelly_lite_pct(p_win=0.5, avg_gain_pct=100, avg_loss_pct=40) == 7.5


def test_position_size_caps_single_name_at_five_percent():
    decision = risk_sizing.calculate_position_size(
        ticker="TST",
        account_value_usd=100_000,
        p_win=0.6,
        avg_gain_pct=100,
        avg_loss_pct=20,
    )
    assert decision["capped_position_pct"] == 5.0
    assert decision["dollar_amount"] == 5_000


def test_position_size_respects_theme_remaining_cap():
    decision = risk_sizing.calculate_position_size(
        ticker="TST",
        account_value_usd=100_000,
        p_win=0.6,
        avg_gain_pct=100,
        avg_loss_pct=20,
        current_theme_exposure_pct=14.5,
    )
    assert decision["capped_position_pct"] == 0.5


def test_position_size_zero_when_exit_would_take_more_than_five_days():
    decision = risk_sizing.calculate_position_size(
        ticker="TST",
        account_value_usd=100_000,
        p_win=0.6,
        avg_gain_pct=100,
        avg_loss_pct=20,
        days_to_exit=6,
    )
    assert decision["decision"] == "skip"
    assert decision["capped_position_pct"] == 0.0


def test_record_decision_persists_row(tmpdb):
    decision = risk_sizing.calculate_position_size(
        ticker="TST",
        account_value_usd=100_000,
        p_win=0.5,
        avg_gain_pct=100,
        avg_loss_pct=40,
    )
    row_id = risk_sizing.record_decision(decision)
    assert row_id > 0
    row = tmpdb.execute(
        "SELECT ticker, capped_position_pct FROM position_sizing_decisions WHERE id = ?",
        (row_id,),
    ).fetchone()
    assert row["ticker"] == "TST"
    assert row["capped_position_pct"] == 5.0


def test_size_cli_calculates_without_recording(tmpdb, capsys):
    code = cli.main(
        [
            "size",
            "TST",
            "--account",
            "100000",
            "--p-win",
            "50",
            "--avg-gain",
            "100",
            "--avg-loss",
            "40",
            "--no-record",
        ]
    )
    assert code == 0
    assert "TST: size 5.00%" in capsys.readouterr().out
    assert tmpdb.execute("SELECT COUNT(*) FROM position_sizing_decisions").fetchone()[0] == 0

def test_latest_sizing_for_returns_most_recent(tmpdb):
    d = risk_sizing.calculate_position_size(
        ticker='TST', account_value_usd=100_000, p_win=0.5, avg_gain_pct=100, avg_loss_pct=40,
    )
    risk_sizing.record_decision(d)
    out = risk_sizing.latest_sizing_for('tst')
    assert out is not None
    assert out['ticker'] == 'TST'
    assert out['decision'] == 'size'
    assert out['dollar_amount'] > 0


def test_shares_from_sizing_floors_to_int():
    sizing = {'decision': 'size', 'dollar_amount': 5_000.0}
    assert risk_sizing.shares_from_sizing(sizing, 123.0) == 40
    assert risk_sizing.shares_from_sizing(sizing, 0.0, fallback_qty=2) == 2
    assert risk_sizing.shares_from_sizing(None, 100.0) == 0
    assert risk_sizing.shares_from_sizing({'decision': 'skip', 'dollar_amount': 0}, 100.0) == 0
