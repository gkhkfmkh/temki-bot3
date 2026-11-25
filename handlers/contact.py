from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import contact_keyboard, home_only, submission_keyboard
from states import SubmissionFlow
from config import settings
from utils import esc

router = Router()
LABELS = {"case": "Кейс / новость", "ad": "Реклама и партнёрство", "support": "Поддержка", "scam_report": "Подозрительная схема"}


@router.callback_query(F.data == "menu:contact")
async def contact_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📨 <b>Связь с PlayFunPay</b>\n\nВыберите тему обращения. Сообщения поступят команде на модерацию:", reply_markup=contact_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("contact:"))
async def contact_start(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    if category not in LABELS:
        return await callback.answer("Неизвестный тип обращения.", show_alert=True)
    await state.clear()
    await state.update_data(category=category)
    await state.set_state(SubmissionFlow.content)
    guidance = {
        "case": "Пришлите историю, идею или новость. Можно добавить скриншот. Не публикуйте чужие персональные данные.",
        "ad": "Опишите продукт, формат интеграции, сроки и ориентировочный бюджет. Оставьте контакт для обратной связи, если нужен.",
        "support": "Подробно опишите вопрос. Не отправляйте пароли, коды подтверждения и платёжные данные.",
        "scam_report": "Укажите ник или ссылку на профиль, хронологию и детали ситуации. Приложите скриншот. Не делайте публичных обвинений без доказательств.",
    }[category]
    await callback.message.edit_text(f"📨 <b>{LABELS[category]}</b>\n\n{guidance}\n\nОтправьте одно сообщение: текст, фото с подписью или документ с пояснением.", reply_markup=home_only())
    await callback.answer()


@router.message(SubmissionFlow.content)
async def contact_receive(message: Message, state: FSMContext, db, bot):
    data = await state.get_data()
    category = data["category"]
    text = message.text or message.caption or ""
    file_id = None
    file_type = None
    if message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, file_type = message.document.file_id, "document"
        if not text:
            text = f"Документ: {message.document.file_name or 'без названия'}"
    elif message.video:
        file_id, file_type = message.video.file_id, "video"
    elif message.animation:
        file_id, file_type = message.animation.file_id, "animation"
    if not text and not file_id:
        return await message.answer("Отправьте текст или файл с пояснением.", reply_markup=home_only())
    if len(text) > 3500:
        return await message.answer("Сообщение слишком длинное. Максимум 3500 символов.", reply_markup=home_only())
    if category == "scam_report" and len(text.strip()) < 15:
        return await message.answer("Для репорта добавьте контекст: что произошло, когда и с каким профилем.", reply_markup=home_only())

    submission_id = await db.create_submission(message.from_user.id, category, text, file_id, file_type)
    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    card = (
        f"📨 <b>Новое обращение #{submission_id}</b>\n\n"
        f"Категория: <b>{LABELS[category]}</b>\n"
        f"Пользователь: {esc(message.from_user.full_name)}\n"
        f"Username: {esc(username)}\nTelegram ID: <code>{message.from_user.id}</code>\n\n"
        f"{esc(text) if text else '<i>Текст не приложен</i>'}"
    )
    recipients = set(settings.admin_ids)
    if settings.submissions_chat_id is not None:
        recipients.add(settings.submissions_chat_id)
    for recipient in recipients:
        try:
            await bot.send_message(recipient, card, reply_markup=submission_keyboard(submission_id))
            if file_id:
                if file_type == "photo":
                    await bot.send_photo(recipient, file_id, caption=f"Вложение к обращению #{submission_id}")
                elif file_type == "document":
                    await bot.send_document(recipient, file_id, caption=f"Вложение к обращению #{submission_id}")
                elif file_type == "video":
                    await bot.send_video(recipient, file_id, caption=f"Вложение к обращению #{submission_id}")
                elif file_type == "animation":
                    await bot.send_animation(recipient, file_id, caption=f"Вложение к обращению #{submission_id}")
        except Exception:
            continue
    await state.clear()
    await message.answer(
        f"✅ <b>Обращение #{submission_id} принято</b>\n\nКоманда PlayFunPay рассмотрит сообщение. Ответ придёт сюда, если он потребуется.",
        reply_markup=home_only(),
    )
