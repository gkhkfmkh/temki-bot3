import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.db import Database
from middlewares import ActivityMiddleware
from handlers import common, calculators, seller, contact, premium, admin, fallback


async def create_storage():
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage
        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger("playfunpay")

    db = Database(settings.database_path)
    await db.initialize()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = await create_storage()
    dp = Dispatcher(storage=storage)
    dp["db"] = db

    middleware = ActivityMiddleware(db)
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)

    dp.include_router(common.router)
    dp.include_router(calculators.router)
    dp.include_router(seller.router)
    dp.include_router(contact.router)
    dp.include_router(premium.router)
    dp.include_router(admin.router)
    dp.include_router(fallback.router)

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="help", description="Как пользоваться PlayFunPay"),
            BotCommand(command="cancel", description="Отменить текущий сценарий"),
            ])
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logger.info("PlayFunPay запущен как @%s", me.username)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        await bot.session.close()
        await storage.close()



if __name__ == "__main__":
    asyncio.run(main())
