import json
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards import calculators_keyboard, percent_keyboard, tax_mode_keyboard, home_only
from config import settings
from states import ProfitFlow, ReverseFlow, TaxFlow
from services.finance_calc import parse_decimal, parse_percent, calculate_profit, calculate_reverse, calculate_tax
from utils import fmt_money, fmt_number

router = Router()


@router.callback_query(F.data == "menu:calculators")
async def menu_calculators(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🧮 <b>Финансовая панель продавца</b>\n\nСчитайте экономику сделки до публикации лота. Процент удержаний вводится вами и не считается официальным тарифом площадки.",
        reply_markup=calculators_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "calc:profit")
async def profit_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ProfitFlow.cost)
    await callback.message.edit_text("💰 <b>Чистая прибыль и ROI · Шаг 1/3</b>\n\nВведите себестоимость. Можно указать <code>0</code>, если вложений не было.", reply_markup=home_only())
    await callback.answer()


@router.message(ProfitFlow.cost)
async def profit_cost(message: Message, state: FSMContext):
    value = parse_decimal(message.text or "", allow_zero=True)
    if value is None:
        return await message.answer("Не удалось распознать сумму. Пример: <code>450</code>, <code>450,50 ₽</code> или <code>0</code>. Отрицательные числа не подходят.", reply_markup=home_only())
    await state.update_data(cost=str(value))
    await state.set_state(ProfitFlow.sale)
    await message.answer("Шаг 2/3. Введите цену продажи на FunPay в рублях:", reply_markup=home_only())


@router.message(ProfitFlow.sale)
async def profit_sale(message: Message, state: FSMContext):
    value = parse_decimal(message.text or "", allow_zero=False)
    if value is None:
        return await message.answer("Цена продажи должна быть положительным числом. Пример: <code>1299,90</code>.", reply_markup=home_only())
    await state.update_data(sale=str(value))
    await state.set_state(ProfitFlow.fee)
    await message.answer("Шаг 3/3. Выберите комиссию и дополнительные издержки:", reply_markup=percent_keyboard())


@router.callback_query(ProfitFlow.fee, F.data.startswith("percent:"))
async def profit_percent_callback(callback: CallbackQuery, state: FSMContext, db):
    raw = callback.data.split(":", 1)[1]
    if raw == "custom":
        await callback.message.answer("Введите свой процент от 0 до 99,99. Пример: <code>6,5</code>.", reply_markup=home_only())
        await callback.answer()
        return
    await finish_profit(callback.message, state, Decimal(raw), callback.from_user.id, db)
    await callback.answer()


@router.message(ProfitFlow.fee)
async def profit_percent_message(message: Message, state: FSMContext, db):
    fee = parse_percent(message.text or "")
    if fee is None:
        return await message.answer("Введите процент от 0 до 99,99. Можно использовать запятую: <code>6,5</code>.", reply_markup=home_only())
    await finish_profit(message, state, fee, message.from_user.id, db)


async def finish_profit(message, state, fee: Decimal, user_id: int, db):
    data = await state.get_data()
    result = calculate_profit(Decimal(data["cost"]), Decimal(data["sale"]), fee)
    status = {"profit": "🟢 Сделка прибыльная", "zero": "⚪ Сделка в ноль", "loss": "🔴 Сделка убыточная"}[result.status]
    roi_text = f"{fmt_number(result.roi_percent)}%" if result.roi_percent is not None else "не рассчитывается при нулевой закупке"
    text = (
        "📊 <b>Результат расчёта</b>\n\n"
        f"Закупка: <b>{fmt_money(result.cost)}</b>\n"
        f"Продажа: <b>{fmt_money(result.sale)}</b>\n"
        f"Удержания ({fmt_number(fee)}%): <b>{fmt_money(result.fee_amount)}</b>\n"
        f"После удержаний: <b>{fmt_money(result.net_revenue)}</b>\n\n"
        f"{status}\nЧистая прибыль: <b>{fmt_money(result.profit)}</b>\n"
        f"Маржинальность от выручки: <b>{fmt_number(result.margin_percent)}%</b>\n"
        f"ROI от закупки: <b>{roi_text}</b>\n\n"
        "<i>Учитываются введённые закупка и удержания. Дополнительные расходы включите в себестоимость.</i>"
    )
    await state.clear()
    await message.answer(text, reply_markup=calculators_keyboard())
    await db.save_calculation(user_id, "profit", json.dumps(data, ensure_ascii=False), text)
    await db.increment_usage(user_id, "calc")


@router.callback_query(F.data == "calc:reverse")
async def reverse_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ReverseFlow.target)
    await callback.message.edit_text("🎯 <b>Реверс-калькулятор</b>\n\nСколько рублей нужно получить чистыми после удержаний?", reply_markup=home_only())
    await callback.answer()


@router.message(ReverseFlow.target)
async def reverse_target(message: Message, state: FSMContext):
    amount = parse_decimal(message.text or "", allow_zero=False)
    if amount is None:
        return await message.answer("Введите положительную сумму. Например: <code>1500</code>.", reply_markup=home_only())
    await state.update_data(target=str(amount))
    await state.set_state(ReverseFlow.fee)
    await message.answer("Выберите процент удержаний:", reply_markup=percent_keyboard())


@router.callback_query(ReverseFlow.fee, F.data.startswith("percent:"))
async def reverse_percent_callback(callback: CallbackQuery, state: FSMContext, db):
    raw = callback.data.split(":", 1)[1]
    if raw == "custom":
        await callback.message.answer("Введите процент от 0 до 99,99.", reply_markup=home_only())
        await callback.answer()
        return
    await finish_reverse(callback.message, state, Decimal(raw), callback.from_user.id, db)
    await callback.answer()


