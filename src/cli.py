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
    capacity_tracker,
    customer_universe,
    db,
    doctor,
    drawdown,
    exit_plan,
    governance,
    ma_floor,
    pair_trade,
    risk_sizing,
    rotation,
    runlog,
    scoring,
    seed,
    seed_builtin,
    seed_signals,
    signal_feeds,
    source_health,
    strategy_signals,
    supply_chain,
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


def cmd_seed_serenity(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="seed_serenity")
    p.add_argument("--csv", help="path to serenity_signals.csv (default data/seeds/...)")
    ns = p.parse_args(args)
    n = seed_signals.import_serenity_signals(ns.csv)
    print(f"seed_serenity: +{n} rows into serenity_signals")
    return 0


def cmd_seed_followers(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="seed_followers")
    p.add_argument("--csv", help="path to follower_history.csv (default data/seeds/...)")
    ns = p.parse_args(args)
    n = seed_signals.import_follower_history(ns.csv)
    print(f"seed_followers: +{n} rows into follower_history")
    return 0


def cmd_seed_govt(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="seed_govt")
    p.add_argument("--csv", help="path to govt_awards.csv")
    p.add_argument("--builtin", action="store_true", help="load the built-in CHIPS Act seed")
    ns = p.parse_args(args)
    total = 0
    if ns.builtin:
        total += seed_signals.import_builtin_govt()
    if ns.csv:
        total += seed_signals.import_govt_awards(path=ns.csv)
    if not ns.builtin and not ns.csv:
        total += seed_signals.import_govt_awards(path=seed_signals.SEED_DIR / "govt_awards.csv")
    print(f"seed_govt: +{total} rows into govt_awards")
    return 0


def cmd_supplychain(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="supplychain")
    p.add_argument("--builtin", action="store_true", help="seed built-in obvious->supplier links")
    p.add_argument("--for", dest="obvious", help="show suppliers for an obvious-trade ticker")
    ns = p.parse_args(args)
    if ns.builtin:
        n = supply_chain.import_builtin()
        print(f"supplychain: +{n} link rows")
    if ns.obvious:
        rows = supply_chain.upstream_for(ns.obvious)
        if not rows:
            print(f"{ns.obvious.upper()}: no upstream suppliers recorded")
            return 0
        print(f"{ns.obvious.upper()} upstream suppliers (ranked by link strength):")
        for r in rows:
            mcap = r.get("market_cap_usd")
            mcap_str = f"${mcap/1e9:.1f}B" if mcap else "n/a"
            overall = r.get("overall") or "Unknown"
            print(
                f"  {r['supplier_ticker']:<6} link={r['link_strength']:.2f} "
                f"mcap={mcap_str:<8} score={overall:<6} {r.get('rationale') or ''}"
            )
    return 0


def cmd_rotation(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="rotation")
    p.add_argument("--builtin", action="store_true", help="seed builtin theme stages first")
    ns = p.parse_args(args)
    if ns.builtin:
        n = rotation.import_builtin_stages()
        print(f"rotation: +{n} stage rows")
    rows = rotation.compute_rotation_signal()
    for s in rows:
        ret = s["avg_return_20d_pct"]
        ret_str = f"{ret:+.1f}%" if ret is not None else "n/a"
        flag = " *ROTATE*" if s["rotation_to_next"] else ""
        print(f"  stage {s['stage_idx']} {s['theme']:<22} 20d={ret_str:<8} {s['signal']}{flag}")
    return 0


