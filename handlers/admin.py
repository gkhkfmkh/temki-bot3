import asyncio
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from config import settings
from keyboards import admin_keyboard, broadcast_keyboard, broadcast_segments_keyboard, submission_keyboard, home_only
from states import AdminReplyFlow, BroadcastFlow
from utils import esc, short_date

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "⚙️ <b>PlayFunPay · Центр управления</b>\n\nВыберите действие:",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>PlayFunPay · Центр управления</b>\n\nВыберите действие:",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, db):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    stats = await db.statistics()
    text = (
        "📊 <b>Аналитика PlayFunPay</b>\n\n"
        f"Всего пользователей: <b>{stats['users']}</b>\n"
        f"Активны за 24 часа: <b>{stats['active24']}</b>\n"
        f"Активны за 7 дней: <b>{stats['active7']}</b>\n"
        f"VIP сейчас: <b>{stats['vip']}</b>\n"
        f"Заблокировано: <b>{stats['banned']}</b>\n\n"
        f"Расчётов: <b>{stats['calculations']}</b>\n"
        f"Проверок текста: <b>{stats['scans']}</b>\n"
        f"Обращений всего: <b>{stats['submissions']}</b>\n"
        f"Новых обращений: <b>{stats['new_submissions']}</b>\n"
        f"Успешных платежей: <b>{stats['payments']}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:submissions")
async def admin_submissions(callback: CallbackQuery, db):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    rows = await db.list_submissions("new", 10)
    if not rows:
        await callback.message.edit_text("📥 <b>Новых обращений нет</b>", reply_markup=admin_keyboard())
        return await callback.answer()
    await callback.message.edit_text(
        f"📥 Найдено новых обращений: <b>{len(rows)}</b>. Карточки отправлены отдельными сообщениями."
    )
    for row in rows:
        text = (
            f"📨 <b>Обращение #{row['id']}</b>\n"
            f"Категория: <b>{esc(row['category'])}</b>\n"
            f"Telegram ID: <code>{row['tg_id']}</code>\n"
            f"Дата: {esc(short_date(row['created_at']))}\n\n"
            f"{esc(row['payload_text'][:2500]) if row['payload_text'] else '<i>Без текста</i>'}"
        )
        await callback.message.answer(text, reply_markup=submission_keyboard(row["id"]))
        if row.get("file_id"):
            try:
                if row["file_type"] == "photo":
                    await callback.bot.send_photo(callback.from_user.id, row["file_id"])
                elif row["file_type"] == "document":
                    await callback.bot.send_document(callback.from_user.id, row["file_id"])
                elif row["file_type"] == "video":
                    await callback.bot.send_video(callback.from_user.id, row["file_id"])
                elif row["file_type"] == "animation":
                    await callback.bot.send_animation(callback.from_user.id, row["file_id"])
            except Exception:
                logger.exception("Не удалось отправить вложение обращения %s", row["id"])
    await callback.answer()


@router.callback_query(F.data.startswith("admin:review:"))
async def review_submission(callback: CallbackQuery, db):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    try:
        submission_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return await callback.answer("Некорректный ID обращения.", show_alert=True)
    row = await db.get_submission(submission_id)
    if not row:
        return await callback.answer("Обращение не найдено.", show_alert=True)
    await db.update_submission(submission_id, "reviewed")
    await db.audit(callback.from_user.id, "submission_reviewed", str(submission_id))
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отмечено как рассмотренное.")


