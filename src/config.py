"""Central configuration loader. Reads .env if present, falls back to env vars."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

BRIDGE_BASE_URL = os.environ.get("BRIDGE_BASE_URL", "http://localhost:4141/v1")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "dummy")
BRIDGE_MODEL = os.environ.get("BRIDGE_MODEL", "claude-opus-4.7-1m-internal")

EDGAR_USER_AGENT = os.environ.get(
    "EDGAR_USER_AGENT",
    "serenity-killer-playbook contact@example.com",
)
EDGAR_RPS = float(os.environ.get("EDGAR_RPS", "5"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

DB_PATH = Path(os.environ.get("DB_PATH", str(DATA_DIR / "playbook.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
