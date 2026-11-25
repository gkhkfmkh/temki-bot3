from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings


def home_keyboard(is_admin: bool = False):
    b = InlineKeyboardBuilder()
    b.button(text="🧮 Калькуляторы", callback_data="menu:calculators")
    b.button(text="🛠 Инструменты продавца", callback_data="menu:seller")
    b.button(text="📚 База знаний", callback_data="menu:knowledge")
    b.button(text="💬 Ответы покупателям", callback_data="menu:scripts")
    b.button(text="📨 Связь с командой", callback_data="menu:contact")
    b.button(text="💎 PlayFunPay VIP", callback_data="menu:vip")
    b.button(text="👤 Личный кабинет", callback_data="menu:profile")
    b.button(text="🔗 Пригласить продавца", callback_data="menu:referral")
    b.button(text="💡 Совет продавцу", callback_data="menu:daily")
    if is_admin:
        b.button(text="⚙️ Админ-панель", callback_data="admin:home")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()


def home_only():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")]])


def calculators_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="💰 Прибыль, маржа и ROI", callback_data="calc:profit")
    b.button(text="🎯 Цена под сумму на руки", callback_data="calc:reverse")
    b.button(text="🎮 Игровой налог", callback_data="calc:tax")
    b.button(text="🧾 История расчётов", callback_data="calc:history")
    b.button(text="🏠 Главное меню", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()


def percent_keyboard():
    b = InlineKeyboardBuilder()
    default = f"{settings.default_fee_percent:g}"
    values = ["3", "5", "7", "10"]
    if default not in values:
        values.insert(0, default)
    for p in values:
        label = f"⭐ {p}%" if p == default else f"{p}%"
        b.button(text=label, callback_data=f"percent:{p}")
    b.button(text="✍️ Свой процент", callback_data="percent:custom")
    b.button(text="🏠 Отмена / меню", callback_data="nav:home")
    b.adjust(4, 1, 1)
    return b.as_markup()


def tax_mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Покупатель должен получить X", callback_data="taxmode:receive")],
        [InlineKeyboardButton(text="Передаю X — сколько дойдёт?", callback_data="taxmode:send")],
        [InlineKeyboardButton(text="🏠 Отмена / меню", callback_data="nav:home")],
    ])


def seller_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡 Проверить описание", callback_data="seller:scan")],
        [InlineKeyboardButton(text="🧾 Собрать описание лота", callback_data="seller:builder")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


def knowledge_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Словарь FunPay", callback_data="knowledge:terms")],
        [InlineKeyboardButton(text="🗂 Гайды PlayFunPay", callback_data="knowledge:guides")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


def contact_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="📝 Кейс / новость", callback_data="contact:case")
    b.button(text="🤝 Реклама и партнёрство", callback_data="contact:ad")
    b.button(text="💬 Поддержка", callback_data="contact:support")
    b.button(text="🚨 Подозрительная схема", callback_data="contact:scam_report")
    b.button(text="🏠 Главное меню", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()


def admin_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="admin:stats")
    b.button(text="📥 Новые обращения", callback_data="admin:submissions")
    b.button(text="📣 Рассылка", callback_data="admin:broadcast")
    b.button(text="🏠 Главное меню", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()


def submission_keyboard(submission_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Ответить", callback_data=f"admin:reply:{submission_id}")],
        [InlineKeyboardButton(text="✅ Рассмотрено", callback_data=f"admin:review:{submission_id}")],
    ])


def broadcast_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:send")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast:cancel")],
    ])


def settings_keyboard(user: dict):
    news = "✅" if user["notify_news"] else "❌"
    tips = "✅" if user["notify_tips"] else "❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{news} Новости канала", callback_data="settings:news")],
        [InlineKeyboardButton(text=f"{tips} Полезные советы", callback_data="settings:tips")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


def vip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оформить VIP на 30 дней", callback_data="vip:buy")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


def broadcast_segments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Всем пользователям", callback_data="broadcast:segment:all")],
        [InlineKeyboardButton(text="📰 Только новости", callback_data="broadcast:segment:news")],
        [InlineKeyboardButton(text="💡 Только полезные советы", callback_data="broadcast:segment:tips")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")],
    ])
