"""Entry point. `py -m src.cli <command>`.

Commands:
    init       - create the SQLite schema
    seed       - load chokepoint-database.csv + write keyword dict
    harvest    - pull recent EDGAR 8-K/10-Q/10-K and keyword-filter
    enrich     - fetch filing text and ask the local Claude bridge for evidence
    prices     - refresh prices via yfinance and recompute crowd contamination
    insider    - harvest recent Form 4 insider transactions
    tweets     - harvest tweets from smart-money X accounts via nitter
    diffwatch  - snapshot customer-partner pages and flag changes
    score      - run the 11-step scoring engine over all chokepoints
    pairs      - print pair-trade candidates from current prices
    monitor    - evaluate exit triggers / drawdown alerts
    digest     - print + (optionally) post daily digest
    brief      - LLM-written weekly brief from filings + tweets + movers
    all        - run the full daily pipeline
"""
from __future__ import annotations
import sys

from . import db, seed, scoring, digest as digest_mod, pair_trade, drawdown, brief
from .scrapers import edgar, yf_prices, insider_form4, nitter_x, customer_diff
from .enrich import filing_text


def cmd_init() -> int:
    db.init()
    print(f"DB initialized at {db.DB_PATH}")  # type: ignore[attr-defined]
    return 0


def cmd_seed() -> int:
    seed.main()
    return 0


def cmd_harvest() -> int:
    edgar.main()
    return 0


def cmd_enrich() -> int:
    filing_text.main()
    return 0


def cmd_prices() -> int:
    yf_prices.main()
    return 0


def cmd_insider() -> int:
    insider_form4.main()
    return 0


def cmd_tweets() -> int:
    nitter_x.main()
    return 0


def cmd_diffwatch() -> int:
    customer_diff.main()
    return 0


def cmd_score() -> int:
    scoring.main()
    return 0


def cmd_pairs() -> int:
    pair_trade.main()
    return 0


def cmd_monitor() -> int:
    drawdown.main()
    return 0


def cmd_digest() -> int:
    digest_mod.main()
    return 0


def cmd_brief() -> int:
    brief.main()
    return 0


def cmd_all() -> int:
    cmd_seed()
    cmd_prices()
    cmd_harvest()
    cmd_insider()
    cmd_tweets()
    cmd_diffwatch()
    cmd_enrich()
    cmd_score()
    cmd_monitor()
    cmd_digest()
    return 0


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "harvest": cmd_harvest,
    "enrich": cmd_enrich,
    "prices": cmd_prices,
    "insider": cmd_insider,
    "tweets": cmd_tweets,
    "diffwatch": cmd_diffwatch,
    "score": cmd_score,
    "pairs": cmd_pairs,
    "monitor": cmd_monitor,
    "digest": cmd_digest,
    "brief": cmd_brief,
    "all": cmd_all,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd = argv[0]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return 2
    return int(fn() or 0)


if __name__ == "__main__":
    raise SystemExit(main())

