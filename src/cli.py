"""Entry point. `py -m src.cli <command>`.

Commands:
    init        - create the SQLite schema
    seed        - load chokepoint-database.csv + write keyword dict
    harvest     - pull recent EDGAR 8-K/10-Q/10-K and keyword-filter
    fulltext    - fetch full filing document bodies into the filings table
    enrich      - ask the local Claude bridge for structured A/B/C/D evidence
    prices      - refresh prices via yfinance and recompute crowd contamination
    insider     - harvest recent Form 4 insider transactions
    tweets      - harvest tweets from smart-money X accounts via nitter
    diffwatch   - snapshot customer-partner pages and flag changes
    score       - run the 11-step scoring engine over all chokepoints
    pairs       - print pair-trade candidates from current prices
    pairwatch   - persist pair-trade candidates to a watchlist
    consensus   - print true-vs-consensus state for a ticker
    reverse     - print Serenity follower/crowd reverse alerts
    sources     - print stale or failed source feeds
    monitor     - evaluate exit triggers / drawdown alerts
    exitplans   - create default exit plans for open positions
    paper       - sync paper portfolio (local or Alpaca) with current scores
    size        - calculate and persist Kelly-lite position size
    backtest    - replay crowd-contamination flag against forward returns
    digest      - print + (optionally) post daily digest
    brief       - LLM-written weekly brief from filings + tweets + movers
    doctor      - validate configuration + environment (run this first)
    all         - run the full daily pipeline
"""
from __future__ import annotations

import argparse
import sys

from . import (
    alpaca_paper,
    backtest,
    brief,
    db,
    doctor,
    drawdown,
    exit_plan,
    pair_trade,
    risk_sizing,
    runlog,
    scoring,
    seed,
    source_health,
    strategy_signals,
)
from . import (
    backup as backup_mod,
)
from . import digest as digest_mod
from .enrich import customer_relationships, filing_full, filing_text
from .scrapers import customer_diff, edgar, insider_form4, nitter_x, yf_prices


def cmd_init(args: list[str]) -> int:
    db.init()
    print(f"DB initialized at {db.DB_PATH}")  # type: ignore[attr-defined]
    return 0


def cmd_pairwatch(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="pairwatch")
    p.add_argument("--limit", type=int, help="max number of pair candidates to persist")
    p.add_argument("--snapshot", action="store_true", help="record price/P&L snapshots for open pairs")
    ns = p.parse_args(args)
    n = pair_trade.sync_watchlist(limit=ns.limit)
    s = pair_trade.record_snapshots() if ns.snapshot else 0
    print(f"pair watchlist: +{n} new pair(s), +{s} snapshot(s)")
    return 0


def cmd_consensus(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="consensus")
    p.add_argument("ticker")
    ns = p.parse_args(args)
    print(f"{ns.ticker.upper()}: {strategy_signals.true_vs_consensus(ns.ticker)}")
    return 0


def cmd_reverse(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="reverse")
    p.add_argument("--handle", default="aleabitoreddit")
    p.add_argument("--lookback-days", type=int, default=7)
    p.add_argument("--growth-threshold", type=float, default=15.0)
    ns = p.parse_args(args)
    alerts = strategy_signals.reverse_crowd_alerts(
        handle=ns.handle,
        lookback_days=ns.lookback_days,
        growth_threshold_pct=ns.growth_threshold,
    )
    for alert in alerts:
        print(
            f"{alert['ticker']}: reverse_watch follower_growth="
            f"{alert['follower_growth_pct']:.1f}% signaled_at={alert['signaled_at']}"
        )
    print(f"reverse alerts: {len(alerts)}")
    return 0


def cmd_sources(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="sources")
    p.add_argument("--max-age-hours", type=int, default=24)
    ns = p.parse_args(args)
    rows = source_health.stale_or_failed_sources(max_age_hours=ns.max_age_hours)
    if not rows:
        print("source feeds: all fresh/ok")
        return 0
    for row in rows:
        print(f"{row['source_name']}: {row['status']} errors={row['error_count']} last_error={row['last_error']}")
    return 1


def cmd_seed(args: list[str]) -> int:
    seed.main()
    return 0


def cmd_harvest(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="harvest")
    p.add_argument("--per-form", type=int, default=40, help="filings per form per ticker")
    p.add_argument("--firehose", action="store_true", help="use market-wide getcurrent feed")
    p.add_argument("--ticker", action="append", help="limit to specific ticker(s)")
    ns = p.parse_args(args)
    tickers = ns.ticker if ns.ticker else ([] if ns.firehose else None)
    n = edgar.harvest(per_form=ns.per_form, tickers=tickers)
    print(f"Inserted {n} new filings.")
    return 0


