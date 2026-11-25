from aiogram import Router
from aiogram.types import Message, CallbackQuery
from keyboards import home_keyboard
from config import settings

router = Router()


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "Я не распознал эту команду. Откройте главное меню и выберите нужный инструмент.",
        reply_markup=home_keyboard(message.from_user.id in settings.admin_ids),
    )


@router.callback_query()
async def unknown_callback(callback: CallbackQuery):
    await callback.answer("Эта кнопка устарела. Откройте главное меню ещё раз.", show_alert=True)
