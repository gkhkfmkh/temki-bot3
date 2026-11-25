import html
import random
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import settings
from keyboards import home_keyboard, home_only, settings_keyboard, knowledge_keyboard
from data.knowledge_base import TERMS, DAILY_TIPS
from utils import esc

router = Router()
logger = logging.getLogger(__name__)
WELCOME = (
    "🎮 <b>PlayFunPay</b>\n"
    "<i>Панель продавца. Меньше ручной рутины — больше контроля над сделками.</i>\n\n"
    "Считайте экономику лота, проверяйте описание до публикации, отвечайте покупателям, изучайте материалы и связывайтесь с командой.\n\n"
    f"Канал: <a href=\"{esc(settings.channel_url)}\">PlayFunPay</a>\n\n"
    "Выберите инструмент:"
)


def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Открыть канал", url=settings.channel_url)],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="subscription:check")],
    ])


async def subscription_is_ok(bot, user_id: int) -> bool:
    if not settings.require_subscription or not settings.optional_sub_channel_id:
        return True
    try:
        member = await bot.get_chat_member(settings.optional_sub_channel_id, user_id)
        if member.status in {"creator", "administrator", "member"}:
            return True
        return member.status == "restricted" and bool(getattr(member, "is_member", False))
    except Exception:
        # Fail-open: ошибка прав бота не должна навсегда закрыть доступ пользователям.
        logger.exception("Не удалось проверить подписку для user_id=%s", user_id)
        return True


@router.callback_query(F.data == "subscription:check")
async def check_subscription(callback: CallbackQuery, bot):
    if await subscription_is_ok(bot, callback.from_user.id):
        await callback.message.edit_text(WELCOME, reply_markup=home_keyboard(callback.from_user.id in settings.admin_ids))
        await callback.answer("Подписка подтверждена.")
    else:
        await callback.answer("Подписка пока не найдена. Подпишитесь и попробуйте снова.", show_alert=True)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, command: CommandObject, db, bot):
    referrer = None
    arg = command.args or ""
    if arg.startswith("ref_") and arg[4:].isdigit():
        referrer = int(arg[4:])
    await db.register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
        message.from_user.id in settings.admin_ids,
        referrer,
    )
    await state.clear()
    if not await subscription_is_ok(bot, message.from_user.id):
        await message.answer(
            "👋 Добро пожаловать в <b>PlayFunPay</b>!\n\n"
            "Для доступа к инструментам подпишитесь на канал и нажмите «Проверить подписку».",
            reply_markup=subscription_keyboard(),
        )
        return
    greeting = WELCOME
    if message.from_user.first_name:
        greeting = f"👋 Добро пожаловать, <b>{esc(message.from_user.first_name)}</b>!\n\n" + WELCOME
    await message.answer(greeting, reply_markup=home_keyboard(message.from_user.id in settings.admin_ids))


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "ℹ️ <b>Как пользоваться PlayFunPay</b>\n\n"
        "• Калькуляторы считают прибыль, маржу, ROI, цену лота и внутриигровой налог.\n"
        "• Сканер ищет рискованные формулировки, но не заменяет проверку правил площадки.\n"
        "• Конструктор помогает собрать описание по разделам.\n"
        "• В кабинете находятся история расчётов, настройки и реферальная ссылка.\n"
        "• VIP открывает историю до 50 последних расчётов.\n\n"
        "Команда /start возвращает в меню, /cancel отменяет текущий сценарий.",
        reply_markup=home_only(),
    )


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=home_keyboard(message.from_user.id in settings.admin_ids))


@router.message(F.text == "🏠 Главное меню")
async def text_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=home_keyboard(message.from_user.id in settings.admin_ids))


@router.callback_query(F.data == "nav:home")
async def nav_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(WELCOME, reply_markup=home_keyboard(callback.from_user.id in settings.admin_ids))
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def profile(callback: CallbackQuery, db):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await db.register_user(callback.from_user.id, callback.from_user.username,
                               callback.from_user.full_name, callback.from_user.id in settings.admin_ids)
        user = await db.get_user(callback.from_user.id)
    role = "Администратор" if user["role"] == "admin" else "VIP" if user["role"] == "vip" else "Продавец"
    expiry = user["vip_until"][:10] if user["vip_until"] else "не активен"
    text = (
        "👤 <b>Личный кабинет</b>\n\n"
        f"Имя: <b>{esc(user['full_name'])}</b>\n"
        f"Telegram ID: <code>{user['tg_id']}</code>\n"
        f"Статус: <b>{role}</b>\n"
        f"VIP до: <b>{expiry}</b>\n\n"
        f"🧮 Расчётов: <b>{user['calc_count']}</b>\n"
        f"🛡 Проверок текста: <b>{user['scan_count']}</b>\n"
        f"👥 Приглашено пользователей: <b>{user['referral_count']}</b>"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 История расчётов", callback_data="calc:history")],
        [InlineKeyboardButton(text="🔔 Настройки уведомлений", callback_data="menu:settings")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ]))
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
async def settings_menu(callback: CallbackQuery, db):
    user = await db.get_user(callback.from_user.id)
    if not user:
        return await callback.answer("Сначала отправьте /start", show_alert=True)
    await callback.message.edit_text(
        "🔔 <b>Настройки уведомлений</b>\n\nВключайте только те категории сообщений, которые вам полезны.",
        reply_markup=settings_keyboard(user),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"settings:news", "settings:tips"}))
async def toggle_setting(callback: CallbackQuery, db):
    kind = callback.data.split(":")[1]
    user = await db.get_user(callback.from_user.id)
    column = "notify_news" if kind == "news" else "notify_tips"
    await db.set_notification(callback.from_user.id, kind, not bool(user[column]))
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard(user))
    await callback.answer("Настройка обновлена")


@router.callback_query(F.data == "menu:referral")
async def referral(callback: CallbackQuery, db, bot):
    user = await db.get_user(callback.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
    await callback.message.edit_text(
        "🔗 <b>Приглашайте продавцов в PlayFunPay</b>\n\n"
        "Поделитесь персональной ссылкой. Каждый новый пользователь, который впервые запустит бота по ней, будет учтён в статистике приглашений.\n\n"
        f"Ваша ссылка:\n<code>{esc(link)}</code>\n\n"
        f"Приглашено: <b>{user['referral_count']}</b>\n\n"
        "Реферальная ссылка не даёт доступ к чужим данным и пока не является партнёрской выплатой.",
        reply_markup=home_only(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:daily")
async def daily_tip(callback: CallbackQuery):
    await callback.message.edit_text("💡 <b>Совет продавцу</b>\n\n" + random.choice(DAILY_TIPS), reply_markup=home_only())
    await callback.answer()


@router.callback_query(F.data == "menu:knowledge")
async def knowledge(callback: CallbackQuery):
    await callback.message.edit_text(
        f"📚 <b>База знаний PlayFunPay</b>\n\nВ справочнике {len(TERMS)} терминов и практические материалы для продавцов. Выберите раздел:",
        reply_markup=knowledge_keyboard(),
    )
    await callback.answer()