def cmd_mafloor(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="mafloor")
    p.add_argument("--builtin", action="store_true", help="seed built-in acquirers before computing")
    p.add_argument("--ticker", help="compute for a single ticker only")
    ns = p.parse_args(args)
    if ns.builtin:
        n = ma_floor.import_builtin_acquirers()
        print(f"mafloor: +{n} acquirer rows")
    if ns.ticker:
        out = ma_floor.compute_floor(ns.ticker)
        if out:
            print(
                f"{out['ticker']}: floor=${out['estimated_floor_usd']:.0f} "
                f"mcap=${out['current_market_cap_usd']:.0f} "
                f"sv=${out['max_strategic_value_usd']:.0f} acquirers=[{out['acquirers']}]"
            )
        else:
            print(f"{ns.ticker}: no acquirers or no market cap recorded")
        return 0
    n = ma_floor.compute_all_floors()
    print(f"mafloor: recomputed {n} chokepoint floor(s)")
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


def cmd_customer_harvest(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="customer_harvest")
    p.add_argument("--per-form", type=int, default=15, help="filings per customer per form")
    p.add_argument("--bodies", type=int, default=80, help="fulltext bodies to fetch after harvest")
    p.add_argument("--scan-limit", type=int, default=2000, help="filings to scan for relationships")
    ns = p.parse_args(args)
    tickers = customer_universe.extract_customer_tickers()
    print(f"customer universe ({len(tickers)}): {', '.join(tickers) or '(none)'}")
    if not tickers:
        return 0
    inserted = edgar.harvest(
        forms=("10-K", "10-Q", "8-K"),
        per_form=ns.per_form,
        tickers=tickers,
    )
    print(f"customer harvest: +{inserted} filings")
    for form in ("10-K", "10-Q"):
        res = filing_full.fetch_recent(limit=ns.bodies, forms=(form,))
        print(
            f"  fulltext {form}: +{res['fetched']} bodies, "
            f"skipped={res['skipped']}, errors={res['errors']}"
        )
    rel = customer_relationships.extract_from_filings(limit=ns.scan_limit)
    print(
        f"relationships rescan: scanned={rel['scanned']}, matched={rel['matched']}, "
        f"inserted={rel['inserted']}, skipped_existing={rel['skipped_existing']}"
    )
    return 0


def cmd_backtest(args: list[str]) -> int:
    backtest.main()
    return 0


def cmd_seed_all(args: list[str]) -> int:
    results = seed_builtin.seed_all()
    total = 0
    for table, count in sorted(results.items()):
        print(f"  {table}: +{count}")
        total += count
    # Also seed capacity quarterly + governance + supplier pages
    cap_n = capacity_tracker.import_builtin_capacity()
    gov_n = governance.import_builtin_events()
    pages_n = signal_feeds.import_builtin_pages()
    print(f"  capacity_quarterly: +{cap_n}")
    print(f"  governance_events: +{gov_n}")
    print(f"  customer_supplier_pages: +{pages_n}")
    total += cap_n + gov_n + pages_n
    print(f"seed_all: +{total} total rows across all tables")
    return 0


def cmd_signals(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="signals")
    p.add_argument("--edgar", action="store_true", help="scan EDGAR EFTS for sole-source filings")
    p.add_argument("--govt", action="store_true", help="scan Federal Register for CHIPS/semiconductor")
    p.add_argument("--pages", action="store_true", help="check customer supplier page changes")
    p.add_argument("--all", action="store_true", help="run all signal feed scans")
    ns = p.parse_args(args)
    if ns.all or not (ns.edgar or ns.govt or ns.pages):
        results = signal_feeds.scan_all()
        for src, n in sorted(results.items()):
            print(f"  {src}: +{n} alert(s)")
        print(f"signals: +{sum(results.values())} total")
    else:
        total = 0
        if ns.edgar:
            n = signal_feeds.scan_edgar_rss()
            print(f"  edgar_rss: +{n}")
            total += n
        if ns.govt:
            n = signal_feeds.scan_federal_register()
            print(f"  federal_register: +{n}")
            total += n
        if ns.pages:
            n = signal_feeds.scan_customer_pages()
            print(f"  customer_pages: +{n}")
            total += n
        print(f"signals: +{total} alert(s)")
    return 0


