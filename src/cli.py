"""Entry point. `py -m src.cli <command>`.

Commands:
    init      - create the SQLite schema
    seed      - load chokepoint-database.csv + write keyword dict
    harvest   - pull recent EDGAR filings and keyword-filter
    score     - run the 11-step scoring engine over all chokepoints
    digest    - print + (optionally) post daily digest
    all       - run seed -> harvest -> score -> digest
"""
from __future__ import annotations
import sys
from . import db, seed, scoring, digest as digest_mod
from .scrapers import edgar


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


def cmd_score() -> int:
    scoring.main()
    return 0


def cmd_digest() -> int:
    digest_mod.main()
    return 0


def cmd_all() -> int:
    cmd_seed()
    cmd_harvest()
    cmd_score()
    cmd_digest()
    return 0


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "harvest": cmd_harvest,
    "score": cmd_score,
    "digest": cmd_digest,
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