@router.message(ReverseFlow.fee)
async def reverse_percent_message(message: Message, state: FSMContext, db):
    fee = parse_percent(message.text or "")
    if fee is None:
        return await message.answer("Процент должен быть от 0 до 99,99.", reply_markup=home_only())
    await finish_reverse(message, state, fee, message.from_user.id, db)


async def finish_reverse(message, state, fee, user_id, db):
    data = await state.get_data()
    result = calculate_reverse(Decimal(data["target"]), fee)
    text = (
        "🎯 <b>Цена для нужной суммы на руки</b>\n\n"
        f"Желаемая сумма: <b>{fmt_money(result.target)}</b>\n"
        f"Удержания: <b>{fmt_number(result.fee_percent)}%</b>\n"
        f"Рекомендуемая цена лота: <b>{fmt_money(result.listing_price)}</b>\n"
        f"Расчётное удержание: <b>{fmt_money(result.fee_amount)}</b>\n"
        f"Останется после удержания: <b>{fmt_money(result.net_amount)}</b>\n\n"
        "<i>Цена округлена вверх до копейки, чтобы не занизить целевую сумму.</i>"
    )
    await state.clear()
    await message.answer(text, reply_markup=calculators_keyboard())
    await db.save_calculation(user_id, "reverse", json.dumps(data, ensure_ascii=False), text)
    await db.increment_usage(user_id, "calc")


@router.callback_query(F.data == "calc:tax")
async def tax_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🎮 <b>Калькулятор внутриигрового налога</b>\n\nВыберите задачу:", reply_markup=tax_mode_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("taxmode:"))
async def tax_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await state.clear()
    await state.update_data(mode=mode)
    await state.set_state(TaxFlow.amount)
    prompt = "Сколько должен получить покупатель?" if mode == "receive" else "Сколько вы передаёте до удержания налога?"
    await callback.message.edit_text("🎮 <b>Игровой налог · Шаг 1/2</b>\n\n" + prompt, reply_markup=home_only())
    await callback.answer()


@router.message(TaxFlow.amount)
async def tax_amount(message: Message, state: FSMContext):
    amount = parse_decimal(message.text or "", allow_zero=False)
    if amount is None:
        return await message.answer("Введите положительное количество. Пример: <code>1000</code>.", reply_markup=home_only())
    await state.update_data(amount=str(amount))
    await state.set_state(TaxFlow.percent)
    await message.answer(
        f"Введите процент игрового налога от 0 до 99,99. По умолчанию: <b>{settings.default_game_tax_percent:g}%</b>.",
        reply_markup=home_only(),
    )


@router.message(TaxFlow.percent)
async def tax_percent(message: Message, state: FSMContext, db):
    tax = parse_percent(message.text or "")
    if tax is None:
        return await message.answer("Введите процент от 0 до 99,99.", reply_markup=home_only())
    data = await state.get_data()
    result = calculate_tax(Decimal(data["amount"]), tax, data["mode"])
    if result.mode == "receive":
        details = (f"Нужно передать: <b>{fmt_number(result.gross_amount, 6)}</b>\n"
                   f"Удержится налогом: <b>{fmt_number(result.tax_amount, 6)}</b>\n"
                   f"Покупатель получит: <b>{fmt_number(result.net_amount, 6)}</b>")
    else:
        details = (f"Вы передаёте: <b>{fmt_number(result.gross_amount, 6)}</b>\n"
                   f"Удержится налогом: <b>{fmt_number(result.tax_amount, 6)}</b>\n"
                   f"Дойдёт покупателю: <b>{fmt_number(result.net_amount, 6)}</b>")
    text = f"🎮 <b>Результат передачи</b>\n\nНалог: <b>{fmt_number(tax)}%</b>\n{details}\n\n<i>Модель предполагает, что налог удерживается из передаваемого количества.</i>"
    await state.clear()
    await message.answer(text, reply_markup=calculators_keyboard())
    await db.save_calculation(message.from_user.id, "game_tax", json.dumps(data, ensure_ascii=False), text)
    await db.increment_usage(message.from_user.id, "calc")


@router.callback_query(F.data == "calc:history")
async def history(callback: CallbackQuery, db):
    user = await db.get_user(callback.from_user.id)
    limit = 50 if user and user["role"] in {"vip", "admin"} else 5
    rows = await db.calculation_history(callback.from_user.id, limit)
    if not rows:
        text = "🧾 <b>История расчётов</b>\n\nПока здесь пусто. Первый расчёт появится автоматически."
    else:
        blocks = []
        for row in rows:
            line = next((x.replace("<b>", "").replace("</b>", "") for x in row["result"].splitlines()
                         if "Чистая прибыль:" in x or "Рекомендуемая цена" in x or "Покупатель получит:" in x), row["calc_type"])
            blocks.append(f"• <b>#{row['id']}</b> · {row['calc_type']} · {row['created_at'][:10]}\n  {line[:120]}")
        text = "🧾 <b>История расчётов</b>\n\n" + "\n\n".join(blocks)
        if limit == 5:
            text += "\n\n<i>Бесплатно доступны последние 5 операций. VIP открывает историю до 50 записей.</i>"
    await callback.message.edit_text(text, reply_markup=calculators_keyboard())
    await callback.answer()