def cmd_alerts(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="alerts")
    p.add_argument("--limit", type=int, default=20, help="max alerts to show")
    p.add_argument("--ack", type=int, help="acknowledge alert by ID")
    ns = p.parse_args(args)
    if ns.ack:
        signal_feeds.acknowledge_alert(ns.ack)
        print(f"acknowledged alert #{ns.ack}")
        return 0
    alerts = signal_feeds.unacknowledged_alerts(limit=ns.limit)
    if not alerts:
        print("No unacknowledged alerts.")
        return 0
    for a in alerts:
        ticker = a.get("ticker") or "?"
        print(
            f"  [{a['alert_priority'].upper():>8}] #{a['id']} {ticker:<6} "
            f"{a['source_type']}: {a['title'][:80]}"
        )
    print(f"{len(alerts)} unacknowledged alert(s)")
    return 0


def cmd_capacity(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="capacity")
    p.add_argument("--builtin", action="store_true", help="seed builtin capacity data")
    p.add_argument("--ticker", help="show capacity timeline for a ticker")
    ns = p.parse_args(args)
    if ns.builtin:
        n = capacity_tracker.import_builtin_capacity()
        print(f"capacity: +{n} quarterly data rows")
    if ns.ticker:
        timeline = capacity_tracker.capacity_timeline(ns.ticker)
        if not timeline:
            print(f"{ns.ticker.upper()}: no capacity data")
            return 0
        print(f"{ns.ticker.upper()} capacity timeline:")
        for row in timeline:
            pp = row.get("price_power") or "?"
            print(
                f"  {row['quarter']}: supply={row['supply_units']:.0f} "
                f"demand={row['demand_units']:.0f} gap={row['gap_pct']:.1f}% "
                f"power={pp} ({row.get('unit_label', 'units')})"
            )
        lc = capacity_tracker.chokepoint_lifecycle(ns.ticker)
        if lc:
            print(
                f"  lifecycle: gap={lc['current_gap_pct']:.1f}% trend={lc['gap_trend']} "
                f"exit_signal={'YES' if lc['exit_signal'] else 'no'} "
                f"close={lc.get('estimated_close') or 'n/a'}"
            )
    elif not ns.builtin:
        lifecycles = capacity_tracker.all_lifecycles()
        if not lifecycles:
            print("No capacity data. Run `capacity --builtin` to seed.")
            return 0
        for lc in lifecycles:
            print(
                f"  {lc['ticker']:<6} gap={lc['current_gap_pct']:+.1f}% "
                f"trend={lc['gap_trend']:<10} power={lc['current_price_power']:<10} "
                f"exit={'⚠ YES' if lc['exit_signal'] else 'no'}"
            )
    return 0


def cmd_governance(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="governance")
    p.add_argument("--builtin", action="store_true", help="seed builtin governance events")
    p.add_argument("--ticker", help="show events for a ticker")
    p.add_argument("--ma-only", action="store_true", help="show only M&A signals")
    ns = p.parse_args(args)
    if ns.builtin:
        n = governance.import_builtin_events()
        print(f"governance: +{n} event rows")
    if ns.ma_only:
        events = governance.ma_signals(ns.ticker)
    elif ns.ticker:
        events = governance.recent_events(ns.ticker)
    else:
        events = governance.recent_events()
    for ev in events:
        person = ev.get("person_name") or ""
        ma = " [M&A]" if ev.get("prior_ma_exp") else ""
        print(
            f"  {ev['ticker']:<6} {ev['event_type']:<20} {ev.get('event_date') or '?':<12} "
            f"{person}{ma} — {(ev.get('notes') or '')[:60]}"
        )
    if not ns.builtin and not events:
        print("No governance events. Run `governance --builtin` to seed.")
    return 0