def cmd_enrich(args: list[str]) -> int:
    filing_text.main()
    return 0


def cmd_prices(args: list[str]) -> int:
    yf_prices.main()
    return 0


def cmd_insider(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="insider")
    p.add_argument("--count", type=int, default=40, help="Form 4 filings per ticker")
    p.add_argument("--ticker", action="append", help="limit to specific ticker(s)")
    ns = p.parse_args(args)
    n = insider_form4.harvest(count=ns.count, tickers=ns.ticker)
    print(f"Inserted {n} insider transactions.")
    return 0


def cmd_tweets(args: list[str]) -> int:
    nitter_x.main()
    return 0


def cmd_diffwatch(args: list[str]) -> int:
    customer_diff.main()
    return 0


def cmd_score(args: list[str]) -> int:
    scoring.main()
    return 0


def cmd_pairs(args: list[str]) -> int:
    pair_trade.main()
    return 0


def cmd_monitor(args: list[str]) -> int:
    drawdown.main()
    return 0


def cmd_exitplans(args: list[str]) -> int:
    n = exit_plan.ensure_for_open_positions()
    print(f"exit plans: +{n} default plan(s) for open positions")
    return 0


def cmd_digest(args: list[str]) -> int:
    digest_mod.main()
    return 0


def cmd_brief(args: list[str]) -> int:
    brief.main()
    return 0


def cmd_doctor(args: list[str]) -> int:
    return doctor.run()


def cmd_backup(args: list[str]) -> int:
    out = backup_mod.create_backup()
    if out:
        print(f"backup: wrote {out} ({out.stat().st_size} bytes)")
    else:
        print("backup: source DB missing; nothing to do")
    return 0


def cmd_fulltext(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="fulltext")
    p.add_argument("--limit", type=int, default=25, help="number of filings to fetch")
    p.add_argument("--form", action="append", help="restrict to specific form type(s), e.g. 10-K")
    p.add_argument("--all-forms", action="store_true", help="fetch all form types, not just 8-K")
    ns = p.parse_args(args)
    if ns.form:
        forms = tuple(ns.form)
    elif ns.all_forms:
        forms = None
    else:
        forms = ("8-K",)
    res = filing_full.fetch_recent(limit=ns.limit, forms=forms)
    print(
        f"filing-text fetch: +{res['fetched']} full docs, "
        f"skipped={res['skipped']}, errors={res['errors']}, "
        f"govt-flagged filings now={res['govt']}"
    )
    return 0


def cmd_relationships(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="relationships")
    p.add_argument("--limit", type=int, default=500, help="recent filings to scan")
    ns = p.parse_args(args)
    res = customer_relationships.extract_from_filings(limit=ns.limit)
    print(
        f"customer-filing extraction: scanned={res['scanned']}, "
        f"matched={res['matched']}, inserted={res['inserted']}, "
        f"skipped_existing={res['skipped_existing']}"
    )
    return 0


def cmd_backtest(args: list[str]) -> int:
    backtest.main()
    return 0


def cmd_paper(args: list[str]) -> int:
    alpaca_paper.main()
    return 0


def cmd_size(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="size")
    p.add_argument("ticker", help="ticker to size")
    p.add_argument("--account", type=float, required=True, help="account value in USD")
    p.add_argument("--p-win", type=float, required=True, help="win probability (0..1 or 0..100)")
    p.add_argument("--avg-gain", type=float, required=True, help="average gain percent")
    p.add_argument("--avg-loss", type=float, required=True, help="average loss percent")
    p.add_argument("--p-loss", type=float, help="loss probability (defaults to 1 - p_win)")
    p.add_argument("--theme-exposure", type=float, default=0.0, help="current theme exposure percent")
    p.add_argument("--max-single", type=float, default=5.0, help="single-name cap percent")
    p.add_argument("--max-theme", type=float, default=15.0, help="theme cap percent")
    p.add_argument("--days-to-exit", type=float, help="estimated trading days needed to exit")
    p.add_argument("--no-record", action="store_true", help="calculate only, do not persist")
    ns = p.parse_args(args)
    decision = risk_sizing.calculate_position_size(
        ticker=ns.ticker,
        account_value_usd=ns.account,
        p_win=ns.p_win,
        p_loss=ns.p_loss,
        avg_gain_pct=ns.avg_gain,
        avg_loss_pct=ns.avg_loss,
        current_theme_exposure_pct=ns.theme_exposure,
        max_single_name_pct=ns.max_single,
        max_theme_pct=ns.max_theme,
        days_to_exit=ns.days_to_exit,
    )
    row_id = None if ns.no_record else risk_sizing.record_decision(decision)
    suffix = "" if row_id is None else f" (recorded #{row_id})"
    print(
        f"{decision['ticker']}: {decision['decision']} "
        f"{decision['capped_position_pct']:.2f}% = ${decision['dollar_amount']:.2f}{suffix}"
    )
    return 0


