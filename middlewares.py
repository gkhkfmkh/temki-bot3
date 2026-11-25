import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    def __init__(self, db):
        self.db = db

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user and not user.is_bot:
            try:
                await self.db.touch_user(user.id)
                if await self.db.is_banned(user.id):
                    if isinstance(event, Message):
                        await event.answer("⛔ Доступ к PlayFunPay ограничен. Для уточнения обратитесь к администрации канала.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("Доступ ограничен.", show_alert=True)
                    return None
            except Exception:
                logger.exception("Middleware activity check failed for tg_id=%s", user.id)
        return await handler(event, data)
