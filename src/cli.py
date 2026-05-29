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
    monitor     - evaluate exit triggers / drawdown alerts
    paper       - sync paper portfolio (local or Alpaca) with current scores
    backtest    - replay crowd-contamination flag against forward returns
    digest      - print + (optionally) post daily digest
    brief       - LLM-written weekly brief from filings + tweets + movers
    doctor      - validate configuration + environment (run this first)
    all         - run the full daily pipeline
"""
from __future__ import annotations

import argparse
import sys

from . import alpaca_paper, backtest, brief, db, doctor, drawdown, pair_trade, scoring, seed
from . import digest as digest_mod
from .enrich import filing_full, filing_text
from .scrapers import customer_diff, edgar, insider_form4, nitter_x, yf_prices


def cmd_init(args: list[str]) -> int:
    db.init()
    print(f"DB initialized at {db.DB_PATH}")  # type: ignore[attr-defined]
    return 0


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


def cmd_digest(args: list[str]) -> int:
    digest_mod.main()
    return 0


def cmd_brief(args: list[str]) -> int:
    brief.main()
    return 0


def cmd_doctor(args: list[str]) -> int:
    return doctor.run()


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


def cmd_backtest(args: list[str]) -> int:
    backtest.main()
    return 0


def cmd_paper(args: list[str]) -> int:
    alpaca_paper.main()
    return 0


def cmd_all(args: list[str]) -> int:
    cmd_seed(args)
    cmd_prices(args)
    cmd_harvest([])
    # 8-K bodies carry catalysts; 10-K risk factors carry CHIPS/DoE govt
    # language that step_4 (govt backstop) keys off of.
    cmd_fulltext(["--form", "8-K", "--limit", "60"])
    cmd_fulltext(["--form", "10-K", "--limit", "40"])
    cmd_insider([])
    cmd_tweets(args)
    cmd_diffwatch(args)
    cmd_enrich(args)
    cmd_score(args)
    cmd_paper(args)
    cmd_monitor(args)
    cmd_digest(args)
    return 0


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "harvest": cmd_harvest,
    "fulltext": cmd_fulltext,
    "enrich": cmd_enrich,
    "prices": cmd_prices,
    "insider": cmd_insider,
    "tweets": cmd_tweets,
    "diffwatch": cmd_diffwatch,
    "score": cmd_score,
    "pairs": cmd_pairs,
    "monitor": cmd_monitor,
    "paper": cmd_paper,
    "backtest": cmd_backtest,
    "digest": cmd_digest,
    "brief": cmd_brief,
    "doctor": cmd_doctor,
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