def _run_step(name: str, fn, args: list[str], *, critical: bool = False) -> tuple[bool, str | None]:
    """Run a pipeline step, catching exceptions.

    Returns ``(ok, error_message)``. If ``critical=True`` and the step raises,
    the exception is re-raised so the caller aborts the pipeline.
    """
    print(f"[STEP {name}]")
    try:
        code = int(fn(args) or 0)
    except Exception as e:  # noqa: BLE001
        msg = f"{name}: {type(e).__name__}: {e}"
        print(f"  [FAIL] {msg}")
        if critical:
            raise
        return False, msg
    if code != 0:
        msg = f"{name}: exit code {code}"
        print(f"  [FAIL] {msg}")
        if critical:
            raise RuntimeError(msg)
        return False, msg
    return True, None


def cmd_all(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="all")
    p.add_argument("--skip-doctor", action="store_true", help="skip pre-flight health checks")
    ns = p.parse_args(args)
    run_id = runlog.start("all")
    errors: list[str] = []
    try:
        if not ns.skip_doctor:
            doctor_code = doctor.run()
            if doctor_code:
                runlog.finish(
                    run_id,
                    status="error",
                    error_count=1,
                    warnings="doctor failed; pipeline aborted before network work",
                )
                return doctor_code

        # (name, fn, args, critical)
        steps: list[tuple[str, object, list[str], bool]] = [
            ("backup",        cmd_backup,        [],                                False),
            ("seed",          cmd_seed,          [],                                True),
            ("prices",        cmd_prices,        [],                                False),
            ("harvest",       cmd_harvest,       [],                                False),
            ("fulltext-8K",   cmd_fulltext,      ["--form", "8-K", "--limit", "60"], False),
            ("fulltext-10K",  cmd_fulltext,      ["--form", "10-K", "--limit", "40"], False),
            ("relationships", cmd_relationships, ["--limit", "500"],                False),
            ("insider",       cmd_insider,       [],                                False),
            ("tweets",        cmd_tweets,        [],                                False),
            ("diffwatch",     cmd_diffwatch,     [],                                False),
            ("enrich",        cmd_enrich,        [],                                False),
            ("score",         cmd_score,         [],                                True),
            ("paper",         cmd_paper,         [],                                False),
            ("monitor",       cmd_monitor,       [],                                False),
            ("digest",        cmd_digest,        [],                                False),
        ]
        for name, fn, step_args, critical in steps:
            ok, msg = _run_step(name, fn, step_args, critical=critical)
            if not ok and msg:
                errors.append(msg)

        if errors:
            runlog.finish(
                run_id,
                status="warn",
                error_count=len(errors),
                warnings="; ".join(errors)[:2000],
            )
            print(f"\n[ALL] completed with {len(errors)} step failure(s).")
            return 1
        runlog.finish(run_id, status="ok")
        return 0
    except Exception as e:  # noqa: BLE001
        errors.append(str(e))
        runlog.finish(
            run_id,
            status="error",
            error_count=len(errors),
            warnings="; ".join(errors)[:2000],
        )
        print(f"\n[ALL] aborted on critical failure: {e}")
        return 2


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "harvest": cmd_harvest,
    "fulltext": cmd_fulltext,
    "relationships": cmd_relationships,
    "enrich": cmd_enrich,
    "prices": cmd_prices,
    "insider": cmd_insider,
    "tweets": cmd_tweets,
    "diffwatch": cmd_diffwatch,
    "score": cmd_score,
    "pairs": cmd_pairs,
    "pairwatch": cmd_pairwatch,
    "consensus": cmd_consensus,
    "reverse": cmd_reverse,
    "sources": cmd_sources,
    "monitor": cmd_monitor,
    "exitplans": cmd_exitplans,
    "paper": cmd_paper,
    "size": cmd_size,
    "backtest": cmd_backtest,
    "digest": cmd_digest,
    "brief": cmd_brief,
    "doctor": cmd_doctor,
    "backup": cmd_backup,
    "all": cmd_all,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd = argv[0]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return 2
    return int(fn(argv[1:]) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

