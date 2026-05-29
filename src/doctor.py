"""Pre-flight health check. Validates configuration and environment so the
pipeline fails fast with actionable messages instead of mid-run surprises.

Run with ``py -m src.cli doctor``. Exit code is non-zero if any *error*-level
check fails (warnings do not fail the run).
"""
from __future__ import annotations

import sqlite3

from . import config

_PLACEHOLDER_AGENTS = {
    "serenity-killer-playbook contact@example.com",
    "contact@example.com",
    "",
}

_EXPECTED_TABLES = {
    "chokepoints",
    "filings",
    "scores",
    "prices",
    "insider_txns",
}


def _check_user_agent() -> tuple[str, str]:
    ua = (config.EDGAR_USER_AGENT or "").strip()
    if ua in _PLACEHOLDER_AGENTS:
        return ("error", "EDGAR_USER_AGENT is the placeholder. SEC requires a real contact "
                         "(e.g. 'YourApp your.name@email.com'). Set it in .env.")
    if "@" not in ua:
        return ("warn", f"EDGAR_USER_AGENT '{ua}' has no email. SEC may rate-limit/block you.")
    return ("ok", f"EDGAR_USER_AGENT set ({ua}).")


def _check_rps() -> tuple[str, str]:
    if config.EDGAR_RPS <= 0:
        return ("warn", "EDGAR_RPS <= 0 disables throttling.")
    if config.EDGAR_RPS > 10:
        return ("warn", f"EDGAR_RPS={config.EDGAR_RPS} exceeds SEC's ~10 req/s guidance.")
    return ("ok", f"EDGAR_RPS={config.EDGAR_RPS} (within SEC guidance).")


def _check_db() -> tuple[str, str]:
    path = config.DB_PATH
    if not path.exists():
        return ("error", f"Database missing at {path}. Run 'py -m src.cli init' then 'seed'.")
    try:
        cx = sqlite3.connect(path)
        have = {r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cx.close()
    except sqlite3.Error as e:
        return ("error", f"Database at {path} is unreadable: {e}")
    missing = _EXPECTED_TABLES - have
    if missing:
        return ("error", f"Database missing tables: {', '.join(sorted(missing))}. Run 'init'.")
    return ("ok", f"Database OK at {path} ({len(have)} tables).")


def _check_seed() -> tuple[str, str]:
    path = config.DB_PATH
    if not path.exists():
        return ("warn", "Skipping seed check (no database).")
    try:
        cx = sqlite3.connect(path)
        n = cx.execute("SELECT COUNT(*) FROM chokepoints").fetchone()[0]
        cx.close()
    except sqlite3.Error as e:
        return ("warn", f"Could not count chokepoints: {e}")
    if n == 0:
        return ("warn", "No chokepoints loaded. Run 'py -m src.cli seed'.")
    return ("ok", f"{n} chokepoints loaded.")


def _check_bridge() -> tuple[str, str]:
    try:
        import requests
    except ImportError:
        return ("warn", "requests not installed; cannot probe the LLM bridge.")
    url = config.BRIDGE_BASE_URL.rstrip("/")
    try:
        r = requests.get(f"{url}/models", timeout=4)
        if r.ok:
            return ("ok", f"LLM bridge reachable at {url}.")
        return ("warn", f"LLM bridge at {url} returned HTTP {r.status_code} "
                        "(enrich/brief will degrade gracefully).")
    except Exception as e:  # noqa: BLE001
        return ("warn", f"LLM bridge not reachable at {url}: {type(e).__name__} "
                        "(enrich/brief will be skipped).")


_CHECKS = (
    ("EDGAR user agent", _check_user_agent),
    ("EDGAR throttle", _check_rps),
    ("Database schema", _check_db),
    ("Seed data", _check_seed),
    ("LLM bridge", _check_bridge),
)

_SYMBOL = {"ok": "[ OK ]", "warn": "[WARN]", "error": "[FAIL]"}


def run() -> int:
    """Run all checks. Return 0 if no error-level failures, else 1."""
    errors = 0
    warns = 0
    print("Serenity-Killer Playbook -- health check\n")
    for label, fn in _CHECKS:
        try:
            level, msg = fn()
        except Exception as e:  # noqa: BLE001
            level, msg = "error", f"check crashed: {e}"
        if level == "error":
            errors += 1
        elif level == "warn":
            warns += 1
        print(f"  {_SYMBOL[level]} {label}: {msg}")
    print()
    if errors:
        print(f"FAIL: {errors} error(s), {warns} warning(s). Fix errors before running the pipeline.")
        return 1
    print(f"OK: 0 errors, {warns} warning(s).")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