@router.callback_query(F.data.startswith("admin:reply:"))
async def reply_start(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    try:
        submission_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        return await callback.answer("Некорректный ID обращения.", show_alert=True)
    row = await db.get_submission(submission_id)
    if not row:
        return await callback.answer("Обращение не найдено.", show_alert=True)
    await state.clear()
    await state.update_data(submission_id=submission_id, target_tg_id=row["tg_id"])
    await state.set_state(AdminReplyFlow.text)
    await callback.message.answer(
        f"✉️ Введите ответ пользователю по обращению #{submission_id}.\n"
        "Отмена: /cancel или кнопка ниже.", reply_markup=home_only()
    )
    await callback.answer()


@router.message(AdminReplyFlow.text)
async def reply_send(message: Message, state: FSMContext, db, bot):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Ответ должен содержать текст.", reply_markup=home_only())
    if len(text) > 3500:
        return await message.answer("Ответ слишком длинный. Максимум 3500 символов.", reply_markup=home_only())
    data = await state.get_data()
    try:
        await bot.send_message(
            data["target_tg_id"],
            "💬 <b>Ответ команды PlayFunPay</b>\n\n" + esc(text),
        )
    except TelegramForbiddenError:
        await db.set_banned(data["target_tg_id"], True)
        await message.answer("Пользователь заблокировал бота. Ответ не доставлен.")
        await state.clear()
        return
    await db.update_submission(data["submission_id"], "answered", text)
    await db.audit(message.from_user.id, "submission_answered", str(data["submission_id"]))
    await state.clear()
    await message.answer(f"✅ Ответ по обращению #{data['submission_id']} отправлен.")


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await state.set_state(BroadcastFlow.segment)
    await callback.message.answer(
        "📣 <b>Новая рассылка</b>\n\nВыберите сегмент аудитории. Пользовательские настройки уведомлений учитываются для новостей и советов:",
        reply_markup=broadcast_segments_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:segment:"))
async def broadcast_segment(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    segment = callback.data.rsplit(":", 1)[1]
    if segment not in {"all", "news", "tips"}:
        return await callback.answer("Неизвестный сегмент.", show_alert=True)
    await state.update_data(segment=segment)
    await state.set_state(BroadcastFlow.content)
    await callback.message.answer(
        "Отправьте текст или медиа-сообщение для рассылки. Перед отправкой будет предпросмотр и подтверждение.",
        reply_markup=home_only(),
    )
    await callback.answer("Сегмент выбран")


@router.message(BroadcastFlow.content)
async def broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    if not (message.text or message.photo or message.video or message.document or message.animation):
        return await message.answer("Поддерживаются текст, фото, видео, документ или GIF.", reply_markup=home_only())
    await state.update_data(source_chat_id=message.chat.id, source_message_id=message.message_id)
    await state.set_state(BroadcastFlow.confirm)
    await message.answer("👁 <b>Предпросмотр рассылки</b>")
    await message.copy_to(message.chat.id)
    await message.answer("Отправить это сообщение всем пользователям бота?", reply_markup=broadcast_keyboard())


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "broadcast:send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, db, bot):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Недостаточно прав.", show_alert=True)
    data = await state.get_data()
    if not data.get("source_message_id"):
        await state.clear()
        return await callback.answer("Нет сообщения для рассылки.", show_alert=True)

    await callback.message.edit_text("📣 Рассылка запущена. Итоговый отчёт появится после завершения.")
    user_ids = await db.get_broadcast_user_ids(data.get("segment", "all"))
    sent = blocked = failed = 0
    for user_id in user_ids:
        try:
            await bot.copy_message(user_id, data["source_chat_id"], data["source_message_id"])
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
            try:
                await bot.copy_message(user_id, data["source_chat_id"], data["source_message_id"])
                sent += 1
            except TelegramForbiddenError:
                blocked += 1
                await db.set_banned(user_id, True)
            except Exception:
                failed += 1
                logger.exception("Повторная отправка не удалась для %s", user_id)
        except TelegramForbiddenError:
            blocked += 1
            await db.set_banned(user_id, True)
        except Exception:
            failed += 1
            logger.exception("Ошибка рассылки для tg_id=%s", user_id)
        await asyncio.sleep(settings.broadcast_delay)

    await state.clear()
    await db.audit(callback.from_user.id, "broadcast_finished", f"sent={sent};blocked={blocked};failed={failed}")
    await callback.message.answer(
        "✅ <b>Рассылка завершена</b>\n\n"
        f"Получателей в базе: <b>{len(user_ids)}</b>\n"
        f"Успешно: <b>{sent}</b>\n"
        f"Заблокировали бота: <b>{blocked}</b>\n"
        f"Ошибки: <b>{failed}</b>",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()
