from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import aiosqlite


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat(timespec="seconds")


class Database:
    """Asynchronous SQLite repository; SQL is kept out of handlers."""

    def __init__(self, path: str):
        self.path = str(path)

    async def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','vip','admin')),
                is_banned INTEGER NOT NULL DEFAULT 0 CHECK(is_banned IN (0,1)),
                notify_news INTEGER NOT NULL DEFAULT 1 CHECK(notify_news IN (0,1)),
                notify_tips INTEGER NOT NULL DEFAULT 1 CHECK(notify_tips IN (0,1)),
                calc_count INTEGER NOT NULL DEFAULT 0,
                scan_count INTEGER NOT NULL DEFAULT 0,
                referral_count INTEGER NOT NULL DEFAULT 0,
                referrer_id INTEGER,
                vip_until TEXT,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                calc_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('case','ad','support','scam_report')),
                payload_text TEXT NOT NULL DEFAULT '',
                file_id TEXT,
                file_type TEXT,
                status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','reviewed','answered')),
                admin_reply TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                payload TEXT NOT NULL UNIQUE,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','failed')),
                telegram_charge_id TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_tg_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_active ON users(last_active);
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
            CREATE INDEX IF NOT EXISTS idx_users_vip ON users(vip_until);
            CREATE INDEX IF NOT EXISTS idx_calculations_user ON calculations(tg_id,id DESC);
            CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status,id DESC);
            CREATE INDEX IF NOT EXISTS idx_payments_payload ON payments(payload);
            """)
            await db.commit()

    async def register_user(self, tg_id: int, username: str | None, full_name: str,
                            is_admin: bool = False, referrer_id: int | None = None) -> bool:
        """Insert/update account; returns True only on first registration."""
        now = iso_now()
        role = "admin" if is_admin else "user"
        ref = referrer_id if referrer_id and referrer_id != tg_id else None
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cur = await db.execute(
                "INSERT OR IGNORE INTO users(tg_id,username,full_name,role,referrer_id,created_at,last_active) VALUES(?,?,?,?,?,?,?)",
                (tg_id, username, full_name, role, ref, now, now),
            )
            is_new = cur.rowcount == 1
            await db.execute(
                """UPDATE users SET username=?,full_name=?,last_active=?,
                role=CASE WHEN ?=1 THEN 'admin' WHEN role='admin' THEN 'admin' ELSE role END
                WHERE tg_id=?""",
                (username, full_name, now, int(is_admin), tg_id),
            )
            if is_new and ref:
                await db.execute("UPDATE users SET referral_count=referral_count+1 WHERE tg_id=?", (ref,))
            await db.commit()
            return is_new

    async def touch_user(self, tg_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET last_active=? WHERE tg_id=?", (iso_now(), tg_id))
            await db.commit()

    async def get_user(self, tg_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
            row = await cur.fetchone()
            if not row:
                return None
            user = dict(row)
            if user["role"] == "vip" and user["vip_until"]:
                try:
                    if datetime.fromisoformat(user["vip_until"]) <= now_utc():
                        await db.execute("UPDATE users SET role='user',vip_until=NULL WHERE tg_id=?", (tg_id,))
                        await db.commit()
                        user["role"], user["vip_until"] = "user", None
                except ValueError:
                    user["role"], user["vip_until"] = "user", None
            return user

    async def is_banned(self, tg_id: int) -> bool:
        user = await self.get_user(tg_id)
        return bool(user and user["is_banned"])

    async def increment_usage(self, tg_id: int, kind: str) -> None:
        column = {"calc": "calc_count", "scan": "scan_count"}.get(kind)
        if column is None:
            raise ValueError("Unknown usage counter")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {column}={column}+1 WHERE tg_id=?", (tg_id,))
            await db.commit()

    async def save_calculation(self, tg_id: int, kind: str, payload: str, result: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO calculations(tg_id,calc_type,payload,result,created_at) VALUES(?,?,?,?,?)",
                (tg_id, kind, payload, result, iso_now()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def calculation_history(self, tg_id: int, limit: int = 10) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM calculations WHERE tg_id=? ORDER BY id DESC LIMIT ?", (tg_id, limit))
            return [dict(r) for r in await cur.fetchall()]

    async def create_submission(self, tg_id: int, category: str, payload_text: str,
                               file_id: str | None = None, file_type: str | None = None) -> int:
        if category not in {"case", "ad", "support", "scam_report"}:
            raise ValueError("Invalid submission category")
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO submissions(tg_id,category,payload_text,file_id,file_type,status,created_at) VALUES(?,?,?,?,?,'new',?)",
                (tg_id, category, payload_text, file_id, file_type, iso_now()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def get_submission(self, submission_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM submissions WHERE id=?", (submission_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_submissions(self, status: str | None = "new", limit: int = 10) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cur = await db.execute("SELECT * FROM submissions WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
            else:
                cur = await db.execute("SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def update_submission(self, submission_id: int, status: str, reply: str | None = None) -> None:
        if status not in {"new", "reviewed", "answered"}:
            raise ValueError("Invalid submission status")
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE submissions SET status=?,admin_reply=COALESCE(?,admin_reply) WHERE id=?", (status, reply, submission_id))
            await db.commit()

    async def create_payment(self, tg_id: int, payload: str, amount: int, currency: str = "XTR") -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO payments(tg_id,payload,amount,currency,status,created_at) VALUES(?,?,?,?,'pending',?)",
                             (tg_id, payload, amount, currency, iso_now()))
            await db.commit()

    async def get_payment(self, payload: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM payments WHERE payload=?", (payload,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def complete_payment(self, payload: str, tg_id: int, amount: int, currency: str,
                               telegram_charge_id: str, days: int = 30) -> tuple[bool, str | None]:
        """Idempotently marks payment paid and extends VIP under an immediate transaction."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN IMMEDIATE")
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM payments WHERE payload=?", (payload,))
            payment = await cur.fetchone()
            if not payment:
                await db.rollback()
                return False, "Payment not found"
            p = dict(payment)
            if p["tg_id"] != tg_id or p["amount"] != amount or p["currency"] != currency:
                await db.rollback()
                return False, "Payment details mismatch"
            if p["status"] == "paid":
                await db.rollback()
                user = await self.get_user(tg_id)
                return True, user["vip_until"] if user else None
            cur = await db.execute("SELECT vip_until FROM users WHERE tg_id=?", (tg_id,))
            user = await cur.fetchone()
            if not user:
                await db.rollback()
                return False, "User not found"
            base = now_utc()
            if user["vip_until"]:
                try:
                    existing = datetime.fromisoformat(user["vip_until"])
                    if existing > base:
                        base = existing
                except ValueError:
                    base = now_utc()
            expiry = (base + timedelta(days=days)).isoformat(timespec="seconds")
            await db.execute("UPDATE users SET role=CASE WHEN role='admin' THEN 'admin' ELSE 'vip' END,vip_until=? WHERE tg_id=?", (expiry, tg_id))
            await db.execute("UPDATE payments SET status='paid',telegram_charge_id=?,paid_at=? WHERE payload=?",
                             (telegram_charge_id, iso_now(), payload))
            await db.commit()
            return True, expiry

    async def get_broadcast_user_ids(self, segment: str = "all") -> list[int]:
        where = "is_banned=0"
        if segment == "news":
            where += " AND notify_news=1"
        elif segment == "tips":
            where += " AND notify_tips=1"
        elif segment != "all":
            raise ValueError("Unknown broadcast segment")
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(f"SELECT tg_id FROM users WHERE {where}")
            return [int(row[0]) for row in await cur.fetchall()]

    async def set_banned(self, tg_id: int, banned: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET is_banned=? WHERE tg_id=?", (int(banned), tg_id))
            await db.commit()

    async def set_notification(self, tg_id: int, kind: str, enabled: bool) -> None:
        column = {"news": "notify_news", "tips": "notify_tips"}.get(kind)
        if not column:
            raise ValueError("Unknown notification setting")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {column}=? WHERE tg_id=?", (int(enabled), tg_id))
            await db.commit()

    async def statistics(self) -> dict[str, int]:
        now = now_utc()
        active24 = (now - timedelta(hours=24)).isoformat(timespec="seconds")
        active7 = (now - timedelta(days=7)).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            async def count(sql: str, params: tuple = ()) -> int:
                cur = await db.execute(sql, params)
                row = await cur.fetchone()
                return int(row[0] or 0)
            return {
                "users": await count("SELECT COUNT(*) FROM users"),
                "active24": await count("SELECT COUNT(*) FROM users WHERE last_active>=?", (active24,)),
                "active7": await count("SELECT COUNT(*) FROM users WHERE last_active>=?", (active7,)),
                "banned": await count("SELECT COUNT(*) FROM users WHERE is_banned=1"),
                "calculations": await count("SELECT COALESCE(SUM(calc_count),0) FROM users"),
                "scans": await count("SELECT COALESCE(SUM(scan_count),0) FROM users"),
                "submissions": await count("SELECT COUNT(*) FROM submissions"),
                "new_submissions": await count("SELECT COUNT(*) FROM submissions WHERE status='new'"),
                "vip": await count("SELECT COUNT(*) FROM users WHERE role='vip' AND vip_until>?", (iso_now(),)),
                "payments": await count("SELECT COUNT(*) FROM payments WHERE status='paid'"),
            }

    async def audit(self, admin_id: int, action: str, details: str = "") -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO audit_log(admin_tg_id,action,details,created_at) VALUES(?,?,?,?)",
                             (admin_id, action, details[:1000], iso_now()))
            await db.commit()
