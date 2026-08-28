import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0") or "0")
USER_NAMES = [
    n.strip() for n in os.getenv("USER_NAMES", "Pessoa1,Pessoa2").split(",") if n.strip()
]
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "America/Sao_Paulo"))
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "tvdash.db")
PORT = int(os.getenv("PORT", "8000"))
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "20"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AUTH_ENABLED = _env_bool("AUTH_ENABLED")
WEB_USERNAME = os.getenv("WEB_USERNAME", "")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")
ROKU_API_KEY = os.getenv("ROKU_API_KEY", "")