def cmd_supplier_pages(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="supplier_pages")
    p.add_argument("--builtin", action="store_true", help="seed builtin supplier page registry")
    p.add_argument("--scan", action="store_true", help="check all registered pages for changes")
    ns = p.parse_args(args)
    if ns.builtin:
        n = signal_feeds.import_builtin_pages()
        print(f"supplier_pages: +{n} page(s) registered")
    if ns.scan:
        n = signal_feeds.scan_customer_pages()
        print(f"supplier_pages: +{n} change alert(s)")
    if not ns.builtin and not ns.scan:
        db.init()
        with db.connect() as cx:
            rows = cx.execute(
                "SELECT customer_ticker, page_url, last_snapshot_at, enabled "
                "FROM customer_supplier_pages ORDER BY customer_ticker"
            ).fetchall()
        if not rows:
            print("No supplier pages registered. Run `supplier_pages --builtin`.")
            return 0
        for r in rows:
            status = "✓" if r["last_snapshot_at"] else "pending"
            enabled = "on" if r["enabled"] else "off"
            print(f"  {r['customer_ticker']:<6} [{enabled}] {status} {r['page_url']}")
    return 0


def cmd_lifecycle(args: list[str]) -> int:
    p = argparse.ArgumentParser(prog="lifecycle")
    p.add_argument("--ticker", help="show lifecycle for a specific ticker")
    ns = p.parse_args(args)
    if ns.ticker:
        lc = capacity_tracker.chokepoint_lifecycle(ns.ticker)
        if not lc:
            print(f"{ns.ticker.upper()}: insufficient capacity data (need ≥2 quarters)")
            return 0
        print(f"{ns.ticker.upper()} chokepoint lifecycle:")
        print(f"  Current gap: {lc['current_gap_pct']:.1f}%")
        print(f"  Price power: {lc['current_price_power']}")
        print(f"  Trend: {lc['gap_trend']}")
        print(f"  Est. gap close: {lc.get('estimated_close') or 'n/a'}")
        print(f"  EXIT SIGNAL: {'⚠ YES — consider reducing' if lc['exit_signal'] else 'No'}")
        return 0
    lifecycles = capacity_tracker.all_lifecycles()
    if not lifecycles:
        print("No capacity data. Run `capacity --builtin` first.")
        return 0
    print("Chokepoint lifecycle summary:")
    for lc in lifecycles:
        exit_flag = " ⚠EXIT" if lc["exit_signal"] else ""
        print(
            f"  {lc['ticker']:<6} gap={lc['current_gap_pct']:+.1f}% "
            f"trend={lc['gap_trend']:<10} power={lc['current_price_power']:<10}"
            f"{exit_flag}"
        )
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
            ("seed_all",      cmd_seed_all,      [],                                False),
            ("prices",        cmd_prices,        [],                                False),
            ("harvest",       cmd_harvest,       [],                                False),
            ("fulltext-8K",   cmd_fulltext,      ["--form", "8-K", "--limit", "60"], False),
            ("fulltext-10K",  cmd_fulltext,      ["--form", "10-K", "--limit", "40"], False),
            ("relationships", cmd_relationships, ["--limit", "500"],                False),
            ("insider",       cmd_insider,       [],                                False),
            ("tweets",        cmd_tweets,        [],                                False),
            ("diffwatch",     cmd_diffwatch,     [],                                False),
            ("signals",       cmd_signals,       ["--all"],                         False),
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
    "customer_harvest": cmd_customer_harvest,
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
    "seed_serenity": cmd_seed_serenity,
    "seed_followers": cmd_seed_followers,
    "seed_govt": cmd_seed_govt,
    "seed_all": cmd_seed_all,
    "mafloor": cmd_mafloor,
    "rotation": cmd_rotation,
    "supplychain": cmd_supplychain,
    "signals": cmd_signals,
    "alerts": cmd_alerts,
    "capacity": cmd_capacity,
    "governance": cmd_governance,
    "supplier_pages": cmd_supplier_pages,
    "lifecycle": cmd_lifecycle,
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

