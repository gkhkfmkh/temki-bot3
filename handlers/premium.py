import secrets
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery
from keyboards import vip_keyboard, home_only
from config import settings
from utils import esc

router = Router()


@router.callback_query(F.data == "menu:vip")
async def vip_page(callback: CallbackQuery, db):
    user = await db.get_user(callback.from_user.id)
    text = (
        "💎 <b>PlayFunPay VIP</b>\n\n"
        "VIP — способ поддержать развитие проекта и получить расширенные возможности кабинета.\n\n"
        "⭐ <b>Что входит:</b>\n"
        "• История расчётов: до 50 последних операций вместо 5.\n"
        "• Отметка VIP в профиле.\n"
        "• Продление доступа: новый период добавляется к текущему сроку.\n\n"
        f"Стоимость: <b>{settings.vip_price_stars} ⭐ за 30 дней</b>\n"
        "Оплата проходит внутри Telegram через Stars."
    )
    if user and user["vip_until"] and user["role"] in {"vip", "admin"}:
        text += f"\n\n✅ VIP действует до: <b>{esc(user['vip_until'][:10])}</b>"
    await callback.message.edit_text(text, reply_markup=vip_keyboard())
    await callback.answer()


@router.callback_query(F.data == "vip:buy")
async def vip_buy(callback: CallbackQuery, db, bot):
    payload = f"playfunpay_vip30_{callback.from_user.id}_{secrets.token_urlsafe(8)}"
    await db.create_payment(callback.from_user.id, payload, settings.vip_price_stars, "XTR")
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="PlayFunPay VIP — 30 дней",
            description="Расширенная история расчётов и поддержка развития PlayFunPay.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="VIP на 30 дней", amount=settings.vip_price_stars)],
        )
        await callback.answer("Счёт отправлен в личный чат с ботом.")
    except Exception:
        await callback.answer("Не удалось создать счёт. Попробуйте ещё раз позже.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, db):
    payment = await db.get_payment(query.invoice_payload)
    valid = bool(
        payment
        and payment["tg_id"] == query.from_user.id
        and payment["amount"] == query.total_amount
        and payment["currency"] == query.currency == "XTR"
        and payment["status"] == "pending"
    )
    if valid:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Счёт недействителен или уже обработан. Создайте новый в разделе VIP.")


@router.message(F.successful_payment)
async def successful_payment(message: Message, db):
    payment = message.successful_payment
    ok, detail = await db.complete_payment(
        payload=payment.invoice_payload,
        tg_id=message.from_user.id,
        amount=payment.total_amount,
        currency=payment.currency,
        telegram_charge_id=payment.telegram_payment_charge_id,
        days=30,
    )
    if not ok:
        await message.answer("Платёж получен, но активация требует проверки администратора. Напишите в поддержку и укажите ваш Telegram ID.")
        return
    user = await db.get_user(message.from_user.id)
    await message.answer(
        "💎 <b>PlayFunPay VIP активирован</b>\n\n"
        f"Доступ действует до: <b>{esc(user['vip_until'][:10])}</b>\n"
        "Спасибо за поддержку проекта. История расчётов расширена до 50 записей.",
        reply_markup=home_only(),
    )
