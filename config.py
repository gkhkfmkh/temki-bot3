import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def parse_admin_ids(raw: str) -> set[int]:
    result = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError as exc:
            raise ValueError(f"ADMIN_IDS: некорректный Telegram ID {item!r}") from exc
        if value <= 0:
            raise ValueError("ADMIN_IDS должны быть положительными целыми числами")
        result.add(value)
    return result


def parse_chat_id(raw: str) -> int | str | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def percent_env(name: str, default: str) -> float:
    try:
        value = float(os.getenv(name, default).replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{name} должен быть числом") from exc
    if not 0 <= value < 100:
        raise ValueError(f"{name} должен быть от 0 до 100, не включая 100")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    channel_url: str
    channel_username: str
    submissions_chat_id: int | str | None
    require_subscription: bool
    optional_sub_channel_id: int | str | None
    default_fee_percent: float
    default_game_tax_percent: float
    vip_price_stars: int
    broadcast_delay: float
    database_path: str
    redis_url: str | None
    log_level: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or "REPLACE_WITH_REAL_TOKEN" in token:
        raise RuntimeError("Заполните BOT_TOKEN в файле .env: токен выдаёт @BotFather")
    try:
        stars = int(os.getenv("VIP_PRICE_STARS", "299"))
        delay = float(os.getenv("BROADCAST_DELAY", "0.05"))
    except ValueError as exc:
        raise ValueError("VIP_PRICE_STARS должен быть целым, BROADCAST_DELAY — числом") from exc
    if stars < 1 or not 0 <= delay <= 5:
        raise ValueError("VIP_PRICE_STARS должен быть >0, BROADCAST_DELAY — в диапазоне 0..5")
    db_path = Path(os.getenv("DATABASE_PATH", "data/playfunpay.db"))
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    log_level = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Некорректный LOG_LEVEL")
    return Settings(
        bot_token=token,
        admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        channel_url=os.getenv("CHANNEL_URL", "https://t.me/playfunpay").strip(),
        channel_username=os.getenv("CHANNEL_USERNAME", "@playfunpay").strip(),
        submissions_chat_id=parse_chat_id(os.getenv("SUBMISSIONS_CHAT_ID", "")),
        require_subscription=os.getenv("REQUIRE_SUBSCRIPTION", "false").lower() in {"1", "true", "yes", "да"},
        optional_sub_channel_id=parse_chat_id(os.getenv("OPTIONAL_SUB_CHANNEL_ID", "")),
        default_fee_percent=percent_env("DEFAULT_FEE_PERCENT", "5"),
        default_game_tax_percent=percent_env("DEFAULT_GAME_TAX_PERCENT", "10"),
        vip_price_stars=stars,
        broadcast_delay=delay,
        database_path=str(db_path),
        redis_url=os.getenv("REDIS_URL", "").strip() or None,
        log_level=log_level,
    )


settings = load_settings()
