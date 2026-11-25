import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import seller_keyboard, home_only, knowledge_keyboard
from states import ListingBuilder, ScanFlow
from services.text_scanner import scan_text
from data.knowledge_base import TERMS, GUIDES, BUYER_SCRIPTS
from utils import esc

router = Router()


@router.callback_query(F.data == "menu:seller")
async def seller_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🛠 <b>Инструменты продавца</b>\n\nПроверьте описание до публикации или соберите новое по понятной структуре.",
        reply_markup=seller_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "seller:scan")
async def scan_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ScanFlow.text)
    await callback.message.edit_text(
        "🛡 <b>Проверка описания лота</b>\n\nОтправьте заголовок или описание одним сообщением. Я отмечу внешние ссылки, рискованные формулировки и дам рекомендации.",
        reply_markup=home_only(),
    )
    await callback.answer()


@router.message(ScanFlow.text)
async def scan_receive(message: Message, state: FSMContext, db):
    if not message.text:
        return await message.answer("Пришлите текстовым сообщением.", reply_markup=home_only())
    if len(message.text) > 6000:
        return await message.answer("Текст слишком длинный. Максимум 6000 символов.", reply_markup=home_only())
    result = scan_text(message.text)
    if result.issues:
        issues = "\n\n".join(
            f"• <b>{esc(item.phrase)}</b> — <b>{item.level}</b>\n"
            f"{esc(item.explanation)}\nСовет: {esc(item.recommendation)}"
            for item in result.issues
        )
    else:
        issues = "Совпадений по текущему словарю не найдено."
    report = (
        "🛡 <b>Отчёт проверки</b>\n\n"
        f"Общий уровень: <b>{esc(result.risk)}</b>\n\n{issues}\n\n"
        f"<b>Итог:</b> {esc(result.advice)}\n\n"
        "<i>Это эвристическая проверка локального словаря, а не официальный валидатор FunPay и не гарантия прохождения модерации.</i>"
    )
    await state.clear()
    await message.answer(report, reply_markup=seller_keyboard())
    await db.increment_usage(message.from_user.id, "scan")


@router.callback_query(F.data == "seller:builder")
async def builder_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ListingBuilder.title)
    await callback.message.edit_text("🧾 <b>Конструктор описания · Шаг 1/5</b>\n\nНапишите название товара или услуги:", reply_markup=home_only())
    await callback.answer()


async def store_step(message: Message, state: FSMContext, key: str, next_state, prompt: str, max_length: int):
    value = (message.text or "").strip()
    if not value:
        return await message.answer("Нужно отправить текст. Для отмены нажмите «Главное меню» или отправьте /cancel.", reply_markup=home_only())
    if len(value) > max_length:
        return await message.answer(f"Слишком длинный ответ. Максимум {max_length} символов.", reply_markup=home_only())
    await state.update_data(**{key: value})
    await state.set_state(next_state)
    await message.answer(prompt, reply_markup=home_only())


@router.message(ListingBuilder.title)
async def builder_title(message: Message, state: FSMContext):
    await store_step(message, state, "title", ListingBuilder.delivery,
                     "Шаг 2/5. Как происходит выдача? Например: автоматическая выдача ключа, ручная передача, выполнение услуги без входа в аккаунт.", 180)


@router.message(ListingBuilder.delivery)
async def builder_delivery(message: Message, state: FSMContext):
    await store_step(message, state, "delivery", ListingBuilder.timing,
                     "Шаг 3/5. Укажите реальные сроки выполнения и часы доступности.", 350)


@router.message(ListingBuilder.timing)
async def builder_timing(message: Message, state: FSMContext):
    await store_step(message, state, "timing", ListingBuilder.requirements,
                     "Шаг 4/5. Какие требования есть к покупателю? Не запрашивайте пароли и одноразовые коды.", 500)


@router.message(ListingBuilder.requirements)
async def builder_requirements(message: Message, state: FSMContext):
    await store_step(message, state, "requirements", ListingBuilder.extras,
                     "Шаг 5/5. Дополнительные условия, комплектация, ограничения или бонусы. Если их нет, напишите «Нет».", 700)


@router.message(ListingBuilder.extras)
async def builder_extras(message: Message, state: FSMContext):
    extras = (message.text or "").strip()
    if not extras:
        return await message.answer("Напишите дополнительные условия или слово «Нет».", reply_markup=home_only())
    if len(extras) > 700:
        return await message.answer("Слишком длинный ответ. Максимум 700 символов.", reply_markup=home_only())
    data = await state.get_data()
    text = (
        f"📦 <b>{esc(data['title'])}</b>\n\n"
        f"⚙️ <b>Способ выдачи</b>\n{esc(data['delivery'])}\n\n"
        f"⏱ <b>Сроки</b>\n{esc(data['timing'])}\n\n"
        f"📌 <b>Что потребуется</b>\n{esc(data['requirements'])}\n\n"
        f"🎁 <b>Дополнительные условия</b>\n{esc(extras)}\n\n"
        "💬 Перед покупкой внимательно ознакомьтесь с описанием. Условия заказа фиксируйте в переписке на площадке."
    )
    await state.clear()
    await message.answer("✅ <b>Описание собрано</b>\n\n" + text + "\n\n<i>Скопируйте текст и проверьте его перед публикацией.</i>", reply_markup=seller_keyboard())


@router.callback_query(F.data == "menu:scripts")
async def scripts_menu(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for index, title in enumerate(BUYER_SCRIPTS):
        builder.button(text=title, callback_data=f"script:{index}")
    builder.button(text="🏠 Главное меню", callback_data="nav:home")
    builder.adjust(1)
    await callback.message.edit_text("💬 <b>Готовые ответы покупателям</b>\n\nВыберите ситуацию:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("script:"))
async def show_script(callback: CallbackQuery):
    keys = list(BUYER_SCRIPTS)
    try:
        key = keys[int(callback.data.split(":")[1])]
    except (ValueError, IndexError):
        return await callback.answer("Шаблон не найден.", show_alert=True)
    await callback.message.edit_text(
        f"💬 <b>{esc(key)}</b>\n\n<code>{esc(BUYER_SCRIPTS[key])}</code>\n\n"
        "<i>Перед отправкой убедитесь, что текст соответствует реальной ситуации.</i>",
        reply_markup=seller_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "knowledge:terms")
async def terms(callback: CallbackQuery):
    body = "\n\n".join(f"<b>{esc(name)}</b>\n{esc(description)}" for name, description in TERMS.items())
    await callback.message.edit_text("📖 <b>Словарь продавца</b>\n\n" + body, reply_markup=knowledge_keyboard())
    await callback.answer()


@router.callback_query(F.data == "knowledge:guides")
async def guides(callback: CallbackQuery):
    items = []
    for title, description, url in GUIDES:
        item = f"• <b>{esc(title)}</b>\n{esc(description)}"
        if url:
            item += f'\n<a href="{html.escape(url, quote=True)}">Открыть канал PlayFunPay</a>'
        items.append(item)
    await callback.message.edit_text("🗂 <b>Гайды и рубрики</b>\n\n" + "\n\n".join(items), reply_markup=knowledge_keyboard())
    await callback.answer()
